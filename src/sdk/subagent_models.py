"""Subagent models — AgentDef, SubagentResult, and task status types.

V1 subagent architecture: delegation-and-return with SQLite work_queue coordination.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_DISALLOWED_TOOLS = [
    "subagent_create",
    "subagent_invoke",
    "subagent_list",
    "subagent_progress",
    "subagent_instruct",
    "subagent_cancel",
    "subagent_delete",
    "subagent_update",
]

DEFAULT_MAX_LLM_CALLS = 50
DEFAULT_COST_LIMIT_USD = 1.0
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_OUTPUT_CHARS = 10000


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentDef(BaseModel):
    """Declarative subagent definition.

    Created dynamically at runtime or loaded from persisted config.
    Can be reused (invoke by name) or amended (partial update).
    """

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    description: str = ""
    model: str | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None
    disallowed_tools: list[str] = Field(default_factory=lambda: list(DEFAULT_DISALLOWED_TOOLS))
    skills: list[str] = Field(default_factory=list)
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS
    cost_limit_usd: float = DEFAULT_COST_LIMIT_USD
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    mcp_config: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}


class SubagentResult(BaseModel):
    """Structured result from a subagent invocation."""

    name: str
    task: str
    success: bool
    output: str
    truncated: bool = False
    cost_usd: float = 0.0
    llm_calls: int = 0
    error: str | None = None


class TaskCancelledError(Exception):
    """Raised when a task is cancelled by the supervisor."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task {task_id} cancelled by supervisor")


class MaxCallsExceededError(Exception):
    """Raised when max_llm_calls is exceeded."""

    def __init__(self, task_id: str, limit: int):
        self.task_id = task_id
        self.limit = limit
        super().__init__(f"Task {task_id}: exceeded max_llm_calls ({limit})")


class CostLimitExceededError(Exception):
    """Raised when cost_limit_usd is exceeded."""

    def __init__(self, task_id: str, limit: float):
        self.task_id = task_id
        self.limit = limit
        super().__init__(f"Task {task_id}: exceeded cost_limit_usd (${limit})")
