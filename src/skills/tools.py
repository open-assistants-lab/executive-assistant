"""Load skill tool for on-demand skill content loading.

Based on LangChain docs: https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
"""

import threading
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from src.skills.registry import SkillRegistry

# Per-user registry instances (thread-safe)
_registries: dict[str, SkillRegistry] = {}
_lock = threading.Lock()


def set_skill_registry(registry: SkillRegistry, user_id: str | None = None) -> None:
    """Set the skill registry for a specific user.

    Args:
        registry: SkillRegistry instance
        user_id: User ID to associate with this registry. If None, uses "default".
    """
    uid = user_id or "default"
    with _lock:
        _registries[uid] = registry


def get_skill_registry(system_dir: str = "src/skills", user_id: str | None = None) -> SkillRegistry:
    """Get or create skill registry for a specific user.

    Each user gets their own SkillRegistry instance so that user-specific
    skills are isolated. Previously, a single global registry was shared
    across all users, causing cross-user data leakage.

    Args:
        system_dir: Path to system skills directory
        user_id: User ID for user-specific skills

    Returns:
        SkillRegistry instance for the given user
    """
    uid = user_id or "default"
    with _lock:
        if uid not in _registries:
            _registries[uid] = SkillRegistry(system_dir=system_dir, user_id=user_id)
        return _registries[uid]


@tool
def skills_load(
    skill_name: str,
    runtime: Any | None = None,
    user_id: str = "default",
) -> str | Command:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about handling a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "pdf-processing", "sql-analytics")
        user_id: User identifier

    Returns:
        Full skill content as a ToolMessage, or error message if not found.
        When runtime is provided, also updates state to track loaded skill.
    """
    registry = get_skill_registry(user_id=user_id)

    skill = registry.get_skill(skill_name)

    if not skill:
        available = ", ".join(registry.list_skills())
        error_msg = f"Skill '{skill_name}' not found. Available skills: {available}"

        if runtime:
            tool_call_id = getattr(runtime, "tool_call_id", None)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id or "unknown",
                        )
                    ]
                }
            )
        return error_msg

    # Build skill content
    skill_content = f"# {skill['name']}\n\n{skill['content']}"

    if runtime:
        # Track loaded skill in registry (the middleware checks registry for gating)
        registry.mark_skill_loaded(skill_name)

        tool_call_id = getattr(runtime, "tool_call_id", None)
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=skill_content,
                        tool_call_id=tool_call_id or "unknown",
                    )
                ],
            }
        )

    return skill_content


def list_available_skills(user_id: str = "default") -> str:
    """List all available skills.

    Args:
        user_id: User identifier

    Returns:
        Formatted list of skill names and descriptions
    """
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
    from pathlib import Path

    from src.skills.models import _is_valid_skill_name

    if not _is_valid_skill_name(name):
        return (
            f"Invalid skill name: '{name}'. "
            "Must be 1-64 chars, lowercase letters/digits/hyphens only, "
            "no leading/trailing hyphens, no consecutive hyphens."
        )

    user_skills_dir = f"data/users/{user_id}/skills"

    skill_path = Path(user_skills_dir) / name / "SKILL.md"

    # Verify the resolved path stays within the user's skills directory
    resolved = skill_path.resolve()
    skills_root = Path(user_skills_dir).resolve()
    if not resolved.is_relative_to(skills_root):
        return f"Invalid skill name: '{name}' resolves outside skills directory."

    try:
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(content, encoding="utf-8")

        # Invalidate registry cache so the new skill is visible
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
