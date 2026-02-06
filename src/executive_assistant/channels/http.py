"""Web/HTTP channel with streaming support."""

import asyncio
import json
import time
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from executive_assistant.channels.base import BaseChannel, MessageFormat
from executive_assistant.config import settings
from executive_assistant.logging import format_log_context, truncate_log_text
from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.storage.user_registry import UserRegistry
from executive_assistant.storage.user_allowlist import is_authorized
from loguru import logger


class MessageRequest(BaseModel):
    """Request model for sending a message."""

    content: str = Field(..., description="The message content")
    user_id: str = Field(..., description="Thread identifier (caller-supplied)")
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

        async def _get_conversation_history_from_registry(self, conversation_id: str, limit: int = 100):
            """Get conversation history from UserRegistry."""
            from executive_assistant.storage.user_registry import UserRegistry

            try:
                registry = UserRegistry()
                return await registry.get_conversation_history(conversation_id, limit)
            except Exception:
                return None

        @self.app.post("/message", response_model=None)
        async def send_message(req: MessageRequest) -> StreamingResponse | list[dict]:
            """
            Send a message and get response.

            Streamed responses use Server-Sent Events (SSE).
            Non-streamed responses return a JSON array.
            """
            # Generate conversation_id if not provided
            conversation_id = req.conversation_id or f"http_{req.user_id}"

            thread_id = f"http:{conversation_id}"

            if not is_authorized(thread_id):
                raise HTTPException(
                    status_code=403,
                    detail="Access restricted. Ask an admin to add you using /user add <channel:id>.",
                )

            message = MessageFormat(
                content=req.content,
                user_id=req.user_id,
                conversation_id=conversation_id,
                message_id="",  # No message_id for HTTP requests
                metadata=req.metadata or {},
            )

            # === ONBOARDING CHECK ===
            # Trigger onboarding if user data folder is empty (new user or reset)
            # Skip if admin skills are present (specialized mode)
            from executive_assistant.utils.onboarding import is_user_data_empty, mark_onboarding_started
            from executive_assistant.logging import get_logger, format_log_context
            from executive_assistant.config import settings

            logger = get_logger(__name__)
            ctx_system = format_log_context("system", component="context", channel="http", user=thread_id, conversation=conversation_id)

            try:
                # Check if admin skills are present (specialized mode - no onboarding needed)
                admin_skills_dir = settings.ADMINS_ROOT / "skills"
                has_admin_skills = admin_skills_dir.exists() and any(admin_skills_dir.glob("on_start/*.md"))

                # Check if user data folder is empty
                user_folder_empty = is_user_data_empty(thread_id)

                # Only trigger onboarding if: user folder is empty AND no admin skills
                if user_folder_empty and not has_admin_skills:
                    logger.info(f"{ctx_system} ONBOARDING: User data folder empty for {thread_id}, triggering onboarding")
                    # Mark onboarding as in-progress to prevent re-triggering
                    mark_onboarding_started(thread_id)
                    # Add system note to trigger onboarding skill
                    # The onboarding skill is loaded at startup (on_start) and will handle the flow
                    message.content += (
                        "\n\n[SYSTEM: New user detected (empty data folder). "
                        "Follow this onboarding flow: "
                        "1. Welcome warmly: 'Hi! I'm Ken, your AI assistant. What do you do, and what would you like help with?' "
                        "2. From their response, extract: name, role, responsibilities (comma-separated), communication preference (professional/casual/concise). "
                        "3. Call create_user_profile(name, role, responsibilities, communication_preference) to store structured profile. "
                        "4. Suggest 2-3 specific things you can CREATE based on their role (database, automation, workflow, reminders). "
                        "5. Ask 'Should I set this up for you?' - if yes, create it immediately, then call mark_onboarding_complete(). "
                        "Keep it BRIEF and conversational. Focus on learning about them, not explaining capabilities.]"
                    )
            except Exception as e:
                logger.warning(f"{ctx_system} Onboarding check failed: {e}")

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

        # ========================================================================
        # Google OAuth Endpoints
        # ========================================================================

        @self.app.get("/auth/google/start")
        async def start_google_oauth(user_id: str, redirect: str = "/"):
            """
            Start Google OAuth flow.

            Args:
                user_id: User/thread identifier
                redirect: Where to redirect after authorization (default: /)

            Returns:
                Redirect to Google OAuth consent screen
            """
            from executive_assistant.auth.google_oauth import get_google_oauth_manager

            thread_id = f"http:{user_id}"

            try:
                oauth_manager = get_google_oauth_manager()
                state = thread_id  # Encode thread_id in state parameter
                auth_url = oauth_manager.create_authorization_url(state)

                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=auth_url)

            except ValueError as e:
                logger.error(f"Google OAuth not configured: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Google OAuth not configured. Contact administrator.",
                )
            except Exception as e:
                logger.error(f"Error starting Google OAuth: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to start Google OAuth.",
                )

        @self.app.get("/auth/callback/google")
        async def google_oauth_callback(
            code: str,
            state: str,
            error: str = None,
        ):
            """
            Handle Google OAuth callback.

            Args:
                code: Authorization code from Google
                state: State parameter (contains thread_id)
                error: OAuth error if user cancelled

            Returns:
                Redirect to success/error page
            """
            from starlette.responses import RedirectResponse
            from executive_assistant.auth.google_oauth import get_google_oauth_manager

            if error:
                logger.warning(f"Google OAuth error: {error}")
                return RedirectResponse(url=f"/?auth_error={error}")

            try:
                # Exchange code for tokens
                oauth_manager = get_google_oauth_manager()
                credentials = await oauth_manager.exchange_code_for_tokens(code)

                # Get thread_id from state parameter
                thread_id = state

                # Save encrypted tokens
                await oauth_manager.save_tokens(thread_id, credentials)

                logger.info(f"Google OAuth successful for {thread_id}")
                return RedirectResponse(url="/?auth=success")

            except Exception as e:
                logger.error(f"Error in Google OAuth callback: {e}")
                return RedirectResponse(url=f"/?auth_error=server_error")

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

    async def stream_agent_response(self, message: MessageFormat) -> list[BaseMessage]:
        """
        Run the agent and collect all response messages.

        Used by the non-streaming endpoint to collect all messages
        before returning them as JSON.

        Args:
            message: The incoming message

        Returns:
            List of AI messages from the agent
        """
        thread_id = self.get_thread_id(message)
        # Bootstrap check-in defaults for this user so proactive scheduler can discover it.
        try:
            from executive_assistant.checkin.config import get_checkin_config

            get_checkin_config(thread_id, persist_default=True)
        except Exception as e:
            logger.debug(f"Failed to bootstrap check-in config for {thread_id}: {e}")

        # Build state
        memories = self._get_relevant_memories(thread_id, message.content)
        enhanced_content = self._inject_memories(message.content, memories)
        message_id = message.message_id or f"http_{int(time.time() * 1000)}"

        state = {
            "messages": [
                HumanMessage(
                    content=enhanced_content,
                    additional_kwargs={"executive_assistant_message_id": message_id},
                )
            ],
            "run_model_call_count": 0,
            "run_tool_call_count": {},
            "thread_model_call_count": 0,
            "thread_tool_call_count": {},
            "todos": [],
            "thread_id": thread_id,
            "conversation_id": message.conversation_id,
        }

        config = {"configurable": {"thread_id": thread_id}}
        set_thread_id(thread_id)

        # Collect all messages from stream
        all_messages: list[BaseMessage] = []
        request_agent = await self._build_request_agent(message.content, message.conversation_id)

        async for event in request_agent.astream(state, config):
            messages = self._extract_messages_from_event(event)
            new_messages = self._get_new_ai_messages(messages, message_id)
            all_messages.extend(new_messages)

        return all_messages

    async def _run_agent_stream(
        self,
        thread_id: str,
        batch: list[MessageFormat],
    ) -> AsyncIterator[str]:
        config = {"configurable": {"thread_id": thread_id}}

        set_thread_id(thread_id)
        # Bootstrap check-in defaults for this user so proactive scheduler can discover it.
        try:
            from executive_assistant.checkin.config import get_checkin_config

            get_checkin_config(thread_id, persist_default=True)
        except Exception as e:
            logger.debug(f"Failed to bootstrap check-in config for {thread_id}: {e}")

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
            "thread_id": thread_id,
            "conversation_id": batch[-1].conversation_id,
        }

        request_agent = await self._build_request_agent(batch[-1].content, batch[-1].conversation_id)

        # Token tracking
        total_input_tokens = 0
        total_output_tokens = 0

        async for event in request_agent.astream(state, config):
            msgs = self._extract_messages_from_event(event)
            new_messages = self._get_new_ai_messages(msgs, last_message_id) if last_message_id else []
            for msg in new_messages:
                # Extract token usage from message if available
                if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                    usage = msg.usage_metadata
                    input_tok = usage.get('input_tokens') or usage.get('prompt_tokens')
                    output_tok = usage.get('output_tokens') or usage.get('completion_tokens')
                    if input_tok:
                        total_input_tokens += input_tok
                    if output_tok:
                        total_output_tokens += output_tok
                if hasattr(msg, "content") and msg.content and msg.content.strip():
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

        # Log total tokens (this executes when stream ends)
        total_tokens = total_input_tokens + total_output_tokens
        thread_id = batch[-1].conversation_id if batch else "unknown"
        ctx = format_log_context("message", channel="http", conversation=thread_id, type="token_usage")
        if total_tokens > 0:
            logger.info(f"{ctx} tokens={total_input_tokens}+{total_output_tokens}={total_tokens}")
        else:
            logger.debug(f"{ctx} no_token_metadata found total_input={total_input_tokens} total_output={total_output_tokens}")

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
        # DEBUG: Log entry
        from executive_assistant.logging import get_logger, format_log_context
        logger = get_logger(__name__)
        thread_id = self.get_thread_id(message)
        ctx_system = format_log_context("system", component="context", channel="http", user=thread_id, conversation=message.conversation_id)
        logger.info(f"{ctx_system} HTTP handle_message called: user={thread_id}, content='{message.content[:50]}'")

        # Check for onboarding - enhance message before processing
        from executive_assistant.utils.onboarding import (
            should_show_onboarding,
            has_completed_onboarding,
            is_vague_request,
        )

        try:
            # Only check onboarding for new conversations
            conversation_history = self._get_conversation_history(message.conversation_id)
            is_new_conversation = not conversation_history or len(conversation_history) < 5
            history_len = len(conversation_history) if conversation_history else 0

            logger.info(f"{ctx_system} DEBUG: history_len={history_len}, is_new={is_new_conversation}")

            if is_new_conversation:
                has_completed = has_completed_onboarding(thread_id)
                is_vague = is_vague_request(message.content)
                logger.info(f"{ctx_system} DEBUG: has_completed={has_completed}, is_vague={is_vague}")

                if not has_completed and is_vague:
                    logger.info(f"{ctx_system} ONBOARDING: TRIGGERED - showing capabilities")
                    # Inject onboarding instructions
                    message.content += (
                        "\n\n=== IMPORTANT ONBOARDING INSTRUCTION ===\n"
                        "This is a NEW user who sent a vague greeting. You MUST:\n"
                        "1. Welcome them briefly (1 sentence)\n"
                        "2. Show 3-4 BULLET POINTS of what you can do (be specific!)\n"
                        "3. End with 'What would you like help with?'\n\n"
                        "Keep it SHORT - expert users hate tutorials.\n"
                        "Example bullet points:\n"
                        "- Build mini-apps and workflows\n"
                        "- Analyze data with SQL and Python\n"
                        "- Search web and save to knowledge base\n"
                        "- Manage reminders and track work\n"
                        "=== END ONBOARDING INSTRUCTION ===\n"
                    )
        except Exception as e:
            logger.error(f"{ctx_system} Onboarding error: {e}", exc_info=True)

        # Process the message but don't send via send_message
        # The API endpoint handles returning the response
        await self.stream_agent_response(message)
