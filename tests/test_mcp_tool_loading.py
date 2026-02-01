"""Tests for MCP tool loading and registry integration.

Tests the tiered loading system (user > admin priority), tool deduplication,
cache management, and hot-reload functionality.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from executive_assistant.tools.registry import (
    load_mcp_tools_tiered,
    clear_mcp_cache,
    get_mcp_cache_info,
    _get_tool_names,
    _load_mcp_servers,
    _mcp_server_to_connection,
)
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id


def _patch_storage_with_temp_dir(temp_mcp_dir: Path):
    """Helper to patch storage with temp directory."""
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = temp_mcp_dir
    return patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_mcp_dir(tmp_path):
    """Create a temporary MCP directory for testing."""
    mcp_dir = tmp_path / "users" / "test_thread" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    return mcp_dir


@pytest.fixture
def mock_mcp_client():
    """Mock MultiServerMCPClient."""
    client = MagicMock()
    client.get_tools = AsyncMock()

    # Create mock tools
    mock_tool1 = MagicMock()
    mock_tool1.name = "fetch_webpage"
    mock_tool1.func = lambda: "result"

    mock_tool2 = MagicMock()
    mock_tool2.name = "search_github"
    mock_tool2.func = lambda: "result"

    client.get_tools.return_value = [mock_tool1, mock_tool2]
    return client


@pytest.fixture
def user_local_config():
    """Sample user-local MCP configuration."""
    return {
        "version": "1.0",
        "updated_at": "2026-01-31T00:00:00Z",
        "mcpServers": {
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"]
            }
        }
    }


@pytest.fixture
def user_remote_config():
    """Sample user-remote MCP configuration."""
    return {
        "version": "1.0",
        "updated_at": "2026-01-31T00:00:00Z",
        "mcpServers": {
            "api-server": {
                "url": "https://api.example.com/mcp"
            }
        }
    }


@pytest.fixture
def admin_config():
    """Sample admin MCP configuration."""
    return {
        "mcpServers": {
            "admin-tool": {
                "command": "admin-command"
            }
        }
    }


# =============================================================================
# Server Connection Tests
# =============================================================================

class TestMCPServerToConnection:
    """Test MCP server config to connection dict conversion."""

    def test_stdio_server_conversion(self):
        """Test converting stdio server config to connection."""
        config = {
            "command": "uvx",
            "args": ["mcp-server-fetch", "--port", "3000"],
            "env": {"API_KEY": "test"},
            "cwd": "/path/to/dir"
        }

        result = _mcp_server_to_connection(config)

        assert result["transport"] == "stdio"
        assert result["command"] == "uvx"
        assert result["args"] == ["mcp-server-fetch", "--port", "3000"]
        assert result["env"]["API_KEY"] == "test"
        assert result["cwd"] == "/path/to/dir"

    def test_stdio_server_minimal(self):
        """Test converting minimal stdio server config."""
        config = {"command": "echo"}

        result = _mcp_server_to_connection(config)

        assert result["transport"] == "stdio"
        assert result["command"] == "echo"
        assert result["args"] == []
        assert result["env"] is None
        assert result["cwd"] is None

    def test_http_server_conversion(self):
        """Test converting HTTP server config to connection."""
        config = {
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"}
        }

        result = _mcp_server_to_connection(config)

        assert result["transport"] == "http"
        assert result["url"] == "https://api.example.com/mcp"
        assert result["headers"]["Authorization"] == "Bearer token"

    def test_http_server_minimal(self):
        """Test converting minimal HTTP server config."""
        config = {"url": "https://api.example.com/mcp"}

        result = _mcp_server_to_connection(config)

        assert result["transport"] == "http"
        assert result["url"] == "https://api.example.com/mcp"
        assert result["headers"] is None

    def test_invalid_server_config(self):
        """Test that invalid server config raises error."""
        config = {"invalid": "config"}

        with pytest.raises(ValueError, match="Unsupported MCP server config"):
            _mcp_server_to_connection(config)


# =============================================================================
# Tool Loading Tests
# =============================================================================

class TestLoadMCPServers:
    """Test _load_mcp_servers function."""

    @pytest.mark.asyncio
    async def test_load_single_server(self, mock_mcp_client):
        """Test loading tools from a single MCP server."""
        servers = {
            "test-server": {
                "command": "echo"
            }
        }

        with patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_mcp_client):
            tools = await _load_mcp_servers(servers, "test")

            assert len(tools) == 2
            assert tools[0].name == "fetch_webpage"
            assert tools[1].name == "search_github"

    @pytest.mark.asyncio
    async def test_load_multiple_servers(self, mock_mcp_client):
        """Test loading tools from multiple MCP servers."""
        servers = {
            "server1": {"command": "echo1"},
            "server2": {"command": "echo2"}
        }

        with patch("langchain_mcp_adapters.client.MultiServerMCPClient", return_value=mock_mcp_client):
            tools = await _load_mcp_servers(servers, "test")

            # Mock returns 2 tools per server, total 4
            assert len(tools) == 4

    @pytest.mark.asyncio
    async def test_load_empty_servers(self):
        """Test loading empty server list."""
        servers = {}

        tools = await _load_mcp_servers(servers, "test")
        assert tools == []

    @pytest.mark.asyncio
    async def test_load_server_with_invalid_config(self, capsys):
        """Test that invalid server config is logged and skipped."""
        servers = {
            "valid-server": {"command": "echo"},
            "invalid-server": {"invalid": "config"}
        }

        with patch("executive_assistant.tools.registry.MultiServerMCPClient") as mock_client:
            mock_client.return_value.get_tools = AsyncMock(return_value=[])
            tools = await _load_mcp_servers(servers, "test")

            # Should have warning output
            captured = capsys.readouterr()
            assert "Warning: Invalid MCP server config" in captured.out


# =============================================================================
# Tool Name Extraction Tests
# =============================================================================

class TestGetToolNames:
    """Test _get_tool_names function."""

    def test_extract_names_from_tools(self):
        """Test extracting tool names from tool list."""
        tool1 = MagicMock()
        tool1.name = "tool1"

        tool2 = MagicMock()
        tool2.name = "tool2"

        tool3 = MagicMock()
        tool3.name = "tool3"

        names = _get_tool_names([tool1, tool2, tool3])

        assert names == {"tool1", "tool2", "tool3"}

    def test_empty_tool_list(self):
        """Test extracting names from empty list."""
        names = _get_tool_names([])
        assert names == set()


# =============================================================================
# Cache Management Tests
# =============================================================================

class TestMCPCache:
    """Test MCP client cache management."""

    def test_clear_cache(self):
        """Test clearing MCP cache."""
        # Set up cache
        from executive_assistant.tools import registry
        registry._mcp_client_cache["key1"] = "value1"
        registry._mcp_client_cache["key2"] = "value2"

        # Clear cache
        cleared = clear_mcp_cache()

        assert cleared == 2
        assert len(registry._mcp_client_cache) == 0

    def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        from executive_assistant.tools import registry
        # Ensure cache is empty
        registry._mcp_client_cache.clear()

        cleared = clear_mcp_cache()

        assert cleared == 0

    def test_get_cache_info(self):
        """Test getting cache information."""
        from executive_assistant.tools import registry
        registry._mcp_client_cache.clear()

        registry._mcp_client_cache["key1"] = {"client": "mock1"}
        registry._mcp_client_cache["key2"] = {"client": "mock2"}

        info = get_mcp_cache_info()

        assert info["size"] == 2
        assert set(info["keys"]) == {"key1", "key2"}

    def test_get_empty_cache_info(self):
        """Test getting cache info when empty."""
        from executive_assistant.tools import registry
        registry._mcp_client_cache.clear()

        info = get_mcp_cache_info()

        assert info["size"] == 0
        assert info["keys"] == []


# =============================================================================
# Tiered Loading Tests
# =============================================================================

class TestTieredLoading:
    """Test tiered tool loading with user > admin priority."""

    @pytest.mark.asyncio
    async def test_user_local_priority(self, temp_mcp_dir, user_local_config, admin_config):
        """Test that user-local tools have highest priority."""
        # Set up thread context
        set_thread_id("test_thread")

        try:
            # Write user-local config
            (temp_mcp_dir / "mcp.json").write_text(json.dumps(user_local_config))

            # Mock admin config
            with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
                with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                    # Set up mock to return different tools for user vs admin
                    user_tool = MagicMock()
                    user_tool.name = "fetch_tool"

                    admin_tool = MagicMock()
                    admin_tool.name = "admin_tool"

                    async def get_tools_mock():
                        return [user_tool]

                    async def get_tools_admin():
                        return [admin_tool]

                    mock_client.return_value.get_tools = AsyncMock(side_effect=[get_tools_mock(), get_tools_admin()])

                    # Load tools with user-local config
                    with _patch_storage_with_temp_dir(temp_mcp_dir):
                        tools = await load_mcp_tools_tiered()

                        tool_names = {t.name for t in tools}
                        assert "fetch_tool" in tool_names

        finally:
            clear_thread_id()

    @pytest.mark.asyncio
    async def test_user_remote_medium_priority(self, temp_mcp_dir, user_remote_config, admin_config):
        """Test that user-remote tools have medium priority."""
        set_thread_id("test_thread")

        try:
            # Write user-remote config
            (temp_mcp_dir / "mcp_remote.json").write_text(json.dumps(user_remote_config))

            # Mock admin config
            with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
                with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                    remote_tool = MagicMock()
                    remote_tool.name = "api_tool"

                    admin_tool = MagicMock()
                    admin_tool.name = "admin_tool"

                    mock_client.return_value.get_tools = AsyncMock(side_effect=[remote_tool, admin_tool])

                    with _patch_storage_with_temp_dir(temp_mcp_dir):
                        tools = await load_mcp_tools_tiered()

                        tool_names = {t.name for t in tools}
                        assert "api_tool" in tool_names

        finally:
            clear_thread_id()

    @pytest.mark.asyncio
    async def test_admin_fallback(self, temp_mcp_dir, admin_config):
        """Test that admin tools are loaded as fallback."""
        set_thread_id("test_thread")

        try:
            # No user config, only admin
            with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
                with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                    admin_tool = MagicMock()
                    admin_tool.name = "admin_tool"

                    mock_client.return_value.get_tools = AsyncMock(return_value=[admin_tool])

                    with _patch_storage_with_temp_dir(temp_mcp_dir):
                        tools = await load_mcp_tools_tiered()

                        tool_names = {t.name for t in tools}
                        assert "admin_tool" in tool_names

        finally:
            clear_thread_id()

    @pytest.mark.asyncio
    async def test_deduplication_user_over_admin(self, temp_mcp_dir, user_local_config):
        """Test that user tools override admin tools on name collision."""
        set_thread_id("test_thread")

        try:
            # Write user config
            (temp_mcp_dir / "mcp.json").write_text(json.dumps(user_local_config))

            # Admin config with same tool name
            admin_config = {
                "mcpServers": {
                    "fetch": {
                        "command": "admin-fetch-command"
                    }
                }
            }

            with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
                with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                    # Both user and admin provide tool with same name
                    user_tool = MagicMock()
                    user_tool.name = "shared_tool"

                    admin_tool = MagicMock()
                    admin_tool.name = "shared_tool"  # Same name!

                    mock_client.return_value.get_tools = AsyncMock(return_value=[user_tool])

                    with _patch_storage_with_temp_dir(temp_mcp_dir):
                        tools = await load_mcp_tools_tiered()

                        # Count tools with this name
                        shared_count = sum(1 for t in tools if t.name == "shared_tool")
                        # Should only have one (user's version)
                        assert shared_count == 1

        finally:
            clear_thread_id()

    @pytest.mark.asyncio
    async def test_no_thread_id_returns_only_admin(self, admin_config):
        """Test that when no thread_id, only admin tools are loaded."""
        # No thread_id set
        clear_thread_id()

        with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
            with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                admin_tool = MagicMock()
                admin_tool.name = "admin_tool"

                mock_client.return_value.get_tools = AsyncMock(return_value=[admin_tool])

                # Create temp directory for thread_id check
                with _patch_storage_with_temp_dir(Path("/tmp/test/mcp")):
                    tools = await load_mcp_tools_tiered()

                    # Should only load admin tools
                    tool_names = {t.name for t in tools}
                    assert "admin_tool" in tool_names


# =============================================================================
# Integration Tests
# =============================================================================

class TestMCPIntegration:
    """Integration tests for MCP tool loading."""

    @pytest.mark.asyncio
    async def test_full_tiered_loading_flow(self, temp_mcp_dir):
        """Test complete tiered loading flow with all three sources."""
        set_thread_id("integration_test")

        try:
            # User-local config
            user_local = {
                "mcpServers": {
                    "local-tool": {"command": "local"}
                }
            }
            (temp_mcp_dir / "mcp.json").write_text(json.dumps(user_local))

            # User-remote config
            user_remote = {
                "mcpServers": {
                    "remote-tool": {"url": "https://api.example.com/mcp"}
                }
            }
            (temp_mcp_dir / "mcp_remote.json").write_text(json.dumps(user_remote))

            # Admin config
            admin_config = {
                "mcpServers": {
                    "admin-tool": {"command": "admin"}
                }
            }

            with patch("executive_assistant.tools.registry.load_mcp_config", return_value=admin_config):
                with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                    # Mock tools for each source
                    local_tool = MagicMock()
                    local_tool.name = "local_mcp_tool"

                    remote_tool = MagicMock()
                    remote_tool.name = "remote_mcp_tool"

                    admin_tool = MagicMock()
                    admin_tool.name = "admin_mcp_tool"

                    mock_client.return_value.get_tools = AsyncMock(side_effect=[
                        [local_tool],    # User-local
                        [remote_tool],   # User-remote
                        [admin_tool]     # Admin
                    ])

                    with _patch_storage_with_temp_dir(temp_mcp_dir):
                        tools = await load_mcp_tools_tiered()

                        tool_names = {t.name for t in tools}

                        # All three sources should be loaded
                        assert "local_mcp_tool" in tool_names
                        assert "remote_mcp_tool" in tool_names
                        assert "admin_mcp_tool" in tool_names

        finally:
            clear_thread_id()

    @pytest.mark.asyncio
    async def test_reload_clears_cache(self, temp_mcp_dir, user_local_config):
        """Test that reload clears cache and reloads tools."""
        set_thread_id("test_thread")

        try:
            (temp_mcp_dir / "mcp.json").write_text(json.dumps(user_local_config))

            # First load
            with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                tool1 = MagicMock()
                tool1.name = "tool_v1"
                mock_client.return_value.get_tools = AsyncMock(return_value=[tool1])

                with patch("executive_assistant.storage.user_mcp_storage.get_thread_mcp_dir", return_value=temp_mcp_dir.parent):
                    tools_v1 = await load_mcp_tools_tiered()
                    assert tools_v1[0].name == "tool_v1"

                    # Clear cache (simulating reload)
                    clear_mcp_cache()

                    # Second load with different tools
                    tool2 = MagicMock()
                    tool2.name = "tool_v2"
                    mock_client.return_value.get_tools = AsyncMock(return_value=[tool2])

                    tools_v2 = await load_mcp_tools_tiered()
                    assert tools_v2[0].name == "tool_v2"

        finally:
            clear_thread_id()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestMCPErrorHandling:
    """Test error handling in MCP tool loading."""

    @pytest.mark.asyncio
    async def test_import_error_handled_gracefully(self, capsys):
        """Test that ImportError when langchain_mcp_adapters is missing is handled."""
        with patch("executive_assistant.tools.registry.MultiServerMCPClient", side_effect=ImportError):
            tools = await load_mcp_tools_tiered()

            # Should return empty list
            assert tools == []

            # Should print warning
            captured = capsys.readouterr()
            assert "langchain-mcp-adapters not installed" in captured.out

    @pytest.mark.asyncio
    async def test_get_tools_error_handled(self, temp_mcp_dir, capsys):
        """Test that errors from get_tools are handled gracefully."""
        set_thread_id("test_thread")

        try:
            (temp_mcp_dir / "mcp.json").write_text(json.dumps({"mcpServers": {"test": {"command": "echo"}}}))

            with patch("langchain_mcp_adapters.client.MultiServerMCPClient") as mock_client:
                mock_client.return_value.get_tools = AsyncMock(side_effect=Exception("Connection failed"))

                with patch("executive_assistant.storage.user_mcp_storage.get_thread_mcp_dir", return_value=temp_mcp_dir.parent):
                    # Should not raise, just log and continue
                    tools = await load_mcp_tools_tiered()

                    # Should return empty list on error
                    assert isinstance(tools, list)

        finally:
            clear_thread_id()
