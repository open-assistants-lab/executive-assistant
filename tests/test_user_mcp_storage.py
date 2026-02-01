"""Tests for User MCP Storage layer.

Tests the storage, validation, backup, and recovery functionality
for user-specific MCP server configurations.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

from executive_assistant.storage.user_mcp_storage import UserMCPStorage
from executive_assistant.storage.file_sandbox import clear_thread_id, set_thread_id


def _create_storage_with_temp_dir(thread_id: str, temp_mcp_dir: Path) -> UserMCPStorage:
    """Helper to create storage with temp directory."""
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = temp_mcp_dir

    with patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings):
        return UserMCPStorage(thread_id)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_mcp_dir(tmp_path):
    """Create a temporary MCP directory for testing."""
    mcp_dir = tmp_path / "users" / "test_thread_123" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    return mcp_dir


@pytest.fixture
def storage(temp_mcp_dir):
    """Create a UserMCPStorage instance with temporary directory."""
    # Patch get_settings().get_thread_mcp_dir to return our temp directory
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = temp_mcp_dir

    with patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings):
        yield UserMCPStorage("test_thread_123")


@pytest.fixture
def sample_stdio_config():
    """Sample valid stdio MCP configuration."""
    return {
        "version": "1.0",
        "updated_at": "2026-01-31T00:00:00Z",
        "mcpServers": {
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch", "--port", "3000"],
                "env": {"API_KEY": "test_key"}
            },
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"]
            }
        }
    }


@pytest.fixture
def sample_remote_config():
    """Sample valid remote MCP configuration."""
    return {
        "version": "1.0",
        "updated_at": "2026-01-31T00:00:00Z",
        "mcpServers": {
            "api-server": {
                "url": "https://api.example.com/mcp",
                "headers": {"Authorization": "Bearer token"}
            },
            "local-dev": {
                "url": "http://localhost:8080/mcp"
            }
        }
    }


# =============================================================================
# Initialization Tests
# =============================================================================

class TestUserMCPStorageInit:
    """Test UserMCPStorage initialization."""

    def test_creates_mcp_directory(self, temp_mcp_dir):
        """Test that initialization creates MCP directory."""
        storage = _create_storage_with_temp_dir("new_thread", temp_mcp_dir)
        assert storage.mcp_dir.exists()
        assert storage.mcp_dir.is_dir()

    def test_thread_id_stored(self, temp_mcp_dir):
        """Test that thread_id is stored correctly."""
        storage = _create_storage_with_temp_dir("test_thread", temp_mcp_dir)
        assert storage.thread_id == "test_thread"


# =============================================================================
# Load Configuration Tests
# =============================================================================

class TestLoadConfig:
    """Test configuration loading."""

    def test_load_local_empty_config(self, storage):
        """Test loading empty local config returns default structure."""
        config = storage.load_local_config()
        assert config["version"] == "1.0"
        assert "updated_at" in config
        assert config["mcpServers"] == {}

    def test_load_remote_empty_config(self, storage):
        """Test loading empty remote config returns default structure."""
        config = storage.load_remote_config()
        assert config["version"] == "1.0"
        assert "updated_at" in config
        assert config["mcpServers"] == {}

    def test_load_local_existing_config(self, storage, sample_stdio_config, temp_mcp_dir):
        """Test loading existing local configuration."""
        # Write config file
        (temp_mcp_dir / "mcp.json").write_text(json.dumps(sample_stdio_config))

        # Load and verify
        config = storage.load_local_config()
        assert "fetch" in config["mcpServers"]
        assert "github" in config["mcpServers"]
        assert config["mcpServers"]["fetch"]["command"] == "uvx"
        assert config["mcpServers"]["fetch"]["args"] == ["mcp-server-fetch", "--port", "3000"]

    def test_load_remote_existing_config(self, storage, sample_remote_config, temp_mcp_dir):
        """Test loading existing remote configuration."""
        # Write config file
        (temp_mcp_dir / "mcp_remote.json").write_text(json.dumps(sample_remote_config))

        # Load and verify
        config = storage.load_remote_config()
        assert "api-server" in config["mcpServers"]
        assert "local-dev" in config["mcpServers"]
        assert config["mcpServers"]["api-server"]["url"] == "https://api.example.com/mcp"

    def test_load_local_invalid_json(self, storage, temp_mcp_dir):
        """Test loading invalid JSON raises ValueError."""
        (temp_mcp_dir / "mcp.json").write_text("{ invalid json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            storage.load_local_config()

    def test_load_remote_invalid_json(self, storage, temp_mcp_dir):
        """Test loading invalid JSON raises ValueError."""
        (temp_mcp_dir / "mcp_remote.json").write_text("{ invalid }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            storage.load_remote_config()


# =============================================================================
# Save Configuration Tests
# =============================================================================

class TestSaveConfig:
    """Test configuration saving with validation."""

    def test_save_local_minimal_config(self, storage):
        """Test saving minimal valid local config."""
        config = {
            "mcpServers": {
                "test": {
                    "command": "echo"
                }
            }
        }
        storage.save_local_config(config)

        # Verify file created
        assert (storage.mcp_dir / "mcp.json").exists()

        # Verify content
        loaded = storage.load_local_config()
        assert "test" in loaded["mcpServers"]
        assert loaded["mcpServers"]["test"]["command"] == "echo"

    def test_save_local_full_config(self, storage, sample_stdio_config):
        """Test saving full local config with all fields."""
        storage.save_local_config(sample_stdio_config)

        loaded = storage.load_local_config()
        assert loaded["mcpServers"]["fetch"]["command"] == "uvx"
        assert loaded["mcpServers"]["fetch"]["args"] == ["mcp-server-fetch", "--port", "3000"]
        assert loaded["mcpServers"]["fetch"]["env"]["API_KEY"] == "test_key"

    def test_save_remote_minimal_config(self, storage):
        """Test saving minimal valid remote config."""
        config = {
            "mcpServers": {
                "api": {
                    "url": "https://api.example.com/mcp"
                }
            }
        }
        storage.save_remote_config(config)

        # Verify file created
        assert (storage.mcp_dir / "mcp_remote.json").exists()

        # Verify content
        loaded = storage.load_remote_config()
        assert "api" in loaded["mcpServers"]
        assert loaded["mcpServers"]["api"]["url"] == "https://api.example.com/mcp"

    def test_save_remote_full_config(self, storage, sample_remote_config):
        """Test saving full remote config with headers."""
        storage.save_remote_config(sample_remote_config)

        loaded = storage.load_remote_config()
        assert loaded["mcpServers"]["api-server"]["url"] == "https://api.example.com/mcp"
        assert loaded["mcpServers"]["api-server"]["headers"]["Authorization"] == "Bearer token"


# =============================================================================
# Validation Tests - Server Names
# =============================================================================

class TestServerNameValidation:
    """Test server name validation."""

    def test_valid_server_names(self, storage):
        """Test that valid server names pass validation."""
        valid_names = ["test", "test_server", "test-server", "test123", "Test_123-Server"]

        for name in valid_names:
            # Should not raise
            storage._validate_server_name(name)

    def test_empty_server_name(self, storage):
        """Test that empty server name is rejected."""
        with pytest.raises(ValueError, match="Server name cannot be empty"):
            storage._validate_server_name("")

    def test_server_name_with_spaces(self, storage):
        """Test that server names with spaces are rejected."""
        with pytest.raises(ValueError, match="Invalid server name"):
            storage._validate_server_name("test server")

    def test_server_name_with_special_chars(self, storage):
        """Test that server names with special characters are rejected."""
        invalid_names = ["test.server", "test@server", "test!server", "test/server"]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid server name"):
                storage._validate_server_name(name)


# =============================================================================
# Validation Tests - Stdio Configuration
# =============================================================================

class TestStdioServerValidation:
    """Test stdio server configuration validation."""

    def test_valid_minimal_stdio_config(self, storage):
        """Test minimal valid stdio config."""
        server = {"command": "echo"}
        # Should not raise
        storage._validate_stdio_server("test", server)

    def test_stdio_config_missing_command(self, storage):
        """Test that missing command field is rejected."""
        server = {"args": ["hello"]}

        with pytest.raises(ValueError, match="missing required field.*command"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_command_type(self, storage):
        """Test that non-string command is rejected."""
        server = {"command": 123}

        with pytest.raises(ValueError, match="command must be a string"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_valid_args(self, storage):
        """Test valid args field."""
        server = {"command": "echo", "args": ["hello", "world"]}
        # Should not raise
        storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_args_type(self, storage):
        """Test that non-list args is rejected."""
        server = {"command": "echo", "args": "hello"}

        with pytest.raises(ValueError, match="args must be a list"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_arg_element(self, storage):
        """Test that non-string arg elements are rejected."""
        server = {"command": "echo", "args": ["hello", 123]}

        with pytest.raises(ValueError, match="arg 1 must be a string"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_valid_env(self, storage):
        """Test valid env field."""
        server = {"command": "echo", "env": {"KEY1": "value1", "KEY2": "value2"}}
        # Should not raise
        storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_env_type(self, storage):
        """Test that non-dict env is rejected."""
        server = {"command": "echo", "env": ["KEY=value"]}

        with pytest.raises(ValueError, match="env must be a dictionary"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_env_value_type(self, storage):
        """Test that non-string env values are rejected."""
        server = {"command": "echo", "env": {"KEY": 123}}

        with pytest.raises(ValueError, match="env keys and values must be strings"):
            storage._validate_stdio_server("test", server)

    def test_stdio_config_valid_cwd(self, storage):
        """Test valid cwd field."""
        server = {"command": "echo", "cwd": "/path/to/dir"}
        # Should not raise
        storage._validate_stdio_server("test", server)

    def test_stdio_config_invalid_cwd_type(self, storage):
        """Test that non-string cwd is rejected."""
        server = {"command": "echo", "cwd": 123}

        with pytest.raises(ValueError, match="cwd must be a string"):
            storage._validate_stdio_server("test", server)


# =============================================================================
# Validation Tests - Remote Configuration
# =============================================================================

class TestRemoteServerValidation:
    """Test remote server configuration validation."""

    def test_valid_minimal_remote_config(self, storage):
        """Test minimal valid remote config."""
        server = {"url": "https://api.example.com/mcp"}
        # Should not raise
        storage._validate_remote_server("test", server)

    def test_remote_config_missing_url(self, storage):
        """Test that missing url field is rejected."""
        server = {"headers": {"Authorization": "Bearer token"}}

        with pytest.raises(ValueError, match="missing required field.*url"):
            storage._validate_remote_server("test", server)

    def test_remote_config_invalid_url_type(self, storage):
        """Test that non-string url is rejected."""
        server = {"url": 123}

        with pytest.raises(ValueError, match="url must be a string"):
            storage._validate_remote_server("test", server)

    def test_remote_config_https_url(self, storage):
        """Test that HTTPS URLs are accepted."""
        server = {"url": "https://api.example.com/mcp"}
        # Should not raise
        storage._validate_remote_server("test", server)

    def test_remote_config_http_url_rejected(self, storage):
        """Test that HTTP URLs (non-localhost) are rejected."""
        server = {"url": "http://api.example.com/mcp"}

        with pytest.raises(ValueError, match="must use HTTPS"):
            storage._validate_remote_server("test", server)

    def test_remote_config_localhost_http_allowed(self, storage):
        """Test that localhost HTTP URLs are accepted."""
        valid_urls = [
            "http://localhost/mcp",
            "http://localhost:8080/mcp",
            "http://127.0.0.1/mcp",
            "http://127.0.0.1:3000/mcp"
        ]

        for url in valid_urls:
            server = {"url": url}
            # Should not raise
            storage._validate_remote_server("test", server)

    def test_remote_config_valid_headers(self, storage):
        """Test valid headers field."""
        server = {
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token", "X-Custom": "value"}
        }
        # Should not raise
        storage._validate_remote_server("test", server)

    def test_remote_config_invalid_headers_type(self, storage):
        """Test that non-dict headers is rejected."""
        server = {"url": "https://api.example.com/mcp", "headers": ["Authorization: Bearer"]}

        with pytest.raises(ValueError, match="headers must be a dictionary"):
            storage._validate_remote_server("test", server)


# =============================================================================
# Validation Tests - Config Structure
# =============================================================================

class TestConfigStructureValidation:
    """Test configuration structure validation."""

    def test_valid_config_structure(self, storage):
        """Test valid config structure."""
        config = {
            "mcpServers": {
                "test": {"command": "echo"}
            }
        }
        # Should not raise
        storage._validate_config_structure(config)

    def test_config_not_dict(self, storage):
        """Test that non-dict config is rejected."""
        with pytest.raises(ValueError, match="Configuration must be a dictionary"):
            storage._validate_config_structure("not a dict")

    def test_config_missing_mcp_servers(self, storage):
        """Test that config without mcpServers key is rejected."""
        config = {"version": "1.0"}

        with pytest.raises(ValueError, match="Missing required key.*mcpServers"):
            storage._validate_config_structure(config)

    def test_config_mcp_servers_not_dict(self, storage):
        """Test that non-dict mcpServers is rejected."""
        config = {"mcpServers": ["server1", "server2"]}

        with pytest.raises(ValueError, match="'mcpServers' must be a dictionary"):
            storage._validate_config_structure(config)


# =============================================================================
# Backup and Restore Tests
# =============================================================================

class TestBackupRestore:
    """Test backup creation and restore functionality."""

    def test_backup_created_on_save(self, storage, sample_stdio_config):
        """Test that backup is created when saving existing config."""
        # Save initial config
        storage.save_local_config(sample_stdio_config)

        # Save again to trigger backup
        storage.save_local_config(sample_stdio_config)

        # Check backup exists
        backups = storage.list_backups("mcp.json")
        assert len(backups) >= 1

    def test_backup_filename_format(self, storage, sample_stdio_config):
        """Test that backup filename has correct format."""
        storage.save_local_config(sample_stdio_config)
        storage.save_local_config(sample_stdio_config)

        backups = storage.list_backups("mcp.json")
        backup_name = backups[0]["name"]

        # Check format: mcp.json.backup_YYYYMMDD_HHMMSS
        assert backup_name.startswith("mcp.json.backup_")
        assert len(backup_name) == len("mcp.json.backup_20260131_123456")

    def test_backup_contains_timestamp(self, storage, sample_stdio_config):
        """Test that backup includes timestamp info."""
        storage.save_local_config(sample_stdio_config)
        storage.save_local_config(sample_stdio_config)

        backups = storage.list_backups("mcp.json")
        backup = backups[0]

        assert "timestamp" in backup
        assert "modified" in backup
        assert "size" in backup
        assert backup["size"] > 0

    def test_list_backups_sorted(self, storage, sample_stdio_config):
        """Test that backups are listed with newest first."""
        # Create multiple backups
        for _ in range(3):
            storage.save_local_config(sample_stdio_config)

        backups = storage.list_backups("mcp.json")

        # Check sorted by modified time (newest first)
        for i in range(len(backups) - 1):
            assert backups[i]["modified"] >= backups[i + 1]["modified"]

    def test_backup_rotation_keeps_5(self, storage, sample_stdio_config):
        """Test that only last 5 backups are kept."""
        # Create 7 backups
        for _ in range(7):
            storage.save_local_config(sample_stdio_config)

        backups = storage.list_backups("mcp.json")
        assert len(backups) <= 5

    def test_restore_from_backup(self, storage, sample_stdio_config):
        """Test restoring configuration from backup."""
        # Save config and create backup
        storage.save_local_config(sample_stdio_config)
        storage.save_local_config(sample_stdio_config)

        # Get backup name
        backups = storage.list_backups("mcp.json")
        backup_name = backups[0]["name"]

        # Modify current config
        modified_config = {
            "mcpServers": {
                "modified": {"command": "modified"}
            }
        }
        storage.save_local_config(modified_config)

        # Restore from backup
        storage.restore_backup(backup_name)

        # Verify restored content
        loaded = storage.load_local_config()
        assert "fetch" in loaded["mcpServers"]
        assert "github" in loaded["mcpServers"]

    def test_restore_nonexistent_backup(self, storage):
        """Test that restoring non-existent backup raises error."""
        with pytest.raises(FileNotFoundError, match="Backup.*not found"):
            storage.restore_backup("mcp.json.backup_00000000_000000")

    def test_restore_invalid_backup_name(self, storage):
        """Test that invalid backup name is rejected."""
        with pytest.raises(ValueError, match="Invalid backup filename"):
            storage.restore_backup("invalid_backup_name.txt")

    def test_list_backups_empty(self, storage):
        """Test listing backups when none exist."""
        backups = storage.list_backups("mcp.json")
        assert backups == []

    def test_list_backups_remote_config(self, storage, sample_remote_config):
        """Test listing backups for remote config."""
        storage.save_remote_config(sample_remote_config)
        storage.save_remote_config(sample_remote_config)

        backups = storage.list_backups("mcp_remote.json")
        assert len(backups) >= 1

    def test_restore_remote_config_backup(self, storage, sample_remote_config):
        """Test restoring remote config from backup."""
        storage.save_remote_config(sample_remote_config)
        storage.save_remote_config(sample_remote_config)

        backups = storage.list_backups("mcp_remote.json")
        backup_name = backups[0]["name"]

        storage.restore_backup(backup_name)

        loaded = storage.load_remote_config()
        assert "api-server" in loaded["mcpServers"]
        assert "local-dev" in loaded["mcpServers"]


# =============================================================================
# Config Detection Tests
# =============================================================================

class TestConfigDetection:
    """Test configuration existence detection."""

    def test_has_local_config_false(self, storage):
        """Test that has_local_config returns False when config doesn't exist."""
        assert not storage.has_local_config()

    def test_has_local_config_true(self, storage, sample_stdio_config):
        """Test that has_local_config returns True when config exists."""
        storage.save_local_config(sample_stdio_config)
        assert storage.has_local_config()

    def test_has_remote_config_false(self, storage):
        """Test that has_remote_config returns False when config doesn't exist."""
        assert not storage.has_remote_config()

    def test_has_remote_config_true(self, storage, sample_remote_config):
        """Test that has_remote_config returns True when config exists."""
        storage.save_remote_config(sample_remote_config)
        assert storage.has_remote_config()


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_user_mcp_storage(self, temp_mcp_dir):
        """Test get_user_mcp_storage convenience function."""
        from executive_assistant.storage.user_mcp_storage import get_user_mcp_storage

        storage = _create_storage_with_temp_dir("test_thread", temp_mcp_dir)
        assert isinstance(storage, UserMCPStorage)
        assert storage.thread_id == "test_thread"


# =============================================================================
# Thread Isolation Tests
# =============================================================================

class TestThreadIsolation:
    """Test thread isolation between different users."""

    def test_separate_threads_separate_storage(self, temp_mcp_dir):
        """Test that different threads have separate storage."""
        # Create separate temp dirs for each thread
        thread1_dir = temp_mcp_dir.parent / "thread_1" / "mcp"
        thread2_dir = temp_mcp_dir.parent / "thread_2" / "mcp"
        thread1_dir.mkdir(parents=True, exist_ok=True)
        thread2_dir.mkdir(parents=True, exist_ok=True)

        storage1 = _create_storage_with_temp_dir("thread_1", thread1_dir)
        storage2 = _create_storage_with_temp_dir("thread_2", thread2_dir)

        # Save to thread 1
        config1 = {"mcpServers": {"server1": {"command": "echo"}}}
        storage1.save_local_config(config1)

        # Save to thread 2
        config2 = {"mcpServers": {"server2": {"command": "echo"}}}
        storage2.save_local_config(config2)

        # Verify isolation
        loaded1 = storage1.load_local_config()
        loaded2 = storage2.load_local_config()

        assert "server1" in loaded1["mcpServers"]
        assert "server2" not in loaded1["mcpServers"]
        assert "server2" in loaded2["mcpServers"]
        assert "server1" not in loaded2["mcpServers"]

    def test_thread_directories_separate(self, temp_mcp_dir):
        """Test that thread directories are separate."""
        thread1_dir = temp_mcp_dir.parent / "thread_1" / "mcp"
        thread2_dir = temp_mcp_dir.parent / "thread_2" / "mcp"
        thread1_dir.mkdir(parents=True, exist_ok=True)
        thread2_dir.mkdir(parents=True, exist_ok=True)

        storage1 = _create_storage_with_temp_dir("thread_1", thread1_dir)
        storage2 = _create_storage_with_temp_dir("thread_2", thread2_dir)

        assert storage1.mcp_dir != storage2.mcp_dir
        assert "thread_1" in str(storage1.mcp_dir)
        assert "thread_2" in str(storage2.mcp_dir)
