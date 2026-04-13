"""Custom summarization middleware that extends LangChain's SummarizationMiddleware.

This middleware:
1. Extends LangChain's SummarizationMiddleware
2. After summarization triggers, calls a callback with the summary content
3. Allows persisting summary to our messages.db
4. Guards against duplicate summarization in the same execution
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import SummarizationMiddleware as LangChainSummarizationMiddleware
from langchain.agents.middleware.types import AgentState
from typing_extensions import override

# Type alias for callback
SummaryCallback = Callable[[str], Awaitable[None]]


class SummarizationMiddleware(LangChainSummarizationMiddleware):
    """Custom summarization middleware with callback support.

    Extends LangChain's SummarizationMiddleware to add callback functionality
    when summarization occurs, allowing us to persist the summary to our database.
    """

    def __init__(self, *args, on_summarize: SummaryCallback | None = None, **kwargs):
        """Initialize with optional callback.

        Args:
            on_summarize: Async callback called when summarization occurs.
                          Receives the summary content as string.
        """
        super().__init__(*args, **kwargs)
        self._on_summarize = on_summarize
        self._last_summary_msg_count: int = 0  # Track message count to prevent duplicates

    @override
    async def abefore_model(self, state: AgentState[Any], runtime: Any) -> dict[str, Any] | None:
        """Process messages before model, triggering summarization if needed.

        After LangChain's summarization runs, calls the callback with the summary.
        """
        from src.app_logging import get_logger

        logger = get_logger()

        # Guard: Don't summarize if we already did in this execution cycle
        # Check message count - if we've already summarized, the count should be lower
        current_msg_count = len(state.get("messages", []))
        if current_msg_count <= self._last_summary_msg_count and self._last_summary_msg_count > 0:
            logger.debug(
                "summarization.middleware.skipped",
                {"reason": "already_summarized_in_cycle", "msg_count": current_msg_count},
                user_id="system",
            )
            return None

        # Call parent's implementation
        result = await super().abefore_model(state, runtime)

        # If summarization didn't trigger, nothing to do
        if result is None:
            return result

        logger.debug(
            "summarization.middleware.result",
            {
                "result_keys": list(result.keys()) if result else None,
                "has_callback": self._on_summarize is not None,
            },
            user_id="system",
        )

        messages = result.get("messages", [])

        # Check if there's a RemoveMessage (indicating summarization was attempted)
        has_remove = any(
            hasattr(msg, "type") and msg.type == "remove"
            for msg in messages
            if hasattr(msg, "type")
        )

        if not has_remove:
            return result

        # Find the summary message
        summary_content: str | None = None
        for msg in messages:
            if (
                hasattr(msg, "content")
                and isinstance(msg.content, str)
                and hasattr(msg, "type")
                and msg.type != "remove"
            ):
                summary_content = msg.content
                break

        # Check if summarization failed
        if summary_content:
            content_lower = summary_content.lower()
            failure_reasons = []

            if "too long to summarize" in content_lower:
                failure_reasons.append("content_too_long_for_summary")
            if "failed to summarize" in content_lower:
                failure_reasons.append("summary_generation_failed")
            if "cannot summarize" in content_lower:
                failure_reasons.append("summary_not_possible")
            if len(summary_content) < 200:
                failure_reasons.append(f"summary_too_short ({len(summary_content)} chars)")

            if failure_reasons:
                # Summarization failed - DON'T apply the changes, just return original state
                logger.warning(
                    "summarization.middleware.failed",
                    {
                        "failure_reasons": failure_reasons,
                        "summary_preview": summary_content[:100],
                    },
                    user_id="system",
                )
                # Return None to prevent message deletion
                return None

        # Mark that we've summarized successfully
        self._last_summary_msg_count = current_msg_count

        # Summarization succeeded - invoke callback
        if summary_content and self._on_summarize:
            logger.info(
                "summarization.callback.invoking",
                {"summary_length": len(summary_content)},
                user_id="system",
            )
            await self._on_summarize(summary_content)

        return result
