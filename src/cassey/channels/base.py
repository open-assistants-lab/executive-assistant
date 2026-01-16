"""Abstract base class for messaging channels."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Runnable

from cassey.config import settings
from cassey.storage.file_sandbox import (
    set_thread_id,
    clear_thread_id,
    set_user_id,
    clear_user_id,
    read_file,
    write_file,
)
from cassey.storage.user_registry import UserRegistry


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
        runtime: str | None = None,
    ) -> None:
        self.agent = agent
        self.registry = registry  # Optional UserRegistry instance
        self.runtime = (runtime or settings.AGENT_RUNTIME).lower()

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

    @abstractmethod
    async def handle_message(self, message: MessageFormat) -> None:
        """
        Handle an incoming message through the agent.

        This method should:
        1. Create or retrieve the thread_id for this conversation
        2. Stream the agent response
        3. Send responses back to the user

        Args:
            message: Incoming message in MessageFormat.
        """
        try:
            # Stream agent response
            messages = await self.stream_agent_response(message)

            # Send responses back
            for msg in messages:
                if hasattr(msg, "content") and msg.content:
                    await self.send_message(message.conversation_id, msg.content)
        except Exception as e:
            import traceback
            traceback.print_exc()
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
            from cassey.storage.mem_storage import get_mem_storage

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

        if isinstance(event.get("messages"), list):
            return event["messages"]

        for key in ("agent", "output", "final"):
            value = event.get(key)
            if isinstance(value, dict) and isinstance(value.get("messages"), list):
                return value["messages"]

        return []

    async def stream_agent_response(
        self,
        message: MessageFormat,
    ) -> list[BaseMessage]:
        """
        Stream agent response and return final messages.

        Args:
            message: Incoming message with user query.

        Returns:
            List of messages from the agent.
        """
        thread_id = self.get_thread_id(message)
        channel = self.__class__.__name__.lower().replace("channel", "")
        config = {"configurable": {"thread_id": thread_id}}

        # Set thread_id context for file sandbox operations
        set_thread_id(thread_id)

        try:
            set_user_id(message.user_id)
            # Log incoming message if audit is enabled
            if self.registry:
                await self.registry.log_message(
                    conversation_id=thread_id,
                    user_id=message.user_id,
                    channel=channel,
                    message=HumanMessage(content=message.content),
                    message_id=message.message_id,
                    metadata=message.metadata,
                )

            # Retrieve relevant memories and inject into message
            memories = self._get_relevant_memories(thread_id, message.content)
            enhanced_content = self._inject_memories(message.content, memories)

            # Build state with only the new message
            # LangGraph's checkpointer will automatically restore previous state
            # (messages, structured_summary, iterations) when we provide the thread_id in config
            state = {"messages": [HumanMessage(content=enhanced_content)]}
            if self.runtime == "custom":
                state.update(
                    {
                        "iterations": 0,
                        "user_id": message.user_id,
                        "channel": channel,
                    }
                )

            # Stream agent responses
            messages = []
            async for event in self.agent.astream(state, config):
                for msg in self._extract_messages_from_event(event):
                    messages.append(msg)
                    # Log each response message if audit is enabled
                    if self.registry:
                        await self.registry.log_message(
                            conversation_id=thread_id,
                            user_id=message.user_id,
                            channel=channel,
                            message=msg,
                        )

            return messages
        finally:
            # Clear thread_id to prevent leaking between conversations
            clear_thread_id()
            clear_user_id()
