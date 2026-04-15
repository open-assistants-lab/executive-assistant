"""Memory tools — SDK-native implementation."""

from datetime import date, timedelta

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.storage.memory import get_memory_store
from src.storage.messages import get_conversation_store

logger = get_logger()


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

    start_date = date.today() - timedelta(days=days)
    messages = conversation.get_messages(start_date=start_date, limit=200)

    if not messages:
        return f"No messages in the last {days} days."

    result = f"Recent conversation (last {days} days):\n\n"
    for msg in messages:
        timestamp = msg.ts.strftime("%Y-%m-%d %H:%M")
        result += f"- {msg.role} [{timestamp}]: {msg.content[:150]}\n"

    return result


memory_get_history.annotations = ToolAnnotations(
    title="Get Conversation History", read_only=True, idempotent=True
)


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
    results = conversation.search_hybrid(query, limit=20)

    if not results:
        return f"No messages found for '{query}'"

    output = f"Found {len(results)} matches:\n"
    for r in results:
        output += f"- {r.role} ({r.ts.date()}): {r.content[:150]} (score: {r.score:.2f})\n"

    return output


memory_search.annotations = ToolAnnotations(
    title="Search Conversations", read_only=True, idempotent=True
)


@tool
def memory_search_all(
    query: str,
    memories_limit: int = 5,
    messages_limit: int = 5,
    insights_limit: int = 3,
    user_id: str = "default",
) -> str:
    """Search across all memory sources: learned memories, conversations, and insights.

    Use this when you need comprehensive context about a topic - it searches
    memories (preferences, facts, workflows), conversation history, and insights
    simultaneously.

    Args:
        query: Search query
        memories_limit: Max memory results (default: 5)
        messages_limit: Max message results (default: 5)
        insights_limit: Max insight results (default: 3)
        user_id: User identifier

    Returns:
        Unified search results
    """
    store = get_memory_store(user_id)
    results = store.search_all(
        query,
        memories_limit=memories_limit,
        messages_limit=messages_limit,
        insights_limit=insights_limit,
        user_id=user_id,
    )

    parts = [f"## Unified Search Results for '{query}'"]

    if results["memories"]:
        parts.append(f"\n### Learned Memories ({len(results['memories'])})")
        for m in results["memories"]:
            parts.append(
                f"- [{m.memory_type}] {m.trigger}: {m.action} (conf: {min(m.confidence, 1.0):.0%})"
            )

    if results["insights"]:
        parts.append(f"\n### Insights ({len(results['insights'])})")
        for i in results["insights"]:
            parts.append(f"- {i.summary} (conf: {min(i.confidence, 1.0):.0%})")

    if results["messages"]:
        parts.append(f"\n### Conversation Messages ({len(results['messages'])})")
        for m in results["messages"]:
            role = m.get("role", "?")
            content = m.get("content", "")[:150]
            score = m.get("score", 0)
            parts.append(f"- {role}: {content} (score: {score:.2f})")

    if not results["memories"] and not results["insights"] and not results["messages"]:
        parts.append("\nNo results found across any source.")

    return "\n".join(parts)


memory_search_all.annotations = ToolAnnotations(
    title="Search All Memory", read_only=True, idempotent=True
)


@tool
def memory_search_insights(
    query: str,
    method: str = "hybrid",
    limit: int = 5,
    user_id: str = "default",
) -> str:
    """Search synthesized insights using keyword or semantic search.

    Insights are higher-order patterns discovered from grouping memories.
    Use this when looking for themes, trends, or synthesized knowledge.

    Args:
        query: Search query
        method: Search method (fts, semantic, or hybrid) - default: hybrid
        limit: Maximum results
        user_id: User identifier

    Returns:
        Search results
    """
    store = get_memory_store(user_id)

    if method == "fts":
        results = store.search_insights(query, limit=limit)
    elif method == "semantic":
        results = store.search_insights_semantic(query, limit=limit)
    else:
        fts_results = store.search_insights(query, limit=limit)
        if fts_results:
            results = fts_results
        else:
            results = store.search_insights_semantic(query, limit=limit)

    if not results:
        return f"No insights found for: {query}"

    parts = [f"## Insights for '{query}' ({method})"]
    for insight in results:
        parts.append(
            f"- [{insight.domain}] {insight.summary} (conf: {min(insight.confidence, 1.0):.0%})"
        )

    return "\n".join(parts)


memory_search_insights.annotations = ToolAnnotations(
    title="Search Insights", read_only=True, idempotent=True
)


@tool
def memory_connect(
    memory_id: str,
    target_id: str,
    relationship: str = "relates_to",
    strength: float = 1.0,
    user_id: str = "default",
) -> str:
    """Create a connection between two memories with a relationship label.

    Use this to link related memories, e.g., marking that one memory
    contradicts, updates, or builds on another.

    Args:
        memory_id: First memory ID
        target_id: Second memory ID
        relationship: Relationship type (relates_to, contradicts, updates, extends, corrects)
        strength: Connection strength 0-1 (default: 1.0)
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_memory_store(user_id)

    mem1 = store.get_memory(memory_id)
    mem2 = store.get_memory(target_id)

    if not mem1:
        return f"Memory not found: {memory_id}"
    if not mem2:
        return f"Memory not found: {target_id}"

    store.add_connection(memory_id, target_id, relationship=relationship, strength=strength)

    return f"Connected {memory_id} → {target_id} ({relationship}, strength: {strength})"


memory_connect.annotations = ToolAnnotations(title="Connect Memories")
