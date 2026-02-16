"""Factory for creating middleware instances from configuration.

Centralizes middleware creation logic and ensures consistency.
Supports both custom middlewares and built-in deepagents middlewares.

Usage:
    from src.middleware import create_middleware_from_config

    middlewares = create_middleware_from_config(
        config=settings.middleware,
        memory_store=store,
        user_id=user_id,
        summarization_model=summarization_llm
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.config.middleware_settings import MiddlewareConfig
from src.config.settings import parse_model_string
from src.llm import get_llm

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.language_models.chat_models import BaseChatModel

    try:
        from src.memory import MemoryStore
    except ImportError:
        MemoryStore = None


def create_middleware_from_config(
    config: MiddlewareConfig,
    memory_store: MemoryStore | None = None,
    user_id: str = "default",
    summarization_model: BaseChatModel | None = None,
) -> list[AgentMiddleware]:
    """Create middleware instances from configuration.

    Instantiates all enabled middlewares based on the provided configuration.
    Supports both custom middlewares and built-in deepagents middlewares.

    Args:
        config: Middleware configuration
        memory_store: Memory store instance (for memory middlewares)
        user_id: User ID for logging and rate limiting
        summarization_model: LLM for summarization (if summarization enabled)

    Returns:
        List of enabled middleware instances

    Example:
        ```python
        from src.config import get_settings
        from src.middleware import create_middleware_from_config

        settings = get_settings()
        middlewares = create_middleware_from_config(
            config=settings.middleware,
            memory_store=memory_store,
            user_id="user-123",
            summarization_model=summarization_llm
        )
        ```
    """
    from pathlib import Path

    middlewares: list[AgentMiddleware] = []

    # =============================================================================
    # Custom Middlewares
    # =============================================================================

    # Memory Context Middleware
    if config.memory_context.enabled:
        if memory_store is None:
            raise ValueError(
                "memory_store is required when memory_context middleware is enabled"
            )

        from src.middleware.memory_context import MemoryContextMiddleware

        middlewares.append(
            MemoryContextMiddleware(
                memory_store=memory_store,
                max_memories=config.memory_context.max_memories,
                min_confidence=config.memory_context.min_confidence,
                include_types=config.memory_context.include_types,
            )
        )

    # Memory Learning Middleware
    if config.memory_learning.enabled:
        if memory_store is None:
            raise ValueError(
                "memory_store is required when memory_learning middleware is enabled"
            )

        from src.middleware.memory_learning import MemoryLearningMiddleware

        extraction_model = None
        if config.memory_learning.extraction_model:
            provider, model = parse_model_string(config.memory_learning.extraction_model)
            extraction_model = get_llm(provider=provider, model=model)

        middlewares.append(
            MemoryLearningMiddleware(
                memory_store=memory_store,
                extraction_model=extraction_model,
                auto_learn=config.memory_learning.auto_learn,
                min_confidence=config.memory_learning.min_confidence,
            )
        )

    # Logging Middleware
    if config.logging.enabled:
        from src.middleware.logging_middleware import LoggingMiddleware

        middlewares.append(
            LoggingMiddleware(
                log_dir=Path(config.logging.log_dir),
                user_id=user_id,
                log_model_calls=config.logging.log_model_calls,
                log_tool_calls=config.logging.log_tool_calls,
                log_memory_access=config.logging.log_memory_access,
                log_errors=config.logging.log_errors,
            )
        )

    # Checkin Middleware
    if config.checkin.enabled:
        from src.middleware.checkin import CheckinMiddleware

        middlewares.append(
            CheckinMiddleware(
                interval_minutes=config.checkin.interval_minutes,
                active_hours_start=config.checkin.active_hours_start,
                active_hours_end=config.checkin.active_hours_end,
                checklist=config.checkin.checklist,
                idle_threshold_hours=config.checkin.idle_threshold_hours,
            )
        )

    # Rate Limit Middleware
    if config.rate_limit.enabled:
        from src.middleware.rate_limit import RateLimitMiddleware

        middlewares.append(
            RateLimitMiddleware(
                max_model_calls_per_minute=config.rate_limit.max_model_calls_per_minute,
                max_tool_calls_per_minute=config.rate_limit.max_tool_calls_per_minute,
                window_seconds=config.rate_limit.window_seconds,
                default_user_id=user_id,
            )
        )

    # =============================================================================
    # Built-in DeepAgents Middlewares
    # =============================================================================

    # SummarizationMiddleware (prioritize for effectiveness testing)
    if config.summarization.enabled:
        try:
            from deepagents.middleware import SummarizationMiddleware
        except ImportError:
            # deepagents might not have this middleware
            pass
        else:
            model = summarization_model
            if not model and config.summarization.summary_model:
                provider, model_name = parse_model_string(config.summarization.summary_model)
                model = get_llm(provider=provider, model=model_name)

            middlewares.append(
                SummarizationMiddleware(
                    model=model,  # positional argument
                    backend=model,  # keyword argument
                    max_tokens=config.summarization.max_tokens,
                    threshold_tokens=config.summarization.threshold_tokens,
                )
            )

    # TodoListMiddleware
    if config.todo_list.enabled:
        try:
            from deepagents.middleware import TodoListMiddleware
        except ImportError:
            pass
        else:
            middlewares.append(
                TodoListMiddleware(max_todos=config.todo_list.max_todos)
            )

    # FilesystemMiddleware
    if config.filesystem.enabled:
        try:
            from deepagents.middleware import FilesystemMiddleware
        except ImportError:
            pass
        else:
            middlewares.append(
                FilesystemMiddleware(max_file_size_mb=config.filesystem.max_file_size_mb)
            )

    # SubagentMiddleware
    if config.subagent.enabled:
        try:
            from deepagents.middleware import SubagentMiddleware
        except ImportError:
            pass
        else:
            middlewares.append(
                SubagentMiddleware(max_delegation_depth=config.subagent.max_delegation_depth)
            )

    # HumanInTheLoopMiddleware
    if config.human_in_the_loop.enabled:
        try:
            from deepagents.middleware import HumanInTheLoopMiddleware
        except ImportError:
            pass
        else:
            middlewares.append(
                HumanInTheLoopMiddleware(
                    confirm_tool_calls=config.human_in_the_loop.confirm_tool_calls,
                    confirm_subagent_calls=config.human_in_the_loop.confirm_subagent_calls,
                )
            )

    # ToolRetryMiddleware
    if config.tool_retry.enabled:
        try:
            from deepagents.middleware import ToolRetryMiddleware
        except ImportError:
            pass
        else:
            middlewares.append(
                ToolRetryMiddleware(
                    max_retries=config.tool_retry.max_retries,
                    retry_on_errors=config.tool_retry.retry_on_errors,
                )
            )

    return middlewares
