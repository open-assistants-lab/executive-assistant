"""Tests for skill resource enumeration and SKILL_DIR substitution."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from src.sdk.tools_core.skills import skills_load


class TestSkillResourceEnumeration:
    def test_skills_load_includes_resource_listing(self):
        """skills_load() enumerates supporting files in the skill directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: Test\n---\n\nDo the thing."
            )
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "run.sh").write_text("echo hello")
            (skill_dir / "references").mkdir()
            (skill_dir / "references" / "guide.md").write_text("# Guide")
            (skill_dir / "assets").mkdir()
            (skill_dir / "assets" / "template.json").write_text('{"key": "val"}')

            with patch("src.sdk.tools_core.skills.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "my-skill",
                    "content": "Do the thing.",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "my-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert "Do the thing." in result
                assert "Skill directory:" in result
                assert "scripts/run.sh" in result
                assert "references/guide.md" in result
                assert "assets/template.json" in result
                assert "SKILL_DIR" not in result

    def test_skills_load_substitutes_skill_dir_placeholder(self):
        """${SKILL_DIR} in skill content is replaced with the skill directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "sub-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sub-skill\ndescription: Test\n---\n\nRun ${SKILL_DIR}/scripts/build.sh"
            )
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "build.sh").write_text("echo built")

            with patch("src.sdk.tools_core.skills.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "sub-skill",
                    "content": "Run ${SKILL_DIR}/scripts/build.sh",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "sub-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert str(skill_dir) in result
                assert "${SKILL_DIR}" not in result

    def test_skills_load_with_empty_skill_dir(self):
        """Skill with no supporting files doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "empty-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: empty-skill\ndescription: Test\n---\n\nJust content."
            )

            with patch("src.sdk.tools_core.skills.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "empty-skill",
                    "content": "Just content.",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "empty-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert "Just content." in result
