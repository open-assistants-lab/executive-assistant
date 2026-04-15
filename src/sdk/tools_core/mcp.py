"""MCP tools — SDK-native implementation.

MCP (Model Context Protocol) server management: list, reload, and inspect tools.
"""

from __future__ import annotations

import asyncio

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool

logger = get_logger()


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@tool
def mcp_list(user_id: str = "") -> str:
    """List configured MCP servers and their status.

    Args:
        user_id: User identifier (REQUIRED)

    Returns:
        List of MCP servers and their status
    """
    if not user_id:
        return "Error: user_id is required."

    async def _list():
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

    return _run_async(_list())


mcp_list.annotations = ToolAnnotations(title="List MCP Servers", read_only=True, idempotent=True)


@tool
def mcp_reload(user_id: str = "") -> str:
    """Reload all MCP servers from configuration file.

    Use this when you've modified .mcp.json and want to apply changes.

    Args:
        user_id: User identifier (REQUIRED)

    Returns:
        Reload status message
    """
    if not user_id:
        return "Error: user_id is required."

    async def _reload():
        from src.sdk.tools_core.mcp_manager import get_mcp_manager

        manager = get_mcp_manager(user_id)
        await manager.initialize()
        return await manager.reload()

    return _run_async(_reload())


mcp_reload.annotations = ToolAnnotations(title="Reload MCP Servers")


@tool
def mcp_tools(user_id: str = "", server_name: str = "") -> str:
    """Get available tools from MCP servers.

    Args:
        user_id: User identifier (REQUIRED)
        server_name: Optional server name to filter tools

    Returns:
        List of available MCP tools
    """
    if not user_id:
        return "Error: user_id is required."

    async def _tools():
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

    return _run_async(_tools())


mcp_tools.annotations = ToolAnnotations(title="List MCP Tools", read_only=True, idempotent=True)
