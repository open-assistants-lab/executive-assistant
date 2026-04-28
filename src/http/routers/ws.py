"""WebSocket conversation endpoint for bidirectional agent communication.

This replaces the SSE /message/stream endpoint with a proper WebSocket
that supports:
- Streaming AI tokens
- Tool call events
- Human-in-the-loop interrupts
- Cancel/approve/reject
- Middleware events (verbose mode)

Uses the SDK AgentLoop for all agent execution.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.app_logging import get_logger
from src.http.ws_protocol import (
    ApproveMessage,
    CancelMessage,
    DoneMessage,
    EditAndApproveMessage,
    ErrorMessage,
    PingMessage,
    PongMessage,
    RejectMessage,
    parse_client_message,
)
from src.sdk.messages import Message
from src.sdk.runner import (
    _messages_from_conversation,
    get_sdk_loop,
    run_sdk_agent_stream,
)
from src.storage.messages import get_message_store

logger = get_logger()

router = APIRouter(tags=["websocket"])


async def _run_agent_stream(
    websocket: WebSocket,
    user_id: str,
    sdk_messages: list[Message],
    conversation,
    session_id: str = "",
    pending_ref: list | None = None,
) -> None:
    """Run the agent streaming loop and handle all chunk types."""
    import uuid as _uuid

    ai_content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_metadata_list: list[dict] = []

    try:
        async for chunk in run_sdk_agent_stream(
            user_id=user_id,
            messages=sdk_messages,
        ):
            canonical = chunk.canonical_type
            is_compat_alias = chunk.type != canonical

            if canonical == "text_delta" and chunk.content and not is_compat_alias:
                ai_content_parts.append(chunk.content)
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "text_start" and not is_compat_alias:
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "text_end" and not is_compat_alias:
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "tool_input_start" and not is_compat_alias:
                tool_name = chunk.tool or "unknown"
                call_id = chunk.call_id or str(_uuid.uuid4())[:8]
                tool_metadata_list.append(
                    {"tool_name": tool_name, "tool_call_id": call_id}
                )
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "tool_input_delta":
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "tool_input_end":
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "reasoning_start" and not is_compat_alias:
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "reasoning_delta" and not is_compat_alias:
                reasoning_parts.append(chunk.content or "")
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "reasoning_end" and not is_compat_alias:
                await websocket.send_json(chunk.to_ws_message())

            elif canonical == "tool_result" or chunk.type == "tool_result":
                tool_name = chunk.tool or "unknown"
                call_id = chunk.call_id or "unknown"
                result_preview = chunk.result_preview or ""
                from src.http.ws_protocol import ToolResultMessage

                await websocket.send_json(
                    ToolResultMessage(
                        tool=tool_name,
                        call_id=call_id,
                        result_preview=result_preview[:500],
                    ).model_dump()
                )

            elif chunk.type == "interrupt":
                if pending_ref is not None:
                    pending_ref[0] = {
                        "tool": chunk.tool or "unknown",
                        "call_id": chunk.call_id or "unknown",
                        "args": chunk.args or {},
                    }
                await websocket.send_json(chunk.to_ws_message())

            elif chunk.type == "done":
                response = (
                    "".join(ai_content_parts) if ai_content_parts else "Task completed."
                )

                reasoning_content = "".join(reasoning_parts) if reasoning_parts else None

                for tm in tool_metadata_list:
                    conversation.add_message("tool", "", metadata=tm)

                if reasoning_content:
                    conversation.add_message(
                        "reasoning", reasoning_content, metadata={"session_id": session_id}
                    )

                conversation.add_message(
                    "assistant",
                    response,
                    metadata={"stream": True, "session_id": session_id},
                )

                await websocket.send_json(
                    DoneMessage(
                        response=response,
                        tool_calls=[
                            {"tool": tm["tool_name"], "call_id": tm["tool_call_id"]}
                            for tm in tool_metadata_list
                        ],
                    ).model_dump()
                )

            elif chunk.type == "error":
                await websocket.send_json(
                    ErrorMessage(message=str(chunk.content), code="AGENT_ERROR").model_dump()
                )

    except Exception as e:
        logger.error(
            "ws.sdk_agent_error",
            {"error": str(e), "error_type": type(e).__name__},
            user_id=user_id,
            channel="ws",
        )
        await websocket.send_json(
            ErrorMessage(message=str(e), code="AGENT_ERROR").model_dump()
        )


@router.websocket("/ws/conversation")
async def ws_conversation(websocket: WebSocket):
    """WebSocket endpoint for bidirectional agent conversation.

    Protocol:
    - Client sends JSON messages with a 'type' field
    - Server streams back JSON messages with a 'type' field
    - See src/http/ws_protocol.py for all message types

    Client → Server:
        user_message: Send a chat message
        approve: Approve a pending tool call (HITL)
        reject: Reject a pending tool call (HITL)
        edit_and_approve: Edit tool args and approve (HITL)
        cancel: Cancel ongoing agent execution
        ping: Heartbeat

    Server → Client:
        ai_token: Streaming text token
        tool_start: Tool call started
        tool_end: Tool call completed
        interrupt: Agent requests human approval
        middleware: Middleware event (verbose mode)
        reasoning: Thinking token (reasoning models)
        done: Agent execution complete
        error: Error occurred
        pong: Heartbeat response
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())[:8]
    user_id = "default_user"
    verbose = False
    pending_container: list = [None]

    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    ErrorMessage(message="Invalid JSON", code="PARSE_ERROR").model_dump()
                )
                continue

            msg = parse_client_message(data)

            if msg is None:
                await websocket.send_json(
                    ErrorMessage(
                        message=f"Unknown message type: {data.get('type', 'missing')}",
                        code="UNKNOWN_TYPE",
                    ).model_dump()
                )
                continue

            if isinstance(msg, PingMessage):
                await websocket.send_json(PongMessage().model_dump())
                continue

            if isinstance(msg, ApproveMessage):
                if pending_container[0]:
                    tool_name = pending_container[0].get("tool", "unknown")
                    args = pending_container[0].get("args", {})
                    loop = await get_sdk_loop(user_id)
                    args_key = (tool_name, json.dumps(args, sort_keys=True))
                    loop._approved_tools.add(args_key)
                    pending_container[0] = None
                continue

            if isinstance(msg, RejectMessage):
                if pending_container[0]:
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Rejected: {pending_container[0].get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_container[0] = None
                else:
                    await websocket.send_json(
                        ErrorMessage(
                            message="No pending tool call to reject",
                            code="NO_PENDING_INTERRUPT",
                        ).model_dump()
                    )
                continue

            if isinstance(msg, EditAndApproveMessage):
                if pending_container[0]:
                    pending_container[0]["args"] = msg.edited_args
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Edited and approved: {pending_container[0].get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_container[0] = None
                else:
                    await websocket.send_json(
                        ErrorMessage(
                            message="No pending tool call to edit",
                            code="NO_PENDING_INTERRUPT",
                        ).model_dump()
                    )
                continue

            if isinstance(msg, CancelMessage):
                await websocket.send_json(DoneMessage(response="Cancelled").model_dump())
                break

            user_id = getattr(msg, "user_id", user_id) or user_id
            verbose = getattr(msg, "verbose", verbose)

            if not hasattr(msg, "content"):
                continue

            content = msg.content
            conversation = get_message_store(user_id)

            # If user types "approve" while a tool is pending, trigger retry
            if pending_container[0] and content.strip().lower() in ("approve", "yes", "accept"):
                tool_name = pending_container[0].get("tool", "unknown")
                args = pending_container[0].get("args", {})
                loop = await get_sdk_loop(user_id)
                args_key = (tool_name, json.dumps(args, sort_keys=True))
                loop._approved_tools.add(args_key)
                conversation.add_message("user", content)
                pending_container[0] = None
                # Fall through to normal agent run — agent will retry the tool

            import time
            t0 = time.monotonic()

            t1 = time.monotonic()

            conversation.add_message("user", content)
            t2 = time.monotonic()

            recent_messages = conversation.get_messages_with_summary(50)
            t3 = time.monotonic()

            sdk_messages = _messages_from_conversation(recent_messages)
            sdk_messages.append(Message.user(content))

            t4 = time.monotonic()
            logger.info(
                "ws.pre_loop_timing",
                {
                    "get_store": f"{t1 - t0:.3f}s",
                    "add_msg": f"{t2 - t1:.3f}s",
                    "get_msgs": f"{t3 - t2:.3f}s",
                    "convert": f"{t4 - t3:.3f}s",
                    "total": f"{t4 - t0:.3f}s",
                    "user_id": user_id,
                },
                user_id=user_id,
                channel="ws",
            )

            await _run_agent_stream(
                websocket, user_id, sdk_messages, conversation, session_id,
                pending_ref=pending_container,
            )

            # After stream finishes: if a tool was interrupted, wait for approval
            while pending_container[0] is not None:
                tool_name = pending_container[0].get("tool", "unknown")
                args = pending_container[0].get("args", {})
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                except (TimeoutError, WebSocketDisconnect):
                    pending_container[0] = None
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg_type = data.get("type", "")
                if msg_type in ("approve_tool", "approve"):
                    loop = await get_sdk_loop(user_id)
                    args_key = (tool_name, json.dumps(args, sort_keys=True))
                    loop._approved_tools.add(args_key)
                    pending_container[0] = None
                    # Retry with approval context
                    retry_msgs = _messages_from_conversation(
                        conversation.get_messages_with_summary(50)
                    )
                    retry_msgs.append(Message.user(f"approve: please proceed with {tool_name}"))
                    await _run_agent_stream(
                        websocket, user_id, retry_msgs, conversation, session_id,
                        pending_ref=pending_container,
                    )
                elif msg_type in ("reject_tool", "reject"):
                    pending_container[0] = None
                    break

    except WebSocketDisconnect:
        logger.info(
            "ws.disconnected",
            {"session_id": session_id, "user_id": user_id},
            user_id=user_id,
            channel="ws",
        )
    except Exception as e:
        logger.error(
            "ws.error", {"error": str(e), "session_id": session_id}, user_id=user_id, channel="ws"
        )
        try:
            await websocket.send_json(
                ErrorMessage(message=str(e), code="WEBSOCKET_ERROR").model_dump()
            )
        except Exception:
            pass
