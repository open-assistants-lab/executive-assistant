"""Todo List Display Middleware for exposing planned tasks to users.

This middleware integrates with LangChain's native TodoListMiddleware to display
the agent's todo list in real-time via status updates.

Usage:
    from executive_assistant.agent.todo_display import TodoDisplayMiddleware
    from langchain.agents.middleware import TodoListMiddleware

    # Use both middlewares together
    middleware = [
        TodoListMiddleware(),           # Adds write_todos tool and state
        TodoDisplayMiddleware(channel)   # Displays todos via status updates
    ]
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id

if TYPE_CHECKING:
    from executive_assistant.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class TodoDisplayMiddleware(AgentMiddleware):
    """
    Middleware that displays the agent's todo list to users via status updates.

    This works with LangChain's TodoListMiddleware to expose the `write_todos`
    tool output to users in real-time. It monitors the state for changes to the
    `todos` field and sends formatted status updates.

    Features:
    - Formats todo list for display (with progress indicators)
    - Sends updates via channel's send_status() method
    - Updates in real-time as todos change
    - Rate-limits to avoid spam
    - Works with Telegram, HTTP, and other channels

    Args:
        channel: The channel instance to send todo list updates through.
        max_display_todos: Maximum number of todos to display (default: 10).
        update_interval: Minimum seconds between todo list updates (default: 0.5).
        show_progress_bar: Whether to show progress bar (default: False).
    """

    def __init__(
        self,
        channel: "BaseChannel",
        max_display_todos: int = 10,
        update_interval: float = 0.5,
        show_progress_bar: bool = False,
    ) -> None:
        super().__init__()
        self.channel = channel
        self.max_display_todos = max_display_todos
        self.update_interval = update_interval
        self.show_progress_bar = show_progress_bar

        # State tracking
        self.last_todos: list[dict] = []
        self.last_update_time: float = 0
        self.current_conversation_id: str | None = None

    def _get_conversation_id(self) -> str | None:
        """Get current conversation ID from thread_id context."""
        try:
            thread_id = get_thread_id()
            if thread_id and ":" in thread_id:
                return thread_id.split(":")[-1]
            return thread_id
        except Exception:
            return None

    def _log_debug(self, event: str, **fields: Any) -> None:
        """Log structured debug info for middleware events."""
        payload = {
            "type": "middleware",
            "name": "TodoDisplayMiddleware",
            "event": event,
            "thread_id": get_thread_id(),
            "conversation_id": self.current_conversation_id,
            **fields,
        }
        logger.debug(json.dumps(payload, separators=(",", ":")))

    def _should_send_update(self) -> bool:
        """Check if enough time has passed since last update."""
        return time.time() - self.last_update_time >= self.update_interval

    def _todos_changed(self, current_todos: list[dict] | None) -> bool:
        """Check if todos have changed since last display."""
        if not current_todos:
            return self.last_todos != []

        # Compare lengths and statuses
        if len(current_todos) != len(self.last_todos):
            return True

        for current, last in zip(current_todos, self.last_todos):
            if current.get("status") != last.get("status"):
                return True
            if current.get("content") != last.get("content"):
                return True

        return False

    def _format_todo_list(self, todos: list[dict]) -> str:
        """
        Format todo list for status display.

        Args:
            todos: List of todo items with content and status fields.

        Returns:
            Formatted string suitable for status updates.
        """
        if not todos:
            return ""

        if self.show_progress_bar:
            return self._format_with_progress_bar(todos)

        # Count statuses
        completed = sum(1 for t in todos if t.get("status") == "completed")
        in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
        total = len(todos)

        lines = [f"📋 Tasks ({completed}/{total} complete):"]

        for i, todo in enumerate(todos[: self.max_display_todos]):
            status = todo.get("status", "pending")
            content = todo.get("content", "")

            if status == "completed":
                lines.append(f"  ✅ {content}")
            elif status == "in_progress":
                lines.append(f"  ⏳ {content}")
            else:  # pending
                lines.append(f"  ⏳ {content}")

        if len(todos) > self.max_display_todos:
            remaining = len(todos) - self.max_display_todos
            lines.append(f"  ... and {remaining} more")

        return "\n".join(lines)

    def _format_with_progress_bar(self, todos: list[dict]) -> str:
        """Format todo list with visual progress bar."""
        completed = sum(1 for t in todos if t.get("status") == "completed")
        total = len(todos)
        pct = (completed / total * 100) if total > 0 else 0

        # Build progress bar
        filled = int(pct / 10)  # 10 segments
        bar = "█" * filled + "░" * (10 - filled)

        lines = [
            f"📋 Progress: [{bar}] {pct:.0f}%",
        ]

        # Show current tasks
        in_progress_tasks = [t for t in todos if t.get("status") == "in_progress"]
        if in_progress_tasks:
            lines.append(f"\n⏳ Working on:")
            for task in in_progress_tasks[:3]:  # Max 3 current tasks
                lines.append(f"  • {task.get('content', '')}")

        # Show next pending tasks
        pending_tasks = [t for t in todos if t.get("status") == "pending"]
        if pending_tasks:
            lines.append(f"\n⏭ Up next:")
            for task in pending_tasks[:3]:  # Max 3 upcoming tasks
                lines.append(f"  • {task.get('content', '')}")

        return "\n".join(lines)

    async def _send_todo_list(self, todos: list[dict] | None) -> None:
        """
        Send formatted todo list to user via status update.

        Args:
            todos: Current todo list from state, or None if no todos.
        """
        if not settings.MW_TODO_LIST_ENABLED:
            logger.debug("Todo list display disabled")
            return

        if not todos:
            return

        if not self._should_send_update():
            logger.debug("Skipping todo list update (rate limited)")
            return

        if not self._todos_changed(todos):
            logger.debug("Skipping todo list update (no change)")
            return

        message = self._format_todo_list(todos)

        conv_id = self.current_conversation_id or self._get_conversation_id()
        if not conv_id:
            logger.warning("No conversation_id for todo list update")
            return

        try:
            self._log_debug("send_todo", todo_count=len(todos))

            # Prefer dedicated todo messages if supported.
            if hasattr(self.channel, "send_todo"):
                await self.channel.send_todo(
                    conversation_id=conv_id,
                    message=message,
                    update=True,
                )
                self.last_update_time = time.time()
                self._log_debug("todo_sent", todo_count=len(todos))
            elif hasattr(self.channel, "send_status"):
                await self.channel.send_status(
                    conversation_id=conv_id,
                    message=message,
                    update=True,
                )
                self.last_update_time = time.time()
                self._log_debug("todo_sent", todo_count=len(todos))
            else:
                logger.warning(
                    f"Channel {type(self.channel).__name__} doesn't support todo updates, "
                    "todo list will not be displayed"
                )

        except Exception as e:
            # Don't let todo list display break the agent
            logger.error(f"Failed to send todo list update to {conv_id}: {e}")

        # Update cached todos
        self.last_todos = todos.copy() if todos else []

    async def abefore_agent(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """Called when agent starts processing."""
        self.last_todos = []
        self.last_update_time = 0

        try:
            thread_id = get_thread_id()
            self.current_conversation_id = (
                thread_id.split(":")[-1] if ":" in thread_id else thread_id
            )
            self._log_debug("start")
        except ValueError:
            logger.warning("TodoDisplayMiddleware: No thread_id in context")
            self.current_conversation_id = None

        # Clear any persisted todos so each run starts fresh.
        if "todos" in state and state["todos"]:
            return {"todos": []}

        return None

    async def aafter_model(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """
        Called after model processes and potentially calls write_todos.

        Check for new or updated todos and send status update.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        # Find the last AI message
        last_ai_msg = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break

        if not last_ai_msg:
            return None

        # Check if write_todos was called
        write_todos_calls = [
            tc for tc in (last_ai_msg.tool_calls or [])
            if tc.get("name") == "write_todos"
        ]

        if write_todos_calls:
            # Extract todos from tool call arguments (don't wait for state update)
            # This is critical because the Command(update={"todos": ...}) hasn't
            # been applied to state yet when this hook runs
            todos = write_todos_calls[0].get("args", {}).get("todos", [])
            self._log_debug("write_todos", todo_count=len(todos) if isinstance(todos, list) else None)
            if todos:
                await self._send_todo_list(todos)
        return None

    async def aafter_agent(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """Called when agent completes."""
        self._log_debug("end")
        return None


def create_todo_display_middleware(
    channel: "BaseChannel",
) -> TodoDisplayMiddleware | None:
    """
    Factory function to create TodoDisplayMiddleware if enabled.

    Args:
        channel: The channel instance to send todo list updates through.

    Returns:
        TodoDisplayMiddleware instance if enabled, None otherwise.
    """
    if not settings.MW_TODO_LIST_ENABLED:
        return None

    return TodoDisplayMiddleware(
        channel=channel,
        max_display_todos=settings.MW_TODO_LIST_MAX_DISPLAY,
        update_interval=settings.MW_TODO_LIST_UPDATE_INTERVAL,
        show_progress_bar=settings.MW_TODO_LIST_SHOW_PROGRESS_BAR,
    )
