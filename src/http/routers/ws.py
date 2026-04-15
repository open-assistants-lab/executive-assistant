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

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.app_logging import get_logger
from src.http.ws_protocol import (
    ApproveMessage,
    CancelMessage,
    DoneMessage,
    ErrorMessage,
    PingMessage,
    PongMessage,
    parse_client_message,
)
from src.sdk.messages import Message
from src.sdk.runner import (
    _messages_from_conversation,
    run_sdk_agent_stream,
)
from src.storage.messages import get_conversation_store

logger = get_logger()

router = APIRouter(tags=["websocket"])


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
    user_id = "default"
    verbose = False
    pending_interrupt: dict | None = None

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

            if isinstance(msg, CancelMessage):
                break

            if isinstance(msg, PingMessage):
                await websocket.send_json(PongMessage().model_dump())
                continue

            if isinstance(msg, ApproveMessage):
                if pending_interrupt:
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Approved: {pending_interrupt.get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_interrupt = None
                continue

            if isinstance(msg, CancelMessage):
                await websocket.send_json(DoneMessage(response="Cancelled").model_dump())
                break

            user_id = getattr(msg, "user_id", user_id) or user_id
            verbose = getattr(msg, "verbose", verbose)

            if not hasattr(msg, "content"):
                continue

            content = msg.content

            conversation = get_conversation_store(user_id)
            conversation.add_message("user", content)

            recent_messages = conversation.get_messages_with_summary(50)
            sdk_messages = _messages_from_conversation(recent_messages)
            sdk_messages.append(Message.user(content))

            ai_content_parts: list[str] = []
            tool_metadata_list: list[dict] = []

            try:
                async for chunk in run_sdk_agent_stream(
                    user_id=user_id,
                    messages=sdk_messages,
                ):
                    chunk_type = chunk.type
                    canonical = chunk.canonical_type

                    if chunk_type == "ai_token" and chunk.content:
                        ai_content_parts.append(chunk.content)
                        from src.http.ws_protocol import AiTokenMessage

                        await websocket.send_json(
                            AiTokenMessage(
                                content=chunk.content, session_id=session_id
                            ).model_dump()
                        )

                    elif chunk_type == "tool_start":
                        tool_name = chunk.tool or "unknown"
                        call_id = chunk.call_id or str(uuid.uuid4())[:8]
                        tool_args = chunk.args or {}
                        tool_metadata_list.append({"tool_name": tool_name, "tool_call_id": call_id})
                        from src.http.ws_protocol import ToolStartMessage

                        await websocket.send_json(
                            ToolStartMessage(
                                tool=tool_name,
                                call_id=call_id,
                                args=tool_args,
                            ).model_dump()
                        )

                    elif canonical == "text_delta" and chunk_type != "ai_token":
                        ai_content_parts.append(chunk.content)
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "text_start":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "text_end":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "tool_input_start" and chunk_type != "tool_start":
                        tool_name = chunk.tool or "unknown"
                        call_id = chunk.call_id or str(uuid.uuid4())[:8]
                        tool_metadata_list.append({"tool_name": tool_name, "tool_call_id": call_id})
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "tool_input_delta":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "tool_input_end":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "reasoning_start":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "reasoning_delta" and chunk_type == "reasoning":
                        from src.http.ws_protocol import ReasoningMessage

                        await websocket.send_json(
                            ReasoningMessage(
                                content=chunk.content, session_id=session_id
                            ).model_dump()
                        )

                    elif canonical == "reasoning_delta" and chunk_type != "reasoning":
                        await websocket.send_json(chunk.to_ws_message())

                    elif canonical == "reasoning_end":
                        await websocket.send_json(chunk.to_ws_message())

                    elif chunk_type == "tool_end":
                        tool_name = chunk.tool or "unknown"
                        call_id = chunk.call_id or "unknown"
                        result_preview = chunk.result_preview or ""
                        from src.http.ws_protocol import ToolEndMessage

                        await websocket.send_json(
                            ToolEndMessage(
                                tool=tool_name,
                                call_id=call_id,
                                result_preview=result_preview[:500],
                            ).model_dump()
                        )

                    elif chunk_type == "tool_result":
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

                    elif chunk_type == "interrupt":
                        interrupt_data = {
                            "tool": chunk.tool,
                            "call_id": chunk.call_id,
                            "args": chunk.args,
                            "allowed_actions": ["approve", "reject", "edit"],
                        }
                        pending_interrupt = interrupt_data
                        from src.http.ws_protocol import InterruptMessage

                        await websocket.send_json(
                            InterruptMessage(
                                call_id=chunk.call_id or "",
                                tool=chunk.tool or "",
                                args=chunk.args or {},
                            ).model_dump()
                        )

                    elif chunk_type == "done":
                        pass

                    elif chunk_type == "error":
                        await websocket.send_json(
                            ErrorMessage(message=chunk.content, code="AGENT_ERROR").model_dump()
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
                continue

            response = "".join(ai_content_parts) if ai_content_parts else "Task completed."

            for i, tm in enumerate(tool_metadata_list):
                tool_content = ""
                conversation.add_message(
                    "tool",
                    tool_content,
                    metadata=tm,
                )

            conversation.add_message(
                "assistant", response, metadata={"stream": True, "session_id": session_id}
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
