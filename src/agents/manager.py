"""Shared Agent Manager - single LangGraph instance for all channels."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.agents.factory import get_agent_factory
from src.app_logging import get_logger
from src.config import get_settings
from src.llm import create_model_from_config

logger = get_logger()

_agents: dict[str, Any] = {}
_model: BaseChatModel | None = None
_checkpoint_managers: dict[str, Any] = {}


def get_model() -> BaseChatModel:
    """Get or create the shared model."""
    global _model
    if _model is None:
        _model = create_model_from_config()
        model_name = getattr(_model, "model", "unknown")
        provider = getattr(_model, "_provider", "ollama")
        logger.info("agent_manager.model_initialized", {"provider": provider, "model": model_name})
    return _model


def get_default_tools(user_id: str) -> list[Any]:
    """Get default tools for a user with proper user_id binding."""
    from src.skills.example_constrained_tool import write_sql_query
    from src.tools.file_search import glob_search, grep_search
    from src.tools.filesystem import (
        delete_file,
        edit_file,
        list_files,
        read_file,
        write_file,
    )
    from src.tools.firecrawl import (
        cancel_crawl,
        crawl_url,
        get_crawl_status,
        map_url,
        scrape_url,
        search_web,
    )
    from src.tools.memory import get_conversation_history, search_conversation_hybrid
    from src.tools.shell import run_shell
    from src.tools.time import get_time
    from src.tools.todo import write_todos

    return [
        get_conversation_history,
        search_conversation_hybrid,
        list_files,
        read_file,
        write_file,
        edit_file,
        delete_file,
        glob_search,
        grep_search,
        run_shell,
        write_todos,
        get_time,
        scrape_url,
        search_web,
        map_url,
        crawl_url,
        get_crawl_status,
        cancel_crawl,
        write_sql_query,  # Example constrained tool
    ]


def get_agent(
    user_id: str = "default",
    tools: list[Any] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Get or create agent for user (shared across channels).

    NOTE: To avoid caching bugs, always use consistent parameters.
    If you need a different checkpointer, use a different user_id
    or call reset_agent() first.

    Args:
        user_id: User identifier
        tools: Tools to use (default: get_default_tools)
        checkpointer: Checkpointer for conversation persistence

    Returns:
        Compiled LangGraph agent
    """
    key = user_id

    if key not in _agents:
        model = get_model()
        effective_tools = tools or get_default_tools(user_id)

        settings = get_settings()
        base_prompt = getattr(
            settings.agent, "system_prompt", "You are a helpful executive assistant."
        )
        system_prompt = (
            base_prompt
            + f"""

user_id: {user_id}

## Available Tools:

1. **Filesystem tools** - Manage files in user's directory:
   - list_files: List files in a directory
   - read_file: Read file content
   - write_file: Create or overwrite a file
   - edit_file: Replace text in a file
   - delete_file: Delete a file (REQUIRES human approval first)

2. **Search tools** - Find files and content:
   - glob_search: Find files matching a pattern (e.g., "*.py")
   - grep_search: Search file contents using regex

3. **Shell tool** - Execute commands in user's directory:
   - run_shell: Run shell commands like `echo`, `python`, `node`, etc.
   - Use this when user wants to run commands, scripts, or get system info
   - DANGEROUS commands (rm, rmdir) require human approval

        4. **Todo tool** - Track tasks during complex multi-step operations:
           - write_todos: Manage todo list with actions: list/add/update/delete/replace
           - ALWAYS call write_todos with action="list" at the END of your response to show current todos
           - NEVER modify todos without showing the updated list
           - Use for multi-step tasks (e.g., "plan a trip", "refactor codebase", "research topic")
           - After ANY todo modification (add/update/delete/replace), you MUST immediately call write_todos(action="list") to display the updated list

        5. **Time tool** - Get current time:
           - get_time: Get current time, optionally for a specific timezone
           - If user mentions their location (e.g., "I'm in Sydney"), use that timezone
           - Common timezones: 'America/New_York', 'Europe/London', 'Asia/Shanghai', 'Australia/Sydney', etc.
           - Or use city names: 'New York', 'Shanghai', 'London', 'Sydney'

        6. **Web tools** - Scrape and search the web (requires API key):
            - scrape_url: Scrape a URL and get content (markdown, html, json)
            - search_web: Search the web and get results with content
            - map_url: Discover all URLs on a website
            - crawl_url: Crawl a website recursively (multiple pages)
            - get_crawl_status: Check status of a crawl job
            - cancel_crawl: Cancel a running crawl job
            - Set FIRECRAWL_API_KEY env var to enable (supports self-hosted with FIRECRAWL_BASE_URL)

IMPORTANT: Always use the default user_id parameter (already set to {user_id})."""
        )

        factory = get_agent_factory(checkpointer=checkpointer, enable_skills=True, user_id=user_id)
        _agents[key] = factory.create(
            model=model,
            tools=effective_tools,
            system_prompt=system_prompt,
        )
        logger.info("agent_manager.agent_created", {"user_id": user_id})

    return _agents[key]


async def get_checkpoint_manager(user_id: str) -> Any:
    """Get or create checkpoint manager for user."""
    if user_id not in _checkpoint_managers:
        from src.storage.checkpoint import init_checkpoint_manager

        _checkpoint_managers[user_id] = await init_checkpoint_manager(user_id)
    return _checkpoint_managers[user_id]


def reset_agent(user_id: str = "default") -> None:
    """Reset agent for a user (useful for testing)."""
    if user_id in _agents:
        del _agents[user_id]
    logger.info("agent_manager.agent_reset", {"user_id": user_id})


def reset_all() -> None:
    """Reset all agents (useful for testing)."""
    global _model
    _agents.clear()
    _model = None
    logger.info("agent_manager.reset_all")
