"""HTTP server for Executive Assistant."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.factory import get_agent_factory
from src.llm import create_model_from_config
from src.logging import get_logger
from langchain_core.messages import HumanMessage, AIMessage


class MessageRequest(BaseModel):
    message: str
    model: str | None = None


class MessageResponse(BaseModel):
    response: str
    error: str | None = None


# Global state
_agent = None
_model = None


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
        agent = get_agent()
        logger = get_logger()

        with logger.timer("agent", {"message": req.message}):
            result = await agent.ainvoke({"messages": [HumanMessage(content=req.message)]})

        response = result["messages"][-1].content
        return MessageResponse(response=response)

    except Exception as e:
        return MessageResponse(response="", error=str(e))


@app.post("/message/stream")
async def message_stream(req: MessageRequest):
    """Send a message and stream response."""
    try:
        agent = get_agent()

        async def generate():
            result = await agent.ainvoke({"messages": [HumanMessage(content=req.message)]})
            response = result["messages"][-1].content
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
