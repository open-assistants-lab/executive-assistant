"""LangGraph Studio dev server for Executive Assistant.

Run with: langgraph dev
Or: uv run executive_assistant-dev
"""

from asyncio import run as asyncio_run

from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from executive_assistant.agent.langchain_agent import create_langchain_agent
from executive_assistant.config import create_model
from executive_assistant.config.constants import DEFAULT_SYSTEM_PROMPT
from executive_assistant.tools.registry import get_all_tools


async def get_graph():
    """
    Create the Executive Assistant graph for LangGraph Studio.

    This function is called by langgraph dev to get the graph.
    """
    model = create_model()
    tools = await get_all_tools()

    # Use MemorySaver for dev (persisted in memory only, resets on restart)
    checkpointer = MemorySaver()

    graph = create_langchain_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    )

    return graph


# Optional: standalone dev server entry point
if __name__ == "__main__":
    import asyncio
    from langgraph_cli.cli import dev

    # Run langgraph dev programmatically
    asyncio_run(dev.dev())
