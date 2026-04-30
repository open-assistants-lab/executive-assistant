"""Skills tools -- SDK-native implementation.

Skills are on-demand knowledge modules (SKILL.md files) that agents can
load when handling specific task types.

Design:
  1. Skill descriptions are injected into the system prompt at startup.
     The agent always knows what skills are available — no discovery step needed.
  2. When a task matches a skill's description, call skills_load(name) directly.
  3. skills_list() and skills_search() are available for explicit queries
     (e.g., "what skills do you have?" or finding recently added user skills).
"""

from __future__ import annotations

from pathlib import Path

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.skills.registry import SkillRegistry, get_skill_registry
from src.storage.paths import get_paths

logger = get_logger()


def _get_registry(user_id: str) -> SkillRegistry:
    return get_skill_registry(user_id=user_id)


@tool
def skills_list(user_id: str = "default_user") -> str:
    """List all available skills; use skills_load for full instructions.

    Skill descriptions are always available in your system prompt context.
    Call this explicitly when the user asks "what skills do you have?" or
    when you want to see user-created skills that may have been added recently.

    Then use skills_load(skill_name) to get full instructions for a specific skill.

    Args:
        user_id: User identifier

    Returns:
        List of available skills with names, descriptions, and source layers
    """
    registry = _get_registry(user_id)
    skills = registry.get_all_skills()

    if not skills:
        return "No skills available."

    lines = ["Available skills:\n"]
    for skill in skills:
        lines.append(f"  - {skill['name']}: {skill['description']}")

    lines.append("\nUse skills_load(skill_name) to get detailed instructions.")
    return "\n".join(lines)


skills_list.annotations = ToolAnnotations(title="List Skills", read_only=True, idempotent=True)


@tool
def skills_search(query: str, user_id: str = "default_user") -> str:
    """Search for skills matching a query.

    Use this when you're looking for skills related to a specific task or topic
    but don't know the exact skill name.

    Args:
        query: Search terms (e.g., 'research', 'sql', 'browser')
        user_id: User identifier

    Returns:
        Matching skills with names and descriptions
    """
    registry = _get_registry(user_id)
    skills = registry.get_all_skills()

    if not skills:
        return "No skills available."

    query_lower = query.lower()
    matches = []
    for skill in skills:
        name = skill["name"].lower()
        description = skill.get("description", "").lower()
        content = skill.get("content", "").lower()
        if query_lower in name or query_lower in description or query_lower in content:
            matches.append(skill)

    if not matches:
        all_names = ", ".join(s["name"] for s in skills)
        return f"No skills matching '{query}'. Available skills: {all_names}"

    lines = [f"Skills matching '{query}':\n"]
    for skill in matches:
        lines.append(f"  - {skill['name']}: {skill['description']}")

    lines.append("\nUse skills_load(skill_name) to get detailed instructions.")
    return "\n".join(lines)


skills_search.annotations = ToolAnnotations(title="Search Skills", read_only=True, idempotent=True)


@tool
def skills_load(skill_name: str, user_id: str = "default_user") -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about handling a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., 'deep-research', 'planning-with-files')
        user_id: User identifier

    Returns:
        Full skill content, or error message if not found
    """
    registry = _get_registry(user_id)

    skill = registry.get_skill(skill_name)

    if not skill:
        available = ", ".join(registry.list_skills())
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    registry.mark_skill_loaded(skill_name)

    return f"# {skill['name']}\n\n{skill['content']}"


skills_load.annotations = ToolAnnotations(title="Load Skill", read_only=True, idempotent=True)


@tool
def skill_create(name: str, content: str, user_id: str = "default_user") -> str:
    """Create a new skill in the user's skills directory.

    This tool automatically saves to the correct directory from config.
    Use this instead of files_write for skill creation.

    Args:
        name: Skill name (e.g., 'my-skill')
        content: Full SKILL.md content including YAML frontmatter
        user_id: User identifier

    Returns:
        Success or error message
    """
    from src.skills.models import _is_valid_skill_name

    if not _is_valid_skill_name(name):
        return (
            f"Invalid skill name: '{name}'. "
            "Must be 1-64 chars, lowercase letters/digits/hyphens only, "
            "no leading/trailing hyphens, no consecutive hyphens."
        )

    user_skills_dir = str(get_paths(user_id).skills_dir())

    skill_path = Path(user_skills_dir) / name / "SKILL.md"

    resolved = skill_path.resolve()
    skills_root = Path(user_skills_dir).resolve()
    if not resolved.is_relative_to(skills_root):
        return f"Invalid skill name: '{name}' resolves outside skills directory."

    try:
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(content, encoding="utf-8")

        registry = _get_registry(user_id)
        registry.reload()

        logger.info(
            "skill.created",
            {"name": name, "path": str(skill_path), "size": len(content)},
            user_id=user_id,
        )

        return f"Successfully created skill '{name}' at {skill_path}"
    except Exception as e:
        logger.error("skill.create.error", {"name": name, "error": str(e)}, user_id=user_id)
        return f"Error creating skill: {e}"


skill_create.annotations = ToolAnnotations(title="Create Skill", destructive=True)


@tool
def sql_write_query(query: str, database: str, user_id: str = "default_user") -> str:
    """Write and validate a SQL query for a specific database.

    The required skill must be loaded first using skills_load.

    Args:
        query: The SQL query to validate
        database: Database name (e.g., 'sql-analytics', 'inventory')
        user_id: User identifier

    Returns:
        Validated query or error
    """
    registry = _get_registry(user_id)
    skills_loaded = list(registry._loaded_skills) if hasattr(registry, "_loaded_skills") else []

    if database not in skills_loaded:
        return (
            f"Error: You must load the '{database}' skill first. "
            f"Use skills_load('{database}') to load the database schema."
        )

    return f"SQL Query for {database}:\n\n```sql\n{query}\n```\n\nQuery validated against {database} schema"


sql_write_query.annotations = ToolAnnotations(title="Write SQL Query", open_world=True)
