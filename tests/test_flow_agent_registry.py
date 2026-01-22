"""Tests for agent registry + flow tooling integration."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from executive_assistant.config.settings import settings
from executive_assistant.flows.runner import _build_prompt, _resolve_agents
from executive_assistant.storage.agent_registry import get_agent_registry
from executive_assistant.storage.file_sandbox import clear_thread_id, set_thread_id
from executive_assistant.tools import flow_tools


class _DummyFlow:
    def __init__(self, flow_id: int) -> None:
        self.id = flow_id


class _DummyStorage:
    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        return _DummyFlow(123)


@pytest.fixture(autouse=True)
def _use_tmp_users_root(tmp_path, monkeypatch):
    users_root = tmp_path / "users"
    users_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "USERS_ROOT", users_root, raising=False)
    yield


def _create_agent(user_id: str, agent_id: str, tools: list[str]):
    registry = get_agent_registry(user_id)
    msg = registry.create_agent(
        agent_id=agent_id,
        name=agent_id,
        description="test",
        model="gpt-oss:20b",
        tools=tools,
        system_prompt="Do the thing",
    )
    return msg, registry


def test_agent_registry_crud(tmp_path):
    user_id = "anon_test_user"
    msg, registry = _create_agent(user_id, "agent_one", ["read_file"])
    assert "created" in msg.lower()

    agents = registry.list_agents()
    assert len(agents) == 1
    assert agents[0].agent_id == "agent_one"

    record = registry.get_agent("agent_one")
    assert record is not None
    assert record.model == "gpt-oss:20b"

    update_msg = registry.update_agent("agent_one", description="updated")
    assert "updated" in update_msg.lower()
    assert registry.get_agent("agent_one").description == "updated"

    delete_msg = registry.delete_agent("agent_one")
    assert "deleted" in delete_msg.lower()
    assert registry.get_agent("agent_one") is None


def test_agent_registry_tool_limits():
    user_id = "anon_limits"
    tools = [f"tool_{i}" for i in range(6)]
    msg, registry = _create_agent(user_id, "warn_agent", tools)
    assert "warning" in msg.lower()

    too_many = [f"tool_{i}" for i in range(11)]
    msg = registry.create_agent(
        agent_id="bad_agent",
        name="bad_agent",
        description="bad",
        model="gpt-oss:20b",
        tools=too_many,
        system_prompt="",
    )
    assert "exceeds hard limit" in msg.lower()


@pytest.mark.asyncio
async def test_flow_create_validations(monkeypatch):
    set_thread_id("telegram:123")
    user_id = "anon_telegram_123"

    _, registry = _create_agent(user_id, "flow_agent", ["read_file"])

    async def _dummy_storage():
        return _DummyStorage()

    monkeypatch.setattr(flow_tools, "get_scheduled_flow_storage", _dummy_storage)

    # Missing agent_ids
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": [],
            "input_payload": {"x": 1},
        }
    )
    assert "requires at least one agent_id" in msg

    # Missing agent
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": ["missing"],
            "input_payload": {"x": 1},
        }
    )
    assert "not found" in msg

    # Forbidden tools
    registry.update_agent("flow_agent", tools=["create_flow"])
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": ["flow_agent"],
            "input_payload": {"x": 1},
        }
    )
    assert "may not use flow management tools" in msg

    # Middleware cap
    registry.update_agent("flow_agent", tools=["read_file"])
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": ["flow_agent"],
            "input_payload": {"x": 1},
            "middleware": {"model_call_limit": 11},
        }
    )
    assert "model_call_limit" in msg.lower()

    # Warning when agent uses >5 tools
    registry.update_agent("flow_agent", tools=[f"tool_{i}" for i in range(6)])
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": ["flow_agent"],
            "input_payload": {"x": 1},
        }
    )
    assert "Warnings" in msg
    assert "first agent prompt does not reference $flow_input" in msg

    # Missing input_payload
    msg = await flow_tools.create_flow.ainvoke(
        {
            "name": "f",
            "description": "d",
            "agent_ids": ["flow_agent"],
        }
    )
    assert "input_payload is required" in msg

    clear_thread_id()


@pytest.mark.asyncio
async def test_resolve_agents_and_prompt():
    user_id = "anon_resolve"
    msg, registry = _create_agent(user_id, "ok_agent", ["read_file"])
    assert "created" in msg.lower()

    agents = await _resolve_agents(user_id, ["ok_agent"])
    assert len(agents) == 1
    assert agents[0].agent_id == "ok_agent"

    # Insert a bad agent directly to test resolve validation (>10 tools)
    db_path = Path(settings.USERS_ROOT / user_id / "agents" / "agents.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agents (agent_id, name, description, model, tools, system_prompt, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                "too_many",
                "too_many",
                "bad",
                "gpt-oss:20b",
                json.dumps([f"tool_{i}" for i in range(11)]),
                "",
            ),
        )

    with pytest.raises(ValueError):
        await _resolve_agents(user_id, ["too_many"])

    prompt = _build_prompt("Hello $previous_output", {"a": 1}, None)
    assert "\"a\": 1" in prompt

    prompt = _build_prompt("Input $flow_input", None, {"url": "https://example.com"})
    assert "https://example.com" in prompt
