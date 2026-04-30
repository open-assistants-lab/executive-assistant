"""SDK-native tools registry.

This module serves as the single source of truth for all SDK-native tools.
Tools are registered here as they are migrated to the SDK @tool decorator
(from src.sdk.tools).

The runner's _build_tool_list() calls get_native_tools() which returns all
registered ToolDefinitions. Native tools take priority over adapted LangChain
tools of the same name.
"""

from src.sdk.tools import ToolRegistry
from src.sdk.tools_core.apps import (
    app_column_add,
    app_column_delete,
    app_column_rename,
    app_create,
    app_delete,
    app_delete_row,
    app_insert,
    app_list,
    app_query,
    app_schema,
    app_search_fts,
    app_search_hybrid,
    app_search_semantic,
    app_update,
)
from src.sdk.tools_core.browser import (
    browser_back,
    browser_click,
    browser_close_all,
    browser_eval,
    browser_fill,
    browser_forward,
    browser_get_html,
    browser_get_text,
    browser_get_title,
    browser_get_url,
    browser_hover,
    browser_open,
    browser_press,
    browser_screenshot,
    browser_scroll,
    browser_sessions,
    browser_snapshot,
    browser_status,
    browser_tab_close,
    browser_tab_new,
    browser_type,
    browser_wait_text,
)
from src.sdk.tools_core.file_search import (
    files_glob_search,
    files_grep_search,
)
from src.sdk.tools_core.file_versioning import (
    files_versions_clean,
    files_versions_delete,
    files_versions_list,
    files_versions_restore,
)
from src.sdk.tools_core.filesystem import (
    files_delete,
    files_edit,
    files_list,
    files_mkdir,
    files_read,
    files_rename,
    files_write,
)
from src.sdk.tools_core.firecrawl import (
    cancel_crawl,
    crawl_url,
    firecrawl_agent,
    firecrawl_status,
    get_crawl_status,
    map_url,
    scrape_url,
    search_web,
)
from src.sdk.tools_core.mcp import (
    mcp_list,
    mcp_reload,
    mcp_tools,
)
from src.sdk.tools_core.memory import (
    memory_connect,
    memory_get_history,
    memory_search,
    memory_search_all,
    memory_search_insights,
)
from src.sdk.tools_core.shell import shell_execute
from src.sdk.tools_core.skills import (
    skill_create,
    skills_list,
    skills_load,
    skills_search,
    sql_write_query,
)
from src.sdk.tools_core.subagent import (
    subagent_cancel,
    subagent_create,
    subagent_delete,
    subagent_instruct,
    subagent_invoke,
    subagent_list,
    subagent_progress,
    subagent_update,
)
from src.sdk.tools_core.time import time_get
from src.sdk.tools_core.workspace import (
    workspace_create,
    workspace_delete,
    workspace_list,
    workspace_current,
    workspace_switch,
)

_registry = ToolRegistry()


def _register_all() -> None:
    registry = _registry

    registry.register(time_get)
    registry.register(shell_execute)

    registry.register(files_list)
    registry.register(files_read)
    registry.register(files_write)
    registry.register(files_edit)
    registry.register(files_delete)
    registry.register(files_mkdir)
    registry.register(files_rename)
    registry.register(files_glob_search)
    registry.register(files_grep_search)
    registry.register(files_versions_list)
    registry.register(files_versions_restore)
    registry.register(files_versions_delete)
    registry.register(files_versions_clean)

    registry.register(memory_get_history)
    registry.register(memory_search)
    registry.register(memory_search_all)
    registry.register(memory_search_insights)
    registry.register(memory_connect)

    registry.register(scrape_url)
    registry.register(search_web)
    registry.register(map_url)
    registry.register(crawl_url)
    registry.register(get_crawl_status)
    registry.register(cancel_crawl)
    registry.register(firecrawl_status)
    registry.register(firecrawl_agent)

    registry.register(browser_open)
    registry.register(browser_snapshot)
    registry.register(browser_click)
    registry.register(browser_fill)
    registry.register(browser_type)
    registry.register(browser_press)
    registry.register(browser_scroll)
    registry.register(browser_hover)
    registry.register(browser_screenshot)
    registry.register(browser_eval)
    registry.register(browser_get_title)
    registry.register(browser_get_text)
    registry.register(browser_get_html)
    registry.register(browser_get_url)
    registry.register(browser_tab_new)
    registry.register(browser_tab_close)
    registry.register(browser_back)
    registry.register(browser_forward)
    registry.register(browser_wait_text)
    registry.register(browser_sessions)
    registry.register(browser_close_all)
    registry.register(browser_status)

    registry.register(app_create)
    registry.register(app_list)
    registry.register(app_schema)
    registry.register(app_delete)
    registry.register(app_insert)
    registry.register(app_update)
    registry.register(app_delete_row)
    registry.register(app_column_add)
    registry.register(app_column_delete)
    registry.register(app_column_rename)
    registry.register(app_query)
    registry.register(app_search_fts)
    registry.register(app_search_semantic)
    registry.register(app_search_hybrid)

    registry.register(subagent_create)
    registry.register(subagent_invoke)
    registry.register(subagent_list)
    registry.register(subagent_progress)
    registry.register(subagent_instruct)
    registry.register(subagent_cancel)
    registry.register(subagent_delete)
    registry.register(subagent_update)

    registry.register(workspace_create)
    registry.register(workspace_list)
    registry.register(workspace_switch)
    registry.register(workspace_current)
    registry.register(workspace_delete)

    registry.register(mcp_list)
    registry.register(mcp_reload)
    registry.register(mcp_tools)

    registry.register(skills_list)
    registry.register(skills_search)
    registry.register(skills_load)
    registry.register(skill_create)
    registry.register(sql_write_query)

    # Agent Connect meta-tools
    try:
        from agent_connect.meta_tools import (
            connector_connect,
            connector_disconnect,
            connector_health,
            connector_list,
        )

        registry.register(connector_list)
        registry.register(connector_connect)
        registry.register(connector_disconnect)
        registry.register(connector_health)
    except ImportError:
        pass


_register_all()


def get_native_tools() -> list:
    """Return all registered SDK-native ToolDefinitions."""
    return _registry.list_tools()


def get_native_tool_names() -> set[str]:
    """Return the set of all registered SDK-native tool names."""
    return set(_registry.list_names())
