"""Tests for flow runner agent execution harness."""

from __future__ import annotations

import json
import types
import sys

import pytest

from executive_assistant.flows import runner
from executive_assistant.flows.spec import AgentSpec, FlowMiddlewareConfig


class _DummyModel:
    def with_structured_output(self, schema):
        return self


class _DummyAgent:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, payload):
        return types.SimpleNamespace(content=self._content)


def _install_fake_create_agent(monkeypatch, content: str, captured: dict):
    import langchain.agents as lc_agents

    def _fake_create_agent(model, tools, system_prompt, middleware, state_schema):
        captured["prompt"] = system_prompt
        captured["tools"] = tools
        captured["middleware"] = middleware
        return _DummyAgent(content)

    monkeypatch.setattr(lc_agents, "create_agent", _fake_create_agent)


@pytest.mark.asyncio
async def test_run_agent_injects_payload_and_previous_output(monkeypatch):
    captured: dict = {}

    async def _fake_get_tools(names):
        return [f"tool:{name}" for name in names]

    monkeypatch.setattr(runner, "create_model", lambda model=None: _DummyModel())
    monkeypatch.setattr(runner, "get_tools_by_name", _fake_get_tools)

    _install_fake_create_agent(monkeypatch, "hello", captured)

    agent = AgentSpec(
        agent_id="a1",
        name="a1",
        description="test",
        tools=["execute_python"],
        system_prompt="Use $flow_input then $previous_output",
        output_schema={},
    )

    output = await runner._run_agent(
        agent,
        previous_output={"key": "value"},
        input_payload={"url": "https://example.com"},
        run_mode="normal",
        middleware_config=FlowMiddlewareConfig(),
    )

    assert output == {"raw": "hello"}
    assert "https://example.com" in captured["prompt"]
    assert "key" in captured["prompt"]


@pytest.mark.asyncio
async def test_run_agent_structured_output(monkeypatch):
    captured: dict = {}

    async def _fake_get_tools(names):
        return []

    monkeypatch.setattr(runner, "create_model", lambda model=None: _DummyModel())
    monkeypatch.setattr(runner, "get_tools_by_name", _fake_get_tools)

    payload = {"title": "Invoice", "total": 123.45}
    _install_fake_create_agent(monkeypatch, json.dumps(payload), captured)

    agent = AgentSpec(
        agent_id="a2",
        name="a2",
        description="test",
        tools=[],
        system_prompt="Return JSON",
        output_schema={"title": "string", "total": "number"},
    )

    output = await runner._run_agent(
        agent,
        previous_output=None,
        input_payload=None,
        run_mode="normal",
        middleware_config=FlowMiddlewareConfig(),
    )

    assert output == payload





def test_build_flow_middleware_caps_limits(monkeypatch):
    middleware = runner._build_flow_middleware(
        FlowMiddlewareConfig(model_call_limit=99, tool_call_limit=99),
        run_mode="normal",
    )
    assert any(getattr(item, "run_limit", None) == 10 for item in middleware)


def test_build_flow_middleware_emulated_includes_emulator(monkeypatch):
    import langchain.agents.middleware as mw

    class _DummyEmulator:
        def __init__(self, tools=None):
            self.tools = tools

    monkeypatch.setattr(mw, "LLMToolEmulator", _DummyEmulator)

    middleware = runner._build_flow_middleware(
        FlowMiddlewareConfig(tool_emulator_tools=["execute_python"]),
        run_mode="emulated",
    )
    assert any(isinstance(item, _DummyEmulator) for item in middleware)
@pytest.mark.asyncio
async def test_run_agent_prefers_tool_message_output(monkeypatch):
    captured: dict = {}

    async def _fake_get_tools(names):
        return []

    monkeypatch.setattr(runner, "create_model", lambda model=None: _DummyModel())
    monkeypatch.setattr(runner, "get_tools_by_name", _fake_get_tools)

    from langchain_core.messages import AIMessage, ToolMessage

    messages = [
        AIMessage(content=""),
        ToolMessage(content="tool output", tool_call_id="call-1"),
    ]

    async def _ainvoke(_payload):
        return {"messages": messages}

    class _Agent:
        async def ainvoke(self, payload):
            return await _ainvoke(payload)

    def _fake_create_agent(model, tools, system_prompt, middleware, state_schema):
        captured["prompt"] = system_prompt
        return _Agent()

    import langchain.agents as lc_agents

    monkeypatch.setattr(lc_agents, "create_agent", _fake_create_agent)

    agent = AgentSpec(
        agent_id="a3",
        name="a3",
        description="test",
        tools=[],
        system_prompt="Return tool output",
        output_schema={},
    )

    output = await runner._run_agent(
        agent,
        previous_output=None,
        input_payload=None,
        run_mode="normal",
        middleware_config=FlowMiddlewareConfig(),
    )

    assert output == {"raw": "tool output"}


@pytest.mark.asyncio
async def test_run_agent_structured_output_invalid(monkeypatch):
    captured: dict = {}

    async def _fake_get_tools(names):
        return []

    monkeypatch.setattr(runner, "create_model", lambda model=None: _DummyModel())
    monkeypatch.setattr(runner, "get_tools_by_name", _fake_get_tools)

    _install_fake_create_agent(monkeypatch, "not-json", captured)

    agent = AgentSpec(
        agent_id="a4",
        name="a4",
        description="test",
        tools=[],
        system_prompt="Return JSON",
        output_schema={"title": "string"},
    )

    with pytest.raises(ValueError):
        await runner._run_agent(
            agent,
            previous_output=None,
            input_payload=None,
            run_mode="normal",
            middleware_config=FlowMiddlewareConfig(),
        )

@pytest.mark.asyncio
async def test_execute_flow_passes_input_payload_once(monkeypatch):
    calls = []

    async def _fake_run_agent(agent_spec, previous_output, input_payload, run_mode, middleware_config, **kwargs):
        calls.append((agent_spec.agent_id, input_payload, previous_output))
        return {"raw": agent_spec.agent_id}

    async def _fake_storage():
        raise AssertionError("storage not expected")

    async def _fake_get_by_id(flow_id):
        raise AssertionError("storage not expected")

    monkeypatch.setattr(runner, "_run_agent", _fake_run_agent)

    flow_spec = runner.FlowSpec(
        flow_id="f1",
        name="flow",
        description="flow",
        owner="anon",
        agent_ids=["a1", "a2"],
        schedule_type="immediate",
        input_payload={"hello": "world"},
    )

    flow = runner.ScheduledFlow(
        id=1,
        user_id="anon",
        thread_id="telegram:1",
        worker_id=None,
        name="flow",
        task="flow",
        flow=flow_spec.model_dump_json(),
        due_time=runner.datetime.now(),
        status="pending",
        cron=None,
        created_at=runner.datetime.now(),
        started_at=None,
        completed_at=None,
        error_message=None,
        result=None,
    )

    # bypass storage by calling execute_flow directly with patched storage methods
    async def _fake_storage_obj():
        class _Store:
            async def mark_started(self, *args, **kwargs):
                return None

            async def mark_completed(self, *args, **kwargs):
                return None

            async def mark_failed(self, *args, **kwargs):
                return None

        return _Store()

    async def _fake_resolve(owner, agent_ids):
        return [
            runner.AgentSpec(
                agent_id="a1",
                name="a1",
                description="a1",
                        tools=[],
                system_prompt="",
                output_schema={},
            ),
            runner.AgentSpec(
                agent_id="a2",
                name="a2",
                description="a2",
                        tools=[],
                system_prompt="",
                output_schema={},
            ),
        ]

    monkeypatch.setattr(runner, "get_scheduled_flow_storage", _fake_storage_obj)
    monkeypatch.setattr(runner, "_resolve_agents", _fake_resolve)

    await runner.execute_flow(flow)

    assert calls[0][1] == {"hello": "world"}
    assert calls[1][1] is None
