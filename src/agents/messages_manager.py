"""Message Manager - Centralized management of conversation messages and summarization.

This module provides a unified interface for:
- Loading messages for the agent (with automatic summarization handling)
- Persisting summaries when summarization middleware triggers
- Configuration of summarization behavior

Architecture:
    HTTP/Telegram/CLI --> MessageManager.get_messages() --> Agent
                          ↑                                    ↓
                    Middleware ---------------------> on_summarize callback
"""

from collections.abc import Awaitable, Callable
from typing import Any

from src.app_logging import get_logger
from src.config import get_settings
from src.storage.messages import get_conversation_store

logger = get_logger()

# Type alias for callback
SummaryCallback = Callable[[str], Awaitable[None]]


class MessageManager:
    """Centralized management of conversation messages and summarization.

    This class consolidates all message-related operations including:
    - Loading messages for the agent
    - Handling summarization (triggered by middleware)
    - Managing summary persistence

    Usage:
        manager = MessageManager(user_id="desktop_user")

        # Get messages for agent (handles summarization automatically)
        messages = manager.get_messages(limit=50)

        # Get middleware config (for factory)
        middleware_config = manager.get_middleware_config()

        # Async callback for when summarization occurs
        await manager.on_summarize(summary_content)
    """

    def __init__(self, user_id: str):
        """Initialize MessageManager for a user.

        Args:
            user_id: The user whose messages to manage
        """
        self.user_id = user_id
        self._store = get_conversation_store(user_id)
        self._config = get_settings().memory.summarization

    def get_messages(self, limit: int = 50) -> list:
        """Get messages for the agent, handling summarization automatically.

        If a summary exists in the conversation, this returns:
            - The summary message
            - All messages after the summary

        Otherwise, returns the most recent N messages.

        Args:
            limit: Maximum number of messages to return (when no summary)

        Returns:
            List of Message objects
        """
        if self._store.has_summary():
            return self._store.get_messages_with_summary(limit)
        return self._store.get_recent_messages(limit)

    async def on_summarize(self, summary_content: str) -> None:
        """Callback invoked by SummarizationMiddleware when summarization occurs.

        This saves the summary to the message store.

        Args:
            summary_content: The generated summary text
        """
        try:
            self._store.add_summary_message(summary_content)
            logger.info(
                "message_manager.summarization.saved",
                {"summary_length": len(summary_content)},
                user_id=self.user_id,
            )
        except Exception as e:
            logger.error(
                "message_manager.summarization.failed",
                {"error": str(e)},
                user_id=self.user_id,
            )

    def get_middleware_config(self) -> dict[str, Any]:
        """Get configuration dict for creating SummarizationMiddleware.

        Returns:
            Dict with model, trigger, keep, and on_summarize keys
        """
        from src.config import get_settings
        from src.llm import create_model_from_config

        settings = get_settings()
        model = create_model_from_config(settings.llm)

        return {
            "model": model,
            "trigger": ("tokens", self._config.trigger_tokens),
            "keep": ("tokens", self._config.keep_tokens),
            "on_summarize": lambda content: self.on_summarize(content),
        }

    @property
    def summarization_enabled(self) -> bool:
        """Check if summarization is enabled."""
        return self._config.enabled

    @property
    def trigger_tokens(self) -> int:
        """Get the token threshold for triggering summarization."""
        return self._config.trigger_tokens

    @property
    def keep_tokens(self) -> int:
        """Get the number of tokens to keep after summarization."""
        return self._config.keep_tokens


# Cache for MessageManager instances per user
_message_managers: dict[str, MessageManager] = {}


def get_message_manager(user_id: str) -> MessageManager:
    """Get or create a MessageManager for a user.

    Args:
        user_id: The user ID

    Returns:
        MessageManager instance
    """
    if user_id not in _message_managers:
        _message_managers[user_id] = MessageManager(user_id)
    return _message_managers[user_id]


def clear_message_manager(user_id: str | None = None) -> None:
    """Clear cached MessageManager instances.

    Args:
        user_id: Specific user to clear, or None to clear all
    """
    global _message_managers
    if user_id:
        _message_managers.pop(user_id, None)
    else:
        _message_managers.clear()
