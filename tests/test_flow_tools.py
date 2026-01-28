"""Unit tests for flow tools."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from executive_assistant.tools import flow_tools
from executive_assistant.storage.agent_registry import AgentRegistry


class _DummyFlow:
    def __init__(self, flow_id=1, name="flow", due_time=None, status="pending"):
        self.id = flow_id
        self.name = name
        self.due_time = due_time or datetime.now()
        self.status = status


@pytest.mark.asyncio
async def test_flow_tools_create_list_delete(monkeypatch, tmp_path):
    # Setup registry path
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    # Setup thread id
    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(flow_tools, "get_thread_id", _fake_thread_id)

    # Create agent in registry
    registry = AgentRegistry("telegram:123")
    registry.create_agent(
        agent_id="a1",
        name="Agent One",
        description="test",
        tools=["execute_python"],
        system_prompt="use $input.url",
    )

    # Mock storage
    class _Store:
        async def create(self, **kwargs):
            return _DummyFlow(flow_id=1, name=kwargs.get("name"), due_time=kwargs.get("due_time"))

        async def list_by_thread(self, *args, **kwargs):
            return [_DummyFlow(flow_id=1, name="flow", due_time=datetime.now(), status="pending")]

        async def cancel(self, flow_id):
            return flow_id == 1

        async def delete(self, flow_id):
            return flow_id == 1

    async def _fake_storage():
        return _Store()

    monkeypatch.setattr(flow_tools, "get_scheduled_flow_storage", _fake_storage)

    # Create flow (immediate)
    res = await flow_tools.create_flow.ainvoke({"name":"flow","description":"flow","agent_ids":["a1"],"schedule_type":"immediate","flow_input":{"url":"https://example.com"}})
    assert "Flow created" in res

    listing = await flow_tools.list_flows.ainvoke({})
    assert "flow" in listing

    cancel = await flow_tools.cancel_flow.ainvoke({"flow_id": 1})
    assert "cancelled" in cancel

    delete = await flow_tools.delete_flow.ainvoke({"flow_id": 1})
    assert "deleted" in delete


@pytest.mark.asyncio
async def test_flow_tools_flow_input_required(monkeypatch, tmp_path):
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(flow_tools, "get_thread_id", _fake_thread_id)

    registry = AgentRegistry("telegram:123")
    registry.create_agent(
        agent_id="a1",
        name="Agent One",
        description="test",
        tools=["execute_python"],
        system_prompt="use $input.url",
    )

    res = await flow_tools.create_flow.ainvoke({"name":"flow","description":"flow","agent_ids":["a1"],"schedule_type":"immediate","flow_input":None})
    assert "flow_input" in res


@pytest.mark.asyncio
async def test_flow_tools_cron_guard(monkeypatch, tmp_path):
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(flow_tools, "get_thread_id", _fake_thread_id)

    registry = AgentRegistry("telegram:123")
    registry.create_agent(
        agent_id="a1",
        name="Agent One",
        description="test",
        tools=["execute_python"],
        system_prompt="use $input.url",
    )

    res = await flow_tools.create_flow.ainvoke({"name":"flow","description":"flow","agent_ids":["a1"],"schedule_type":"recurring","cron_expression":"* * * * *","flow_input":{"url":"https://example.com"}})
    assert "cron '* * * * *' is not allowed" in res
