"""Agent nodes for the ReAct graph."""

import asyncio
import contextvars
import json
import time
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage
from loguru import logger
from langchain_core.messages.utils import trim_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from executive_assistant.agent.state import AgentState
from executive_assistant.agent.prompts import get_system_prompt
from executive_assistant.agent.status_middleware import record_llm_call
from executive_assistant.config.settings import settings


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

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    # Build system prompt with summary
    prompt = system_prompt or get_system_prompt(state.get("channel"))

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

    # Invoke model with timing
    logger.debug("🤖 LLM_CALL: Starting model invocation...")
    llm_start = time.time()
    response = await model_with_tools.ainvoke(messages_to_send, config)
    llm_elapsed = time.time() - llm_start

    # Log token usage if available
    token_info = ""
    token_dict = None
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        if usage:
            input_tokens = usage.get('input_tokens', '?')
            output_tokens = usage.get('output_tokens', '?')
            total_tokens = usage.get('total_tokens', '?')
            token_info = f" | tokens: in={input_tokens} out={output_tokens} total={total_tokens}"
            token_dict = {"in": input_tokens, "out": output_tokens, "total": total_tokens}

    logger.debug(f"🤖 LLM_RESPONSE: {llm_elapsed:.2f}s{token_info}")

    # Record LLM timing for status middleware (shows in verbose mode)
    record_llm_call(llm_elapsed, token_dict)

    # Also log slow calls at INFO level (visible without DEBUG mode)
    if llm_elapsed > 5:
        logger.warning(f"⚠️ SLOW_LLM: {llm_elapsed:.2f}s (threshold: 5s){token_info}")
    elif llm_elapsed > 2:
        logger.info(f"🤖 LLM_CALL: {llm_elapsed:.2f}s{token_info}")

    result = {"messages": [response]}
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
    state_updates: dict[str, Any] = {}

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

    return {"messages": outputs, **state_updates}


