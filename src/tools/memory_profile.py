"""Memory tools for learning user preferences and behavioral patterns."""

from datetime import UTC, datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.storage.memory import (
    DEFAULT_CONFIDENCE,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
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

    if name:
        store.add_memory(
            trigger="when user provides name",
            action=name,
            confidence=1.0,
            domain="personal",
            source=SOURCE_EXPLICIT,
            memory_type=MEMORY_TYPE_FACT,
            is_update=True,
        )
    if role:
        store.add_memory(
            trigger="when user provides role",
            action=role,
            confidence=1.0,
            domain="work",
            source=SOURCE_EXPLICIT,
            memory_type=MEMORY_TYPE_FACT,
            is_update=True,
        )
    if company:
        store.add_memory(
            trigger="when user provides company",
            action=company,
            confidence=1.0,
            domain="work",
            source=SOURCE_EXPLICIT,
            memory_type=MEMORY_TYPE_FACT,
            is_update=True,
        )
    if city:
        store.add_memory(
            trigger="when user provides location",
            action=city,
            confidence=1.0,
            domain="location",
            source=SOURCE_EXPLICIT,
            memory_type=MEMORY_TYPE_FACT,
            is_update=True,
        )
    if bio:
        store.add_memory(
            trigger="when user provides bio",
            action=bio,
            confidence=1.0,
            domain="personal",
            source=SOURCE_EXPLICIT,
            memory_type=MEMORY_TYPE_FACT,
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

    Returns:
        Formatted list of memories
    """
    store = get_memory_store(user_id)
    memories = store.list_memories(
        domain=domain,
        memory_type=memory_type,
        min_confidence=min_confidence,
        limit=limit,
    )

    if not memories:
        return f"No memories found for user {user_id}."

    parts = [f"## Learned Memories for {user_id}"]
    if domain:
        parts.append(f"(filtered by domain: {domain})")
    if memory_type:
        parts.append(f"(filtered by type: {memory_type})")
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
        parts.append(f"- **Confidence**: {memory.confidence:.0%}{recency}")
        parts.append(f"- **Domain**: {memory.domain}")
        parts.append(f"- **Type**: {memory.memory_type}")
        parts.append(f"- **Observations**: {memory.observations}")
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
        method: Search method (fts, semantic, or hybrid)
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
    else:
        results = store.search_hybrid(query, limit=limit)

    if not results:
        return f"No results found for: {query}"

    parts = [f"## Search Results for '{query}' ({method})"]
    for memory in results:
        parts.append(f"- **{memory.trigger}**: {memory.action}")

    return "\n".join(parts)


# Backward compatibility aliases
instincts_list = memory_list
instincts_remove = memory_remove
instincts_search = memory_search

__all__ = [
    "profile_set",
    "memory_list",
    "memory_remove",
    "memory_search",
    "instincts_list",
    "instincts_remove",
    "instincts_search",
]
