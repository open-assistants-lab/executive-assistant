"""Routing logic for the ReAct graph."""

from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import END

from executive_assistant.agent.state import AgentState
from executive_assistant.config import settings


def should_continue(state: AgentState) -> Literal["tools", "continue", "end"]:
    """
    Determine whether to continue with tools or end the conversation.

    Args:
        state: Current agent state.

    Returns:
        "tools" if more tool calls needed, "continue" to check for summarization.
    """
    messages = state["messages"]
    iterations = state.get("iterations", 0)

    # Check iteration limit first
    if iterations >= settings.MAX_ITERATIONS:
        return "continue"

    # Check last message for tool calls
    last_message = messages[-1]

    # Only AIMessage can have tool_calls
    if not isinstance(last_message, AIMessage):
        return "continue"

    # If there are tool calls, continue to tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, we're done - check for summarization
    return "continue"
