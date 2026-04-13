"""WebSocket conversation endpoint for bidirectional agent communication.

This replaces the SSE /message/stream endpoint with a proper WebSocket
that supports:
- Streaming AI tokens
- Tool call events
- Human-in-the-loop interrupts
- Cancel/approve/reject
- Middleware events (verbose mode)
"""

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.manager import run_agent_stream
from src.app_logging import get_logger
from src.http.ws_protocol import (
    AiTokenMessage,
    CancelMessage,
    DoneMessage,
    ErrorMessage,
    MiddlewareMessage,
    PongMessage,
    ReasoningMessage,
    ToolEndMessage,
    ToolStartMessage,
    parse_client_message,
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

            if isinstance(msg, PongMessage):
                await websocket.send_json(PongMessage().model_dump())
                continue

            if isinstance(msg, CancelMessage):
                await websocket.send_json(DoneMessage(response="Cancelled").model_dump())
                break

            if isinstance(msg, type) and msg.__name__ == "ApproveMessage":
                pass

            if not isinstance(msg, type(None)):
                user_id = getattr(msg, "user_id", user_id) or user_id
                verbose = getattr(msg, "verbose", verbose)

            if hasattr(msg, "type") and msg.type == "approve":
                if pending_interrupt:
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Approved: {pending_interrupt.get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_interrupt = None
                continue

            if hasattr(msg, "type") and msg.type == "reject":
                if pending_interrupt:
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Rejected: {pending_interrupt.get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_interrupt = None
                continue

            if hasattr(msg, "type") and msg.type == "edit_and_approve":
                if pending_interrupt:
                    await websocket.send_json(
                        DoneMessage(
                            response=f"Edited & approved: {pending_interrupt.get('tool', 'unknown')}"
                        ).model_dump()
                    )
                    pending_interrupt = None
                continue

            if not hasattr(msg, "content"):
                continue

            content = msg.content

            conversation = get_conversation_store(user_id)
            conversation.add_message("user", content)

            recent_messages = conversation.get_messages_with_summary(50)

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

            langgraph_messages.append(HumanMessage(content=content))

            ai_content_parts: list[str] = []
            tool_results: list[str] = []
            tool_metadata_list: list[dict] = []
            in_summarization = False

            try:
                async for chunk in run_agent_stream(
                    user_id=user_id,
                    messages=langgraph_messages,
                    message=content,
                    verbose=verbose,
                ):
                    if isinstance(chunk, dict) and "event" in chunk:
                        event_type = chunk.get("event", "")
                        name = chunk.get("name", "")
                        chunk_data = chunk.get("data", {})

                        if "Middleware" in name:
                            if "start" in event_type:
                                if "Summarization" in name:
                                    in_summarization = True
                                await websocket.send_json(
                                    MiddlewareMessage(name=name, event="start").model_dump()
                                )
                            elif "end" in event_type:
                                if "Summarization" in name:
                                    in_summarization = False
                                await websocket.send_json(
                                    MiddlewareMessage(name=name, event="end").model_dump()
                                )

                        elif "chat_model_stream" in event_type:
                            text_content = ""

                            if isinstance(chunk_data, dict) and "chunk" in chunk_data:
                                chunk_obj = chunk_data["chunk"]
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
                                    text_content = "".join(text_parts)
                                    reasoning = "".join(reasoning_parts)
                                    if reasoning:
                                        await websocket.send_json(
                                            ReasoningMessage(
                                                content=reasoning, session_id=session_id
                                            ).model_dump()
                                        )
                                elif hasattr(chunk_obj, "content"):
                                    text_content = chunk_obj.content
                                else:
                                    text_content = str(chunk_obj)
                            elif isinstance(chunk_data, dict) and "content" in chunk_data:
                                text_content = str(chunk_data.get("content", ""))
                            elif hasattr(chunk_data, "content"):
                                text_content = chunk_data.content

                            if text_content and not in_summarization:
                                ai_content_parts.append(text_content)
                                await websocket.send_json(
                                    AiTokenMessage(
                                        content=text_content, session_id=session_id
                                    ).model_dump()
                                )

                        elif "tool" in event_type:
                            if "start" in event_type:
                                tool_name = (
                                    chunk_data.get("name", name)
                                    if isinstance(chunk_data, dict)
                                    else name
                                )
                                call_id = str(uuid.uuid4())[:8]
                                tool_args = (
                                    chunk_data.get("input", {})
                                    if isinstance(chunk_data, dict)
                                    else {}
                                )
                                tool_metadata_list.append(
                                    {"tool_name": tool_name, "tool_call_id": call_id}
                                )
                                await websocket.send_json(
                                    ToolStartMessage(
                                        tool=tool_name,
                                        call_id=call_id,
                                        args=tool_args if isinstance(tool_args, dict) else {},
                                    ).model_dump()
                                )
                            elif "end" in event_type:
                                if isinstance(chunk_data, dict) and "output" in chunk_data:
                                    output = str(chunk_data.get("output", ""))[:500]
                                    tool_results.append(output)
                                    tool_name = (
                                        chunk_data.get("name", name)
                                        if isinstance(chunk_data, dict)
                                        else name
                                    )
                                    await websocket.send_json(
                                        ToolEndMessage(
                                            tool=tool_name,
                                            call_id=tool_metadata_list[-1]["tool_call_id"]
                                            if tool_metadata_list
                                            else "unknown",
                                            result_preview=output,
                                        ).model_dump()
                                    )

                    elif isinstance(chunk, dict):
                        chunk_type = getattr(chunk, "type", None) or chunk.get("type")
                        if chunk_type == "tool":
                            content = getattr(chunk, "content", None) or chunk.get("content")
                            if content:
                                tool_results.append(str(content))
                                await websocket.send_json(
                                    ToolEndMessage(
                                        tool="unknown",
                                        call_id="unknown",
                                        result_preview=str(content)[:500],
                                    ).model_dump()
                                )
                        elif chunk_type == "ai":
                            content = getattr(chunk, "content", None) or chunk.get("content", "")
                            if content and not in_summarization:
                                ai_content_parts.append(str(content))
                                await websocket.send_json(
                                    AiTokenMessage(
                                        content=str(content), session_id=session_id
                                    ).model_dump()
                                )

            except Exception as e:
                logger.error("ws.agent_error", {"error": str(e)}, user_id=user_id, channel="ws")
                await websocket.send_json(
                    ErrorMessage(message=str(e), code="AGENT_ERROR").model_dump()
                )
                continue

            response = "".join(ai_content_parts) if ai_content_parts else ""
            if tool_results and not response:
                response = "\n".join(tool_results)
            if not response:
                response = "Task completed."

            for i, tool_content in enumerate(tool_results):
                tool_meta = (
                    tool_metadata_list[i]
                    if i < len(tool_metadata_list)
                    else {"tool_name": "unknown", "tool_call_id": ""}
                )
                conversation.add_message("tool", str(tool_content), metadata=tool_meta)

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
