def test_new_runtime_tools_registered():
    from src.sdk.native_tools import get_native_tools

    names = {t.name for t in get_native_tools()}
    assert "subagent_start" in names
    assert "subagent_check" in names
    assert "subagent_tasks" in names
    assert "subagent_invoke" not in names
    assert "subagent_progress" not in names


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
