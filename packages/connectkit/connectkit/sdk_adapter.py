"""Generic tool specification — the adapter boundary between ConnectKit and any agent SDK.

ConnectKit meta-tools produce ToolSpec objects. Framework adapters (EA SDK, OpenAI,
LangChain, etc.) convert ToolSpec into their own tool format.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Framework-agnostic tool definition.

    Fields match the OpenAI tool-calling JSON Schema pattern so any SDK
    (EA, LangChain, OpenAI, Anthropic) can adapt it with minimal glue.
    """

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)  # JSON Schema
    annotations: dict[str, Any] = Field(default_factory=dict)  # read_only, destructive, etc.

    # One of these must be set. Both accept **kwargs matching the parameter schema.
    function: Callable[..., Any] | None = None
    async_function: (
        Callable[..., Coroutine[Any, Any, Any]] | None
    ) = None

    def model_dump_tool(self) -> dict[str, Any]:
        """Return a plain dict for framework-agnostic serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "annotations": self.annotations,
            "function": self.function,
            "async_function": self.async_function,
        }