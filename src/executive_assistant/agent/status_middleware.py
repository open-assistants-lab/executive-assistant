"""Status update middleware for real-time progress feedback.

Sends status updates to the user during agent execution:
- Agent start: "Thinking..."
- Tool calls: "Tool 1: search_web..."
- Completion: "Done in 45.2s"
- Middleware actions: Summarization, context editing, retries

Uses wrap_tool_call hook for per-tool tracking.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from langchain.tools.tool_node import ToolCallRequest
from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage
from langgraph.types import Command

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.agent.middleware_debug import MiddlewareDebug, RetryTracker
from executive_assistant.logging import format_log_context, truncate_log_text
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id

if TYPE_CHECKING:
    from executive_assistant.channels.base import BaseChannel

logger = logging.getLogger(__name__)

# Thread-local storage for LLM timing (keyed by thread_id)
_llm_timing_by_thread: dict[str, dict] = {}

# Thread-local storage for middleware debug tracking
# NOTE: No lock needed - relies on:
# 1. GIL-protected dict operations in CPython
# 2. ContextVar isolation (different conversations = different thread_ids)
# 3. Sequential task execution per conversation in asyncio
_middleware_debug_by_thread: dict[str, MiddlewareDebug] = {}
_retry_tracker_by_thread: dict[str, RetryTracker] = {}


def get_middleware_debug() -> MiddlewareDebug:
    """Get or create MiddlewareDebug for current thread."""
    thread_id = get_thread_id()
    if not thread_id:
        return MiddlewareDebug()  # Return empty instance if no thread_id

    # setdefault() is atomic under GIL for CPython dict operations
    return _middleware_debug_by_thread.setdefault(thread_id, MiddlewareDebug())


def get_retry_tracker() -> RetryTracker:
    """Get or create RetryTracker for current thread."""
    thread_id = get_thread_id()
    if not thread_id:
        return RetryTracker()  # Return empty instance if no thread_id

    # setdefault() is atomic under GIL for CPython dict operations
    return _retry_tracker_by_thread.setdefault(thread_id, RetryTracker())


def clear_middleware_debug() -> None:
    """Clear middleware debug tracking for current thread."""
    thread_id = get_thread_id()
    if thread_id:
        # pop() is atomic under GIL for CPython dict operations
        _middleware_debug_by_thread.pop(thread_id, None)
        _retry_tracker_by_thread.pop(thread_id, None)


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

    # setdefault() and dict operations are atomic under GIL
    if thread_id not in _llm_timing_by_thread:
        _llm_timing_by_thread[thread_id] = {"count": 0, "total_time": 0, "calls": []}

    current = _llm_timing_by_thread[thread_id]
    current["count"] += 1
    current["total_time"] += elapsed
    current["calls"].append({"elapsed": elapsed, "tokens": tokens})

    # Also track in RetryTracker
    tracker = get_retry_tracker()
    tracker.record_llm_call()


class StatusUpdateMiddleware(AgentMiddleware):
    """
    Middleware that sends real-time status updates to users during agent execution.

    Provides visibility into:
    - Agent starting ("Thinking...")
    - Each tool call ("Tool 1: search_web...")
    - Agent completion ("Done in 45.2s")
    - Middleware actions (Summarization, Context Editing, Retries)
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
        expected_llm_calls: int = 1,
    ) -> None:
        super().__init__()
        self.channel = channel
        self.show_tool_args = show_tool_args
        self.update_interval = update_interval
        self.expected_llm_calls = expected_llm_calls

        # State tracking
        self.tool_count: int = 0
        self.start_time: float | None = None
        self.last_status_time: float | None = None
        self.current_conversation_id: str | None = None

        # Middleware debug tracking
        self.middleware_debug: MiddlewareDebug | None = None
        self.retry_tracker: RetryTracker | None = None

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
        thread_id = get_thread_id()
        channel = thread_id.split(":")[0] if thread_id and ":" in thread_id else None
        user_id = sanitize_thread_id_to_user_id(thread_id) if thread_id else None
        ctx = format_log_context("message", channel=channel, user=user_id, conversation=conv_id, type="status")
        if not conv_id:
            logger.warning(f"{ctx} send status skipped: no conversation_id")
            return

        try:
            logger.debug(f'{ctx} send status text="{truncate_log_text(message)}"')
            await self.channel.send_status(
                conversation_id=conv_id,
                message=message,
                update=True,  # Edit previous message if available
            )
            self.last_status_time = time.time()
            logger.debug(f"{ctx} sent status")
        except Exception as e:
            # Don't let status updates break the agent
            logger.error(f'{ctx} send status failed error="{e}"')
            self.last_status_time = time.time()

    def _log_debug(self, event: str, **fields: Any) -> None:
        """Log structured debug info for middleware events."""
        payload = {
            "type": "middleware",
            "name": "StatusUpdateMiddleware",
            "event": event,
            "thread_id": get_thread_id(),
            "conversation_id": self.current_conversation_id,
            **fields,
        }
        logger.debug(json.dumps(payload, separators=(",", ":")))

    async def abefore_agent(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """Called when agent starts processing."""
        self.tool_count = 0
        self.start_time = time.time()
        self.last_status_time = None

        # Prefer ContextVar thread_id; fall back to runtime config (tests/mocked)
        thread_id = get_thread_id()
        if not thread_id:
            thread_id = (
                runtime.get("config", {})
                .get("configurable", {})
                .get("thread_id")
            )

        if thread_id:
            # Extract conversation_id from thread_id (e.g., "TelegramChannel:123" -> "123")
            self.current_conversation_id = thread_id.split(":")[-1] if ":" in thread_id else thread_id
            self._log_debug("start")

            # Initialize middleware debug tracking for this run (only if ContextVar is set)
            if get_thread_id():
                self.middleware_debug = get_middleware_debug()
                self.retry_tracker = get_retry_tracker()
                self.retry_tracker.start_run(
                    expected_llm=self.expected_llm_calls,
                    expected_tools=0
                )
            else:
                self.middleware_debug = None
                self.retry_tracker = None
        else:
            logger.warning("StatusMiddleware: No thread_id in context")
            self.current_conversation_id = None
            self.middleware_debug = None
            self.retry_tracker = None

        await self._send_status("🤔 Thinking...")
        return None

    async def abefore_model(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """
        Capture state before model/middleware processing.

        This is where SummarizationMiddleware, ContextEditingMiddleware, etc. may run.
        """
        if self.middleware_debug:
            self.middleware_debug.capture_before_model(state)
        return None

    async def aafter_model(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """
        Detect and log middleware actions after model/middleware processing.

        Checks for:
        - Summarization (message count reduction)
        - Context editing (tool_uses reduction)
        """
        if not self.middleware_debug:
            return None

        self.middleware_debug.capture_after_model(state)

        # Check for summarization
        summary_result = self.middleware_debug.detect_summarization()
        if summary_result:
            self._log_debug(
                "summarization",
                messages_before=summary_result["messages_before"],
                messages_after=summary_result["messages_after"],
                tokens_before=summary_result["tokens_before"],
                tokens_after=summary_result["tokens_after"],
                reduction_pct=summary_result["reduction_pct"],
            )
            self._log_debug(
                "summarization_config",
                trigger=settings.MW_SUMMARIZATION_MAX_TOKENS,
                target=settings.MW_SUMMARIZATION_TARGET_TOKENS,
            )

        # Check for context editing
        context_result = self.middleware_debug.detect_context_editing()
        if context_result:
            self._log_debug(
                "context_editing",
                tool_uses_before=context_result["tool_uses_before"],
                tool_uses_after=context_result["tool_uses_after"],
                reduction_pct=context_result["reduction_pct"],
            )

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

        # Track tool calls for retry detection
        if self.retry_tracker:
            self.retry_tracker.record_tool_call()
        self._log_debug("tool_start", tool_name=tool_name)

        # Build status message
        status_msg = f"🛠️ Tool[{self.tool_count}]: {tool_name}"
        if self.show_tool_args and tool_args:
            status_msg = f"{status_msg} {self._sanitize_args(tool_args)}"
        await self._send_status(status_msg)
        self._log_debug(
            "tool_call",
            tool_name=tool_name,
            tool_index=self.tool_count,
            args=self._sanitize_args(tool_args),
        )

        # Execute the tool
        tool_start = time.time()
        try:
            result = await handler(request)
            elapsed = time.time() - tool_start

            self._log_debug(
                "tool_complete",
                tool_name=tool_name,
                elapsed=round(elapsed, 2),
            )
            return result

        except Exception as e:
            elapsed = time.time() - tool_start
            error_msg = str(e)[:100]  # Truncate long errors
            self._log_debug(
                "tool_error",
                tool_name=tool_name,
                elapsed=round(elapsed, 2),
                error=error_msg,
            )
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
        if thread_id:
            # pop() is atomic under GIL
            llm_info = _llm_timing_by_thread.pop(thread_id, None)
            if llm_info and llm_info["count"] > 0:
                count = llm_info["count"]
                llm_time = llm_info["total_time"]
                llm_summary = f" | LLM: {count} call ({llm_time:.1f}s)"

        # Check for retries
        if self.retry_tracker:
            llm_retry_result = self.retry_tracker.detect_llm_retries()
            if llm_retry_result:
                self._log_debug(
                    "llm_retries",
                    expected=llm_retry_result["expected"],
                    actual=llm_retry_result["actual"],
                )

            tool_retry_result = self.retry_tracker.detect_tool_retries()
            if tool_retry_result:
                self._log_debug(
                    "tool_retries",
                    expected=tool_retry_result["expected"],
                    actual=tool_retry_result["actual"],
                )

        # Log call limit messages if present in state.
        self._log_call_limit_messages(state)
        if self._state_has_error(state):
            self._log_debug("state_dump", messages=self._serialize_messages(state.get("messages", [])))

        try:
            if elapsed < 1:
                await self._send_status(f"✅ Done{llm_summary}")
            else:
                await self._send_status(f"✅ Done in {elapsed:.1f}s{llm_summary}")
        finally:
            # ⚡ CRITICAL: Always cleanup, even on exception
            self._log_debug("end", elapsed=round(elapsed, 2))
            clear_middleware_debug()

        return None

    def _sanitize_args(self, args: dict) -> dict:
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

        if len(str(safe_args)) > 150:
            return {"_truncated": str(safe_args)[:100] + "..."}

        return safe_args

    def _log_call_limit_messages(self, state: dict[str, Any]) -> None:
        """Log when call limit middleware terminates a run."""
        messages = state.get("messages", [])
        for msg in messages:
            content = getattr(msg, "content", "")
            if not isinstance(content, str):
                continue
            if "Model call limits exceeded" in content or "Model call limit reached" in content:
                self._log_debug("model_call_limit", message=content)
            if "Tool call limits exceeded" in content or "Tool call limit reached" in content:
                self._log_debug("tool_call_limit", message=content)

    def _state_has_error(self, state: dict[str, Any]) -> bool:
        """Return True if the state includes an error message."""
        messages = state.get("messages", [])
        for msg in messages:
            status = getattr(msg, "status", None)
            if status == "error":
                return True
            content = getattr(msg, "content", "")
            if isinstance(content, str) and ("error" in content.lower() or "failed" in content.lower()):
                return True
        return False

    def _serialize_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Serialize messages for debug dumps."""
        serialized: list[dict[str, Any]] = []
        for msg in messages:
            serialized.append(
                {
                    "type": getattr(msg, "type", None),
                    "status": getattr(msg, "status", None),
                    "content": getattr(msg, "content", None),
                }
            )
        return serialized


def create_status_middleware(
    channel: "BaseChannel",
    expected_llm_calls: int = 1,
) -> StatusUpdateMiddleware | None:
    """
    Factory function to create StatusUpdateMiddleware if enabled.

    Args:
        channel: The channel instance to send status updates through.
        expected_llm_calls: Expected number of LLM calls per agent turn
            (default: 1 for simple agents, use 2+ for reflection/chained reasoning agents).

    Returns:
        StatusUpdateMiddleware instance if enabled, None otherwise.
    """
    if not settings.MW_STATUS_UPDATE_ENABLED:
        return None

    return StatusUpdateMiddleware(
        channel=channel,
        show_tool_args=settings.MW_STATUS_SHOW_TOOL_ARGS,
        update_interval=settings.MW_STATUS_UPDATE_INTERVAL,
        expected_llm_calls=expected_llm_calls,
    )
