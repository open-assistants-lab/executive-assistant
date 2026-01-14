"""Abstract base class for messaging channels."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Runnable

from cassey.storage.file_sandbox import set_thread_id, clear_thread_id
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

    def __init__(self, agent: Runnable, registry: Any = None) -> None:
        self.agent = agent
        self.registry = registry  # Optional UserRegistry instance

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

            # Build state
            state = {
                "messages": [HumanMessage(content=message.content)],
                "summary": "",  # Initialize with empty summary
                "iterations": 0,
                "user_id": message.user_id,
                "channel": channel,
            }

            # Stream agent responses
            messages = []
            async for event in self.agent.astream(state, config):
                # Check all possible keys for messages
                for key in event:
                    if key == "messages":
                        for msg in event["messages"]:
                            messages.append(msg)
                            # Log each response message if audit is enabled
                            if self.registry:
                                await self.registry.log_message(
                                    conversation_id=thread_id,
                                    user_id=message.user_id,
                                    channel=channel,
                                    message=msg,
                                )
                    elif key == "agent" and isinstance(event["agent"], dict) and "messages" in event["agent"]:
                        for msg in event["agent"]["messages"]:
                            messages.append(msg)
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
