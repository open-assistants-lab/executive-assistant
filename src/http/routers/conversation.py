import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes

from src.agents.manager import run_agent, run_agent_stream
from src.http.models import MessageRequest, MessageResponse
from src.storage.messages import get_conversation_store

_pending_approvals: dict[str, dict] = {}

router = APIRouter(tags=["conversation"])


@router.get("/conversation")
async def get_conversation(user_id: str = "default", limit: int = 100):
    """Get conversation history."""
    conversation = get_conversation_store(user_id)
    messages = conversation.get_recent_messages(limit)

    return {
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.ts.isoformat() if m.ts else None}
            for m in messages
        ]
    }


@router.delete("/conversation")
async def clear_conversation(user_id: str = "default"):
    """Clear conversation history."""
    conversation = get_conversation_store(user_id)
    conversation.clear()

    return {"status": "cleared", "user_id": user_id}


@router.post("/message", response_model=MessageResponse)
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
                from src.tools.filesystem.tools import files_delete

                result = files_delete.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            return MessageResponse(response=f"Unknown tool: {tool_name}")

        msg_content = req.message  # Restore original message
        conversation = get_conversation_store(user_id)
        conversation.add_message("user", msg_content)
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

                    if (not response or response == "Task completed.") and not tool_events:
                        result = await run_agent(
                            user_id=user_id,
                            messages=langgraph_messages,
                            message=msg_content,
                        )

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

                    logger.info(
                        "http.before_save.verbose",
                        {"user_id": user_id},
                        user_id=user_id,
                        channel="http",
                    )

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
            assistant_metadata = {"middleware_events": verbose_data["middleware_events"]}
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


@router.post("/message/stream")
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
            tool_metadata_list = []
            ai_content = []
            in_summarization_stream = False
            async for chunk in run_agent_stream(
                user_id=user_id,
                messages=langgraph_messages,
                message=req.message,
                verbose=req.verbose,
            ):
                if isinstance(chunk, dict) and "event" in chunk:
                    event_type = chunk.get("event", "")
                    name = chunk.get("name", "")
                    data = chunk.get("data", {})
                    ns = name

                    if "Middleware" in name:
                        if "start" in event_type:
                            if "Summarization" in name:
                                in_summarization_stream = True
                            yield f"data: {json.dumps({'type': 'custom', 'ns': ns, 'data': {'content': f'Starting: {name}'}})}\n\n"
                        elif "end" in event_type:
                            if "Summarization" in name:
                                in_summarization_stream = False
                            yield f"data: {json.dumps({'type': 'custom', 'ns': ns, 'data': {'content': f'Finished: {name}'}})}\n\n"

                    elif "chat_model_stream" in event_type:
                        content = ""

                        agent_name = (
                            data.get("metadata", {}).get("lc_agent_name")
                            if isinstance(data, dict)
                            else None
                        )
                        if agent_name:
                            ns = agent_name

                        if isinstance(data, dict):
                            if "chunk" in data:
                                chunk_obj = data["chunk"]
                                if hasattr(chunk_obj, "content_blocks"):
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
                                pass
                            else:
                                ai_content.append(content)
                                yield f"data: {json.dumps({'type': 'messages', 'ns': ns, 'data': {'content': content}})}\n\n"

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

                # Legacy format handling
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

            if req.verbose:
                verbose_content = list(ai_content)

                if tool_results:
                    response = "\n".join(tool_results)
                elif verbose_content:
                    response = "".join(verbose_content)
                else:
                    response = "".join(ai_content)
            else:
                response = None
                if ai_content:
                    if in_summarization_stream:
                        non_summary = [
                            c for c in ai_content if not c.strip().startswith("##") and len(c) > 3
                        ]
                    else:
                        non_summary = ai_content

                    for c in reversed(non_summary):
                        if len(c) > 20:
                            response = c
                            break

                    if not response:
                        seen = set()
                        unique = []
                        for c in non_summary:
                            if c not in seen:
                                seen.add(c)
                                unique.append(c)
                        response = "".join(unique)

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

            if in_summarization_stream:
                response = "Task completed."
            response_upper = response.upper() if response else ""
            if (
                "SESSION INTENT" in response_upper
                or "ARTIFACTS" in response_upper
                or "NEXT STEP" in response_upper
            ):
                response = "Task completed."

            for i, tool_content in enumerate(tool_results):
                tool_meta = (
                    tool_metadata_list[i]
                    if i < len(tool_metadata_list)
                    else {"tool_name": "unknown", "tool_call_id": ""}
                )
                conversation.add_message("tool", str(tool_content), metadata=tool_meta)

            conversation.add_message("assistant", response, metadata={"stream": True})
            logger.info("agent.response", {"response": response}, user_id=user_id, channel="http")

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
