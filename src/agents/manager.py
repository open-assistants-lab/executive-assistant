"""Agent Manager with per-user pool for concurrent request handling."""

import asyncio
import uuid
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

from langchain_core.language_models import BaseChatModel

from src.agents.factory import get_agent_factory
from src.app_logging import get_logger
from src.config import get_settings
from src.llm import create_model_from_config

logger = get_logger()

_model: BaseChatModel | None = None
_checkpoint_managers: dict[str, Any] = {}
_agent_pools: dict[str, "AgentPool"] = {}
_pools_lock = asyncio.Lock()


def _get_pool_size() -> int:
    """Get pool size from settings, default to 3."""
    try:
        settings = get_settings()
        return int(getattr(settings.agent, "pool_size", 3))
    except Exception:
        return 3


class AgentInstance:
    """Single agent instance with its own thread_id."""

    def __init__(self, agent: Any, thread_id: str):
        self.agent = agent
        self.thread_id = thread_id
        self.in_use = False


class AgentPool:
    """Per-user agent pool with thread-safe acquisition."""

    def __init__(self, user_id: str, pool_size: int = 3):
        self.user_id = user_id
        self.pool_size = pool_size
        self._pool: deque[AgentInstance] = deque()
        self._lock = asyncio.Lock()
        self._logger = logger

    async def _create_agent_instance(self, thread_id: str) -> AgentInstance:
        """Create a new agent instance."""
        model = get_model()
        tools = get_default_tools(self.user_id)
        settings = get_settings()
        base_prompt = getattr(
            settings.agent, "system_prompt", "You are a helpful executive assistant."
        )
        system_prompt = base_prompt + f"\n\nuser_id: {self.user_id}\n"

        checkpoint_manager = await get_checkpoint_manager(self.user_id)
        checkpointer = checkpoint_manager.checkpointer

        factory = get_agent_factory(
            checkpointer=checkpointer, enable_skills=True, user_id=self.user_id
        )
        agent = factory.create(model=model, tools=tools, system_prompt=system_prompt)

        self._logger.info(
            "agent_pool.instance_created",
            {"user_id": self.user_id, "thread_id": thread_id},
        )

        return AgentInstance(agent=agent, thread_id=thread_id)

    @asynccontextmanager
    async def acquire(self) -> "asynccontextmanager[AgentInstance]":
        """Acquire an agent from the pool, creating one if needed."""
        async with self._lock:
            if self._pool:
                instance = self._pool.popleft()
                self._logger.debug(
                    "agent_pool.instance_reused",
                    {"user_id": self.user_id, "thread_id": instance.thread_id},
                )
            else:
                thread_id = f"{self.user_id}_{uuid.uuid4().hex[:8]}"
                instance = await self._create_agent_instance(thread_id)

            instance.in_use = True

        try:
            yield instance
        finally:
            async with self._lock:
                if len(self._pool) < self.pool_size:
                    instance.in_use = False
                    self._pool.append(instance)
                    self._logger.debug(
                        "agent_pool.instance_returned",
                        {"user_id": self.user_id, "thread_id": instance.thread_id},
                    )
                else:
                    self._logger.debug(
                        "agent_pool.instance_discarded",
                        {"user_id": self.user_id, "thread_id": instance.thread_id},
                    )

    def get_config(self, instance: AgentInstance) -> dict[str, Any]:
        """Get LangGraph config for an agent instance."""
        return {"configurable": {"thread_id": instance.thread_id}}


async def get_agent_pool(user_id: str) -> AgentPool:
    """Get or create agent pool for a user."""
    async with _pools_lock:
        if user_id not in _agent_pools:
            pool_size = _get_pool_size()
            _agent_pools[user_id] = AgentPool(user_id, pool_size)
            logger.info("agent_pool.created", {"user_id": user_id, "pool_size": pool_size})
        return _agent_pools[user_id]


async def run_agent(
    user_id: str,
    messages: list[Any],
    message: str,
) -> dict[str, Any]:
    """Run agent with pool - main entry point for HTTP server."""
    pool = await get_agent_pool(user_id)

    async with pool.acquire() as instance:
        config = pool.get_config(instance)

        from src.app_logging import get_logger, timer

        app_logger = get_logger()
        if app_logger.langfuse_handler:
            config["callbacks"] = [app_logger.langfuse_handler]

        with timer("agent", {"message": message, "user_id": user_id}, channel="http"):
            result = await instance.agent.ainvoke(
                {"messages": messages},
                config=config,
            )

    return result  # type: ignore[return-value]


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
    from src.tools.email import (
        email_accounts,
        email_connect,
        email_delete,
        email_disconnect,
        email_get,
        email_list,
        email_search,
        email_send,
        email_stats,
        email_sync,
        run_email_sql,
    )
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
        write_sql_query,
        email_connect,
        email_disconnect,
        email_accounts,
        email_sync,
        email_list,
        email_get,
        email_delete,
        email_search,
        email_send,
        email_stats,
        run_email_sql,
    ]


async def get_checkpoint_manager(user_id: str) -> Any:
    """Get or create checkpoint manager for user."""
    if user_id not in _checkpoint_managers:
        from src.storage.checkpoint import init_checkpoint_manager

        _checkpoint_managers[user_id] = await init_checkpoint_manager(user_id)
    return _checkpoint_managers[user_id]


def reset_agent(user_id: str = "default") -> None:
    """Reset agent pool for a user."""
    if user_id in _agent_pools:
        del _agent_pools[user_id]
    logger.info("agent_manager.agent_reset", {"user_id": user_id})


def reset_all() -> None:
    """Reset all agents and pools."""
    global _model
    _agent_pools.clear()
    _model = None
    logger.info("agent_manager.reset_all", {})
