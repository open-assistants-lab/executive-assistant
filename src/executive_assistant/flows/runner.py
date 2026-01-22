"""Flow execution runner for APScheduler-backed flows."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage

from executive_assistant.config import settings, create_model
from executive_assistant.agent.langchain_state import ExecutiveAssistantAgentState
from executive_assistant.flows.spec import FlowSpec, AgentSpec, FlowMiddlewareConfig
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
from executive_assistant.storage.scheduled_flows import ScheduledFlow, get_scheduled_flow_storage
from executive_assistant.storage.agent_registry import get_agent_registry
from executive_assistant.tools.registry import get_tools_by_name
from executive_assistant.utils.cron import parse_cron_next

logger = logging.getLogger(__name__)

FLOW_TOOL_NAMES = {"create_flow", "list_flows", "run_flow", "cancel_flow", "delete_flow"}
_FLOW_OUTPUT_PREVIEW_CHARS = 240


def _preview_text(value: str, limit: int = _FLOW_OUTPUT_PREVIEW_CHARS) -> str:
    text = value.replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _parse_flow_spec(flow_payload: str, owner: str) -> FlowSpec:
    data = json.loads(flow_payload)
    if "owner" not in data:
        data["owner"] = owner
    return FlowSpec.model_validate(data)


def _build_flow_middleware(config: FlowMiddlewareConfig, run_mode: str) -> list[Any]:
    middleware: list[Any] = []

    try:
        from langchain.agents.middleware import (
            ModelCallLimitMiddleware,
            ToolCallLimitMiddleware,
            ToolRetryMiddleware,
            ModelRetryMiddleware,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "LangChain middleware could not be imported. Ensure langchain>=1.0 is installed."
        ) from exc

    model_call_limit = config.model_call_limit
    tool_call_limit = config.tool_call_limit

    if model_call_limit is None:
        model_call_limit = 10
    if tool_call_limit is None:
        tool_call_limit = 10

    if model_call_limit > 10:
        logger.warning(f"Flow model_call_limit capped to 10 (requested {model_call_limit})")
        model_call_limit = 10
    if tool_call_limit > 10:
        logger.warning(f"Flow tool_call_limit capped to 10 (requested {tool_call_limit})")
        tool_call_limit = 10

    if model_call_limit and model_call_limit > 0:
        middleware.append(ModelCallLimitMiddleware(run_limit=model_call_limit))

    if tool_call_limit and tool_call_limit > 0:
        middleware.append(ToolCallLimitMiddleware(run_limit=tool_call_limit))

    if config.tool_retry_enabled:
        middleware.append(ToolRetryMiddleware())

    if config.model_retry_enabled:
        middleware.append(ModelRetryMiddleware())

    if run_mode == "emulated":
        try:
            from langchain.agents.middleware import LLMToolEmulator

            emulator = None
            try:
                emulator = LLMToolEmulator(tools=config.tool_emulator_tools or None)
            except Exception:
                emulator = LLMToolEmulator()

            middleware.append(emulator)
        except Exception as exc:
            logger.warning(f"LLMToolEmulator unavailable; skipping: {exc}")

    return middleware


def _build_prompt(
    system_prompt: str,
    previous_output: dict[str, Any] | None,
    input_payload: dict[str, Any] | None,
) -> str:
    prompt = system_prompt
    if input_payload is not None:
        prompt = prompt.replace(
            "$flow_input",
            json.dumps(input_payload, indent=2, ensure_ascii=False),
        )
    if previous_output is not None:
        prompt = prompt.replace(
            "$previous_output",
            json.dumps(previous_output, indent=2, ensure_ascii=False),
        )
    return prompt




async def _resolve_agents(owner: str, agent_ids: list[str]) -> list[AgentSpec]:
    registry = get_agent_registry(owner)
    agents: list[AgentSpec] = []
    for agent_id in agent_ids:
        record = registry.get_agent(agent_id)
        if not record:
            raise ValueError(f"Agent '{agent_id}' not found")
        if len(record.tools) > 10:
            raise ValueError(f"Agent '{agent_id}' uses {len(record.tools)} tools (max 10)")
        agents.append(
            AgentSpec(
                agent_id=record.agent_id,
                name=record.name,
                description=record.description,
                tools=record.tools,
                system_prompt=record.system_prompt,
                output_schema={},
            )
        )
    return agents


def _extract_structured_output(content: str, schema: dict) -> dict:
    if not schema:
        return {"raw": content}

    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            payload = content[start : end + 1]
            return json.loads(payload)
    except Exception:
        pass

    raise ValueError("Agent output did not contain valid JSON payload")


def _extract_result_content(result: Any) -> str:
    if result is None:
        return ""

    content = getattr(result, "content", None)
    if content:
        return content

    messages = None
    if isinstance(result, dict):
        messages = result.get("messages")
    else:
        messages = getattr(result, "messages", None)

    if messages:
        for msg in reversed(messages):
            msg_content = getattr(msg, "content", None)
            if msg_content:
                return msg_content

    return content or ""


async def _run_agent(
    agent_spec: AgentSpec,
    previous_output: dict[str, Any] | None,
    input_payload: dict[str, Any] | None,
    run_mode: str,
    middleware_config: FlowMiddlewareConfig,
    flow_run_id: str | None = None,
    agent_index: int | None = None,
) -> dict:
    tool_list = ",".join(agent_spec.tools)
    flow_input_size = len(json.dumps(input_payload, ensure_ascii=False)) if input_payload is not None else 0
    prev_output_size = len(json.dumps(previous_output, ensure_ascii=False)) if previous_output is not None else 0

    effective_model = "fast"

    logger.info(
        "Flow agent start: run_id=%s agent_index=%s agent_id=%s model=%s tools=%s tool_count=%s run_mode=%s has_flow_input=%s has_previous_output=%s flow_input_size=%s prev_output_size=%s",
        flow_run_id,
        agent_index,
        agent_spec.agent_id,
        effective_model,
        tool_list,
        len(agent_spec.tools),
        run_mode,
        bool(input_payload),
        bool(previous_output),
        flow_input_size,
        prev_output_size,
    )
    model = create_model(model=effective_model)
    tools = await get_tools_by_name([name for name in agent_spec.tools if name not in FLOW_TOOL_NAMES])

    prompt = _build_prompt(agent_spec.system_prompt, previous_output, input_payload)

    if tools:
        try:
            model = model.bind_tools(tools, tool_choice="required")
        except Exception:
            model = model.bind_tools(tools)

    logger.info(
        "Flow agent prompt markers: run_id=%s agent_id=%s uses_flow_input=%s uses_previous_output=%s prompt_len=%s",
        flow_run_id,
        agent_spec.agent_id,
        "$flow_input" in agent_spec.system_prompt,
        "$previous_output" in agent_spec.system_prompt,
        len(prompt),
    )

    try:
        from langchain.agents import create_agent
    except Exception as exc:
        raise RuntimeError(
            "LangChain create_agent is required. Ensure langchain>=1.0 is installed."
        ) from exc

    middleware = _build_flow_middleware(middleware_config, run_mode)

    if agent_spec.output_schema:
        try:
            model = model.with_structured_output(agent_spec.output_schema)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "Flow structured output unsupported: agent_id=%s error=%s",
                agent_spec.agent_id,
                exc,
            )

    agent_runner = create_agent(
        model=model,
        tools=tools,
        system_prompt=prompt,
        middleware=middleware,
        state_schema=ExecutiveAssistantAgentState,
    )

    result = await agent_runner.ainvoke({"messages": [HumanMessage(content="Execute your task.")]})
    content = _extract_result_content(result)
    tool_message_count = 0
    messages = None
    if isinstance(result, dict):
        messages = result.get("messages")
    else:
        messages = getattr(result, "messages", None)
    if messages:
        tool_message_count = sum(1 for msg in messages if msg.__class__.__name__ == "ToolMessage")

    logger.info(
        "Flow agent output: run_id=%s agent_id=%s chars=%s tool_messages=%s preview=\"%s\"",
        flow_run_id,
        agent_spec.agent_id,
        len(content),
        tool_message_count,
        _preview_text(content),
    )
    output = _extract_structured_output(content, agent_spec.output_schema)
    logger.info(
        "Flow agent complete: run_id=%s agent_id=%s output_keys=%s",
        flow_run_id,
        agent_spec.agent_id,
        ",".join(output.keys()),
    )
    return output


async def execute_flow(flow: ScheduledFlow) -> dict:
    storage = await get_scheduled_flow_storage()
    thread_id = flow.thread_id
    owner = sanitize_thread_id_to_user_id(thread_id)

    try:
        flow_spec = _parse_flow_spec(flow.flow, owner)
    except Exception as exc:
        await storage.mark_failed(flow.id, f"Invalid flow spec: {exc}")
        raise

    set_thread_id(thread_id)
    now = datetime.now()

    try:
        flow_run_id = str(uuid.uuid4())
        logger.info(
            "Flow start: run_id=%s flow_id=%s name=%s owner=%s agents=%s schedule_type=%s",
            flow_run_id,
            flow.id,
            flow_spec.name,
            flow_spec.owner,
            ",".join(flow_spec.agent_ids),
            flow_spec.schedule_type,
        )
        await storage.mark_started(flow.id, started_at=now)
        results: list[dict[str, Any]] = []
        agents = await _resolve_agents(flow_spec.owner, flow_spec.agent_ids)
        previous_output: dict[str, Any] | None = None

        for idx, agent_spec in enumerate(agents):
            payload = flow_spec.input_payload if idx == 0 else None
            output = await _run_agent(
                agent_spec,
                previous_output,
                payload,
                flow_spec.run_mode,
                flow_spec.middleware,
                flow_run_id=flow_run_id,
                agent_index=idx,
            )
            previous_output = output
            results.append(
                {
                    "agent_id": agent_spec.agent_id,
                    "status": "success",
                    "output": output,
                }
            )

        result_payload = json.dumps({"results": results}, ensure_ascii=False)
        await storage.mark_completed(flow.id, result=result_payload, completed_at=datetime.now())

        if flow_spec.notify_on_complete:
            from executive_assistant.scheduler import send_notification

            for channel in flow_spec.notification_channels:
                await send_notification([thread_id], f"Flow completed: {flow_spec.name}", channel)

        # Handle recurring flows
        if flow_spec.cron_expression:
            next_due = parse_cron_next(flow_spec.cron_expression, datetime.now())
            await storage.create_next_instance(flow, next_due)

        logger.info("Flow completed: run_id=%s flow_id=%s name=%s", flow_run_id, flow.id, flow_spec.name)
        return {"status": "completed", "results": results}

    except Exception as exc:
        await storage.mark_failed(flow.id, str(exc), completed_at=datetime.now())
        if flow_spec.notify_on_failure:
            from executive_assistant.scheduler import send_notification

            for channel in flow_spec.notification_channels:
                await send_notification([thread_id], f"Flow failed: {flow_spec.name}", channel)
        logger.error("Flow failed: run_id=%s flow_id=%s name=%s error=%s", flow_run_id, flow.id, flow_spec.name, exc)
        raise
    finally:
        clear_thread_id()


async def run_flow_by_id(flow_id: int) -> dict:
    storage = await get_scheduled_flow_storage()
    flow = await storage.get_by_id(flow_id)
    if not flow:
        raise ValueError(f"Flow {flow_id} not found")
    return await execute_flow(flow)


def build_flow_payload(spec: FlowSpec) -> str:
    return spec.model_dump_json()
