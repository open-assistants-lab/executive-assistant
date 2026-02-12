"""Abstract base class for messaging channels."""

from abc import ABC, abstractmethod
import asyncio
from collections import OrderedDict
import contextvars
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import Runnable

from executive_assistant.config import settings
from executive_assistant.logging import get_logger, format_log_context, truncate_log_text
from executive_assistant.storage.file_sandbox import (
    read_file,
    write_file,
)
from executive_assistant.storage.user_registry import UserRegistry
from executive_assistant.storage.thread_storage import (
    set_thread_id,
    set_channel,
    set_chat_type,
)
from executive_assistant.agent.flow_mode import (
    set_flow_mode_active,
    is_flow_mode_enabled,
)

logger = get_logger(__name__)
_fallback_tool_calls_ctx: contextvars.ContextVar[int] = contextvars.ContextVar(
    "fallback_tool_calls_ctx",
    default=0,
)

_SIMPLE_CHAT_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|yo|sup|good (morning|afternoon|evening)|thanks?|thank you|thx|ok|okay|cool|great|nice|how are you( doing)?|what can you do\??|help\??)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

_TOOL_INTENT_HINTS = (
    "file", "folder", "path", "table", "database", "sql", "query",
    "tdb", "adb", "vdb", "python", "script", "code", "run ",
    "create", "insert", "update", "delete", "write", "read", "fetch", "summarize",
    "search", "web", "browse", "scrape", "crawl",
    "reminder", "schedule", "todo", "checkin", "flow",
    "mcp", "server", "skill", "load_skill",
    "memory", "remember", "forget",
)


@dataclass
class _AgentCacheEntry:
    agent: Runnable
    created_at: float
    last_used_at: float


class MessageFormat(dict):
    """
    Standardized message format across all channels.

    Attributes:
        content: Text content of the message.
        user_id: Thread identifier (channel + channel user id).
        conversation_id: Unique identifier for the conversation.
        message_id: Unique identifier for this message.
        attachments: List of file attachments (images, documents, etc.).
        metadata: Additional channel-specific data.
    """

    def __init__(
        self,
        content: str,
        user_id: str,
        conversation_id: str,
        message_id: str,
        attachments: list[dict] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.content = content
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.attachments = attachments or []
        self.metadata = metadata or {}
        super().__init__(
            content=content,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            attachments=self.attachments,
            metadata=self.metadata,
        )


class BaseChannel(ABC):
    """
    Abstract base class for messaging channels.

    All channel implementations (Telegram, Slack, WhatsApp, etc.)
    must inherit from this class and implement the required methods.

    This abstraction allows the same ReAct agent to work across
    multiple messaging platforms without modification.

    Attributes:
        agent: The compiled LangGraph agent to process messages.
        registry: Optional user registry for message logging and ownership tracking.
    """

    def __init__(
        self,
        agent: Runnable,
        registry: Any = None,
    ) -> None:
        self.agent = agent
        self.registry = registry  # Optional UserRegistry instance
        self._active_tasks: dict[str, Any] = {}
        self._interrupted_chats: set[str] = set()
        self._profile_loaded: set[str] = set()  # Track which thread profiles are cached
        self._request_agent_cache: OrderedDict[str, _AgentCacheEntry] = OrderedDict()
        self._request_agent_cache_lock = asyncio.Lock()
        self._agent_cache_enabled = bool(getattr(settings, "AGENT_CACHE_ENABLED", True))
        self._agent_cache_ttl_seconds = max(
            int(getattr(settings, "AGENT_CACHE_TTL_SECONDS", 900)),
            30,
        )
        self._agent_cache_max_entries = max(
            int(getattr(settings, "AGENT_CACHE_MAX_ENTRIES", 64)),
            1,
        )


    def cancel_active_task(self, conversation_id: str) -> bool:
        task = self._active_tasks.get(str(conversation_id))
        if task and not task.done():
            task.cancel()
            self._interrupted_chats.add(str(conversation_id))
            return True
        return False

    def get_channel_name(self) -> str:
        """Get the channel name (e.g., 'telegram', 'http', 'slack')."""
        return self.__class__.__name__.lower().replace("channel", "")

    def format_user_id(self, raw_user_id: str) -> str:
        """
        Format user_id (thread identifier) with channel prefix for unique identification.

        Args:
            raw_user_id: The raw user ID from the channel (e.g., '123456')

        Returns:
            User ID with channel prefix (e.g., 'telegram:123456')
        """
        return f"{self.get_channel_name()}:{raw_user_id}"

    def _is_planning_only(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        planning_keywords = (
            "plan",
            "planning",
            "roadmap",
            "outline",
            "strategy",
            "breakdown",
            "estimate",
        )
        tool_keywords = (
            "file",
            "folder",
            "database",
            "tdb",
            "vdb",
            "adb",
            "flow",
            "agent",
            "scrape",
            "crawl",
            "search",
            "web",
            "python",
            "reminder",
            "memory",
        )
        return any(k in lowered for k in planning_keywords) and not any(
            k in lowered for k in tool_keywords
        )

    def _is_simple_chat(self, text: str) -> bool:
        """Conservative classifier for low-risk conversational turns."""
        if not text:
            return False
        trimmed = text.strip()
        if len(trimmed) > 80:
            return False
        if _SIMPLE_CHAT_PATTERN.match(trimmed):
            return True
        lowered = trimmed.lower()
        if "http://" in lowered or "https://" in lowered:
            return False
        if any(hint in lowered for hint in _TOOL_INTENT_HINTS):
            return False
        # Keep simple-tool profile for very short acknowledgements only.
        return len(trimmed.split()) <= 2 and trimmed.isalpha()

    def _tools_signature(self, tools: list[Any]) -> str:
        names = []
        for tool in tools:
            name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
            if name:
                names.append(name)
        names.sort()
        payload = "|".join(names)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _reset_fallback_tool_call_metric() -> None:
        _fallback_tool_calls_ctx.set(0)

    @staticmethod
    def _increment_fallback_tool_call_metric() -> None:
        _fallback_tool_calls_ctx.set(_fallback_tool_calls_ctx.get() + 1)

    @staticmethod
    def _get_fallback_tool_call_metric() -> int:
        return int(_fallback_tool_calls_ctx.get())

    async def _get_cached_agent(self, cache_key: str) -> Runnable | None:
        if not self._agent_cache_enabled:
            return None
        now = time.time()
        async with self._request_agent_cache_lock:
            # Evict expired entries first.
            expired_keys = [
                key
                for key, entry in self._request_agent_cache.items()
                if now - entry.created_at > self._agent_cache_ttl_seconds
            ]
            for key in expired_keys:
                self._request_agent_cache.pop(key, None)

            entry = self._request_agent_cache.get(cache_key)
            if not entry:
                return None
            entry.last_used_at = now
            self._request_agent_cache.move_to_end(cache_key)
            return entry.agent

    async def _set_cached_agent(self, cache_key: str, agent: Runnable) -> None:
        if not self._agent_cache_enabled:
            return
        now = time.time()
        async with self._request_agent_cache_lock:
            self._request_agent_cache[cache_key] = _AgentCacheEntry(
                agent=agent,
                created_at=now,
                last_used_at=now,
            )
            self._request_agent_cache.move_to_end(cache_key)
            while len(self._request_agent_cache) > self._agent_cache_max_entries:
                self._request_agent_cache.popitem(last=False)

    async def _build_request_agent(
        self,
        message_text: str,
        conversation_id: str,
        thread_id: str | None = None,
    ) -> tuple[Runnable, dict[str, Any]]:
        from executive_assistant.agent.langchain_agent import create_langchain_agent
        from executive_assistant.config import create_model
        from executive_assistant.tools.registry import get_all_tools, get_tools_for_request
        from executive_assistant.storage.checkpoint import get_async_checkpointer
        from executive_assistant.agent.prompts import get_system_prompt

        tool_profile = "full"
        if self._is_simple_chat(message_text):
            tools = await get_tools_for_request(message_text)
            tool_profile = "simple"
            if not tools:
                tools = await get_all_tools()
                tool_profile = "full_fallback"
        else:
            tools = await get_all_tools()
        logger.debug("Building agent with tools: profile=%s count=%s", tool_profile, len(tools))
        model_variant = "fast" if self._is_planning_only(message_text) else "default"
        system_prompt = get_system_prompt(self.get_channel_name(), thread_id=thread_id)
        tools_sig = self._tools_signature(tools)
        prompt_sig = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]
        cache_thread_id = thread_id or f"{self.get_channel_name()}:{conversation_id}"
        cache_key = f"{cache_thread_id}|{model_variant}|{tool_profile}|{tools_sig}|{prompt_sig}"

        cached_agent = await self._get_cached_agent(cache_key)
        if cached_agent is not None:
            return cached_agent, {
                "cache_hit": True,
                "model_variant": model_variant,
                "tool_profile": tool_profile,
                "tools_count": len(tools),
            }

        model = create_model(model=model_variant)
        checkpointer = await get_async_checkpointer()
        agent = create_langchain_agent(
            model=model,
            tools=tools,
            checkpointer=checkpointer,
            system_prompt=system_prompt,
            channel=self,
        )
        await self._set_cached_agent(cache_key, agent)

        return agent, {
            "cache_hit": False,
            "model_variant": model_variant,
            "tool_profile": tool_profile,
            "tools_count": len(tools),
        }

    async def initialize_agent_with_channel(self) -> None:
        """
        Re-create the agent with this channel as the channel parameter.

        This enables status update middleware to send progress updates.
        Should be called after channel initialization but before start().
        """
        from executive_assistant.agent.langchain_agent import create_langchain_agent
        from executive_assistant.config import create_model
        from executive_assistant.tools.registry import get_all_tools
        from executive_assistant.storage.checkpoint import get_async_checkpointer
        from executive_assistant.agent.prompts import get_system_prompt

        # Get the same configuration used to create the original agent
        model = create_model()
        tools = await get_all_tools()
        checkpointer = await get_async_checkpointer()
        system_prompt = get_system_prompt(self.__class__.__name__.replace("Channel", "").lower())

        # Create new agent with this channel
        self.agent = create_langchain_agent(
            model=model,
            tools=tools,
            checkpointer=checkpointer,
            system_prompt=system_prompt,
            channel=self,  # Pass this channel for status updates
        )

    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel.

        This should begin listening for incoming messages.
        For polling-based channels, start the poll loop.
        For webhook-based channels, start the webhook server.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel gracefully."""

    @abstractmethod
    async def send_message(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """
        Send a message to a conversation.

        Args:
            conversation_id: Target conversation identifier.
            content: Message content to send.
            **kwargs: Channel-specific parameters (parse_mode, etc.).
        """

    async def send_status(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send a status update to the user.

        Status updates are ephemeral progress messages during agent execution.
        Channels may choose to update in-place (edit) or send new messages.

        Args:
            conversation_id: Target conversation identifier.
            message: Status message to send.
            update: If True, try to edit previous status message instead of sending new.

        Default implementation just sends a regular message.
        Subclasses should override for better UX (e.g., Telegram message editing).
        """
        await self.send_message(conversation_id, message)

    async def send_todo(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send a todo update message.

        Default implementation sends a normal message; channels can override to edit
        a dedicated todo message separate from status updates.
        """
        await self.send_message(conversation_id, message)

    @abstractmethod
    async def handle_message(self, message: MessageFormat) -> None:
        """
        Handle an incoming message through the agent.

        This method should:
        1. Create or retrieve the thread_id for this conversation
        2. Stream the agent response
        3. Send responses back to the user AS THEY ARRIVE (not batched)

        Args:
            message: Incoming message in MessageFormat.
        """
        try:
            request_start = time.perf_counter()
            memory_ms = 0.0
            build_agent_ms = 0.0
            first_response_ms: float | None = None
            build_meta: dict[str, Any] = {}
            self._reset_fallback_tool_call_metric()

            # Set up context
            thread_id = self.get_thread_id(message)
            channel = self.__class__.__name__.lower().replace("channel", "")
            config = {"configurable": {"thread_id": thread_id}}

            # Thread-only storage (thread_id is the storage identifier)
            ctx = format_log_context("message", channel=channel, user=thread_id, conversation=message.conversation_id, type="text")

            # Add Langfuse callback handler if enabled
            try:
                from executive_assistant.observability.langfuse_integration import get_callback_handler

                langfuse_handler = get_callback_handler()
                if langfuse_handler:
                    config["callbacks"] = [langfuse_handler]
                    logger.debug(f"{ctx} Langfuse tracing enabled")
            except Exception as e:
                logger.debug(f"{ctx} Failed to setup Langfuse tracing: {e}")

            # Set thread_id context for file sandbox operations
            set_thread_id(thread_id)

            logger.info(f'{ctx} recv text="{truncate_log_text(message.content)}"')

            # Thread-only context
            set_thread_id(thread_id)
            set_channel(channel)
            set_chat_type("private")
            set_flow_mode_active(is_flow_mode_enabled(message.conversation_id))

            ctx_system = format_log_context("system", component="context", channel=channel, user=thread_id, conversation=message.conversation_id)
            logger.info(f"{ctx_system} set thread_id context")

            # Retrieve relevant memories and inject into message
            memory_start = time.perf_counter()
            memories = self._get_relevant_memories(thread_id, message.content)
            enhanced_content = self._inject_memories(message.content, memories)
            memory_ms = (time.perf_counter() - memory_start) * 1000.0
            if message.conversation_id in self._interrupted_chats:
                enhanced_content = (
                    "[Note] The previous run in this conversation was interrupted by the user.\n"
                    + enhanced_content
                )
                self._interrupted_chats.discard(message.conversation_id)

            # Observe user message for instinct learning (non-blocking)
            # Use raw message content, not enhanced (with memory injection)
            # This prevents false pattern detection from memory context
            try:
                from executive_assistant.instincts.observer import get_instinct_observer

                observer = get_instinct_observer()
                detected = observer.observe_message(message.content, thread_id=thread_id)
                if detected:
                    logger.debug(f"{ctx_system} Observed {len(detected)} instinct patterns")
            except Exception as e:
                # Don't break message handling if instinct observation fails
                logger.debug(f"{ctx_system} Instinct observation failed: {e}")

            # Track emotional state (non-blocking)
            try:
                from executive_assistant.instincts.emotional_tracker import get_emotional_tracker

                tracker = get_emotional_tracker()
                # Get conversation length for context
                history = self._get_conversation_history(message.conversation_id)
                state = tracker.update_state(
                    message.content,
                    conversation_length=len(history) if history else 0
                )
                if state.value != "neutral":
                    logger.debug(f"{ctx_system} Emotional state: {state.value} (confidence: {tracker.confidence:.2f})")
            except Exception as e:
                # Don't break message handling if emotional tracking fails
                logger.debug(f"{ctx_system} Emotional tracking failed: {e}")


            # Build state with only the new message
            state = {
                "messages": [
                    HumanMessage(
                        content=enhanced_content,
                        additional_kwargs={"executive_assistant_message_id": message.message_id},
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

            # Log incoming message if audit is enabled
            if self.registry:
                await self.registry.log_message(
                    conversation_id=thread_id,
                    channel=channel,
                    message=HumanMessage(content=enhanced_content),
                    message_id=message.message_id,
                    metadata=message.metadata,
                )

            self._active_tasks[message.conversation_id] = asyncio.current_task()
            # Stream agent responses and send IMMEDIATELY (no batching)
            import time
            agent_start = time.time()
            event_count = 0
            messages_sent = 0
            total_input_tokens = 0
            total_output_tokens = 0
            embedded_seen: set[str] = set()
            build_agent_start = time.perf_counter()
            request_agent, build_meta = await self._build_request_agent(
                enhanced_content,
                message.conversation_id,
                thread_id,
            )
            build_agent_ms = (time.perf_counter() - build_agent_start) * 1000.0

            async def _fallback_status(step: int, tool_name: str, _args: dict[str, Any]) -> None:
                await self.send_status(message.conversation_id, f"🛠️ {step}: {tool_name}")

            async for event in request_agent.astream(state, config):
                event_count += 1
                if event_count <= 20:
                    logger.debug(f"Stream event {event_count}: {type(event).__name__}")
                    if isinstance(event, dict):
                        logger.debug(f"  Event keys: {list(event.keys())}")
                        if "messages" in event:
                            logger.debug(f"  Messages count: {len(event['messages'])}")
                        if "model" in event:
                            logger.debug(f"  Model event: {type(event['model']).__name__ if event['model'] else 'None'}")

                # Extract token usage from event if available
                if isinstance(event, dict):
                    # Check for usage metadata in various event formats
                    usage = event.get('usage_metadata') or event.get('usage')
                    if usage:
                        input_tok = usage.get('input_tokens') or usage.get('prompt_tokens')
                        output_tok = usage.get('output_tokens') or usage.get('completion_tokens')
                        if input_tok:
                            total_input_tokens += input_tok
                        if output_tok:
                            total_output_tokens += output_tok

                # Extract and send messages immediately as they arrive
                messages = self._extract_messages_from_event(event)
                new_messages = self._get_new_ai_messages(messages, message.message_id)
                for msg in new_messages:
                    if isinstance(msg, AIMessage) and getattr(msg, "content", None):
                        embedded_results = await self._execute_embedded_tool_calls(
                            msg.content,
                            embedded_seen,
                            on_tool_start=_fallback_status,
                        )
                        if embedded_results:
                            for result_text in embedded_results:
                                await self.send_message(message.conversation_id, result_text)
                                messages_sent += 1
                                if first_response_ms is None:
                                    first_response_ms = (time.perf_counter() - request_start) * 1000.0
                            continue

                    # Extract token usage from message if available
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        usage = msg.usage_metadata
                        input_tok = usage.get('input_tokens') or usage.get('prompt_tokens')
                        output_tok = usage.get('output_tokens') or usage.get('completion_tokens')
                        if input_tok:
                            total_input_tokens += input_tok
                        if output_tok:
                            total_output_tokens += output_tok

                    # Send immediately, don't accumulate!
                    if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                        await self.send_message(message.conversation_id, msg.content)
                        messages_sent += 1
                        if first_response_ms is None:
                            first_response_ms = (time.perf_counter() - request_start) * 1000.0

                    # Log message if audit is enabled
                    if self.registry and (hasattr(msg, 'content') and msg.content or (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                        await self.registry.log_message(
                            conversation_id=thread_id,
                            channel=channel,
                            message=msg,
                        )

            agent_elapsed = time.time() - agent_start
            total_tokens = total_input_tokens + total_output_tokens
            
            # Note: Agent should always generate a final response after tool calls
            # If no response is received, check the LLM/model configuration
            
            # Try to get final state for token usage (some checkpointers store this)
            if total_tokens == 0:
                try:
                    final_state = await request_agent.aget_state(config)
                    if final_state and hasattr(final_state, 'values'):
                        messages = final_state.values.get('messages', [])
                        for msg in messages:
                            if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                                usage = msg.usage_metadata
                                input_tok = usage.get('input_tokens') or usage.get('prompt_tokens')
                                output_tok = usage.get('output_tokens') or usage.get('completion_tokens')
                                if input_tok:
                                    total_input_tokens += input_tok
                                if output_tok:
                                    total_output_tokens += output_tok
                        total_tokens = total_input_tokens + total_output_tokens
                except Exception:
                    pass  # Ignore errors in token extraction
            
            if total_tokens > 0:
                logger.info(f"{ctx_system} agent processing elapsed={agent_elapsed:.2f}s events={event_count} messages={messages_sent} tokens={total_input_tokens}+{total_output_tokens}={total_tokens}")
            else:
                logger.info(f"{ctx_system} agent processing elapsed={agent_elapsed:.2f}s events={event_count} messages={messages_sent}")

            # Stage timing instrumentation
            model_ms = 0.0
            tools_ms = 0.0
            model_calls = 0
            tool_calls = 0
            try:
                from executive_assistant.agent.status_middleware import pop_stage_timing

                timing = pop_stage_timing(thread_id)
                if timing:
                    model_ms = float(timing.get("model_total_ms", 0.0))
                    tools_ms = float(timing.get("tool_total_ms", 0.0))
                    model_calls = int(timing.get("model_calls", 0))
                    tool_calls = int(timing.get("tool_calls", 0))
            except Exception:
                pass

            total_ms = (time.perf_counter() - request_start) * 1000.0
            post_process_ms = max(total_ms - (memory_ms + build_agent_ms + model_ms + tools_ms), 0.0)
            first_ms = first_response_ms if first_response_ms is not None else -1.0
            fallback_tool_calls = self._get_fallback_tool_call_metric()
            logger.info(
                f"{ctx_system} stage_timing_ms memory={memory_ms:.1f} build_agent={build_agent_ms:.1f} "
                f"model={model_ms:.1f} tools={tools_ms:.1f} post_process={post_process_ms:.1f} "
                f"first_response={first_ms:.1f} total={total_ms:.1f} model_calls={model_calls} "
                f"tool_calls={tool_calls} fallback_tool_calls={fallback_tool_calls} "
                f"tool_profile={build_meta.get('tool_profile', 'unknown')} "
                f"agent_cache_hit={build_meta.get('cache_hit', False)} tools_count={build_meta.get('tools_count', -1)}"
            )
            self._active_tasks.pop(message.conversation_id, None)

        except asyncio.CancelledError:
            ctx_cancel = format_log_context("system", component="agent", channel=self.get_channel_name(), user=message.user_id, conversation=message.conversation_id)
            logger.info(f"{ctx_cancel} cancelled")
            self._active_tasks.pop(message.conversation_id, None)
            return

        except Exception as e:
            ctx_error = format_log_context("system", component="agent", channel=self.get_channel_name(), user=message.user_id, conversation=message.conversation_id)
            logger.exception(f"{ctx_error} unhandled exception")
            await self.send_message(
                message.conversation_id,
                f"Sorry, an error occurred: {e}",
            )

    def get_thread_id(self, message: MessageFormat) -> str:
        """
        Generate a thread_id for conversation persistence.

        The thread_id is used by the checkpointer to maintain
        conversation history across requests.

        Args:
            message: Incoming message.

        Returns:
            Thread identifier (usually conversation_id with channel prefix).
        """
        return f"{self.__class__.__name__}:{message.conversation_id}"

    def _is_general_query(self, query: str) -> bool:
        """
        Detect if a query is asking for general memory information.

        General queries like "What do you remember?" should return all profile memories,
        not perform semantic search which won't match profile content.

        Args:
            query: The user's query string.

        Returns:
            True if this is a general memory query, False for specific queries.
        """
        if not query:
            return False

        query_lower = query.lower()
        general_patterns = [
            "what do you remember",
            "what do you know",
            "about me",
            "about myself",
            "remind me",
            "information do you have",
            "tell me about",
        ]

        return any(pattern in query_lower for pattern in general_patterns)

    def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5) -> list[dict]:
        """
        Retrieve relevant memories for a query.

        CRITICAL FIX: Always load profile memories, not just search results.
        Profile memories (name, role, preferences) must always be available.

        Strategy:
        1. ALWAYS load profile memories (name, role, preferences, etc.)
        2. For general queries, return all memories
        3. For specific queries, combine profiles + search results

        Note: Profile caching is handled at the conversation level (not implemented here)
        to avoid complexity. The key fix is using list_memories() instead of search_memories().

        Args:
            thread_id: Thread identifier.
            query: Search query (typically the user's message).
            limit: Maximum number of memories to return.

        Returns:
            List of relevant memory dictionaries.
        """
        try:
            from executive_assistant.storage.mem_storage import get_mem_storage

            storage = get_mem_storage()

            # CRITICAL: ALWAYS load profile memories (they define WHO the user is)
            # This is the fix: use list_memories() not search_memories()
            profile_memories = storage.list_memories(
                memory_type="profile",
                status="active",
                thread_id=thread_id,
            )

            logger.debug(
                "Loaded %d profile memories for thread %s",
                len(profile_memories),
                thread_id[:20],
            )

            # For general queries, get all memories (not just profile)
            if self._is_general_query(query):
                all_memories = storage.list_memories(
                    status="active",
                    thread_id=thread_id,
                )
                # Combine: profiles + other memories
                non_profile = [m for m in all_memories if m.get("memory_type") != "profile"]
                return profile_memories + non_profile

            # For specific queries, use semantic search for other memory types
            other_memories = storage.search_memories(
                query=query,
                limit=limit,
                min_confidence=settings.MEM_CONFIDENCE_MIN,
                thread_id=thread_id,
            )

            # Combine: profiles + search results
            return profile_memories + other_memories

        except Exception:
            # Don't fail if memory system isn't set up
            return []

    def _inject_memories(self, content: str, memories: list[dict]) -> str:
        """
        Inject relevant memories into the message content.

        Args:
            content: Original message content.
            memories: List of memory dictionaries.

        Returns:
            Content with memory context injected.
        """
        if not memories:
            return content

        memory_lines = []
        for m in memories[:5]:  # Max 5 memories
            memory_lines.append(f"- {m['content']}")

        memory_context = "\n".join(memory_lines)
        return f"[User Memory]\n{memory_context}\n\n[User Message]\n{content}"

    def _extract_messages_from_event(self, event: Any) -> list[BaseMessage]:
        """Extract messages from LangGraph/LangChain stream events."""
        if not isinstance(event, dict):
            return []

        # Direct messages array
        if isinstance(event.get("messages"), list):
            return event["messages"]

        # LangChain agent middleware events: {'model': {'messages': [...]}}
        if "model" in event and isinstance(event["model"], dict):
            if isinstance(event["model"].get("messages"), list):
                return event["model"]["messages"]

        # Also check nested structures
        for value in event.values():
            if isinstance(value, dict) and isinstance(value.get("messages"), list):
                return value["messages"]

        return []

    def _get_new_ai_messages(
        self,
        messages: list[BaseMessage],
        message_id: str,
    ) -> list[AIMessage]:
        """Return only AI messages produced after the current user message."""
        if not messages:
            return []

        last_human_index = -1
        for idx, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                msg_id = msg.additional_kwargs.get("executive_assistant_message_id")
                if msg_id == message_id:
                    last_human_index = idx

        if last_human_index == -1:
            return [msg for msg in messages if isinstance(msg, AIMessage)]

        return [
            msg
            for msg in messages[last_human_index + 1 :]
            if isinstance(msg, AIMessage)
        ]

    def _extract_embedded_tool_calls(self, content: str) -> list[dict[str, Any]]:
        """Extract JSON tool calls from model text when structured tool-calls are missing."""
        if not content:
            return []

        decoder = json.JSONDecoder()
        calls: list[dict[str, Any]] = []

        def _scan_json_objects(text: str) -> None:
            idx = 0
            while idx < len(text):
                start = text.find("{", idx)
                if start == -1:
                    break
                try:
                    obj, end = decoder.raw_decode(text, start)
                except json.JSONDecodeError:
                    idx = start + 1
                    continue
                if isinstance(obj, dict):
                    name = obj.get("name")
                    arguments = obj.get("arguments", obj.get("args"))
                    if isinstance(name, str) and isinstance(arguments, dict):
                        calls.append({"name": name, "arguments": arguments})
                idx = end

        def _extract_attr(attrs_text: str, attr_name: str) -> str | None:
            match = re.search(
                rf"{re.escape(attr_name)}\s*=\s*(?:\"([^\"]*)\"|'([^']*)')",
                attrs_text,
                flags=re.IGNORECASE,
            )
            if not match:
                return None
            return html.unescape(match.group(1) or match.group(2) or "").strip()

        def _coerce_xml_param_value(raw: str, string_hint: str | None) -> Any:
            value = html.unescape(raw).strip()
            if string_hint and string_hint.lower() == "true":
                return value
            lowered = value.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            if lowered in {"null", "none"}:
                return None
            if re.fullmatch(r"-?\d+", value):
                try:
                    return int(value)
                except ValueError:
                    return value
            if re.fullmatch(r"-?\d+\.\d+", value):
                try:
                    return float(value)
                except ValueError:
                    return value
            if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value

        def _scan_xml_function_calls(text: str) -> None:
            # DeepSeek-style fallback:
            # <function_calls><invoke name="tool"><parameter name="x">1</parameter></invoke></function_calls>
            # Also handle variants:
            # <functioncalls> ... </function_calls>
            xml_blocks = re.findall(
                r"<function_?calls\b[^>]*>\s*(.*?)\s*</function_?calls\s*>",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for block in xml_blocks:
                invoke_matches = re.finditer(
                    r"<invoke\b([^>]*)>(.*?)</invoke>",
                    block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                for invoke_match in invoke_matches:
                    invoke_attrs = invoke_match.group(1) or ""
                    invoke_body = invoke_match.group(2) or ""
                    tool_name = _extract_attr(invoke_attrs, "name")
                    if not tool_name:
                        continue
                    args: dict[str, Any] = {}
                    param_matches = re.finditer(
                        r"<parameter\b([^>]*)>(.*?)</parameter>",
                        invoke_body,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                    for param_match in param_matches:
                        param_attrs = param_match.group(1) or ""
                        param_body = param_match.group(2) or ""
                        arg_name = _extract_attr(param_attrs, "name")
                        if not arg_name:
                            continue
                        string_hint = _extract_attr(param_attrs, "string")
                        args[arg_name] = _coerce_xml_param_value(param_body, string_hint)
                    calls.append({"name": tool_name, "arguments": args})

        # 1) `<tools>...</tools>` blocks
        blocks = re.findall(
            r"<tools\b[^>]*>\s*(.*?)\s*</tools\s*>",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for block in blocks:
            _scan_json_objects(block)

        # 1b) `<function_calls>...</function_calls>` XML blocks
        _scan_xml_function_calls(content)

        # 2) fenced json code blocks
        code_blocks = re.findall(r"```json\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        for block in code_blocks:
            _scan_json_objects(block)

        # 3) full content fallback (plain inline JSON snippets)
        # Only allow when payload is mostly tool-call markup/JSON to avoid
        # executing arbitrary JSON fragments from natural language text.
        if self._is_predominantly_tool_payload(content):
            _scan_json_objects(content)

        return calls

    def _contains_embedded_tool_markup(self, content: str) -> bool:
        """Heuristic to detect model-returned tool-call markup in plain text."""
        if not content:
            return False
        return bool(
            re.search(
                r"<\s*(tools|function_?calls?|invoke|parameter)\b",
                content,
                flags=re.IGNORECASE,
            )
        )

    def _is_predominantly_tool_payload(self, content: str) -> bool:
        """Return True when content is mostly tool-call payload.

        This avoids executing accidental/injected tool snippets embedded inside
        longer natural-language responses.
        """
        if not content:
            return False

        stripped = content.strip()
        if not stripped:
            return False

        if re.fullmatch(r"(?is)\s*<function_?calls\b[^>]*>.*?</function_?calls\s*>\s*", stripped):
            return True
        if re.fullmatch(r"(?is)\s*<tools\b[^>]*>.*?</tools\s*>\s*", stripped):
            return True
        if re.fullmatch(r"(?is)\s*```json\s*.*?```\s*", stripped):
            return True

        if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (dict, list)):
                    return True
            except json.JSONDecodeError:
                pass

        residual = re.sub(
            r"(?is)<function_?calls\b[^>]*>.*?</function_?calls\s*>",
            " ",
            stripped,
        )
        residual = re.sub(r"(?is)<tools\b[^>]*>.*?</tools\s*>", " ", residual)
        residual = re.sub(r"(?is)```json\s*.*?```", " ", residual)
        residual = re.sub(r"\s+", " ", residual).strip()

        if not residual:
            return True

        compact = re.sub(r"[^A-Za-z0-9]+", "", residual)
        return len(compact) <= 24

    @staticmethod
    def _normalize_argument_key(key: str) -> str:
        """Normalize argument key variants (camel/squashed) to snake_case."""
        if not key:
            return key
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", key.strip())
        cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", cleaned).lower()
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        alias_map = {
            "memorytype": "memory_type",
            "memory_type": "memory_type",
            "memorykey": "key",
            "threadid": "thread_id",
            "conversationid": "conversation_id",
            "userid": "user_id",
            "numresults": "num_results",
            "numresult": "num_results",
            "scraperesults": "scrape_results",
        }
        return alias_map.get(cleaned, cleaned)

    @staticmethod
    def _resolve_tool_name(name: str, tool_map: dict[str, Any]) -> str:
        """Resolve tool name variants to a concrete registry tool name."""
        if name in tool_map:
            return name

        compact_name = re.sub(r"[^a-z0-9]", "", name.lower())
        compact_map = {
            re.sub(r"[^a-z0-9]", "", tool_name.lower()): tool_name
            for tool_name in tool_map
            if tool_name
        }
        return compact_map.get(compact_name, name)

    async def _execute_embedded_tool_calls(
        self,
        content: str,
        seen_call_keys: set[str] | None = None,
        on_tool_start: Callable[[int, str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> list[str]:
        """Execute embedded `<tools>` calls when model returns text instead of real tool calls."""
        if self._contains_embedded_tool_markup(content) and not self._is_predominantly_tool_payload(content):
            return ["Error: model returned mixed content with tool-call markup. Please retry."]

        calls = self._extract_embedded_tool_calls(content)
        if not calls:
            if self._contains_embedded_tool_markup(content):
                return ["Error: could not parse model tool-call output. Please retry."]
            return []

        from executive_assistant.tools.registry import get_all_tools, get_middleware_tools

        tools = await get_all_tools()
        middleware_tools = await get_middleware_tools()
        all_tools = tools + middleware_tools
        tool_map = {getattr(t, "name", ""): t for t in all_tools}
        outputs: list[str] = []
        tool_step = 0

        for call in calls:
            name = str(call.get("name", "")).strip()
            args = call.get("arguments", {})
            if not isinstance(args, dict):
                args = {}
            args = {
                self._normalize_argument_key(str(k)): v
                for k, v in args.items()
            }
            name = self._resolve_tool_name(name, tool_map)

            key = json.dumps({"name": name, "arguments": args}, sort_keys=True)
            if seen_call_keys is not None:
                if key in seen_call_keys:
                    continue
                seen_call_keys.add(key)

            tool = tool_map.get(name)
            tool_step += 1
            if on_tool_start is not None:
                try:
                    await on_tool_start(tool_step, name, args)
                except Exception as e:
                    logger.debug(f"fallback_tool_status_failed step={tool_step} tool={name} error={e}")
            if tool is None:
                outputs.append(f"Error: unknown tool '{name}'")
                continue

            try:
                self._increment_fallback_tool_call_metric()
                result = await tool.ainvoke(args)
                outputs.append(str(result))
            except Exception as e:
                outputs.append(f"Error: tool '{name}' failed ({type(e).__name__}): {e}")

        return outputs
