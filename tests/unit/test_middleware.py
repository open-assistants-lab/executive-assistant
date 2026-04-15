"""Unit tests for middleware (SDK-native)."""

import tempfile
from unittest.mock import MagicMock


class TestSkillMiddleware:
    """Tests for SkillMiddleware."""

    def test_skill_middleware_init(self):
        """Test SkillMiddleware initialization."""
        from src.sdk.middleware_skill import SkillMiddleware

        middleware = SkillMiddleware(system_dir="src/skills", user_id="test")
        assert middleware is not None
        assert middleware.registry is not None

    def test_skill_middleware_build_skills_prompt_empty(self):
        """Test building skills prompt with no skills."""
        from src.sdk.middleware_skill import SkillMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            middleware = SkillMiddleware(system_dir=tmpdir, user_id="test")
            prompt = middleware._build_skills_prompt()
            assert prompt == ""


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_skill_registry_init(self):
        """Test SkillRegistry initialization."""
        from src.skills.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(system_dir=tmpdir)
            assert registry is not None
