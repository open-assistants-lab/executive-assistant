"""LangChain agent runtime builder."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Runnable

from executive_assistant.config import settings
from executive_assistant.agent.langchain_state import ExecutiveAssistantAgentState

logger = logging.getLogger(__name__)


def _normalize_agent_tools(tools: list):
    normalized = []
    for tool in tools:
        # Don't unwrap MCP tools (StructuredTool) - keep them as-is
        if isinstance(tool, BaseTool):
            # Check if this is an MCP tool (has name, description, args_schema)
            if hasattr(tool, "name") and hasattr(tool, "description") and hasattr(tool, "args_schema"):
                # This is likely an MCP tool - keep it as-is
                normalized.append(tool)
                continue
            # For other BaseTool types, unwrap to the underlying function
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

    # Thread context middleware (ensure ContextVars propagate to tools)
    from executive_assistant.agent.thread_context_middleware import ThreadContextMiddleware
    middleware.append(ThreadContextMiddleware())

    if settings.MW_TODO_LIST_ENABLED:
        middleware.append(
            TodoListMiddleware(
                system_prompt="""## `write_todos` - Task Tracking for Multi-Step Workflows

Use the `write_todos` tool to show your plan for multi-step tasks.

**DO NOT use write_todos for:**
- Simple 1-2 step tasks
- Single-step queries (e.g., "What is 2+2?", "List memories")
- Direct commands starting with `/` or `!` (e.g., `/mem list`, `!ls`)
- Direct tool invocations (user explicitly names a tool)
- Quick informational requests
- Status checks

**Use write_todos for:**
- Tasks with 3 or more steps
- Multi-step tasks involving multiple tool calls
- Complex workflows requiring problem breakdown
- Tasks where showing progress builds user confidence
- Work that spans multiple execution cycles

**Process:**
1. For tasks with 3+ steps: FIRST call write_todos with your plan
2. For commands/simple queries: Execute directly WITHOUT todos
3. Mark steps complete as you work through them
4. Keep todos updated as you learn more

Remember: Use write_todos ONLY for 3+ step tasks - don't create noise for simple commands!

CRITICAL: USER TODOS vs AGENT TODOS - Don't confuse them!

**When user wants to track THEIR personal tasks (USER todos):**
Use TDB tools for persistent storage:
- create_tdb_table("todos", columns="task,status,priority")
- insert_tdb_table("todos", [{"task": "...", "status": "pending"}])
- query_tdb("SELECT * FROM todos WHERE status = 'pending'")
- update_tdb_table("todos", '{"status": "completed"}', where="id = 1")

User phrases that mean USER todos (use TDB):
- "track my todos" / "track todo for me"
- "add to my todo list" / "add to my todos"
- "add [task] to my todo" / "put [task] on my todo"
- "add [task] onto my todo" / "add [task] to my todos"
- "remember this todo" / "remember this task"
- "add [task]" (when context is todo list, NOT scheduling)

**When agent needs to track ITS execution steps (AGENT todos):**
Use write_todos for complex multi-step workflows to show progress.

Signs it's an AGENT todo:
- Multi-step tool execution plan
- Breaking down complex tasks
- Showing progress during a single run

NEVER use write_todos for storing user's personal tasks - those belong in TDB.""",
                tool_description="Create or update the agent's internal execution task list (NOT for user todos - use TDB for user's persistent todos).",
            )
        )

        # Register write_todos for XML parser compatibility
        # The XML parser needs middleware tools registered in the tool registry
        from langchain_core.tools import tool
        from executive_assistant.tools.registry import register_middleware_tool

        @tool
        def write_todos(todos: list[dict]) -> str:
            """Create and manage a structured task list for your current work session.

            This tool helps you track your progress and shows the user what you're working on.
            Use this for EVERY task - simple or complex.

            Args:
                todos: List of todo items with content and status fields.
                       Each todo should have: {"content": "task description", "status": "pending|in_progress|completed"}

            Returns:
                Formatted todo list that will be shown to the user.
            """
            if not todos:
                return ""

            completed = sum(1 for t in todos if t.get("status") == "completed")
            total = len(todos)

            lines = [f"📋 Agent Task List ({completed}/{total} complete):"]

            for todo in todos[:10]:
                status = todo.get("status", "pending")
                content = todo.get("content", "")

                if status == "completed":
                    lines.append(f"  ✅ {content}")
                elif status == "in_progress":
                    lines.append(f"  ⏳ {content}")
                else:
                    lines.append(f"  ⏳ {content}")

            if len(todos) > 10:
                remaining = len(todos) - 10
                lines.append(f"  ... and {remaining} more")

            return "\n".join(lines)

        register_middleware_tool(write_todos)
        if settings.MW_STATUS_UPDATE_ENABLED and channel is not None:
            from executive_assistant.agent.todo_display import TodoDisplayMiddleware
            middleware.append(TodoDisplayMiddleware(channel=channel))

    if settings.MW_SUMMARIZATION_ENABLED:
        # NOTE: Summarization trigger behavior (5:1 ratio = 10,000 → 2,000)
        # The middleware checks TWO triggers (see summarization.py:372-377):
        # 1. Counted tokens >= trigger threshold (uses token_counter)
        # 2. Reported tokens from last AIMessage.usage_metadata (includes system prompt + tools)
        #
        # Trigger #2 fires EARLY due to overhead (~5,700 tokens with 72 tools):
        # - System prompt: ~1,200 tokens
        # - 72 tool definitions: ~4,500-5,000 tokens
        # - Total overhead: ~5,700 tokens
        #
        # Effective thresholds with current settings:
        # - Trigger: 10,000 - 5,700 = ~4,300 message tokens (when usage_metadata check fires)
        # - Target: 2,000 tokens preserves ~15-20 recent messages + summary
        # - Ratio: 5:1 provides balanced context retention without excessive growth
        #
        # Improved prompt: Concise with 300-word limit to prevent verbose summaries
        summary_prompt = """Summarize the conversation below into 200-300 words maximum.

Focus on:
1. User's goal/intent
2. Key decisions made
3. Outstanding tasks or next steps
4. Important constraints or preferences

Exclude:
- Tool call details, errors, or retries
- Raw tool outputs or logs
- Debug or system/internal details
- Middleware events

CRITICAL: Keep summary under 300 words. Be concise.

<messages>
{messages}
</messages>

Respond ONLY with the summary. No additional text."""
        middleware.append(
            SummarizationMiddleware(
                model=model,
                trigger=("tokens", settings.MW_SUMMARIZATION_MAX_TOKENS),
                keep=("tokens", settings.MW_SUMMARIZATION_TARGET_TOKENS),
                summary_prompt=summary_prompt,
                # Set trim_tokens higher than trigger to avoid "too long to summarize" error
                # With trigger=10,000, we need headroom for the summarization LLM call itself
                trim_tokens_to_summarize=settings.MW_SUMMARIZATION_MAX_TOKENS + 2000,
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
        middleware.append(ModelCallLimitMiddleware(run_limit=settings.MW_MODEL_CALL_LIMIT))

    if settings.MW_TOOL_CALL_LIMIT and settings.MW_TOOL_CALL_LIMIT > 0:
        middleware.append(ToolCallLimitMiddleware(run_limit=settings.MW_TOOL_CALL_LIMIT))

    if settings.MW_TOOL_RETRY_ENABLED:
        middleware.append(ToolRetryMiddleware())

    if settings.MW_MODEL_RETRY_ENABLED:
        middleware.append(ModelRetryMiddleware())

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
