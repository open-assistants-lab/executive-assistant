"""Tests for skills system."""

import tempfile
from pathlib import Path

import pytest


class TestSkillParsing:
    """Test skill file parsing."""

    def test_parse_valid_skill(self, tmp_path):
        """Test parsing a valid SKILL.md file."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill for unit testing.
---

# Test Skill

This is the content of the skill.
""")

        skill = parse_skill_file(skill_file)

        assert skill is not None
        assert skill["name"] == "test-skill"
        assert skill["description"] == "A test skill for unit testing."
        assert skill["content"] == "# Test Skill\n\nThis is the content of the skill."
        assert skill["path"] == str(skill_dir)

    def test_parse_skill_with_optional_fields(self, tmp_path):
        """Test parsing SKILL.md with optional fields."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "complex-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: complex-skill
description: A skill with optional fields.
license: MIT
compatibility: Requires Python 3.11+
metadata:
  author: test-author
  version: "1.0"
---

# Content
""")

        skill = parse_skill_file(skill_file)

        assert skill is not None
        assert skill["name"] == "complex-skill"
        assert skill["license"] == "MIT"
        assert skill["compatibility"] == "Requires Python 3.11+"
        assert skill["metadata"] == {"author": "test-author", "version": "1.0"}

    def test_parse_invalid_skill_no_frontmatter(self, tmp_path):
        """Test parsing a file without YAML frontmatter."""
        from src.skills.models import parse_skill_file

        skill_file = tmp_path / "invalid.md"
        skill_file.write_text("# Just Markdown\n\nNo frontmatter")

        skill = parse_skill_file(skill_file)

        assert skill is None

    def test_parse_invalid_skill_missing_name(self, tmp_path):
        """Test parsing skill with missing name."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
description: Missing name field.
---

Content
""")

        skill = parse_skill_file(skill_file)

        assert skill is None

    def test_parse_invalid_skill_missing_description(self, tmp_path):
        """Test parsing skill with missing description."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "no-desc"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: no-desc
---

Content
""")

        skill = parse_skill_file(skill_file)

        assert skill is None

    def test_parse_invalid_skill_uppercase_name(self, tmp_path):
        """Test parsing skill with uppercase in name."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "UpperCase"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: UpperCase
description: Invalid name format.
---

Content
""")

        skill = parse_skill_file(skill_file)

        assert skill is None

    def test_parse_invalid_skill_hyphen_start(self, tmp_path):
        """Test parsing skill with hyphen at start."""
        from src.skills.models import parse_skill_file

        skill_dir = tmp_path / "-invalid"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: -invalid
description: Invalid name format.
---

Content
""")

        skill = parse_skill_file(skill_file)

        assert skill is None


class TestSkillNameValidation:
    """Test skill name validation."""

    def test_valid_names(self):
        """Test valid skill names."""
        from src.skills.models import _is_valid_skill_name

        assert _is_valid_skill_name("pdf-processing") is True
        assert _is_valid_skill_name("sql-analytics") is True
        assert _is_valid_skill_name("code-review") is True
        assert _is_valid_skill_name("a") is True
        assert _is_valid_skill_name("abc123") is True

    def test_invalid_names(self):
        """Test invalid skill names."""
        from src.skills.models import _is_valid_skill_name

        assert _is_valid_skill_name("") is False
        assert _is_valid_skill_name("UpperCase") is False
        assert _is_valid_skill_name("-start") is False
        assert _is_valid_skill_name("end-") is False
        assert _is_valid_skill_name("double--hyphen") is False
        assert _is_valid_skill_name("with_underscore") is False
        assert _is_valid_skill_name("with space") is False


class TestSkillStorage:
    """Test skill storage."""

    def test_load_skills_from_directory(self, tmp_path):
        """Test loading multiple skills from directory."""
        from src.skills.storage import SkillStorage

        # Create skills
        skill1_dir = tmp_path / "skill-one"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
name: skill-one
description: First skill.
---

Content 1
""")

        skill2_dir = tmp_path / "skill-two"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
name: skill-two
description: Second skill.
---

Content 2
""")

        # Create invalid skill (wrong directory name)
        skill3_dir = tmp_path / "wrong-name"
        skill3_dir.mkdir()
        (skill3_dir / "SKILL.md").write_text("""---
name: skill-three
description: Wrong directory name.
---

Content 3
""")

        storage = SkillStorage(tmp_path)
        skills = storage.load_skills()

        assert len(skills) == 2
        names = [s["name"] for s in skills]
        assert "skill-one" in names
        assert "skill-two" in names

    def test_load_specific_skill(self, tmp_path):
        """Test loading a specific skill by name."""
        from src.skills.storage import SkillStorage

        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: A specific skill.
---

Specific content here.
""")

        storage = SkillStorage(tmp_path)
        skill = storage.load_skill("my-skill")

        assert skill is not None
        assert skill["name"] == "my-skill"
        assert skill["content"] == "Specific content here."

    def test_load_nonexistent_skill(self, tmp_path):
        """Test loading a skill that doesn't exist."""
        from src.skills.storage import SkillStorage

        storage = SkillStorage(tmp_path)
        skill = storage.load_skill("nonexistent")

        assert skill is None

    def test_list_skills(self, tmp_path):
        """Test listing skill names."""
        from src.skills.storage import SkillStorage

        skill1_dir = tmp_path / "skill-a"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
name: skill-a
description: Skill A.
---

""")

        skill2_dir = tmp_path / "skill-b"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
name: skill-b
description: Skill B.
---

""")

        storage = SkillStorage(tmp_path)
        names = storage.list_skills()

        assert len(names) == 2
        assert "skill-a" in names
        assert "skill-b" in names


class TestSkillRegistry:
    """Test skill registry."""

    def test_get_all_skills(self, tmp_path):
        """Test getting all skills from registry."""
        from src.skills.registry import SkillRegistry

        # Create system skills
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        (sys_dir / "sys-skill").mkdir()
        (sys_dir / "sys-skill" / "SKILL.md").write_text("""---
name: sys-skill
description: System skill.
---

System content.
""")

        # Create user skills (using base_dir to point to tmp_path)
        user_dir = tmp_path / "user_skills"
        user_dir.mkdir(parents=True)
        (user_dir / "user-skill").mkdir()
        (user_dir / "user-skill" / "SKILL.md").write_text("""---
name: user-skill
description: User skill.
---

User content.
""")

        registry = SkillRegistry(system_dir=str(sys_dir), user_id="user1")
        # Override user storage base_dir for testing
        registry.user_storage = registry.user_storage.__class__("user1", base_dir=str(user_dir))
        skills = registry.get_all_skills()

        assert len(skills) == 2
        names = [s["name"] for s in skills]
        assert "sys-skill" in names
        assert "user-skill" in names

    def test_get_skill_prefers_user(self, tmp_path):
        """Test that user skills take priority over system skills."""
        from src.skills.registry import SkillRegistry

        # Create system skill
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        (sys_dir / "shared-skill").mkdir()
        (sys_dir / "shared-skill" / "SKILL.md").write_text("""---
name: shared-skill
description: System version.
---

System content.
""")

        # Create user skill with same name (using base_dir override)
        user_dir = tmp_path / "user_skills"
        user_dir.mkdir(parents=True)
        (user_dir / "shared-skill").mkdir()
        (user_dir / "shared-skill" / "SKILL.md").write_text("""---
name: shared-skill
description: User version.
---

User content.
""")

        registry = SkillRegistry(system_dir=str(sys_dir), user_id="user1")
        # Override user storage base_dir for testing
        registry.user_storage = registry.user_storage.__class__("user1", base_dir=str(user_dir))
        skill = registry.get_skill("shared-skill")

        assert skill is not None
        assert skill["description"] == "User version."

    def test_reload_clears_cache(self, tmp_path):
        """Test that reload clears the cache."""
        from src.skills.registry import SkillRegistry

        # Create initial skill
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        (sys_dir / "initial-skill").mkdir()
        (sys_dir / "initial-skill" / "SKILL.md").write_text("""---
name: initial-skill
description: Initial version.
---

Initial content.
""")

        registry = SkillRegistry(system_dir=str(sys_dir))
        assert len(registry.get_all_skills()) == 1

        # Add new skill
        (sys_dir / "new-skill").mkdir()
        (sys_dir / "new-skill" / "SKILL.md").write_text("""---
name: new-skill
description: New skill.
---

New content.
""")

        # Without reload - should still have old cache
        assert len(registry.get_all_skills()) == 1

        # With reload - should see new skill
        registry.reload()
        assert len(registry.get_all_skills()) == 2


class TestSkillToSystemPrompt:
    """Test skill to system prompt conversion."""

    def test_skill_to_system_prompt_entry(self):
        """Test converting skill to system prompt entry."""
        from src.skills.models import skill_to_system_prompt_entry, Skill

        skill: Skill = {
            "name": "test-skill",
            "description": "A test skill description.",
            "content": "Full content here.",
            "path": "/path/to/skill",
        }

        result = skill_to_system_prompt_entry(skill)

        assert result == "- **test-skill**: A test skill description."


class TestSkillTools:
    """Test skill tools."""

    def test_load_skill_tool(self, tmp_path):
        """Test load_skill tool."""
        from src.skills.registry import SkillRegistry
        from src.skills.tools import set_skill_registry

        # Create a test skill
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        (sys_dir / "test-skill").mkdir()
        (sys_dir / "test-skill" / "SKILL.md").write_text("""---
name: test-skill
description: A test skill.
---

Full content of the skill.
""")

        # Set up registry
        registry = SkillRegistry(system_dir=str(sys_dir))
        set_skill_registry(registry)

        # Test load_skill tool
        from src.skills.tools import load_skill

        # Without runtime
        result = load_skill.invoke({"skill_name": "test-skill"})
        assert "Full content of the skill" in result

    def test_load_skill_not_found(self, tmp_path):
        """Test load_skill with nonexistent skill."""
        from src.skills.registry import SkillRegistry
        from src.skills.tools import set_skill_registry

        # Set up empty registry
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        registry = SkillRegistry(system_dir=str(sys_dir))
        set_skill_registry(registry)

        from src.skills.tools import load_skill

        result = load_skill.invoke({"skill_name": "nonexistent"})
        assert "not found" in result
        assert "Available skills:" in result

    def test_list_skills_tool(self, tmp_path):
        """Test list_skills tool."""
        from src.skills.registry import SkillRegistry
        from src.skills.tools import set_skill_registry

        # Create skills
        sys_dir = tmp_path / "system"
        sys_dir.mkdir()
        (sys_dir / "skill-one").mkdir()
        (sys_dir / "skill-one" / "SKILL.md").write_text("""---
name: skill-one
description: First skill.
---

""")

        registry = SkillRegistry(system_dir=str(sys_dir))
        set_skill_registry(registry)

        from src.skills.tools import list_skills

        result = list_skills.invoke({})
        assert "skill-one" in result
        assert "First skill" in result
