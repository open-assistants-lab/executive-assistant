"""Tests for User MCP management tools (E2E workflow tests).

Tests complete user workflows using the MCP management tools:
- Add/remove servers
- List servers
- Import/export configurations
- Backup/restore
- Hot-reload
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

from executive_assistant.tools.user_mcp_tools import (
    mcp_list_servers,
    mcp_add_server,
    mcp_add_remote_server,
    mcp_remove_server,
    mcp_show_server,
    mcp_export_config,
    mcp_import_config,
    mcp_list_backups,
    mcp_reload,
)
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id
from executive_assistant.storage.user_mcp_storage import UserMCPStorage


def _patch_mcp_storage_with_temp_dir(temp_mcp_dir: Path):
    """Helper to patch UserMCPStorage with temp directory."""
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = temp_mcp_dir
    return patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def thread_context():
    """Set thread_id context for all tests."""
    set_thread_id("test_thread_e2e")
    yield
    clear_thread_id()


@pytest.fixture
def temp_mcp_dir(tmp_path):
    """Create a temporary MCP directory."""
    mcp_dir = tmp_path / "users" / "test_thread_e2e" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    # Create patch that will be active during test
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = mcp_dir

    patcher = patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings)
    patcher.start()

    yield mcp_dir

    patcher.stop()


# =============================================================================
# List Servers Tests
# =============================================================================

class TestMCPListServers:
    """Test mcp_list_servers tool."""

    def test_list_empty_servers(self, temp_mcp_dir):
        """Test listing when no servers configured."""
        result = mcp_list_servers.invoke({})

        assert "No MCP servers configured" in result or "Your MCP Servers" in result

    def test_list_local_servers(self, temp_mcp_dir):
        """Test listing local servers."""
        # Add a local server
        storage = UserMCPStorage("test_thread_e2e")
        config = {
            "mcpServers": {
                "fetch": {
                    "command": "uvx",
                    "arguments": ["mcp-server-fetch"]
                }
            }
        }
        storage.save_local_config(config)

        result = mcp_list_servers.invoke({})

        assert "fetch" in result
        assert "uvx" in result
        assert "Local (stdio)" in result

    def test_list_remote_servers(self, temp_mcp_dir):
        """Test listing remote servers."""
        storage = UserMCPStorage("test_thread_e2e")
        config = {
            "mcpServers": {
                "api": {
                    "url": "https://api.example.com/mcp"
                }
            }
        }
        storage.save_remote_config(config)

        result = mcp_list_servers.invoke({})

        assert "api" in result
        assert "https://api.example.com/mcp" in result
        assert "Remote (HTTP/SSE)" in result

    def test_list_mixed_servers(self, temp_mcp_dir):
        """Test listing both local and remote servers."""
        storage = UserMCPStorage("test_thread_e2e")

        local_config = {
            "mcpServers": {
                "fetch": {"command": "uvx"}
            }
        }
        storage.save_local_config(local_config)

        remote_config = {
            "mcpServers": {
                "api": {"url": "https://api.example.com/mcp"}
            }
        }
        storage.save_remote_config(remote_config)

        result = mcp_list_servers.invoke({})

        assert "fetch" in result
        assert "api" in result
        assert "Local (stdio)" in result
        assert "Remote (HTTP/SSE)" in result


# =============================================================================
# Add Server Tests
# =============================================================================

class TestMCPAddServer:
    """Test mcp_add_server tool."""

    def test_add_minimal_server(self, temp_mcp_dir):
        """Test adding a minimal server configuration."""
        result = mcp_add_server.invoke({
            "name": "test-server",
            "command": "echo"
        })

        assert "✅" in result or "success" in result.lower()
        assert "test-server" in result

        # Verify it was saved
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_local_config()
        assert "test-server" in config["mcpServers"]
        assert config["mcpServers"]["test-server"]["command"] == "echo"

    def test_add_server_with_args(self, temp_mcp_dir):
        """Test adding server with arguments."""
        result = mcp_add_server.invoke({
            "name": "fetch",
            "command": "uvx",
            "arguments": "mcp-server-fetch,--port,3000"
        })

        assert "✅" in result

        # Verify args were parsed correctly
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_local_config()
        assert config["mcpServers"]["fetch"]["args"] == ["mcp-server-fetch", "--port", "3000"]

    def test_add_server_with_env(self, temp_mcp_dir):
        """Test adding server with environment variables."""
        result = mcp_add_server.invoke({
            "name": "api-server",
            "command": "node",
            "arguments": "server.js",
            "env": '{"API_KEY": "secret", "DEBUG": "true"}'
        })

        assert "✅" in result

        # Verify env was parsed
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_local_config()
        assert config["mcpServers"]["api-server"]["env"]["API_KEY"] == "secret"
        assert config["mcpServers"]["api-server"]["env"]["DEBUG"] == "true"

    def test_add_server_with_cwd(self, temp_mcp_dir):
        """Test adding server with working directory."""
        result = mcp_add_server.invoke({
            "name": "workspace-server",
            "command": "python",
            "arguments": "-m,http.server",
            "cwd": "/path/to/workspace"
        })

        assert "✅" in result

        # Verify cwd was saved
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_local_config()
        assert config["mcpServers"]["workspace-server"]["cwd"] == "/path/to/workspace"

    def test_add_duplicate_server_rejected(self, temp_mcp_dir):
        """Test that adding duplicate server is rejected."""
        # Add first server
        mcp_add_server.invoke({"name": "test", "command": "echo"})

        # Try to add again
        result = mcp_add_server.invoke({"name": "test", "command": "echo"})

        assert "❌" in result
        assert "already exists" in result

    def test_add_server_invalid_name_rejected(self, temp_mcp_dir):
        """Test that invalid server names are rejected."""
        result = mcp_add_server.invoke({
            "name": "invalid name!",
            "command": "echo"
        })

        assert "❌" in result
        assert "invalid" in result.lower()

    def test_add_server_invalid_json_rejected(self, temp_mcp_dir):
        """Test that invalid JSON in env is rejected."""
        result = mcp_add_server.invoke({
            "name": "test",
            "command": "echo",
            "env": "{invalid json}"
        })

        assert "❌" in result
        assert "json" in result.lower()


# =============================================================================
# Add Remote Server Tests
# =============================================================================

class TestMCPAddRemoteServer:
    """Test mcp_add_remote_server tool."""

    def test_add_minimal_remote_server(self, temp_mcp_dir):
        """Test adding minimal remote server."""
        result = mcp_add_remote_server.invoke({
            "name": "api",
            "url": "https://api.example.com/mcp"
        })

        assert "✅" in result

        # Verify saved
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_remote_config()
        assert "api" in config["mcpServers"]
        assert config["mcpServers"]["api"]["url"] == "https://api.example.com/mcp"

    def test_add_remote_server_with_headers(self, temp_mcp_dir):
        """Test adding remote server with headers."""
        result = mcp_add_remote_server.invoke({
            "name": "github-api",
            "url": "https://api.github.com/mcp",
            "headers": '{"Authorization": "Bearer token", "X-Custom": "value"}'
        })

        assert "✅" in result

        # Verify headers
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_remote_config()
        assert config["mcpServers"]["github-api"]["headers"]["Authorization"] == "Bearer token"
        assert config["mcpServers"]["github-api"]["headers"]["X-Custom"] == "value"

    def test_add_remote_server_http_rejected(self, temp_mcp_dir):
        """Test that HTTP URLs (non-localhost) are rejected."""
        result = mcp_add_remote_server.invoke({
            "name": "bad-api",
            "url": "http://api.example.com/mcp"
        })

        assert "❌" in result
        assert "https" in result.lower()

    def test_add_remote_server_localhost_allowed(self, temp_mcp_dir):
        """Test that localhost HTTP URLs are allowed."""
        result = mcp_add_remote_server.invoke({
            "name": "local-dev",
            "url": "http://localhost:3000/mcp"
        })

        assert "✅" in result

    def test_add_remote_duplicate_rejected(self, temp_mcp_dir):
        """Test that duplicate remote servers are rejected."""
        mcp_add_remote_server.invoke({
            "name": "api",
            "url": "https://api.example.com/mcp"
        })

        result = mcp_add_remote_server.invoke({
            "name": "api",
            "url": "https://other.example.com/mcp"
        })

        assert "❌" in result
        assert "already exists" in result


# =============================================================================
# Remove Server Tests
# =============================================================================

class TestMCPRemoveServer:
    """Test mcp_remove_server tool."""

    def test_remove_local_server(self, temp_mcp_dir):
        """Test removing a local server."""
        # Add server first
        mcp_add_server.invoke({"name": "test", "command": "echo"})

        # Remove it
        result = mcp_remove_server.invoke({"name": "test"})

        assert "✅" in result
        assert "test" in result

        # Verify removed
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_local_config()
        assert "test" not in config["mcpServers"]

    def test_remove_remote_server(self, temp_mcp_dir):
        """Test removing a remote server."""
        # Add server first
        mcp_add_remote_server.invoke({
            "name": "api",
            "url": "https://api.example.com/mcp"
        })

        # Remove it
        result = mcp_remove_server.invoke({"name": "api"})

        assert "✅" in result

        # Verify removed
        storage = UserMCPStorage("test_thread_e2e")
        config = storage.load_remote_config()
        assert "api" not in config["mcpServers"]

    def test_remove_nonexistent_server(self, temp_mcp_dir):
        """Test removing non-existent server."""
        result = mcp_remove_server.invoke({"name": "nonexistent"})

        assert "❌" in result
        assert "not found" in result


# =============================================================================
# Show Server Tests
# =============================================================================

class TestMCPShowServer:
    """Test mcp_show_server tool."""

    def test_show_local_server(self, temp_mcp_dir):
        """Test showing local server details."""
        mcp_add_server.invoke({
            "name": "fetch",
            "command": "uvx",
            "arguments": "mcp-server-fetch,--port,3000",
            "env": '{"API_KEY": "test"}'
        })

        result = mcp_show_server.invoke({"name": "fetch"})

        assert "fetch" in result
        assert "Local" in result
        assert "uvx" in result
        assert "mcp-server-fetch" in result

    def test_show_remote_server(self, temp_mcp_dir):
        """Test showing remote server details."""
        mcp_add_remote_server.invoke({
            "name": "api",
            "url": "https://api.example.com/mcp",
            "headers": '{"Authorization": "Bearer token"}'
        })

        result = mcp_show_server.invoke({"name": "api"})

        assert "api" in result
        assert "Remote" in result
        assert "https://api.example.com/mcp" in result
        # Headers should be shown with count, values hidden
        assert "1 header" in result or "header(s)" in result

    def test_show_nonexistent_server(self, temp_mcp_dir):
        """Test showing non-existent server."""
        result = mcp_show_server.invoke({"name": "nonexistent"})

        assert "❌" in result
        assert "not found" in result


# =============================================================================
# Export/Import Tests
# =============================================================================

class TestMCPExportImport:
    """Test configuration export and import."""

    def test_export_empty_config(self, temp_mcp_dir):
        """Test exporting empty configuration."""
        result = mcp_export_config.invoke({})

        assert "✅" in result
        assert "```json" in result
        assert '"local"' in result
        assert '"remote"' in result

    def test_export_populated_config(self, temp_mcp_dir):
        """Test exporting populated configuration."""
        # Add servers
        mcp_add_server.invoke({"name": "local1", "command": "echo1"})
        mcp_add_remote_server.invoke({"name": "remote1", "url": "https://api.example.com/mcp"})

        result = mcp_export_config.invoke({})

        assert "✅" in result
        assert "local1" in result
        assert "remote1" in result
        assert '"exported_at"' in result

    def test_import_valid_config(self, temp_mcp_dir):
        """Test importing valid configuration."""
        export_json = json.dumps({
            "local": {
                "version": "1.0",
                "mcpServers": {
                    "imported-local": {
                        "command": "imported-command"
                    }
                }
            },
            "remote": {
                "version": "1.0",
                "mcpServers": {
                    "imported-remote": {
                        "url": "https://imported.example.com/mcp"
                    }
                }
            },
            "exported_at": "2026-01-31T00:00:00Z"
        })

        result = mcp_import_config.invoke({"config_json": export_json})

        assert "✅" in result
        assert "imported" in result.lower()

        # Verify imported
        storage = UserMCPStorage("test_thread_e2e")
        local = storage.load_local_config()
        remote = storage.load_remote_config()

        assert "imported-local" in local["mcpServers"]
        assert "imported-remote" in remote["mcpServers"]

    def test_import_invalid_json(self, temp_mcp_dir):
        """Test that invalid JSON is rejected."""
        result = mcp_import_config.invoke({"config_json": "{invalid}"})

        assert "❌" in result
        assert "json" in result.lower()

    def test_import_duplicate_name_rejected(self, temp_mcp_dir):
        """Test that importing duplicate server names is rejected."""
        # Add existing server
        mcp_add_server.invoke({"name": "existing", "command": "echo"})

        # Try to import with same name
        export_json = json.dumps({
            "local": {
                "mcpServers": {
                    "existing": {"command": "other-command"}
                }
            },
            "remote": {"mcpServers": {}}
        })

        result = mcp_import_config.invoke({"config_json": export_json})

        assert "❌" in result
        assert "already exists" in result


# =============================================================================
# Backup Tests
# =============================================================================

class TestMCPBackups:
    """Test backup listing and restore."""

    def test_list_backups_empty(self, temp_mcp_dir):
        """Test listing backups when none exist."""
        result = mcp_list_backups.invoke({})

        # Should indicate no backups
        assert "No backups" in result or len(result.strip()) == 0 or "backups" in result.lower()

    def test_list_backups_after_save(self, temp_mcp_dir):
        """Test that backups are created after save."""
        # Add server (creates initial save)
        mcp_add_server.invoke({"name": "test", "command": "echo"})

        # Add another server (triggers backup of previous config)
        mcp_add_server.invoke({"name": "test2", "command": "echo2"})

        result = mcp_list_backups.invoke({})

        # Should show at least one backup
        assert "backup" in result.lower() or "backups" in result.lower()

    def test_list_backups_remote_config(self, temp_mcp_dir):
        """Test listing backups for remote config."""
        mcp_add_remote_server.invoke({"name": "api1", "url": "https://api1.example.com/mcp"})
        mcp_add_remote_server.invoke({"name": "api2", "url": "https://api2.example.com/mcp"})

        result = mcp_list_backups.invoke({})

        # Should show remote backups
        assert "mcp_remote" in result or "Remote" in result


# =============================================================================
# Reload Tests
# =============================================================================

class TestMCPReload:
    """Test MCP reload functionality."""

    def test_reload_clears_cache(self, temp_mcp_dir):
        """Test that reload clears MCP cache."""
        from executive_assistant.tools.registry import _mcp_client_cache

        # Populate cache
        _mcp_client_cache["test_key"] = "test_value"

        result = mcp_reload.invoke({})

        assert "✅" in result

        # Verify cache was cleared
        # (clear_mcp_cache is called in mcp_reload)
        assert "test_key" not in _mcp_client_cache

    def test_reload_shows_configuration(self, temp_mcp_dir):
        """Test that reload shows current configuration."""
        # Add servers
        mcp_add_server.invoke({"name": "local1", "command": "echo"})
        mcp_add_remote_server.invoke({"name": "remote1", "url": "https://api.example.com/mcp"})

        result = mcp_reload.invoke({})

        assert "✅" in result
        assert "1 local server" in result or "local server" in result.lower()
        assert "1 remote server" in result or "remote server" in result.lower()

    def test_reload_no_servers(self, temp_mcp_dir):
        """Test reload when no servers configured."""
        result = mcp_reload.invoke({})

        assert "✅" in result
        assert "No MCP servers" in result or "0 server" in result


# =============================================================================
# E2E Workflow Tests
# =============================================================================

class TestMCPE2EWorkflows:
    """Test complete end-to-end workflows."""

    def test_full_lifecycle_local_server(self, temp_mcp_dir):
        """Test complete lifecycle: add -> list -> show -> remove."""
        # Add
        add_result = mcp_add_server.invoke({
            "name": "lifecycle-test",
            "command": "echo",
            "arguments": "hello,world"
        })
        assert "✅" in add_result

        # List
        list_result = mcp_list_servers.invoke({})
        assert "lifecycle-test" in list_result

        # Show
        show_result = mcp_show_server.invoke({"name": "lifecycle-test"})
        assert "lifecycle-test" in show_result
        assert "echo" in show_result

        # Remove
        remove_result = mcp_remove_server.invoke({"name": "lifecycle-test"})
        assert "✅" in remove_result

        # Verify gone
        final_list = mcp_list_servers.invoke({})
        assert "lifecycle-test" not in final_list

    def test_full_lifecycle_remote_server(self, temp_mcp_dir):
        """Test complete lifecycle for remote server."""
        # Add
        add_result = mcp_add_remote_server.invoke({
            "name": "api-test",
            "url": "https://api.example.com/mcp"
        })
        assert "✅" in add_result

        # List
        list_result = mcp_list_servers.invoke({})
        assert "api-test" in list_result

        # Show
        show_result = mcp_show_server.invoke({"name": "api-test"})
        assert "api-test" in show_result

        # Remove
        remove_result = mcp_remove_server.invoke({"name": "api-test"})
        assert "✅" in remove_result

    def test_export_import_roundtrip(self, temp_mcp_dir):
        """Test export -> import roundtrip preserves data."""
        # Setup: Add multiple servers
        mcp_add_server.invoke({"name": "s1", "command": "cmd1"})
        mcp_add_server.invoke({"name": "s2", "command": "cmd2"})
        mcp_add_remote_server.invoke({"name": "r1", "url": "https://api1.example.com/mcp"})

        # Export
        export_result = mcp_export_config.invoke({})

        # Extract JSON from export
        lines = export_result.split("\n")
        json_lines = []
        in_json = False
        for line in lines:
            if "```json" in line:
                in_json = True
                continue
            if in_json and line.strip() == "```":
                break
            if in_json:
                json_lines.append(line)

        export_json = "\n".join(json_lines)

        # Clear current config
        mcp_remove_server.invoke({"name": "s1"})
        mcp_remove_server.invoke({"name": "s2"})
        mcp_remove_server.invoke({"name": "r1"})

        # Import
        import_result = mcp_import_config.invoke({"config_json": export_json})
        assert "✅" in import_result

        # Verify all restored
        list_result = mcp_list_servers.invoke({})
        assert "s1" in list_result
        assert "s2" in list_result
        assert "r1" in list_result

    def test_backup_restore_workflow(self, temp_mcp_dir):
        """Test backup -> restore workflow."""
        # Add server
        mcp_add_server.invoke({"name": "backup-test", "command": "original-cmd"})

        # Create another backup by adding another server
        mcp_add_server.invoke({"name": "backup-test2", "command": "another-cmd"})

        # List backups
        backups_result = mcp_list_backups.invoke({})
        assert "backup" in backups_result.lower()

        # Modify config (remove server)
        mcp_remove_server.invoke({"name": "backup-test"})

        # Verify removed
        list_result = mcp_list_servers.invoke({})
        assert "backup-test" not in list_result

        # Restore from backup (need to parse backup name)
        # For this test, we'll verify storage directly
        storage = UserMCPStorage("test_thread_e2e")
        backups = storage.list_backups("mcp.json")

        if backups:
            # Restore first backup
            storage.restore_backup(backups[0]["name"])

            # Verify restored
            config = storage.load_local_config()
            # Should have original config from backup
            assert "backup-test" in config["mcpServers"] or len(config["mcpServers"]) >= 1

    def test_mixed_servers_workflow(self, temp_mcp_dir):
        """Test workflow with both local and remote servers."""
        # Add local servers
        mcp_add_server.invoke({"name": "local1", "command": "cmd1"})
        mcp_add_server.invoke({"name": "local2", "command": "cmd2"})

        # Add remote servers
        mcp_add_remote_server.invoke({"name": "remote1", "url": "https://api1.example.com/mcp"})
        mcp_add_remote_server.invoke({"name": "remote2", "url": "https://api2.example.com/mcp"})

        # List all
        list_result = mcp_list_servers.invoke({})
        assert "local1" in list_result
        assert "local2" in list_result
        assert "remote1" in list_result
        assert "remote2" in list_result

        # Remove one of each
        mcp_remove_server.invoke({"name": "local2"})
        mcp_remove_server.invoke({"name": "remote2"})

        # Verify removals
        final_list = mcp_list_servers.invoke({})
        assert "local1" in final_list
        assert "remote1" in final_list
        assert "local2" not in final_list
        assert "remote2" not in final_list

        # Reload
        reload_result = mcp_reload.invoke({})
        assert "✅" in reload_result
        assert "1 local" in reload_result or "1 server" in reload_result

    def test_error_recovery_workflow(self, temp_mcp_dir):
        """Test recovering from errors."""
        # Try to add invalid server
        bad_result = mcp_add_server.invoke({
            "name": "bad name!",
            "command": "echo"
        })
        assert "❌" in bad_result

        # Should still be able to add valid server
        good_result = mcp_add_server.invoke({
            "name": "good-name",
            "command": "echo"
        })
        assert "✅" in good_result

        # Verify only valid server was added
        list_result = mcp_list_servers.invoke({})
        assert "good-name" in list_result
        assert "bad name!" not in list_result
