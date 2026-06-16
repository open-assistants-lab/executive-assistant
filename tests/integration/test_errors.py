"""Error handling tests via AgentLoop with FakeProvider."""

import pytest

from src.sdk.messages import Message
from src.sdk.providers.base import LLMProvider


class FailingProvider(LLMProvider):
    """A provider that raises on every non-streaming call."""

    @property
    def provider_id(self) -> str:
        return "failing"

    @property
    def model_info(self):
        return {"id": "failing-model"}

    async def get_model_info(self, model: str):
        return {"id": "failing-model", "provider_id": "failing"}

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return len(text) // 4 or 1

    async def chat(self, messages, **kwargs):
        raise RuntimeError("API error")

    def chat_stream(self, messages, **kwargs):
        return self._stream(messages)

    async def _stream(self, messages):
        yield type("err", (), {"type": "error", "content": "API error"})()
        return


@pytest.mark.asyncio
async def test_provider_error(loop, fake_provider):
    """When the provider raises, the agent loop catches it and doesn't crash."""
    loop.provider = FailingProvider()
    loop.run_config.max_llm_calls = 3
    result = await loop.run([Message.user("this will fail")])
    assert result is not None


@pytest.mark.asyncio
async def test_tool_execution_error(loop):
    """Tool execution errors are captured, agent reports failure."""
    loop.provider._responses = [
        {"tool_calls": [{"name": "files_list", "arguments": {"path": "/nonexistent/path"}, "id": "call_err1"}]},
        {"content": "I couldn't list that directory."},
    ]
    result = await loop.run([Message.user("list that path")])
    # Should complete without crashing
    assert len(result) > 0
