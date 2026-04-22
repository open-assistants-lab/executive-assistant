"""MCP tools — SDK-native implementation.

MCP (Model Context Protocol) server management: list, reload, and inspect tools.
All tools are now native async — no thread hack needed.
"""

from __future__ import annotations

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, ToolDefinition

logger = get_logger()


async def _mcp_list(user_id: str = "") -> str:
    if not user_id:
        return "Error: user_id is required."

    from src.sdk.tools_core.mcp_manager import get_mcp_manager

    manager = get_mcp_manager(user_id)
    await manager.initialize()
    servers = await manager.list_servers()

    if not servers:
        return "No MCP servers configured. Add .mcp.json to your user data directory."

    lines = ["MCP Servers:"]
    for name, info in servers.items():
        status = "running" if info["running"] else "stopped"
        lines.append(f"  - {name}: {status} ({info['tool_count']} tools)")

    return "\n".join(lines)


mcp_list = ToolDefinition(
    name="mcp_list",
    description="List configured MCP servers and their status.\n\nArgs:\n    user_id: User identifier (REQUIRED)",
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(title="List MCP Servers", read_only=True, idempotent=True),
    function=_mcp_list,
)


async def _mcp_reload(user_id: str = "") -> str:
    if not user_id:
        return "Error: user_id is required."

    from src.sdk.tools_core.mcp_manager import get_mcp_manager

    manager = get_mcp_manager(user_id)
    await manager.initialize()
    result = await manager.reload()

    try:
        from src.sdk.runner import _loop_cache
        from src.sdk.tools_core.mcp_bridge import MCPToolBridge

        loop = _loop_cache.get(user_id)
        if loop:
            bridge = getattr(loop, "_mcp_bridge", None)
            if bridge is None:
                bridge = MCPToolBridge(user_id=user_id)
                loop._mcp_bridge = bridge

            old_names = list(bridge._tool_to_server.keys())
            for name in old_names:
                loop.unregister_tool(name)
            bridge._tool_to_server = {}

            mcp_count = await bridge.discover()
            for td in bridge.get_tool_definitions():
                loop.register_tool(td)

            return f"{result} ({mcp_count} MCP tools registered)"
    except Exception as e:
        logger.warning(f"mcp_reload.bridge_error: {e}")

    return result


mcp_reload = ToolDefinition(
    name="mcp_reload",
    description=(
        "Reload all MCP servers from configuration file.\n\n"
        "Use this when you've modified .mcp.json and want to apply changes.\n\n"
        "Args:\n    user_id: User identifier (REQUIRED)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(title="Reload MCP Servers"),
    function=_mcp_reload,
)


async def _mcp_tools(user_id: str = "", server_name: str = "") -> str:
    if not user_id:
        return "Error: user_id is required."

    from src.sdk.tools_core.mcp_manager import get_mcp_manager

    manager = get_mcp_manager(user_id)
    await manager.initialize()
    tools = await manager.get_tools(server_name if server_name else None)

    if not tools:
        return "No MCP tools available."

    lines = ["Available MCP Tools:"]
    for t in tools:
        desc = t.description or "No description"
        lines.append(f"  - {t.name}: {desc[:80]}")

    return "\n".join(lines)


mcp_tools = ToolDefinition(
    name="mcp_tools",
    description=(
        "Get available tools from MCP servers.\n\n"
        "Args:\n    user_id: User identifier (REQUIRED)\n"
        "    server_name: Optional server name to filter tools"
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "default": "", "title": "User Id"},
            "server_name": {"type": "string", "default": "", "title": "Server Name"},
        },
    },
    annotations=ToolAnnotations(title="List MCP Tools", read_only=True, idempotent=True),
    function=_mcp_tools,
)
