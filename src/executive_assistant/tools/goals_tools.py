"""Minimal goals tools for user-facing goal management."""

from __future__ import annotations

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.goals_storage import get_goals_storage


def _require_thread_id() -> str:
    thread_id = get_thread_id()
    if not thread_id:
        raise ValueError("No thread_id in context.")
    return thread_id


def _resolve_goal_id(goal_id_or_prefix: str, thread_id: str) -> tuple[str | None, str | None]:
    storage = get_goals_storage()
    goals = storage.list_goals(thread_id=thread_id, limit=500)

    exact = [g["id"] for g in goals if g["id"] == goal_id_or_prefix]
    if exact:
        return exact[0], None

    matches = [g["id"] for g in goals if g["id"].startswith(goal_id_or_prefix)]
    if not matches:
        return None, f"Goal not found: {goal_id_or_prefix}"
    if len(matches) > 1:
        return None, f"Ambiguous goal ID prefix: {goal_id_or_prefix} (matches {len(matches)} goals)"
    return matches[0], None


@tool
def create_goal(
    title: str,
    category: str = "short_term",
    priority: int = 5,
    importance: int = 5,
    description: str | None = None,
    target_date: str | None = None,
) -> str:
    """
    Create a goal for the current thread.

    Args:
        title: Goal title.
        category: Goal category (for example: short_term, medium_term, long_term).
        priority: Priority (1-10).
        importance: Importance (1-10).
        description: Optional description.
        target_date: Optional target date (ISO timestamp).

    Returns:
        Confirmation with goal ID.
    """
    if not (1 <= priority <= 10):
        return "Error: priority must be between 1 and 10."
    if not (1 <= importance <= 10):
        return "Error: importance must be between 1 and 10."

    thread_id = _require_thread_id()
    storage = get_goals_storage()
    goal_id = storage.create_goal(
        title=title,
        category=category,
        priority=priority,
        importance=importance,
        description=description,
        target_date=target_date,
        thread_id=thread_id,
    )
    return f"Goal created: {goal_id}"


@tool
def list_goals(
    status: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> str:
    """
    List goals for the current thread.

    Args:
        status: Optional status filter.
        category: Optional category filter.
        limit: Max number of goals to return.

    Returns:
        Formatted goals list.
    """
    thread_id = _require_thread_id()
    storage = get_goals_storage()
    bounded_limit = max(1, min(limit, 100))
    goals = storage.list_goals(
        thread_id=thread_id,
        status=status,
        category=category,
        limit=bounded_limit,
    )

    if not goals:
        return "No goals found."

    lines = [f"Goals ({len(goals)}):"]
    for goal in goals:
        lines.append(
            f"- {goal['id'][:8]}... | {goal['title']} | "
            f"status={goal['status']} progress={goal['progress']:.1f}% "
            f"priority={goal['priority']} importance={goal['importance']}"
        )
    return "\n".join(lines)


@tool
def update_goal(
    goal_id: str,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    target_date: str | None = None,
    status: str | None = None,
    progress: float | None = None,
    priority: int | None = None,
    importance: int | None = None,
) -> str:
    """
    Update a goal by ID or ID prefix.

    Args:
        goal_id: Goal ID or unique prefix.
        title: Updated title.
        description: Updated description.
        category: Updated category.
        target_date: Updated target date (ISO timestamp).
        status: Updated status.
        progress: Updated progress (0-100).
        priority: Updated priority (1-10).
        importance: Updated importance (1-10).

    Returns:
        Update status with final goal state.
    """
    if progress is not None and not (0.0 <= progress <= 100.0):
        return "Error: progress must be between 0 and 100."
    if priority is not None and not (1 <= priority <= 10):
        return "Error: priority must be between 1 and 10."
    if importance is not None and not (1 <= importance <= 10):
        return "Error: importance must be between 1 and 10."

    thread_id = _require_thread_id()
    resolved_goal_id, err = _resolve_goal_id(goal_id, thread_id)
    if err:
        return err
    assert resolved_goal_id is not None

    has_non_progress_update = any(
        value is not None
        for value in [title, description, category, target_date, status, priority, importance]
    )
    if not has_non_progress_update and progress is None:
        return "No update fields provided."

    storage = get_goals_storage()
    updated = False

    if has_non_progress_update:
        updated = storage.update_goal(
            goal_id=resolved_goal_id,
            thread_id=thread_id,
            title=title,
            description=description,
            category=category,
            target_date=target_date,
            status=status,
            priority=priority,
            importance=importance,
            change_type="modification",
            change_reason="Updated via goals tool",
        )

    if progress is not None:
        progress_updated = storage.update_goal_progress(
            goal_id=resolved_goal_id,
            thread_id=thread_id,
            progress=progress,
            source="manual",
            notes="Updated via goals tool",
        )
        updated = updated or progress_updated

    if not updated:
        return f"Failed to update goal: {goal_id}"

    goal = storage.get_goal(resolved_goal_id, thread_id=thread_id)
    if not goal:
        return f"Goal updated: {resolved_goal_id}"

    return (
        f"Goal updated: {goal['id'][:8]}... | {goal['title']} | "
        f"status={goal['status']} progress={goal['progress']:.1f}%"
    )


def get_goals_tools() -> list:
    """Get all goals tools for the agent."""
    return [create_goal, list_goals, update_goal]

