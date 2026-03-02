"""Unit tests for middleware."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSkillMiddleware:
    """Tests for SkillMiddleware."""

    def test_skill_middleware_init(self):
        """Test SkillMiddleware initialization."""
        from src.skills.middleware import SkillMiddleware

        middleware = SkillMiddleware(system_dir="src/skills", user_id="test")
        assert middleware is not None
        assert middleware.registry is not None

    def test_skill_middleware_build_skills_prompt_empty(self):
        """Test building skills prompt with no skills."""
        from src.skills.middleware import SkillMiddleware

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


class TestAgentFactory:
    """Tests for AgentFactory middleware configuration."""

    def test_agent_factory_init(self):
        """Test AgentFactory initialization."""
        from src.agents.factory import AgentFactory

        factory = AgentFactory(user_id="test")
        assert factory is not None
        assert factory.user_id == "test"

    def test_agent_factory_middleware_disabled(self):
        """Test middleware configuration when disabled."""
        from src.agents.factory import AgentFactory

        with patch("src.agents.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                memory=MagicMock(summarization=MagicMock(enabled=False)),
                filesystem=MagicMock(enabled=False),
            )

            factory = AgentFactory(
                user_id="test",
                enable_summarization=False,
            )
            middleware = factory._get_middleware(MagicMock())
            assert middleware == []


class TestAgentPool:
    """Tests for AgentPool."""

    def test_agent_pool_init(self):
        """Test AgentPool initialization."""
        from src.agents.manager import AgentPool

        pool = AgentPool("test_user", pool_size=3)
        assert pool.user_id == "test_user"
        assert pool.pool_size == 3
