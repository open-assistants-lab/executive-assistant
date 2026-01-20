"""MCP configuration management tools."""

from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from executive_assistant.storage.mcp_storage import (
    load_mcp_config,
    save_user_mcp_config,
    delete_user_mcp_config,
)
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id


def _get_current_user_id() -> str:
    """Get user_id from current thread context."""
    thread_id = get_thread_id()
    if thread_id:
        return sanitize_thread_id_to_user_id(thread_id)
    raise ValueError("No thread_id context available")


def get_mcp_config_tools():
    """Return MCP configuration tools."""
    return [
        get_mcp_config,
        reload_mcp_tools,
        enable_mcp_tools,
        disable_mcp_tools,
        add_mcp_server,
        remove_mcp_server,
    ]


@tool
def get_mcp_config() -> str:
    """
    Get current MCP configuration for current user.

    Shows available MCP servers, enabled status, and load mode.

    Returns:
        Formatted MCP configuration.
    """
    user_id = _get_current_user_id()
    config = load_mcp_config(user_id)

    mcp_enabled = config.get("mcpEnabled", False)
    mcp_servers = config.get("mcpServers", {})

    if not mcp_servers:
        return """
# MCP Configuration

**Status:** Disabled

No MCP servers configured.

To enable MCP tools:
1. Create `data/users/{user_id}/mcp.json` file
2. Add MCP server configuration
3. Use `reload_mcp_tools` tool to refresh

Example configuration (data/users/{user_id}/mcp.json):
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_URL": "https://...",
        "FIRECRAWL_API_KEY": "your-key"
      }
    }
  },
  "mcpEnabled": true
}
```
"""

    lines = [
        f"# MCP Configuration",
        f"",
        f"**Status:** {'Enabled' if mcp_enabled else 'Disabled'}",
        f"",
        f"**Load Mode:** {config.get('loadMcpTools', 'default')}",
        f"",
        f"**Available Servers ({len(mcp_servers)}):**",
    ]

    if mcp_servers:
        for server_name, server_config in mcp_servers.items():
            command = server_config.get("command", "N/A")
            lines.append(f"- {server_name}")
            lines.append(f"  Command: {command}")
            if "env" in server_config:
                env_vars = list(server_config["env"].keys())
                lines.append(f"  Environment: {', '.join(env_vars)}")

    lines.append("")
    lines.append("**Configuration Files:**")
    lines.append(f"  User: data/users/{user_id}/mcp.json")
    lines.append(f"  Shared: data/shared/shared_mcp.json (independent config)")

    return "\n".join(lines)


@tool
def reload_mcp_tools() -> str:
    """
    Reload MCP tools for current user.

    Reloads MCP configuration and clears tool cache.
    Call this after modifying `mcp.json` to apply changes.

    Returns:
        Confirmation message.
    """
    user_id = _get_current_user_id()

    # Clear MCP client cache (in registry.py)
    from executive_assistant.tools.registry import clear_mcp_cache

    clear_mcp_cache()

    return f"MCP tools reloaded for user {user_id}. Configuration loaded from data/users/{user_id}/mcp.json."


@tool
def enable_mcp_tools(
    mode: Literal["default", "manual"] = "default",
    user_id: str | None = None,
) -> str:
    """
    Enable MCP tools for the current user.

    Args:
        mode: "default" (auto-load with agent tools) OR
              "manual" (load only when explicitly requested).

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    # Update configuration
    config["mcpEnabled"] = True
    config["loadMcpTools"] = mode

    save_user_mcp_config(user_id, config)

    mode_desc = (
        "auto-load with agent tools" if mode == "default" else "manual load only"
    )

    return f"MCP tools enabled for user {user_id} ({mode_desc})."


@tool
def disable_mcp_tools(user_id: str | None = None) -> str:
    """
    Disable MCP tools for the current user.

    Clears per-user MCP config, reverting to shared config.

    Args:
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Delete per-user config (reverts to shared)
    delete_user_mcp_config(user_id)

    # Clear MCP cache
    from executive_assistant.tools.registry import clear_mcp_cache

    clear_mcp_cache()

    return f"MCP tools disabled for user {user_id}. Per-user config removed; reverting to shared configuration if available."


@tool
def add_mcp_server(
    server_name: str,
    command: str,
    args: list[str] = [],
    env: dict[str, str] = {},
    user_id: str | None = None,
) -> str:
    """
    Add a custom MCP server configuration.

    Args:
        server_name: Name for MCP server (must be unique).
        command: Command to run the MCP server (e.g., "npx", "node").
        args: Command arguments (e.g., ["-y", "firecrawl-mcp"]).
        env: Environment variables for the MCP server.
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.

    Example:
        add_mcp_server("my-api", "node", ["dist/api.js"], {"API_KEY": "secret"})
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    # Add server
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][server_name] = {
        "command": command,
        "args": args,
        "env": env,
    }

    save_user_mcp_config(user_id, config)

    # Clear MCP cache to reload
    from executive_assistant.tools.registry import clear_mcp_cache

    clear_mcp_cache()

    return f"MCP server '{server_name}' added for user {user_id}. Use reload_mcp_tools to activate."


@tool
def remove_mcp_server(server_name: str, user_id: str | None = None) -> str:
    """
    Remove an MCP server configuration.

    Args:
        server_name: Name of MCP server to remove.
        user_id: User ID. If None, uses current thread context.

    Returns:
        Confirmation message.
    """
    if user_id is None:
        user_id = _get_current_user_id()

    # Load current config
    config = load_mcp_config(user_id)

    if "mcpServers" in config and server_name in config["mcpServers"]:
        del config["mcpServers"][server_name]
        save_user_mcp_config(user_id, config)

        # Clear MCP cache
        from executive_assistant.tools.registry import clear_mcp_cache

        clear_mcp_cache()

        return f"MCP server '{server_name}' removed for user {user_id}."
    else:
        return f"MCP server '{server_name}' not found for user {user_id}."
