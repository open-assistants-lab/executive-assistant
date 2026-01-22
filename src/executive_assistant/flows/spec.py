"""Flow specification models for APScheduler-backed execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class FlowMiddlewareConfig(BaseModel):
    """Middleware configuration for flow agents."""

    model_call_limit: Optional[int] = None
    tool_call_limit: Optional[int] = None
    model_retry_enabled: bool = True
    tool_retry_enabled: bool = True
    tool_emulator_tools: Optional[list[str]] = None


class AgentSpec(BaseModel):
    """Definition of a single agent (tools + prompt)."""

    agent_id: str
    name: str
    description: str
    tools: list[str]
    system_prompt: str
    output_schema: dict = Field(default_factory=dict)


class FlowSpec(BaseModel):
    """Definition of a flow (multi-agent chain)."""

    flow_id: str
    name: str
    description: str
    owner: str
    agent_ids: list[str]
    agents: list[AgentSpec] | None = None
    schedule_type: Literal["immediate", "scheduled", "recurring"] = "immediate"
    schedule_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    notify_on_complete: bool = False
    notify_on_failure: bool = True
    notification_channels: list[str] = Field(default_factory=lambda: ["telegram"])
    run_mode: Literal["normal", "emulated"] = "normal"
    middleware: FlowMiddlewareConfig = Field(default_factory=FlowMiddlewareConfig)
    input_payload: dict[str, Any] | None = None
