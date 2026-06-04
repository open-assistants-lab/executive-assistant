import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.app_logging import get_logger, timer
from src.http.auth import require_auth
from src.http.models import MessageRequest, MessageResponse
from src.sdk.runner import (
    _messages_from_conversation,
    run_sdk_agent,
    run_sdk_agent_stream,
)
from src.storage.messages import get_message_store

_pending_approvals: dict[str, dict] = {}

router = APIRouter(tags=["conversation"])
logger = get_logger()

# ── Canvas HTML fence block parser ──────────────────────────────────────────

_CANVAS_FENCE = re.compile(
    r"```html:(canvas|skill-form|subagent-form)\s*\n(.*?)```",
    re.DOTALL,
)

CANVAS_SCHEMAS: dict[str, list[str]] = {
    "skill-form": ["name", "description", "content"],
    "subagent-form": ["name", "description", "model", "system_prompt"],
    "canvas": [],
}


def _extract_canvas(text: str, surface_id_prefix: str = "canvas") -> list[dict]:
    surfaces: list[dict] = []
    for i, match in enumerate(_CANVAS_FENCE.finditer(text)):
        surface_type = match.group(1)
        html = match.group(2).strip()
        if not html:
            continue
        surfaces.append({
            "surface_id": f"{surface_id_prefix}-{i}",
            "action": "create",
            "html": html,
            "surface_type": surface_type,
        })
    return surfaces


def _persist_tool_messages(conversation, tool_events: list[dict], workspace_id: str) -> None:
    for event in tool_events:
        output = event.get("output")
        if event.get("stage") != "end" or not output:
            continue
        conversation.add_message(
            "tool",
            str(output),
            metadata={
                "tool_name": event.get("tool") or event.get("tool_name") or "unknown",
                "tool_call_id": event.get("call_id") or event.get("tool_call_id") or "",
                "workspace_id": workspace_id,
            },
        )


@router.get("/conversation")
async def get_conversation(user_id: str = "default_user", limit: int = 100, workspace_id: str = "personal"):
    """Get conversation history filtered by workspace."""
    conversation = get_message_store(user_id, workspace_id)
    messages = conversation.get_recent_messages_for_workspace(workspace_id, limit)

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


def _filter_by_workspace(messages: list, workspace_id: str) -> list:
    """Filter messages to only those matching the given workspace_id."""
    if not workspace_id:
        return messages
    if workspace_id == "personal":
        return [
            m for m in messages
            if (m.metadata or {}).get("workspace_id", "personal") == "personal"
        ]
    return [
        m for m in messages
        if (m.metadata or {}).get("workspace_id", "personal") == workspace_id
    ]


@router.delete("/conversation")
async def clear_conversation(user_id: str = "default_user", workspace_id: str = "personal"):
    """Clear conversation history."""
    conversation = get_message_store(user_id, workspace_id)
    conversation.delete_messages_for_workspace(workspace_id)
    return {"status": "cleared", "user_id": user_id, "workspace_id": workspace_id}


@router.post("/message", response_model=MessageResponse)
async def handle_message(req: MessageRequest, _: None = Depends(require_auth)) -> MessageResponse:
    """Send a message to the agent (SDK-powered)."""
    try:
        user_id = req.user_id or "default_user"
        workspace_id = getattr(req, "workspace_id", "personal") or "personal"
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

        conversation = get_message_store(user_id, workspace_id)
        conversation.add_message("user", req.message, metadata={"workspace_id": workspace_id})

        recent_messages = conversation.get_messages_with_summary(50)
        recent_messages = _filter_by_workspace(recent_messages, workspace_id)
        sdk_messages = _messages_from_conversation(recent_messages)

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
                    workspace_id=workspace_id,
                    model=req.model,
                    provider_keys=req.provider_keys,
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
                                "call_id": chunk.call_id,
                                "output": (chunk.result_preview or "")[:2000],
                            }
                        )
                    elif chunk.type == "tool_result" and chunk.tool:
                        tool_events.append(
                            {
                                "tool": chunk.tool,
                                "stage": "end",
                                "call_id": chunk.call_id,
                                "output": (chunk.result_preview or "")[:2000],
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
                    response = "Task completed."

                _persist_tool_messages(conversation, tool_events, workspace_id)
            else:
                result_messages = await run_sdk_agent(
                    user_id=user_id, messages=sdk_messages, workspace_id=workspace_id,
                    model=req.model, provider_keys=req.provider_keys,
                )

                tool_contents = []
                for m in result_messages:
                    if m.role == "tool" and m.content:
                        tool_contents.append(
                            m.content if isinstance(m.content, str) else str(m.content)
                        )
                conversation.add_message(
                    "tool",
                    str(m.content),
                    metadata={"tool_name": m.name or "unknown", "workspace_id": workspace_id},
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

        canvas_blocks = _extract_canvas(response)

        tool_calls_list = None
        if req.verbose:
            seen_call_ids: set[str] = set()
            tool_calls_list = []
            for t in tool_events:
                call_id = t.get("call_id", "")
                tool_name = t.get("tool", "")
                if tool_name and call_id not in seen_call_ids:
                    seen_call_ids.add(call_id)
                    tool_calls_list.append({"name": tool_name, "tool_call_id": call_id})

        assistant_metadata: dict[str, Any] = {"workspace_id": workspace_id}
        if verbose_data and verbose_data.get("tool_events"):
            assistant_metadata["tool_events"] = verbose_data["tool_events"]
        conversation.add_message("assistant", response, metadata=assistant_metadata)

        logger.info(
            "agent.response",
            {"response": response[:80], "verbose": req.verbose},
            user_id=user_id,
            channel="http",
        )

        if verbose_data is None:
            verbose_data = {}
        verbose_data["canvas_blocks"] = canvas_blocks

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
async def message_stream(req: MessageRequest, _: None = Depends(require_auth)):
    """Send a message and stream response using SSE (SDK-powered)."""
    try:
        user_id = req.user_id or "default_user"
        workspace_id = getattr(req, "workspace_id", "personal") or "personal"

        conversation = get_message_store(user_id, workspace_id)
        conversation.add_message("user", req.message, metadata={"workspace_id": workspace_id})

        recent_messages = conversation.get_messages_with_summary(50)
        recent_messages = _filter_by_workspace(recent_messages, workspace_id)
        sdk_messages = _messages_from_conversation(recent_messages)

        logger = get_logger()

        async def generate():
            ai_content_parts: list[str] = []
            tool_metadata_list: list[dict] = []
            tool_results: list[dict] = []

            async for chunk in run_sdk_agent_stream(
                user_id=user_id,
                messages=sdk_messages,
                workspace_id=workspace_id,
                model=req.model,
                provider_keys=req.provider_keys,
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
                        tool_results.append(
                            {"tool_call_id": chunk.call_id or "", "output": output}
                        )
                        yield f"data: {json.dumps({'type': 'updates', 'data': {'content': output}})}\n\n"

                elif canonical == "reasoning_delta" and chunk.content:
                    yield f"data: {json.dumps({'type': 'messages', 'data': {'content': f'[Reasoning] {chunk.content}'}})}\n\n"

                elif canonical == "reasoning_start":
                    yield f"data: {json.dumps({'type': 'updates', 'data': {'content': '[Thinking...]'}})}\n\n"

                elif chunk.type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'data': {'content': chunk.content}})}\n\n"

            response = "".join(ai_content_parts) if ai_content_parts else ""
            if not response and tool_results:
                response = "\n".join(result["output"] for result in tool_results)
            if not response:
                response = "Task completed."

            canvas_blocks = _extract_canvas(response)
            for surface in canvas_blocks:
                yield f"data: {json.dumps({'type': 'canvas_update', 'data': surface})}\n\n"

            result_by_call_id = {
                result["tool_call_id"]: result["output"] for result in tool_results
            }
            for tm in tool_metadata_list:
                output = result_by_call_id.get(tm.get("tool_call_id", ""), "")
                tm["workspace_id"] = workspace_id
                conversation.add_message("tool", output, metadata=tm)

            conversation.add_message("assistant", response, metadata={"stream": True, "workspace_id": workspace_id})
            logger.info(
                "agent.response", {"response": response[:80]}, user_id=user_id, channel="http"
            )

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConversationImportRequest(BaseModel):
    user_id: str = "default_user"
    workspace_id: str = "personal"
    messages: list[dict]  # [{"role": "user", "content": "..."}, ...]


@router.post("/conversation/import")
async def import_conversation(req: ConversationImportRequest, _: None = Depends(require_auth)):
    """Bulk-import conversation history without triggering the agent loop.

    Used by evaluation frameworks (LongMemEval) to pre-load session data
    before asking a single question. Each message is added to the
    conversation store but NOT sent to the agent.
    """
    from src.storage.messages import get_message_store

    conversation = get_message_store(req.user_id, req.workspace_id)
    for msg in req.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content.strip():
            meta = msg.get("metadata")
            conversation.add_message(role, content, metadata=meta)
    return {"imported": len(req.messages)}



