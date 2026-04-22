"""Tests for subagent V1: WorkQueueDB, middlewares, coordinator, models.

Covers:
- WorkQueueDB CRUD (insert, status transitions, progress, instructions, cancel, queries)
- ProgressMiddleware (progress updates, doom loop detection)
- InstructionMiddleware (cancel signal, instruction injection)
- SubagentCoordinator (create, update, invoke, cancel, instruct, delete)
- AgentDef/SubagentResult models
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

os.environ.setdefault("AGENT_MODEL", "ollama:minimax-m2.5")


# -- Fixtures --


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mock_paths(tmp_dir):
    """Patch get_paths to use a temp directory."""
    from src.storage.paths import DataPaths

    mock = DataPaths(data_path=tmp_dir, user_id="test_user")
    with patch("src.storage.paths.get_paths", return_value=mock):
        with patch("src.sdk.work_queue.get_paths", return_value=mock):
            with patch("src.sdk.coordinator.get_paths", return_value=mock):
                yield mock


@pytest.fixture
async def db(mock_paths):
    from src.sdk.work_queue import WorkQueueDB

    db = WorkQueueDB("test_user")
    yield db
    await db.close()


@pytest.fixture
def agent_def():
    from src.sdk.subagent_models import AgentDef

    return AgentDef(
        name="test_agent",
        description="Test agent",
        model="ollama:minimax-m2.5",
        tools=["time_get"],
        max_llm_calls=10,
        cost_limit_usd=0.5,
        timeout_seconds=30,
    )


# -- Model Tests --


class TestAgentDef:
    def test_valid_creation(self):
        from src.sdk.subagent_models import AgentDef

        d = AgentDef(name="my-agent", description="desc")
        assert d.name == "my-agent"
        assert d.max_llm_calls == 50
        assert "subagent_create" in d.disallowed_tools

    def test_invalid_name(self):
        from src.sdk.subagent_models import AgentDef

        with pytest.raises(Exception):
            AgentDef(name="has spaces")

        with pytest.raises(Exception):
            AgentDef(name="")

    def test_custom_limits(self):
        from src.sdk.subagent_models import AgentDef

        d = AgentDef(name="a", max_llm_calls=5, cost_limit_usd=0.01, timeout_seconds=10)
        assert d.max_llm_calls == 5
        assert d.cost_limit_usd == 0.01
        assert d.timeout_seconds == 10


class TestSubagentResult:
    def test_success_result(self):
        from src.sdk.subagent_models import SubagentResult

        r = SubagentResult(name="a", task="t", success=True, output="done")
        assert r.success
        assert not r.truncated
        assert r.error is None

    def test_failure_result(self):
        from src.sdk.subagent_models import SubagentResult

        r = SubagentResult(name="a", task="t", success=False, output="", error="boom")
        assert not r.success
        assert r.error == "boom"


class TestTaskStatus:
    def test_values(self):
        from src.sdk.subagent_models import TaskStatus

        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"


# -- WorkQueueDB Tests --


class TestWorkQueueDB:
    @pytest.mark.asyncio
    async def test_insert_and_get(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "do something", agent_def)
        assert task_id

        row = await db.get_task(task_id)
        assert row is not None
        assert row["agent_name"] == "test_agent"
        assert row["task"] == "do something"
        assert row["status"] == "pending"
        assert row["user_id"] == "test_user"
        assert row["cancel_requested"] == 0

    @pytest.mark.asyncio
    async def test_set_running(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.set_running(task_id)
        assert ok
        row = await db.get_task(task_id)
        assert row["status"] == "running"

    @pytest.mark.asyncio
    async def test_set_completed(self, db, agent_def):
        from src.sdk.subagent_models import SubagentResult

        task_id = await db.insert_task("test_agent", "t", agent_def)
        await db.set_running(task_id)

        result = SubagentResult(name="test_agent", task="t", success=True, output="done", cost_usd=0.01, llm_calls=3)
        ok = await db.set_completed(task_id, result)
        assert ok

        row = await db.get_task(task_id)
        assert row["status"] == "completed"
        stored = json.loads(row["result"])
        assert stored["success"] is True
        assert stored["output"] == "done"

    @pytest.mark.asyncio
    async def test_set_failed(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.set_failed(task_id, "something broke")
        assert ok

        row = await db.get_task(task_id)
        assert row["status"] == "failed"
        assert row["error"] == "something broke"

    @pytest.mark.asyncio
    async def test_set_cancelled(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.set_cancelled(task_id)
        assert ok

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_requested"] == 1

    @pytest.mark.asyncio
    async def test_update_progress(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.update_progress(task_id, {"steps_completed": 5, "phase": "executing"})
        assert ok

        row = await db.get_task(task_id)
        progress = json.loads(row["progress"])
        assert progress["steps_completed"] == 5

    @pytest.mark.asyncio
    async def test_add_instruction(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.add_instruction(task_id, "Focus on the top 3")
        assert ok

        row = await db.get_task(task_id)
        instructions = json.loads(row["instructions"])
        assert len(instructions) == 1
        assert instructions[0]["message"] == "Focus on the top 3"

    @pytest.mark.asyncio
    async def test_multiple_instructions(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        await db.add_instruction(task_id, "First instruction")
        await db.add_instruction(task_id, "Second instruction")

        row = await db.get_task(task_id)
        instructions = json.loads(row["instructions"])
        assert len(instructions) == 2

    @pytest.mark.asyncio
    async def test_request_cancel_and_check(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        ok = await db.request_cancel(task_id)
        assert ok

        assert await db.is_cancel_requested(task_id)

    @pytest.mark.asyncio
    async def test_is_cancel_requested_nonexistent(self, db):
        assert not await db.is_cancel_requested("nonexistent")

    @pytest.mark.asyncio
    async def test_check_progress_by_parent(self, db, agent_def):
        t1 = await db.insert_task("test_agent", "task1", agent_def, parent_id="parent-1")
        t2 = await db.insert_task("test_agent", "task2", agent_def, parent_id="parent-1")
        t3 = await db.insert_task("test_agent", "task3", agent_def, parent_id="parent-2")

        tasks = await db.check_progress(parent_id="parent-1")
        assert len(tasks) == 2
        ids = {t["id"] for t in tasks}
        assert t1 in ids
        assert t2 in ids
        assert t3 not in ids

    @pytest.mark.asyncio
    async def test_check_progress_by_status(self, db, agent_def):
        from src.sdk.subagent_models import TaskStatus

        t1 = await db.insert_task("test_agent", "task1", agent_def)
        await db.set_running(t1)
        await db.insert_task("test_agent", "task2", agent_def)

        running = await db.check_progress(status=TaskStatus.RUNNING)
        assert len(running) == 1
        assert running[0]["id"] == t1

    @pytest.mark.asyncio
    async def test_get_result(self, db, agent_def):
        from src.sdk.subagent_models import SubagentResult

        task_id = await db.insert_task("test_agent", "t", agent_def)
        result = SubagentResult(name="test_agent", task="t", success=True, output="hello")
        await db.set_completed(task_id, result)

        stored = await db.get_result(task_id)
        assert stored is not None
        assert stored.success
        assert stored.output == "hello"

    @pytest.mark.asyncio
    async def test_get_result_nonexistent(self, db):
        result = await db.get_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_config_frozen(self, db, agent_def):
        task_id = await db.insert_task("test_agent", "t", agent_def)
        row = await db.get_task(task_id)
        config_data = json.loads(row["config"])
        assert config_data["name"] == "test_agent"
        assert config_data["max_llm_calls"] == 10


# -- ProgressMiddleware Tests --


class TestProgressMiddleware:
    @pytest.mark.asyncio
    async def test_updates_progress_on_tool_result(self, db, agent_def):
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", agent_def)

        mw = ProgressMiddleware(task_id, db)
        state = AgentState(messages=[
            Message.user("do it"),
            Message.assistant(content=""),
            Message.tool_result(tool_call_id="tc1", content="result", name="time_get"),
        ])

        await mw.abefore_model(state)

        row = await db.get_task(task_id)
        progress = json.loads(row["progress"])
        assert progress["steps_completed"] == 1
        assert progress["phase"] == "executing"
        assert "time_get" in progress["message"]

    @pytest.mark.asyncio
    async def test_no_update_without_tool_results(self, db, agent_def):
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", agent_def)

        mw = ProgressMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("hello")])

        result = await mw.abefore_model(state)
        assert result is None

        row = await db.get_task(task_id)
        progress = json.loads(row["progress"])
        assert progress == {}


# -- InstructionMiddleware Tests --


class TestInstructionMiddleware:
    @pytest.mark.asyncio
    async def test_injects_instructions(self, db, agent_def):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", agent_def)
        await db.add_instruction(task_id, "Focus on the top 3")

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("do it")])

        await mw.abefore_model(state)

        system_msgs = [m for m in state.messages if m.role == "system"]
        assert len(system_msgs) == 1
        assert "[Supervisor Update]" in system_msgs[0].content
        assert "Focus on the top 3" in system_msgs[0].content

    @pytest.mark.asyncio
    async def test_raises_on_cancel(self, db, agent_def):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState
        from src.sdk.subagent_models import TaskCancelledError

        task_id = await db.insert_task("test_agent", "t", agent_def)
        await db.request_cancel(task_id)

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("do it")])

        with pytest.raises(TaskCancelledError):
            await mw.abefore_model(state)

    @pytest.mark.asyncio
    async def test_no_injection_without_instructions(self, db, agent_def):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", agent_def)

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("hello")])

        result = await mw.abefore_model(state)
        assert result is None
        system_msgs = [m for m in state.messages if m.role == "system"]
        assert len(system_msgs) == 0


# -- Coordinator Tests --


class TestSubagentCoordinator:
    @pytest.mark.asyncio
    async def test_create_and_load(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        agent_def = AgentDef(name="researcher", description="Web researcher", model="ollama:minimax-m2.5")
        await coord.create(agent_def)

        loaded = coord.load_def("researcher")
        assert loaded is not None
        assert loaded.name == "researcher"
        assert loaded.description == "Web researcher"

    @pytest.mark.asyncio
    async def test_create_persists_yaml(self, mock_paths):
        import yaml

        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        agent_def = AgentDef(name="writer", description="Report writer", tools=["time_get"])
        await coord.create(agent_def)

        config_path = mock_paths.subagents_dir() / "writer" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text())
        assert data["name"] == "writer"
        assert data["tools"] == ["time_get"]

    @pytest.mark.asyncio
    async def test_update(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        agent_def = AgentDef(name="updater", description="Original", max_llm_calls=10)
        await coord.create(agent_def)

        updated = await coord.update("updater", description="Updated", max_llm_calls=20)
        assert updated is not None
        assert updated.description == "Updated"
        assert updated.max_llm_calls == 20

        loaded = coord.load_def("updater")
        assert loaded.description == "Updated"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        result = await coord.update("ghost", description="nope")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_defs(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentDef(name="a1", description="Agent 1"))
        await coord.create(AgentDef(name="a2", description="Agent 2"))

        defs = await coord.list_defs()
        names = {d.name for d in defs}
        assert "a1" in names
        assert "a2" in names

    @pytest.mark.asyncio
    async def test_delete(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentDef(name="deleteme", description="Temporary"))
        assert coord.load_def("deleteme") is not None

        ok = await coord.delete("deleteme")
        assert ok
        assert coord.load_def("deleteme") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        ok = await coord.delete("ghost")
        assert not ok

    @pytest.mark.asyncio
    async def test_cancel_and_instruct(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentDef(name="canceller", description="Test"))

        db = await coord._get_db()
        task_id = await db.insert_task("canceller", "task", coord.load_def("canceller"))
        await db.set_running(task_id)

        ok = await coord.cancel(task_id)
        assert ok
        assert await db.is_cancel_requested(task_id)

        task_id2 = await db.insert_task("canceller", "task2", coord.load_def("canceller"))
        await db.set_running(task_id2)
        ok = await coord.instruct(task_id2, "Change focus")
        assert ok

        row = await db.get_task(task_id2)
        instructions = json.loads(row["instructions"])
        assert len(instructions) == 1
        assert instructions[0]["message"] == "Change focus"

    @pytest.mark.asyncio
    async def test_check_progress(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentDef(name="progressor", description="Test"))

        db = await coord._get_db()
        await db.insert_task("progressor", "task1", coord.load_def("progressor"), parent_id="p1")
        await db.insert_task("progressor", "task2", coord.load_def("progressor"), parent_id="p1")

        tasks = await coord.check_progress(parent_id="p1")
        assert len(tasks) == 2


# -- Integration: Full lifecycle --


class TestSubagentLifecycle:
    @pytest.mark.asyncio
    async def test_config_frozen_at_invoke(self, mock_paths):
        """Verify that config is frozen into work_queue when task is inserted,
        even if AgentDef is updated afterwards."""
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef

        coord = SubagentCoordinator("test_user")
        original = AgentDef(name="freeze_test", description="Original", max_llm_calls=10)
        await coord.create(original)

        db = await coord._get_db()
        task_id = await db.insert_task("freeze_test", "task", original)
        row = await db.get_task(task_id)
        frozen = json.loads(row["config"])
        assert frozen["max_llm_calls"] == 10

        await coord.update("freeze_test", max_llm_calls=50)
        row = await db.get_task(task_id)
        frozen = json.loads(row["config"])
        assert frozen["max_llm_calls"] == 10

    @pytest.mark.asyncio
    async def test_doom_loop_detection(self, db, agent_def):
        """Simulate doom loop detection in ProgressMiddleware."""
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", agent_def)

        mw = ProgressMiddleware(task_id, db)

        for i in range(4):
            state = AgentState(messages=[
                Message.user("do it"),
                Message.assistant(content=""),
                Message.tool_result(tool_call_id=f"tc{i}", content='{"args": "same"}', name="time_get"),
            ])
            await mw.abefore_model(state)

        row = await db.get_task(task_id)
        progress = json.loads(row["progress"])
        assert progress.get("stuck") is True

        instructions = json.loads(row["instructions"])
        assert len(instructions) > 0
        assert "Doom loop" in instructions[0]["message"]

    @pytest.mark.asyncio
    async def test_cancel_then_check_status(self, db, agent_def):
        """Full cancel flow: insert -> cancel_requested -> set_cancelled."""
        task_id = await db.insert_task("test_agent", "t", agent_def)
        await db.set_running(task_id)

        await db.request_cancel(task_id)
        assert await db.is_cancel_requested(task_id)

        await db.set_cancelled(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
