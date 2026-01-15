"""Tool registry for aggregating all available tools."""

from langchain_core.tools import BaseTool

from cassey.storage.file_sandbox import list_files, read_file, write_file


async def get_confirmation_tools() -> list[BaseTool]:
    """Get user confirmation tools for large operations."""
    from cassey.tools.confirmation_tool import request_confirmation
    return [request_confirmation]


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
    """Get workspace database tabular data tools (thread-scoped)."""
    from cassey.storage.db_tools import (
        db_create_table,
        db_insert_table,
        db_query,
        db_list_tables,
        db_describe_table,
        db_drop_table,
        db_export_table,
        db_import_table,
    )
    return [
        db_create_table,
        db_insert_table,
        db_query,
        db_list_tables,
        db_describe_table,
        db_drop_table,
        db_export_table,
        db_import_table,
    ]


async def get_time_tools() -> list[BaseTool]:
    """Get time and date tools."""
    from cassey.tools.time_tool import get_current_time, get_current_date, list_timezones
    return [get_current_time, get_current_date, list_timezones]


async def get_reminder_tools() -> list[BaseTool]:
    """Get reminder tools."""
    from cassey.tools.reminder_tools import get_reminder_tools as _get
    return _get()


async def get_python_tools() -> list[BaseTool]:
    """Get Python code execution tools."""
    from cassey.tools.python_tool import get_python_tools as _get
    return _get()


async def get_search_tools() -> list[BaseTool]:
    """Get web search tools."""
    from cassey.tools.search_tool import get_search_tools as _get
    return _get()


async def get_orchestrator_tools() -> list[BaseTool]:
    """Get orchestrator tools for delegation."""
    from cassey.tools.orchestrator_tools import get_orchestrator_tools as _get
    return _get()


async def get_kb_tools() -> list[BaseTool]:
    """Get Knowledge Base tools with full-text search."""
    from cassey.storage.kb_tools import get_kb_tools as _get
    return await _get()


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

    # Add calculator tool
    from langchain_core.tools import tool

    @tool
    def calculator(expression: str) -> str:
        """
        Evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate.

        Returns:
            Result of the calculation.

        Examples:
            >>> calculator("2 + 2")
            "4"
            >>> calculator("10 * 5")
            "50"
        """
        try:
            # Safe evaluation of math expressions
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    tools.append(calculator)

    return tools


async def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Aggregates tools from:
    - File operations (read, write, list, create_folder, delete_folder, rename_folder, move_file, glob_files, grep_files)
    - Database operations (db_create_table, db_query, etc.)
    - Knowledge Base (kb_store, kb_search, kb_list, etc.)
    - Time tools (get_current_time, get_current_date, list_timezones)
    - Reminder tools (set_reminder, list_reminders, cancel_reminder, edit_reminder)
    - Python execution (execute_python for calculations and data processing)
    - Web search (web_search via SearXNG)
    - Orchestrator (delegate_to_orchestrator for scheduling and workflows)
    - Confirmation (request_confirmation for large operations)
    - Standard tools (calculator, search)

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

    # Add KB tools
    all_tools.extend(await get_kb_tools())

    # Add time tools
    all_tools.extend(await get_time_tools())

    # Add reminder tools
    all_tools.extend(await get_reminder_tools())

    # Add python tools
    all_tools.extend(await get_python_tools())

    # Add search tools
    all_tools.extend(await get_search_tools())

    # Add orchestrator tools
    all_tools.extend(await get_orchestrator_tools())

    # Add confirmation tools
    all_tools.extend(await get_confirmation_tools())

    # MCP tools are NOT loaded by default - use get_mcp_tools() manually if needed

    # Add standard tools
    all_tools.extend(get_standard_tools())

    return all_tools
