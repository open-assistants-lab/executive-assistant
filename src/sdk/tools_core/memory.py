"""Memory tools — read from unified MemoryStore (observations + reflections)."""

from typing import Any

from src.sdk.tools import ToolAnnotations, tool


def _get_memory_store(user_id: str, workspace_id: str) -> Any:
    from src.storage.memory import get_memory_store
    return get_memory_store(user_id, workspace_id)


@tool
def memory_profile(
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Return observations about the user — may be empty if Observer hasn't run.

    Returns recent observations collected by the Observer. If no observations
    are available, use message_search to find specific facts from conversation
    history instead.

    Use when the user asks "what do you know about me?" or the agent needs
    to refresh its understanding of the user's context.

    Args:
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)
    """
    store = _get_memory_store(user_id, workspace_id)
    recent = store.get_recent_observations(days=7, limit=50)

    if not recent:
        return "No observations available. Try message_search to find specific facts from conversation history."

    parts = ["## Working Memory (Recent Observations)\n"]
    for obs in recent:
        priority = obs.get("priority", "\U0001f7e2")
        ts = str(obs.get("observation_ts", ""))[:10]
        content = str(obs.get("content", ""))
        parts.append(f"{priority} {ts} {content}")

    return "\n".join(parts)


memory_profile.annotations = ToolAnnotations(
    title="Get User Profile", read_only=True, idempotent=True
)


@tool
def memory_reflection(
    query: str,
    method: str = "hybrid",
    limit: int = 5,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Search synthesized reflections — patterns and insights about the user.

    Reflections are higher-order patterns discovered by the Reflector from
    analyzing observations across time. May be empty if the Reflector hasn't
    run yet (requires 10+ observations and 24h interval).

    Use when looking for themes, trends, or synthesized understanding about
    the user. For specific fact recall, use message_search instead.

    Args:
        query: What to search for (e.g., "career", "relationships", "habits")
        method: Search method (fts, semantic, or hybrid) — default: hybrid
        limit: Maximum results (default: 5)
        user_id: User identifier
        workspace_id: Workspace ID (defaults to current workspace)
    """
    store = _get_memory_store(user_id, workspace_id)
    results = store.search_reflections(query, method=method, limit=limit)

    if not results:
        return f"No reflections found for: {query}"

    parts = [f"## Reflections for '{query}'\n"]
    for i, refl in enumerate(results, 1):
        confidence = float(refl.get("confidence", 0.6))
        domain = str(refl.get("domain", ""))
        content = str(refl.get("content", ""))
        parts.append(f"{i}. [{domain}] {content} (confidence: {confidence:.0%})")
        store.boost_reflection(refl["id"])

    return "\n".join(parts)


memory_reflection.annotations = ToolAnnotations(
    title="Search Reflections", read_only=True, idempotent=True
)
