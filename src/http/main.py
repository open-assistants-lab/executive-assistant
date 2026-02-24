"""HTTP server for Executive Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from pydantic import BaseModel

from src.agents.manager import run_agent
from src.storage.conversation import get_conversation_store


class MessageRequest(BaseModel):
    message: str
    model: str | None = None
    user_id: str | None = None


class MessageResponse(BaseModel):
    response: str
    error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager."""
    from src.agents.manager import get_agent_pool, get_model

    get_model()  # Initialize model on startup
    await get_agent_pool("default")  # Pre-warm pool
    print("HTTP server ready")
    yield


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


@app.post("/message", response_model=MessageResponse)
async def handle_message(req: MessageRequest) -> MessageResponse:
    """Send a message to the agent."""
    try:
        user_id = req.user_id or "default"
        msg_content = req.message

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", msg_content)
        recent_messages = conversation.get_recent_messages(50)

        langgraph_messages = [
            HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            for m in recent_messages
        ] + [HumanMessage(content=msg_content)]

        from src.app_logging import get_logger, timer

        logger = get_logger()

        with timer("agent", {"message": msg_content, "user_id": user_id}, channel="http"):
            with propagate_attributes(user_id=user_id):
                result = await run_agent(
                    user_id=user_id,
                    messages=langgraph_messages,
                    message=msg_content,
                )

        messages = result.get("messages", [])

        response = None
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
                    tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                    response = f"Tool(s) executed: {', '.join(tool_names)}"
                    break
                if content and content.strip():
                    response = content
                    break

        if not response:
            response = "Task completed."

        conversation.add_message("assistant", response)

        logger.info("agent.response", {"response": response}, channel="http")

        return MessageResponse(response=response)

    except Exception as e:
        return MessageResponse(response="", error=str(e))


@app.post("/message/stream")
async def message_stream(req: MessageRequest):
    """Send a message and stream response."""
    try:
        user_id = req.user_id or "default"

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", req.message)
        recent_messages = conversation.get_recent_messages(50)

        langgraph_messages = [
            HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            for m in recent_messages
        ] + [HumanMessage(content=req.message)]

        async def generate():
            result = await run_agent(
                user_id=user_id,
                messages=langgraph_messages,
                message=req.message,
            )
            response = result["messages"][-1].content
            conversation.add_message("assistant", response)
            yield f"data: {response}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run():
    """Run the HTTP server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
