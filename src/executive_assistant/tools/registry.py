"""Tool registry for aggregating all available tools."""

import logging
from typing import Any
import re

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)
_mcp_client_cache: dict[str, Any] = {}


def _normalize_tool(tool):
    if isinstance(tool, BaseTool):
        if getattr(tool, "coroutine", None):
            return tool.coroutine
        if getattr(tool, "func", None):
            return tool.func
    return tool


def _mcp_server_to_connection(server_config: dict) -> dict:
    if "command" in server_config:
        return {
            "transport": "stdio",
            "command": server_config.get("command"),
            "args": server_config.get("args", []),
            "env": server_config.get("env"),
            "cwd": server_config.get("cwd"),
        }
    if "url" in server_config:
        return {
            "transport": "http",
            "url": server_config.get("url"),
            "headers": server_config.get("headers"),
        }
    raise ValueError("Unsupported MCP server config; expected command/args or url")


def clear_mcp_cache() -> None:
    """Clear MCP client cache to force reload."""
    global _mcp_client_cache
    _mcp_client_cache.clear()


async def get_confirmation_tools() -> list[BaseTool]:
    """Get user confirmation tools for large operations."""
    from executive_assistant.tools.confirmation_tool import confirm_request
    return [confirm_request]


async def get_file_tools() -> list[BaseTool]:
    """Get file operation tools."""
    from executive_assistant.storage.file_sandbox import (
        read_file,
        write_file,
        list_files,
        create_folder,
        delete_folder,
        delete_file,
        rename_folder,
        move_file,
        glob_files,
        grep_files,
    )
    return [
        read_file,
        write_file,
        list_files,
        create_folder,
        delete_folder,
        delete_file,
        rename_folder,
        move_file,
        glob_files,
        grep_files,
    ]


async def get_tdb_tools() -> list[BaseTool]:
    """Get transactional database (TDB) tools (thread-scoped)."""
    from executive_assistant.storage.tdb_tools import (
        create_tdb_table,
        insert_tdb_table,
        query_tdb,
        list_tdb_tables,
        describe_tdb_table,
        delete_tdb_table,
        export_tdb_table,
        import_tdb_table,
        add_tdb_column,
        drop_tdb_column,
    )
    return [
        create_tdb_table,
        insert_tdb_table,
        query_tdb,
        list_tdb_tables,
        describe_tdb_table,
        delete_tdb_table,
        export_tdb_table,
        import_tdb_table,
        add_tdb_column,
        drop_tdb_column,
    ]


async def get_adb_tools() -> list[BaseTool]:
    """Get analytics DB (DuckDB) tools."""
    from executive_assistant.storage.adb_tools import get_adb_tools as _get
    return await _get()


async def get_time_tools() -> list[BaseTool]:
    """Get time and date tools."""
    from executive_assistant.tools.time_tool import get_current_time, get_current_date, list_timezones
    return [get_current_time, get_current_date, list_timezones]


async def get_reminder_tools() -> list[BaseTool]:
    """Get reminder tools."""
    from executive_assistant.tools.reminder_tools import get_reminder_tools as _get
    return _get()


async def get_meta_tools() -> list[BaseTool]:
    """Get system metadata tools."""
    from executive_assistant.tools.meta_tools import get_meta_tools as _get
    return _get()


async def get_python_tools() -> list[BaseTool]:
    """Get Python code execution tools."""
    from executive_assistant.tools.python_tool import get_python_tools as _get
    return _get()


async def get_search_tools() -> list[BaseTool]:
    """Get web search tools."""
    from executive_assistant.tools.search_tool import get_search_tools as _get
    return _get()


async def get_browser_tools() -> list[BaseTool]:
    """Get browser automation tools (Playwright)."""
    from executive_assistant.tools.playwright_tool import playwright_scrape
    return [playwright_scrape]


async def get_ocr_tools() -> list[BaseTool]:
    """Get OCR tools."""
    from executive_assistant.tools.ocr_tool import get_ocr_tools as _get
    return _get()


async def get_skills_tools() -> list[BaseTool]:
    """Get skills tools for on-demand skill loading and user skill creation."""
    from executive_assistant.skills.tool import load_skill
    from executive_assistant.skills.user_tools import get_user_skill_tools

    tools = [load_skill]
    tools.extend(get_user_skill_tools())
    return tools


async def get_vdb_tools() -> list[BaseTool]:
    """Get Vector Database (VDB) tools backed by LanceDB for vector search."""
    from executive_assistant.storage.vdb_tools import get_vdb_tools as _get
    return await _get()


async def get_memory_tools() -> list[BaseTool]:
    """Get Memory tools for storing and retrieving user memories."""
    from executive_assistant.tools.mem_tools import get_memory_tools as _get
    return _get()


async def get_instinct_tools() -> list[BaseTool]:
    """Get Instinct tools for behavioral pattern learning."""
    from executive_assistant.tools.instinct_tools import get_instinct_tools as _get
    return _get()


async def get_mcp_tools() -> list[BaseTool]:
    """Get tools from MCP servers configured in admin mcp.json."""
    tools: list[BaseTool] = []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        import json

        from executive_assistant.storage.mcp_storage import get_admin_mcp_config_path
        mcp_config_path = get_admin_mcp_config_path()
        if not mcp_config_path.exists():
            return tools

        with open(mcp_config_path) as f:
            mcp_config = json.load(f)

        connections = {}
        for server_name, server_config in mcp_config.get("mcpServers", {}).items():
            try:
                connections[server_name] = _mcp_server_to_connection(server_config)
            except Exception as e:
                print(f"Warning: Invalid MCP server config for '{server_name}': {e}")

        if connections:
            client = MultiServerMCPClient(connections=connections)
            server_tools = await client.get_tools()
            tools.extend(server_tools)
    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")
    except Exception as e:
        print(f"Warning: Error loading MCP tools: {e}")

    return tools


def get_standard_tools() -> list[BaseTool]:
    """Get standard LangChain tools."""
    tools: list[BaseTool] = []
    # Tavily integration removed - using Firecrawl for search instead
    return tools


async def get_flow_tools() -> list[BaseTool]:
    """Get flow scheduling/execution tools."""
    from executive_assistant.tools.flow_tools import (
        create_flow,
        list_flows,
        run_flow,
        cancel_flow,
        delete_flow,
    )
    return [create_flow, list_flows, run_flow, cancel_flow, delete_flow]


async def get_tools_by_name(names: list[str]) -> list[BaseTool]:
    """Resolve tools by name from the registry."""
    all_tools = await get_all_tools()
    tool_map: dict[str, BaseTool] = {}
    for tool in all_tools:
        name = getattr(tool, "name", None)
        if not name:
            name = getattr(tool, "__name__", None)
        if name:
            tool_map[name] = tool
    missing = [name for name in names if name not in tool_map]
    if missing:
        raise ValueError(f"Unknown tool(s): {', '.join(missing)}")
    return [tool_map[name] for name in names]


async def get_all_tools() -> list[BaseTool]:
    """Aggregate all available tools for the agent."""
    all_tools: list = []

    all_tools.extend(await get_file_tools())
    all_tools.extend(await get_tdb_tools())
    all_tools.extend(await get_adb_tools())
    all_tools.extend(await get_skills_tools())
    all_tools.extend(await get_vdb_tools())
    all_tools.extend(await get_memory_tools())
    all_tools.extend(await get_instinct_tools())
    all_tools.extend(await get_time_tools())
    all_tools.extend(await get_reminder_tools())
    # DISABLED: Flow tools - not production-ready yet
    # all_tools.extend(await get_flow_tools())
    all_tools.extend(await get_meta_tools())
    all_tools.extend(await get_python_tools())
    all_tools.extend(await get_search_tools())
    all_tools.extend(await get_browser_tools())
    all_tools.extend(await get_ocr_tools())
    all_tools.extend(await get_confirmation_tools())

    from executive_assistant.tools.firecrawl_tool import get_firecrawl_tools
    all_tools.extend(get_firecrawl_tools())

    # DISABLED: Agent tools - not production-ready yet
    # from executive_assistant.tools.agent_tools import (
    #     create_agent,
    #     list_agents,
    #     get_agent,
    #     update_agent,
    #     delete_agent,
    #     run_agent,
    # )
    # all_tools.extend([create_agent, list_agents, get_agent, update_agent, delete_agent, run_agent])

    # DISABLED: Flow project tools - not production-ready yet
    # from executive_assistant.tools.flow_project_tools import create_flow_project
    # all_tools.append(create_flow_project)

    from executive_assistant.tools.mcp_tools import get_mcp_config_tools
    all_tools.extend(get_mcp_config_tools())

    # User MCP management tools
    from executive_assistant.tools.user_mcp_tools import (
        mcp_add_server,
        mcp_add_remote_server,
        mcp_export_config,
        mcp_import_config,
        mcp_list_backups,
        mcp_list_servers,
        mcp_remove_server,
        mcp_show_server,
        mcp_reload,
    )
    all_tools.extend([
        mcp_list_servers,
        mcp_add_server,
        mcp_add_remote_server,
        mcp_remove_server,
        mcp_show_server,
        mcp_export_config,
        mcp_import_config,
        mcp_list_backups,
        mcp_reload,
    ])

    all_tools.extend(get_standard_tools())

    # Load MCP tools with tiered priority: User > Admin
    all_tools.extend(await load_mcp_tools_tiered())

    all_tools = [_normalize_tool(t) for t in all_tools]
    return all_tools


def _text_has_any(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    hay = text.lower()
    return any(p in hay for p in patterns)


def _matches_regex(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


async def get_tools_for_request(
    message_text: str,
    *,
    flow_mode: bool = False,
) -> list[BaseTool]:
    """
    Return a minimized tool list based on the user message.

    .. deprecated::
        This function is deprecated in favor of always using :func:`get_all_tools`.
        Progressive disclosure based on message keywords caused broken multi-step
        workflows. With modern LLMs (200K context), the token overhead of all tools
        (~937 tokens) is negligible (0.5% of context) compared to the reliability
        improvement of having all tools available.

    Use :func:`get_all_tools` instead.
    """
    tools: list[BaseTool] = []

    # Always allow skills + confirmations.
    tools.extend(await get_skills_tools())
    tools.extend(await get_confirmation_tools())

    if flow_mode or _text_has_any(message_text, ["flow", "flows", "agent", "agents"]):
        from executive_assistant.tools.agent_tools import (
            create_agent,
            list_agents,
            get_agent,
            update_agent,
            delete_agent,
            run_agent,
        )
        tools.extend([create_agent, list_agents, get_agent, update_agent, delete_agent, run_agent])
        tools.extend(await get_flow_tools())
        from executive_assistant.tools.flow_project_tools import create_flow_project
        tools.append(create_flow_project)

    if _text_has_any(message_text, ["file", "folder", "directory", "path", "read file", "write file", "list files"]):
        tools.extend(await get_file_tools())

    if _text_has_any(message_text, ["tdb", "table", "sql", "database", "transactional database"]):
        tools.extend(await get_tdb_tools())

    if _text_has_any(
        message_text,
        [
            "vdb",
            "vector",
            "semantic",
            "embedding",
            "vector database",
            "collection",
            "collections",
        ],
    ):
        tools.extend(await get_vdb_tools())

    if _text_has_any(message_text, ["adb", "duckdb", "analytics", "aggregate", "join"]):
        tools.extend(await get_adb_tools())

    if _text_has_any(message_text, ["memory", "remember", "forget", "preference"]):
        tools.extend(await get_memory_tools())

    if _text_has_any(message_text, ["reminder", "remind", "schedule"]):
        tools.extend(await get_reminder_tools())

    if _text_has_any(message_text, ["time", "date", "timezone", "clock"]):
        tools.extend(await get_time_tools())

    if _text_has_any(message_text, ["python", "script", "code", "execute_python"]):
        tools.extend(await get_python_tools())

    if _text_has_any(message_text, ["search", "web", "browse", "crawl", "scrape", "firecrawl", "playwright"]):
        tools.extend(await get_search_tools())
        from executive_assistant.tools.firecrawl_tool import get_firecrawl_tools
        tools.extend(get_firecrawl_tools())
        tools.extend(await get_browser_tools())

    if _text_has_any(message_text, ["ocr", "image", "scan", "screenshot", "pdf"]):
        tools.extend(await get_ocr_tools())

    if _text_has_any(message_text, ["meta", "inventory", "system inventory"]):
        tools.extend(await get_meta_tools())

    if _text_has_any(message_text, ["mcp", "server", "tools config"]):
        from executive_assistant.tools.mcp_tools import get_mcp_config_tools
        tools.extend(get_mcp_config_tools())
        tools.extend(await load_mcp_tools_if_enabled())

    # Deduplicate by name
    deduped: dict[str, BaseTool] = {}
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
        if name and name not in deduped:
            deduped[name] = tool
    return [_normalize_tool(t) for t in deduped.values()]


async def load_mcp_tools_if_enabled() -> list[BaseTool]:
    """Load MCP tools from admin config if enabled."""
    tools: list[BaseTool] = []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from executive_assistant.storage.mcp_storage import load_mcp_config

        config = load_mcp_config()
        mcp_servers = config.get("mcpServers", {})
        if not config.get("mcpEnabled", False):
            return []
        if config.get("loadMcpTools", "default") == "disabled":
            return []

        global _mcp_client_cache
        cache_key = "all"
        if cache_key not in _mcp_client_cache:
            connections = {}
            for server_name, server_config in mcp_servers.items():
                try:
                    connections[server_name] = _mcp_server_to_connection(server_config)
                except Exception as e:
                    print(f"Warning: Invalid MCP server config for '{server_name}': {e}")
            if connections:
                client = MultiServerMCPClient(connections=connections)
                server_tools = await client.get_tools()
                tools.extend(server_tools)
                _mcp_client_cache[cache_key] = client
        else:
            try:
                server_tools = await _mcp_client_cache[cache_key].get_tools()
                tools.extend(server_tools)
            except Exception as e:
                print(f"Warning: Failed to load MCP tools: {e}")

    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")

    return tools


async def load_mcp_tools_tiered() -> list[BaseTool]:
    """Load MCP tools with tiered priority: User > Admin.

    Priority order:
    1. User-local MCP (stdio): data/users/{thread_id}/mcp/mcp.json
    2. User-remote MCP (HTTP/SSE): data/users/{thread_id}/mcp/mcp_remote.json
    3. Admin MCP (fallback): data/admins/mcp.json

    Returns:
        List of MCP tools from all sources (user tools override admin tools)

    Note:
        Tool name collisions: User tools take priority over admin tools
        with warnings logged when collisions occur.
    """
    tools: list[BaseTool] = []
    all_tool_names = set()

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from executive_assistant.storage.file_sandbox import get_thread_id
        from executive_assistant.storage.user_mcp_storage import UserMCPStorage

        thread_id = get_thread_id()

        # Priority 1: User-local MCP (highest priority)
        if thread_id:
            try:
                storage = UserMCPStorage(thread_id)
                user_local_config = storage.load_local_config()
                user_local_servers = user_local_config.get("mcpServers", {})

                if user_local_servers:
                    user_tools = await _load_mcp_servers(user_local_servers, "user-local")
                    tools.extend(user_tools)
                    all_tool_names.update(_get_tool_names(user_tools))
                    logger.debug(f"Loaded {len(user_tools)} user-local MCP tools")
            except Exception as e:
                logger.debug(f"Failed to load user-local MCP: {e}")

            # Priority 2: User-remote MCP (medium priority)
            try:
                user_remote_config = storage.load_remote_config()
                user_remote_servers = user_remote_config.get("mcpServers", {})

                if user_remote_servers:
                    user_tools = await _load_mcp_servers(user_remote_servers, "user-remote")
                    tools.extend(user_tools)
                    all_tool_names.update(_get_tool_names(user_tools))
                    logger.debug(f"Loaded {len(user_tools)} user-remote MCP tools")
            except Exception as e:
                logger.debug(f"Failed to load user-remote MCP: {e}")

        # Priority 3: Admin MCP (fallback, lowest priority)
        from executive_assistant.storage.mcp_storage import load_mcp_config

        admin_config = load_mcp_config()
        admin_servers = admin_config.get("mcpServers", {})

        if admin_servers:
            # Only load admin tools that don't collide with user tools
            filtered_servers = {}
            for name, config in admin_servers.items():
                # Check if this server would collide with user tools
                # (We can't know tool names without loading, so we load all
                # and deduplicate by name later)
                filtered_servers[name] = config

            if filtered_servers:
                admin_tools = await _load_mcp_servers(filtered_servers, "admin")
                # Deduplicate: user tools take priority
                for tool in admin_tools:
                    if tool.name not in all_tool_names:
                        tools.append(tool)
                        all_tool_names.add(tool.name)
                    else:
                        logger.debug(f"Admin MCP tool '{tool.name}' overridden by user tool")

                if admin_tools:
                    logger.debug(f"Loaded {len(admin_tools)} admin MCP tools (non-colliding)")

    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")

    return tools


async def _load_mcp_servers(
    servers: dict,
    source: str,
) -> list[BaseTool]:
    """Load tools from MCP servers.

    Args:
        servers: Dict of server_name -> server_config
        source: Source label for logging

    Returns:
        List of MCP tools
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    tools = []
    connections = {}

    for server_name, server_config in servers.items():
        try:
            connection = _mcp_server_to_connection(server_config)
            connections[server_name] = connection
        except Exception as e:
            print(f"Warning: Invalid MCP server config for '{server_name}' ({source}): {e}")

    if connections:
        client = MultiServerMCPClient(connections=connections)
        server_tools = await client.get_tools()
        tools.extend(server_tools)

    return tools


def _get_tool_names(tools: list[BaseTool]) -> set[str]:
    """Extract tool names from a list of tools.

    Args:
        tools: List of BaseTool instances

    Returns:
        Set of tool names
    """
    return {tool.name for tool in tools}


def clear_mcp_cache() -> int:
    """Clear the MCP client cache.

    This function clears all cached MCP connections, forcing a reload
    on the next tool loading. Use this when MCP configurations have changed.

    Returns:
        Number of cache entries cleared
    """
    global _mcp_client_cache

    cleared = len(_mcp_client_cache)
    _mcp_client_cache.clear()

    logger.debug(f"Cleared {cleared} MCP cache entries")
    return cleared


def get_mcp_cache_info() -> dict:
    """Get information about the MCP cache.

    Returns:
        Dict with cache size and keys
    """
    global _mcp_client_cache

    return {
        "size": len(_mcp_client_cache),
        "keys": list(_mcp_client_cache.keys()),
    }
