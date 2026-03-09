"""Profile and instincts tools."""

from datetime import datetime

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.storage.instincts import get_instincts_store
from src.storage.profile import get_profile_store

logger = get_logger()


@tool
def profile_get(user_id: str = "default") -> str:
    """Get user profile information.

    Returns the user's profile including name, role, company, city, bio,
    preferences, interests, and other background information.

    Args:
        user_id: User identifier

    Returns:
        Formatted profile information
    """
    store = get_profile_store(user_id)
    profile = store.get_profile()

    if not profile:
        return f"No profile found for user {user_id}. Use profile_set to add information."

    parts = [f"## User Profile: {user_id}"]

    if profile.name:
        parts.append(f"Name: {profile.name}")
    if profile.role:
        parts.append(f"Role: {profile.role}")
    if profile.company:
        parts.append(f"Company: {profile.company}")
    if profile.city:
        parts.append(f"City: {profile.city}")
    if profile.bio:
        parts.append(f"Bio: {profile.bio}")
    if profile.preferences:
        parts.append(f"Preferences: {profile.preferences}")
    if profile.interests:
        parts.append(f"Interests: {profile.interests}")
    if profile.background:
        parts.append(f"Background: {profile.background}")

    parts.append(f"\nSource: {profile.source}")
    parts.append(f"Confidence: {profile.confidence}")
    parts.append(f"Updated: {profile.updated_at}")

    return "\n".join(parts)


@tool
def profile_set(
    name: str | None = None,
    role: str | None = None,
    company: str | None = None,
    city: str | None = None,
    bio: str | None = None,
    user_id: str = "default",
) -> str:
    """Set user profile information manually.

    Args:
        name: User's name
        role: User's role (e.g., developer, manager, designer)
        company: User's company
        city: User's city/location
        bio: Short bio about the user
        user_id: User identifier

    Returns:
        Confirmation message
    """
    store = get_profile_store(user_id)

    store.set_profile(
        name=name,
        role=role,
        company=company,
        city=city,
        bio=bio,
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

    return f"Profile updated for {user_id}:\n" + store.to_context()


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
        days_old = (datetime.now() - instinct.updated_at).days
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
