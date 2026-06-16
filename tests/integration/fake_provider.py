"""Fake LLM provider for deterministic integration tests.

Returns predetermined responses. No LLM call made.
Keeps the entire AgentLoop pipeline real — tool registry, middleware, hooks, streaming.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from src.sdk.messages import Message, StreamChunk, ToolCall, Usage
from src.sdk.providers.base import LLMProvider, ModelCost, ModelInfo
from src.sdk.tools import ToolDefinition


class FakeProvider(LLMProvider):
    """Returns predetermined responses. No LLM call made."""

    def __init__(self, responses: list[dict] | None = None):
        self._responses = list(responses) if responses else []
        self._default = {"content": "OK"}
        self._history: list[Message] = []
        self._token_count = 0

    @property
    def provider_id(self) -> str:
        return "fake"

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(
            id="fake-model",
            provider_id="fake",
            cost=ModelCost(input=0.0, output=0.0),
        )

    async def get_model_info(self, model: str) -> ModelInfo:
        return self.model_info

    def count_tokens(self, text: str, model: str | None = None) -> int:
        self._token_count += max(100, len(text) // 4)
        return max(100, len(text) // 4)

    def _next(self) -> dict:
        if self._responses:
            return self._responses.pop(0)
        return dict(self._default)

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Message:
        resp = self._next()
        self._history.extend(messages)
        if "tool_calls" in resp:
            return Message.assistant(
                content=resp.get("content", ""),
                tool_calls=[
                    ToolCall(**tc) for tc in resp["tool_calls"]
                ],
            )
        return Message.assistant(content=resp.get("content", ""))

    def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream predetermined responses. Not async — yields synchronously."""
        return self._stream(messages, **kwargs)

    async def _stream(self, messages: list[Message], **kwargs: Any):
        resp = self._next()
        self._history.extend(messages)
        if resp.get("reasoning"):
            yield StreamChunk.reasoning_start()
            yield StreamChunk.reasoning_delta(content=resp["reasoning"])
            yield StreamChunk.reasoning_end()
        for tc in resp.get("tool_calls", []):
            cid = tc.get("id", f"call_{id(tc)}")
            yield StreamChunk.tool_input_start(tool=tc["name"], call_id=cid)
            yield StreamChunk.tool_input_delta(
                call_id=cid, content=json.dumps(tc["arguments"])
            )
            yield StreamChunk.tool_input_end(call_id=cid, tool=tc["name"])
        if resp.get("content"):
            yield StreamChunk.text_start()
            yield StreamChunk.text_delta(content=resp["content"])
            yield StreamChunk.text_end()
        usage = resp.get("usage")
        if usage:
            yield StreamChunk.usage_event(Usage(**usage))
        yield StreamChunk.done(content=resp.get("content", ""))
