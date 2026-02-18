"""Factory for creating middleware instances from configuration.

Centralizes middleware creation logic and ensures consistency.
Supports both custom middlewares and built-in deepagents middlewares.

Usage:
    from src.middleware import create_middleware_from_config

    middlewares = create_middleware_from_config(
        config=settings.middleware,
        memory_store=store,
        user_id=user_id,
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.config.middleware_settings import MiddlewareConfig
from src.config.settings import parse_model_string
from src.llm import get_llm

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentMiddleware

    try:
        from src.memory import MemoryStore
    except ImportError:
        MemoryStore = None


def create_middleware_from_config(
    config: MiddlewareConfig,
    memory_store: MemoryStore | None = None,
    user_id: str = "default",
) -> list[AgentMiddleware]:
    """Create middleware instances from configuration.

    Instantiates all enabled middlewares based on the provided configuration.
    Supports both custom middlewares and built-in deepagents middlewares.

    Args:
        config: Middleware configuration
        memory_store: Memory store instance (for memory middlewares)
        user_id: User ID for logging and rate limiting

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
            # No per-request summarization model init needed; deepagents handles this.
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
            raise ValueError("memory_store is required when memory_context middleware is enabled")

        from src.middleware.memory_context import MemoryContextMiddleware

        logger.info(
            f"[MiddlewareFactory] Creating MemoryContextMiddleware: max_memories={config.memory_context.max_memories}, min_confidence={config.memory_context.min_confidence}"
        )
        middlewares.append(
            MemoryContextMiddleware(
                memory_store=memory_store,
                max_memories=config.memory_context.max_memories,
                min_confidence=config.memory_context.min_confidence,
                include_types=config.memory_context.include_types,
            )
        )
        logger.info(
            f"[MiddlewareFactory] MemoryContextMiddleware added, total middlewares: {len(middlewares)}"
        )

    # Memory Learning Middleware
    if config.memory_learning.enabled:
        if memory_store is None:
            raise ValueError("memory_store is required when memory_learning middleware is enabled")

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

    # Checkpoint cleanup is intentionally disabled from the active stack.
    # The deepagents summarization middleware maintains checkpoint integrity.
    if config.checkpoint_cleanup.enabled:
        logger.info(
            "[MiddlewareFactory] checkpoint_cleanup.enabled=true, "
            "but CheckpointCleanupMiddleware is disabled in runtime."
        )

    # Todo Display Middleware
    # This is a DISPLAY-ONLY middleware that enhances todo list presentation.
    # It does NOT modify todo state - TodoListMiddleware handles that.
    # This middleware runs AFTER the agent to enhance how todos are displayed.
    if config.todo_display.enabled:
        from src.middleware.todo_display import TodoDisplayMiddleware

        logger.info(f"[MiddlewareFactory] Creating TodoDisplayMiddleware")
        middlewares.append(
            TodoDisplayMiddleware(
                enable_progress_tracking=config.todo_display.enable_progress_tracking,
                auto_mark_complete=config.todo_display.auto_mark_complete,
            )
        )
        logger.info(
            f"[MiddlewareFactory] TodoDisplayMiddleware added, total middlewares: {len(middlewares)}"
        )

    # Tool display is intentionally handled by channel-specific streaming renderers
    # (Telegram + HTTP SSE) to avoid duplicate/conflicting output.
    if config.tool_display.enabled:
        logger.info(
            "[MiddlewareFactory] tool_display.enabled=true, "
            "but ToolDisplayMiddleware is disabled in runtime."
        )

    # =============================================================================
    # Built-in DeepAgents Middlewares
    # =============================================================================
    # NOTE: The following middlewares are BUILT-IN to create_deep_agent's standard
    # stack and are always enabled. Configuration parameters for these middlewares
    # are applied via the model's profile attribute (see agent factory).
    #
    # Built-in middlewares (always included):
    # - TodoListMiddleware (not configurable via this factory)
    # - FilesystemMiddleware (not configurable via this factory)
    # - SubAgentMiddleware (not configurable via this factory)
    # - SummarizationMiddleware (configured via model.profile in agent factory)
    # - ToolRetryMiddleware (not configurable via this factory)
    # - AnthropicPromptCachingMiddleware (not configurable via this factory)
    # - PatchToolCallsMiddleware (not configurable via this factory)
    #
    # The 'middleware' parameter only accepts ADDITIONAL middleware beyond the
    # standard stack. Therefore, we DO NOT add built-in middlewares here.

    return middlewares
