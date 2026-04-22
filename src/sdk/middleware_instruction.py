"""Instruction middleware — checks for course-correction and cancel signals.

Runs inside subagent AgentLoops. Before each LLM call, polls the work_queue
for new instructions (injected via subagent_instruct) and cancel_requested flag.

Uses abefore_model hook: fires before each LLM call, ensuring the subagent
sees supervisor updates before generating its next response.
"""

from __future__ import annotations

import json
from typing import Any

from src.app_logging import get_logger
from src.sdk.messages import Message
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState
from src.sdk.subagent_models import TaskCancelledError

logger = get_logger()


class InstructionMiddleware(Middleware):
    """Checks work_queue for instructions and cancel signals before each LLM call."""

    def __init__(self, task_id: str, db: Any):
        self.task_id = task_id
        self.db = db
        self._last_checked = ""

    async def abefore_model(self, state: AgentState) -> dict[str, Any] | None:
        try:
            row = await self.db.get_task(self.task_id)
        except Exception as e:
            logger.warning(
                "subagent.instruction_check_failed",
                {"task_id": self.task_id, "error": str(e)},
            )
            return None

        if row is None:
            return None

        if row.get("cancel_requested"):
            raise TaskCancelledError(self.task_id)

        instructions = json.loads(row.get("instructions") or "[]")
        new = [i for i in instructions if i["added_at"] > self._last_checked] if self._last_checked else instructions

        if new:
            self._last_checked = instructions[-1]["added_at"]
            for inst in new:
                state.add_message(Message.system(
                    f"[Supervisor Update] {inst['message']}"
                ))

        return None
