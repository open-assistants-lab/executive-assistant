"""Todo tool for agent - track tasks during complex multi-step operations."""

import uuid
from typing import Literal

from langchain_core.tools import tool

from src.app_logging import get_logger

logger = get_logger()

TodoStatus = Literal["pending", "in_progress", "completed"]


class TodoItem:
    """Todo item with id, content, status, and optional priority."""

    def __init__(
        self,
        content: str,
        status: TodoStatus = "pending",
        priority: int = 0,
        todo_id: str | None = None,
    ):
        self.id = todo_id or str(uuid.uuid4())[:8]
        self.content = content
        self.status = status
        self.priority = priority

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TodoItem":
        return cls(
            content=data["content"],
            status=data["status"],
            priority=data.get("priority", 0),
            todo_id=data.get("id"),
        )


_todos: dict[str, list[TodoItem]] = {}


def _get_user_todos(user_id: str) -> list[TodoItem]:
    """Get todos for a user."""
    if user_id not in _todos:
        _todos[user_id] = []
    return _todos[user_id]


@tool
def write_todos(
    todos: list[dict] | None = None,
    action: Literal["list", "add", "update", "delete", "replace"] = "list",
    todo_id: str | None = None,
    content: str | None = None,
    status: TodoStatus | None = None,
    user_id: str = "default",
) -> str:
    """Manage todo list for tracking complex multi-step tasks.

    Use this tool when:
    - User asks for multi-step tasks (e.g., "plan a trip", "refactor codebase")
    - Breaking down complex requests into actionable steps
    - Tracking progress on ongoing tasks

    Args:
        todos: List of todo items for replace action. Each item: {"content": str, "status": "pending"|"in_progress"|"completed", "priority": int}
        action: Action to perform - "list", "add", "update", "delete", or "replace"
        todo_id: ID of todo to update/delete (for add/update/delete actions)
        content: Todo content (for add/update actions)
        status: Todo status - "pending", "in_progress", "completed" (for add/update actions)
        user_id: User identifier

    Returns:
        Current todo list in markdown format, suitable for displaying to user.
        ALWAYS show the result to the user after modifying todos.

    Examples:
        # List all todos
        write_todos.invoke({"action": "list", "user_id": "default"})

        # Add a new todo
        write_todos.invoke({"action": "add", "content": "Book flight", "status": "pending", "user_id": "default"})

        # Update todo status
        write_todos.invoke({"action": "update", "todo_id": "abc123", "status": "completed", "user_id": "default"})

        # Replace entire todo list (useful for planning)
        write_todos.invoke({"todos": [{"content": "Step 1", "status": "pending"}, {"content": "Step 2", "status": "pending"}], "action": "replace", "user_id": "default"})
    """
    user_todos = _get_user_todos(user_id)

    if action == "list":
        pass

    elif action == "add":
        if not content:
            return "Error: content is required for add action"
        new_todo = TodoItem(content=content, status=status or "pending")
        user_todos.append(new_todo)
        todo_id = new_todo.id

    elif action == "update":
        if not todo_id:
            return "Error: todo_id is required for update action"
        found = False
        for todo in user_todos:
            if todo.id == todo_id:
                if content:
                    todo.content = content
                if status:
                    todo.status = status
                found = True
                break
        if not found:
            return f"Error: todo with id {todo_id} not found"

    elif action == "delete":
        if not todo_id:
            return "Error: todo_id is required for delete action"
        user_todos[:] = [t for t in user_todos if t.id != todo_id]

    elif action == "replace":
        if todos is None:
            return "Error: todos list is required for replace action"
        user_todos.clear()
        for item in todos:
            user_todos.append(TodoItem.from_dict(item))

    else:
        return f"Error: unknown action {action}"

    return _format_todos(user_todos)


def _format_todos(todos: list[TodoItem]) -> str:
    """Format todos as markdown for display."""
    if not todos:
        return "No todos yet."

    lines = ["### 📋 Todo List\n"]

    pending = [t for t in todos if t.status == "pending"]
    in_progress = [t for t in todos if t.status == "in_progress"]
    completed = [t for t in todos if t.status == "completed"]

    if in_progress:
        lines.append("**🔄 In Progress:**")
        for t in in_progress:
            lines.append(f"- [ ] *{t.content}*")
        lines.append("")

    if pending:
        lines.append("**📝 Pending:**")
        for t in pending:
            lines.append(f"- [ ] {t.content}")
        lines.append("")

    if completed:
        lines.append("**✅ Completed:**")
        for t in completed:
            lines.append(f"- [x] ~~{t.content}~~")
        lines.append("")

    return "\n".join(lines)
