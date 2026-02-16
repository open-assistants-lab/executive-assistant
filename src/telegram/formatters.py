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
            for todo in todos[:5]:  # Show max 5 todos
                status += f"• {todo}\n"
            if len(todos) > 5:
                status += f"... and {len(todos) - 5} more\n"

        # Show tool calls (just names, with special formatting for subagents)
        if tool_calls:
            if status and not middleware_activities:
                status += "\n"
            for tc in tool_calls:
                # Use display_name if available (for subagents), otherwise use name
                display = tc.get("display_name", tc["name"])
                status += f"🔧 {display}\n"

        return status

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
    def format_final_response(
        tool_calls: list[dict],
        content: str,
        todos: list[str] | None = None,
        middleware_activities: list[dict] | None = None,
    ) -> str:
        """Format final response (just the content, no tool/middleware summary).

        The status message stays separate. This only returns the agent's response.

        Args:
            tool_calls: List of tool call dictionaries (not used in final response)
            content: The agent's response content
            todos: Optional list of todo items (not used in final response)
            middleware_activities: Optional list of middleware activities (not used in final response)

        Returns:
            Formatted final message (just the content)
        """
        # Add agent response (truncate if too long for Telegram)
        # Telegram message limit is 4096 characters
        MAX_LENGTH = 4000  # Leave some buffer
        if len(content) > MAX_LENGTH:
            content = content[:MAX_LENGTH - 50] + "\n\n... (truncated, too long)"

        return content

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
        status_text = self.formatter.format_processing_status(tool_calls, todos, middleware_activities)
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
    ) -> bool:
        """Update the message with final response.

        Args:
            tool_calls: List of tool calls made during execution
            content: The agent's final response content
            todos: Optional list of todo items
            middleware_activities: Optional list of middleware activity dicts

        Returns:
            True if update succeeded, False otherwise
        """
        response_text = self.formatter.format_final_response(
            tool_calls, content, todos, middleware_activities
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
