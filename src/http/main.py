"""HTTP server for Executive Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from pydantic import BaseModel

from src.agents.manager import get_agent, get_checkpoint_manager
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
    get_agent("default")  # Initialize agent on startup
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
async def message(req: MessageRequest) -> MessageResponse:
    """Send a message to the agent."""
    try:
        user_id = req.user_id or "default"

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", req.message)
        recent_messages = conversation.get_recent_messages(50)

        checkpoint_manager = await get_checkpoint_manager(user_id)
        agent = get_agent(user_id, checkpointer=checkpoint_manager.checkpointer)

        from src.app_logging import get_logger

        logger = get_logger()
        handler = logger.langfuse_handler

        config = {"configurable": {"thread_id": user_id}}
        if handler:
            config["callbacks"] = [handler]

        from src.app_logging import timer

        with timer("agent", {"message": req.message, "user_id": user_id}, channel="http"):
            with propagate_attributes(user_id=user_id):
                result = await agent.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content=m.content)
                            if m.role == "user"
                            else AIMessage(content=m.content)
                            for m in recent_messages
                        ]
                        + [HumanMessage(content=req.message)]
                    },
                    config=config,
                )

        # Extract response - handle tool messages properly
        messages = result.get("messages", [])

        # Find the last AI message content (not tool message)
        response = None
        for msg in reversed(messages):
            msg_type = getattr(msg, "type", None)
            if msg_type == "ai":
                # Skip messages that are just tool calls
                if not getattr(msg, "tool_calls", None):
                    response = getattr(msg, "content", None)
                    break
            elif msg_type == "human":
                break

        if not response:
            response = "Task completed."

        conversation.add_message("assistant", response)

        logger.info(
            "agent.response",
            {"response": response},
            channel="http",
        )

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

        checkpoint_manager = await get_checkpoint_manager(user_id)
        agent = get_agent(user_id, checkpointer=checkpoint_manager.checkpointer)

        async def generate():
            result = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(content=m.content)
                        if m.role == "user"
                        else AIMessage(content=m.content)
                        for m in recent_messages
                    ]
                    + [HumanMessage(content=req.message)]
                }
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
