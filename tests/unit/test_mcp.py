"""Unit tests for MCP module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestMCPConfig:
    """Tests for MCP config loading."""

    def test_load_config_missing_file(self):
        """Test loading config when file doesn't exist."""
        from src.tools.mcp.config import load_mcp_config

        result = load_mcp_config("nonexistent_user")
        assert result is None

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "data" / "users" / "test_user"
            user_dir.mkdir(parents=True)
            config_file = user_dir / ".mcp.json"
            config_file.write_text("invalid json{")

            with patch("src.tools.mcp.config.Path") as mock_path:
                mock_path.return_value = config_file
                from src.tools.mcp.config import load_mcp_config

                result = load_mcp_config("test_user")
                assert result is None

    def test_load_config_valid(self):
        """Test loading valid config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "data" / "users" / "test_user"
            user_dir.mkdir(parents=True)
            config_file = user_dir / ".mcp.json"
            config_file.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "math": {
                                "command": "python",
                                "args": ["tests/mcp/math_server.py"],
                            }
                        }
                    }
                )
            )

            with patch("src.tools.mcp.config.Path") as mock_path:
                mock_path.return_value = config_file
                from src.tools.mcp.config import load_mcp_config

                result = load_mcp_config("test_user")
                assert result is not None
                assert "math" in result.mcpServers

    def test_config_path(self):
        """Test config path generation."""
        from src.tools.mcp.config import get_config_path

        path = get_config_path("test_user")
        assert str(path) == "data/users/test_user/.mcp.json"

    def test_config_mtime_missing(self):
        """Test mtime when config doesn't exist."""
        from src.tools.mcp.config import get_config_mtime

        result = get_config_mtime("nonexistent_user")
        assert result == 0.0


class TestMCPTools:
    """Tests for MCP tools."""

    def test_mcp_list_requires_user_id(self):
        """Test mcp_list requires user_id."""
        from src.tools.mcp.tools import mcp_list

        result = mcp_list.invoke({})
        assert "Error: user_id is required" in result

    def test_mcp_reload_requires_user_id(self):
        """Test mcp_reload requires user_id."""
        from src.tools.mcp.tools import mcp_reload

        result = mcp_reload.invoke({})
        assert "Error: user_id is required" in result

    def test_mcp_tools_requires_user_id(self):
        """Test mcp_tools requires user_id."""
        from src.tools.mcp.tools import mcp_tools

        result = mcp_tools.invoke({})
        assert "Error: user_id is required" in result

    @patch("src.tools.mcp.tools.get_mcp_manager")
    def test_mcp_list_empty(self, mock_get_manager):
        """Test mcp_list with no servers."""
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.list_servers = AsyncMock(return_value={})
        mock_get_manager.return_value = mock_manager

        from src.tools.mcp.tools import mcp_list

        result = mcp_list.invoke({"user_id": "test_user"})
        assert "No MCP servers configured" in result

    @patch("src.tools.mcp.tools.get_mcp_manager")
    def test_mcp_list_with_servers(self, mock_get_manager):
        """Test mcp_list with servers running."""
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

        from src.tools.mcp.tools import mcp_list

        result = mcp_list.invoke({"user_id": "test_user"})
        assert "math" in result
        assert "running" in result


class TestMCPManager:
    """Tests for MCP manager."""

    def test_compute_config_hash(self):
        """Test config hash computation."""
        from src.tools.mcp.config import MCPConfig, MCPServerConfig

        config = MCPConfig(mcpServers={"math": MCPServerConfig(command="python", args=["test.py"])})

        from src.tools.mcp.manager import MCPManager

        manager = MCPManager("test_user")
        hash1 = manager._compute_config_hash(config)
        hash2 = manager._compute_config_hash(config)

        assert hash1 == hash2
        assert len(hash1) == 32

    def test_config_changed_no_config(self):
        """Test config changed when no config exists."""
        with patch("src.tools.mcp.manager.load_mcp_config") as mock_load:
            mock_load.return_value = None

            from src.tools.mcp.manager import MCPManager

            manager = MCPManager("test_user")
            assert not manager._config_changed()
