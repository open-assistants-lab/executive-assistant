"""MCP server configuration storage and loader (admin-only)."""

import json
from pathlib import Path
from typing import Any

from executive_assistant.config import settings


def get_admin_mcp_config_path() -> Path:
    """Get admin MCP config path."""
    return settings.ADMINS_ROOT / "mcp.json"


def load_mcp_config() -> dict[str, Any]:
    """Load admin MCP configuration.

    Returns:
        MCP configuration dict with 'mcpServers', 'mcpEnabled', and 'loadMcpTools'.
    """
    config_path = get_admin_mcp_config_path()
    if not config_path.exists():
        return {"mcpServers": {}, "mcpEnabled": False, "loadMcpTools": "default"}
    with open(config_path) as f:
        config = json.load(f)
    config.setdefault("mcpServers", {})
    config.setdefault("mcpEnabled", False)
    config.setdefault("loadMcpTools", "default")
    return config


def save_admin_mcp_config(config: dict) -> None:
    """Save admin MCP configuration."""
    config_path = get_admin_mcp_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def delete_admin_mcp_config() -> None:
    """Delete admin MCP configuration (removes config file)."""
    config_path = get_admin_mcp_config_path()
    if config_path.exists():
        config_path.unlink()
