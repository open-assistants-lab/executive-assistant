"""Agent registry tools (per-user)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from executive_assistant.storage.agent_registry import get_agent_registry
from executive_assistant.storage.file_sandbox import get_thread_id

def _get_thread_id() -> str:
    thread_id = get_thread_id()
    if not thread_id:
        raise ValueError("No thread context available.")
    return thread_id


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
    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
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
    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
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
    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
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
    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
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
    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
    return registry.delete_agent(agent_id)


@tool
async def run_agent(
    agent_id: str,
    flow_input: dict | str | None = None,
    previous_output: dict | str | None = None,
    run_mode: str = "normal",
) -> str:
    """Run a mini-agent once for testing. Provide flow_input/previous_output as dict or JSON string."""
    import json as _json
    from executive_assistant.flows.spec import AgentSpec, FlowMiddlewareConfig
    from executive_assistant.flows import runner

    thread_id = _get_thread_id()
    registry = get_agent_registry(thread_id)
    record = registry.get_agent(agent_id)
    if not record:
        return f"Agent '{agent_id}' not found."

    def _parse_dict(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = _json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except _json.JSONDecodeError:
                return None
        return None

    flow_input_dict = _parse_dict(flow_input)
    prev_output_dict = _parse_dict(previous_output)

    if flow_input is not None and flow_input_dict is None:
        return "Error: flow_input must be a dict or JSON object string."
    if previous_output is not None and prev_output_dict is None:
        return "Error: previous_output must be a dict or JSON object string."

    if flow_input_dict is not None and "$input" not in record.system_prompt:
        return "Error: agent prompt must include $input when flow_input is provided."
    if prev_output_dict is not None and "$output" not in record.system_prompt:
        return "Error: agent prompt must include $output when previous_output is provided."

    agent_spec = AgentSpec(
        agent_id=record.agent_id,
        name=record.name,
        description=record.description,
        tools=record.tools,
        system_prompt=record.system_prompt,
        output_schema=record.output_schema or {},
    )

    output = await runner._run_agent(
        agent_spec,
        previous_output=prev_output_dict,
        flow_input=flow_input_dict,
        run_mode=run_mode,
        middleware_config=FlowMiddlewareConfig(),
    )
    return _json.dumps(output, indent=2, ensure_ascii=False)
