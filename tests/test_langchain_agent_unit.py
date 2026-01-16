"""Unit tests for LangChain agent runtime."""

import pytest

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from cassey.agent.langchain_agent import create_langchain_agent
from cassey.config import settings


class ToolBindingFakeChatModel(GenericFakeChatModel):
    """Generic fake model that supports tool binding."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def _build_tool_call():
    try:
        from langchain_core.messages import ToolCall

        return ToolCall(name="add", args={"a": 1, "b": 2}, id="call_1")
    except Exception:
        return {"name": "add", "args": {"a": 1, "b": 2}, "id": "call_1"}


@pytest.mark.asyncio
async def test_langchain_agent_executes_tool(monkeypatch):
    """Agent should execute tool calls from the model response."""
    monkeypatch.setattr(settings, "MW_SUMMARIZATION_ENABLED", False)
    monkeypatch.setattr(settings, "MW_TOOL_RETRY_ENABLED", False)
    monkeypatch.setattr(settings, "MW_MODEL_RETRY_ENABLED", False)
    monkeypatch.setattr(settings, "MW_MODEL_CALL_LIMIT", 0)
    monkeypatch.setattr(settings, "MW_TOOL_CALL_LIMIT", 0)

    calls: list[tuple[int, int]] = []

    @tool
    def add(a: int, b: int) -> str:
        """Add two numbers."""
        calls.append((a, b))
        return str(a + b)

    model = ToolBindingFakeChatModel(
        messages=iter(
            [
                AIMessage(content="", tool_calls=[_build_tool_call()]),
                AIMessage(content="3"),
            ]
        )
    )

    agent = create_langchain_agent(
        model=model,
        tools=[add],
        checkpointer=InMemorySaver(),
        system_prompt="You are a test agent.",
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Add 1 and 2")]},
        config={"configurable": {"thread_id": "unit-test"}},
    )

    assert calls == [(1, 2)]
    assert any(
        getattr(message, "content", "") == "3"
        for message in result.get("messages", [])
    )
