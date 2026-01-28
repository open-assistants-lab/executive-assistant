"""Unit tests for agent tools."""

from __future__ import annotations

import json

import pytest

from executive_assistant.tools import agent_tools
from executive_assistant.storage.agent_registry import AgentRegistry


@pytest.mark.asyncio
async def test_agent_tools_crud(monkeypatch, tmp_path):
    # Force registry path to temp
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(agent_tools, "get_thread_id", _fake_thread_id)

    # create
    result = await agent_tools.create_agent.ainvoke({"agent_id":"a1","name":"Agent One","description":"test","tools":["execute_python"],"system_prompt":"Do the thing","output_schema":{"ok": True}})
    assert "created" in result

    # list
    listing = await agent_tools.list_agents.ainvoke({})
    assert "a1" in listing

    # get
    detail = await agent_tools.get_agent.ainvoke({"agent_id": "a1"})
    assert "Agent a1" in detail

    # update
    result = await agent_tools.update_agent.ainvoke({"agent_id":"a1","name":"Agent One Updated","tools":["execute_python"],"system_prompt":"Updated"})
    assert "updated" in result

    detail = await agent_tools.get_agent.ainvoke({"agent_id": "a1"})
    assert "Agent One Updated" in detail

    # delete
    result = await agent_tools.delete_agent.ainvoke({"agent_id": "a1"})
    assert "deleted" in result

    detail = await agent_tools.get_agent.ainvoke({"agent_id": "a1"})
    assert "not found" in detail


@pytest.mark.asyncio
async def test_agent_tools_rejects_too_many_tools(monkeypatch, tmp_path):
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(agent_tools, "get_thread_id", _fake_thread_id)

    tools = [f"tool_{i}" for i in range(11)]
    result = await agent_tools.create_agent.ainvoke({"agent_id":"too_many","name":"TooMany","description":"test","tools":tools,"system_prompt":"x"})
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_agent_tool(monkeypatch, tmp_path):
    from executive_assistant.storage import agent_registry as registry_mod

    monkeypatch.setattr(registry_mod.settings, "USERS_ROOT", tmp_path)

    def _fake_thread_id():
        return "telegram:123"

    monkeypatch.setattr(agent_tools, "get_thread_id", _fake_thread_id)

    # create agent
    await agent_tools.create_agent.ainvoke({
        "agent_id": "a1",
        "name": "Agent One",
        "description": "test",
        "tools": ["execute_python"],
        "system_prompt": "Use $input then $output",
        "output_schema": {},
    })

    async def _fake_run_agent(*args, **kwargs):
        return {"raw": "ok"}

    from executive_assistant.flows import runner
    monkeypatch.setattr(runner, "_run_agent", _fake_run_agent)

    result = await agent_tools.run_agent.ainvoke({
        "agent_id": "a1",
        "flow_input": {"url": "https://example.com"},
        "previous_output": {"x": 1},
    })
    assert "ok" in result
