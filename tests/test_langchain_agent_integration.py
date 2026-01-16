"""Integration tests for LangChain agent runtime using live LLMs."""

import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from cassey.agent.langchain_agent import create_langchain_agent
from cassey.config import settings

pytest.importorskip("agentevals")
from agentevals.trajectory.match import create_trajectory_match_evaluator


def _build_tool_call():
    try:
        from langchain_core.messages import ToolCall

        return ToolCall(name="echo", args={"text": "ping"}, id="call_1")
    except Exception:
        return {"name": "echo", "args": {"text": "ping"}, "id": "call_1"}


def _get_live_model():
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0)
    pytest.skip("No live LLM API key set for integration test.")


def _skip_if_disabled():
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to enable live LLM integration tests.")


@pytest.mark.asyncio
@pytest.mark.vcr()
@pytest.mark.langchain_integration
async def test_langchain_agent_trajectory_superset(monkeypatch):
    """Validate tool usage trajectory with AgentEvals (superset match)."""
    _skip_if_disabled()

    monkeypatch.setattr(settings, "MW_SUMMARIZATION_ENABLED", False)
    monkeypatch.setattr(settings, "MW_TOOL_RETRY_ENABLED", False)
    monkeypatch.setattr(settings, "MW_MODEL_RETRY_ENABLED", False)
    monkeypatch.setattr(settings, "MW_MODEL_CALL_LIMIT", 0)
    monkeypatch.setattr(settings, "MW_TOOL_CALL_LIMIT", 0)

    @tool
    def echo(text: str) -> str:
        """Return the provided text."""
        return text

    model = _get_live_model()
    agent = create_langchain_agent(
        model=model,
        tools=[echo],
        checkpointer=InMemorySaver(),
        system_prompt=(
            "You must call the echo tool exactly once when asked and then reply 'done'."
        ),
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Call the echo tool with text 'ping', then reply done.")]},
        config={"configurable": {"thread_id": "integration-echo"}},
    )

    evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="superset",
        tool_args_match_mode="ignore",
    )

    reference = [
        HumanMessage(content="Call the echo tool with text 'ping', then reply done."),
        AIMessage(content="", tool_calls=[_build_tool_call()]),
    ]

    evaluation = evaluator(
        outputs=result.get("messages", []),
        reference_outputs=reference,
    )

    assert evaluation["score"] is True
