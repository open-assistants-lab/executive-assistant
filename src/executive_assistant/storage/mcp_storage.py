"""MCP server configuration storage and loader."""

import json
from pathlib import Path
from typing import Any

from executive_assistant.config import settings


def get_user_mcp_config_path(user_id: str) -> Path:
    """Get per-user MCP config path."""
    return settings.get_user_root(user_id) / "mcp.json"


def get_shared_mcp_config_path() -> Path:
    """Get shared MCP config path."""
    return settings.SHARED_ROOT / "shared_mcp.json"


def load_mcp_config(user_id: str | None = None) -> dict[str, Any]:
    """
    Load MCP configuration for a user (both per-user and shared independently).

    Priority:
    1. User MCP config (data/users/{user_id}/mcp.json) - user-specific servers
    2. Shared MCP config (data/shared/shared_mcp.json) - organization-wide servers

    Both configs are loaded independently and merged. No priority or fallback logic.

    Args:
        user_id: User ID. If None, loads from current thread context.
        If user_id is None (for shared access only), returns only shared config.

    Returns:
        MCP configuration dict with 'mcpServers', 'mcpEnabled', and 'loadMcpTools'.
    """
    # 1. Try user-specific config
    user_config = None
    if user_id:
        user_config_path = get_user_mcp_config_path(user_id)
        if user_config_path.exists():
            with open(user_config_path) as f:
                user_config = json.load(f)

    # 2. Load shared config (always loaded for completeness, independent from user config)
    shared_config_path = get_shared_mcp_config_path()
    shared_config = {}
    if shared_config_path.exists():
        with open(shared_config_path) as f:
            shared_config = json.load(f)

    # 3. Merge configs (both are independent, no override - they coexist)
    mcp_servers = {}
    mcp_enabled = False
    load_mcp_tools_mode = "default"  # Options: "default"|"manual"|"disabled"

    # User config takes precedence (adds servers, overrides enabled mode)
    if user_config:
        mcp_servers.update(user_config.get("mcpServers", {}))
        mcp_enabled = user_config.get(
            "mcpEnabled", shared_config.get("mcpEnabled", False)
        )
        load_mcp_tools_mode = user_config.get(
            "loadMcpTools", shared_config.get("loadMcpTools", "default")
        )

    # Shared config is loaded independently (independent from user config)
    if shared_config:
        mcp_servers.update(shared_config.get("mcpServers", {}))
        mcp_enabled = shared_config.get("mcpEnabled", mcp_enabled)
        load_mcp_tools_mode = shared_config.get(
            "loadMcpTools", user_config.get("loadMcpTools", "default")
        )

    return {
        "mcpServers": mcp_servers,
        "mcpEnabled": mcp_enabled,
        "loadMcpTools": load_mcp_tools_mode,
    }


def save_user_mcp_config(user_id: str, config: dict) -> None:
    """Save per-user MCP configuration."""
    config_path = get_user_mcp_config_path(user_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def delete_user_mcp_config(user_id: str) -> None:
    """Delete per-user MCP configuration (removes config file)."""
    config_path = get_user_mcp_config_path(user_id)
    if config_path.exists():
        config_path.unlink()


def save_shared_mcp_config(config: dict) -> None:
    """Save shared MCP configuration."""
    shared_config_path = settings.SHARED_ROOT / "shared_mcp.json"
    shared_config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(shared_config_path, "w") as f:
        json.dump(config, f, indent=2)
