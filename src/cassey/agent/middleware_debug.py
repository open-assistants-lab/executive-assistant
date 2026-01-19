"""Middleware debugging utilities for tracking agent middleware effectiveness.

Provides detection and logging for:
- Summarization (message/token reduction)
- Context editing (tool_uses reduction)
- Retries (LLM and tool call retries)
- Limits (call limits hit)

Usage:
    from cassey.agent.middleware_debug import MiddlewareDebug

    debug = MiddlewareDebug()
    debug.capture_before_model(state)
    debug.capture_after_model(state)
    debug.log_detections()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.messages.utils import count_tokens_approximately

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class MiddlewareDebug:
    """
    Tracks middleware actions for debugging and effectiveness verification.

    Captures state before/after model calls to detect:
    - Summarization: Messages reduced to summary
    - Context editing: Tool uses trimmed
    - Retries: Additional LLM/tool calls beyond expected
    """

    def __init__(self) -> None:
        # Before state
        self.messages_before: int = 0
        self.tokens_before: int = 0
        self.tool_uses_before: int = 0

        # After state
        self.messages_after: int = 0
        self.tokens_after: int = 0
        self.tool_uses_after: int = 0

        # Detection flags
        self._captured_before: bool = False
        self._captured_after: bool = False

    def capture_before_model(self, state: dict) -> None:
        """Capture state before model/middleware processing."""
        messages = state.get("messages", [])
        self.messages_before = len(messages)
        self.tokens_before = count_tokens_approximately(messages) if messages else 0
        self.tool_uses_before = self._count_tool_uses(messages)
        self._captured_before = True

    def capture_after_model(self, state: dict) -> None:
        """Capture state after model/middleware processing."""
        messages = state.get("messages", [])
        self.messages_after = len(messages)
        self.tokens_after = count_tokens_approximately(messages) if messages else 0
        self.tool_uses_after = self._count_tool_uses(messages)
        self._captured_after = True

    def _count_tool_uses(self, messages: list) -> int:
        """Count tool use entries in messages (for context editing detection)."""
        count = 0
        for msg in messages:
            if hasattr(msg, "content") and isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        count += 1
            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                count += len(msg.tool_calls)
        return count

    def detect_summarization(self) -> dict | None:
        """
        Detect if summarization occurred (message count dropped significantly).

        Returns:
            Dict with before/after stats, or None if no summarization.
        """
        if not self._captured_before:
            logger.warning("detect_summarization() called before capture_before_model()")
            return None

        if not self._captured_after:
            logger.warning("detect_summarization() called before capture_after_model()")
            return None

        # Summarization typically reduces messages significantly
        # Only trigger if we had meaningful content before (>10 messages)
        if self.messages_before <= 10:
            return None

        if self.messages_after >= self.messages_before:
            return None

        msg_reduction = self.messages_before - self.messages_after
        token_reduction = self.tokens_before - self.tokens_after
        reduction_pct = (
            (token_reduction / self.tokens_before * 100) if self.tokens_before > 0 else 0
        )

        return {
            "type": "summarization",
            "messages_before": self.messages_before,
            "messages_after": self.messages_after,
            "messages_removed": msg_reduction,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "tokens_saved": token_reduction,
            "reduction_pct": reduction_pct,
        }

    def detect_context_editing(self) -> dict | None:
        """
        Detect if context editing occurred (tool_uses reduced).

        Returns:
            Dict with before/after stats, or None if no context editing.
        """
        if not self._captured_before:
            logger.warning("detect_context_editing() called before capture_before_model()")
            return None

        if not self._captured_after:
            logger.warning("detect_context_editing() called before capture_after_model()")
            return None

        # Context editing reduces tool_uses while keeping messages
        if self.tool_uses_before == 0:
            return None

        if self.tool_uses_after >= self.tool_uses_before:
            return None

        uses_reduction = self.tool_uses_before - self.tool_uses_after
        reduction_pct = (
            (uses_reduction / self.tool_uses_before * 100) if self.tool_uses_before > 0 else 0
        )

        return {
            "type": "context_editing",
            "tool_uses_before": self.tool_uses_before,
            "tool_uses_after": self.tool_uses_after,
            "uses_removed": uses_reduction,
            "reduction_pct": reduction_pct,
        }

    def log_summarization(self, result: dict, print_func: Callable = print) -> None:
        """Log summarization detection results."""
        print_func(
            f"[SUMMARIZATION] {result['messages_before']} → {result['messages_after']} messages "
            f"({result['messages_removed']} removed)"
        )
        print_func(
            f"[SUMMARIZATION] ~{result['tokens_before']} → ~{result['tokens_after']} tokens "
            f"({result['tokens_saved']} saved, {result['reduction_pct']:.1f}% reduction)"
        )

    def log_context_editing(self, result: dict, print_func: Callable = print) -> None:
        """Log context editing detection results."""
        print_func(
            f"[CONTEXT_EDIT] Tool uses: {result['tool_uses_before']} → {result['tool_uses_after']} "
            f"({result['uses_removed']} removed, {result['reduction_pct']:.1f}% reduction)"
        )

    def reset(self) -> None:
        """Reset state for next detection cycle."""
        self.messages_before = 0
        self.tokens_before = 0
        self.tool_uses_before = 0
        self.messages_after = 0
        self.tokens_after = 0
        self.tool_uses_after = 0
        self._captured_before = False
        self._captured_after = False


class RetryTracker:
    """
    Tracks LLM and tool call retries by counting actual vs expected calls.

    Usage:
        tracker = RetryTracker()
        tracker.start_run(expected_calls=1)  # 1 expected for this turn
        # ... LLM calls happen ...
        tracker.record_llm_call()
        # ... if more calls happen, it's a retry ...
        tracker.end_run()
        tracker.log_retries()
    """

    def __init__(self) -> None:
        self.llm_calls_this_run: int = 0
        self.tool_calls_this_run: int = 0
        self.expected_llm_calls: int = 1
        self.expected_tool_calls: int = 0

    def start_run(self, expected_llm: int = 1, expected_tools: int = 0) -> None:
        """Start tracking a new run with expected call counts."""
        self.llm_calls_this_run = 0
        self.tool_calls_this_run = 0
        self.expected_llm_calls = expected_llm
        self.expected_tool_calls = expected_tools

    def record_llm_call(self) -> None:
        """Record an LLM call (increment counter)."""
        self.llm_calls_this_run += 1

    def record_tool_call(self) -> None:
        """Record a tool call (increment counter)."""
        self.tool_calls_this_run += 1

    def detect_llm_retries(self) -> dict | None:
        """Detect if LLM retries occurred (more calls than expected)."""
        excess = self.llm_calls_this_run - self.expected_llm_calls
        if excess > 0:
            return {
                "type": "llm_retry",
                "expected": self.expected_llm_calls,
                "actual": self.llm_calls_this_run,
                "retries": excess,
            }
        return None

    def detect_tool_retries(self) -> dict | None:
        """Detect if tool retries occurred (more calls than expected)."""
        # Note: Multi-tool agents legitimately make multiple calls
        # Only flag if same tool was called multiple times (would need tool name tracking)
        # For now, just report the count
        if self.tool_calls_this_run > self.expected_tool_calls and self.expected_tool_calls > 0:
            excess = self.tool_calls_this_run - self.expected_tool_calls
            return {
                "type": "tool_retry",
                "expected": self.expected_tool_calls,
                "actual": self.tool_calls_this_run,
                "retries": excess,
            }
        return None

    def log_llm_retries(self, result: dict, print_func: Callable = print) -> None:
        """Log LLM retry detection."""
        print_func(
            f"[LLM_RETRY] Expected {result['expected']} call, "
            f"got {result['actual']} ({result['retries']} retry{'ies' if result['retries'] > 1 else 'y'})"
        )

    def log_tool_retries(self, result: dict, print_func: Callable = print) -> None:
        """Log tool retry detection."""
        print_func(
            f"[TOOL_RETRY] Expected {result['expected']} tool call, "
            f"got {result['actual']} ({result['retries']} retry{'ies' if result['retries'] > 1 else 'y'})"
        )
