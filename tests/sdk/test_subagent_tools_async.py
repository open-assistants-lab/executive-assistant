import pytest


def test_new_runtime_tools_registered():
    from src.sdk.native_tools import get_native_tools

    names = {t.name for t in get_native_tools()}
    assert "subagent_start" in names
    assert "subagent_check" in names
    assert "subagent_tasks" in names
    assert {"subagent_start", "subagent_check", "subagent_tasks"}.issubset(names)


def test_subagent_start_returns_job_id(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    class FakeCoordinator:
        def load_def(self, name):
            return object()

        async def start(self, agent_name, task, parent_id=None):
            return "job123"

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )
    result = mod.subagent_start.invoke(
        {
            "agent_name": "worker",
            "task": "do work",
            "user_id": "u",
            "workspace_id": "w",
        }
    )
    assert "job123" in result
    assert "subagent_check" in result


def test_subagent_check_returns_single_job_status(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    class FakeDB:
        async def get_task(self, task_id):
            assert task_id == "job123"
            return {
                "id": "job123",
                "agent_name": "worker",
                "status": "completed",
                "progress": '{"steps_completed": 2, "phase": "done"}',
                "result": '{"output": "finished", "truncated": false}',
            }

    class FakeCoordinator:
        async def _get_db(self):
            return FakeDB()

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )

    result = mod.subagent_check.invoke(
        {"task_id": "job123", "user_id": "u", "workspace_id": "w"}
    )

    assert "job123" in result
    assert "completed" in result
    assert "finished" in result


def test_subagent_tasks_filters_by_status(monkeypatch):
    from src.sdk.subagent_models import TaskStatus
    from src.sdk.tools_core import subagent as mod

    seen = {}

    class FakeDB:
        async def check_progress(self, status=None):
            seen["status"] = status
            return [{"id": "job123", "agent_name": "worker", "status": "running"}]

    class FakeCoordinator:
        async def _get_db(self):
            return FakeDB()

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )

    result = mod.subagent_tasks.invoke(
        {"status": "running", "user_id": "u", "workspace_id": "w"}
    )

    assert seen["status"] == TaskStatus.RUNNING
    assert "job123" in result
    assert "worker" in result


def test_subagent_tasks_rejects_invalid_status(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    result = mod.subagent_tasks.invoke(
        {"status": "not-a-status", "user_id": "u", "workspace_id": "w"}
    )

    assert result.startswith("Error: Invalid status")
    assert "running" in result


def test_subagent_create_parses_new_json_fields_and_validates(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    saved = {}

    class FakeCoordinator:
        def load_def(self, name):
            return None

        async def create(self, agent_def):
            saved["agent_def"] = agent_def
            return agent_def

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )
    monkeypatch.setattr(mod, "validate_agent_def", lambda agent_def, **kwargs: [], raising=False)

    result = mod.subagent_create.invoke(
        {
            "name": "worker",
            "user_id": "u",
            "workspace_id": "w",
            "provider_options": '{"anthropic": {"thinking": {"type": "enabled"}}}',
            "output_schema": '{"type": "object"}',
            "handoff_instructions": "return concise output",
            "artifact_policy": "none",
        }
    )

    agent_def = saved["agent_def"]
    assert "created successfully" in result
    assert agent_def.provider_options == {"anthropic": {"thinking": {"type": "enabled"}}}
    assert agent_def.output_schema == {"type": "object"}
    assert agent_def.handoff_instructions == "return concise output"
    assert agent_def.artifact_policy == "none"


def test_subagent_create_rejects_non_object_provider_options(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    result = mod.subagent_create.invoke(
        {"name": "worker", "user_id": "u", "provider_options": '["bad"]'}
    )

    assert result == "Error: provider_options must be a JSON object."


def test_subagent_update_parses_new_fields_and_validates_before_save(monkeypatch):
    from src.sdk.subagent_models import AgentDef
    from src.sdk.tools_core import subagent as mod

    saved = {}
    validated = {}
    existing = AgentDef(name="worker", description="old")

    class FakeCoordinator:
        def load_def(self, name):
            return existing

        async def update(self, name, **kwargs):
            saved["name"] = name
            saved["kwargs"] = kwargs
            return existing.model_copy(update=kwargs)

    def fake_validate(agent_def, **kwargs):
        validated["agent_def"] = agent_def
        validated["kwargs"] = kwargs
        return []

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )
    monkeypatch.setattr(mod, "validate_agent_def", fake_validate, raising=False)

    result = mod.subagent_update.invoke(
        {
            "name": "worker",
            "user_id": "u",
            "workspace_id": "w",
            "provider_options": '{"anthropic": {"thinking": {"type": "enabled"}}}',
            "output_schema": '{"type": "object"}',
            "handoff_instructions": "return concise output",
            "artifact_policy": "none",
        }
    )

    assert "updated" in result
    assert saved["name"] == "worker"
    assert saved["kwargs"]["provider_options"] == {
        "anthropic": {"thinking": {"type": "enabled"}}
    }
    assert saved["kwargs"]["output_schema"] == {"type": "object"}
    assert saved["kwargs"]["handoff_instructions"] == "return concise output"
    assert saved["kwargs"]["artifact_policy"] == "none"
    assert validated["agent_def"].provider_options == {
        "anthropic": {"thinking": {"type": "enabled"}}
    }
    assert validated["agent_def"].output_schema == {"type": "object"}
    assert validated["agent_def"].handoff_instructions == "return concise output"
    assert validated["agent_def"].artifact_policy == "none"
    assert validated["kwargs"] == {"user_id": "u", "workspace_id": "w"}


def test_subagent_update_rejects_invalid_provider_options_json(monkeypatch):
    from src.sdk.subagent_models import AgentDef
    from src.sdk.tools_core import subagent as mod

    class FakeCoordinator:
        def load_def(self, name):
            return AgentDef(name="worker")

        async def update(self, name, **kwargs):
            raise AssertionError("update should not be called")

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )

    result = mod.subagent_update.invoke(
        {"name": "worker", "user_id": "u", "provider_options": "{"}
    )

    assert result.startswith("Error: Invalid provider_options JSON")


def test_subagent_update_rejects_invalid_output_schema_json(monkeypatch):
    from src.sdk.subagent_models import AgentDef
    from src.sdk.tools_core import subagent as mod

    class FakeCoordinator:
        def load_def(self, name):
            return AgentDef(name="worker")

        async def update(self, name, **kwargs):
            raise AssertionError("update should not be called")

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )

    result = mod.subagent_update.invoke(
        {"name": "worker", "user_id": "u", "output_schema": "{"}
    )

    assert result.startswith("Error: Invalid output_schema JSON")


def test_subagent_update_rejects_validation_errors_before_save(monkeypatch):
    from src.sdk.subagent_models import AgentDef
    from src.sdk.tools_core import subagent as mod

    validated = {}

    class FakeCoordinator:
        def load_def(self, name):
            return AgentDef(name="worker")

        async def update(self, name, **kwargs):
            raise AssertionError("update should not be called")

    def fake_validate(agent_def, **kwargs):
        validated["tools"] = agent_def.tools
        return ["Unknown tool: not_a_tool"]

    monkeypatch.setattr(
        mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False
    )
    monkeypatch.setattr(mod, "validate_agent_def", fake_validate, raising=False)

    result = mod.subagent_update.invoke(
        {"name": "worker", "user_id": "u", "tools": ["not_a_tool"]}
    )

    assert result == "Error: Unknown tool: not_a_tool"
    assert validated["tools"] == ["not_a_tool"]


class TestAsyncBridgeRecovery:
    def test_run_async_respects_timeout(self):
        import asyncio
        from unittest import mock

        import src.sdk.tools_core.subagent as subagent_module

        async def slow_coro():
            await asyncio.sleep(60)
            return "done"

        with mock.patch.object(subagent_module, "_TIMEOUT_SECONDS", 0.5):
            with pytest.raises(TimeoutError):
                subagent_module._run_async(slow_coro())

    def test_get_loop_creates_fresh_loop_when_closed(self):
        import time

        import src.sdk.tools_core.subagent as subagent_module

        subagent_module._loop = None
        loop1 = subagent_module._get_loop()
        assert not loop1.is_closed()

        loop1.call_soon_threadsafe(loop1.stop)
        time.sleep(0.2)
        loop1.close()

        loop2 = subagent_module._get_loop()
        assert loop2 is not None
        assert not loop2.is_closed()
        assert loop2 is not loop1
