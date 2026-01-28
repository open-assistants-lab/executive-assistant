"""LangChain agent runtime builder."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Runnable

from executive_assistant.config import settings
from executive_assistant.agent.langchain_state import ExecutiveAssistantAgentState


def _normalize_agent_tools(tools: list):
    normalized = []
    for tool in tools:
        if isinstance(tool, BaseTool):
            if getattr(tool, "coroutine", None):
                normalized.append(tool.coroutine)
                continue
            if getattr(tool, "func", None):
                normalized.append(tool.func)
                continue
        normalized.append(tool)
    return normalized



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
        from executive_assistant.agent.status_middleware import StatusUpdateMiddleware



        middleware.append(StatusUpdateMiddleware(channel=channel))

    if settings.MW_TODO_LIST_ENABLED:
        middleware.append(
            TodoListMiddleware(
                system_prompt="Use write_todos for complex multi-step tasks.",
                tool_description="Create or update the current todo list.",
            )
        )

        # Add todo display middleware to show todos via status updates
        if settings.MW_STATUS_UPDATE_ENABLED and channel is not None:
            from executive_assistant.agent.todo_display import TodoDisplayMiddleware

            middleware.append(TodoDisplayMiddleware(channel=channel))

    if settings.MW_SUMMARIZATION_ENABLED:
        summary_prompt = """<role>
Context Extraction Assistant
</role>

<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>

<objective_information>
You're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.
This context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to your overall goal.
</objective_information>

<instructions>
The conversation history below will be replaced with the context you extract in this step. Because of this, you must do your very best to extract and record all of the most important context from the conversation history.
You want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.
</instructions>

<include_only>
- User goals, preferences, and constraints
- Decisions and outcomes
- Outstanding tasks or next steps
</include_only>

<exclude>
- Tool call limits, model call limits, or middleware events
- Tool error messages or retries
- Raw tool outputs or logs
- Debug or system/internal details
</exclude>

The user will message you with the full message history you'll be extracting context from, to then replace. Carefully read over it all, and think deeply about what information is most important to your overall goal that should be saved:

With all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.
Respond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.

<messages>
Messages to summarize:
{messages}
</messages>
"""
        middleware.append(
            SummarizationMiddleware(
                model=model,
                trigger=("tokens", settings.MW_SUMMARIZATION_MAX_TOKENS),
                keep=("tokens", settings.MW_SUMMARIZATION_TARGET_TOKENS),
                summary_prompt=summary_prompt,
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
            ModelCallLimitMiddleware(run_limit=settings.MW_MODEL_CALL_LIMIT)
        )

    if settings.MW_TOOL_CALL_LIMIT and settings.MW_TOOL_CALL_LIMIT > 0:
        middleware.append(
            ToolCallLimitMiddleware(run_limit=settings.MW_TOOL_CALL_LIMIT)
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
    tools = _normalize_agent_tools(tools)
    middleware = _build_middleware(model, channel=channel)

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        state_schema=ExecutiveAssistantAgentState,
        checkpointer=checkpointer,
    )
