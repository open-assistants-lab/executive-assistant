"""Skills tools — SDK-native implementation."""

import threading
from pathlib import Path
from typing import Any

from src.sdk.tools import tool
from src.skills.registry import SkillRegistry
from src.storage.paths import get_paths

_registries: dict[str, SkillRegistry] = {}
_lock = threading.Lock()


def set_skill_registry(registry: SkillRegistry, user_id: str | None = None) -> None:
    uid = user_id or "default"
    with _lock:
        _registries[uid] = registry


def get_skill_registry(system_dir: str = "src/skills", user_id: str | None = None) -> SkillRegistry:
    uid = user_id or "default"
    with _lock:
        if uid not in _registries:
            _registries[uid] = SkillRegistry(system_dir=system_dir, user_id=user_id)
        return _registries[uid]


@tool
def skills_load(
    skill_name: str,
    user_id: str = "default",
) -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about handling a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "pdf-processing", "sql-analytics")
        user_id: User identifier

    Returns:
        Full skill content, or error message if not found.
    """
    registry = get_skill_registry(user_id=user_id)

    skill = registry.get_skill(skill_name)

    if not skill:
        available = ", ".join(registry.list_skills())
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    skill_content = f"# {skill['name']}\n\n{skill['content']}"

    registry.mark_skill_loaded(skill_name)

    return skill_content


def list_available_skills(user_id: str = "default") -> str:
    """List all available skills."""
    registry = get_skill_registry(user_id=user_id)
    skills = registry.get_all_skills()

    if not skills:
        return "No skills available."

    lines = ["### Available Skills\n"]
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")

    return "\n".join(lines)


@tool
def skills_list(user_id: str = "default") -> str:
    """List all available skills with their descriptions.

    Use this to see what skills are available before loading one.

    Args:
        user_id: User identifier

    Returns:
        Formatted list of available skills
    """
    return list_available_skills(user_id=user_id)


@tool
def skill_create(
    name: str,
    content: str,
    user_id: str = "default",
) -> str:
    """Create a new skill in the user's skills directory.

    This tool automatically saves to the correct directory from config.
    Use this instead of files_write for skill creation.

    Args:
        name: Skill name (e.g., "my-skill")
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

    skills_dir = get_paths(user_id).skills_dir()
    skill_path = skills_dir / name / "SKILL.md"

    resolved = skill_path.resolve()
    if not resolved.is_relative_to(skills_dir.resolve()):
        return f"Invalid skill name: '{name}' resolves outside skills directory."

    try:
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(content, encoding="utf-8")

        registry = get_skill_registry(user_id=user_id)
        registry.reload()

        from src.app_logging import get_logger

        logger = get_logger()
        logger.info(
            "skill.created",
            {"name": name, "path": str(skill_path), "size": len(content)},
            user_id=user_id,
        )

        return f"Successfully created skill '{name}' at {skill_path}"
    except Exception as e:
        from src.app_logging import get_logger

        logger = get_logger()
        logger.error(
            "skill.create.error",
            {"name": name, "error": str(e)},
            user_id=user_id,
        )
        return f"Error creating skill: {e}"
