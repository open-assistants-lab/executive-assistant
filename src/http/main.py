"""HTTP server for Executive Assistant."""

import json

from dotenv import load_dotenv

load_dotenv()

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from pydantic import BaseModel, Field

from src.agents.manager import run_agent, run_agent_stream
from src.storage.messages import get_conversation_store

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
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None
    )  # Only populated when verbose=True


class MemorySearchRequest(BaseModel):
    query: str
    method: str = "hybrid"
    limit: int = 10
    user_id: str = "default"


class InsightSearchRequest(BaseModel):
    query: str
    method: str = "hybrid"
    limit: int = 5
    user_id: str = "default"


class SearchAllRequest(BaseModel):
    query: str
    memories_limit: int = 5
    messages_limit: int = 5
    insights_limit: int = 3
    user_id: str = "default"


class ConnectionRequest(BaseModel):
    memory_id: str
    target_id: str
    relationship: str = "relates_to"
    strength: float = 1.0
    user_id: str = "default"


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
    from src.storage.messages import get_conversation_store

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
    conversation = get_conversation_store(user_id)
    conversation.clear()

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
            if tool_name == "files_delete":
                from src.tools.filesystem import files_delete

                result = files_delete.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            return MessageResponse(response=f"Unknown tool: {tool_name}")

        msg_content = req.message  # Restore original message
        conversation = get_conversation_store(user_id)
        conversation.add_message("user", msg_content)
        recent_messages = conversation.get_messages_with_summary(50)

        # Convert DB messages to LangChain format
        # - user → HumanMessage
        # - assistant → AIMessage
        # - tool → ToolMessage (if we want to preserve tool call structure)
        # - summary → HumanMessage (treat as context, not AI response)
        langgraph_messages = []
        for m in recent_messages:
            if m.role == "user":
                langgraph_messages.append(HumanMessage(content=m.content))
            elif m.role == "summary":
                # Summary is context, treat as HumanMessage
                langgraph_messages.append(
                    HumanMessage(content=f"[SUMMARY OF PREVIOUS CONVERSATION]\n{m.content}")
                )
            else:
                # assistant and anything else → AIMessage
                langgraph_messages.append(AIMessage(content=m.content))

        langgraph_messages.append(HumanMessage(content=msg_content))

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

                    # Save tool messages from tool_events to DB
                    for tool_event in tool_events:
                        if tool_event.get("stage") == "end" and tool_event.get("output"):
                            tool_metadata = {
                                "tool_name": tool_event.get("tool", "unknown"),
                            }
                            conversation.add_message(
                                "tool", str(tool_event.get("output", "")), metadata=tool_metadata
                            )

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

                    # If still no response and no tool events were captured,
                    # run agent normally as a fallback. But if tool events
                    # already executed, do NOT re-invoke the agent (which would
                    # duplicate side effects like email_send, files_write, etc.)
                    if (not response or response == "Task completed.") and not tool_events:
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
                                tool_name = getattr(msg, "name", "unknown")
                                tool_call_id = getattr(msg, "tool_call_id", "")
                                if content:
                                    tool_results.append(content)
                                    # Save tool message as separate entry
                                    tool_metadata = {
                                        "tool_name": tool_name,
                                        "tool_call_id": tool_call_id,
                                    }
                                    conversation.add_message(
                                        "tool", str(content), metadata=tool_metadata
                                    )

                        for msg in reversed(messages):
                            msg_type = getattr(msg, "type", None)
                            content = getattr(msg, "content", None)
                            if msg_type == "ai":
                                # Priority: use AI's own content first
                                if content and content.strip():
                                    response = content
                                    break
                                tool_calls = getattr(msg, "tool_calls", None)
                                if tool_calls and tool_results:
                                    response = "\n".join(tool_results)
                                    break
                                if tool_calls:
                                    response = f"Tool(s) executed: {', '.join([tc.get('name', 'unknown') for tc in tool_calls])}"
                                    break

                        if not response:
                            response = "Task completed."

                    logger.warning(
                        "agent.response.final.verbose",
                        {"response": response[:50], "user_id": user_id},
                        user_id=user_id,
                        channel="http",
                    )

                    # Save assistant response to DB - with logging
                    logger.info(
                        "http.before_save.verbose",
                        {"user_id": user_id},
                        user_id=user_id,
                        channel="http",
                    )
                    # Note: Assistant message will be saved at the end of the function
                    # Don't save here to avoid duplicate

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

        # Debug: log message types
        msg_types = [getattr(m, "type", None) for m in messages]
        logger.debug("http.messages_types", {"types": msg_types}, user_id=user_id)

        tool_results = []

        # Save tool messages to DB
        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                content = getattr(msg, "content", None)
                tool_name = getattr(msg, "name", "unknown")
                tool_call_id = getattr(msg, "tool_call_id", "")
                if content:
                    tool_results.append(content)
                    # Save tool message as separate entry
                    tool_metadata = {"tool_name": tool_name, "tool_call_id": tool_call_id}
                    conversation.add_message("tool", str(content), metadata=tool_metadata)

        # Extract tool_calls from tool results since LangChain may not populate tool_calls properly
        tool_calls_list = []
        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                tool_name = getattr(msg, "name", "unknown")
                tool_call_id = getattr(msg, "tool_call_id", "")
                tool_calls_list.append(
                    {
                        "name": tool_name,
                        "tool_call_id": tool_call_id,
                        "id": tool_call_id,
                    }
                )

        # Deduplicate by tool_call_id
        seen_ids = set()
        unique_tool_calls = []
        for tc in tool_calls_list:
            if tc["tool_call_id"] not in seen_ids:
                seen_ids.add(tc["tool_call_id"])
                unique_tool_calls.append(tc)
        tool_calls_list = unique_tool_calls

        for msg in reversed(messages):
            msg_type = getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            if msg_type == "ai":
                # Priority: use AI's own content first (even if brief)
                if content and content.strip():
                    response = content
                    break
                # Only use tool results if AI has no content
                if tool_results:
                    response = "\n".join(tool_results)
                    break

            if not response:
                response = "Task completed."

        logger.warning(
            "agent.response.final",
            {
                "tool_results_count": len(tool_results),
                "response": response[:50],
                "user_id": user_id,
            },
            user_id=user_id,
            channel="http",
        )

        # Save assistant response to DB - only save middleware_events if there are actual events
        assistant_metadata = None
        if verbose_data and verbose_data.get("middleware_events"):
            # Only save if there are actual middleware events (verbose mode)
            assistant_metadata = {"middleware_events": verbose_data["middleware_events"]}
        # If no middleware events, don't save metadata at all (None)
        conversation.add_message("assistant", response, metadata=assistant_metadata)

        logger.info(
            "agent.response",
            {"response": response, "verbose": req.verbose},
            user_id=user_id,
            channel="http",
        )

        return MessageResponse(
            response=response,
            verbose_data=verbose_data,
            tool_calls=tool_calls_list if req.verbose else None,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return MessageResponse(response="", error=str(e))


@app.post("/message/stream")
async def message_stream(req: MessageRequest):
    """Send a message and stream response using SSE."""
    try:
        user_id = req.user_id or "default"

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", req.message)
        recent_messages = conversation.get_messages_with_summary(50)

        # Convert DB messages to LangChain format
        langgraph_messages = []
        for m in recent_messages:
            if m.role == "user":
                langgraph_messages.append(HumanMessage(content=m.content))
            elif m.role == "summary":
                langgraph_messages.append(
                    HumanMessage(content=f"[SUMMARY OF PREVIOUS CONVERSATION]\n{m.content}")
                )
            else:
                langgraph_messages.append(AIMessage(content=m.content))

        langgraph_messages.append(HumanMessage(content=req.message))

        from src.app_logging import get_logger

        logger = get_logger()

        async def generate():
            all_messages = []
            tool_results = []
            tool_metadata_list = []  # Track tool names and call IDs
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

                        # Check for subagent name in metadata (for subgraphs)
                        agent_name = (
                            data.get("metadata", {}).get("lc_agent_name")
                            if isinstance(data, dict)
                            else None
                        )
                        if agent_name:
                            ns = agent_name  # Use subagent name as namespace

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
                            tool_metadata_list.append({"tool_name": tool_name, "tool_call_id": ""})
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
                # For non-verbose mode, use ai_content ONLY - tool results shown via toasts
                response = None
                if ai_content:
                    # Use in_summarization_stream flag to filter
                    if in_summarization_stream:
                        non_summary = [
                            c for c in ai_content if not c.strip().startswith("##") and len(c) > 3
                        ]
                    else:
                        non_summary = ai_content

                    # Find the last substantial chunk (the complete response (>20 chars))
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

            # Save tool messages to DB (streaming endpoint)
            for i, tool_content in enumerate(tool_results):
                tool_meta = (
                    tool_metadata_list[i]
                    if i < len(tool_metadata_list)
                    else {"tool_name": "unknown", "tool_call_id": ""}
                )
                conversation.add_message("tool", str(tool_content), metadata=tool_meta)

            conversation.add_message("assistant", response, metadata={"stream": True})
            logger.info("agent.response", {"response": response}, user_id=user_id, channel="http")

        import json

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skills")
async def list_skills(user_id: str = "default"):
    """List all available skills."""
    from src.skills.registry import SkillRegistry

    registry = SkillRegistry(system_dir="src/skills", user_id=user_id)
    all_skills = registry.get_all_skills()
    system_skills = registry.get_system_skills()
    system_names = {s["name"] for s in system_skills}

    skills = []
    for s in all_skills:
        skills.append(
            {
                "name": s["name"],
                "description": s["description"],
                "is_system": s["name"] in system_names,
            }
        )

    return {"skills": skills}


@app.post("/skills")
async def create_skill(name: str, description: str, content: str, user_id: str = "default"):
    """Create a new skill."""
    from src.skills.storage import UserSkillStorage

    storage = UserSkillStorage(user_id)
    skill_dir = storage.base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")

    return {"status": "created", "name": name, "path": str(skill_dir)}


@app.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str, user_id: str = "default"):
    """Delete a user skill."""
    from src.skills.storage import UserSkillStorage

    storage = UserSkillStorage(user_id)
    skill_dir = storage.base_dir / skill_name
    if skill_dir.exists():
        import shutil

        shutil.rmtree(skill_dir)

    return {"status": "deleted", "name": skill_name}


@app.get("/subagents")
async def list_subagents(user_id: str = "default"):
    """List all subagents."""
    from src.agents.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagents = manager.list_all()

    # For now, all subagents are user-created (no system subagents)
    # This can be extended later if system subagents are added
    return {
        "subagents": [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "is_system": False,
            }
            for s in subagents
        ]
    }


@app.post("/subagents")
async def create_subagent(
    name: str,
    description: str = "",
    model: str | None = None,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    system_prompt: str | None = None,
    user_id: str = "default",
):
    """Create a new subagent."""
    from src.agents.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagent, result = manager.create(
        name=name,
        model=model,
        description=description,
        skills=skills,
        tools=tools,
        system_prompt=system_prompt,
    )

    if subagent is None:
        raise HTTPException(status_code=400, detail=result.get("errors", "Validation failed"))

    return {"status": "created", "name": name}


@app.delete("/subagents/{subagent_name}")
async def delete_subagent(subagent_name: str, user_id: str = "default"):
    """Delete a subagent."""
    import shutil

    from src.agents.subagent.manager import get_subagent_manager

    manager = get_subagent_manager(user_id)
    subagent_path = manager.base_path / subagent_name
    if subagent_path.exists():
        shutil.rmtree(subagent_path)

    return {"status": "deleted", "name": subagent_name}


@app.get("/memories")
async def list_memories(
    user_id: str = "default",
    domain: str | None = None,
    memory_type: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    scope: str | None = None,
    project_id: str | None = None,
):
    """List user memories/preferences."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    memories = store.list_memories(
        domain=domain,
        memory_type=memory_type,
        min_confidence=min_confidence,
        limit=limit,
        scope=scope,
        project_id=project_id,
    )

    return {
        "memories": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
                "source": m.source,
                "is_superseded": m.is_superseded,
                "superseded_by": m.superseded_by,
                "scope": m.scope,
                "project_id": m.project_id,
                "access_count": m.access_count,
                "structured_data": m.structured_data,
                "connections": [
                    {
                        "target_id": c.target_id,
                        "relationship": c.relationship,
                        "strength": c.strength,
                    }
                    for c in m.connections
                ],
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in memories
        ]
    }


@app.delete("/memories/{memory_id}")
async def remove_memory(memory_id: str, user_id: str = "default"):
    """Remove a memory."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    removed = store.remove_memory(memory_id)

    return {"status": "removed" if removed else "not_found", "id": memory_id}


@app.post("/memories/search")
async def search_memories(request: MemorySearchRequest):
    """Search memories using keyword, semantic, hybrid, or field search."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)

    if request.method == "fts":
        results = store.search_fts(request.query, limit=request.limit)
    elif request.method == "semantic":
        results = store.search_semantic(request.query, limit=request.limit)
    elif request.method == "field":
        results = store.search_field_semantic(request.query, limit=request.limit)
    else:
        results = store.search_hybrid(request.query, limit=request.limit)

    return {
        "query": request.query,
        "method": request.method,
        "results": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
                "scope": m.scope,
                "project_id": m.project_id,
            }
            for m in results
        ],
    }


@app.post("/memories/consolidate")
async def consolidate_memories(user_id: str = "default"):
    """Trigger memory consolidation manually."""
    from src.storage.consolidation import trigger_consolidation

    result = trigger_consolidation(user_id)
    return result


@app.get("/memories/insights")
async def list_insights(user_id: str = "default", limit: int = 20, domain: str | None = None):
    """List synthesized insights from memory consolidation."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    insights = store.list_insights(limit=limit, domain=domain)

    return {
        "insights": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
                "linked_memories": i.linked_memories,
                "is_superseded": i.is_superseded,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in insights
        ]
    }


@app.delete("/memories/insights/{insight_id}")
async def remove_insight(insight_id: str, user_id: str = "default"):
    """Remove an insight."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    removed = store.remove_insight(insight_id)

    return {"status": "removed" if removed else "not_found", "id": insight_id}


@app.post("/memories/insights/search")
async def search_insights(request: InsightSearchRequest):
    """Search insights using keyword or semantic search."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)

    if request.method == "fts":
        results = store.search_insights(request.query, limit=request.limit)
    elif request.method == "semantic":
        results = store.search_insights_semantic(request.query, limit=request.limit)
    else:
        results = store.search_insights(request.query, limit=request.limit)
        if not results:
            results = store.search_insights_semantic(request.query, limit=request.limit)

    return {
        "query": request.query,
        "method": request.method,
        "results": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
                "linked_memories": i.linked_memories,
            }
            for i in results
        ],
    }


@app.post("/memories/connections")
async def add_connection(request: ConnectionRequest):
    """Create a connection between two memories."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)
    store.add_connection(
        request.memory_id,
        request.target_id,
        relationship=request.relationship,
        strength=request.strength,
    )

    return {
        "status": "connected",
        "memory_id": request.memory_id,
        "target_id": request.target_id,
        "relationship": request.relationship,
        "strength": request.strength,
    }


@app.get("/memories/stats")
async def memory_stats(user_id: str = "default"):
    """Get memory system statistics."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    return store.get_stats()


@app.post("/memories/search-all")
async def search_all(request: SearchAllRequest):
    """Unified search across memories, messages, and insights."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(request.user_id)
    results = store.search_all(
        request.query,
        memories_limit=request.memories_limit,
        messages_limit=request.messages_limit,
        insights_limit=request.insights_limit,
        user_id=request.user_id,
    )

    return {
        "query": request.query,
        "memories": [
            {
                "id": m.id,
                "trigger": m.trigger,
                "action": m.action,
                "confidence": m.confidence,
                "domain": m.domain,
                "memory_type": m.memory_type,
            }
            for m in results["memories"]
        ],
        "insights": [
            {
                "id": i.id,
                "summary": i.summary,
                "domain": i.domain,
                "confidence": i.confidence,
            }
            for i in results["insights"]
        ],
        "messages": results["messages"],
    }


@app.get("/workspace/read/{path:path}")
async def read_workspace_file(path: str, user_id: str = "default"):
    """Read file - auto-mark as downloaded."""
    from pathlib import Path

    from src.tools.file_cache import get_file_cache
    from src.tools.filesystem import files_read

    # Read the file content
    result = files_read.invoke({"path": path, "user_id": user_id})

    # Auto-update sync status (mark as downloaded when opened)
    file_cache = get_file_cache(user_id)
    workspace_path = Path(f"data/users/{user_id}/workspace/{path}")
    server_modified = str(workspace_path.stat().st_mtime) if workspace_path.exists() else ""

    # Update sync status - file is now "synced" locally
    file_cache.update_sync(path, server_modified)

    return {"response": str(result), "path": path}


@app.get("/workspace/{path:path}")
async def list_workspace_files(path: str = "", user_id: str = "default"):
    """List files in workspace."""
    from src.tools.filesystem import files_list

    result = files_list.invoke({"path": path, "user_id": user_id})
    return {"response": str(result)}


@app.post("/workspace/{path:path}")
async def write_workspace_file(
    path: str,
    user_id: str = "default",
    request: dict | None = None,
):
    """Write file to workspace."""
    if request is None:
        return {"error": "content is required"}

    content = request.get("content", "")

    from src.tools.filesystem import files_write

    result = files_write.invoke({"path": path, "content": content, "user_id": user_id})
    return {"response": str(result)}


@app.delete("/workspace/{path:path}")
async def delete_workspace_file(path: str, user_id: str = "default"):
    """Delete file from workspace."""
    from src.tools.filesystem import files_delete

    result = files_delete.invoke({"path": path, "user_id": user_id})
    return {"response": str(result)}


# =============================================================================
# TODOS ENDPOINTS
# =============================================================================


@app.get("/todos")
async def list_todos(user_id: str = "default"):
    """List all todos."""
    from src.tools.todos.tools import todos_list

    result = todos_list.invoke({"user_id": user_id})
    return {"todos": result}


@app.post("/todos")
async def add_todo(
    content: str,
    priority: int | None = None,
    user_id: str = "default",
):
    """Add a new todo."""
    from src.tools.todos.tools import todos_add

    args = {"user_id": user_id, "content": content}
    if priority is not None:
        args["priority"] = str(priority)
    result = todos_add.invoke(args)
    return {"result": str(result)}


@app.put("/todos/{todo_id}")
async def update_todo(
    todo_id: str,
    content: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    user_id: str = "default",
):
    """Update a todo."""
    from src.tools.todos.tools import todos_update

    args = {"user_id": user_id, "todo_id": todo_id}
    if content is not None:
        args["content"] = content
    if status is not None:
        args["status"] = status
    if priority is not None:
        args["priority"] = priority
    result = todos_update.invoke(args)
    return {"result": str(result)}


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: str, user_id: str = "default"):
    """Delete a todo."""
    from src.tools.todos.tools import todos_delete

    result = todos_delete.invoke({"user_id": user_id, "todo_id": todo_id})
    return {"result": str(result)}


# =============================================================================
# CONTACTS ENDPOINTS
# =============================================================================


@app.get("/contacts")
async def list_contacts(user_id: str = "default"):
    """List all contacts."""
    from src.tools.contacts.tools import contacts_list

    result = contacts_list.invoke({"user_id": user_id})
    return {"contacts": result}


@app.get("/contacts/search")
async def search_contacts(query: str, user_id: str = "default"):
    """Search contacts."""
    from src.tools.contacts.tools import contacts_search

    result = contacts_search.invoke({"user_id": user_id, "query": query})
    return {"results": result}


@app.post("/contacts")
async def add_contact(
    email: str,
    name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    user_id: str = "default",
):
    """Add a new contact."""
    from src.tools.contacts.tools import contacts_add

    args = {"user_id": user_id, "email": email}
    if name is not None:
        args["name"] = name
    if phone is not None:
        args["phone"] = phone
    if company is not None:
        args["company"] = company
    result = contacts_add.invoke(args)
    return {"result": str(result)}


@app.put("/contacts/{contact_id}")
async def update_contact(
    contact_id: str,
    email: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    user_id: str = "default",
):
    """Update a contact."""
    from src.tools.contacts.tools import contacts_update

    args = {"user_id": user_id, "contact_id": contact_id}
    if email is not None:
        args["email"] = email
    if name is not None:
        args["name"] = name
    if phone is not None:
        args["phone"] = phone
    if company is not None:
        args["company"] = company
    result = contacts_update.invoke(args)
    return {"result": str(result)}


@app.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, user_id: str = "default"):
    """Delete a contact."""
    from src.tools.contacts.tools import contacts_delete

    result = contacts_delete.invoke({"user_id": user_id, "contact_id": contact_id})
    return {"result": str(result)}


# =============================================================================
# EMAIL ENDPOINTS
# =============================================================================


@app.get("/email/accounts")
async def list_email_accounts(user_id: str = "default"):
    """List connected email accounts."""
    from src.tools.email.account import email_accounts

    result = email_accounts.invoke({"user_id": user_id})
    return {"accounts": result}


class EmailConnectRequest(BaseModel):
    email: str
    password: str
    provider: str | None = None
    user_id: str = "default"


@app.post("/email/accounts")
async def connect_email(req: EmailConnectRequest):
    """Connect an email account."""
    from src.tools.email.account import email_connect

    args = {"user_id": req.user_id, "email": req.email, "password": req.password}
    if req.provider is not None:
        args["provider"] = req.provider
    result = email_connect.invoke(args)
    return {"result": str(result)}


@app.delete("/email/accounts/{account_name}")
async def disconnect_email(account_name: str, user_id: str = "default"):
    """Disconnect an email account."""
    from src.tools.email.account import email_disconnect

    result = email_disconnect.invoke({"user_id": user_id, "account_name": account_name})
    return {"result": str(result)}


@app.get("/email/messages")
async def list_emails(
    account_name: str = "default",
    limit: int = 20,
    folder: str = "INBOX",
    user_id: str = "default",
):
    """List emails from an account."""
    from src.tools.email.read import email_list

    result = email_list.invoke(
        {"user_id": user_id, "account_name": account_name, "limit": limit, "folder": folder}
    )
    return {"emails": result}


@app.get("/email/messages/{email_id}")
async def get_email(
    email_id: str,
    account_name: str = "default",
    user_id: str = "default",
):
    """Get a specific email."""
    from src.tools.email.read import email_get

    result = email_get.invoke(
        {"user_id": user_id, "account_name": account_name, "email_id": email_id}
    )
    return {"email": result}


@app.get("/email/search")
async def search_emails(
    query: str,
    account_name: str = "default",
    user_id: str = "default",
):
    """Search emails."""
    from src.tools.email.read import email_search

    result = email_search.invoke({"user_id": user_id, "account_name": account_name, "query": query})
    return {"results": result}


@app.post("/email/send")
async def send_email(
    to: str,
    subject: str,
    body: str,
    account_name: str = "default",
    user_id: str = "default",
):
    """Send an email."""
    from src.tools.email.send import email_send

    result = email_send.invoke(
        {
            "user_id": user_id,
            "account_name": account_name,
            "to": to,
            "subject": subject,
            "body": body,
        }
    )
    return {"result": str(result)}


# =============================================================================
# SUBAGENT JOB ENDPOINTS
# =============================================================================


@app.get("/subagents/jobs")
async def list_subagent_jobs(user_id: str = "default"):
    """List all subagent jobs (scheduled, running, completed, failed)."""
    from src.agents.subagent.scheduler import list_jobs

    jobs = list_jobs(user_id)
    return {"jobs": jobs}


@app.get("/subagents/jobs/{job_id}")
async def get_subagent_job(job_id: str):
    """Get status of a specific subagent job."""
    from src.agents.subagent.scheduler import get_job_status

    status = get_job_status(job_id)
    if status is None:
        return {"error": "Job not found"}, 404
    return {"job": status}


@app.post("/subagents/invoke")
async def invoke_subagent(
    name: str,
    task: str,
    user_id: str = "default",
):
    """Invoke a subagent to execute a task (async)."""
    from src.agents.subagent.tools import subagent_invoke

    result = subagent_invoke.invoke({"user_id": user_id, "name": name, "task": task})
    return {"result": str(result)}


@app.post("/subagents/batch")
async def batch_invoke_subagents(
    tasks: list[dict[str, str]],
    user_id: str = "default",
):
    """Batch invoke multiple subagents."""
    import json

    from src.agents.subagent.tools import subagent_batch

    result = subagent_batch.invoke({"user_id": user_id, "tasks": json.dumps(tasks)})
    return {"result": str(result)}


@app.post("/subagents/schedule")
async def schedule_subagent(
    name: str,
    task: str,
    run_at: str | None = None,
    cron: str | None = None,
    user_id: str = "default",
):
    """Schedule a subagent task (one-time or recurring)."""
    from src.agents.subagent.tools import subagent_schedule

    args = {"user_id": user_id, "name": name, "task": task}
    if run_at is not None:
        args["run_at"] = run_at
    if cron is not None:
        args["cron"] = cron
    result = subagent_schedule.invoke(args)
    return {"result": str(result)}


@app.delete("/subagents/jobs/{job_id}")
async def cancel_subagent_job(job_id: str, user_id: str = "default"):
    """Cancel a scheduled subagent job."""
    from src.agents.subagent.tools import subagent_schedule_cancel

    result = subagent_schedule_cancel.invoke({"user_id": user_id, "job_id": job_id})
    return {"result": str(result)}


# =============================================================================
# MEMORY ENDPOINTS
# =============================================================================


@app.post("/memories")
async def add_memory(
    trigger: str,
    action: str,
    domain: str = "general",
    memory_type: str = "fact",
    user_id: str = "default",
):
    """Add a new memory entry."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    memory = store.add_memory(
        trigger=trigger,
        action=action,
        domain=domain,
        memory_type=memory_type,
    )
    return {"memory": memory}


@app.put("/memories/{memory_id}")
async def update_memory(
    memory_id: str,
    trigger: str | None = None,
    action: str | None = None,
    confidence: float | None = None,
    user_id: str = "default",
):
    """Update a memory entry."""
    from src.storage.memory import get_memory_store

    store = get_memory_store(user_id)
    updated = store.update_memory(
        memory_id,
        new_trigger=trigger,
        new_action=action,
    )
    if updated is None:
        return {"error": "Memory not found"}, 404
    return {"result": "Memory updated"}


# =============================================================================
# SYNC ENDPOINTS
# =============================================================================


def run():
    """Run the HTTP server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)


@app.get("/sync/status")
async def get_sync_status(user_id: str = "default"):
    """Get sync status for all files."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    return {"status": cache.get_all()}


@app.post("/sync/pin/{path:path}")
async def pin_file(path: str, user_id: str = "default"):
    """Pin a file (keep downloaded)."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_pinned(path)
    return {"status": "pinned", "path": path}


@app.delete("/sync/pin/{path:path}")
async def unpin_file(path: str, user_id: str = "default"):
    """Unpin a file (remove from keep downloaded)."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_cloud_only(path)
    return {"status": "cloud_only", "path": path}


@app.post("/sync/download/{path:path}")
async def mark_downloaded(path: str, user_id: str = "default"):
    """Mark a file as downloaded."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_downloaded(path)
    return {"status": "downloaded", "path": path}


@app.get("/sync/stream")
async def sync_stream(user_id: str = "default"):
    """SSE stream for real-time file change notifications."""
    import asyncio
    from datetime import datetime
    from pathlib import Path

    from fastapi.responses import StreamingResponse

    from src.tools.file_cache import get_file_cache

    async def event_generator():
        cache = get_file_cache(user_id)
        workspace_path = Path(f"data/users/{user_id}/workspace")

        # Track all data stores
        skills_path = Path(f"data/users/{user_id}/skills")
        subagents_path = Path(f"data/users/{user_id}/subagents")

        last_state = {
            "workspace": {},
            "skills": {},
            "subagents": {},
        }

        while True:
            try:
                current_state = {
                    "workspace": {},
                    "skills": {},
                    "subagents": {},
                }

                # Watch workspace files
                if workspace_path.exists():
                    for f in workspace_path.rglob("*"):
                        if f.is_file():
                            rel_path = str(f.relative_to(workspace_path))
                            mtime = str(f.stat().st_mtime)
                            current_state["workspace"][rel_path] = mtime

                # Watch skills (stored as subdirectories with SKILL.md)
                if skills_path.exists():
                    for f in skills_path.glob("*/SKILL.md"):
                        skill_name = f.parent.name
                        current_state["skills"][skill_name] = str(f.stat().st_mtime)

                # Watch subagents (stored as subdirectories with config.yaml)
                if subagents_path.exists():
                    for f in subagents_path.glob("*/config.yaml"):
                        agent_name = f.parent.name
                        current_state["subagents"][agent_name] = str(f.stat().st_mtime)

                # Check for changes in each category
                for category in ["workspace", "skills", "subagents"]:
                    new_items = set(current_state[category].keys()) - set(
                        last_state[category].keys()
                    )
                    changed_items = []

                    for path, mtime in current_state[category].items():
                        if path not in last_state[category]:
                            changed_items.append(path)
                        elif last_state[category][path] != mtime:
                            changed_items.append(path)

                    if changed_items or new_items:
                        all_changed = list(set(changed_items) | set(new_items))
                        for item in all_changed:
                            data = {
                                "type": f"{category}_changed",
                                "category": category,
                                "path": item,
                                "action": "created" if item in new_items else "modified",
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                            yield f"data: {json.dumps(data)}\n\n"

                last_state = current_state
                await asyncio.sleep(3)

            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    run()
