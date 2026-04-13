"""Memory tools for learning user preferences and behavioral patterns."""

from datetime import UTC, datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.storage.memory import (
    CONNECTION_RELATIONSHIPS,
    DEFAULT_CONFIDENCE,
    MEMORY_TYPE_FACT,
    SCOPE_GLOBAL,
    SCOPE_PROJECT,
    SOURCE_EXPLICIT,
    get_memory_store,
)

logger = get_logger()


@tool
def profile_set(
    name: str | None = None,
    role: str | None = None,
    company: str | None = None,
    city: str | None = None,
    bio: str | None = None,
    interests: str | None = None,
    skills: str | None = None,
    user_id: str = "default",
) -> str:
    """Set user profile information manually.

    Stores profile information as memories with high confidence (1.0) so they
    are always injected into context and not overwritten by auto-learned patterns.

    Args:
        name: User's name
        role: User's role (e.g., developer, manager, designer)
        company: User's company
        city: User's city/location
        bio: Short bio about the user
        interests: Comma-separated interests (e.g., "AI, hiking, cooking")
        skills: Comma-separated skills (e.g., "Python, TypeScript, React")
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_memory_store(user_id)

    fields = {
        "name": (name, "when user provides name", "personal"),
        "role": (role, "when user provides role", "work"),
        "company": (company, "when user provides company", "work"),
        "city": (city, "when user provides location", "location"),
        "bio": (bio, "when user provides bio", "personal"),
    }

    for field_name, (value, trigger, domain) in fields.items():
        if value:
            store.add_memory(
                trigger=trigger,
                action=value,
                confidence=1.0,
                domain=domain,
                source=SOURCE_EXPLICIT,
                memory_type=MEMORY_TYPE_FACT,
                structured_data={"entity": "user", "attribute": field_name, "value": value},
                is_update=True,
            )

    if interests:
        for interest in interests.split(","):
            interest = interest.strip()
            if interest:
                store.add_memory(
                    trigger="when user provides interest",
                    action=interest,
                    confidence=1.0,
                    domain="interests",
                    source=SOURCE_EXPLICIT,
                    memory_type=MEMORY_TYPE_FACT,
                    structured_data={"entity": "user", "attribute": "interest", "value": interest},
                    is_update=True,
                )

    if skills:
        for skill in skills.split(","):
            skill = skill.strip()
            if skill:
                store.add_memory(
                    trigger="when user provides skill",
                    action=skill,
                    confidence=1.0,
                    domain="skills",
                    source=SOURCE_EXPLICIT,
                    memory_type=MEMORY_TYPE_FACT,
                    structured_data={"entity": "user", "attribute": "skill", "value": skill},
                    is_update=True,
                )

    logger.info(
        "profile.set",
        {
            "user_id": user_id,
            "name": name,
            "role": role,
            "company": company,
            "city": city,
        },
        user_id=user_id,
    )

    return f"Profile updated for {user_id}. Use memory_list to view all memories."


@tool
def memory_list(
    domain: str | None = None,
    memory_type: str | None = None,
    min_confidence: float = DEFAULT_CONFIDENCE,
    limit: int = 20,
    user_id: str = "default",
    scope: str | None = None,
    project_id: str | None = None,
) -> str:
    """List learned user memories/preferences.

    Memories are behavioral patterns learned from user interactions,
    including corrections, preferences, and workflow habits.

    Args:
        domain: Filter by domain (personal, work, location, interests, etc.)
        memory_type: Filter by memory type (preference, fact, workflow, correction)
        min_confidence: Minimum confidence score (0-1)
        limit: Maximum number of results
        user_id: User identifier
        scope: Filter by scope (global or project)
        project_id: Filter by project ID (includes global memories too)

    Returns:
        Formatted list of memories
    """
    store = get_memory_store(user_id)
    memories = store.list_memories(
        domain=domain,
        memory_type=memory_type,
        min_confidence=min_confidence,
        limit=limit,
        scope=scope,
        project_id=project_id,
    )

    if not memories:
        return f"No memories found for user {user_id}."

    parts = [f"## Learned Memories for {user_id}"]
    if domain:
        parts.append(f"(filtered by domain: {domain})")
    if memory_type:
        parts.append(f"(filtered by type: {memory_type})")
    if scope:
        parts.append(f"(filtered by scope: {scope})")
    parts.append("")

    for memory in memories:
        recency = ""
        now = datetime.now(UTC)
        days_old = (now - memory.updated_at).days
        if days_old < 7:
            recency = " (recent)"
        elif days_old > 90:
            recency = " (outdated)"

        source_marker = "★" if memory.source == SOURCE_EXPLICIT else ""

        parts.append(f"### {memory.id}{source_marker}")
        parts.append(f"- **When**: {memory.trigger}")
        parts.append(f"- **Action**: {memory.action}")
        parts.append(f"- **Confidence**: {min(memory.confidence, 1.0):.0%}{recency}")
        parts.append(f"- **Domain**: {memory.domain}")
        parts.append(f"- **Type**: {memory.memory_type}")
        parts.append(f"- **Observations**: {memory.observations}")
        if memory.structured_data:
            for key, value in memory.structured_data.items():
                parts.append(f"- **{key}**: {value}")
        if memory.connections:
            conn_strs = [f"{c.target_id[:8]}({c.relationship})" for c in memory.connections[:5]]
            parts.append(f"- **Connections**: {', '.join(conn_strs)}")
        if memory.scope != SCOPE_GLOBAL:
            parts.append(
                f"- **Scope**: {memory.scope}"
                + (f" ({memory.project_id})" if memory.project_id else "")
            )
        parts.append("")

    return "\n".join(parts)


@tool
def memory_remove(memory_id: str, user_id: str = "default") -> str:
    """Remove a learned memory.

    Args:
        memory_id: The memory ID to remove
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_memory_store(user_id)
    removed = store.remove_memory(memory_id)

    if removed:
        logger.info("memory.removed", {"memory_id": memory_id}, user_id=user_id)
        return f"Removed memory: {memory_id}"
    else:
        return f"Memory not found: {memory_id}"


@tool
def memory_search(
    query: str,
    method: str = "hybrid",
    limit: int = 10,
    user_id: str = "default",
) -> str:
    """Search memories using keyword, semantic, or hybrid search.

    Args:
        query: Search query
        method: Search method (fts, semantic, hybrid, field) - default: hybrid
        limit: Maximum results
        user_id: User identifier

    Returns:
        Search results
    """
    store = get_memory_store(user_id)

    if method == "fts":
        results = store.search_fts(query, limit=limit)
    elif method == "semantic":
        results = store.search_semantic(query, limit=limit)
    elif method == "field":
        results = store.search_field_semantic(query, limit=limit)
    else:
        results = store.search_hybrid(query, limit=limit)

    if not results:
        return f"No results found for: {query}"

    parts = [f"## Search Results for '{query}' ({method})"]
    for memory in results:
        parts.append(
            f"- **{memory.trigger}**: {memory.action} [{memory.domain}/{memory.memory_type}] (conf: {min(memory.confidence, 1.0):.0%})"
        )

    return "\n".join(parts)


@tool
def insight_list(
    domain: str | None = None,
    limit: int = 10,
    user_id: str = "default",
) -> str:
    """List synthesized insights from memory consolidation.

    Insights are higher-order patterns discovered by analyzing groups of memories.

    Args:
        domain: Filter by domain (optional)
        limit: Maximum number of results
        user_id: User identifier

    Returns:
        Formatted list of insights
    """
    store = get_memory_store(user_id)
    insights = store.list_insights(domain=domain, limit=limit)

    if not insights:
        return f"No insights found for user {user_id}."

    parts = [f"## Insights for {user_id}"]
    if domain:
        parts.append(f"(filtered by domain: {domain})")
    parts.append("")

    for insight in insights:
        parts.append(f"### {insight.id}")
        parts.append(f"- **Summary**: {insight.summary}")
        parts.append(f"- **Domain**: {insight.domain}")
        parts.append(f"- **Confidence**: {min(insight.confidence, 1.0):.0%}")
        if insight.linked_memories:
            parts.append(f"- **Linked memories**: {', '.join(insight.linked_memories[:5])}")
        parts.append("")

    return "\n".join(parts)


@tool
def insight_remove(insight_id: str, user_id: str = "default") -> str:
    """Remove an insight.

    Args:
        insight_id: The insight ID to remove
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_memory_store(user_id)
    removed = store.remove_insight(insight_id)

    if removed:
        return f"Removed insight: {insight_id}"
    else:
        return f"Insight not found: {insight_id}"


@tool
def insight_search(
    query: str,
    method: str = "hybrid",
    limit: int = 5,
    user_id: str = "default",
) -> str:
    """Search insights using keyword or semantic search.

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
        results = store.search_insights(query, limit=limit)
        if not results:
            results = store.search_insights_semantic(query, limit=limit)

    if not results:
        return f"No insights found for: {query}"

    parts = [f"## Insight Results for '{query}' ({method})"]
    for insight in results:
        parts.append(
            f"- [{insight.domain}] {insight.summary} (conf: {min(insight.confidence, 1.0):.0%})"
        )

    return "\n".join(parts)


@tool
def memory_stats(user_id: str = "default") -> str:
    """Get memory system statistics.

    Returns counts of memories, insights, domains, types, and average confidence.

    Args:
        user_id: User identifier

    Returns:
        Formatted statistics
    """
    store = get_memory_store(user_id)
    stats = store.get_stats()

    parts = [f"## Memory Statistics for {user_id}"]
    parts.append(f"- **Total memories**: {stats['total']}")
    parts.append(f"- **Average confidence**: {min(stats['avg_confidence'], 1.0):.1%}")
    parts.append(f"- **Consolidated**: {stats['consolidated']}")
    parts.append(f"- **Insights**: {stats['insights']}")
    parts.append("")
    parts.append("### By Domain")
    for domain, count in stats["by_domain"].items():
        parts.append(f"- {domain}: {count}")
    parts.append("")
    parts.append("### By Type")
    for mtype, count in stats["by_type"].items():
        parts.append(f"- {mtype}: {count}")
    parts.append("")
    parts.append("### By Source")
    for source, count in stats["by_source"].items():
        parts.append(f"- {source}: {count}")
    parts.append("")
    parts.append("### By Scope")
    for scope, count in stats["by_scope"].items():
        parts.append(f"- {scope}: {count}")

    return "\n".join(parts)


@tool
def memory_connect(
    memory_id: str,
    target_id: str,
    relationship: str = "relates_to",
    strength: float = 1.0,
    user_id: str = "default",
) -> str:
    """Create a connection between two memories with a relationship label.

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
    store.add_connection(memory_id, target_id, relationship=relationship, strength=strength)
    return f"Connected {memory_id} → {target_id} ({relationship}, strength: {strength})"


instincts_list = memory_list
instincts_remove = memory_remove
instincts_search = memory_search

__all__ = [
    "profile_set",
    "memory_list",
    "memory_remove",
    "memory_search",
    "memory_stats",
    "memory_connect",
    "insight_list",
    "insight_remove",
    "insight_search",
    "instincts_list",
    "instincts_remove",
    "instincts_search",
    "SCOPE_GLOBAL",
    "SCOPE_PROJECT",
    "CONNECTION_RELATIONSHIPS",
]
