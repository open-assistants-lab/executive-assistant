from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

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
    todos: list[str] = Field(default_factory=list, description="Current todo list")
    middleware_activities: list[dict] = Field(
        default_factory=list, description="Middleware activities during execution"
    )


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
    thread_id = request.thread_id or f"{request.user_id}-default"

    async with create_ea_agent(settings, user_id=request.user_id) as agent:
        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "middleware_activities": [],
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    last_message = result["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

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

    # Extract todos if available
    todos = result.get("todos", [])

    # Extract middleware activities if available
    middleware_activities = result.get("middleware_activities", [])

    return MessageResponse(
        content=content,
        thread_id=thread_id,
        tool_calls=tool_calls,
        todos=todos,
        middleware_activities=middleware_activities,
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
    thread_id = request.thread_id or f"{request.user_id}-default"

    async def generate() -> AsyncGenerator[str]:
        seen_tool_calls = set()
        seen_todos = set()
        seen_middleware = set()

        async with create_ea_agent(settings, user_id=request.user_id) as agent:
            async for chunk in agent.astream(
                {
                    "messages": [HumanMessage(content=request.message)],
                    "middleware_activities": [],
                },
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
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
                        # Check if it's a tool result (not AI thinking)
                        is_tool_result = (
                            chunk.get("messages", [])[-2].type == "tool"
                            if len(chunk.get("messages", [])) > 1
                            else False
                        )

                        content_event = {
                            "type": "content",
                            "content": last_msg.content,
                            "is_tool_result": is_tool_result,
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

    from src.config.settings import get_settings
    from src.llm import get_summarization_llm

    settings = get_settings()
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
