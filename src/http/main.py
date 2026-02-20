"""HTTP server for Executive Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langfuse import propagate_attributes
from pydantic import BaseModel

from src.agents.factory import get_agent_factory
from src.llm import create_model_from_config
from src.logging import get_logger
from src.storage.checkpoint import init_checkpoint_manager
from src.storage.conversation import get_conversation_store


class MessageRequest(BaseModel):
    message: str
    model: str | None = None
    user_id: str | None = None


class MessageResponse(BaseModel):
    response: str
    error: str | None = None


# Global state
_agent = None
_model = None
_checkpoint_managers: dict[str, any] = {}


async def get_checkpoint_manager(user_id: str):
    """Get or create checkpoint manager for user."""
    if user_id not in _checkpoint_managers:
        _checkpoint_managers[user_id] = await init_checkpoint_manager(user_id)
    return _checkpoint_managers[user_id]


def get_agent():
    """Get or create agent."""
    global _agent, _model
    if _agent is None:
        _model = create_model_from_config()
        model_name = getattr(_model, "model", "unknown")
        provider = getattr(_model, "_provider", "ollama")
        print(f"Provider: {provider}")
        print(f"Model: {model_name}")

        factory = get_agent_factory()
        _agent = factory.create(
            model=_model,
            tools=[],
            system_prompt="You are a helpful executive assistant.",
        )
        print("Agent ready")
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager."""
    get_agent()  # Initialize agent on startup
    print("HTTP server ready")
    yield
    # Cleanup on shutdown


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

        # Get conversation store and checkpoint manager
        conversation = get_conversation_store(user_id)
        from src.tools.progressive_disclosure import create_progressive_disclosure_tools

        conversation.add_message("user", req.message)
        recent_messages = conversation.get_recent_messages(50)

        checkpoint_manager = await get_checkpoint_manager(user_id)
        tools = create_progressive_disclosure_tools(user_id)

        logger = get_logger()
        handler = logger.langfuse_handler

        # Build config
        config = {"configurable": {"thread_id": user_id}}
        if handler:
            config["callbacks"] = [handler]

        # Create agent with checkpointer
        factory = get_agent_factory(checkpointer=checkpoint_manager.checkpointer)
        agent = factory.create(
            model=_model,
            tools=tools,
            system_prompt="You are a helpful executive assistant. Use the conversation history tools when user asks about past conversations.",
        )

        with logger.timer("agent", {"message": req.message, "user_id": user_id}, channel="http"):
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

        response = result["messages"][-1].content
        conversation.add_message("assistant", response)

        # Log response
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

        from src.tools.progressive_disclosure import create_progressive_disclosure_tools

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", req.message)
        recent_messages = conversation.get_recent_messages(50)

        checkpoint_manager = await get_checkpoint_manager(user_id)
        tools = create_progressive_disclosure_tools(user_id)

        factory = get_agent_factory(checkpointer=checkpoint_manager.checkpointer)
        agent = factory.create(
            model=_model,
            tools=tools,
            system_prompt="You are a helpful executive assistant. Use the conversation history tools when user asks about past conversations.",
        )

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
