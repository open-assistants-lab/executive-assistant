"""Memory tools — SDK-native implementation."""

from datetime import date, timedelta

from src.app_logging import get_logger
from src.sdk.memory_planner import plan_memory_query
from src.sdk.tools import ToolAnnotations, tool
from src.storage.memory import get_memory_store
from src.storage.messages import SearchResult, get_message_store

logger = get_logger()


@tool
def memory_get_history(
    days: int = 7,
    date_str: str | None = None,
    user_id: str = "default_user",
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
    conversation = get_message_store(user_id)

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
                result += f"- {msg.role}: {msg.content}\n"
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
        result += f"- {msg.role} [{timestamp}]: {msg.content}\n"

    return result


memory_get_history.annotations = ToolAnnotations(
    title="Get Conversation History", read_only=True, idempotent=True
)


@tool
def memory_search(
    query: str,
    user_id: str = "default_user",
) -> str:
    """Search through conversation history using keyword + semantic search.

    This is the most comprehensive search - combines exact keyword matching
    with semantic similarity for better results. Automatically generates
    query variants to improve recall across different phrasings.

    Use this when user asks about specific topics from past conversations.

    Args:
        query: Query to search for
        user_id: User identifier

    Returns:
        Search results
    """
    conversation = get_message_store(user_id)
    memory_store = get_memory_store(user_id)
    plan = plan_memory_query(query)

    fact_limit = plan.max_facts if plan.intent != "unknown" else 5
    fact_results = memory_store.find_facts_for_query(query, limit=fact_limit)
    temporal_results = (
        memory_store.find_fact_history_for_query(query, limit=plan.max_history)
        if plan.needs_fact_history
        else []
    )

    queries = _expand_queries(query)
    seen_ids: set[int] = set()
    all_results: list[SearchResult] = []

    recency_keywords = ["current", "latest", "now", "after", "updated", "new",
                         "recently", "last", "nowadays", "these days"]
    recency_boost = any(kw in query.lower() for kw in recency_keywords)

    for q in queries:
        results = conversation.search_hybrid(
            q, limit=8,
            recency_weight=0.7 if recency_boost else 0.3,
        )
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    all_results.sort(key=lambda r: r.score, reverse=True)
    all_results = all_results[:10]

    if not fact_results and not temporal_results and not all_results:
        return f"No messages found for '{query}'"

    output = ""
    if fact_results:
        output += f"Found {len(fact_results)} exact facts:\n"
        for m in fact_results:
            sd = m.structured_data
            previous = sd.get("previous_value")
            previous_text = f" (previous: {previous})" if previous else ""
            output += (
                f"- {sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text} "
                f"(conf: {min(m.confidence, 1.0):.0%})\n"
            )

    if temporal_results:
        output += f"Found {len(temporal_results)} temporal/update facts:\n"
        for m in temporal_results:
            sd = m.structured_data
            status = "current" if not m.is_superseded else "superseded"
            effective_at = sd.get("effective_at") or m.updated_at.date().isoformat()
            previous = sd.get("previous_value")
            previous_text = f"; previous={previous}" if previous else ""
            output += (
                f"- {effective_at} [{status}] "
                f"{sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text}\n"
            )

    output += f"Found {len(all_results)} conversation matches:\n"
    for r in all_results:
        output += f"- {r.role} ({r.ts.date()}): {r.content} (score: {r.score:.2f})\n"

    return output


def _expand_queries(query: str) -> list[str]:
    """Generate search query variants for better recall."""
    queries = [query]

    words = query.lower().split()
    if len(words) > 4:
        queries.append(" ".join(words[:4]))

    for kw in ["how many", "how much", "how long", "how often", "how many days",
                "how many times", "total", "all the", "list of", "every"]:
        if kw in query.lower():
            queries.append(query.lower().replace(kw, "").strip())
            break

    for kw in ["current", "latest", "now", "after", "updated", "new", "recently",
                "last", "previous", "before", "changed"]:
        if kw in query.lower():
            core = query.lower().replace(kw, "").strip()
            if core and core != query.lower():
                queries.append(core)
            break

    for kw in ["recommend", "suggest", "should i", "what kind of", "what type of",
                "can you recommend", "can you suggest", "do i like", "do i prefer",
                "what do i", "what's my favorite", "what is my favorite"]:
        if kw in query.lower():
            for sub in ["like", "enjoy", "love", "prefer", "favorite", "interested in"]:
                queries.append(sub)
            break

    import re
    date_refs = re.findall(r"\b(?:january|february|march|april|may|june|july|august"
                           r"|september|october|november|december|\d{1,2}(?:st|nd|rd|th)?"
                           r"(?:\s+of)?\s+\d{4})\b", query.lower())
    for d in date_refs:
        queries.append(d)

    return queries


memory_search.annotations = ToolAnnotations(
    title="Search Conversations", read_only=True, idempotent=True
)


@tool
def memory_search_all(
    query: str,
    memories_limit: int = 5,
    messages_limit: int = 5,
    insights_limit: int = 3,
    user_id: str = "default_user",
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
    plan = plan_memory_query(query)
    fact_limit = plan.max_facts if plan.intent != "unknown" else memories_limit
    fact_results = store.find_facts_for_query(query, limit=fact_limit)
    temporal_results = (
        store.find_fact_history_for_query(query, limit=plan.max_history)
        if plan.needs_fact_history
        else []
    )
    results = store.search_all(
        query,
        memories_limit=memories_limit,
        messages_limit=messages_limit,
        insights_limit=insights_limit,
        user_id=user_id,
    )

    parts = [f"## Unified Search Results for '{query}'"]

    if fact_results:
        parts.append(f"\n### Exact Facts ({len(fact_results)})")
        for m in fact_results:
            sd = m.structured_data
            previous = sd.get("previous_value")
            previous_text = f" (previous: {previous})" if previous else ""
            parts.append(
                f"- {sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text} "
                f"(conf: {min(m.confidence, 1.0):.0%})"
            )

    if temporal_results:
        parts.append(f"\n### Temporal / Update Facts ({len(temporal_results)})")
        for m in temporal_results:
            sd = m.structured_data
            status = "current" if not m.is_superseded else "superseded"
            effective_at = sd.get("effective_at") or m.updated_at.date().isoformat()
            previous = sd.get("previous_value")
            previous_text = f"; previous={previous}" if previous else ""
            parts.append(
                f"- {effective_at} [{status}] "
                f"{sd.get('entity', 'user')}.{sd.get('attribute', m.trigger)} = "
                f"{sd.get('value', m.action)}{previous_text}"
            )

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
            content = m.get("content", "")
            score = m.get("score", 0)
            parts.append(f"- {role}: {content} (score: {score:.2f})")

    if (
        not fact_results
        and not temporal_results
        and not results["memories"]
        and not results["insights"]
        and not results["messages"]
    ):
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
    user_id: str = "default_user",
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
    user_id: str = "default_user",
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
