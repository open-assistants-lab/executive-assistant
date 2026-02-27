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

# Store pending approvals: user_id -> interrupt data
_pending_approvals: dict[str, dict] = {}


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
        msg_content = req.message.strip().lower()

        # Check if this is a response to a pending approval
        if user_id in _pending_approvals and msg_content in ("approve", "reject", "edit"):
            pending = _pending_approvals.pop(user_id)
            tool_name = pending["tool_name"]
            tool_args = pending["tool_args"]

            # Auto-fill missing required args
            if "user_id" not in tool_args or not tool_args.get("user_id"):
                tool_args["user_id"] = user_id

            if msg_content == "reject":
                return MessageResponse(response=f"❌ {tool_name} rejected.")

            # Execute the tool directly
            if tool_name == "email_delete":
                from src.tools.email import email_delete

                result = email_delete.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            if tool_name == "delete_file":
                from src.tools.filesystem import delete_file

                result = delete_file.invoke(tool_args)
                return MessageResponse(response=f"✅ {result}")

            return MessageResponse(response=f"Unknown tool: {tool_name}")

        msg_content = req.message  # Restore original message
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

        # Check for human-in-the-loop interrupt
        if "__interrupt__" in result:
            interrupt_obj = result["__interrupt__"][0]
            interrupt_value = getattr(interrupt_obj, "value", None)

            if interrupt_value and isinstance(interrupt_value, dict):
                action_requests = interrupt_value.get("action_requests", [{}])[0]
                review_configs = interrupt_value.get("review_configs", [{}])[0]

                tool_name = action_requests.get("name", "unknown")
                tool_args = action_requests.get("args", {})
                allowed = review_configs.get("allowed_decisions", [])

                _pending_approvals[user_id] = {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                }

                response = f"⚠️ **{tool_name.replace('_', ' ').title()} - Approval Required**\n\n"
                response += f"Tool: `{tool_name}`\n"
                response += f"Arguments: `{tool_args}`\n\n"
                response += f"Available actions: {', '.join(['`' + a + '`' for a in allowed])}\n\n"
                response += "Reply with one of the above actions to proceed."

                return MessageResponse(response=response)

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
                    # Include tool results in response
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
