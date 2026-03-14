"""HTTP server for Executive Assistant."""

from dotenv import load_dotenv

load_dotenv()

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from pydantic import BaseModel

from src.agents.manager import run_agent, run_agent_stream
from src.storage.conversation import get_conversation_store

# Store pending approvals: user_id -> interrupt data
_pending_approvals: dict[str, dict] = {}


class MessageRequest(BaseModel):
    message: str
    model: str | None = None
    user_id: str | None = None
    verbose: bool = False  # Include middleware events in stream


class MessageResponse(BaseModel):
    response: str
    error: str | None = None
    verbose_data: dict | None = None  # Additional info when verbose=True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager."""
    from src.agents.manager import get_agent_pool, get_model
    from src.agents.subagent.scheduler import get_scheduler
    from src.tools.email.sync import start_interval_sync, stop_interval_sync

    get_model()  # Initialize model on startup
    await get_agent_pool("default")  # Pre-warm pool

    # Start email sync scheduler
    await start_interval_sync()

    # Start subagent scheduler
    get_scheduler()

    print("HTTP server ready")
    yield

    # Cleanup
    await stop_interval_sync()


app = FastAPI(
    title="Executive Assistant",
    description="HTTP API for Executive Assistant",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.get("/health/ready")
async def ready():
    """Readiness check."""
    return {"status": "ready"}


@app.get("/conversation")
async def get_conversation(user_id: str = "default", limit: int = 100):
    """Get conversation history."""
    from src.storage.conversation import get_conversation_store

    conversation = get_conversation_store(user_id)
    messages = conversation.get_recent_messages(limit)

    return {
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.ts.isoformat() if m.ts else None}
            for m in messages
        ]
    }


@app.delete("/conversation")
async def clear_conversation(user_id: str = "default"):
    """Clear conversation history."""
    import sqlite3
    from src.storage.conversation import get_conversation_store

    conversation = get_conversation_store(user_id)
    conn = sqlite3.connect(conversation.messages_db_path)
    conn.execute("DELETE FROM messages")
    conn.commit()
    conn.close()

    return {"status": "cleared", "user_id": user_id}


@app.post("/message", response_model=MessageResponse)
async def handle_message(req: MessageRequest) -> MessageResponse:
    """Send a message to the agent."""
    try:
        user_id = req.user_id or "default"
        msg_content = req.message.strip().lower()

        # Check if this is a response to a pending approval
        if user_id in _pending_approvals and msg_content in ("approve", "reject", "edit"):
            pending = _pending_approvals.pop(user_id)
            tool_name = pending["tool_name"]
            tool_args = pending["tool_args"]

            # Auto-fill missing required args
            if "user_id" not in tool_args or not tool_args.get("user_id"):
                tool_args["user_id"] = user_id

            if msg_content == "reject":
                return MessageResponse(response=f"❌ {tool_name} rejected.")

            # Execute the tool directly
            if tool_name == "email_delete":
                from src.tools.email import email_delete

                result = email_delete.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            if tool_name == "delete_file":
                from src.tools.filesystem import delete_file

                result = delete_file.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            return MessageResponse(response=f"Unknown tool: {tool_name}")

        msg_content = req.message  # Restore original message
        conversation = get_conversation_store(user_id)
        conversation.add_message("user", msg_content)
        recent_messages = conversation.get_recent_messages(50)

        langgraph_messages = [
            HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            for m in recent_messages
        ] + [HumanMessage(content=msg_content)]

        from src.app_logging import get_logger, timer

        logger = get_logger()

        verbose_data: dict | None = None
        response: str = ""

        with timer(
            "agent",
            {"message": msg_content, "user_id": user_id, "verbose": req.verbose},
            channel="http",
        ):
            with propagate_attributes(user_id=user_id):
                if req.verbose:
                    # Use streaming with verbose=True to collect middleware events
                    middleware_events = []
                    tool_events = []
                    ai_content = []

                    async for chunk in run_agent_stream(
                        user_id=user_id,
                        messages=langgraph_messages,
                        message=msg_content,
                        verbose=True,
                    ):
                        # Parse verbose events
                        if isinstance(chunk, dict) and "event" in chunk:
                            event_type = chunk.get("event", "")
                            name = chunk.get("name", "")

                            if "Middleware" in name:
                                middleware_events.append(
                                    {
                                        "name": name,
                                        "event": event_type,
                                    }
                                )
                            elif "tool" in event_type:
                                data = chunk.get("data", {})
                                if "start" in event_type:
                                    tool_name = (
                                        data.get("name", name) if isinstance(data, dict) else name
                                    )
                                    tool_events.append({"tool": tool_name, "stage": "start"})
                                elif (
                                    "end" in event_type
                                    and isinstance(data, dict)
                                    and "output" in data
                                ):
                                    tool_events.append(
                                        {
                                            "tool": data.get("name", name),
                                            "stage": "end",
                                            "output": str(data.get("output", ""))[:200],
                                        }
                                    )
                            elif "chat_model_stream" in event_type:
                                data = chunk.get("data", {})
                                content = ""
                                if isinstance(data, dict):
                                    if "chunk" in data:
                                        chunk_obj = data["chunk"]
                                        content = (
                                            chunk_obj.content
                                            if hasattr(chunk_obj, "content")
                                            else str(chunk_obj)
                                        )
                                elif hasattr(data, "content"):
                                    content = data.content
                                if content:
                                    ai_content.append(content)

                    verbose_data = {
                        "middleware_events": middleware_events,
                        "tool_events": tool_events,
                    }

                    # Build response from accumulated content
                    if tool_events:
                        response = "\n".join(
                            [
                                t.get("output", f"Tool: {t.get('tool')}")
                                for t in tool_events
                                if t.get("stage") == "end"
                            ]
                        )
                    elif ai_content:
                        response = "".join(ai_content)

                    # If still no response, run agent normally to get response
                    if not response or response == "Task completed.":
                        result = await run_agent(
                            user_id=user_id,
                            messages=langgraph_messages,
                            message=msg_content,
                        )

                        # Extract response from result
                        messages = result.get("messages", [])
                        tool_results = []
                        for msg in messages:
                            msg_type = getattr(msg, "type", None)
                            if msg_type == "tool":
                                content = getattr(msg, "content", None)
                                if content:
                                    tool_results.append(content)

                        for msg in reversed(messages):
                            msg_type = getattr(msg, "type", None)
                            content = getattr(msg, "content", None)
                            if msg_type == "ai":
                                tool_calls = getattr(msg, "tool_calls", None)
                                if tool_calls and tool_results:
                                    response = "\n".join(tool_results)
                                    break
                                if tool_calls:
                                    response = f"Tool(s) executed: {', '.join([tc.get('name', 'unknown') for tc in tool_calls])}"
                                    break
                                if content and content.strip():
                                    response = content
                                    break

                        if not response:
                            response = "Task completed."

                    # Use result for interrupt check
                    result = {"messages": []}
                else:
                    result = await run_agent(
                        user_id=user_id,
                        messages=langgraph_messages,
                        message=msg_content,
                    )

        # Check for human-in-the-loop interrupt
        if "__interrupt__" in result:
            interrupt_obj = result["__interrupt__"][0]
            interrupt_value = getattr(interrupt_obj, "value", None)

            if interrupt_value and isinstance(interrupt_value, dict):
                action_requests = interrupt_value.get("action_requests", [{}])[0]
                review_configs = interrupt_value.get("review_configs", [{}])[0]

                tool_name = action_requests.get("name", "unknown")
                tool_args = action_requests.get("args", {})
                allowed = review_configs.get("allowed_decisions", [])

                _pending_approvals[user_id] = {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                }

                response = f"⚠️ **{tool_name.replace('_', ' ').title()} - Approval Required**\n\n"
                response += f"Tool: `{tool_name}`\n"
                response += f"Arguments: `{tool_args}`\n\n"
                response += f"Available actions: {', '.join(['`' + a + '`' for a in allowed])}\n\n"
                response += "Reply with one of the above actions to proceed."

                return MessageResponse(response=response)

        messages = result.get("messages", [])

        tool_results = []

        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                content = getattr(msg, "content", None)
                if content:
                    tool_results.append(content)

        for msg in reversed(messages):
            msg_type = getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            if msg_type == "ai":
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls and tool_results:
                    # Include tool results in response
                    response = "\n".join(tool_results)
                    break
                if tool_calls:
                    tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                    response = f"Tool(s) executed: {', '.join(tool_names)}"
                    break
                if content and content.strip():
                    response = content
                    break

            if not response:
                response = "Task completed."

            logger.warning(
                "agent.response.final",
                {
                    "ai_content_count": len(ai_content) if "ai_content" in dir() else 0,
                    "response": response[:50],
                },
                user_id=user_id,
                channel="http",
            )

            conversation.add_message("assistant", response)

        logger.info(
            "agent.response",
            {"response": response, "verbose": req.verbose},
            user_id=user_id,
            channel="http",
        )

        return MessageResponse(response=response, verbose_data=verbose_data)

    except Exception as e:
        return MessageResponse(response="", error=str(e))


@app.post("/message/stream")
async def message_stream(req: MessageRequest):
    """Send a message and stream response using SSE."""
    try:
        user_id = req.user_id or "default"

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", req.message)
        recent_messages = conversation.get_recent_messages(50)

        langgraph_messages = [
            HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            for m in recent_messages
        ] + [HumanMessage(content=req.message)]

        from src.app_logging import get_logger

        logger = get_logger()

        async def generate():
            all_messages = []
            tool_results = []
            ai_content = []
            summarization_ran = False  # Track if summarization ran in this request

            in_summarization_stream = False  # Track if we're streaming summarization output
            async for chunk in run_agent_stream(
                user_id=user_id,
                messages=langgraph_messages,
                message=req.message,
                verbose=req.verbose,
            ):
                # LangChain astream_events format: {"event": "...", "name": "...", "data": {...}}
                # Convert to LangChain streaming format: {"type": "...", "ns": "...", "data": {...}}
                if isinstance(chunk, dict) and "event" in chunk:
                    event_type = chunk.get("event", "")
                    name = chunk.get("name", "")
                    data = chunk.get("data", {})
                    ns = name  # Use name as namespace

                    # Middleware events - track summarization to filter its output
                    if "Middleware" in name:
                        if "start" in event_type:
                            if "Summarization" in name:
                                in_summarization_stream = True
                            yield f"data: {json.dumps({'type': 'custom', 'ns': ns, 'data': {'content': f'Starting: {name}'}})}\n\n"
                        elif "end" in event_type:
                            if "Summarization" in name:
                                in_summarization_stream = False
                            yield f"data: {json.dumps({'type': 'custom', 'ns': ns, 'data': {'content': f'Finished: {name}'}})}\n\n"

                    # Model tokens (chat_model_stream) -> messages
                    elif "chat_model_stream" in event_type:
                        content = ""
                        if isinstance(data, dict):
                            if "chunk" in data:
                                chunk_obj = data["chunk"]
                                # Get content from AIMessageChunk
                                if hasattr(chunk_obj, "content_blocks"):
                                    # New content blocks format
                                    blocks = chunk_obj.content_blocks
                                    text_parts = [
                                        b.get("text", "") for b in blocks if b.get("type") == "text"
                                    ]
                                    reasoning_parts = [
                                        b.get("reasoning", "")
                                        for b in blocks
                                        if b.get("type") == "reasoning"
                                    ]
                                    content = "".join(text_parts)
                                    # Also yield reasoning if present
                                    reasoning = "".join(reasoning_parts)
                                    if reasoning:
                                        yield f"data: {json.dumps({'type': 'messages', 'ns': ns, 'data': {'content': f'[Reasoning] {reasoning}'}})}\n\n"
                                elif hasattr(chunk_obj, "content"):
                                    content = chunk_obj.content
                                else:
                                    content = str(chunk_obj)
                            elif "content" in data:
                                content = str(data.get("content", ""))
                        elif hasattr(data, "content"):
                            content = data.content

                        if content:
                            if in_summarization_stream:
                                pass  # Skip - filter out
                            else:
                                ai_content.append(content)
                                yield f"data: {json.dumps({'type': 'messages', 'ns': ns, 'data': {'content': content}})}\n\n"

                    # Tool events -> updates
                    elif "tool" in event_type:
                        if "start" in event_type:
                            tool_name = data.get("name", name) if isinstance(data, dict) else name
                            yield f"data: {json.dumps({'type': 'updates', 'ns': ns, 'data': {'content': f'Using tool: {tool_name}'}})}\n\n"
                        elif "end" in event_type:
                            if isinstance(data, dict) and "output" in data:
                                output = str(data.get("output", ""))[:500]
                                tool_results.append(output)
                                yield f"data: {json.dumps({'type': 'updates', 'ns': ns, 'data': {'content': output}})}\n\n"

                    all_messages.append(chunk)
                    continue

                # Fallback for other formats
                if isinstance(chunk, dict):
                    chunk_type = getattr(chunk, "type", None)
                    data = chunk.get("data")

                    if chunk_type == "messages" and data:
                        if isinstance(data, tuple) and len(data) == 2:
                            message_chunk, metadata = data
                            content = getattr(message_chunk, "content", "")
                            if content:
                                if not in_summarization_stream:
                                    ai_content.append(content)
                                    yield f"data: {json.dumps({'type': 'messages', 'ns': 'model', 'data': {'content': content}})}\n\n"

                    elif chunk_type == "updates" and data:
                        if isinstance(data, dict):
                            for node_name, state in data.items():
                                if isinstance(state, dict) and "messages" in state:
                                    for msg in state["messages"]:
                                        msg_type = getattr(msg, "type", None)
                                        msg_content = getattr(msg, "content", "")
                                        if msg_type == "tool":
                                            if msg_content:
                                                tool_results.append(msg_content)
                                                yield f"data: {json.dumps({'type': 'updates', 'ns': node_name, 'data': {'content': msg_content}})}\n\n"
                                        elif msg_type == "ai":
                                            if msg_content:
                                                if not in_summarization_stream:
                                                    ai_content.append(msg_content)
                                                    yield f"data: {json.dumps({'type': 'messages', 'ns': node_name, 'data': {'content': msg_content}})}\n\n"

                    all_messages.append(chunk)
                    continue

                # Legacy format handling - convert to v2 format
                chunk_type = getattr(chunk, "type", None)

                if chunk_type == "tool":
                    content = getattr(chunk, "content", None)
                    if content:
                        tool_results.append(content)
                        yield f"data: {json.dumps({'type': 'updates', 'ns': 'tools', 'data': {'content': content}})}\n\n"

                elif chunk_type == "ai":
                    content = getattr(chunk, "content", "")
                    if content:
                        if not in_summarization_stream:
                            ai_content.append(content)
                            yield f"data: {json.dumps({'type': 'messages', 'ns': 'model', 'data': {'content': content}})}\n\n"

                all_messages.append(chunk)

            # Build final response
            response = None

            # For verbose mode, use accumulated content (includes tool messages)
            if req.verbose:
                # In verbose mode, also include tool_results
                verbose_content = list(ai_content)

                if tool_results:
                    response = "\n".join(tool_results)
                elif verbose_content:
                    response = "".join(verbose_content)
                else:
                    response = "".join(ai_content)
            else:
                # For non-verbose mode, use ai_content (most reliable)
                # Get the last substantial chunk (the complete response)
                response = None
                if ai_content:
                    # Use in_summarization_stream flag to filter
                    if in_summarization_stream:
                        non_summary = [
                            c for c in ai_content if not c.strip().startswith("##") and len(c) > 3
                        ]
                    else:
                        non_summary = ai_content

                    # Find the last chunk that looks like a complete response (>20 chars)
                    for c in reversed(non_summary):
                        if len(c) > 20:
                            response = c
                            break

                    # If no good response found, join all non-summary unique chunks
                    if not response:
                        seen = set()
                        unique = []
                        for c in non_summary:
                            if c not in seen:
                                seen.add(c)
                                unique.append(c)
                        response = "".join(unique)

                # Fallback
                if not response:
                    response = "Task completed."

            if not response:
                response = "Task completed."

            # Deduplicate response for database
            if response and response.count(response[:20]) > 1:
                for check_len in range(20, len(response) // 2, 10):
                    prefix = response[:check_len]
                    first_end = response.find(prefix, check_len)
                    if first_end > check_len:
                        response = response[:first_end]
                        break

            # Don't save summarization output to database - use in_summarization_stream flag
            if in_summarization_stream:
                response = "Task completed."
            # Also fix the done event content if it contains summarization
            response_upper = response.upper() if response else ""
            if (
                "SESSION INTENT" in response_upper
                or "ARTIFACTS" in response_upper
                or "NEXT STEP" in response_upper
            ):
                response = "Task completed."

            conversation.add_message("assistant", response)
            logger.info("agent.response", {"response": response}, user_id=user_id, channel="http")

        import json

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run():
    """Run the HTTP server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
