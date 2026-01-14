"""Agent nodes for the ReAct graph."""

import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage
from langchain_core.messages.utils import trim_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from cassey.agent.state import AgentState
from cassey.agent.prompts import get_system_prompt
from cassey.config.constants import MAX_ITERATIONS
from cassey.config import settings


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

    # Check iteration limit
    if state.get("iterations", 0) >= MAX_ITERATIONS:
        # Return a message indicating we've reached max iterations
        return {
            "messages": [
                AIMessage(
                    content=f"I've reached the maximum number of reasoning steps ({MAX_ITERATIONS}). Let me summarize what I've found so far."
                )
            ]
        }

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    # Build system prompt with summary if available
    prompt = system_prompt or get_system_prompt(state.get("channel"))
    summary = state.get("summary", "")
    if summary:
        prompt += f"\n\nPrevious conversation summary:\n{summary}"

    # Trim messages to fit context window (keep recent, preserve continuity)
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

    return {"messages": [response]}


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
            # Execute the tool
            tool = tools_by_name[tool_name]
            result = await tool.ainvoke(tool_args)
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
    Summarize old messages and replace them with a condensed summary.

    Keeps recent messages (last 6 exchanges) and summarizes older ones.
    Also persists the summary to PostgreSQL for audit purposes.
    """
    from cassey.storage.db_storage import get_thread_id

    messages = state["messages"]
    current_summary = state.get("summary", "")

    # Filter to human/AI messages (skip tool messages for summary)
    conversation_messages = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    if len(conversation_messages) < 10:
        # Not enough to summarize yet
        return {}

    # Keep recent messages (last 6 exchanges = 12 messages)
    recent_count = min(12, len(conversation_messages) - 4)
    recent_messages = messages[-recent_count:]

    # Get old messages to summarize
    old_messages = messages[:-recent_count]

    # Build summary prompt
    summary_prompt = [
        SystemMessage(
            content="Summarize the following conversation concisely. "
            "Focus on key topics, decisions, and important information. "
            "Keep it brief and readable."
        ),
    ] + [m for m in old_messages if isinstance(m, (HumanMessage, AIMessage, ToolMessage))]

    try:
        # Use base model (without tools) for summarization
        summary_response = await model.ainvoke(summary_prompt)
        new_summary = summary_response.content

        # Combine with existing summary
        if current_summary:
            combined = f"{current_summary}\n\n[Newer conversation]\n{new_summary}"
        else:
            combined = new_summary

        # Persist summary to PostgreSQL if we have a registry
        thread_id = get_thread_id()
        if thread_id:
            try:
                from cassey.storage.user_registry import UserRegistry
                registry = UserRegistry()
                await registry.update_summary(thread_id, combined)
            except Exception:
                # Fail silently - summary is still in checkpoint state
                pass

        return {
            "messages": recent_messages,
            "summary": combined,
        }
    except Exception:
        # If summarization fails, just continue without changes
        return {}
