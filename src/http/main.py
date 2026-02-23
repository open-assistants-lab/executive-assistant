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
async def handle_message(req: MessageRequest) -> MessageResponse:
    """Send a message to the agent."""
    try:
        user_id = req.user_id or "default"
        msg_content = req.message

        conversation = get_conversation_store(user_id)
        conversation.add_message("user", msg_content)
        recent_messages = conversation.get_recent_messages(50)

        checkpoint_manager = await get_checkpoint_manager(user_id)
        checkpointer = checkpoint_manager.checkpointer

        # Create a fresh agent each time to avoid concurrent state issues
        from src.agents.manager import get_agent_factory, get_default_tools
        from src.config import get_settings
        from src.llm import create_model_from_config

        model = create_model_from_config()
        settings = get_settings()
        base_prompt = getattr(
            settings.agent, "system_prompt", "You are a helpful executive assistant."
        )

        # Create agent without caching to avoid concurrency issues
        factory = get_agent_factory(checkpointer=checkpointer, enable_skills=True, user_id=user_id)
        tools = get_default_tools(user_id)

        system_prompt = base_prompt + f"\n\nuser_id: {user_id}\n"
        agent = factory.create(model=model, tools=tools, system_prompt=system_prompt)

        from src.app_logging import get_logger

        logger = get_logger()
        handler = logger.langfuse_handler

        config = {"configurable": {"thread_id": user_id}}
        if handler:
            config["callbacks"] = [handler]

        from src.app_logging import timer

        with timer("agent", {"message": msg_content, "user_id": user_id}, channel="http"):
            with propagate_attributes(user_id=user_id):
                result = await agent.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content=m.content)
                            if m.role == "user"
                            else AIMessage(content=m.content)
                            for m in recent_messages
                        ]
                        + [HumanMessage(content=msg_content)]
                    },
                    config=config,
                )

        # Extract response - handle tool messages properly
        messages = result.get("messages", [])

        # Find the last AI message with actual content
        response = None
        tool_results = []

        # First pass: collect tool results
        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                content = getattr(msg, "content", None)
                if content:
                    tool_results.append(content)

        # Second pass: find AI response
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
        checkpointer = checkpoint_manager.checkpointer
        agent = get_agent(user_id, checkpointer=checkpointer)

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
