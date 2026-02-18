"""Todo Display Middleware for enhanced todo list presentation.

This middleware reads the todo list from state and provides a formatted
display with progress tracking, status icons, and completion indicators.

It does NOT modify todos - that's handled by the built-in TodoListMiddleware.
This middleware is for PRESENTATION only.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState

if TYPE_CHECKING:
    from langgraph.types import Runtime

logger = logging.getLogger(__name__)


class TodoDisplayMiddleware(AgentMiddleware):
    """Middleware that enhances todo list display with progress tracking.

    This middleware:
    1. Tracks which tool calls are being made
    2. Attempts to correlate tool calls with todos
    3. Updates todo display with progress indicators

    Key features:
    - Does NOT modify the actual todos (TodoListMiddleware handles that)
    - Only enhances how todos are displayed
    - Adds progress tracking based on tool execution

    The middleware tracks tool calls and heuristically updates todo statuses
    for display purposes only.
    """

    def __init__(
        self,
        *,
        enable_progress_tracking: bool = True,
        auto_mark_complete: bool = False,
    ) -> None:
        """Initialize the todo display middleware.

        Args:
            enable_progress_tracking: Whether to track tool calls and update
                todo progress automatically. Defaults to True.
            auto_mark_complete: Whether to automatically mark todos as complete
                when their associated tools are called. Defaults to False (conservative).
        """
        super().__init__()
        self.enable_progress_tracking = enable_progress_tracking
        self.auto_mark_complete = auto_mark_complete
        logger.info(
            f"[TodoDisplay] Initialized: progress_tracking={enable_progress_tracking}, "
            f"auto_mark_complete={auto_mark_complete}"
        )

    def before_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Run before agent execution.

        Initialize tracking for this message.
        Clears stale completed todos - keeps pending/in_progress for continuity.
        """
        logger.debug("[TodoDisplay] before_agent called")

        todos = state.get("todos", [])
        if not todos:
            return None

        # Check if all todos are completed
        all_completed = all(
            todo.get("status") == "completed"
            for todo in todos
            if isinstance(todo, dict) and "status" in todo
        )

        # If all todos are completed, clear them for fresh start
        # Keep pending/in_progress todos so agent can continue
        if all_completed and todos:
            logger.info(f"[TodoDisplay] Clearing {len(todos)} completed todos for fresh start")
            return {"todos": []}

        # Log pending todos for continuity
        pending_count = sum(
            1
            for t in todos
            if isinstance(t, dict) and t.get("status") in ("pending", "in_progress")
        )
        if pending_count > 0:
            logger.info(f"[TodoDisplay] Continuing with {pending_count} pending todos")

        return None

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Run after agent execution.

        Update todo display with progress information.

        This method:
        1. Checks if there are todos in the state
        2. Looks at tool calls that were made
        3. Heuristically correlates tools with todos
        4. Updates todo statuses for display purposes

        Args:
            state: The agent state (may contain todos, messages, etc.)
            runtime: The runtime context

        Returns:
            State update with enhanced todo display, or None if no todos present.
        """
        logger.debug("[TodoDisplay] after_agent called")

        todos = state.get("todos", [])
        if not todos:
            logger.debug("[TodoDisplay] No todos in state")
            return None

        messages = state.get("messages", [])
        if not messages:
            logger.debug("[TodoDisplay] No messages in state")
            return None

        # Extract tool calls from messages
        tool_calls = self._extract_tool_calls(messages)
        if not tool_calls:
            logger.debug("[TodoDisplay] No tool calls found")
            return None

        logger.info(
            f"[TodoDisplay] Processing {len(todos)} todos with {len(tool_calls)} tool calls"
        )

        # Enhance todos with display metadata
        enhanced_todos = self._enhance_todo_display(todos, tool_calls)

        # Return enhanced todos (but don't modify original todos)
        # Store them in a separate field for display purposes
        return {"todos_display": enhanced_todos}

    def _extract_tool_calls(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Extract all tool calls from message history.

        Args:
            messages: List of messages from the state

        Returns:
            List of tool call dictionaries with name and args
        """
        tool_calls = []

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(
                        {
                            "name": tc.get("name", "unknown"),
                            "args": tc.get("args", {}),
                            "id": tc.get("id", ""),
                        }
                    )

        return tool_calls

    def _enhance_todo_display(
        self,
        todos: list[Any],
        tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Enhance todos with progress tracking for display.

        This uses heuristics to correlate tool calls with todos:
        1. Look for keyword matches between todo content and tool names/args
        2. Check if todos mention specific tool names
        3. Track completion based on tool execution

        Args:
            todos: List of todo items (strings or dicts)
            tool_calls: List of tool calls made during execution

        Returns:
            Enhanced list with display metadata added
        """
        enhanced = []

        for i, todo in enumerate(todos):
            # Handle both string and dict todos
            if isinstance(todo, dict):
                content = todo.get("content", "")
                original_status = todo.get("status", "pending")
            else:
                content = str(todo)
                original_status = "pending"

            # Determine display status
            display_status = self._calculate_display_status(
                content,
                original_status,
                tool_calls,
                todo_index=i,
                total_todos=len(todos),
            )

            enhanced.append(
                {
                    "content": content,
                    "status": original_status,  # Keep original status
                    "display_status": display_status,  # Add display-specific status
                    "index": i + 1,
                }
            )

        return enhanced

    def _calculate_display_status(
        self,
        todo_content: str,
        original_status: str,
        tool_calls: list[dict[str, Any]],
        todo_index: int,
        total_todos: int,
    ) -> str:
        """Calculate the display status for a todo item.

        Uses conservative heuristics to determine if a todo is in progress or complete:

        1. If original status is "completed" → return "completed"
        2. If explicitly marked "in_progress" → return "in_progress"
        3. If this is the FIRST pending todo AND tools were called → "in_progress"
        4. If todo content mentions specific tools that were called → "in_progress"
        5. Default → use original_status (don't assume)

        Args:
            todo_content: The todo content text
            original_status: The original status from TodoListMiddleware
            tool_calls: List of tool calls made
            todo_index: Index of this todo in the list
            total_todos: Total number of todos

        Returns:
            Display status: "pending", "in_progress", or "completed"
        """
        # If already marked complete, keep it
        if original_status == "completed":
            return "completed"

        # If explicitly marked in_progress, keep it
        if original_status == "in_progress":
            return "in_progress"

        # Heuristic: Only mark FIRST pending todo as in_progress (not all of them)
        # This prevents the agent from thinking all todos are active
        if tool_calls and original_status == "pending" and todo_index == 0:
            return "in_progress"

        # Heuristic: if todo mentions specific tools that were called
        todo_lower = todo_content.lower()
        for tool in tool_calls:
            tool_name = tool.get("name", "").lower()
            if tool_name in todo_lower or tool_name.replace("_", "") in todo_lower:
                return "in_progress"

        # Default: use original status (conservative - don't assume)
        # Don't mark pending todos as in_progress just because other tools were called
        return original_status


def create_todo_display_middleware(
    enable_progress_tracking: bool = True,
    auto_mark_complete: bool = False,
) -> TodoDisplayMiddleware:
    """Factory function to create TodoDisplayMiddleware.

    This is a convenience function for use with the middleware factory.

    Args:
        enable_progress_tracking: Whether to enable progress tracking
        auto_mark_complete: Whether to auto-mark todos as complete

    Returns:
        Configured TodoDisplayMiddleware instance
    """
    return TodoDisplayMiddleware(
        enable_progress_tracking=enable_progress_tracking,
        auto_mark_complete=auto_mark_complete,
    )
