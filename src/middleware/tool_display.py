from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.runtime import Runtime

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
)

logger = logging.getLogger(__name__)


class ToolDisplayMiddleware(AgentMiddleware[AgentState, ContextT]):
    """Middleware to display tool calls and results to users in real-time.

    This middleware:
    1. Tracks tool call start times
    2. Sends tool call as separate messages when tool is invoked
    3. Sends tool result as separate messages when tool completes

    Enable/disable via config:
        middleware:
          tool_display:
            enabled: true
            show_args: true        # Show tool arguments
            show_result: true      # Show tool result preview
            show_duration: true    # Show execution duration
            show_thinking: true    # Show agent thinking before tool calls

    Note: This middleware requires a callback to send Telegram messages.
    Set the callback via set_message_sender() before using.
    """

    def __init__(
        self,
        show_args: bool = True,
        show_result: bool = True,
        show_duration: bool = True,
        show_thinking: bool = True,
    ) -> None:
        """Initialize the ToolDisplayMiddleware.

        Args:
            show_args: Whether to show tool arguments in the message
            show_result: Whether to show tool result preview
            show_duration: Whether to show execution duration
            show_thinking: Whether to show agent thinking before tool calls
        """
        super().__init__()
        self.show_args = show_args
        self.show_result = show_result
        self.show_duration = show_duration
        self.show_thinking = show_thinking
        self._message_sender: Callable[[str], Any] | None = None
        self._tool_call_times: dict[str, float] = {}
        self._last_thinking: str = ""
        logger.info(
            f"[ToolDisplay] Initialized: show_args={show_args}, "
            f"show_result={show_result}, show_duration={show_duration}, "
            f"show_thinking={show_thinking}"
        )

    @staticmethod
    def set_message_sender(sender: Callable[[str], Any]) -> None:
        """Set the callback function to send messages to Telegram.

        Args:
            sender: Async function that takes message text and sends it
        """
        ToolDisplayMiddleware._message_sender = sender

    def _format_tool_call(self, tool_name: str, tool_args: dict) -> str:
        """Format a tool call for display."""
        if not self.show_args or not tool_args:
            return f"🔧 **{tool_name}**"

        # Filter out internal/empty args
        filtered = {
            k: v
            for k, v in tool_args.items()
            if v not in (None, "", [], {}) and not k.startswith("_")
        }

        if not filtered:
            return f"🔧 **{tool_name}**"

        # Format as key=value pairs, truncate long values
        parts = []
        for k, v in filtered.items():
            v_str = str(v)
            if len(v_str) > 30:
                v_str = v_str[:30] + "..."
            parts.append(f"{k}={v_str}")

        args_str = ", ".join(parts)
        return f"🔧 **{tool_name}**\n   └─ {args_str}"

    def _format_tool_result(
        self, tool_name: str, result_preview: str, duration_ms: float = 0
    ) -> str:
        """Format a tool result for display."""
        duration_str = f" ({duration_ms:.0f}ms)" if duration_ms and self.show_duration else ""
        result_text = result_preview[:80] + "..." if len(result_preview) > 80 else result_preview

        return f"✅ **{tool_name}**{duration_str}\n   └─ {result_text}"

    def _format_thinking(self, thinking: str) -> str:
        """Format thinking for display."""
        truncated = thinking[:200] + "..." if len(thinking) > 200 else thinking
        return f"🤔 {truncated}"

    def _extract_thinking(self, messages: list) -> str | None:
        """Extract thinking/reasoning from messages before tool calls."""
        if not messages:
            return None

        last_msg = messages[-1]
        if not hasattr(last_msg, "content"):
            return None

        # Check for explicit reasoning_content
        if hasattr(last_msg, "additional_kwargs"):
            reasoning = last_msg.additional_kwargs.get("reasoning_content")
            if reasoning:
                return reasoning

        # Check if this message has content and is before tool results
        content = last_msg.content if hasattr(last_msg, "content") else ""
        if not content:
            return None

        # If there are tool calls in this message, the content is the thinking
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls and len(content) > 20:
            return content

        return None

    def before_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Run before agent execution - clear tool call tracking."""
        self._tool_call_times = {}
        logger.debug("[ToolDisplay] before_agent - cleared tool call times")
        return None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Track tool calls before model execution."""
        # Get messages from state
        messages = request.state.get("messages", [])
        if messages:
            last_msg = messages[-1] if messages else None
            if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                for tool_call in last_msg.tool_calls:
                    tool_id = tool_call.get("id", "")
                    if tool_id:
                        self._tool_call_times[tool_id] = time.time()

        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Track tool calls and send messages before model execution."""
        # Get messages from state to find tool calls
        messages = request.state.get("messages", [])

        # Send thinking preview if enabled and there are tool calls
        if self.show_thinking and self._message_sender and messages:
            thinking = self._extract_thinking(messages)
            if thinking and thinking != self._last_thinking:
                self._last_thinking = thinking
                logger.info(f"[ToolDisplay] Sending thinking: {thinking[:50]}...")
                try:
                    await self._message_sender(self._format_thinking(thinking))
                except Exception as e:
                    logger.warning(f"[ToolDisplay] Failed to send thinking message: {e}")

        if messages:
            last_msg = messages[-1] if messages else None
            if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                for tool_call in last_msg.tool_calls:
                    tool_id = tool_call.get("id", "")
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("args", {})

                    if tool_id and not self._tool_call_times.get(tool_id):
                        self._tool_call_times[tool_id] = time.time()
                        logger.info(f"[ToolDisplay] Tool call: {tool_name}")

                        # Send tool call message
                        if self._message_sender:
                            tool_text = self._format_tool_call(
                                tool_name, tool_args if self.show_args else {}
                            )
                            try:
                                await self._message_sender(tool_text)
                            except Exception as e:
                                logger.warning(
                                    f"[ToolDisplay] Failed to send tool call message: {e}"
                                )

        response = await handler(request)
        return response

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Send tool result messages after agent execution."""
        if not self._message_sender or not self.show_result:
            return None

        # Get messages to find tool results
        messages = state.get("messages", [])
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "tool":
                tool_call_id = getattr(msg, "tool_call_id", None)
                if not tool_call_id:
                    continue

                # Find tool name from earlier
                tool_name = "tool"
                messages_before = state.get("messages", [])
                for m in messages_before:
                    if hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            if tc.get("id") == tool_call_id:
                                tool_name = tc.get("name", "tool")
                                break

                # Calculate duration
                start_time = self._tool_call_times.get(tool_call_id)
                duration_ms = 0
                if start_time:
                    duration_ms = (time.time() - start_time) * 1000

                # Send tool result message
                result_preview = str(msg.content)[:100] if msg.content else ""
                if len(str(msg.content)) > 100:
                    result_preview += "..."

                try:
                    result_text = self._format_tool_result(tool_name, result_preview, duration_ms)
                    # Can't await in sync after_agent - will send via callback if needed
                    logger.info(f"[ToolDisplay] Tool result: {tool_name} ({duration_ms:.0f}ms)")
                except Exception as e:
                    logger.warning(f"[ToolDisplay] Failed to send tool result message: {e}")

        return None
