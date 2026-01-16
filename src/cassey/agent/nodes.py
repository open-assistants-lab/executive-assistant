"""Agent nodes for the ReAct graph."""

import asyncio
import contextvars
import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage
from langchain_core.messages.utils import trim_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from cassey.agent.state import AgentState
from cassey.agent.prompts import get_system_prompt
from cassey.config.settings import settings


async def call_model(
    state: AgentState,
    config: RunnableConfig,
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Call the LLM node - generates responses and tool calls.

    Args:
        state: Current agent state.
        config: RunnableConfig for the model invocation.
        model: The chat model to use.
        tools: List of tools available to the agent.
        system_prompt: Optional custom system prompt.

    Returns:
        Dict with messages key containing the model response.
    """
    messages = state["messages"]
    iterations = state.get("iterations", 0)
    reset_iterations = False

    # Check for user saying "continue" after hitting limit - reset counter
    if iterations >= settings.MAX_ITERATIONS:
        # Check if the last user message is asking to continue
        last_human = None
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                last_human = m.content.lower()
                break

        # If user explicitly says "continue", "go on", "proceed", "keep going", reset counter
        continue_phrases = ["continue", "go on", "proceed", "keep going", "carry on", "resume"]
        if last_human and any(phrase in last_human for phrase in continue_phrases):
            # Reset iterations and continue processing
            iterations = 0
            reset_iterations = True

    # Check iteration limit
    if iterations >= settings.MAX_ITERATIONS:
        # Provide helpful context about what was accomplished
        tool_calls = [m for m in messages if hasattr(m, 'tool_calls') and m.tool_calls]
        tool_names = [tc.name for m in tool_calls for tc in getattr(m, 'tool_calls', [])]

        # Count tool calls by type
        from collections import Counter
        tool_summary = Counter(tool_names)

        summary_parts = [f"I've reached the maximum number of reasoning steps ({settings.MAX_ITERATIONS})."]

        if tool_summary:
            summary_parts.append("\n\nWhat I attempted:")
            for tool, count in tool_summary.most_common():
                summary_parts.append(f"- {tool}: {count} call(s)")

        summary_parts.append("\n\nSay 'continue' to resume, or ask me to try a different approach.")
        summary_parts.append("\n\n💡 Tip: For complex tasks, break them into smaller steps.")

        return {
            "messages": [
                AIMessage(content="".join(summary_parts))
            ]
        }

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    # Build system prompt with summary
    prompt = system_prompt or get_system_prompt(state.get("channel"))

    # Get structured summary and intent for KB-first routing
    structured_summary = state.get("structured_summary")
    intent = "hybrid"  # Default

    if structured_summary:
        # Extract intent from active topic if available
        active_topics = [
            t for t in structured_summary.get("topics", [])
            if t.get("status") == "active"
        ]
        if active_topics:
            intent = active_topics[0].get("intent", "hybrid")

        # For factual queries, use minimal summary context (KB-first mode)
        if intent == "factual":
            # Only show current request, skip the rest of the summary
            # This prevents context contamination for factual lookups
            active_request = structured_summary.get("active_request", {})
            if isinstance(active_request, dict) and active_request.get("text"):
                prompt += f"\n\n[Current Request]\n{active_request['text']}"
                prompt += "\n\nNote: For this factual query, prioritize KB results over conversation context."
        else:
            # For conversational/hybrid, show full summary
            from cassey.agent.topic_classifier import StructuredSummaryBuilder
            rendered = StructuredSummaryBuilder.render_for_prompt(structured_summary)
            if rendered:
                prompt += f"\n\n{rendered}"

    # Trim messages to fit context window (keep recent, preserve continuity)
    # IMPORTANT: Don't trim if there are pending tool calls to avoid checkpoint corruption
    last_message = messages[-1] if messages else None
    has_pending_tool_calls = (
        isinstance(last_message, AIMessage) and
        hasattr(last_message, "tool_calls") and
        last_message.tool_calls
    )

    if has_pending_tool_calls:
        # Don't trim - we have pending tool calls that need ToolMessage responses
        # Trimming here could cut off the responses and cause checkpoint corruption
        trimmed = messages
    else:
        try:
            trimmed = trim_messages(
                messages,
                strategy="last",
                max_tokens=settings.MAX_CONTEXT_TOKENS,
                start_on="human",
                end_on=("human", "tool", "ai"),
            )
        except Exception:
            # Fallback to original messages if trimming fails
            trimmed = messages

    # Build message list with system prompt
    messages_to_send = [SystemMessage(content=prompt)] + list(trimmed)

    # Invoke model
    response = await model_with_tools.ainvoke(messages_to_send, config)

    result = {"messages": [response]}
    if reset_iterations:
        result["iterations"] = 0
    return result


async def call_tools(
    state: AgentState,
    tools_by_name: dict[str, BaseTool],
) -> dict[str, Any]:
    """
    Execute tool calls requested by the model.

    Args:
        state: Current agent state.
        tools_by_name: Mapping of tool names to tool instances.

    Returns:
        Dict with messages key containing ToolMessage results.
    """
    outputs = []
    last_message = state["messages"][-1]

    # Only process if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if tool_name not in tools_by_name:
            outputs.append(
                ToolMessage(
                    content=f"Error: Tool '{tool_name}' not found",
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        try:
            # Execute the tool with proper context propagation
            tool = tools_by_name[tool_name]

            # Check if tool is async or sync
            # LangChain tools with async def have _arun method
            is_async = hasattr(tool, '_arun') and asyncio.iscoroutinefunction(tool._arun)

            if is_async:
                # Async tool - use ainvoke (ContextVars propagate automatically)
                result = await tool.ainvoke(tool_args)
            else:
                # Sync tool - run in executor with copied context
                ctx = contextvars.copy_context()
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, ctx.run, tool.invoke, tool_args)

            outputs.append(
                ToolMessage(
                    content=json.dumps(result) if not isinstance(result, str) else result,
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )
            )
        except Exception as e:
            outputs.append(
                ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )
            )

    return {"messages": outputs}


def increment_iterations(state: AgentState) -> dict[str, Any]:
    """Increment the iteration counter."""
    return {"iterations": state.get("iterations", 0) + 1}


async def should_summarize(state: AgentState) -> str:
    """
    Decide whether to summarize the conversation.

    Returns:
        "summarize" if threshold exceeded, "continue" otherwise.
    """
    if not settings.ENABLE_SUMMARIZATION:
        return "continue"

    message_count = len([m for m in state["messages"] if isinstance(m, (HumanMessage, AIMessage))])
    if message_count >= settings.SUMMARY_THRESHOLD:
        return "summarize"
    return "continue"


async def summarize_conversation(
    state: AgentState,
    model: BaseChatModel,
) -> dict[str, Any]:
    """
    Summarize old messages using the structured summary schema.

    Key improvements:
    - Topic-based: Separate summaries by topic, not just chronologically
    - Intent-first: active_request always shows current user intent
    - Active/inactive topics: Old topics fade when new ones dominate
    - Source binding: Each summary item tied to message IDs

    Keeps recent messages (last 6 exchanges) and summarizes older ones.
    Also persists the summary to PostgreSQL for audit purposes.
    """
    from cassey.storage.db_storage import get_thread_id
    from cassey.agent.summary_extractor import update_structured_summary

    messages = state["messages"]
    current_summary = state.get("structured_summary")

    # Filter to human/AI messages (skip tool messages for summary)
    conversation_messages = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    if len(conversation_messages) < 10:
        # Not enough to summarize yet
        return {}

    # Get thread_id for persistence
    thread_id = get_thread_id()

    # Update structured summary with new messages
    new_structured_summary = await update_structured_summary(
        current_summary if isinstance(current_summary, dict) else None,
        messages,
        model,
        thread_id or "unknown",
    )

    # Keep recent messages (last 6 exchanges = 12 messages)
    recent_count = min(12, len(conversation_messages) - 4)
    recent_messages = messages[-recent_count:]

    # Persist structured summary to PostgreSQL
    if thread_id:
        try:
            from cassey.storage.user_registry import UserRegistry

            registry = UserRegistry()
            # Update the structured_summary column (JSONB)
            await registry.update_structured_summary(thread_id, new_structured_summary)

            # Also update active_request column (for quick access)
            active_request_text = new_structured_summary.get("active_request", {}).get("text", "")
            if active_request_text:
                await registry.update_active_request(thread_id, active_request_text)

        except Exception as e:
            # If persistence fails, continue with in-memory summary
            import traceback
            traceback.print_exc()

    return {
        "messages": recent_messages,
        "structured_summary": new_structured_summary,
    }
