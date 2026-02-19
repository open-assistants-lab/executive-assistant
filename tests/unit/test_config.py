"""Tests for config module."""

import os
import pytest
from pydantic import ValidationError


class TestConfigValidation:
    """Test configuration validation."""

    def test_agent_config_valid(self):
        """Test valid agent configuration."""
        # Import after setting env vars
        os.environ["OLLAMA_API_KEY"] = "test-key"
        os.environ["OLLAMA_BASE_URL"] = "https://api.ollama.cloud/v1"

        from src.config.settings import AgentConfig

        config = AgentConfig(name="Test Agent", model="ollama:test-model")
        assert config.name == "Test Agent"
        assert config.model == "ollama:test-model"

    def test_agent_config_missing_model(self):
        """Test agent config requires model."""
        from src.config.settings import AgentConfig

        with pytest.raises(ValidationError):
            AgentConfig(name="Test Agent")


class TestDatabaseConfig:
    """Test database configuration."""

    def test_database_config(self):
        """Test database configuration."""
        from src.config.settings import DatabaseConfig

        config = DatabaseConfig(
            host="localhost", port=5432, name="test_db", user="test_user", password="test_pass"
        )
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.name == "test_db"

    def test_database_config_default_port(self):
        """Test database default port."""
        from src.config.settings import DatabaseConfig

        config = DatabaseConfig(
            host="localhost", name="test_db", user="test_user", password="test_pass"
        )
        assert config.port == 5432
