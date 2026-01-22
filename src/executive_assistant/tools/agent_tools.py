"""Agent registry tools (per-user)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from executive_assistant.storage.agent_registry import get_agent_registry
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id


def _get_user_id() -> str:
    thread_id = get_thread_id()
    if not thread_id:
        raise ValueError("No thread context available.")
    return sanitize_thread_id_to_user_id(thread_id)


def _parse_tools(tools: list[str] | str) -> list[str]:
    if isinstance(tools, list):
        return tools
    if isinstance(tools, str):
        try:
            parsed = json.loads(tools)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return [t.strip() for t in tools.split(",") if t.strip()]
    return []


@tool
async def create_agent(
    agent_id: str,
    name: str,
    description: str,
    tools: list[str] | str,
    system_prompt: str,
    output_schema: dict | None = None,
) -> str:
    """Create a mini-agent for flows (per-user)."""
    user_id = _get_user_id()
    registry = get_agent_registry(user_id)
    tools_list = _parse_tools(tools)
    return registry.create_agent(
        agent_id=agent_id,
        name=name,
        description=description,
        tools=tools_list,
        system_prompt=system_prompt,
        output_schema=output_schema,
    )


@tool
async def list_agents() -> str:
    """List registered mini-agents for the current user."""
    user_id = _get_user_id()
    registry = get_agent_registry(user_id)
    agents = registry.list_agents()
    if not agents:
        return "No agents found."
    lines = ["Agents:"]
    for i, agent in enumerate(agents, start=1):
        lines.append(
            f"- [{i}] {agent.agent_id} — {agent.name} (tools: {len(agent.tools)})"
        )
    return "\n".join(lines)


@tool
async def get_agent(agent_id: str) -> str:
    """Get a mini-agent definition by agent_id."""
    user_id = _get_user_id()
    registry = get_agent_registry(user_id)
    agent = registry.get_agent(agent_id)
    if not agent:
        return f"Agent '{agent_id}' not found."
    return (
        f"Agent {agent.agent_id}\n"
        f"Name: {agent.name}\n"
        f"Description: {agent.description}\n"
        f"Tools: {agent.tools}\n"
        f"System prompt: {agent.system_prompt}\n"
        f"Output schema: {agent.output_schema}"
    )


@tool
async def update_agent(
    agent_id: str,
    name: str | None = None,
    description: str | None = None,
    tools: list[str] | str | None = None,
    system_prompt: str | None = None,
    output_schema: dict | None = None,
) -> str:
    """Update a mini-agent definition."""
    user_id = _get_user_id()
    registry = get_agent_registry(user_id)
    tools_list = _parse_tools(tools) if tools is not None else None
    return registry.update_agent(
        agent_id=agent_id,
        name=name,
        description=description,
        tools=tools_list,
        system_prompt=system_prompt,
        output_schema=output_schema,
    )


@tool
async def delete_agent(agent_id: str) -> str:
    """Delete a mini-agent by agent_id."""
    user_id = _get_user_id()
    registry = get_agent_registry(user_id)
    return registry.delete_agent(agent_id)
