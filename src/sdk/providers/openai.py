"""OpenAI + OpenAI-compatible provider.

Covers OpenAI, Ollama Cloud, Together, Groq, DeepSeek, OpenRouter,
Fireworks, LM Studio, llama.cpp, and 80+ OpenAI-compatible APIs.

Uses the `openai` Python SDK for protocol handling (SSE parsing, retries,
error handling). We wrap it with our SDK Message types.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from src.sdk.messages import Message, StreamChunk, ToolCall, Usage
from src.sdk.providers.base import LLMProvider, ModelInfo
from src.sdk.tools import ToolDefinition

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider using the openai SDK.

    Works with any OpenAI-compatible API by changing base_url.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENAI_DEFAULT_BASE_URL,
        model: str = "gpt-4o",
        organization: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self._client = AsyncOpenAI(
            api_key=api_key or "unused",
            base_url=base_url,
            organization=organization,
            timeout=timeout,
        )

    @property
    def provider_id(self) -> str:
        return "openai"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Message:
        model = model or self.model
        openai_msgs = [m.to_openai() for m in messages]
        tool_schemas = [t.to_openai_format() for t in tools] if tools else None

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_msgs,
        }
        if tool_schemas:
            params["tools"] = tool_schemas
        provider_opts = self._extract_provider_options(provider_options)
        params.update(kwargs)
        params.update(provider_opts)

        response = await self._client.chat.completions.create(**params)
        return self._parse_response(response)

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        # deepseek streaming has known issues with reasoning_content round-trip.
        # Use non-streaming chat() and synthesize stream events from response.
        base_url = str(self._client.base_url) if hasattr(self._client, 'base_url') else ""
        if "deepseek" in base_url:
            chat_kwargs = {k: v for k, v in kwargs.items() if k != "stream"}
            response = await self.chat(messages, tools, model, provider_options, **chat_kwargs)

            # Store reasoning for the AgentLoop to pick up if streaming
            # pipeline drops it (known issue with multi-turn tool calls)
            if response.reasoning:
                self._last_reasoning = response.reasoning

            if response.reasoning:
                for msg in reversed(messages):
                    if msg.role == "assistant" and msg.tool_calls:
                        msg.reasoning = msg.reasoning or response.reasoning
                        break

            # Synthesize reasoning events
            if response.reasoning:
                yield StreamChunk.reasoning_start()
                yield StreamChunk.reasoning(content=response.reasoning)
                yield StreamChunk.reasoning_end()

            # Synthesize text events
            if response.content:
                yield StreamChunk.text_start()
                yield StreamChunk.text_delta(content=response.content)
                yield StreamChunk.text_end()

            # Synthesize tool call events
            if response.tool_calls:
                for tc in response.tool_calls:
                    args_str = json.dumps(tc.arguments) if tc.arguments else "{}"
                    yield StreamChunk.tool_input_start(tool=tc.name, call_id=tc.id)
                    yield StreamChunk.tool_input_delta(call_id=tc.id, content=args_str)
                    yield StreamChunk.tool_input_end(tool=tc.name, call_id=tc.id)

            if response.usage:
                yield StreamChunk.usage_event(response.usage)
            yield StreamChunk.done()
            return

        model = model or self.model
        openai_msgs = [m.to_openai() for m in messages]
        tool_schemas = [t.to_openai_format() for t in tools] if tools else None

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_msgs,
            "stream": True,
        }
        if tool_schemas:
            params["tools"] = tool_schemas
        provider_opts = self._extract_provider_options(provider_options)
        params.update(kwargs)
        params.update(provider_opts)

        current_tool_calls: dict[int, dict] = {}

        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            for event in self._parse_stream_chunk(chunk, current_tool_calls):
                yield event

    def _parse_response(self, response: Any) -> Message:
        choice = response.choices[0] if response.choices else None
        if not choice:
            return Message.assistant(content="")

        msg = choice.message
        content = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                import json

                args = {}
                if tc.function.arguments:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        pass
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        reasoning = None
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            if isinstance(msg.reasoning_content, str):
                reasoning = msg.reasoning_content

        usage = None
        if hasattr(response, "usage") and response.usage:
            u = response.usage
            usage = Usage(
                input_tokens=getattr(u, "prompt_tokens", 0) or 0,
                output_tokens=getattr(u, "completion_tokens", 0) or 0,
                reasoning_tokens=getattr(u, "completion_tokens_details", None)
                and getattr(u.completion_tokens_details, "reasoning_tokens", 0)
                or 0,
                cache_read_tokens=getattr(u, "prompt_tokens_details", None)
                and getattr(u.prompt_tokens_details, "cached_tokens", 0)
                or 0,
            )

        return Message.assistant(content=content, tool_calls=tool_calls, usage=usage, reasoning=reasoning)

    def _parse_stream_chunk(
        self, chunk: Any, current_tool_calls: dict[int, dict]
    ) -> list[StreamChunk]:
        events: list[StreamChunk] = []

        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                events.append(
                    StreamChunk.usage_event(
                        Usage(
                            input_tokens=getattr(u, "prompt_tokens", 0) or 0,
                            output_tokens=getattr(u, "completion_tokens", 0) or 0,
                            reasoning_tokens=getattr(u, "completion_tokens_details", None)
                            and getattr(u.completion_tokens_details, "reasoning_tokens", 0)
                            or 0,
                            cache_read_tokens=getattr(u, "prompt_tokens_details", None)
                            and getattr(u.prompt_tokens_details, "cached_tokens", 0)
                            or 0,
                        )
                    )
                )
            return events

        choice = chunk.choices[0]
        delta = choice.delta

        if delta.content:
            events.append(StreamChunk.text_delta(content=delta.content))
            events.append(StreamChunk.ai_token(content=delta.content))

        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            if isinstance(delta.reasoning_content, str):
                events.append(StreamChunk.reasoning(content=delta.reasoning_content))

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in current_tool_calls:
                    current_tool_calls[idx] = {
                        "id": tc_delta.id or "",
                        "name": "",
                        "arguments": "",
                    }
                    events.append(
                        StreamChunk.tool_input_start(
                            tool="",
                            call_id=tc_delta.id or f"call_{uuid4().hex[:8]}",
                        )
                    )
                    events.append(
                        StreamChunk.tool_start(
                            tool="",
                            call_id=tc_delta.id or f"call_{uuid4().hex[:8]}",
                        )
                    )
                entry = current_tool_calls[idx]
                if tc_delta.id:
                    entry["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        entry["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments
                        events.append(
                            StreamChunk.tool_input_delta(
                                call_id=entry["id"] or f"call_{uuid4().hex[:8]}",
                                content=tc_delta.function.arguments,
                            )
                        )

        if choice.finish_reason:
            for idx, tc in current_tool_calls.items():
                events.append(
                    StreamChunk.tool_input_end(
                        call_id=tc["id"] or f"call_{uuid4().hex[:8]}",
                        tool=tc["name"],
                    )
                )
            current_tool_calls.clear()
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                events.append(
                    StreamChunk.usage_event(
                        Usage(
                            input_tokens=getattr(u, "prompt_tokens", 0) or 0,
                            output_tokens=getattr(u, "completion_tokens", 0) or 0,
                            reasoning_tokens=getattr(u, "completion_tokens_details", None)
                            and getattr(u.completion_tokens_details, "reasoning_tokens", 0)
                            or 0,
                            cache_read_tokens=getattr(u, "prompt_tokens_details", None)
                            and getattr(u.prompt_tokens_details, "cached_tokens", 0)
                            or 0,
                        )
                    )
                )
            events.append(StreamChunk.done())

        return events

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return max(1, len(text) // 4)

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(id=model, name=model, provider_id="openai", context_window=128000)
