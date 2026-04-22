"""Unit tests for MCP module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMCPConfig:
    """Tests for MCP config loading."""

    def test_load_config_missing_file(self):
        """Test loading config when file doesn't exist."""
        from src.sdk.tools_core.mcp_config import load_mcp_config

        result = load_mcp_config("nonexistent_user")
        assert result is None

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "data" / "users" / "test_user"
            user_dir.mkdir(parents=True)
            config_file = user_dir / ".mcp.json"
            config_file.write_text("invalid json{")

            with patch("src.sdk.tools_core.mcp_config.Path") as mock_path:
                mock_path.return_value = config_file
                from src.sdk.tools_core.mcp_config import load_mcp_config

                result = load_mcp_config("test_user")
                assert result is None

    def test_config_mtime_missing(self):
        """Test mtime when config doesn't exist."""
        from src.sdk.tools_core.mcp_config import get_config_mtime

        result = get_config_mtime("nonexistent_user")
        assert result == 0.0


class TestMCPTools:
    """Tests for MCP tools (async)."""

    async def test_mcp_list_requires_user_id(self):
        from src.sdk.tools_core.mcp import mcp_list

        result = await mcp_list.ainvoke({"user_id": ""})
        assert "Error: user_id is required" in result

    async def test_mcp_reload_requires_user_id(self):
        from src.sdk.tools_core.mcp import mcp_reload

        result = await mcp_reload.ainvoke({"user_id": ""})
        assert "Error: user_id is required" in result

    async def test_mcp_tools_requires_user_id(self):
        from src.sdk.tools_core.mcp import mcp_tools

        result = await mcp_tools.ainvoke({"user_id": ""})
        assert "Error: user_id is required" in result

    @patch("src.sdk.tools_core.mcp_manager.get_mcp_manager")
    async def test_mcp_list_empty(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.list_servers = AsyncMock(return_value={})
        mock_get_manager.return_value = mock_manager

        from src.sdk.tools_core.mcp import mcp_list

        result = await mcp_list.ainvoke({"user_id": "test_user"})
        assert "No MCP servers configured" in result

    @patch("src.sdk.tools_core.mcp_manager.get_mcp_manager")
    async def test_mcp_list_with_servers(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.list_servers = AsyncMock(
            return_value={
                "math": {
                    "command": "python",
                    "args": ["math.py"],
                    "transport": "stdio",
                    "running": True,
                    "tool_count": 2,
                }
            }
        )
        mock_get_manager.return_value = mock_manager

        from src.sdk.tools_core.mcp import mcp_list

        result = await mcp_list.ainvoke({"user_id": "test_user"})
        assert "math" in result
        assert "running" in result


class TestMCPManager:
    """Tests for MCP manager."""

    def test_compute_config_hash(self):
        """Test config hash computation."""
        from src.sdk.tools_core.mcp_config import MCPConfig, MCPServerConfig

        config = MCPConfig(mcpServers={"math": MCPServerConfig(command="python", args=["test.py"])})

        from src.sdk.tools_core.mcp_manager import MCPManager

        manager = MCPManager("test_user")
        hash1 = manager._compute_config_hash(config)
        hash2 = manager._compute_config_hash(config)

        assert hash1 == hash2
        assert len(hash1) == 32

    def test_config_changed_no_config(self):
        """Test config changed when no config exists."""
        with patch("src.sdk.tools_core.mcp_manager.load_mcp_config") as mock_load:
            mock_load.return_value = None

            from src.sdk.tools_core.mcp_manager import MCPManager

            manager = MCPManager("test_user")
            assert not manager._config_changed()
