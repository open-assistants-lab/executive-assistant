"""Status update middleware for real-time progress feedback.

Sends status updates to the user during agent execution:
- Agent start: "Thinking..."
- Tool calls: "Tool 1: search_web..."
- Completion: "Done in 45.2s"

Uses wrap_tool_call hook for per-tool tracking.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from langchain.tools.tool_node import ToolCallRequest
from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage
from langgraph.types import Command

from cassey.config import settings
from cassey.storage.file_sandbox import get_thread_id

if TYPE_CHECKING:
    from cassey.channels.base import BaseChannel

logger = logging.getLogger(__name__)

# Thread-local storage for LLM timing (keyed by thread_id)
_llm_timing_by_thread: dict[str, dict] = {}


def record_llm_call(elapsed: float, tokens: dict | None = None) -> None:
    """
    Record an LLM call for status reporting in verbose mode.

    Args:
        elapsed: Time taken for the LLM call in seconds.
        tokens: Optional dict with token counts (in, out, total).
    """
    thread_id = get_thread_id()
    if not thread_id:
        return

    if thread_id not in _llm_timing_by_thread:
        _llm_timing_by_thread[thread_id] = {"count": 0, "total_time": 0, "calls": []}

    current = _llm_timing_by_thread[thread_id]
    current["count"] += 1
    current["total_time"] += elapsed
    current["calls"].append({"elapsed": elapsed, "tokens": tokens})


class StatusUpdateMiddleware(AgentMiddleware):
    """
    Middleware that sends real-time status updates to users during agent execution.

    Provides visibility into:
    - Agent starting ("Thinking...")
    - Each tool call ("Tool 1: search_web...")
    - Agent completion ("Done in 45.2s")
    - Errors ("Tool X failed: reason")

    Args:
        channel: The channel instance to send status updates through.
        show_tool_args: Whether to include tool arguments in status (default: False for security).
        update_interval: Minimum seconds between status updates (default: 0.5 to avoid spam).
    """

    def __init__(
        self,
        channel: "BaseChannel",
        show_tool_args: bool = False,
        update_interval: float = 0.5,
    ) -> None:
        super().__init__()
        self.channel = channel
        self.show_tool_args = show_tool_args
        self.update_interval = update_interval

        # State tracking
        self.tool_count: int = 0
        self.start_time: float | None = None
        self.last_status_time: float | None = None
        self.current_conversation_id: str | None = None

    def _should_send_status(self) -> bool:
        """Check if enough time has passed since last status update."""
        if self.last_status_time is None:
            return True
        return time.time() - self.last_status_time >= self.update_interval

    async def _send_status(self, message: str, conversation_id: str | None = None) -> None:
        """Send a status update to the user."""
        if not settings.MW_STATUS_UPDATE_ENABLED:
            logger.debug("Status update disabled")
            return

        conv_id = conversation_id or self.current_conversation_id
        if not conv_id:
            logger.warning(f"No conversation_id for status update: {message}")
            return

        try:
            logger.info(f"Sending status to {conv_id}: {message}")
            await self.channel.send_status(
                conversation_id=conv_id,
                message=message,
                update=True,  # Edit previous message if available
            )
            self.last_status_time = time.time()
            logger.info(f"Status sent to {conv_id}")
        except Exception as e:
            # Don't let status updates break the agent
            logger.error(f"Failed to send status update to {conv_id}: {e}")

    async def abefore_agent(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """Called when agent starts processing."""
        self.tool_count = 0
        self.start_time = time.time()
        self.last_status_time = None

        # Get thread_id from ContextVar (set by the channel before invoking agent)
        try:
            thread_id = get_thread_id()
            # Extract conversation_id from thread_id (e.g., "TelegramChannel:123" -> "123")
            self.current_conversation_id = thread_id.split(":")[-1] if ":" in thread_id else thread_id
            logger.info(f"StatusMiddleware: thread_id={thread_id}, conversation_id={self.current_conversation_id}")
        except ValueError:
            logger.warning("StatusMiddleware: No thread_id in context")
            self.current_conversation_id = None

        await self._send_status("🤔 Thinking...")
        return None

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """
        Wrap each tool call to send status updates.

        Sends status before and after each tool execution.
        """
        self.tool_count += 1
        tool_name = request.tool_call.get("name", "unknown")
        tool_args = request.tool_call.get("args", {})

        # Build status message
        if self.show_tool_args and tool_args:
            # Sanitize args for display (truncate, hide sensitive values)
            args_preview = self._sanitize_args(tool_args)
            status_msg = f"⚙️ Tool {self.tool_count}: {tool_name} {args_preview}"
        else:
            status_msg = f"⚙️ Tool {self.tool_count}: {tool_name}"

        await self._send_status(status_msg)

        # Execute the tool
        tool_start = time.time()
        try:
            result = await handler(request)
            elapsed = time.time() - tool_start

            # Send completion status
            await self._send_status(f"✅ {tool_name} ({elapsed:.1f}s)")
            return result

        except Exception as e:
            elapsed = time.time() - tool_start
            error_msg = str(e)[:100]  # Truncate long errors
            await self._send_status(f"❌ {tool_name} failed ({elapsed:.1f}s): {error_msg}")
            raise

    async def aafter_agent(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """Called when agent completes."""
        if self.start_time is None:
            return None

        elapsed = time.time() - self.start_time

        # Get LLM timing info if any was recorded
        thread_id = get_thread_id()
        llm_summary = ""
        if thread_id and thread_id in _llm_timing_by_thread:
            llm_info = _llm_timing_by_thread[thread_id]
            if llm_info["count"] > 0:
                count = llm_info["count"]
                llm_time = llm_info["total_time"]
                llm_summary = f" | LLM: {count} call ({llm_time:.1f}s)"
            # Clear timing for next run
            del _llm_timing_by_thread[thread_id]

        if elapsed < 1:
            await self._send_status(f"✅ Done{llm_summary}")
        else:
            await self._send_status(f"✅ Done in {elapsed:.1f}s{llm_summary}")

        return None

    def _sanitize_args(self, args: dict) -> str:
        """
        Sanitize tool arguments for safe display.

        - Truncates long values
        - Hides sensitive keys (api_key, password, token)
        - Limits total length
        """
        sensitive_keys = {"api_key", "password", "token", "secret", "key"}
        safe_args = {}

        for key, value in args.items():
            if key.lower() in sensitive_keys:
                safe_args[key] = "***"
            elif isinstance(value, str) and len(value) > 50:
                safe_args[key] = value[:50] + "..."
            elif isinstance(value, (list, dict)) and len(str(value)) > 100:
                safe_args[key] = str(value)[:100] + "..."
            else:
                safe_args[key] = value

        args_str = str(safe_args)
        if len(args_str) > 100:
            args_str = args_str[:100] + "..."

        return args_str


def create_status_middleware(channel: "BaseChannel") -> StatusUpdateMiddleware | None:
    """
    Factory function to create StatusUpdateMiddleware if enabled.

    Args:
        channel: The channel instance to send status updates through.

    Returns:
        StatusUpdateMiddleware instance if enabled, None otherwise.
    """
    if not settings.MW_STATUS_UPDATE_ENABLED:
        return None

    return StatusUpdateMiddleware(
        channel=channel,
        show_tool_args=settings.MW_STATUS_SHOW_TOOL_ARGS,
        update_interval=settings.MW_STATUS_UPDATE_INTERVAL,
    )
