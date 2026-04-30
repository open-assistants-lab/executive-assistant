import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.app_logging import get_logger, timer
from src.http.models import MessageRequest, MessageResponse
from src.sdk.runner import (
    _messages_from_conversation,
    run_sdk_agent,
    run_sdk_agent_stream,
)
from src.storage.messages import get_message_store

_pending_approvals: dict[str, dict] = {}

router = APIRouter(tags=["conversation"])


@router.get("/conversation")
async def get_conversation(user_id: str = "default_user", limit: int = 100, workspace_id: str = "personal"):
    """Get conversation history."""
    conversation = get_message_store(user_id, workspace_id)
    messages = conversation.get_recent_messages(limit)

    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.ts.isoformat() if m.ts else None,
                "metadata": m.metadata,
            }
            for m in messages
        ]
    }


@router.delete("/conversation")
async def clear_conversation(user_id: str = "default_user"):
    """Clear conversation history."""
    conversation = get_message_store(user_id)
    conversation.clear()

    return {"status": "cleared", "user_id": user_id}


@router.post("/message", response_model=MessageResponse)
async def handle_message(req: MessageRequest) -> MessageResponse:
    """Send a message to the agent (SDK-powered)."""
    try:
        user_id = req.user_id or "default_user"
        msg_content = req.message.strip()

        if user_id in _pending_approvals and msg_content.lower() in ("approve", "reject", "edit"):
            pending = _pending_approvals.pop(user_id)
            tool_name = pending["tool_name"]

            if msg_content.lower() == "reject":
                return MessageResponse(response=f"{tool_name} rejected.")

            tool_args = pending.get("tool_args", {})
            if "user_id" not in tool_args:
                tool_args["user_id"] = user_id

            return MessageResponse(response=f"{tool_name} approved (execution pending).")

        conversation = get_message_store(user_id)
        conversation.add_message("user", req.message)

        recent_messages = conversation.get_messages_with_summary(50)
        sdk_messages = _messages_from_conversation(recent_messages)
        # recent_messages already includes the just-added user message

        logger = get_logger()
        verbose_data: dict | None = None
        tool_events: list[dict] = []
        ai_content_parts: list[str] = []

        with timer(
            "agent",
            {"message": msg_content, "user_id": user_id, "verbose": req.verbose},
            channel="http",
        ):
            if req.verbose:
                async for chunk in run_sdk_agent_stream(
                    user_id=user_id,
                    messages=sdk_messages,
                ):
                    if chunk.type == "ai_token" and chunk.content:
                        ai_content_parts.append(chunk.content)
                    elif (
                        chunk.canonical_type == "text_delta"
                        and chunk.type != "ai_token"
                        and chunk.content
                    ):
                        ai_content_parts.append(chunk.content)
                    elif chunk.type == "tool_start" and chunk.tool:
                        tool_events.append(
                            {"tool": chunk.tool, "stage": "start", "call_id": chunk.call_id}
                        )
                    elif chunk.type == "tool_input_start" and chunk.tool:
                        tool_events.append(
                            {"tool": chunk.tool, "stage": "start", "call_id": chunk.call_id}
                        )
                    elif chunk.type == "tool_end" and chunk.tool:
                        tool_events.append(
                            {
                                "tool": chunk.tool,
                                "stage": "end",
                                "output": (chunk.result_preview or "")[:200],
                            }
                        )
                    elif chunk.type == "tool_result" and chunk.tool:
                        tool_events.append(
                            {
                                "tool": chunk.tool,
                                "stage": "end",
                                "output": (chunk.result_preview or "")[:200],
                            }
                        )

                verbose_data = {"tool_events": tool_events}

                response = ""
                if tool_events:
                    tool_outputs = [
                        t["output"]
                        for t in tool_events
                        if t.get("stage") == "end" and t.get("output")
                    ]
                    if tool_outputs:
                        response = "\n".join(tool_outputs)
                if not response and ai_content_parts:
                    response = "".join(ai_content_parts)
                if not response:
                    if not tool_events:
                        result_messages = await run_sdk_agent(
                            user_id=user_id, messages=sdk_messages
                        )
                        last_ai = None
                        for m in reversed(result_messages):
                            if m.role == "assistant" and m.content:
                                last_ai = m
                                break
                        if last_ai:
                            response = (
                                last_ai.content
                                if isinstance(last_ai.content, str)
                                else str(last_ai.content)
                            )
                        else:
                            response = "Task completed."
                    else:
                        response = "Task completed."
            else:
                result_messages = await run_sdk_agent(user_id=user_id, messages=sdk_messages)

                tool_contents = []
                for m in result_messages:
                    if m.role == "tool" and m.content:
                        tool_contents.append(
                            m.content if isinstance(m.content, str) else str(m.content)
                        )
                        conversation.add_message(
                            "tool", str(m.content), metadata={"tool_name": m.name or "unknown"}
                        )

                response = ""
                last_ai = None
                for m in reversed(result_messages):
                    if m.role == "assistant" and m.content:
                        last_ai = m
                        break

                if (
                    last_ai
                    and last_ai.content
                    and (
                        last_ai.content
                        if isinstance(last_ai.content, str)
                        else str(last_ai.content)
                    ).strip()
                ):
                    response = (
                        last_ai.content
                        if isinstance(last_ai.content, str)
                        else str(last_ai.content)
                    )
                elif tool_contents:
                    response = "\n".join(tool_contents)

                if not response:
                    response = "Task completed."

        tool_calls_list = (
            [
                {"name": t["tool"], "tool_call_id": t.get("call_id", "")}
                for t in tool_events
                if t.get("stage") == "start"
            ]
            if req.verbose
            else None
        )

        assistant_metadata = None
        if verbose_data and verbose_data.get("tool_events"):
            assistant_metadata = {"tool_events": verbose_data["tool_events"]}
        conversation.add_message("assistant", response, metadata=assistant_metadata)

        logger.info(
            "agent.response",
            {"response": response[:80], "verbose": req.verbose},
            user_id=user_id,
            channel="http",
        )

        return MessageResponse(
            response=response,
            verbose_data=verbose_data,
            tool_calls=tool_calls_list,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return MessageResponse(response="", error=str(e))


@router.post("/message/stream")
async def message_stream(req: MessageRequest):
    """Send a message and stream response using SSE (SDK-powered)."""
    try:
        user_id = req.user_id or "default_user"

        conversation = get_message_store(user_id)
        conversation.add_message("user", req.message)

        recent_messages = conversation.get_messages_with_summary(50)
        sdk_messages = _messages_from_conversation(recent_messages)

        logger = get_logger()

        async def generate():
            ai_content_parts: list[str] = []
            tool_metadata_list: list[dict] = []
            tool_results: list[str] = []

            async for chunk in run_sdk_agent_stream(
                user_id=user_id,
                messages=sdk_messages,
            ):
                canonical = chunk.canonical_type

                if canonical == "text_delta" and chunk.content:
                    ai_content_parts.append(chunk.content)
                    yield f"data: {json.dumps({'type': 'messages', 'data': {'content': chunk.content}})}\n\n"

                elif canonical == "tool_input_start" and chunk.tool:
                    tool_metadata_list.append(
                        {"tool_name": chunk.tool, "tool_call_id": chunk.call_id or ""}
                    )
                    yield f"data: {json.dumps({'type': 'updates', 'data': {'content': f'Using tool: {chunk.tool}'}})}\n\n"

                elif canonical == "tool_result" and chunk.tool:
                    output = (chunk.result_preview or "")[:500]
                    if output:
                        tool_results.append(output)
                        yield f"data: {json.dumps({'type': 'updates', 'data': {'content': output}})}\n\n"

                elif canonical == "reasoning_delta" and chunk.content:
                    yield f"data: {json.dumps({'type': 'messages', 'data': {'content': f'[Reasoning] {chunk.content}'}})}\n\n"

                elif canonical == "reasoning_start":
                    yield f"data: {json.dumps({'type': 'updates', 'data': {'content': '[Thinking...]'}})}\n\n"

                elif chunk.type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'data': {'content': chunk.content}})}\n\n"

            response = "".join(ai_content_parts) if ai_content_parts else ""
            if not response and tool_results:
                response = "\n".join(tool_results)
            if not response:
                response = "Task completed."

            for tm in tool_metadata_list:
                conversation.add_message("tool", "", metadata=tm)

            conversation.add_message("assistant", response, metadata={"stream": True})
            logger.info(
                "agent.response", {"response": response[:80]}, user_id=user_id, channel="http"
            )

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
