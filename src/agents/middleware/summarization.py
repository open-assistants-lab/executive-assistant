"""Custom summarization middleware that extends LangChain's SummarizationMiddleware.

This middleware:
1. Extends LangChain's SummarizationMiddleware
2. After summarization triggers, calls a callback with the summary content
3. Allows persisting summary to our messages.db
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import SummarizationMiddleware as LangChainSummarizationMiddleware
from langchain.agents.middleware.types import AgentState, ContextT
from langgraph.runtime import Runtime
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

    @override
    async def abefore_model(
        self, state: AgentState[Any], runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        """Process messages before model, triggering summarization if needed.

        After LangChain's summarization runs, calls the callback with the summary.
        """
        # Call parent's implementation
        result = await super().abefore_model(state, runtime)

        # If summarization happened (result is not None)
        if result is not None and self._on_summarize:
            # Extract summary message from the result
            messages = result.get("messages", [])

            # Find the summary message (it's an AIMessage, not RemoveMessage)
            for msg in messages:
                # Skip RemoveMessage
                if hasattr(msg, "id") and hasattr(msg, "type") and msg.type == "remove":
                    continue

                # The summary should be the first non-RemoveMessage after RemoveAll
                # It will be an AIMessage with content
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    summary_content = msg.content
                    # Call the callback
                    await self._on_summarize(summary_content)
                    break

        return result
