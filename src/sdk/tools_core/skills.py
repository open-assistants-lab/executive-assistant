"""Skills tools — SDK-native implementation.

Skills are on-demand knowledge modules (SKILL.md files) that agents can
load when handling specific task types.

Design:
  1. Skill catalog is injected into the system prompt at startup.
     The agent always knows what skills are available.
  2. When a task matches a skill's description, call skills_load(name).
  3. After creating/editing/deleting a SKILL.md file via files_* tools,
     call skills_reload() to refresh the catalog.
"""

from __future__ import annotations

import logging

from src.sdk.tools import tool, ToolAnnotations
from src.storage.paths import get_paths
from src.app_logging import get_logger

from src.skills.registry import get_skill_registry

logger = get_logger()


def _get_registry(user_id: str, workspace_id: str = "personal"):
    """Resolve the SkillRegistry for the given user and workspace."""
    try:
        return get_skill_registry(user_id=user_id, workspace_id=workspace_id)
    except Exception as exc:
        raise RuntimeError(f"Could not resolve skill registry: {exc}") from exc


@tool
def skills_load(
    name: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Load a skill's full SKILL.md content into context.

    Call this when the current task matches a skill's description from the
    available skills catalog in the system prompt.

    Args:
        name: Skill name (e.g. 'skill-creator', 'autoresearch')
        user_id: User identifier
        workspace_id: Workspace identifier

    Returns:
        The skill's full instructions, or an error if not found.
    """
    try:
        registry = _get_registry(user_id, workspace_id)
    except RuntimeError as exc:
        return str(exc)

    skill = registry.get_skill(name)
    if not skill:
        available = [s["name"] for s in registry.get_all_skills()]
        return f"Skill '{name}' not found. Available skills: {', '.join(available) or 'none'}."

    parts = [
        f"<skill_content name=\"{skill.get('name', name)}\">",
        skill.get("content", "").strip(),
        "</skill_content>",
    ]

    if not skill.get("content"):
        return f"Skill '{name}' exists but has no content."

    registry.touch(name)

    logger.info(
        "skill.loaded",
        {"name": name},
        user_id=user_id,
    )

    return "\n".join(parts)


skills_load.annotations = ToolAnnotations(
    title="Load Skill", read_only=True, idempotent=True
)


@tool
def skills_reload(
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Reload the skill registry after creating, editing, or deleting SKILL.md files.

    Call this after using files_write, files_edit, or files_delete to create,
    modify, or remove a SKILL.md file. The registry must be reloaded for the
    new or changed skill to appear in the available skills catalog.

    Args:
        user_id: User identifier
        workspace_id: Workspace identifier

    Returns:
        Updated list of available skills with their descriptions.
    """
    try:
        registry = _get_registry(user_id, workspace_id)
        registry.reload()
    except RuntimeError as exc:
        return str(exc)

    skills = registry.get_all_skills()
    if not skills:
        return "No skills available."

    parts: list[str] = []
    for s in skills:
        name = s.get("name", "")
        desc = s.get("description", "") or ""
        loaded = " [loaded]" if name in registry.get_loaded_skills() else ""
        parts.append(f"  {name}: {desc}{loaded}")

    logger.info(
        "skill.reloaded",
        {"count": len(skills)},
        user_id=user_id,
    )

    return "Skills reloaded:\n" + "\n".join(parts)


skills_reload.annotations = ToolAnnotations(
    title="Reload Skills", read_only=False, destructive=False, idempotent=True
)
