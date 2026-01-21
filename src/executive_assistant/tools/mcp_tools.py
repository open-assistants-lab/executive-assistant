"""MCP configuration management tools (admin-only)."""

from typing import Literal

from langchain_core.tools import tool
from executive_assistant.storage.mcp_storage import (
    load_mcp_config,
    save_admin_mcp_config,
    delete_admin_mcp_config,
)
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
from executive_assistant.storage.user_allowlist import is_admin


def _ensure_admin() -> bool:
    thread_id = get_thread_id()
    if not thread_id:
        return False
    user_id = sanitize_thread_id_to_user_id(thread_id)
    return is_admin(thread_id, user_id)


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
    """Get current admin MCP configuration."""
    if not _ensure_admin():
        return "Admin access required."
    config = load_mcp_config()
    mcp_enabled = config.get("mcpEnabled", False)
    mcp_servers = config.get("mcpServers", {})

    if not mcp_servers:
        return """
# MCP Configuration

**Status:** Disabled

No MCP servers configured.

To enable MCP tools:
1. Create `data/admins/mcp.json` file
2. Add MCP server configuration
3. Use `reload_mcp_tools` tool to refresh

Example configuration (data/admins/mcp.json):
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
        "# MCP Configuration",
        "",
        f"**Status:** {'Enabled' if mcp_enabled else 'Disabled'}",
        "",
        f"**Load Mode:** {config.get('loadMcpTools', 'default')}",
        "",
        f"**Available Servers ({len(mcp_servers)}):**",
    ]

    for server_name, server_config in mcp_servers.items():
        command = server_config.get("command", "N/A")
        lines.append(f"- {server_name}")
        lines.append(f"  Command: {command}")
        if "env" in server_config:
            env_vars = list(server_config["env"].keys())
            lines.append(f"  Environment: {', '.join(env_vars)}")

    lines.append("")
    lines.append("**Configuration File:**")
    lines.append("  Admin: data/admins/mcp.json")

    return "
".join(lines)


@tool
def reload_mcp_tools() -> str:
    """Reload MCP tools after modifying admin config."""
    if not _ensure_admin():
        return "Admin access required."
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()
    return "MCP tools reloaded from data/admins/mcp.json."


@tool
def enable_mcp_tools(mode: Literal["default", "manual"] = "default") -> str:
    """Enable MCP tools globally (admin)."""
    if not _ensure_admin():
        return "Admin access required."
    config = load_mcp_config()
    config["mcpEnabled"] = True
    config["loadMcpTools"] = mode
    save_admin_mcp_config(config)
    mode_desc = "auto-load with agent tools" if mode == "default" else "manual load only"
    return f"MCP tools enabled ({mode_desc})."


@tool
def disable_mcp_tools() -> str:
    """Disable MCP tools globally (admin)."""
    if not _ensure_admin():
        return "Admin access required."
    delete_admin_mcp_config()
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()
    return "MCP tools disabled. Admin config removed."


@tool
def add_mcp_server(
    server_name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Add a custom MCP server to admin config."""
    if not _ensure_admin():
        return "Admin access required."
    config = load_mcp_config()
    config.setdefault("mcpServers", {})
    config["mcpServers"][server_name] = {
        "command": command,
        "args": args or [],
        "env": env or {},
    }
    save_admin_mcp_config(config)
    from executive_assistant.tools.registry import clear_mcp_cache
    clear_mcp_cache()
    return f"MCP server '{server_name}' added."


@tool
def remove_mcp_server(server_name: str) -> str:
    """Remove an MCP server from admin config."""
    if not _ensure_admin():
        return "Admin access required."
    config = load_mcp_config()
    if "mcpServers" in config and server_name in config["mcpServers"]:
        del config["mcpServers"][server_name]
        save_admin_mcp_config(config)
        from executive_assistant.tools.registry import clear_mcp_cache
        clear_mcp_cache()
        return f"MCP server '{server_name}' removed."
    return f"MCP server '{server_name}' not found."
