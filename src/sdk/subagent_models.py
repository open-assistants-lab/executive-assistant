"""Subagent models — AgentDef, SubagentResult, and task status types.

V1 subagent architecture: delegation-and-return with SQLite work_queue coordination.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_DISALLOWED_TOOLS = [
    "subagent_create",
    "subagent_update",
    "subagent_delete",
    "subagent_list",
    "subagent_start",
    "subagent_check",
    "subagent_tasks",
    "subagent_instruct",
    "subagent_cancel",
    "research_start",
    "research_list",
]

DEFAULT_SAFE_DENIED_TOOLS = [
    "shell_execute",
    "email_send",
    "email_connect",
    "email_disconnect",
    "browser_click",
    "browser_input",
    "browser_type",
    "browser_eval",
    "browser_open",
    "browser_keys",
]

SAFE_DISALLOWED_TOOLS = list(DEFAULT_DISALLOWED_TOOLS) + list(DEFAULT_SAFE_DENIED_TOOLS)

DEFAULT_MAX_LLM_CALLS = 50
DEFAULT_COST_LIMIT_USD = 1.0
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_OUTPUT_CHARS = 10000


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
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
    workspace_id: str = "personal"
    model: str | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    tools: list[str] | None = None
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS
    cost_limit_usd: float = DEFAULT_COST_LIMIT_USD
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    mcp_config: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None

    model_config = {"extra": "ignore"}

    def to_profile(self) -> dict[str, Any]:
        """Serialize to AgentProfile-compatible dict."""
        data: dict[str, Any] = {
            "version": 1,
            "name": self.name,
            "description": self.description,
            "model": self.model or "",
            "tools": self.tools or [],
            "system_prompt": self.system_prompt or "",
            "skills": self.skills or [],
            "tags": self.tags or [],
            "handoff_instructions": self.handoff_instructions,
        }
        if self.provider_options:
            data["provider"] = "provider.json"
        if self.output_schema:
            data["output_schema"] = "output-schema.json"
        return data

    @classmethod
    def from_profile(cls, data: dict[str, Any]) -> "AgentDef":
        """Create AgentDef from an AgentProfile dict."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            model=data.get("model"),
            tools=data.get("tools"),
            system_prompt=data.get("system_prompt"),
            skills=data.get("skills", []),
            tags=data.get("tags", []),
            output_schema=data.get("output_schema_def"),
            provider_options=data.get("provider_options", {}),
            handoff_instructions=data.get("handoff_instructions"),
        )


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
