"""Tool registry for aggregating all available tools."""

from langchain_core.tools import BaseTool
from typing import Any

from executive_assistant.storage.file_sandbox import (
    list_files,
    read_file,
    write_file,
)

_mcp_client_cache: dict[str, Any] = {}


def clear_mcp_cache() -> None:
    """Clear MCP client cache to force reload."""
    global _mcp_client_cache
    _mcp_client_cache.clear()


async def get_confirmation_tools() -> list[BaseTool]:
    """Get user confirmation tools for large operations."""
    from executive_assistant.tools.confirmation_tool import confirmation_request
    return [confirmation_request]


async def get_file_tools() -> list[BaseTool]:
    """Get file operation tools."""
    from executive_assistant.storage.file_sandbox import (
        read_file,
        write_file,
        list_files,
        create_folder,
        delete_folder,
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
        rename_folder,
        move_file,
        glob_files,
        grep_files,
    ]


async def get_db_tools() -> list[BaseTool]:
    """Get DB tabular data tools (thread-scoped)."""
    from executive_assistant.storage.db_tools import (
        create_db_table,
        insert_db_table,
        query_db,
        list_db_tables,
        describe_db_table,
        delete_db_table,
        export_db_table,
        import_db_table,
    )
    return [
        create_db_table,
        insert_db_table,
        query_db,
        list_db_tables,
        describe_db_table,
        delete_db_table,
        export_db_table,
        import_db_table,
    ]


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

async def get_ocr_tools() -> list[BaseTool]:
    """Get OCR tools."""
    from executive_assistant.tools.ocr_tool import get_ocr_tools as _get
    return _get()



async def get_skills_tools() -> list[BaseTool]:
    """Get skills tools for on-demand skill loading."""
    from executive_assistant.skills.tool import load_skill
    return [load_skill]


async def get_vs_tools() -> list[BaseTool]:
    """Get Vector Store tools backed by LanceDB for high-performance vector search."""
    from executive_assistant.storage.vs_tools import get_vs_tools as _get
    return await _get()


async def get_memory_tools() -> list[BaseTool]:
    """Get Memory tools for storing and retrieving user memories."""
    from executive_assistant.tools.mem_tools import get_memory_tools as _get
    return _get()


async def get_identity_tools() -> list[BaseTool]:
    """Get identity merge tools for user identity consolidation."""
    from executive_assistant.tools.identity_tools import (
        request_identity_merge,
        confirm_identity_merge,
        merge_additional_identity,
        get_my_identity,
    )
    return [
        request_identity_merge,
        confirm_identity_merge,
        merge_additional_identity,
        get_my_identity,
    ]


async def get_mcp_tools() -> list[BaseTool]:
    """
    Get tools from MCP servers configured in admin mcp.json.

    This connects to the configured MCP servers (Firecrawl, Chrome DevTools,
    Meilisearch) and converts their tools to LangChain-compatible format.

    Returns:
        List of LangChain tools from MCP servers.
    """
    tools = []

    try:
        from langchain_mcp_adapters import MCPClient
        from pathlib import Path
        import json

        from executive_assistant.storage.mcp_storage import get_admin_mcp_config_path
        mcp_config_path = get_admin_mcp_config_path()
        if not mcp_config_path.exists():
            return tools

        with open(mcp_config_path) as f:
            mcp_config = json.load(f)

        # Connect to each MCP server and get tools
        for server_name, server_config in mcp_config.get("mcpServers", {}).items():
            try:
                client = MCPClient(server_config)
                server_tools = await client.get_tools()
                tools.extend(server_tools)
            except Exception as e:
                print(f"Warning: Failed to connect to MCP server '{server_name}': {e}")

    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")
    except Exception as e:
        print(f"Warning: Error loading MCP tools: {e}")

    return tools


def get_standard_tools() -> list[BaseTool]:
    """Get standard LangChain tools."""
    tools = []

    # Add Tavily search if API key is available
    try:
        from langchain_community.tools import TavilySearchResults
        import os

        if os.getenv("TAVILY_API_KEY"):
            tools.append(TavilySearchResults(max_results=5))
    except ImportError:
        pass
    except Exception:
        pass

    return tools


async def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Aggregates tools from:
    - File operations (read_file, write_file, list_files, create_folder, delete_folder, rename_folder, move_file, glob_files, grep_files)
    - Database operations (create_db_table, query_db, etc. with scope="context"|"shared")
    - Vector Store (create_vs_collection, search_vs, vs_list, etc.)
    - Memory (create_memory, update_memory, delete_memory, list_memories, search_memories, etc.)
    - Identity (request_identity_merge, confirm_identity_merge, merge_additional_identity, get_my_identity)
    - Time tools (get_current_time, get_current_date, list_timezones)
    - Reminder tools (reminder_set with dateparser, reminder_list, reminder_cancel, reminder_edit)
    - Python execution (execute_python for calculations and data processing)
    - Web search (search_web via SearXNG)
    - OCR (extract text/structured data from images/PDFs)
    - Confirmation (confirmation_request for large operations)
    - Standard tools (search)
    - **MCP configuration** (get_mcp_config, reload_mcp_tools, enable_mcp_tools, disable_mcp_tools, add_mcp_server, remove_mcp_server)
    - **MCP tools** (auto-loaded if enabled via load_mcp_tools_if_enabled)
    - **Skills** (load_skill)
    """
    all_tools = []

    # Add file tools
    all_tools.extend(await get_file_tools())

    # Add database tools
    all_tools.extend(await get_db_tools())

    # Add skills tools
    all_tools.extend(await get_skills_tools())

    # Add VS tools
    all_tools.extend(await get_vs_tools())

    # Add memory tools
    all_tools.extend(await get_memory_tools())

    # Add identity tools
    all_tools.extend(await get_identity_tools())

    # Add time tools
    all_tools.extend(await get_time_tools())

    # Add reminder tools
    all_tools.extend(await get_reminder_tools())

    # Add meta tools
    all_tools.extend(await get_meta_tools())

    # Add python tools
    all_tools.extend(await get_python_tools())

    # Add search tools
    all_tools.extend(await get_search_tools())

    # Add OCR tools
    all_tools.extend(await get_ocr_tools())

    # Add confirmation tools
    all_tools.extend(await get_confirmation_tools())

    # Add Firecrawl tools (only if API key is configured)
    from executive_assistant.tools.firecrawl_tool import get_firecrawl_tools
    all_tools.extend(get_firecrawl_tools())

    # Add MCP configuration tools ✅ NEW
    from executive_assistant.tools.mcp_tools import get_mcp_config_tools
    all_tools.extend(get_mcp_config_tools())

    # Add standard tools
    all_tools.extend(get_standard_tools())

    # Load MCP tools if enabled ✅ NEW
    from executive_assistant.tools.registry import load_mcp_tools_if_enabled
    all_tools.extend(await load_mcp_tools_if_enabled())

    return all_tools


async def load_mcp_tools_if_enabled() -> list[BaseTool]:
    """
    Load MCP tools from admin config if enabled.

    Returns:
        List of LangChain tools from MCP servers.
    """
    tools = []

    try:
        from langchain_mcp_adapters import MCPClient
        from executive_assistant.storage.mcp_storage import load_mcp_config

        config = load_mcp_config()
        mcp_servers = config.get("mcpServers", {})
        if not config.get("mcpEnabled", False):
            return []
        if config.get("loadMcpTools", "default") == "disabled":
            return []

        global _mcp_client_cache
        for server_name, server_config in mcp_servers.items():
            cache_key = server_name
            if cache_key not in _mcp_client_cache:
                try:
                    client = MCPClient(server_config)
                    server_tools = await client.get_tools()
                    tools.extend(server_tools)
                    _mcp_client_cache[cache_key] = client
                except Exception as e:
                    print(f"Warning: Failed to connect to MCP server '{server_name}': {e}")

    except ImportError:
        print("Warning: langchain-mcp-adapters not installed. MCP tools unavailable.")

    return tools
