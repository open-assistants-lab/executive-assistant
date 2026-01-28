"""Flow tools for APScheduler-backed executor chains."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from executive_assistant.flows.spec import FlowSpec, FlowMiddlewareConfig
from executive_assistant.flows.runner import build_flow_payload, run_flow_by_id
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.agent_registry import get_agent_registry
from executive_assistant.storage.scheduled_flows import get_scheduled_flow_storage
from executive_assistant.tools.reminder_tools import _parse_time_expression
from executive_assistant.utils.cron import parse_cron_next

FLOW_TOOL_NAMES = {"create_flow", "list_flows", "run_flow", "cancel_flow", "delete_flow"}


def _parse_agent_ids(agent_ids: list[str] | str) -> list[str]:
    """Parse agent_ids from list or JSON string."""
    if isinstance(agent_ids, list):
        return agent_ids
    if isinstance(agent_ids, str):
        try:
            parsed = json.loads(agent_ids)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            # Try comma-separated
            return [t.strip() for t in agent_ids.split(",") if t.strip()]
    return []


@tool
async def create_flow(
    name: str,
    description: str,
    agent_ids: list[str] | str,
    schedule_type: str = "immediate",
    schedule_time: str | None = None,
    cron_expression: str | None = None,
    notify_on_complete: bool = False,
    notify_on_failure: bool = True,
    notification_channels: list[str] | str | None = None,
    run_mode: str = "normal",
    flow_input: dict[str, Any] | None = None,
    middleware: dict[str, Any] | None = None,
) -> str:
    """Create a flow (executor chain) for immediate, scheduled, or recurring execution.

    IMPORTANT:
    - Agents are referenced by ID via `agent_ids`.
    - Define agents using create_agent before creating flows.
    - Agent tools should be <=5 (hard cap 10).
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "No thread context available to create a flow."

    owner = thread_id
    flow_id = str(uuid.uuid4())

    schedule_type = schedule_type or "immediate"
    schedule_type = schedule_type.lower()
    if schedule_type == "once":
        schedule_type = "scheduled"
    if schedule_type == "cron":
        schedule_type = "recurring"

    due_time = datetime.now()
    
    # Parse agent_ids (handle both list and JSON string)
    parsed_agent_ids = _parse_agent_ids(agent_ids)
    if not parsed_agent_ids:
        return "Flow creation requires at least one agent_id."
    
    # Parse notification_channels if provided
    parsed_channels = None
    if notification_channels:
        parsed_channels = _parse_agent_ids(notification_channels)  # Same parsing logic

    registry = get_agent_registry(owner)
    missing = [agent_id for agent_id in parsed_agent_ids if not registry.get_agent(agent_id)]
    if missing:
        return f"Error: Agent(s) not found: {missing}. Create them first with create_agent."

    agent_records = [registry.get_agent(agent_id) for agent_id in parsed_agent_ids]
    agents_snapshot = []
    for record in agent_records:
        if not record:
            continue
        agents_snapshot.append(
            {
                "agent_id": record.agent_id,
                "name": record.name,
                "description": record.description,
                "tools": record.tools,
                "system_prompt": record.system_prompt,
                "output_schema": record.output_schema,
            }
        )

    warnings = []
    for agent_id in parsed_agent_ids:
        agent = registry.get_agent(agent_id)
        if agent and len(agent.tools) > 5:
            warnings.append(f"{agent_id} uses {len(agent.tools)} tools (recommended <=5)")

    # Validate first agent uses $input when flow_input is provided
    first_agent = registry.get_agent(parsed_agent_ids[0]) if parsed_agent_ids else None
    if flow_input is not None and first_agent and "$input" not in first_agent.system_prompt:
        return "Error: first agent system_prompt must include $input when flow_input is provided."

    # Require flow_input for the first agent to avoid empty context
    if flow_input is None:
        return "Error: flow_input is required for flows to provide context to the first agent."

    # Guard: cron "* * * * *" is often used to mean "run now" and can create duplicate flows.
    if schedule_type == "recurring" and cron_expression and cron_expression.strip() == "* * * * *":
        return "Error: cron '* * * * *' is not allowed. Use schedule_type='immediate' for one-off runs."

    # If immediate flow includes a cron, ignore it to avoid accidental recurring duplicates.
    if schedule_type == "immediate" and cron_expression:
        warnings.append("cron_expression ignored for immediate flows")
        cron_expression = None


    if schedule_type == "scheduled":
        if not schedule_time:
            return "schedule_time is required for scheduled flows."
        due_time = _parse_time_expression(schedule_time)
    elif schedule_type == "recurring":
        if not cron_expression:
            return "cron_expression is required for recurring flows."
        due_time = parse_cron_next(cron_expression, datetime.now())
    elif schedule_type != "immediate":
        return "schedule_type must be immediate, scheduled, or recurring."

    forbidden = []
    for agent_id in parsed_agent_ids:
        agent = registry.get_agent(agent_id)
        if not agent:
            continue
        for tool_name in agent.tools:
            if tool_name in FLOW_TOOL_NAMES:
                forbidden.append(tool_name)
    if forbidden:
        return f"Flow agents may not use flow management tools: {sorted(set(forbidden))}"

    middleware_config = FlowMiddlewareConfig.model_validate(middleware or {})
    if middleware_config.model_call_limit and middleware_config.model_call_limit > 10:
        return "Error: flow model_call_limit must be <= 10"
    if middleware_config.tool_call_limit and middleware_config.tool_call_limit > 10:
        return "Error: flow tool_call_limit must be <= 10"

    spec = FlowSpec(
        flow_id=flow_id,
        name=name,
        description=description,
        owner=owner,
        agent_ids=parsed_agent_ids,
        agents=agents_snapshot,
        schedule_type=schedule_type,
        schedule_time=due_time if schedule_type == "scheduled" else None,
        cron_expression=cron_expression,
        notify_on_complete=notify_on_complete,
        notify_on_failure=notify_on_failure,
        notification_channels=parsed_channels or [thread_id.split(":")[0]],
        run_mode=run_mode,
        middleware=middleware_config,
        flow_input=flow_input,
    )

    storage = await get_scheduled_flow_storage()
    payload = build_flow_payload(spec)
    flow = await storage.create(
        thread_id=thread_id,
        task=description,
        flow=payload,
        due_time=due_time,
        name=name,
        cron=cron_expression,
    )

    msg = f"Flow created: {flow.id} ({spec.name}) scheduled for {due_time.isoformat()}"
    if warnings:
        msg += " | Warnings: " + "; ".join(warnings)
    return msg


@tool
async def list_flows(status: str | None = None) -> str:
    """List flows for the current thread."""
    thread_id = get_thread_id()
    if not thread_id:
        return "No thread context available to list flows."

    if status is not None:
        status = status.strip().lower()
        if status in {"all", "any", "*", ""}:
            status = None

    storage = await get_scheduled_flow_storage()
    flows = await storage.list_by_thread(thread_id, status=status)

    if not flows:
        return "No flows found."

    lines = []
    for flow in flows:
        lines.append(f"- [{flow.id}] {flow.name or '-'} — {flow.status} (due {flow.due_time})")

    return "\n".join(lines)


@tool
async def run_flow(flow_id: int) -> str:
    """Run a flow immediately by ID."""
    result = await run_flow_by_id(flow_id)
    return json.dumps(result, ensure_ascii=False)


@tool
async def cancel_flow(flow_id: int) -> str:
    """Cancel a pending flow by ID."""
    storage = await get_scheduled_flow_storage()
    success = await storage.cancel(flow_id)
    if success:
        return f"Flow {flow_id} cancelled."
    return f"Flow {flow_id} not found or not pending."


@tool
async def delete_flow(flow_id: int) -> str:
    """Delete a flow by ID."""
    storage = await get_scheduled_flow_storage()
    success = await storage.delete(flow_id)
    if success:
        return f"Flow {flow_id} deleted."
    return f"Flow {flow_id} not found."
