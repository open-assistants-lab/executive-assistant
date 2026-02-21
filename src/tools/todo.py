"""Todo tools for agent - manage tasks/todos."""

import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


def _get_todo_path(user_id: str) -> Path:
    """Get path to user's todo file."""
    settings = get_settings()
    root = Path(settings.filesystem.root_path.format(user_id=user_id))
    root.mkdir(parents=True, exist_ok=True)
    return root / "todos.json"


def _load_todos(user_id: str) -> list[dict]:
    """Load todos from file."""
    todo_file = _get_todo_path(user_id)
    if not todo_file.exists():
        return []
    import json

    try:
        return json.loads(todo_file.read_text())
    except Exception:
        return []


def _save_todos(user_id: str, todos: list[dict]) -> None:
    """Save todos to file."""
    import json

    todo_file = _get_todo_path(user_id)
    todo_file.write_text(json.dumps(todos, indent=2))


@tool
def todo_add(
    title: str, due: str | None = None, priority: str = "medium", user_id: str = "default"
) -> str:
    """Add a task to the todo list.

    Args:
        title: Task title/description
        due: Due date (optional, e.g., "2024-12-31" or "tomorrow")
        priority: Priority level (low, medium, high)
        user_id: User identifier

    Returns:
        Confirmation message with task ID
    """
    todos = _load_todos(user_id)

    task_id = str(uuid.uuid4())[:8]
    task = {
        "id": task_id,
        "title": title,
        "due": due,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    todos.append(task)
    _save_todos(user_id, todos)

    logger.info("todo_add", {"task_id": task_id, "title": title, "priority": priority})
    return f"Added task **{task_id}**: {title}\nPriority: {priority}\nDue: {due or 'Not set'}"


@tool
def todo_list(status: str = "all", priority: str | None = None, user_id: str = "default") -> str:
    """List tasks from the todo list.

    Args:
        status: Filter by status (all, pending, completed)
        priority: Filter by priority (low, medium, high)
        user_id: User identifier

    Returns:
        Formatted list of tasks
    """
    todos = _load_todos(user_id)

    filtered = todos
    if status != "all":
        filtered = [t for t in filtered if t.get("status") == status]
    if priority:
        filtered = [t for t in filtered if t.get("priority") == priority]

    if not filtered:
        return "No tasks found."

    lines = ["## Todo List\n"]
    for t in filtered:
        status_icon = "✅" if t.get("status") == "completed" else "⬜"
        due = t.get("due", "No due date")
        lines.append(
            f"- {status_icon} **[{t['id']}]** {t['title']} (priority: {t['priority']}, due: {due})"
        )

    lines.append(f"\nTotal: {len(filtered)} tasks")
    return "\n".join(lines)


@tool
def todo_complete(task_id: str, user_id: str = "default") -> str:
    """Mark a task as completed.

    Args:
        task_id: Task ID to mark as completed
        user_id: User identifier

    Returns:
        Confirmation message
    """
    todos = _load_todos(user_id)

    for t in todos:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["completed_at"] = datetime.now().isoformat()
            _save_todos(user_id, todos)
            logger.info("todo_complete", {"task_id": task_id})
            return f"Completed task **[{task_id}]**: {t['title']}"

    return f"Task **[{task_id}]** not found."


@tool
def todo_delete(task_id: str, user_id: str = "default") -> str:
    """Delete a task from the todo list.

    NOTE: This tool requires human approval before execution.

    Args:
        task_id: Task ID to delete
        user_id: User identifier

    Returns:
        Confirmation message
    """
    todos = _load_todos(user_id)

    for i, t in enumerate(todos):
        if t["id"] == task_id:
            title = t["title"]
            todos.pop(i)
            _save_todos(user_id, todos)
            logger.info("todo_delete", {"task_id": task_id})
            return f"Deleted task **[{task_id}]**: {title}"

    return f"Task **[{task_id}]** not found."
