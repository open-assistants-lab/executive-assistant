from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from src.commands import get_current_model
from src.utils import create_thread_id, get_last_displayable_message

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

router = APIRouter()


class MessageRequest(BaseModel):
    message: str = Field(..., description="User message to the agent")
    thread_id: str | None = Field(None, description="Thread ID for conversation continuity")
    user_id: str = Field(default="default", description="User identifier")
    stream: bool = Field(default=False, description="Whether to stream the response")


class MessageResponse(BaseModel):
    content: str
    thread_id: str
    tool_calls: list[dict] = Field(default_factory=list, description="Tool calls made during execution")
    todos: list[dict] = Field(default_factory=list, description="Current todo list (with status)")


class ConversationHistoryItem(BaseModel):
    thread_id: str = Field(..., description="Conversation/thread ID")
    modified_at: str = Field(..., description="Last modified timestamp (ISO-8601)")
    size_bytes: int = Field(..., description="File size in bytes")
    preview: str = Field("", description="Short preview snippet")


class ConversationHistoryListResponse(BaseModel):
    items: list[ConversationHistoryItem] = Field(default_factory=list)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    has_next: bool = Field(...)


class ConversationHistoryDetailResponse(BaseModel):
    thread_id: str
    line_offset: int = Field(..., ge=0)
    line_limit: int = Field(..., ge=1)
    total_lines: int = Field(..., ge=0)
    content: str


@router.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest) -> MessageResponse:
    """Send a message to the Executive Assistant and get a response.

    The Executive Assistant is a deep agent with:
    - Web tools (search, scrape, crawl, map)
    - Filesystem access (/user/, /shared/)
    - Subagents (coder, researcher, planner)
    - Todo list for planning
    - Persistent memory via Postgres checkpoints

    Returns tool_calls and todos if present in the execution.
    """
    from src.agent import create_ea_agent
    from src.config.settings import get_settings

    settings = get_settings()
    model_override = get_current_model(request.user_id)
    thread_id = request.thread_id or create_thread_id(
        user_id=request.user_id,
        channel="api",
        reason="session",
    )

    async with create_ea_agent(
        settings,
        user_id=request.user_id,
        model_override=model_override,
    ) as agent:
        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "middleware_activities": [],
            },
            config={"configurable": {"thread_id": thread_id}},
            durability="async",
        )

    # Get last message, skipping internal summarization messages
    content = get_last_displayable_message(result)

    # Extract tool calls from messages
    tool_calls = []
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args"),
                })

    # Extract todos - prefer enhanced todos from TodoDisplayMiddleware
    # Fall back to original todos if enhanced ones not available
    todos = result.get("todos_display") or result.get("todos", [])

    return MessageResponse(
        content=content,
        thread_id=thread_id,
        tool_calls=tool_calls,
        todos=todos,
    )


@router.post("/message/stream")
async def send_message_stream(request: MessageRequest) -> StreamingResponse:
    """Send a message to the Executive Assistant and stream the response.

    Returns Server-Sent Events with:
    - Tool calls when invoked
    - Todo list updates
    - Middleware activities
    - Content chunks as they're generated
    - [THREAD:id] marker for thread ID
    - [DONE] marker when complete
    """
    import json

    from src.agent import create_ea_agent
    from src.config.settings import get_settings

    settings = get_settings()
    model_override = get_current_model(request.user_id)
    thread_id = request.thread_id or create_thread_id(
        user_id=request.user_id,
        channel="api",
        reason="session",
    )

    async def generate() -> AsyncGenerator[str]:
        seen_tool_calls = set()
        seen_todos = set()
        seen_middleware = set()
        content_progress: dict[str, str] = {}

        async with create_ea_agent(
            settings,
            user_id=request.user_id,
            model_override=model_override,
        ) as agent:
            async for chunk in agent.astream(
                {
                    "messages": [HumanMessage(content=request.message)],
                    "middleware_activities": [],
                },
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
                durability="async",
            ):
                # Stream tool calls
                if "messages" in chunk and chunk["messages"]:
                    last_msg = chunk["messages"][-1]

                    # Check for tool calls
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            tool_id = tool_call.get("id", "")
                            if tool_id and tool_id not in seen_tool_calls:
                                seen_tool_calls.add(tool_id)
                                tool_event = {
                                    "type": "tool_call",
                                    "tool": tool_call.get("name", "unknown"),
                                    "args": tool_call.get("args", {}),
                                    "id": tool_id,
                                }
                                yield f"data: {json.dumps(tool_event)}\n\n"

                    # Stream content
                    if hasattr(last_msg, "content") and last_msg.content:
                        # Skip summarization messages (they're for internal context, not display)
                        is_summary_message = (
                            last_msg.additional_kwargs.get("lc_source") == "summarization"
                            if hasattr(last_msg, "additional_kwargs")
                            else False
                        )
                        if is_summary_message:
                            continue

                        # Check if it's a tool result (not AI thinking)
                        is_tool_result = (
                            chunk.get("messages", [])[-2].type == "tool"
                            if len(chunk.get("messages", [])) > 1
                            else False
                        )

                        message_key = getattr(last_msg, "id", None) or str(len(chunk.get("messages", [])))
                        current_content = str(last_msg.content)
                        previous_content = content_progress.get(message_key, "")

                        if current_content == previous_content:
                            continue

                        if previous_content and current_content.startswith(previous_content):
                            payload = current_content[len(previous_content):]
                            is_delta = True
                        else:
                            payload = current_content
                            is_delta = False

                        content_progress[message_key] = current_content

                        content_event = {
                            "type": "content",
                            "content": payload,
                            "is_delta": is_delta,
                            "is_tool_result": is_tool_result,
                            "message_id": message_key,
                        }
                        yield f"data: {json.dumps(content_event)}\n\n"

                # Stream todo list updates
                if "todos" in chunk and chunk["todos"]:
                    todos = chunk["todos"]
                    # Create a hash of the todos to detect changes
                    todos_str = json.dumps(todos, sort_keys=True, default=str)
                    if todos_str not in seen_todos:
                        seen_todos.add(todos_str)
                        todo_event = {
                            "type": "todos",
                            "todos": todos,
                        }
                        yield f"data: {json.dumps(todo_event)}\n\n"

                # Stream middleware activities
                if "middleware_activities" in chunk and chunk["middleware_activities"]:
                    for activity in chunk["middleware_activities"]:
                        # Create a unique key for this activity
                        activity_key = json.dumps(
                            {"name": activity["name"], "status": activity["status"]},
                            sort_keys=True,
                        )
                        if activity_key not in seen_middleware:
                            seen_middleware.add(activity_key)
                            middleware_event = {
                                "type": "middleware",
                                "name": activity["name"],
                                "status": activity["status"],
                                "message": activity.get("message", ""),
                                "details": activity.get("details", {}),
                            }
                            yield f"data: {json.dumps(middleware_event)}\n\n"

        yield f"data: {json.dumps({'type': 'thread', 'thread_id': thread_id})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _safe_history_path(base_dir: Path, thread_id: str) -> Path:
    if not thread_id or "/" in thread_id or "\\" in thread_id or ".." in thread_id:
        raise HTTPException(status_code=400, detail="Invalid thread_id")
    path = (base_dir / f"{thread_id}.md").resolve()
    if base_dir.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid thread_id")
    return path


@router.get("/conversation_history", response_model=ConversationHistoryListResponse)
async def list_conversation_history(
    user_id: str = "default",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    query: str | None = Query(default=None, description="Filter by thread ID or content snippet"),
) -> ConversationHistoryListResponse:
    """List persisted conversation history summaries with pagination."""
    from src.config.settings import get_settings

    settings = get_settings()
    history_dir = settings.get_user_path(user_id) / ".conversation_history"
    if not history_dir.exists():
        return ConversationHistoryListResponse(
            items=[],
            page=page,
            page_size=page_size,
            total=0,
            has_next=False,
        )

    history_files = [p for p in history_dir.glob("*.md") if p.is_file()]
    history_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    normalized_query = query.strip().lower() if query else None
    if normalized_query:
        filtered: list[Path] = []
        for file_path in history_files:
            if normalized_query in file_path.stem.lower():
                filtered.append(file_path)
                continue
            try:
                if normalized_query in file_path.read_text(encoding="utf-8").lower():
                    filtered.append(file_path)
            except Exception:
                continue
        history_files = filtered

    total = len(history_files)
    start = (page - 1) * page_size
    end = start + page_size
    paged = history_files[start:end]

    items: list[ConversationHistoryItem] = []
    for file_path in paged:
        stat = file_path.stat()
        preview = ""
        try:
            preview = file_path.read_text(encoding="utf-8").strip().replace("\n", " ")[:200]
        except Exception:
            preview = ""
        items.append(
            ConversationHistoryItem(
                thread_id=file_path.stem,
                modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                size_bytes=int(stat.st_size),
                preview=preview,
            )
        )

    return ConversationHistoryListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_next=end < total,
    )


@router.get(
    "/conversation_history/{thread_id}",
    response_model=ConversationHistoryDetailResponse,
)
async def get_conversation_history_detail(
    thread_id: str,
    user_id: str = "default",
    line_offset: int = Query(default=0, ge=0),
    line_limit: int = Query(default=200, ge=1, le=2000),
) -> ConversationHistoryDetailResponse:
    """Get paginated lines for a single persisted conversation history file."""
    from src.config.settings import get_settings

    settings = get_settings()
    history_dir = settings.get_user_path(user_id) / ".conversation_history"
    if not history_dir.exists():
        raise HTTPException(status_code=404, detail="Conversation history not found")

    history_path = _safe_history_path(history_dir, thread_id)
    if not history_path.exists():
        raise HTTPException(status_code=404, detail="Conversation history not found")

    content = history_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    selected = lines[line_offset: line_offset + line_limit]
    return ConversationHistoryDetailResponse(
        thread_id=thread_id,
        line_offset=line_offset,
        line_limit=line_limit,
        total_lines=len(lines),
        content="\n".join(selected),
    )


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Text to summarize")
    max_length: int = Field(200, description="Maximum summary length in characters")


class SummarizeResponse(BaseModel):
    summary: str


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest) -> SummarizeResponse:
    """Summarize text using the configured summarization model.

    This is a utility endpoint that bypasses the agent for fast summarization.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from src.llm import get_summarization_llm

    llm = get_summarization_llm()

    messages = [
        SystemMessage(
            content=f"Summarize the following text in no more than {request.max_length} characters. "
            "Be concise and capture the key points."
        ),
        HumanMessage(content=request.text),
    ]

    response = await llm.ainvoke(messages)

    return SummarizeResponse(
        summary=response.content,
    )
