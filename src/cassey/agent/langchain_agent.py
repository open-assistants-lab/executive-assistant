"""LangChain agent runtime builder."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Runnable

from cassey.config import settings
from cassey.agent.langchain_state import CasseyAgentState


def _load_create_agent() -> Any:
    """Load LangChain create_agent with a clear error if unavailable."""
    try:
        from langchain.agents import create_agent as _create_agent
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "LangChain create_agent is required. "
            "Ensure langchain>=1.0 is installed."
        ) from exc
    return _create_agent


def _build_middleware(model: BaseChatModel, channel: Any = None) -> list[Any]:
    """Build LangChain middleware list from settings.

    Args:
        model: The chat model (needed for some middleware like SummarizationMiddleware).
        channel: Optional channel instance for status update middleware.
    """
    try:
        from langchain.agents.middleware import (
            SummarizationMiddleware,
            ModelCallLimitMiddleware,
            ToolCallLimitMiddleware,
            ToolRetryMiddleware,
            ModelRetryMiddleware,
            TodoListMiddleware,
            ContextEditingMiddleware,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "LangChain middleware could not be imported. "
            "Ensure langchain>=1.0 is installed."
        ) from exc

    middleware: list[Any] = []

    # Status update middleware (first to capture all events)
    if settings.MW_STATUS_UPDATE_ENABLED and channel is not None:
        from cassey.agent.status_middleware import StatusUpdateMiddleware

        middleware.append(StatusUpdateMiddleware(channel=channel))

    if settings.MW_TODO_LIST_ENABLED:
        middleware.append(TodoListMiddleware())

    if settings.MW_SUMMARIZATION_ENABLED:
        middleware.append(
            SummarizationMiddleware(
                model=model,
                trigger=("tokens", settings.MW_SUMMARIZATION_MAX_TOKENS),
                keep=("tokens", settings.MW_SUMMARIZATION_TARGET_TOKENS),
            )
        )

    if settings.MW_CONTEXT_EDITING_ENABLED:
        from langchain.agents.middleware import ClearToolUsesEdit

        middleware.append(
            ContextEditingMiddleware(
                edits=[
                    ClearToolUsesEdit(
                        trigger=("tokens", settings.MW_CONTEXT_EDITING_TRIGGER_TOKENS),
                        keep=("tool_uses", settings.MW_CONTEXT_EDITING_KEEP_TOOL_USES),
                    )
                ]
            )
        )

    if settings.MW_MODEL_CALL_LIMIT and settings.MW_MODEL_CALL_LIMIT > 0:
        middleware.append(
            ModelCallLimitMiddleware(thread_limit=settings.MW_MODEL_CALL_LIMIT)
        )

    if settings.MW_TOOL_CALL_LIMIT and settings.MW_TOOL_CALL_LIMIT > 0:
        middleware.append(
            ToolCallLimitMiddleware(thread_limit=settings.MW_TOOL_CALL_LIMIT)
        )

    if settings.MW_TOOL_RETRY_ENABLED:
        middleware.append(ToolRetryMiddleware())

    if settings.MW_MODEL_RETRY_ENABLED:
        middleware.append(ModelRetryMiddleware())

    if settings.MW_HITL_ENABLED:
        raise ValueError(
            "MW_HITL_ENABLED is set but no HITL policy/configuration is defined."
        )

    return middleware


def create_langchain_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
    system_prompt: str | None = None,
    channel: Any = None,
) -> Runnable:
    """
    Create a LangChain-native agent runtime with middleware.

    Args:
        model: The chat model to use.
        tools: Tool list to expose to the agent.
        checkpointer: Optional checkpointer for persistence.
        system_prompt: Optional static system prompt.
        channel: Optional channel instance for status update middleware.

    Returns:
        Compiled LangGraph agent runnable.
    """
    create_agent = _load_create_agent()
    middleware = _build_middleware(model, channel=channel)

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        state_schema=CasseyAgentState,
        checkpointer=checkpointer,
    )
