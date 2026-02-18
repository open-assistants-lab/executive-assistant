"""Message utilities for extracting displayable content from agent results.

This module provides helper functions to process agent results and extract
user-facing content, filtering out internal messages like those injected by
SummarizationMiddleware.
"""

from langchain_core.messages import HumanMessage


def get_last_displayable_message(result: dict) -> str:
    """Extract the last message content, skipping internal summarization messages.

    SummarizationMiddleware injects HumanMessages with lc_source="summarization"
    for context, but these should not be displayed to the user.

    This function searches backwards through the message list to find the last
    message that is NOT a summarization message.

    Args:
        result: The agent result dictionary containing messages.

    Returns:
        The content of the last displayable message as a string.
        Returns empty string if no displayable message is found.

    Example:
        >>> result = {"messages": [HumanMessage("Summary...", additional_kwargs={"lc_source": "summarization"}), HumanMessage("Hello!")]}
        >>> get_last_displayable_message(result)
        'Hello!'
    """
    messages = result.get("messages", [])

    # Find the last message that's not a summary message
    for msg in reversed(messages):
        # Skip summarization messages (they're for internal context, not display)
        if msg.additional_kwargs.get("lc_source") == "summarization":
            continue
        if hasattr(msg, "content") and msg.content:
            return msg.content

    # Fallback to last message or empty string
    last_msg = messages[-1] if messages else None
    if last_msg and hasattr(last_msg, "content"):
        return last_msg.content
    return str(last_msg) if last_msg else ""
