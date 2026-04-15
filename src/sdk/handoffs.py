"""Handoffs for the agent SDK — multi-agent delegation.

A Handoff defines how one agent can transfer control to another.
It is exposed as a tool (auto-named "transfer_to_{agent_name}") that
the LLM can call to delegate to a sub-agent.

The input_filter controls what conversation history the receiving agent sees.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from src.sdk.messages import Message


class HandoffInput(BaseModel):
    """Input data passed when a handoff occurs."""

    input_history: list[Message] = Field(default_factory=list)
    pre_handoff_items: list[Message] = Field(default_factory=list)
    new_items: list[Message] = Field(default_factory=list)


class Handoff(BaseModel):
    """Defines a handoff from one agent to another.

    The handoff is exposed as a tool named "transfer_to_{agent_name}".
    """

    agent_name: str
    tool_name: str = ""
    description: str = ""
    input_filter: Callable | None = None
    on_handoff: Callable | None = None
    is_enabled: bool = True

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if not self.tool_name:
            self.tool_name = f"transfer_to_{self.agent_name}"
        if not self.description:
            self.description = f"Transfer the conversation to the {self.agent_name} agent."

    def to_tool_schema(self) -> dict:
        """Return an OpenAI-format tool definition for this handoff."""
        return {
            "type": "function",
            "function": {
                "name": self.tool_name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Brief reason for the handoff",
                        }
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        }

    def to_anthropic_schema(self) -> dict:
        """Return an Anthropic-format tool definition for this handoff."""
        return {
            "name": self.tool_name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the handoff",
                    }
                },
                "required": [],
            },
        }

    def filter_input(self, handoff_input: HandoffInput) -> list[Message]:
        """Apply the input_filter to determine what the next agent sees."""
        if self.input_filter is not None:
            return self.input_filter(handoff_input)
        return handoff_input.input_history + handoff_input.new_items
