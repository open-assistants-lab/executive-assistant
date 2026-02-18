from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentState, ModelRequest, ModelResponse
    from langchain.tools.tool_node import ToolCallRequest
    from langchain.messages import ToolMessage
    from langgraph.runtime import Runtime
    from langgraph.types import Command

logger = logging.getLogger(__name__)


class LoggingMiddleware(AgentMiddleware):
    """Log agent activity for debugging and analytics.

    Logs model calls, tool calls, and memory access to JSONL files.

    Usage:
        agent = create_deep_agent(
            model="gpt-4o",
            middleware=[LoggingMiddleware(log_dir=Path("/data/logs"))],
        )
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        user_id: str = "default",
        log_model_calls: bool = True,
        log_tool_calls: bool = True,
        log_memory_access: bool = True,
        log_errors: bool = True,
    ) -> None:
        super().__init__()
        self.log_dir = log_dir or Path("/data/logs")
        self.user_id = user_id
        self.log_model_calls = log_model_calls
        self.log_tool_calls = log_tool_calls
        self.log_memory_access = log_memory_access
        self.log_errors = log_errors

        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[LoggingMiddleware] Initialized for user '{user_id}', log_dir={self.log_dir}")

    def _get_log_file(self) -> Path:
        """Get log file path for today."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"agent-{date_str}.jsonl"

    def _log(self, event: str, data: dict) -> None:
        """Write a log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": self.user_id,
            "event": event,
            "data": data,
        }

        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def before_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Log before model call."""
        if not self.log_model_calls:
            return None

        messages = state.get("messages", [])
        last_user_msg = None
        for msg in reversed(messages):
            if msg.type == "human":
                last_user_msg = msg.content[:200] if hasattr(msg, "content") else None
                break

        self._log(
            "model_call_start",
            {
                "message_count": len(messages),
                "last_user_message": last_user_msg,
            },
        )

        return None

    def after_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Log after model response."""
        if not self.log_model_calls:
            return None

        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None

        response_preview = None
        tool_calls = []
        if last_msg:
            if hasattr(last_msg, "content"):
                response_preview = str(last_msg.content)[:200]
            if hasattr(last_msg, "tool_calls"):
                tool_calls = [
                    {"name": tc.get("name"), "args": str(tc.get("args", {}))[:100]}
                    for tc in last_msg.tool_calls
                ]

        self._log(
            "model_call_end",
            {
                "response_preview": response_preview,
                "tool_calls": tool_calls,
                "message_count": len(messages),
            },
        )

        return None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Wrap model call with timing and error logging."""
        start_time = datetime.now(timezone.utc)

        try:
            response = handler(request)

            if self.log_model_calls:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self._log(
                    "model_call_complete",
                    {
                        "duration_ms": round(duration_ms, 2),
                        "message_count": len(request.messages),
                        "success": True,
                    },
                )

            return response

        except Exception as e:
            if self.log_errors:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self._log(
                    "model_call_error",
                    {
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            raise

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async wrap model call with timing and error logging."""
        logger.debug("[LoggingMiddleware] awrap_model_call called")
        start_time = datetime.now(timezone.utc)

        try:
            response = await handler(request)

            if self.log_model_calls:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                logger.debug(f"[LoggingMiddleware] Model call completed in {duration_ms:.2f}ms")
                self._log(
                    "model_call_complete",
                    {
                        "duration_ms": round(duration_ms, 2),
                        "message_count": len(request.messages),
                        "success": True,
                    },
                )

            return response

        except Exception as e:
            if self.log_errors:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                logger.debug(f"[LoggingMiddleware] Model call failed after {duration_ms:.2f}ms: {e}")
                self._log(
                    "model_call_error",
                    {
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            raise

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], "ToolMessage | Command"],
    ) -> "ToolMessage | Command":
        """Wrap tool call with logging."""
        if not self.log_tool_calls:
            return handler(request)

        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})

        start_time = datetime.now(timezone.utc)

        self._log(
            "tool_call_start",
            {
                "tool": tool_name,
                "args": str(tool_args)[:200],
            },
        )

        try:
            result = handler(request)

            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            result_preview = None
            if hasattr(result, "content"):
                result_preview = str(result.content)[:200]

            self._log(
                "tool_call_end",
                {
                    "tool": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "success": True,
                    "result_preview": result_preview,
                },
            )

            return result

        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            self._log(
                "tool_call_error",
                {
                    "tool": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable["ToolMessage | Command"]],
    ) -> "ToolMessage | Command":
        """Async wrap tool call with logging."""
        if not self.log_tool_calls:
            return await handler(request)

        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})

        logger.debug(f"[LoggingMiddleware] Tool call started: {tool_name}")

        start_time = datetime.now(timezone.utc)

        self._log(
            "tool_call_start",
            {
                "tool": tool_name,
                "args": str(tool_args)[:200],
            },
        )

        try:
            result = await handler(request)

            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            result_preview = None
            if hasattr(result, "content"):
                result_preview = str(result.content)[:200]

            logger.debug(f"[LoggingMiddleware] Tool call completed: {tool_name} ({duration_ms:.2f}ms)")

            self._log(
                "tool_call_end",
                {
                    "tool": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "success": True,
                    "result_preview": result_preview,
                },
            )

            return result

        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            logger.debug(f"[LoggingMiddleware] Tool call failed: {tool_name} - {e}")

            self._log(
                "tool_call_error",
                {
                    "tool": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Log after agent completes."""
        messages = state.get("messages", [])

        self._log(
            "agent_complete",
            {
                "total_messages": len(messages),
            },
        )

        return None
