"""Telegram-specific message formatters.

This module contains all Telegram-specific formatting logic for displaying:
- Tool calls
- Todo list updates
- Status messages
- Agent responses
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Message

    from src.agent.types import ToolCallInfo


class MessageFormatter:
    """Format messages for Telegram display."""

    @staticmethod
    def format_processing_status(
        tool_calls: list[dict],
        todos: list[str] | None = None,
        middleware_activities: list[dict] | None = None,
    ) -> str:
        """Format processing status message.

        Args:
            tool_calls: List of tool call dictionaries with 'name' and optional 'args'
            todos: Optional list of todo items
            middleware_activities: Optional list of middleware activity dicts

        Returns:
            Formatted status message (empty string if no progress yet)
        """
        # If no progress yet, return empty string (just show typing indicator)
        if not tool_calls and not todos and not middleware_activities:
            return ""

        status = ""

        # Show middleware activities first
        if middleware_activities:
            for activity in middleware_activities:
                status += f"{MessageFormatter._format_middleware_activity(activity)}\n"
            status += "\n"

        # Show todos if available
        if todos:
            status += "📋 **Plan:**\n"
            for i, todo in enumerate(todos[:5], 1):  # Show max 5 todos
                # Handle enhanced todos from TodoDisplayMiddleware (with display_status)
                if isinstance(todo, dict) and "display_status" in todo:
                    # Enhanced todo with display_status from TodoDisplayMiddleware
                    content = todo.get("content", str(todo))
                    display_status = todo.get("display_status", "pending")
                    status_emoji = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                    }.get(display_status, "⏳")
                    status += f"{i}. {status_emoji} {content}\n"
                # Handle regular dict todos
                elif isinstance(todo, dict):
                    content = todo.get("content", str(todo))
                    status_emoji = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                    }.get(todo.get("status", "pending"), "⏳")
                    status += f"{i}. {status_emoji} {content}\n"
                # Handle string todos
                else:
                    status += f"{i}. {todo}\n"
            if len(todos) > 5:
                status += f"... and {len(todos) - 5} more\n"

        # Show tool calls (just names, with special formatting for subagents)
        if tool_calls:
            if status and not middleware_activities:
                status += "\n"
            for i, tc in enumerate(tool_calls, 1):
                # Use display_name if available (for subagents), otherwise use name
                display = tc.get("display_name", tc["name"])

                # Check if tool is completed (has result)
                is_completed = tc.get("completed", False)

                if is_completed:
                    # Completed tool - show with checkmark
                    duration = tc.get("duration_ms", 0)
                    status += f"✅ {i}. {display}"
                    if duration:
                        status += f" ({duration:.0f}ms)"
                    status += "\n"

                    # Show result preview if available
                    if tc.get("result_preview"):
                        result = tc["result_preview"]
                        # Truncate result preview further
                        if len(result) > 80:
                            result = result[:80] + "..."
                        status += f"   └─ {result}\n"
                else:
                    # In-progress tool - show with wrench
                    status += f"🔧 {i}. {display}\n"

                    # Show args if available (human-friendly format)
                    args = tc.get("args", {})
                    if args:
                        # Format args in a human-friendly way
                        args_str = MessageFormatter._format_tool_args(args)
                        if args_str:
                            status += f"   └─ {args_str}\n"

        return status

    @staticmethod
    def _format_tool_args(args: dict) -> str:
        """Format tool arguments in a human-friendly way."""
        if not args:
            return ""

        # Filter out internal/empty args
        filtered = {
            k: v for k, v in args.items() if v not in (None, "", [], {}) and not k.startswith("_")
        }

        if not filtered:
            return ""

        # Format as key=value pairs, truncate long values
        parts = []
        for k, v in filtered.items():
            v_str = str(v)
            # Truncate long values
            if len(v_str) > 30:
                v_str = v_str[:30] + "..."
            parts.append(f"{k}={v_str}")

        return ", ".join(parts)

    @staticmethod
    def _format_middleware_activity(activity: dict) -> str:
        """Format a single middleware activity.

        Args:
            activity: Middleware activity dict with 'name', 'status', 'message'

        Returns:
            Formatted middleware activity string
        """
        name = activity.get("name", "Unknown")
        status = activity.get("status", "active")
        message = activity.get("message", "")

        if status == "active":
            emoji = "⚙️"
        elif status == "completed":
            emoji = "✅"
        elif status == "skipped":
            emoji = "⏭️"
        elif status == "failed":
            emoji = "❌"
        else:
            emoji = "⚙️"

        result = f"{emoji} {name}"
        if message:
            result += f" - {message}"
        return result

    @staticmethod
    def format_tool_call(tool_name: str, tool_args: dict, tool_id: str = "") -> str:
        """Format a single tool call for display."""
        # Format args in human-friendly way
        args_str = MessageFormatter._format_tool_args(tool_args)

        if args_str:
            return f"🔧 **{tool_name}**\n   └─ {args_str}"
        else:
            return f"🔧 **{tool_name}**"

    @staticmethod
    def format_tool_result(tool_name: str, result_preview: str, duration_ms: float = 0) -> str:
        """Format a tool result for display."""
        duration_str = f" ({duration_ms:.0f}ms)" if duration_ms else ""
        result_text = result_preview[:80] + "..." if len(result_preview) > 80 else result_preview

        return f"✅ **{tool_name}**{duration_str}\n   └─ {result_text}"

    @staticmethod
    def format_final_response(
        tool_calls: list[dict],
        content: str,
        todos: list[str] | None = None,
        middleware_activities: list[dict] | None = None,
        reasoning: str | None = None,
    ) -> str:
        """Format final response (just the content, no tool/middleware summary).

        The status message stays separate. This only returns the agent's response.

        Args:
            tool_calls: List of tool call dictionaries (not used in final response)
            content: The agent's response content
            todos: Optional list of todo items (not used in final response)
            middleware_activities: Optional list of middleware activities (not used in final response)
            reasoning: Optional LLM reasoning/thinking process to display

        Returns:
            Formatted final message (just the content, with reasoning if available)
        """
        # Build response with optional reasoning section
        response_parts = []

        # Add reasoning if available (before the main response)
        if reasoning and reasoning.strip():
            response_parts.append(f"💭 **Thinking Process:**\n{reasoning}\n")

        # Add agent response (truncate if too long for Telegram)
        # Telegram message limit is 4096 characters
        MAX_LENGTH = 4000  # Leave some buffer

        # Account for reasoning in length calculation
        reasoning_length = len(response_parts[0]) if response_parts else 0
        remaining_length = MAX_LENGTH - reasoning_length - 50  # Leave buffer for truncation message

        if len(content) > remaining_length:
            content = content[:remaining_length] + "\n\n... (truncated, too long)"

        response_parts.append(content)

        return "\n".join(response_parts)

    @staticmethod
    def format_done_message() -> str:
        """Format done message when no text response is available.

        Returns:
            Formatted done message
        """
        return "✅ Done (no text response)"


class MessageUpdater:
    """Handle message updates for Telegram bot."""

    def __init__(self, message: Message) -> None:
        """Initialize with a Telegram message object.

        Args:
            message: The Telegram message to update
        """
        self.message = message
        self.formatter = MessageFormatter()

    async def update_processing_status(
        self,
        tool_calls: list[dict],
        todos: list[str] | None = None,
        middleware_activities: list[dict] | None = None,
    ) -> bool:
        """Update the status message with current tool calls, todos, and middleware activities.

        Args:
            tool_calls: List of tool calls made so far
            todos: Optional list of todo items
            middleware_activities: Optional list of middleware activity dicts

        Returns:
            True if update succeeded, False otherwise
        """
        status_text = self.formatter.format_processing_status(
            tool_calls, todos, middleware_activities
        )
        try:
            await self.message.edit_text(status_text)
            return True
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Could not edit message: {e}")
            return False

    async def update_final_response(
        self,
        tool_calls: list[dict],
        content: str,
        todos: list[str] | None = None,
        middleware_activities: list[dict] | None = None,
        reasoning: str | None = None,
    ) -> bool:
        """Update the message with final response.

        Args:
            tool_calls: List of tool calls made during execution
            content: The agent's final response content
            todos: Optional list of todo items
            middleware_activities: Optional list of middleware activity dicts
            reasoning: Optional LLM reasoning/thinking process

        Returns:
            True if update succeeded, False otherwise
        """
        response_text = self.formatter.format_final_response(
            tool_calls, content, todos, middleware_activities, reasoning
        )
        try:
            await self.message.edit_text(response_text)
            return True
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Could not edit final message: {e}")
            return False

    async def update_done_message(self) -> bool:
        """Update the message with done status.

        Returns:
            True if update succeeded, False otherwise
        """
        done_text = self.formatter.format_done_message()
        try:
            await self.message.edit_text(done_text)
            return True
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Could not edit done message: {e}")
            return False
