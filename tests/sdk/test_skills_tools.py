"""Behavioral tests for SDK-native skill tools."""

from __future__ import annotations

from pathlib import Path

from src.skills.registry import SkillRegistry


def _write_skill(root: Path, name: str, description: str, body: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: {description}
---
{body}
""",
        encoding="utf-8",
    )


class _FakePaths:
    def __init__(self, user_skills: Path, workspace_skills: Path):
        self._user_skills = user_skills
        self._workspace_skills = workspace_skills

    def skills_dir(self) -> Path:
        self._user_skills.mkdir(parents=True, exist_ok=True)
        return self._user_skills

    def workspace_skills_dir(self) -> Path:
        self._workspace_skills.mkdir(parents=True, exist_ok=True)
        return self._workspace_skills


def test_skills_list_includes_merged_skill_names_and_scopes(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(user_dir, "user-helper", "User helper", "User content")
    _write_skill(workspace_dir, "workspace-helper", "Workspace helper", "Workspace content")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)

    result = skills_tools.skills_list.invoke({"user_id": "test", "workspace_id": "ws1"})

    assert "[user] user-helper: User helper" in result
    assert "[workspace] workspace-helper: Workspace helper" in result


def test_skills_load_prefers_workspace_skill_and_includes_scope(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(user_dir, "shared", "User shared", "User version")
    _write_skill(workspace_dir, "shared", "Workspace shared", "Workspace version")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)

    result = skills_tools.skills_load.invoke(
        {"skill_name": "shared", "user_id": "test", "workspace_id": "ws1"}
    )

    assert "# shared [workspace]" in result
    assert "Workspace version" in result
    assert "User version" not in result
    assert "shared" in registry.get_loaded_skills()


def test_skills_load_rejects_path_traversal_names(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    base_dir = tmp_path / "base"
    user_dir = base_dir / "user-skills"
    workspace_dir = base_dir / "workspace-skills"
    _write_skill(tmp_path, "whatever", "Outside skill", "outside secret")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)

    result = skills_tools.skills_load.invoke(
        {"skill_name": "../../whatever", "user_id": "test", "workspace_id": "ws1"}
    )

    assert "outside secret" not in result
    assert "Invalid skill name" in result


def test_skill_create_workspace_scope_writes_workspace_skill_and_reloads(
    tmp_path, monkeypatch
):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    reload_calls = []
    original_reload = registry.reload

    def reload_spy() -> None:
        reload_calls.append(True)
        original_reload()

    registry.reload = reload_spy
    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )

    result = skills_tools.skill_create.invoke(
        {
            "name": "workspace-new",
            "content": "---\nname: workspace-new\ndescription: Workspace New\n---\nBody",
            "scope": "workspace",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert "Successfully created workspace skill 'workspace-new'" in result
    assert (workspace_dir / "workspace-new" / "SKILL.md").exists()
    assert not (user_dir / "workspace-new" / "SKILL.md").exists()
    assert reload_calls == [True]


def test_skill_create_resets_sdk_loop(tmp_path, monkeypatch):
    from src.sdk import runner
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    reset_calls = []

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )
    monkeypatch.setattr(runner, "reset_sdk_loop", lambda user_id, workspace_id: reset_calls.append((user_id, workspace_id)))

    result = skills_tools.skill_create.invoke(
        {
            "name": "workspace-reset",
            "content": "---\nname: workspace-reset\ndescription: Workspace Reset\n---\nBody",
            "scope": "workspace",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert "Successfully created workspace skill 'workspace-reset'" in result
    assert reset_calls == [("test", "ws1")]


def test_skill_create_user_scope_resets_all_user_sdk_loops(tmp_path, monkeypatch):
    from src.sdk import runner
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    reset_user_calls = []
    reset_workspace_calls = []

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )
    monkeypatch.setattr(runner, "reset_user_sdk_loops", lambda user_id: reset_user_calls.append(user_id))
    monkeypatch.setattr(
        runner,
        "reset_sdk_loop",
        lambda user_id, workspace_id: reset_workspace_calls.append((user_id, workspace_id)),
    )

    result = skills_tools.skill_create.invoke(
        {
            "name": "user-reset",
            "content": "---\nname: user-reset\ndescription: User Reset\n---\nBody",
            "scope": "user",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert "Successfully created user skill 'user-reset'" in result
    assert reset_user_calls == ["test"]
    assert reset_workspace_calls == []


def test_skill_create_rejects_invalid_scope_before_writing(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )

    result = skills_tools.skill_create.invoke(
        {
            "name": "bad-scope",
            "content": "---\nname: bad-scope\ndescription: Bad Scope\n---\nBody",
            "scope": "team",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert result == "Invalid scope: 'team'. Must be 'user' or 'workspace'."
    assert not (user_dir / "bad-scope").exists()
    assert not (workspace_dir / "bad-scope").exists()


def test_skill_delete_removes_requested_scope_and_reloads(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(user_dir, "cleanup", "User cleanup", "User cleanup body")
    _write_skill(workspace_dir, "cleanup", "Workspace cleanup", "Workspace cleanup body")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    reload_calls = []
    original_reload = registry.reload

    def reload_spy() -> None:
        reload_calls.append(True)
        original_reload()

    registry.reload = reload_spy
    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )

    result = skills_tools.skill_delete.invoke(
        {
            "skill_name": "cleanup",
            "scope": "workspace",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert "Successfully deleted workspace skill 'cleanup'" in result
    assert not (workspace_dir / "cleanup").exists()
    assert (user_dir / "cleanup").exists()
    assert reload_calls == [True]


def test_skill_delete_resets_sdk_loop(tmp_path, monkeypatch):
    from src.sdk import runner
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(workspace_dir, "cleanup-reset", "Workspace cleanup", "Body")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    reset_calls = []

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )
    monkeypatch.setattr(runner, "reset_sdk_loop", lambda user_id, workspace_id: reset_calls.append((user_id, workspace_id)))

    result = skills_tools.skill_delete.invoke(
        {
            "skill_name": "cleanup-reset",
            "scope": "workspace",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert "Successfully deleted workspace skill 'cleanup-reset'" in result
    assert reset_calls == [("test", "ws1")]


def test_skill_delete_rejects_invalid_scope_before_deleting(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(user_dir, "keep-me", "Keep me", "Body")
    monkeypatch.setattr(
        skills_tools,
        "get_paths",
        lambda user_id, workspace_id="personal": _FakePaths(user_dir, workspace_dir),
    )

    result = skills_tools.skill_delete.invoke(
        {
            "skill_name": "keep-me",
            "scope": "team",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )

    assert result == "Invalid scope: 'team'. Must be 'user' or 'workspace'."
    assert (user_dir / "keep-me" / "SKILL.md").exists()


def test_skills_search_matches_merged_skills_and_includes_scopes(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    _write_skill(user_dir, "notes-helper", "Organize notes", "Notebook content")
    _write_skill(workspace_dir, "project-helper", "Project planning", "Roadmap content")
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)

    monkeypatch.setattr(skills_tools, "get_skill_registry", lambda **kwargs: registry)

    result = skills_tools.skills_search.invoke(
        {"query": "helper", "user_id": "test", "workspace_id": "ws1"}
    )

    assert "[user] notes-helper: Organize notes" in result
    assert "[workspace] project-helper: Project planning" in result


def test_get_registry_passes_workspace_id(monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    calls = []

    def fake_get_skill_registry(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(skills_tools, "get_skill_registry", fake_get_skill_registry)

    registry = skills_tools._get_registry("test", "ws1")

    assert registry is not None
    assert calls == [{"user_id": "test", "workspace_id": "ws1"}]


def test_sql_write_query_checks_loaded_skill_in_matching_workspace(tmp_path, monkeypatch):
    from src.sdk.tools_core import skills as skills_tools

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    registry_ws1 = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    registry_personal = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)
    registries = {"ws1": registry_ws1, "personal": registry_personal}

    monkeypatch.setattr(
        skills_tools,
        "get_skill_registry",
        lambda user_id, workspace_id="personal": registries[workspace_id],
    )

    registry_ws1.mark_skill_loaded("analytics-db")

    ws_result = skills_tools.sql_write_query.invoke(
        {
            "query": "select 1",
            "database": "analytics-db",
            "user_id": "test",
            "workspace_id": "ws1",
        }
    )
    personal_result = skills_tools.sql_write_query.invoke(
        {"query": "select 1", "database": "analytics-db", "user_id": "test"}
    )

    assert "Query validated against analytics-db schema" in ws_result
    assert "must load the 'analytics-db' skill first" in personal_result
