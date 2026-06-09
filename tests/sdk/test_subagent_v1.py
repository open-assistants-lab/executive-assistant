"""Tests for subagent V1: WorkQueueDB, middlewares, coordinator, models.

Covers:
- WorkQueueDB CRUD (insert, status transitions, progress, instructions, cancel, queries)
- ProgressMiddleware (progress updates, doom loop detection)
- InstructionMiddleware (cancel signal, instruction injection)
- SubagentCoordinator (create, update, invoke, cancel, instruct, delete)
- AgentDef/SubagentResult models
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
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

    mock = DataPaths(data_path=tmp_dir, user_id="test_user", ea_root=tmp_dir)
    # Alias old user-level paths to workspace-scoped for backwards test compat
    def temp_workspace_dir(name: str):
        path = Path(tmp_dir) / "workspaces" / "personal" / name
        path.mkdir(parents=True, exist_ok=True)
        return path

        mock.workspace_subagents_dir = lambda: temp_workspace_dir("subagents")
        mock.workspace_memory_dir = lambda: temp_workspace_dir("memory")
        mock.subagents_dir = mock.workspace_subagents_dir
        mock.user_subagents_dir = mock.workspace_subagents_dir
        mock.memory_dir = mock.workspace_memory_dir
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


@pytest.fixture(autouse=True)
async def cleanup_work_queue_cache():
    yield
    from src.sdk.work_queue import _db_cache

    for cached_db in list(_db_cache.values()):
        await cached_db.close()
    _db_cache.clear()


@pytest.fixture
def profile():
    from agentprofile.models import AgentProfile

    return AgentProfile(
        name="test_agent",
        description="Test agent",
        model="ollama:minimax-m2.5",
        tools=["time_get"],
        max_llm_calls=10,
        cost_limit_usd=0.5,
        timeout_seconds=30,
    )


async def _wait_for_no_background_tasks(coordinator):
    while coordinator._background_tasks:
        await asyncio.sleep(0)


# -- Model Tests --


class TestAgentDef:
    def test_valid_creation(self):
        from agentprofile.models import AgentProfile

        d = AgentProfile(name="my-agent", description="desc")
        assert d.name == "my-agent"
        assert d.max_llm_calls == 50
        assert "subagent_create" not in (d.tools or [])  # recursion guard via capabilities
    def test_invalid_name(self):
        from agentprofile.models import AgentProfile

        with pytest.raises(Exception):
            AgentProfile(name="has spaces")

        with pytest.raises(Exception):
            AgentProfile(name="")

    def test_custom_limits(self):
        from agentprofile.models import AgentProfile

        d = AgentProfile(name="a", max_llm_calls=5, cost_limit_usd=0.01, timeout_seconds=10)
        assert d.max_llm_calls == 5
        assert d.cost_limit_usd == 0.01
        assert d.timeout_seconds == 10

    def test_agent_def_new_fields(self):
        from agentprofile.models import AgentProfile

        d = AgentProfile(
            name="researcher",
            provider_options={"anthropic": {"thinking": {"type": "enabled"}}},
            handoff_instructions="Return concise bullets.",
        )

        assert d.provider_options == {"anthropic": {"thinking": {"type": "enabled"}}}
        assert d.handoff_instructions == "Return concise bullets."


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

    def test_task_status_has_cancelling(self):
        from src.sdk.subagent_models import TaskStatus

        assert TaskStatus.CANCELLING == "cancelling"


# -- WorkQueueDB Tests --


class TestWorkQueueDB:
    @pytest.mark.asyncio
    async def test_insert_and_get(self, db, profile):
        task_id = await db.insert_task("test_agent", "do something", profile)
        assert task_id

        row = await db.get_task(task_id)
        assert row is not None
        assert row["agent_name"] == "test_agent"
        assert row["task"] == "do something"
        assert row["status"] == "pending"
        assert row["user_id"] == "test_user"
        assert row["cancel_requested"] == 0

    @pytest.mark.asyncio
    async def test_set_running(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.set_running(task_id)
        assert ok
        row = await db.get_task(task_id)
        assert row["status"] == "running"
        assert row["started_at"]
        assert row["heartbeat_at"]
        assert row["claimed_by"] is None

    @pytest.mark.asyncio
    async def test_fresh_set_running_task_not_stale_by_default(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.set_running(task_id)

        count = await db.mark_stale_running_failed()

        assert count == 0
        row = await db.get_task(task_id)
        assert row["status"] == "running"

    @pytest.mark.asyncio
    async def test_set_completed(self, db, profile):
        from src.sdk.subagent_models import SubagentResult

        task_id = await db.insert_task("test_agent", "t", profile)
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
    async def test_set_failed(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.set_failed(task_id, "something broke")
        assert ok

        row = await db.get_task(task_id)
        assert row["status"] == "failed"
        assert row["error"] == "something broke"

    @pytest.mark.asyncio
    async def test_set_cancelled(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.set_cancelled(task_id)
        assert ok

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_requested"] == 1

    @pytest.mark.asyncio
    async def test_update_progress(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.update_progress(task_id, {"steps_completed": 5, "phase": "executing"})
        assert ok

        row = await db.get_task(task_id)
        progress = json.loads(row["progress"])
        assert progress["steps_completed"] == 5

    @pytest.mark.asyncio
    async def test_add_instruction(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.add_instruction(task_id, "Focus on the top 3")
        assert ok

        row = await db.get_task(task_id)
        instructions = json.loads(row["instructions"])
        assert len(instructions) == 1
        assert instructions[0]["message"] == "Focus on the top 3"

    @pytest.mark.asyncio
    async def test_multiple_instructions(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.add_instruction(task_id, "First instruction")
        await db.add_instruction(task_id, "Second instruction")

        row = await db.get_task(task_id)
        instructions = json.loads(row["instructions"])
        assert len(instructions) == 2

    @pytest.mark.asyncio
    async def test_request_cancel_and_check(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        ok = await db.request_cancel(task_id)
        assert ok

        assert await db.is_cancel_requested(task_id)

    @pytest.mark.asyncio
    async def test_claim_pending_task_once(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)

        first = await db.claim_task(task_id, worker_id="worker-a")
        second = await db.claim_task(task_id, worker_id="worker-b")

        assert first is True
        assert second is False
        row = await db.get_task(task_id)
        assert row["status"] == "running"
        assert row["claimed_by"] == "worker-a"
        assert row["claimed_at"]
        assert row["heartbeat_at"]

    @pytest.mark.asyncio
    async def test_request_cancel_sets_cancelling_for_running_task(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.claim_task(task_id, worker_id="worker-a")

        ok = await db.request_cancel(task_id)

        assert ok
        row = await db.get_task(task_id)
        assert row["cancel_requested"] == 1
        assert row["status"] == "cancelling"

    @pytest.mark.asyncio
    async def test_set_failed_does_not_overwrite_cancellation(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.claim_task(task_id, worker_id="worker-a")
        await db.request_cancel(task_id)

        ok = await db.set_failed(task_id, "boom")

        row = await db.get_task(task_id)
        assert not ok
        assert row["status"] == "cancelling"
        assert row["cancel_requested"] == 1
        assert row["error"] is None

    @pytest.mark.asyncio
    async def test_request_cancel_active_tasks_for_agent_only(self, db, profile):
        from src.sdk.subagent_models import TaskStatus

        pending_id = await db.insert_task("test_agent", "pending", profile)
        running_id = await db.insert_task("test_agent", "running", profile)
        await db.set_running(running_id)
        completed_id = await db.insert_task("test_agent", "completed", profile)
        await db.set_status(completed_id, TaskStatus.COMPLETED)
        other_id = await db.insert_task("other_agent", "running", profile)
        await db.set_running(other_id)

        count = await db.request_cancel_active_tasks_for_agent("test_agent")

        assert count == 2
        assert await db.is_cancel_requested(pending_id)
        assert await db.is_cancel_requested(running_id)
        assert not await db.is_cancel_requested(completed_id)
        assert not await db.is_cancel_requested(other_id)
        pending = await db.get_task(pending_id)
        running = await db.get_task(running_id)
        assert pending["status"] == "cancelled"
        assert pending["completed_at"] is not None
        assert pending["error"] == "cancelled before start"
        assert json.loads(pending["result"])["error"] == "cancelled before start"
        assert running["status"] == "cancelling"
        assert (await db.get_task(completed_id))["status"] == "completed"
        assert (await db.get_task(other_id))["status"] == "running"

    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.claim_task(task_id, worker_id="worker-a")
        before = (await db.get_task(task_id))["heartbeat_at"]

        ok = await db.heartbeat(task_id, worker_id="worker-a")

        after = (await db.get_task(task_id))["heartbeat_at"]

        assert ok
        assert after >= before

    @pytest.mark.asyncio
    async def test_mark_stale_running_failed(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.claim_task(task_id, worker_id="worker-a")

        count = await db.mark_stale_running_failed(max_age_seconds=-1)

        assert count >= 1
        row = await db.get_task(task_id)
        assert row["status"] == "failed"
        assert "interrupted by restart" in row["error"]

    @pytest.mark.asyncio
    async def test_is_cancel_requested_nonexistent(self, db):
        assert not await db.is_cancel_requested("nonexistent")

    @pytest.mark.asyncio
    async def test_check_progress_by_parent(self, db, profile):
        t1 = await db.insert_task("test_agent", "task1", profile, parent_id="parent-1")
        t2 = await db.insert_task("test_agent", "task2", profile, parent_id="parent-1")
        t3 = await db.insert_task("test_agent", "task3", profile, parent_id="parent-2")

        tasks = await db.check_progress(parent_id="parent-1")
        assert len(tasks) == 2
        ids = {t["id"] for t in tasks}
        assert t1 in ids
        assert t2 in ids
        assert t3 not in ids

    @pytest.mark.asyncio
    async def test_check_progress_by_status(self, db, profile):
        from src.sdk.subagent_models import TaskStatus

        t1 = await db.insert_task("test_agent", "task1", profile)
        await db.set_running(t1)
        await db.insert_task("test_agent", "task2", profile)

        running = await db.check_progress(status=TaskStatus.RUNNING)
        assert len(running) == 1
        assert running[0]["id"] == t1

    @pytest.mark.asyncio
    async def test_get_task_is_scoped_to_user_and_workspace(self, mock_paths, profile):
        from src.sdk.work_queue import WorkQueueDB

        db = WorkQueueDB("test_user", workspace_id="personal")
        other_workspace = WorkQueueDB("test_user", workspace_id="other")
        other_user = WorkQueueDB("other_user", workspace_id="personal")
        try:
            task_id = await db.insert_task("test_agent", "task", profile)

            assert await db.get_task(task_id) is not None
            assert await other_workspace.get_task(task_id) is None
            assert await other_user.get_task(task_id) is None
        finally:
            await db.close()
            await other_workspace.close()
            await other_user.close()

    @pytest.mark.asyncio
    async def test_check_progress_is_scoped_to_user_and_workspace(self, mock_paths, profile):
        from src.sdk.subagent_models import TaskStatus
        from src.sdk.work_queue import WorkQueueDB

        db = WorkQueueDB("test_user", workspace_id="personal")
        other_workspace = WorkQueueDB("test_user", workspace_id="other")
        other_user = WorkQueueDB("other_user", workspace_id="personal")
        try:
            own_id = await db.insert_task("test_agent", "own", profile, parent_id="shared")
            other_workspace_id = await other_workspace.insert_task(
                "test_agent", "other workspace", profile, parent_id="shared"
            )
            other_user_id = await other_user.insert_task(
                "test_agent", "other user", profile, parent_id="shared"
            )
            await db.set_running(own_id)
            await other_workspace.set_running(other_workspace_id)
            await other_user.set_running(other_user_id)

            all_tasks = await db.check_progress()
            parent_tasks = await db.check_progress(parent_id="shared")
            status_tasks = await db.check_progress(status=TaskStatus.RUNNING)
            parent_status_tasks = await db.check_progress(
                parent_id="shared", status=TaskStatus.RUNNING
            )

            assert {t["id"] for t in all_tasks} == {own_id}
            assert {t["id"] for t in parent_tasks} == {own_id}
            assert {t["id"] for t in status_tasks} == {own_id}
            assert {t["id"] for t in parent_status_tasks} == {own_id}
        finally:
            await db.close()
            await other_workspace.close()
            await other_user.close()

    @pytest.mark.asyncio
    async def test_get_result(self, db, profile):
        from src.sdk.subagent_models import SubagentResult

        task_id = await db.insert_task("test_agent", "t", profile)
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
    async def test_config_frozen(self, db, profile):
        task_id = await db.insert_task("test_agent", "t", profile)
        row = await db.get_task(task_id)
        config_data = json.loads(row["config"])
        assert config_data["name"] == "test_agent"
        assert config_data["max_llm_calls"] == 10


# -- ProgressMiddleware Tests --


class TestProgressMiddleware:
    @pytest.mark.asyncio
    async def test_updates_progress_on_tool_result(self, db, profile):
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", profile)

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
    async def test_no_update_without_tool_results(self, db, profile):
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", profile)

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
    async def test_injects_instructions(self, db, profile):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", profile)
        await db.add_instruction(task_id, "Focus on the top 3")

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("do it")])

        await mw.abefore_model(state)

        system_msgs = [m for m in state.messages if m.role == "system"]
        assert len(system_msgs) == 1
        assert "[Supervisor Update]" in system_msgs[0].content
        assert "Focus on the top 3" in system_msgs[0].content

    @pytest.mark.asyncio
    async def test_raises_on_cancel(self, db, profile):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState
        from src.sdk.subagent_models import TaskCancelledError

        task_id = await db.insert_task("test_agent", "t", profile)
        await db.request_cancel(task_id)

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("do it")])

        with pytest.raises(TaskCancelledError):
            await mw.abefore_model(state)

    @pytest.mark.asyncio
    async def test_no_injection_without_instructions(self, db, profile):
        from src.sdk.messages import Message
        from src.sdk.middleware_instruction import InstructionMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", profile)

        mw = InstructionMiddleware(task_id, db)
        state = AgentState(messages=[Message.user("hello")])

        result = await mw.abefore_model(state)
        assert result is None
        system_msgs = [m for m in state.messages if m.role == "system"]
        assert len(system_msgs) == 0


# -- Coordinator Tests --


class TestSubagentCoordinator:
    def test_default_tools_exclude_recursive_subagent_tools(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_tools_for_subagent

        class FakeTool:
            def __init__(self, name: str):
                self.name = name

        tools = [
            FakeTool("time_get"),
            FakeTool("subagent_start"),
            FakeTool("subagent_tasks"),
        ]

        with patch("src.sdk.native_tools.get_native_tools", return_value=tools):
            resolved = _build_tools_for_subagent(AgentProfile(name="researcher"))

        names = {tool.name for tool in resolved}
        assert "time_get" in names
        assert "subagent_start" not in names
        assert "subagent_tasks" not in names

    def test_build_tools_removes_subagent_and_extra_memory_tools(self, profile):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_tools_for_subagent

        d = AgentProfile(name="a", tools=[])
        names = {t.name for t in _build_tools_for_subagent(d)}

        assert "message_search" in names
        assert not any(n.startswith("subagent_") for n in names)
        assert "memory_profile" not in names
        assert "memory_reflection" not in names

    def test_build_tools_allowlist_still_includes_message_search(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_tools_for_subagent

        d = AgentProfile(name="a", tools=["time_get"])
        names = {t.name for t in _build_tools_for_subagent(d)}

        assert "time_get" in names
        assert "message_search" in names

    def test_build_tools_includes_skills_load_when_skills_configured(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_tools_for_subagent

        d = AgentProfile(name="a", tools=["time_get"], skills=["skill-creator"])
        names = {t.name for t in _build_tools_for_subagent(d)}

        assert "skills_load" in names

    def test_build_tools_removes_skill_management_tools(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_tools_for_subagent

        class FakeTool:
            def __init__(self, name: str):
                self.name = name

        tools = [
            FakeTool("time_get"),
            FakeTool("message_search"),
            FakeTool("skill_create"),
            FakeTool("skill_delete"),
            FakeTool("skills_load"),
        ]

        with patch("src.sdk.native_tools.get_native_tools", return_value=tools):
            resolved = _build_tools_for_subagent(AgentProfile(name="a", tools=[]))

        names = {tool.name for tool in resolved}
        assert "time_get" in names
        assert "message_search" in names
        assert "skill_delete" not in names

    def test_validate_agent_def_rejects_denied_memory_tool(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import validate_agent_def

        errors = validate_agent_def(AgentProfile(name="a", tools=["memory_profile"]))

        assert any("Memory tool" in e for e in errors)

    def test_validate_agent_def_rejects_unknown_skill(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import validate_agent_def

        class FakeSkillRegistry:
            def get_skill(self, name: str):
                return None

        with patch("src.skills.registry.get_skill_registry", return_value=FakeSkillRegistry()):
            errors = validate_agent_def(AgentProfile(name="a", skills=["missing-skill"]))

        assert any("Unknown skill" in e for e in errors)

    def test_validate_agent_def_rejects_non_positive_limits(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import validate_agent_def

        errors = validate_agent_def(
            AgentProfile(name="a", max_llm_calls=0, cost_limit_usd=0, timeout_seconds=0)
        )

        assert "max_llm_calls must be positive" in errors
        assert "cost_limit_usd must be positive" in errors
        assert "timeout_seconds must be positive" in errors

    def test_validate_agent_def_allows_default_future_subagent_denylist_names(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import validate_agent_def

        errors = validate_agent_def(AgentProfile(name="a"))
        assert not errors

    def test_build_system_prompt_lists_skills_without_inlining_content(self):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import _build_system_prompt

        class FakeSkillRegistry:
            def get_skill(self, name: str):
                return {
                    "name": name,
                    "description": "Create reusable skills.",
                    "content": "SECRET FULL SKILL CONTENT",
                }

        profile = AgentProfile(name="a", skills=["skill-creator"])
        with patch("src.skills.registry.get_skill_registry", return_value=FakeSkillRegistry()):
            prompt = _build_system_prompt(profile, user_id="test_user", workspace_id="personal")

        assert "## Available Skills" in prompt
        assert "skill-creator" in prompt
        assert "Create reusable skills." in prompt
        assert "skills_load(skill_name=...)" in prompt
        assert "SECRET FULL SKILL CONTENT" not in prompt

    @pytest.mark.asyncio
    async def test_run_loop_passes_provider_options_and_workspace_to_agent_loop(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.messages import Message

        captured_run_config = None
        captured_workspace_id = None

        class FakeAgentLoop:
            def __init__(self, **kwargs):
                nonlocal captured_run_config, captured_workspace_id
                captured_run_config = kwargs["run_config"]
                captured_workspace_id = kwargs["workspace_id"]

            async def run(self, messages):
                return [*messages, Message.assistant("done")]

        provider_options = {"anthropic": {"thinking": {"type": "enabled"}}}
        profile = AgentProfile(name="researcher", provider_options=provider_options)
        coord = SubagentCoordinator("test_user", workspace_id="sales")

        with patch("src.sdk.providers.factory.create_model_from_config", return_value=object()):
            with patch("src.sdk.coordinator._build_tools_for_subagent", return_value=[]):
                with patch("src.sdk.coordinator._build_system_prompt", return_value="system"):
                    with patch("src.sdk.loop.AgentLoop", FakeAgentLoop):
                        await coord._run_loop("task-1", profile, "do it", object())

        assert captured_run_config is not None
        assert captured_run_config.provider_options == provider_options
        assert captured_workspace_id == "sales"

    @pytest.mark.asyncio
    async def test_start_returns_before_runner_finishes(self, mock_paths, profile, monkeypatch):
        from src.sdk.coordinator import SubagentCoordinator

        coordinator = SubagentCoordinator("test_user")
        await coordinator.create(profile)
        started = asyncio.Event()
        finish = asyncio.Event()

        async def fake_run_job(task_id: str):
            started.set()
            await finish.wait()

        monkeypatch.setattr(coordinator, "_run_job", fake_run_job)

        task_id = await coordinator.start("test_agent", "do work")

        await asyncio.wait_for(started.wait(), timeout=1)
        row = await (await coordinator._get_db()).get_task(task_id)
        assert row is not None
        assert row["status"] in {"pending", "running"}
        finish.set()
        await asyncio.sleep(0)

    @pytest.mark.asyncio
    async def test_start_retains_background_task_until_completion(
        self, mock_paths, profile, monkeypatch
    ):
        from src.sdk.coordinator import SubagentCoordinator

        coordinator = SubagentCoordinator("test_user")
        await coordinator.create(profile)
        started = asyncio.Event()
        finish = asyncio.Event()

        async def fake_run_job(task_id: str):
            started.set()
            await finish.wait()

        monkeypatch.setattr(coordinator, "_run_job", fake_run_job)

        await coordinator.start("test_agent", "do work")

        await asyncio.wait_for(started.wait(), timeout=1)
        assert len(coordinator._background_tasks) == 1

        finish.set()
        await asyncio.wait_for(_wait_for_no_background_tasks(coordinator), timeout=1)
        assert coordinator._background_tasks == set()

    @pytest.mark.asyncio
    async def test_start_freezes_config_snapshot(self, mock_paths, profile, monkeypatch):
        from src.sdk.coordinator import SubagentCoordinator

        coordinator = SubagentCoordinator("test_user")
        await coordinator.create(profile)

        async def fake_run_job(task_id: str):
            return None

        monkeypatch.setattr(coordinator, "_run_job", fake_run_job)
        task_id = await coordinator.start("test_agent", "do work")
        await coordinator.update("test_agent", model="changed:model")

        row = await (await coordinator._get_db()).get_task(task_id)
        config = json.loads(row["config"])
        assert config["model"] == profile.model

    @pytest.mark.asyncio
    async def test_run_job_claims_pending_task_and_marks_completed(
        self, mock_paths, profile, monkeypatch
    ):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import SubagentResult

        coordinator = SubagentCoordinator("test_user")
        db = await coordinator._get_db()
        task_id = await db.insert_task("test_agent", "do work", profile)

        async def fake_run_loop(task_id: str, frozen_agent_def, task: str, db):
            return SubagentResult(
                name=frozen_agent_def.name,
                task=task,
                success=True,
                output=f"completed {task_id}",
            )

        monkeypatch.setattr(coordinator, "_run_loop", fake_run_loop)

        await coordinator._run_job(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "completed"
        assert row["claimed_by"] is not None
        result = json.loads(row["result"])
        assert result["output"] == f"completed {task_id}"

    @pytest.mark.asyncio
    async def test_run_job_preserves_cancel_racing_with_completion(
        self, mock_paths, profile, monkeypatch
    ):
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import SubagentResult

        coordinator = SubagentCoordinator("test_user")
        db = await coordinator._get_db()
        task_id = await db.insert_task("test_agent", "do work", profile)

        async def fake_run_loop(task_id: str, frozen_agent_def, task: str, db):
            return SubagentResult(
                name=frozen_agent_def.name,
                task=task,
                success=True,
                output="done",
            )

        original_set_completed = db.set_completed

        async def cancel_before_complete(task_id: str, result):
            await db.request_cancel(task_id)
            return await original_set_completed(task_id, result)

        monkeypatch.setattr(coordinator, "_run_loop", fake_run_loop)
        monkeypatch.setattr(db, "set_completed", cancel_before_complete)

        await coordinator._run_job(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_requested"] == 1
        result = json.loads(row["result"])
        assert result["error"] == "cancelled by supervisor"

    @pytest.mark.asyncio
    async def test_run_job_preserves_cancel_racing_with_error_failure(
        self, mock_paths, profile, monkeypatch
    ):
        from src.sdk.coordinator import SubagentCoordinator

        coordinator = SubagentCoordinator("test_user")
        db = await coordinator._get_db()
        task_id = await db.insert_task("test_agent", "do work", profile)

        async def fake_run_loop(task_id: str, frozen_agent_def, task: str, db):
            raise RuntimeError("boom")

        original_set_failed = db.set_failed

        async def cancel_before_fail(task_id: str, error: str):
            await db.request_cancel(task_id)
            return await original_set_failed(task_id, error)

        monkeypatch.setattr(coordinator, "_run_loop", fake_run_loop)
        monkeypatch.setattr(db, "set_failed", cancel_before_fail)

        await coordinator._run_job(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_requested"] == 1
        result = json.loads(row["result"])
        assert result["error"] == "cancelled by supervisor"

    @pytest.mark.asyncio
    async def test_run_job_preserves_cancel_racing_with_timeout_failure(
        self, mock_paths, profile, monkeypatch
    ):
        from src.sdk.coordinator import SubagentCoordinator

        coordinator = SubagentCoordinator("test_user")
        db = await coordinator._get_db()
        task_id = await db.insert_task("test_agent", "do work", profile)

        async def fake_run_loop(task_id: str, frozen_agent_def, task: str, db):
            raise TimeoutError

        original_set_failed = db.set_failed

        async def cancel_before_fail(task_id: str, error: str):
            await db.request_cancel(task_id)
            return await original_set_failed(task_id, error)

        monkeypatch.setattr(coordinator, "_run_loop", fake_run_loop)
        monkeypatch.setattr(db, "set_failed", cancel_before_fail)

        await coordinator._run_job(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"
        assert row["cancel_requested"] == 1
        result = json.loads(row["result"])
        assert result["error"] == "cancelled by supervisor"

    @pytest.mark.asyncio
    async def test_create_and_load(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        profile = AgentProfile(name="researcher", description="Web researcher", model="ollama:minimax-m2.5")
        await coord.create(profile)

        loaded = coord.load_def("researcher")
        assert loaded is not None
        assert loaded.name == "researcher"
        assert loaded.description == "Web researcher"

    @pytest.mark.asyncio
    async def test_create_persists_profile(self, mock_paths):
        from agentprofile.models import AgentProfile
        from agentprofile.parser import load_profile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        profile = AgentProfile(name="writer", description="Report writer", tools=["time_get"])
        await coord.create(profile)

        profile_path = mock_paths.workspace_subagents_dir() / "writer" / "PROFILE.md"
        assert profile_path.exists()
        loaded = load_profile(str(profile_path))
        assert loaded.name == "writer"
        assert loaded.tools == ["time_get"]

    @pytest.mark.asyncio
    async def test_update(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        profile = AgentProfile(name="updater", description="Original", max_llm_calls=10)
        await coord.create(profile)

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
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentProfile(name="a1", description="Agent 1"))
        await coord.create(AgentProfile(name="a2", description="Agent 2"))

        defs = await coord.list_defs()
        names = {d.name for d in defs}
        assert "a1" in names
        assert "a2" in names

    @pytest.mark.asyncio
    async def test_delete(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentProfile(name="deleteme", description="Temporary"))
        assert coord.load_def("deleteme") is not None

        ok = await coord.delete("deleteme")
        assert ok
        assert coord.load_def("deleteme") is None

    @pytest.mark.asyncio
    async def test_delete_requests_cancel_for_active_jobs_only(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import TaskStatus

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentProfile(name="deleteme", description="Temporary"))
        await coord.create(AgentProfile(name="keepme", description="Persistent"))
        db = await coord._get_db()

        profile = coord.load_def("deleteme")
        other_def = coord.load_def("keepme")
        pending_id = await db.insert_task("deleteme", "pending", profile)
        running_id = await db.insert_task("deleteme", "running", profile)
        await db.set_running(running_id)
        cancelling_id = await db.insert_task("deleteme", "cancelling", profile)
        await db.set_status(cancelling_id, TaskStatus.CANCELLING)
        completed_id = await db.insert_task("deleteme", "completed", profile)
        await db.set_status(completed_id, TaskStatus.COMPLETED)
        failed_id = await db.insert_task("deleteme", "failed", profile)
        await db.set_status(failed_id, TaskStatus.FAILED)
        cancelled_id = await db.insert_task("deleteme", "cancelled", profile)
        await db.set_status(cancelled_id, TaskStatus.CANCELLED)
        other_id = await db.insert_task("keepme", "running", other_def)
        await db.set_running(other_id)

        ok = await coord.delete("deleteme")

        assert ok
        assert await db.is_cancel_requested(pending_id)
        assert await db.is_cancel_requested(running_id)
        assert await db.is_cancel_requested(cancelling_id)
        assert not await db.is_cancel_requested(completed_id)
        assert not await db.is_cancel_requested(failed_id)
        assert not await db.is_cancel_requested(cancelled_id)
        assert not await db.is_cancel_requested(other_id)
        pending = await db.get_task(pending_id)
        assert pending["status"] == "cancelled"
        assert pending["completed_at"] is not None
        assert pending["error"] == "cancelled before start"
        assert json.loads(pending["result"])["error"] == "cancelled before start"
        assert (await db.get_task(running_id))["status"] == "cancelling"
        assert (await db.get_task(cancelling_id))["status"] == "cancelling"
        assert (await db.get_task(completed_id))["status"] == "completed"
        assert (await db.get_task(failed_id))["status"] == "failed"
        assert (await db.get_task(cancelled_id))["status"] == "cancelled"
        assert (await db.get_task(other_id))["status"] == "running"

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, mock_paths):
        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        ok = await coord.delete("ghost")
        assert not ok

    @pytest.mark.asyncio
    async def test_cancel_and_instruct(self, mock_paths):
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentProfile(name="canceller", description="Test"))

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
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        await coord.create(AgentProfile(name="progressor", description="Test"))

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
        from agentprofile.models import AgentProfile

        from src.sdk.coordinator import SubagentCoordinator

        coord = SubagentCoordinator("test_user")
        original = AgentProfile(name="freeze_test", description="Original", max_llm_calls=10)
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
    async def test_doom_loop_detection(self, db, profile):
        """Simulate doom loop detection in ProgressMiddleware."""
        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        task_id = await db.insert_task("test_agent", "t", profile)

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
    async def test_cancel_then_check_status(self, db, profile):
        """Full cancel flow: insert -> cancel_requested -> set_cancelled."""
        task_id = await db.insert_task("test_agent", "t", profile)
        await db.set_running(task_id)

        await db.request_cancel(task_id)
        assert await db.is_cancel_requested(task_id)

        await db.set_cancelled(task_id)

        row = await db.get_task(task_id)
        assert row["status"] == "cancelled"


# -- Stale Job Recovery --


class TestStaleJobRecovery:
    @pytest.mark.asyncio
    async def test_coordinator_recovers_stale_jobs_on_init(self, tmp_path):
        from datetime import UTC, datetime, timedelta
        from unittest import mock

        import aiosqlite

        from src.sdk.coordinator import SubagentCoordinator

        db_dir = tmp_path / "subagents"
        db_dir.mkdir()

        # Direct DB: insert a stale RUNNING task
        db = await aiosqlite.connect(str(db_dir / "work_queue.db"))
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS work_queue (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL DEFAULT 'personal',
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress TEXT DEFAULT '{}',
                result TEXT,
                error TEXT,
                instructions TEXT DEFAULT '[]',
                config TEXT DEFAULT '{}',
                cancel_requested INTEGER DEFAULT 0,
                claimed_by TEXT,
                claimed_at TEXT,
                heartbeat_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        stale_time = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
        await db.execute(
            "INSERT INTO work_queue (id, user_id, workspace_id, agent_name, task, status, heartbeat_at, created_at, updated_at) "
            "VALUES ('stale-job', 'test_user', 'test_ws', 'helper', 'do thing', 'running', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (stale_time,)
        )
        await db.commit()
        await db.close()

        # Patch get_paths to use tmp dir (both coordinator and work_queue paths)
        mock_paths = mock.MagicMock()
        mock_paths.workspace_subagents_dir = mock.MagicMock(return_value=db_dir)
        mock_paths.work_queue_db = mock.MagicMock(return_value=db_dir / "work_queue.db")

        with mock.patch('src.sdk.coordinator.get_paths', return_value=mock_paths), \
             mock.patch('src.sdk.work_queue.get_paths', return_value=mock_paths):
            coordinator = SubagentCoordinator("test_user", "test_ws")
            db = await coordinator._get_db()
            await coordinator._recovery_task
            task = await db.get_task("stale-job")
            assert task is not None
            assert task["status"] == "failed"




class TestDoomLoopDetection:
    """Verify doom loop detection uses tool call args, not result content."""

    @pytest.mark.asyncio
    async def test_doom_loop_detects_same_tool_with_same_args(self):
        from unittest import mock

        from src.sdk.messages import Message, ToolCall
        from src.sdk.middleware_progress import DOOM_THRESHOLD, ProgressMiddleware
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-1", mock_db)

        state = AgentState()
        args = {"path": "/a.txt"}
        for i in range(DOOM_THRESHOLD):
            state.add_message(Message.assistant(
                tool_calls=[ToolCall(id=f"tc{i}", name="files_read", arguments=args)]
            ))
            state.add_message(Message.tool_result(
                tool_call_id=f"tc{i}", content="file contents", name="files_read"
            ))
            await mw.abefore_model(state)

        assert len(mw._last_tool_calls) == DOOM_THRESHOLD
        assert len(set(mw._last_tool_calls)) == 1

    @pytest.mark.asyncio
    async def test_doom_loop_distinguishes_same_tool_with_different_args(self):
        from unittest import mock

        from src.sdk.messages import Message, ToolCall
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-2", mock_db)

        state = AgentState()

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc0", name="files_read", arguments={"path": "/a.txt"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc0", content="content A", name="files_read"
        ))
        await mw.abefore_model(state)

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc1", name="files_read", arguments={"path": "/b.txt"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc1", content="content B", name="files_read"
        ))
        await mw.abefore_model(state)

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc2", name="files_read", arguments={"path": "/c.txt"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc2", content="content C", name="files_read"
        ))
        result = await mw.abefore_model(state)

        assert result is None
        assert len(set(mw._last_tool_calls)) == 3

    @pytest.mark.asyncio
    async def test_doom_loop_distinguishes_string_returning_tools(self):
        from unittest import mock

        from src.sdk.messages import Message, ToolCall
        from src.sdk.middleware_progress import ProgressMiddleware
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-3", mock_db)

        state = AgentState()

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc0", name="shell_execute", arguments={"command": "ls"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc0", content="file1\\nfile2", name="shell_execute"
        ))
        await mw.abefore_model(state)

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc1", name="shell_execute", arguments={"command": "pwd"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc1", content="/home/user", name="shell_execute"
        ))
        await mw.abefore_model(state)

        state.add_message(Message.assistant(
            tool_calls=[ToolCall(id="tc2", name="shell_execute", arguments={"command": "date"})]
        ))
        state.add_message(Message.tool_result(
            tool_call_id="tc2", content="Mon May 19", name="shell_execute"
        ))
        result = await mw.abefore_model(state)

        assert result is None
        assert len(set(mw._last_tool_calls)) == 3
