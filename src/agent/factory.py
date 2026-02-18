from __future__ import annotations
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain_core.tools import tool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config.settings import Settings, get_settings
from src.llm import get_llm
from src.memory import (
    MemoryStore,
    MEMORY_WORKFLOW,
    memory_delete,
    memory_get,
    memory_save,
    memory_search,
    memory_timeline,
    reset_memory_store,
    set_memory_store,
)

if TYPE_CHECKING:
    from langgraph.graph import CompiledStateGraph


@dataclass
class AgentContext:
    user_id: str
    project_id: str | None = None


_checkpointer_setup_done = False


def _make_user_backend_factory(user_id: str, data_path: Path):
    """Create a backend factory with user-isolated filesystem routes.

    Returns a factory function that receives runtime from create_deep_agent.

    Routes:
        /user/*     → /data/users/{user_id}/ (user's private data)
        /conversation_history/* → /data/users/{user_id}/.conversation_history/ (persistent summaries)
        /shared/*   → /data/shared/ (team-shared resources)
        /*          → StateBackend (ephemeral workspace, per-thread)

    The agent can organize its own structure within /user/ (e.g., /user/memories/)

    Args:
        user_id: User identifier for isolation
        data_path: Base data path (e.g., /data)

    Returns:
        Backend factory function for create_deep_agent
    """
    user_dir = data_path / "users" / user_id
    conversation_history_dir = user_dir / ".conversation_history"
    shared_dir = data_path / "shared"

    user_dir.mkdir(parents=True, exist_ok=True)
    conversation_history_dir.mkdir(parents=True, exist_ok=True)
    shared_dir.mkdir(parents=True, exist_ok=True)

    def make_backend(runtime) -> CompositeBackend:
        return CompositeBackend(
            default=StateBackend(runtime),
            routes={
                "/user/": FilesystemBackend(
                    root_dir=str(user_dir),
                    virtual_mode=True,
                ),
                "/conversation_history/": FilesystemBackend(
                    root_dir=str(conversation_history_dir),
                    virtual_mode=True,
                ),
                "/shared/": FilesystemBackend(
                    root_dir=str(shared_dir),
                    virtual_mode=True,
                ),
            },
        )

    return make_backend


@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information.

    Uses Tavily if configured, otherwise falls back to Firecrawl.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    settings = get_settings()

    if settings.tavily_api_key:
        return _web_search_tavily(query, settings.tavily_api_key)
    elif settings.firecrawl_api_key:
        return _web_search_firecrawl(query, settings.firecrawl_api_key, settings.firecrawl_base_url)
    else:
        return "Error: No search API configured. Set either TAVILY_API_KEY or FIRECRAWL_API_KEY in your .env file."


def _web_search_tavily(query: str, api_key: str) -> str:
    """Search using Tavily API."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    results = client.search(query, max_results=5)

    if not results.get("results"):
        return "No results found."

    output = []
    for r in results["results"]:
        output.append(
            f"**{r.get('title', 'Untitled')}**\n{r.get('url', '')}\n{r.get('content', '')}\n"
        )

    return "\n---\n".join(output)


def _web_search_firecrawl(query: str, api_key: str, base_url: str) -> str:
    """Search using Firecrawl API."""
    import httpx

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"query": query, "limit": 5}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{base_url}/search", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results = data.get("data", data.get("results", []))
        if not results:
            return "No results found."

        output = []
        for r in results[:5]:
            title = r.get("title", r.get("metadata", {}).get("title", "Untitled"))
            url = r.get("url", r.get("metadata", {}).get("sourceURL", ""))
            content = r.get("description", r.get("markdown", ""))[:300]
            output.append(f"**{title}**\n{url}\n{content}\n")

        return "\n---\n".join(output)
    except httpx.HTTPStatusError as e:
        return f"Error searching: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error searching: {e}"


@tool
def web_scrape(url: str) -> str:
    """Scrape content from a web page using Firecrawl.

    Args:
        url: The URL to scrape

    Returns:
        The page content as markdown
    """
    import httpx

    settings = get_settings()
    api_key = settings.firecrawl_api_key
    base_url = settings.firecrawl_base_url

    if not api_key:
        return "Error: FIRECRAWL_API_KEY not configured. Set it in your .env file."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "formats": ["markdown"]}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{base_url}/scrape", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "data" in data and "markdown" in data["data"]:
            return data["data"]["markdown"]
        return str(data.get("data", data))
    except httpx.HTTPStatusError as e:
        return f"Error scraping {url}: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error scraping {url}: {e}"


@tool
def web_crawl(url: str, max_pages: int = 10) -> str:
    """Crawl a website starting from a URL using Firecrawl.

    Args:
        url: The starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10)

    Returns:
        List of crawled URLs and their content summaries
    """
    import httpx

    settings = get_settings()
    api_key = settings.firecrawl_api_key
    base_url = settings.firecrawl_base_url

    if not api_key:
        return "Error: FIRECRAWL_API_KEY not configured. Set it in your .env file."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "limit": max_pages, "scrapeOptions": {"formats": ["markdown"]}}

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{base_url}/crawl", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("data", [])[:max_pages]:
            source_url = item.get("metadata", {}).get("sourceURL", item.get("url", "Unknown"))
            md_content = item.get("markdown", "")[:500]
            results.append(f"**{source_url}**\n{md_content}...\n")

        return "\n---\n".join(results) if results else "No pages crawled."
    except httpx.HTTPStatusError as e:
        return f"Error crawling {url}: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error crawling {url}: {e}"


@tool
def web_map(url: str, search_query: str | None = None) -> str:
    """Map a website to discover all URLs. Optionally filter by search query.

    Args:
        url: The base URL to map
        search_query: Optional search query to filter URLs (e.g., "blog", "docs")

    Returns:
        List of discovered URLs
    """
    import httpx

    settings = get_settings()
    api_key = settings.firecrawl_api_key
    base_url = settings.firecrawl_base_url

    if not api_key:
        return "Error: FIRECRAWL_API_KEY not configured. Set it in your .env file."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url}
    if search_query:
        payload["search"] = search_query

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{base_url}/map", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        links = data.get("links", [])
        if not links:
            return "No URLs found."

        return "\n".join(f"- {link}" for link in links[:50])
    except httpx.HTTPStatusError as e:
        return f"Error mapping {url}: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error mapping {url}: {e}"


@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Get the current time and date.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London').
                 Defaults to 'UTC'.

    Returns:
        Current time in the specified timezone with date and time information.
    """
    from datetime import datetime as dt
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(timezone)
        now = dt.now(tz)
        return (
            f"Current time in {timezone}:\n"
            f"📅 Date: {now.strftime('%Y-%m-%d (%A)')}\n"
            f"🕐 Time: {now.strftime('%H:%M:%S')}\n"
            f"🌍 Full datetime: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
    except Exception:
        # Fallback to UTC if timezone is invalid
        now = dt.now(dt_timezone.utc)
        return (
            f"Current time in UTC (fallback, timezone '{timezone}' not found):\n"
            f"📅 Date: {now.strftime('%Y-%m-%d (%A)')}\n"
            f"🕐 Time: {now.strftime('%H:%M:%S')}\n"
            f"🌍 Full datetime: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )


def _get_model(
    settings: Settings,
    model_override: tuple[str, str] | None = None,
):
    """Get the LLM model from settings or per-user override."""
    if model_override:
        provider, model = model_override
    else:
        provider, model = settings.llm.get_default_provider_model()
    return get_llm(provider=provider, model=model)


async def _ensure_checkpointer_setup(checkpointer: AsyncPostgresSaver) -> None:
    """Run LangGraph checkpoint schema setup once per process."""
    global _checkpointer_setup_done
    if _checkpointer_setup_done:
        return
    await checkpointer.setup()
    _checkpointer_setup_done = True


def _collect_skill_paths(settings: Settings, user_id: str) -> list[str]:
    """Collect skill paths from shared and user directories.

    Priority:
    1. Team skills - /data/shared/skills/
    2. User skills - /data/users/{user_id}/skills/
    """
    skill_paths = []

    team_skills = settings.shared_path / "skills"
    if team_skills.exists():
        skill_paths.append(str(team_skills))

    user_skills = settings.get_user_path(user_id) / "skills"
    if user_skills.exists():
        skill_paths.append(str(user_skills))

    return skill_paths


SUBAGENTS = [
    {
        "name": "coder",
        "description": "Write, debug, and refactor code. Use for programming tasks.",
        "system_prompt": """You are a specialized coding assistant. Write clean, well-documented code.

CRITICAL - Filesystem Path Rules:
- Virtual `/user/` maps to real path `./data/users/{user_id}/` (persistent storage)
- ALWAYS create code files with `/user/` prefix: `/user/projects/weather/code.py`
- Files at root level (no prefix) are LOST after conversation
- Use `/shared/` for reusable code templates""",
    },
    {
        "name": "researcher",
        "description": "Search the web and gather information. Use for research tasks.",
        "system_prompt": """You are a specialized research assistant. Gather and synthesize information from web search and scraping tools.

CRITICAL - Filesystem Path Rules:
- Virtual `/user/` maps to real path `./data/users/{user_id}/` (persistent storage)
- ALWAYS save research with `/user/` prefix: `/user/research/topic.md`
- Use `/shared/` for team knowledge base articles""",
    },
    {
        "name": "planner",
        "description": "Break down complex tasks into actionable steps. Use for planning.",
        "system_prompt": """You are a specialized planning assistant. Analyze and organize complex tasks into manageable steps.

CRITICAL - Filesystem Path Rules:
- Virtual `/user/` maps to real path `./data/users/{user_id}/` (persistent storage)
- ALWAYS save plans with `/user/` prefix: `/user/plans/project-plan.md`
- Use `/shared/` for project templates""",
    },
]


def _build_system_prompt(agent_name: str) -> str:
    """Build the system prompt with the agent's name and memory workflow."""
    return f"""You are {agent_name}, a deep agent with executive assistant capabilities.

## Filesystem Structure (CRITICAL - Read This!)
You work with a VIRTUAL filesystem that maps to REAL disk paths:

### Virtual Path → Real Path Mapping
- `/user/` → `./data/users/{{user_id}}/` (YOUR PERSISTENT STORAGE)
- `/shared/` → `./data/shared/` (team-shared resources)
- (no prefix) → Ephemeral memory (CLEARED after conversation, DO NOT USE for persistence)

### Examples
| What You Create | Virtual Path | Real Disk Path |
|----------------|--------------|----------------|
| Personal project file | `/user/projects/weather/forecast.md` | `./data/users/{{user_id}}/projects/weather/forecast.md` |
| Meeting notes | `/user/notes/meeting-2026-02-17.md` | `./data/users/{{user_id}}/notes/meeting-2026-02-17.md` |
| Reusable skill | `/shared/skills/weather-forecast.md` | `./data/shared/skills/weather-forecast.md` |
| ❌ WRONG (will be lost) | `/skills/weather/sydney.md` | (ephemeral, deleted after conversation)

### Golden Rules
1. **ALWAYS** start file paths with `/user/` for personal files (this ensures persistence)
2. **ALWAYS** start with `/shared/` for team artifacts (visible to all users)
3. **NEVER** create files at root level - they WILL BE LOST after the conversation ends
4. If you want to keep something, use `/user/` prefix - no exceptions!

## Capabilities
- **Time & Date**: Get current time in any timezone using get_current_time
- **Memory**: Remember and retrieve information about the user using memory tools
- **Planning**: Break down complex tasks using the todo list
- **File Operations**: Read, write, edit files (remember `/user/` prefix!)
- **Web Search**: Use web_search to find current information
- **Web Scraping**: Use web_scrape, web_crawl, web_map for web data
- **Subagents**: Delegate specialized work to coder, researcher, or planner

{MEMORY_WORKFLOW}

## Guidelines
1. **CRITICAL**: Always create files with `/user/` prefix for persistence (e.g., `/user/projects/...`)
2. Organize user data in `/user/` with clear structure: `/user/memories/`, `/user/projects/`, `/user/notes/`
3. Check `/shared/` for team resources and skills
4. Save important information about the user using memory_save
5. Search memories before asking the user for information they may have already shared
6. Ask for clarification when uncertain about user needs
"""


@asynccontextmanager
async def create_ea_agent(
    settings: Settings | None = None,
    user_id: str = "default",
    model_override: tuple[str, str] | None = None,
    skills: list[str] | None = None,
) -> AsyncIterator[CompiledStateGraph]:
    """Create an Executive Assistant deep agent with Postgres checkpoints and user-isolated memory.

    Args:
        settings: Application settings (defaults to global settings)
        user_id: User identifier for memory isolation
        model_override: Optional per-user model override `(provider, model)`
        skills: Override skill paths (if None, uses three-tier skill system)

    Yields:
        Compiled LangGraph agent ready for invocation
    """
    if settings is None:
        settings = get_settings()

    model = _get_model(settings, model_override=model_override)

    # Set model profile for summarization middleware
    # The SummarizationMiddleware (built-in to create_deep_agent) uses
    # _compute_summarization_defaults(model) which checks model.profile["max_input_tokens"]
    # to calculate trigger threshold (85% of max tokens). If profile is None, it defaults
    # to 170,000 tokens trigger, which is too high.
    # We set the profile based on the configured threshold_tokens to control when summarization triggers.
    if hasattr(model, "profile"):
        # Calculate max_input_tokens from threshold_tokens
        # trigger = 0.85 * max_input_tokens, so max_input_tokens = threshold / 0.85
        threshold = settings.middleware.summarization.threshold_tokens
        max_input_tokens = int(threshold / 0.85)  # Round to nearest integer

        model.profile = {"max_input_tokens": max_input_tokens}

    # Convert SQLAlchemy async URL to psycopg-compatible URL for LangGraph
    db_uri = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    agent_name = settings.agent_name
    user_path = settings.get_user_path(user_id)

    memory_store = MemoryStore(user_id=user_id, data_path=user_path)
    memory_store_token = set_memory_store(memory_store)

    try:
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            await _ensure_checkpointer_setup(checkpointer)

            skill_paths = skills if skills is not None else _collect_skill_paths(settings, user_id)

            # Create middlewares from configuration
            from src.middleware.factory import create_middleware_from_config
            import logging

            logger = logging.getLogger(__name__)

            logger.info("[AgentFactory] Creating middlewares for user %s...", user_id)
            middlewares = create_middleware_from_config(
                config=settings.middleware,
                memory_store=memory_store,
                user_id=user_id,
            )
            logger.info("[AgentFactory] Created %s middlewares", len(middlewares))

            agent_kwargs: dict[str, Any] = {
                "name": f"ea-{user_id}",
                "model": model,
                "system_prompt": _build_system_prompt(agent_name),
                "checkpointer": checkpointer,
                "backend": _make_user_backend_factory(user_id, settings.data_path),
                "tools": [
                    get_current_time,
                    web_search,
                    web_scrape,
                    web_crawl,
                    web_map,
                    memory_search,
                    memory_timeline,
                    memory_get,
                    memory_save,
                    memory_delete,
                ],
                "subagents": SUBAGENTS,
            }

            # Only add middleware if we have any
            if middlewares:
                agent_kwargs["middleware"] = middlewares

            if skill_paths:
                agent_kwargs["skills"] = skill_paths

            agent = create_deep_agent(**agent_kwargs)
            yield agent
    finally:
        try:
            memory_store.close()
        finally:
            reset_memory_store(memory_store_token)
