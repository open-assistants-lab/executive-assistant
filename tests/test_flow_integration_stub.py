"""Integration-style tests for flow execution."""

from __future__ import annotations

import json

import pytest

from executive_assistant.flows import runner


@pytest.mark.asyncio
async def test_execute_flow_persists_results(monkeypatch):
    calls = []

    async def _fake_run_agent(agent_spec, previous_output, flow_input, run_mode, middleware_config, **kwargs):
        calls.append((agent_spec.agent_id, flow_input, previous_output))
        return {"raw": f"out-{agent_spec.agent_id}"}

    class _Store:
        def __init__(self):
            self.started = False
            self.completed = None
            self.failed = None
            self.next_created = None

        async def mark_started(self, *args, **kwargs):
            self.started = True

        async def mark_completed(self, flow_id, result=None, completed_at=None):
            self.completed = (flow_id, result, completed_at)

        async def mark_failed(self, *args, **kwargs):
            self.failed = (args, kwargs)

        async def create_next_instance(self, flow, next_due):
            self.next_created = (flow.id, next_due)

    store = _Store()

    async def _fake_storage():
        return store

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

    monkeypatch.setattr(runner, "get_scheduled_flow_storage", _fake_storage)
    monkeypatch.setattr(runner, "_resolve_agents", _fake_resolve)
    monkeypatch.setattr(runner, "_run_agent", _fake_run_agent)

    flow_spec = runner.FlowSpec(
        flow_id="f1",
        name="flow",
        description="flow",
        owner="anon",
        agent_ids=["a1", "a2"],
        schedule_type="immediate",
        notify_on_complete=False,
        notify_on_failure=False,
        flow_input={"hello": "world"},
    )

    flow = runner.ScheduledFlow(
        id=1,
        thread_id="telegram:1",
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

    result = await runner.execute_flow(flow)

    assert store.started is True
    assert store.completed is not None
    assert result["status"] == "completed"
    assert calls[0][1] == {"hello": "world"}
    assert calls[1][1] is None

    payload = json.loads(store.completed[1])
    assert payload["results"][0]["output"]["raw"] == "out-a1"
    assert payload["results"][1]["output"]["raw"] == "out-a2"


@pytest.mark.asyncio
async def test_execute_flow_creates_next_instance(monkeypatch):
    async def _fake_run_agent(agent_spec, previous_output, flow_input, run_mode, middleware_config, **kwargs):
        return {"raw": "ok"}

    class _Store:
        def __init__(self):
            self.next_created = None

        async def mark_started(self, *args, **kwargs):
            return None

        async def mark_completed(self, *args, **kwargs):
            return None

        async def mark_failed(self, *args, **kwargs):
            return None

        async def create_next_instance(self, flow, next_due):
            self.next_created = (flow.id, next_due)

    store = _Store()

    async def _fake_storage():
        return store

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
        ]

    monkeypatch.setattr(runner, "get_scheduled_flow_storage", _fake_storage)
    monkeypatch.setattr(runner, "_resolve_agents", _fake_resolve)
    monkeypatch.setattr(runner, "_run_agent", _fake_run_agent)

    flow_spec = runner.FlowSpec(
        flow_id="f2",
        name="flow",
        description="flow",
        owner="anon",
        agent_ids=["a1"],
        schedule_type="recurring",
        cron_expression="0 9 * * *",
        notify_on_complete=False,
        notify_on_failure=False,
        flow_input={"hello": "world"},
    )

    flow = runner.ScheduledFlow(
        id=2,
        thread_id="telegram:1",
        name="flow",
        task="flow",
        flow=flow_spec.model_dump_json(),
        due_time=runner.datetime.now(),
        status="pending",
        cron="0 9 * * *",
        created_at=runner.datetime.now(),
        started_at=None,
        completed_at=None,
        error_message=None,
        result=None,
    )

    await runner.execute_flow(flow)

    assert store.next_created is not None
    assert store.next_created[0] == 2
