"""Web/HTTP channel with streaming support."""

import asyncio
import json
import time
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

from executive_assistant.channels.base import BaseChannel, MessageFormat
from executive_assistant.config import settings
from executive_assistant.logging import format_log_context, truncate_log_text
from executive_assistant.storage.file_sandbox import set_thread_id
from executive_assistant.storage.group_storage import (
    set_group_id as set_workspace_context,
    set_user_id as set_workspace_user_id,
    clear_group_id as clear_workspace_context,
)
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
from executive_assistant.storage.user_registry import UserRegistry
from loguru import logger


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
    ):
        """
        Initialize HTTP channel.

        Args:
            agent: The compiled LangGraph agent
            host: Host to bind to
            port: Port to bind to
        """
        super().__init__(agent)
        self.host = host
        self.port = port
        self.app = FastAPI(
            title=f"{settings.AGENT_NAME} API",
            description="Multi-channel AI agent API",
            version="1.0.0",
        )
        self._setup_routes()
        self._server: Any = None
        self._stream_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._queue_locks: dict[str, asyncio.Lock] = {}
        self._pending_messages: dict[str, list[MessageFormat]] = {}
        self._inflight_tasks: dict[str, asyncio.Task] = {}

    def _get_queue_lock(self, thread_id: str) -> asyncio.Lock:
        """Get or create a queue lock for the given thread_id."""
        if thread_id not in self._queue_locks:
            self._queue_locks[thread_id] = asyncio.Lock()
        return self._queue_locks[thread_id]

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

            # Auto-create identity for anonymous users
            thread_id = f"http:{conversation_id}"
            identity_id = sanitize_thread_id_to_user_id(thread_id)

            # Create identity record if it doesn't exist
            try:
                registry = UserRegistry()
                await registry.create_identity_if_not_exists(
                    thread_id=thread_id,
                    identity_id=identity_id,
                    channel="http"
                )
            except Exception as e:
                # Log but don't fail - user can still interact
                ctx_identity = format_log_context("system", component="identity", channel="http", user=identity_id, conversation=conversation_id)
                logger.warning(f'{ctx_identity} create_identity_failed error="{e}"')

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
            from executive_assistant.storage.user_registry import UserRegistry

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
                "name": f"{settings.AGENT_NAME} API",
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
        thread_id = self.get_thread_id(message)
        ctx = format_log_context("message", channel="http", user=message.user_id, conversation=message.conversation_id, type="text")
        logger.info(f'{ctx} recv text="{truncate_log_text(message.content)}"')
        queue_lock = self._get_queue_lock(thread_id)
        ack_needed = False

        async with queue_lock:
            self._pending_messages.setdefault(thread_id, []).append(message)
            inflight = self._inflight_tasks.get(thread_id)
            if inflight and not inflight.done():
                inflight.cancel()
                ack_needed = True
            self._inflight_tasks[thread_id] = asyncio.current_task()

        if ack_needed:
            ack = MessageChunk(
                content="👍 Got it — I’ll merge this with your current request.",
                role="assistant",
                done=False,
            )
            yield f"data: {ack.model_dump_json()}\n\n"

        self._stream_queues[message.conversation_id] = asyncio.Queue()
        try:
            while True:
                async with queue_lock:
                    batch = self._pending_messages.get(thread_id, []).copy()
                    self._pending_messages[thread_id] = []

                if not batch:
                    break

                try:
                    async for chunk in self._run_agent_stream(thread_id, batch):
                        yield chunk
                except asyncio.CancelledError:
                    async with queue_lock:
                        self._pending_messages[thread_id] = batch + self._pending_messages.get(thread_id, [])
                    raise
        finally:
            self._stream_queues.pop(message.conversation_id, None)
            if self._inflight_tasks.get(thread_id) is asyncio.current_task():
                self._inflight_tasks.pop(thread_id, None)

        # Send final done signal
        yield "data: {\"done\": true}\n\n"

    async def start(self) -> None:
        """Start the HTTP server."""
        # Initialize agent with this channel for status updates
        await self.initialize_agent_with_channel()

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

    async def send_status(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send status update (for HTTP, this would go through SSE stream).

        Note: Full SSE integration for status updates would require
        passing status messages through the response stream.
        For now, this logs for debugging.
        """
        if self._enqueue_stream_event(conversation_id, role="status", content=message):
            return
        import logging
        logger = logging.getLogger(__name__)
        ctx = format_log_context("message", channel="http", conversation=conversation_id, type="status")
        logger.debug(f'{ctx} send status text="{truncate_log_text(message)}"')

    async def send_todo(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """Send todo update (SSE stream if active, else log)."""
        if self._enqueue_stream_event(conversation_id, role="todo", content=message):
            return
        import logging
        logger = logging.getLogger(__name__)
        ctx = format_log_context("message", channel="http", conversation=conversation_id, type="todo")
        logger.debug(f'{ctx} send todo text="{truncate_log_text(message)}"')

    def _enqueue_stream_event(self, conversation_id: str, role: str, content: str) -> bool:
        queue = self._stream_queues.get(conversation_id)
        if not queue:
            return False
        queue.put_nowait({"role": role, "content": content})
        return True

    async def _run_agent_stream(
        self,
        thread_id: str,
        batch: list[MessageFormat],
    ) -> AsyncIterator[str]:
        config = {"configurable": {"thread_id": thread_id}}

        set_thread_id(thread_id)
        user_id_for_storage = sanitize_thread_id_to_user_id(thread_id)
        clear_workspace_context()
        set_workspace_user_id(user_id_for_storage)

        messages: list[HumanMessage] = []
        for idx, msg in enumerate(batch):
            memories = self._get_relevant_memories(thread_id, msg.content)
            enhanced_content = self._inject_memories(msg.content, memories)
            message_id = msg.message_id or f"http_{int(time.time() * 1000)}_{idx}"
            messages.append(
                HumanMessage(
                    content=enhanced_content,
                    additional_kwargs={"executive_assistant_message_id": message_id},
                )
            )

        last_message_id = messages[-1].additional_kwargs.get("executive_assistant_message_id") if messages else None
        state = {
            "messages": messages,
            "run_model_call_count": 0,
            "run_tool_call_count": {},
            "thread_model_call_count": 0,
            "thread_tool_call_count": {},
            "todos": [],
        }

        async for event in self.agent.astream(state, config):
            msgs = self._extract_messages_from_event(event)
            new_messages = self._get_new_ai_messages(msgs, last_message_id) if last_message_id else []
            for msg in new_messages:
                if hasattr(msg, "content") and msg.content:
                    chunk = MessageChunk(
                        content=msg.content,
                        role="assistant",
                        done=False,
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

            queue = self._stream_queues.get(batch[-1].conversation_id)
            if queue:
                while not queue.empty():
                    event_payload = queue.get_nowait()
                    chunk = MessageChunk(
                        content=event_payload["content"],
                        role=event_payload["role"],
                        done=False,
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

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
