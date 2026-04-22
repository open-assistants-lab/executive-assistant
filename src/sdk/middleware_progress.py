"""Progress middleware — updates work_queue progress and detects doom loops.

Runs inside subagent AgentLoops. Updates work_queue.progress after each iteration
(before the next LLM call) and detects doom loops (same tool+args 3x).

Uses abefore_model hook: fires at the start of each LLM call iteration,
which means tool calls from the previous iteration have already completed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.app_logging import get_logger
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState

logger = get_logger()

DOOM_THRESHOLD = 3


class ProgressMiddleware(Middleware):
    """Updates work_queue progress after tool calls and detects doom loops."""

    def __init__(self, task_id: str, db: Any):
        self.task_id = task_id
        self.db = db
        self._last_tool_calls: list[str] = []
        self._steps_completed = 0

    async def abefore_model(self, state: AgentState) -> dict[str, Any] | None:
        tool_results = [m for m in state.messages if m.role == "tool"]
        if not tool_results:
            return None

        last_result = tool_results[-1]
        tool_name = getattr(last_result, "name", None) or "unknown"
        self._steps_completed += 1

        # Doom loop detection: same tool+args 3 times
        tool_args = {}
        try:
            raw = getattr(last_result, "content", "")
            if isinstance(raw, str):
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    tool_args = parsed
        except (json.JSONDecodeError, TypeError):
            pass

        args_json = json.dumps(tool_args, sort_keys=True, ensure_ascii=True)
        call_hash = f"{tool_name}:{hashlib.md5(args_json.encode()).hexdigest()[:8]}"
        self._last_tool_calls.append(call_hash)
        if len(self._last_tool_calls) > DOOM_THRESHOLD:
            self._last_tool_calls = self._last_tool_calls[-DOOM_THRESHOLD:]

        is_stuck = (
            len(self._last_tool_calls) >= DOOM_THRESHOLD
            and len(set(self._last_tool_calls)) == 1
        )

        try:
            await self.db.update_progress(self.task_id, {
                "steps_completed": self._steps_completed,
                "phase": "executing",
                "message": f"Called {tool_name}",
                "stuck": is_stuck,
            })

            if is_stuck:
                await self.db.add_instruction(
                    self.task_id,
                    "Doom loop detected: same tool called 3x with identical args. "
                    "Consider cancelling or redirecting this task.",
                )
        except Exception as e:
            logger.warning(
                "subagent.progress_update_failed",
                {"task_id": self.task_id, "error": str(e)},
            )

        return None
