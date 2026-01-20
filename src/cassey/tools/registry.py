"""Tool registry for aggregating all available tools."""

from langchain_core.tools import BaseTool

from cassey.storage.file_sandbox import (
    list_files,
    read_file,
    write_file,
)


async def get_confirmation_tools() -> list[BaseTool]:
    """Get user confirmation tools for large operations."""
    from cassey.tools.confirmation_tool import confirmation_request
    return [confirmation_request]


async def get_file_tools() -> list[BaseTool]:
    """Get file operation tools."""
    from cassey.storage.file_sandbox import (
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
    from cassey.storage.db_tools import (
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
    from cassey.tools.time_tool import get_current_time, get_current_date, list_timezones
    return [get_current_time, get_current_date, list_timezones]


async def get_reminder_tools() -> list[BaseTool]:
    """Get reminder tools."""
    from cassey.tools.reminder_tools import get_reminder_tools as _get
    return _get()


async def get_meta_tools() -> list[BaseTool]:
    """Get system metadata tools."""
    from cassey.tools.meta_tools import get_meta_tools as _get
    return _get()


async def get_python_tools() -> list[BaseTool]:
    """Get Python code execution tools."""
    from cassey.tools.python_tool import get_python_tools as _get
    return _get()


async def get_search_tools() -> list[BaseTool]:
    """Get web search tools."""
    from cassey.tools.search_tool import get_search_tools as _get
    return _get()

async def get_ocr_tools() -> list[BaseTool]:
    """Get OCR tools."""
    from cassey.tools.ocr_tool import get_ocr_tools as _get
    return _get()



async def get_skills_tools() -> list[BaseTool]:
    """Get skills tools for on-demand skill loading."""
    from cassey.skills.tool import load_skill
    return [load_skill]


async def get_vs_tools() -> list[BaseTool]:
    """Get Vector Store tools backed by LanceDB for high-performance vector search."""
    from cassey.storage.vs_tools import get_vs_tools as _get
    return await _get()


async def get_memory_tools() -> list[BaseTool]:
    """Get Memory tools for storing and retrieving user memories."""
    from cassey.tools.mem_tools import get_memory_tools as _get
    return _get()


async def get_identity_tools() -> list[BaseTool]:
    """Get identity merge tools for user identity consolidation."""
    from cassey.tools.identity_tools import (
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
    Get tools from MCP servers configured in .mcp.json.

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

        mcp_config_path = Path(".mcp.json")
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
    - Web scraping (firecrawl_scrape, firecrawl_crawl via Firecrawl API)
    - Confirmation (confirmation_request for large operations)
    - Standard tools (search)

    Note: MCP tools are available via get_mcp_tools() but not loaded by default.
    They can be loaded manually if needed for specific use cases.

    Returns:
        List of all available LangChain tools.
    """
    all_tools = []

    # Add file tools
    all_tools.extend(await get_file_tools())

    # Add database tools
    all_tools.extend(await get_db_tools())

    # Add skills tools (load_skill)
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
    from cassey.tools.firecrawl_tool import get_firecrawl_tools
    all_tools.extend(get_firecrawl_tools())

    # MCP tools are NOT loaded by default - use get_mcp_tools() manually if needed

    # Add standard tools
    all_tools.extend(get_standard_tools())

    return all_tools
