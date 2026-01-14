"""ReAct agent graph built from scratch using LangGraph."""

from functools import partial
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from cassey.agent.state import AgentState
from cassey.agent.nodes import call_model, call_tools, summarize_conversation
from cassey.config import settings
from cassey.config.constants import MAX_ITERATIONS


def route_agent(state: AgentState) -> str:
    """
    Route after agent node: tools, summarize, or end.

    Priority:
    1. If message count is 2x threshold (urgent) -> summarize immediately
    2. If tool calls needed AND not at urgent threshold -> tools
    3. If summarization enabled and threshold exceeded -> summarize
    4. Otherwise -> END
    """
    from langchain_core.messages import AIMessage, HumanMessage

    messages = state["messages"]
    iterations = state.get("iterations", 0)

    # Count human/AI messages for threshold checking
    message_count = len([m for m in messages if isinstance(m, (HumanMessage, AIMessage))])

    # Urgent summarization: if we're at 2x threshold, force summarize even with pending tools
    if settings.ENABLE_SUMMARIZATION and message_count >= settings.SUMMARY_THRESHOLD * 2:
        return "summarize"

    # Check iteration limit and tool calls
    if iterations < MAX_ITERATIONS:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

    # Normal summarization check
    if settings.ENABLE_SUMMARIZATION:
        if message_count >= settings.SUMMARY_THRESHOLD:
            return "summarize"

    return END


def create_react_graph(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
    system_prompt: str | None = None,
) -> StateGraph:
    """
    Create a ReAct agent graph from scratch.

    This builds a LangGraph StateGraph manually rather than using
    the prebuilt create_react_agent function, providing more control
    over the agent's behavior.

    Args:
        model: The chat model to use for reasoning.
        tools: List of tools available to the agent.
        checkpointer: Optional checkpointer for conversation persistence.
        system_prompt: Optional custom system prompt.

    Returns:
        Compiled StateGraph ready for invocation.

    Examples:
        >>> from cassey.config import create_model
        >>> from cassey.storage import get_checkpointer
        >>>
        >>> model = create_model()
        >>> checkpointer = get_checkpointer()
        >>> graph = create_react_graph(model, tools, checkpointer)
        >>>
        >>> config = {"configurable": {"thread_id": "user_123"}}
        >>> result = await graph.ainvoke(
        ...     {"messages": [("user", "Hello!")]},
        ...     config
        ... )
    """
    # Create tools mapping for efficient lookup
    tools_by_name = {tool.name: tool for tool in tools}

    # Create the state graph
    workflow = StateGraph(AgentState)

    # Create node functions with partial application
    call_model_node = partial(
        call_model,
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )
    call_tools_node = partial(call_tools, tools_by_name=tools_by_name)
    summarize_node = partial(summarize_conversation, model=model)

    # Add nodes to the graph
    workflow.add_node("agent", call_model_node)
    workflow.add_node("tools", call_tools_node)
    workflow.add_node("summarize", summarize_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edge from agent node
    # After agent calls model, decide: tools, summarize, or end?
    workflow.add_conditional_edges(
        "agent",
        route_agent,
        {
            "tools": "tools",
            "summarize": "summarize",
            END: END,
        },
    )

    # Add edge from tools back to agent
    # After executing tools, go back to agent to process results
    workflow.add_edge("tools", "agent")

    # After summarizing, go to END
    workflow.add_edge("summarize", END)

    return workflow


def create_graph(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
    system_prompt: str | None = None,
) -> Any:
    """
    Create and compile a ReAct agent graph.

    This is a convenience function that creates the graph and
    compiles it with the optional checkpointer.

    Args:
        model: The chat model to use for reasoning.
        tools: List of tools available to the agent.
        checkpointer: Optional checkpointer for conversation persistence.
        system_prompt: Optional custom system prompt.

    Returns:
        Compiled graph ready for invocation.
    """
    workflow = create_react_graph(model, tools, checkpointer, system_prompt)
    return workflow.compile(checkpointer=checkpointer)
