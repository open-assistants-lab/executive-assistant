"""Progressive disclosure tool - allows agent to query historical context."""

import hashlib
from datetime import date

from langchain_core.tools import tool

from src.storage.conversation import get_conversation_store


def _simple_embedding(text: str) -> list[float]:
    """Simple fallback embedding using hash."""
    words = text.lower().split()
    dim = 384
    embedding = [0.0] * dim
    for word in words:
        hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
        embedding[hash_val] += 1.0
    mag = sum(x**2 for x in embedding) ** 0.5
    if mag > 0:
        embedding = [x / mag for x in embedding]
    return embedding


@tool
def memory_get_history(
    days: int = 7,
    date_str: str | None = None,
    user_id: str = "default",
) -> str:
    """Get conversation history for progressive disclosure.

    Use this tool when user asks about past conversations, what was discussed,
    or wants to recall previous interactions.

    Args:
        days: Number of days to look back (default: 7)
        date_str: Specific date in YYYY-MM-DD format (optional)
        user_id: User identifier

    Returns:
        Formatted conversation history
    """
    conversation = get_conversation_store(user_id)

    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
            messages = conversation.get_messages(
                start_date=target_date,
                end_date=target_date,
            )
            if not messages:
                return f"No messages found for {date_str}"

            result = f"Conversation on {date_str}:\n"
            for msg in messages:
                result += f"- {msg.role}: {msg.content[:200]}\n"
            return result

        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."

    recent = conversation.get_recent_messages(20)

    if not recent:
        return f"No messages in the last {days} days."

    result = f"Recent conversation (last {days} days):\n\n"
    for msg in recent:
        timestamp = msg.ts.strftime("%Y-%m-%d %H:%M")
        result += f"- {msg.role} [{timestamp}]: {msg.content[:150]}\n"

    return result


@tool
def memory_search(
    query: str,
    user_id: str = "default",
) -> str:
    """Search through conversation history using keyword + semantic search.

    This is the most comprehensive search - combines exact keyword matching
    with semantic similarity for better results.

    Use this when user asks about specific topics from past conversations.

    Args:
        query: Query to search for
        user_id: User identifier

    Returns:
        Search results
    """
    conversation = get_conversation_store(user_id)
    embedding = _simple_embedding(query)
    results = conversation.search_hybrid(query, embedding, limit=20)

    if not results:
        return f"No messages found for '{query}'"

    output = f"Found {len(results)} matches:\n"
    for r in results:
        output += f"- {r.role} ({r.ts.date()}): {r.content[:150]} (score: {r.score:.2f})\n"

    return output


class ProgressiveDisclosureTool:
    """Tool for querying historical conversation context."""

    def __init__(self, user_id: str, model: str = "minimax-m2.5"):
        self.user_id = user_id
        self.model = model

    def get_conversation_history(self, days: int = 7, date_str: str | None = None) -> str:
        """Get conversation history."""
        return memory_get_history.invoke(
            {"days": days, "date_str": date_str, "user_id": self.user_id}
        )

    def search_conversation_hybrid(self, query: str) -> str:
        """Search conversation history."""
        return memory_search.invoke({"query": query, "user_id": self.user_id})
