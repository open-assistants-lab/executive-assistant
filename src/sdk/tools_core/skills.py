"""Skills tools — SDK-native implementation.

Skills are on-demand knowledge modules (SKILL.md files) that agents can
load when handling specific task types.

Design:
  1. Skill catalog is injected into the system prompt at startup.
     The agent always knows what skills are available.
  2. When a task matches a skill's description, call skills_load(name).
  3. After creating/editing/deleting a SKILL.md file via files_* tools,
     call skills_reload() to refresh the catalog.
  4. Both tools respect item_scopes (All / Selected / None) per workspace.
"""

from __future__ import annotations

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.skills.registry import get_skill_registry
from src.storage.paths import get_paths

logger = get_logger()


def _get_registry(user_id: str, workspace_id: str = "personal"):
    return get_skill_registry(user_id=user_id, workspace_id=workspace_id)


def _is_available(name: str, user_id: str, workspace_id: str) -> tuple[bool, str]:
    """Check item_scopes: returns (available, reason)."""
    try:
        from connectkit.item_scopes import ItemScopeDB

        paths = get_paths(user_id, workspace_id=workspace_id)
        scope_db = ItemScopeDB(paths.base)
        excluded = scope_db.get_excluded_names(user_id, "skill")
        if name in excluded:
            return False, f"Skill '{name}' is disabled (scope=none)."
        scoped = scope_db.get(user_id, "skill", name)
        if scoped and scoped.scope == "selected" and workspace_id not in scoped.workspace_ids:
            return False, f"Skill '{name}' is not enabled for this workspace (scope=selected)."
    except Exception:
        pass
    return True, ""


def _get_registry(user_id: str, workspace_id: str = "personal"):
    return get_skill_registry(user_id=user_id, workspace_id=workspace_id)


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
        name: Skill name (e.g. 'skill-creation', 'autoresearch')
        user_id: User identifier
        workspace_id: Workspace identifier

    Returns:
        The skill's full instructions, or an error if not found.
    """
    try:
        registry = _get_registry(user_id, workspace_id)
    except Exception as exc:
        return str(exc)

    available, reason = _is_available(name, user_id, workspace_id)
    if not available:
        return reason

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

    registry.mark_skill_loaded(name)

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
    except Exception as exc:
        return str(exc)

    skills = registry.get_all_skills()
    if not skills:
        return "No skills available."

    # Filter by item_scopes for this workspace
    available_skills = []
    for s in skills:
        name = s.get("name", "")
        avail, _ = _is_available(name, user_id, workspace_id)
        if avail:
            available_skills.append(s)

    parts: list[str] = []
    for s in available_skills:
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
