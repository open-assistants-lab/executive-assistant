"""Checkpoint cleanup middleware to remove old messages after summarization.

This middleware runs after SummarizationMiddleware to remove old messages
from the checkpoint that have been summarized and stored in the virtual filesystem.

This prevents checkpoint bloat while maintaining a backup of the full conversation
history in the virtual filesystem at /conversation_history/{thread_id}.md.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import HumanMessage
from langgraph.types import Command

if TYPE_CHECKING:
    from langgraph.types import Runtime

logger = logging.getLogger(__name__)


class CheckpointCleanupMiddleware(AgentMiddleware):
    """Middleware that removes old messages from checkpoint after summarization.

    This middleware should be added AFTER SummarizationMiddleware in the stack.
    It checks for a `_summarization_event` in the state and removes messages
    that have been summarized (before the cutoff_index) from the checkpoint.

    This prevents checkpoint bloat while preserving the full conversation history
    in the virtual filesystem at /conversation_history/{thread_id}.md.

    Usage:
        ```python
        from src.middleware.checkpoint_cleanup import CheckpointCleanupMiddleware

        middleware = [CheckpointCleanupMiddleware()]
        ```
    """

    def __init__(
        self,
        *,
        keep_buffer_messages: int = 5,
        backup_enabled: bool = True,
    ) -> None:
        """Initialize the checkpoint cleanup middleware.

        Args:
            keep_buffer_messages: Number of messages to keep before the summary
                as a buffer. This ensures we don't delete messages that might be
                referenced by the summary. Defaults to 5.
            backup_enabled: Whether to keep the message file in virtual filesystem
                as backup. Defaults to True (recommended).
        """
        super().__init__()
        self.keep_buffer_messages = keep_buffer_messages
        self.backup_enabled = backup_enabled
        logger.info(f"[CheckpointCleanup] Initialized: keep_buffer={keep_buffer_messages}, backup={backup_enabled}")

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Run cleanup after agent completes.

        Checks for `_summarization_event` in state and removes summarized messages
        from the checkpoint, keeping only:
        - The summary message
        - A buffer of messages before the cutoff
        - All messages after the cutoff index

        Args:
            state: The agent state (may contain messages, _summarization_event, etc.)
            runtime: The runtime context

        Returns:
            State update with cleaned messages, or None if no cleanup needed.
        """
        logger.debug("[CheckpointCleanup] after_agent called")

        messages = state.get("messages", [])
        if not messages:
            logger.debug("[CheckpointCleanup] No messages in state, skipping cleanup")
            return None

        # Check if summarization occurred
        summarization_event = state.get("_summarization_event")
        if not summarization_event:
            logger.debug("[CheckpointCleanup] No summarization event found, skipping cleanup")
            return None

        cutoff_index = summarization_event.get("cutoff_index")
        if cutoff_index is None:
            logger.debug("[CheckpointCleanup] No cutoff_index in event, skipping cleanup")
            return None

        logger.info(
            f"[CheckpointCleanup] Summarization event found: "
            f"cutoff_index={cutoff_index}, "
            f"total_messages={len(messages)}"
        )

        # Validate cutoff_index
        if cutoff_index < 0 or cutoff_index > len(messages):
            logger.warning(
                f"[CheckpointCleanup] Invalid cutoff_index {cutoff_index} for {len(messages)} messages, skipping"
            )
            return None

        original_count = len(messages)
        summary_message = summarization_event.get("summary_message")

        # Build new message list:
        # 1. Buffer messages before cutoff (for context)
        buffer_start = max(0, cutoff_index - self.keep_buffer_messages)
        buffer_messages = messages[buffer_start:cutoff_index]

        # 2. Summary message
        if summary_message:
            summary_position = [summary_message]
        else:
            logger.warning("[CheckpointCleanup] No summary_message in event, skipping")
            return None

        # 3. Messages after cutoff (preserved)
        preserved_messages = messages[cutoff_index:]

        # Combine: buffer + summary + preserved
        new_messages = buffer_messages + summary_position + preserved_messages
        messages_removed = original_count - len(new_messages)

        logger.info(
            f"[CheckpointCleanup] Cleaned checkpoint: "
            f"{original_count} → {len(new_messages)} messages (removed {messages_removed})"
        )

        # Log backup file location if exists
        file_path = summarization_event.get("file_path")
        if file_path and self.backup_enabled:
            logger.debug(f"[CheckpointCleanup] Full history backed up to: {file_path}")

        # Return Command with cleaned messages to update state
        # This ensures the checkpoint is saved with the cleaned message list
        return Command(update={"messages": new_messages})
