"""Guardrails for the agent SDK — input, output, and tool-level checks.

Guardrails are async checks that run at defined points in the agent loop.
If a guardrail's tripwire is triggered, a GuardrailTripwire exception is raised,
which the agent loop catches and handles gracefully.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel


class GuardrailResult(BaseModel):
    """Result from a guardrail check."""

    tripwire_triggered: bool = False
    message: str | None = None


class InputGuardrail(BaseModel):
    """Guardrail that checks user input before the LLM call."""

    name: str
    check: Callable  # async (input: str, state: AgentState) -> GuardrailResult

    model_config = {"arbitrary_types_allowed": True}


class OutputGuardrail(BaseModel):
    """Guardrail that checks LLM output after generation."""

    name: str
    check: Callable  # async (output: str, state: AgentState) -> GuardrailResult

    model_config = {"arbitrary_types_allowed": True}


class ToolGuardrail(BaseModel):
    """Guardrail that checks tool call arguments and/or results."""

    name: str
    check_input: Callable | None = (
        None  # async (tool_name: str, args: dict) -> GuardrailResult | None
    )
    check_output: Callable | None = (
        None  # async (tool_name: str, result: str) -> GuardrailResult | None
    )

    model_config = {"arbitrary_types_allowed": True}


class GuardrailTripwire(Exception):  # noqa: N818
    """Raised when a guardrail's tripwire is triggered."""

    def __init__(self, result: GuardrailResult, guardrail_name: str = ""):
        self.result = result
        self.guardrail_name = guardrail_name
        super().__init__(result.message or f"Guardrail '{guardrail_name}' triggered")
