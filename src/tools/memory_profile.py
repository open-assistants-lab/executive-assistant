"""Instincts tools for learning user preferences and behavioral patterns."""

from datetime import UTC, datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.storage.instincts import get_instincts_store

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

    Stores profile information as instincts with high confidence (1.0) so they
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
    store = get_instincts_store(user_id)

    if name:
        store.add_instinct(
            trigger="when user provides name",
            action=name,
            confidence=1.0,
            domain="personal",
            source="manual",
        )
    if role:
        store.add_instinct(
            trigger="when user provides role",
            action=role,
            confidence=1.0,
            domain="work",
            source="manual",
        )
    if company:
        store.add_instinct(
            trigger="when user provides company",
            action=company,
            confidence=1.0,
            domain="work",
            source="manual",
        )
    if city:
        store.add_instinct(
            trigger="when user provides location",
            action=city,
            confidence=1.0,
            domain="location",
            source="manual",
        )
    if bio:
        store.add_instinct(
            trigger="when user provides bio",
            action=bio,
            confidence=1.0,
            domain="personal",
            source="manual",
        )
    if interests:
        for interest in interests.split(","):
            interest = interest.strip()
            if interest:
                store.add_instinct(
                    trigger="when user provides interest",
                    action=interest,
                    confidence=1.0,
                    domain="interests",
                    source="manual",
                )
    if skills:
        for skill in skills.split(","):
            skill = skill.strip()
            if skill:
                store.add_instinct(
                    trigger="when user provides skill",
                    action=skill,
                    confidence=1.0,
                    domain="skills",
                    source="manual",
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

    return f"Profile updated for {user_id}. Use instincts_list to view all instincts."


@tool
def instincts_list(
    domain: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 20,
    user_id: str = "default",
) -> str:
    """List learned user instincts/preferences.

    Instincts are behavioral patterns learned from user interactions,
    including corrections, preferences, and workflow habits.

    Args:
        domain: Filter by domain (preference, workflow, correction, lesson)
        min_confidence: Minimum confidence score (0-1)
        limit: Maximum number of results
        user_id: User identifier

    Returns:
        Formatted list of instincts
    """
    store = get_instincts_store(user_id)
    instincts = store.list_instincts(domain=domain, min_confidence=min_confidence, limit=limit)

    if not instincts:
        return f"No instincts found for user {user_id}."

    parts = [f"## Learned Instincts for {user_id}"]
    if domain:
        parts.append(f"(filtered by domain: {domain})")
    parts.append("")

    for instinct in instincts:
        recency = ""
        now = datetime.now(UTC)
        days_old = (now - instinct.updated_at).days
        if days_old < 7:
            recency = " (recent)"
        elif days_old > 90:
            recency = " (outdated)"

        parts.append(f"### {instinct.id}")
        parts.append(f"- **When**: {instinct.trigger}")
        parts.append(f"- **Action**: {instinct.action}")
        parts.append(f"- **Confidence**: {instinct.confidence:.0%}{recency}")
        parts.append(f"- **Domain**: {instinct.domain}")
        parts.append(f"- **Observations**: {instinct.observations}")
        parts.append("")

    return "\n".join(parts)


@tool
def instincts_remove(instinct_id: str, user_id: str = "default") -> str:
    """Remove a learned instinct.

    Args:
        instinct_id: The instinct ID to remove
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_instincts_store(user_id)
    removed = store.remove_instinct(instinct_id)

    if removed:
        logger.info("instinct.removed", {"instinct_id": instinct_id}, user_id=user_id)
        return f"Removed instinct: {instinct_id}"
    else:
        return f"Instinct not found: {instinct_id}"


@tool
def instincts_search(
    query: str,
    method: str = "hybrid",
    limit: int = 10,
    user_id: str = "default",
) -> str:
    """Search instincts using keyword, semantic, or hybrid search.

    Args:
        query: Search query
        method: Search method (fts, semantic, or hybrid)
        limit: Maximum results
        user_id: User identifier

    Returns:
        Search results
    """
    store = get_instincts_store(user_id)

    if method == "fts":
        results = store.search_fts(query, limit=limit)
    elif method == "semantic":
        results = store.search_semantic(query, limit=limit)
    else:
        results = store.search_hybrid(query, limit=limit)

    if not results:
        return f"No results found for: {query}"

    parts = [f"## Search Results for '{query}' ({method})"]
    for instinct in results:
        parts.append(f"- **{instinct.trigger}**: {instinct.action}")

    return "\n".join(parts)
