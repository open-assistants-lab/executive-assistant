"""Tests for workspace-aware skill registry."""

import tempfile
from pathlib import Path

from src.skills.registry import SkillRegistry, get_skill_registry, reset_skill_registries


def test_registry_workspace_override_user_by_name():
    """Workspace skill with same name overrides user skill."""
    with tempfile.TemporaryDirectory() as user_d, tempfile.TemporaryDirectory() as ws_d:
        usp = Path(user_d) / "greeting" / "SKILL.md"
        usp.parent.mkdir(parents=True)
        usp.write_text("""---
name: greeting
description: User-level greeting skill
---
# User greeting
Say hello from user scope.""")

        wsp = Path(ws_d) / "greeting" / "SKILL.md"
        wsp.parent.mkdir(parents=True)
        wsp.write_text("""---
name: greeting
description: Workspace-level greeting skill
---
# Workspace greeting
Say hello from workspace scope.""")

        registry = SkillRegistry(skills_dir=user_d, workspace_skills_dir=ws_d)
        skills = registry.get_all_skills()

        names = [s["name"] for s in skills]
        assert "greeting" in names
        assert len([s for s in skills if s["name"] == "greeting"]) == 1

        greeting = next(s for s in skills if s["name"] == "greeting")
        assert "workspace scope" in greeting["content"]
        assert greeting["description"] == "Workspace-level greeting skill"
        assert greeting.get("metadata", {}).get("scope") == "workspace"


def test_registry_scope_fields_populated():
    """User skills get scope=user, workspace skills get scope=workspace."""
    with tempfile.TemporaryDirectory() as user_d, tempfile.TemporaryDirectory() as ws_d:
        (Path(user_d) / "alpha").mkdir(parents=True)
        (Path(user_d) / "alpha" / "SKILL.md").write_text("""---
name: alpha
description: User only
---
Content A""")

        (Path(ws_d) / "beta").mkdir(parents=True)
        (Path(ws_d) / "beta" / "SKILL.md").write_text("""---
name: beta
description: Workspace only
---
Content B""")

        registry = SkillRegistry(skills_dir=user_d, workspace_skills_dir=ws_d)
        skills = registry.get_all_skills()

        alpha = next(s for s in skills if s["name"] == "alpha")
        beta = next(s for s in skills if s["name"] == "beta")

        assert alpha.get("metadata", {}).get("scope") == "user"
        assert beta.get("metadata", {}).get("scope") == "workspace"


def test_get_skill_registry_cached_by_user_and_workspace():
    """Factory caches per (user_id, workspace_id)."""
    reset_skill_registries()
    r1 = get_skill_registry(user_id="alice", workspace_id="personal")
    r2 = get_skill_registry(user_id="alice", workspace_id="personal")
    r3 = get_skill_registry(user_id="alice", workspace_id="project-x")
    r4 = get_skill_registry(user_id="bob", workspace_id="personal")

    assert r1 is r2
    assert r1 is not r3
    assert r1 is not r4


def test_get_skill_registry_uses_tuple_cache_keys():
    """Factory cache keys keep user/workspace identity structurally separate."""
    from src.skills import registry as skills_registry

    reset_skill_registries()

    r1 = get_skill_registry(user_id="a", workspace_id="b")
    r2 = get_skill_registry(user_id="a-b", workspace_id="personal")

    assert r1 is not r2
    assert set(skills_registry._registries) == {("a", "b"), ("a-b", "personal")}


def test_seeded_skill_deleted_after_reload_is_not_reseeded(tmp_path, monkeypatch):
    """Seed marker makes seeded skills normal user skills after first seed."""
    seed_root = tmp_path / "src" / "skills_seed"
    seeded = seed_root / "seeded-skill"
    seeded.mkdir(parents=True)
    (seeded / "SKILL.md").write_text("""---
name: seeded-skill
description: Seeded Skill
---
Seeded body
""", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    user_dir = tmp_path / "user-skills"
    workspace_dir = tmp_path / "workspace-skills"
    registry = SkillRegistry(skills_dir=user_dir, workspace_skills_dir=workspace_dir)

    assert "seeded-skill" in registry.list_skills()
    assert (user_dir / ".skills_seeded").exists()

    import shutil

    shutil.rmtree(user_dir / "seeded-skill")
    registry.reload()

    assert "seeded-skill" not in registry.list_skills()
