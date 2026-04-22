"""Unit tests for middleware (SDK-native)."""

import tempfile


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_skill_registry_init(self):
        """Test SkillRegistry initialization."""
        from src.skills.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(system_dir=tmpdir)
            assert registry is not None
