"""Web/HTTP channel with streaming support."""

import json
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

from cassey.channels.base import BaseChannel, MessageFormat
from cassey.config import settings


class MessageRequest(BaseModel):
    """Request model for sending a message."""

    content: str = Field(..., description="The message content")
    user_id: str = Field(..., description="User identifier")
    conversation_id: str | None = Field(None, description="Conversation ID (auto-generated if not provided)")
    stream: bool = Field(True, description="Whether to stream the response")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class MessageChunk(BaseModel):
    """A chunk of streamed response."""

    content: str
    role: str
    done: bool = False


class ConversationResponse(BaseModel):
    """Response model for conversation history."""

    conversation_id: str
    messages: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    channel: str
    version: str = "1.0.0"


class HttpChannel(BaseChannel):
    """
    HTTP REST API channel with streaming support.

    Provides a FastAPI application with:
    - POST /message - Send message (streamed or non-streamed)
    - GET /conversations/{id} - Get conversation history
    - GET /health - Health check
    """

    channel_name: str = "http"

    def __init__(
        self,
        agent: Any,
        host: str = "0.0.0.0",
        port: int = 8000,
        runtime: str | None = None,
    ):
        """
        Initialize HTTP channel.

        Args:
            agent: The compiled LangGraph agent
            host: Host to bind to
            port: Port to bind to
        """
        super().__init__(agent, runtime=runtime)
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="Cassey API",
            description="Multi-channel AI agent API",
            version="1.0.0",
        )
        self._setup_routes()
        self._server: Any = None

    def _setup_routes(self) -> None:
        """Setup API routes."""

        @self.app.post("/message", response_model=None)
        async def send_message(req: MessageRequest) -> StreamingResponse | list[dict]:
            """
            Send a message and get response.

            Streamed responses use Server-Sent Events (SSE).
            Non-streamed responses return a JSON array.
            """
            # Generate conversation_id if not provided
            conversation_id = req.conversation_id or f"http_{req.user_id}"

            message = MessageFormat(
                content=req.content,
                user_id=req.user_id,
                conversation_id=conversation_id,
                message_id="",  # No message_id for HTTP requests
                metadata=req.metadata or {},
            )

            if req.stream:
                return StreamingResponse(
                    self._stream_response(message),
                    media_type="text/event-stream",
                )
            else:
                # Non-streamed: collect all and return as JSON
                messages = await self.stream_agent_response(message)
                return [
                    {
                        "content": msg.content,
                        "role": "assistant" if isinstance(msg, AIMessage) else "user",
                    }
                    for msg in messages
                    if hasattr(msg, "content") and msg.content
                ]

        @self.app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
        async def get_conversation(conversation_id: str, limit: int = 100) -> ConversationResponse:
            """Get conversation history (audit endpoint)."""
            from cassey.storage.user_registry import UserRegistry

            registry = UserRegistry()
            history = await registry.get_conversation_history(conversation_id, limit)

            return ConversationResponse(
                conversation_id=conversation_id,
                messages=[
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                        "metadata": msg.metadata,
                    }
                    for msg in history
                ],
            )

        @self.app.get("/health", response_model=HealthResponse)
        async def health() -> HealthResponse:
            """Health check endpoint."""
            return HealthResponse(status="healthy", channel="http")

        @self.app.get("/")
        async def root() -> dict[str, Any]:
            """Root endpoint with API info."""
            return {
                "name": "Cassey API",
                "version": "1.0.0",
                "endpoints": {
                    "POST /message": "Send a message",
                    "GET /conversations/{id}": "Get conversation history",
                    "GET /health": "Health check",
                },
            }

    async def _stream_response(self, message: MessageFormat) -> AsyncIterator[str]:
        """
        Stream response in Server-Sent Events format.

        Args:
            message: The incoming message

        Yields:
            SSE-formatted chunks
        """
        messages = await self.stream_agent_response(message)

        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                chunk = MessageChunk(
                    content=msg.content,
                    role="assistant" if isinstance(msg, AIMessage) else "user",
                    done=False,
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

        # Send final done signal
        yield "data: {\"done\": true}\n\n"

    async def start(self) -> None:
        """Start the HTTP server."""
        import uvicorn

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.should_exit = True

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """
        Send a message (used for outgoing notifications).

        Note: For push notifications, you'd need WebSocket or webhook support.
        This is a no-op for the basic HTTP channel.
        """
        # Could implement webhook callback here
        pass

    @staticmethod
    def get_thread_id(message: MessageFormat) -> str:
        """Generate thread_id for HTTP conversations."""
        return f"http:{message.conversation_id}"

    async def handle_message(self, message: MessageFormat) -> None:
        """
        Handle an incoming message through the agent.

        For HTTP channel, this is called internally by the API endpoint.
        The actual response is returned by the endpoint, not sent via send_message.

        Args:
            message: Incoming message in MessageFormat.
        """
        # Process the message but don't send via send_message
        # The API endpoint handles returning the response
        await self.stream_agent_response(message)
