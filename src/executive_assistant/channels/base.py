"""Abstract base class for messaging channels."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import Runnable

from executive_assistant.config import settings
from executive_assistant.logging import get_logger, format_log_context, truncate_log_text
from executive_assistant.storage.file_sandbox import (
    set_thread_id,
    clear_thread_id,
    set_user_id,
    clear_user_id,
    read_file,
    write_file,
)
from executive_assistant.storage.user_registry import UserRegistry
from executive_assistant.storage.group_storage import (
    ensure_thread_group,
    set_group_id as set_workspace_context,
    set_user_id as set_workspace_user_id,
    clear_group_id as clear_workspace_context,
    clear_user_id as clear_workspace_user_id,
)

logger = get_logger(__name__)


class MessageFormat(dict):
    """
    Standardized message format across all channels.

    Attributes:
        content: Text content of the message.
        user_id: Unique identifier for the user.
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

    def get_channel_name(self) -> str:
        """Get the channel name (e.g., 'telegram', 'http', 'slack')."""
        return self.__class__.__name__.lower().replace("channel", "")

    def format_user_id(self, raw_user_id: str) -> str:
        """
        Format user_id with channel prefix for unique identification.

        Args:
            raw_user_id: The raw user ID from the channel (e.g., '123456')

        Returns:
            User ID with channel prefix (e.g., 'telegram:123456')
        """
        return f"{self.get_channel_name()}:{raw_user_id}"

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
            # Set up context
            thread_id = self.get_thread_id(message)
            channel = self.__class__.__name__.lower().replace("channel", "")
            config = {"configurable": {"thread_id": thread_id}}

            # Set thread_id context for file sandbox operations
            set_thread_id(thread_id)

            # Convert thread_id to user_id (identity_id) for storage and permission checks
            from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
            user_id_for_storage = sanitize_thread_id_to_user_id(thread_id)

            ctx = format_log_context("message", channel=channel, user=user_id_for_storage, conversation=message.conversation_id, type="text")
            logger.info(f'{ctx} recv text="{truncate_log_text(message.content)}"')

            # Ensure group exists and set group_id context
            group_id = await ensure_thread_group(thread_id, user_id_for_storage)
            set_workspace_context(group_id)

            ctx_system = format_log_context("system", component="context", channel=channel, user=user_id_for_storage, conversation=message.conversation_id)
            logger.info(f"{ctx_system} set user_id context from thread_id")
            set_workspace_user_id(user_id_for_storage)

            # Verify it was set
            from executive_assistant.storage.group_storage import get_user_id as check_user_id
            verified_id = check_user_id()
            logger.debug(f"{ctx_system} verified user_id")

            # Retrieve relevant memories and inject into message
            memories = self._get_relevant_memories(thread_id, message.content)
            enhanced_content = self._inject_memories(message.content, memories)

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
            }

            # Log incoming message if audit is enabled
            if self.registry:
                await self.registry.log_message(
                    conversation_id=thread_id,
                    user_id=message.user_id,
                    channel=channel,
                    message=HumanMessage(content=enhanced_content),
                    message_id=message.message_id,
                    metadata=message.metadata,
                )

            # Stream agent responses and send IMMEDIATELY (no batching)
            import time
            agent_start = time.time()
            event_count = 0
            async for event in self.agent.astream(state, config):
                event_count += 1
                if event_count <= 10:
                    logger.opt(lazy=True).debug(
                        "Stream event {idx}: {event_type}",
                        idx=event_count,
                        event_type=lambda: type(event).__name__,
                    )

                # Extract and send messages immediately as they arrive
                messages = self._extract_messages_from_event(event)
                new_messages = self._get_new_ai_messages(messages, message.message_id)
                for msg in new_messages:
                    # Send immediately, don't accumulate!
                    if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                        await self.send_message(message.conversation_id, msg.content)

                    # Log message if audit is enabled
                    if self.registry and (hasattr(msg, 'content') and msg.content or (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                        await self.registry.log_message(
                            conversation_id=thread_id,
                            user_id=message.user_id,
                            channel=channel,
                            message=msg,
                        )

            agent_elapsed = time.time() - agent_start
            logger.info(f"{ctx_system} agent processing elapsed={agent_elapsed:.2f}s events={event_count}")

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

    def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5) -> list[dict]:
        """
        Retrieve relevant memories for a query.

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
            memories = storage.search_memories(
                query=query,
                limit=limit,
                min_confidence=settings.MEM_CONFIDENCE_MIN,
            )
            return memories
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
