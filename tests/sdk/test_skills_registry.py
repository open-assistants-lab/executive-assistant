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
