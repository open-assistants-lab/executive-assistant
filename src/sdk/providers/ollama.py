"""Ollama providers — OllamaLocal and OllamaCloud.

OllamaLocal:  POST http://localhost:11434/v1/chat/completions (OpenAI-compatible)
OllamaCloud:  POST https://ollama.com/api/chat (native Ollama format, Bearer auth)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx

from src.sdk.messages import Message, StreamChunk, ToolCall, Usage
from src.sdk.providers.base import LLMProvider, ModelInfo
from src.sdk.tools import ToolDefinition


class OllamaLocal(LLMProvider):
    """Provider for local Ollama instance (OpenAI-compatible /v1 endpoint).

    Default: http://localhost:11434/v1
    No API key needed.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "minimax-m2.5",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = None
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None

    @property
    def provider_id(self) -> str:
        return "ollama"

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._http_client

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        model: str,
        stream: bool = False,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.to_openai() for m in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]
        provider_opts = self._extract_provider_options(provider_options)
        payload.update(kwargs)
        payload.update(provider_opts)
        return payload

    def _parse_response(self, data: dict) -> Message:
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        tool_calls_data = msg.get("tool_calls", [])
        parsed_tcs = [ToolCall.from_openai(tc) for tc in tool_calls_data]

        usage = None
        raw_usage = data.get("usage")
        if raw_usage:
            usage = Usage(
                input_tokens=raw_usage.get("prompt_tokens", 0),
                output_tokens=raw_usage.get("completion_tokens", 0),
            )

        return Message.assistant(content=content, tool_calls=parsed_tcs, usage=usage)

    def _parse_stream_chunk(
        self, data: dict, current_tool_calls: dict[int, dict]
    ) -> list[StreamChunk]:
        chunks: list[StreamChunk] = []
        choice = data.get("choices", [{}])[0]
        delta = choice.get("delta", {})

        if "tool_calls" in delta:
            for tc_delta in delta["tool_calls"]:
                idx = tc_delta.get("index", 0)
                if idx not in current_tool_calls:
                    current_tool_calls[idx] = {
                        "id": tc_delta.get("id", ""),
                        "name": tc_delta.get("function", {}).get("name", ""),
                        "arguments": "",
                    }
                    chunks.append(
                        StreamChunk.tool_input_start(
                            tool=tc_delta.get("function", {}).get("name", ""),
                            call_id=tc_delta.get("id", f"call_{uuid4().hex[:8]}"),
                        )
                    )
                    chunks.append(
                        StreamChunk.tool_start(
                            tool=tc_delta.get("function", {}).get("name", ""),
                            call_id=tc_delta.get("id", f"call_{uuid4().hex[:8]}"),
                        )
                    )
                entry = current_tool_calls[idx]
                if tc_delta.get("id"):
                    entry["id"] = tc_delta["id"]
                func_delta = tc_delta.get("function", {})
                if func_delta.get("name"):
                    entry["name"] = func_delta["name"]
                if func_delta.get("arguments"):
                    entry["arguments"] += func_delta["arguments"]
                    chunks.append(
                        StreamChunk.tool_input_delta(
                            call_id=entry["id"] or f"call_{uuid4().hex[:8]}",
                            content=func_delta["arguments"],
                        )
                    )

        content_delta = delta.get("content")
        if content_delta:
            chunks.append(StreamChunk.text_delta(content=content_delta))
            chunks.append(StreamChunk.ai_token(content=content_delta))

        finish_reason = choice.get("finish_reason")
        if finish_reason:
            for idx, tc in current_tool_calls.items():
                chunks.append(
                    StreamChunk.tool_input_end(
                        call_id=tc["id"] or f"call_{uuid4().hex[:8]}",
                        tool=tc["name"],
                    )
                )
            chunks.append(StreamChunk.done())
            current_tool_calls.clear()

        raw_usage = data.get("usage")
        if raw_usage:
            chunks.append(
                StreamChunk.usage_event(
                    Usage(
                        input_tokens=raw_usage.get("prompt_tokens", 0),
                        output_tokens=raw_usage.get("completion_tokens", 0),
                    )
                )
            )

        return chunks

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Message:
        model = model or self.model
        payload = self._build_payload(
            messages, tools, model, stream=False, provider_options=provider_options, **kwargs
        )
        client = self._get_client()
        response = await client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        return self._parse_response(response.json())

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        model = model or self.model
        payload = self._build_payload(
            messages, tools, model, stream=True, provider_options=provider_options, **kwargs
        )
        client = self._get_client()
        current_tool_calls: dict[int, dict] = {}
        async with client.stream(
            "POST", f"{self.base_url}/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                for chunk in self._parse_stream_chunk(data, current_tool_calls):
                    yield chunk

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return max(1, len(text) // 4)

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(id=model, name=model, provider_id="ollama", context_window=128000)


class OllamaCloud(LLMProvider):
    """Provider for Ollama Cloud (ollama.com/api/chat).

    Uses the native Ollama /api/chat API with Bearer authentication.
    Requires OLLAMA_API_KEY.

    Message format uses Ollama native format (to_ollama):
        - tool results: {role: "tool", tool_name: "...", content: "..."}
        - assistant tool_calls: {type: "function", function: {name, arguments}}
    """

    def __init__(
        self,
        base_url: str = "https://ollama.com",
        model: str = "minimax-m2.5",
        api_key: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None

    @property
    def provider_id(self) -> str:
        return "ollama-cloud"

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
            )
        return self._http_client

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        model: str,
        stream: bool = False,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.to_ollama() for m in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]
        provider_opts = self._extract_provider_options(provider_options)
        payload.update(kwargs)
        payload.update(provider_opts)
        return payload

    def _parse_response(self, data: dict) -> Message:
        msg = data.get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("thinking", None)
        tool_calls = msg.get("tool_calls", [])
        parsed_tcs = []
        for tc in tool_calls:
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            parsed_tcs.append(
                ToolCall(
                    id=tc.get("id", f"call_{uuid4().hex[:8]}"),
                    name=func.get("name", ""),
                    arguments=args,
                )
            )

        usage = None
        raw_usage = data.get("usage") or data.get("eval_count")
        if isinstance(raw_usage, dict):
            usage = Usage(
                input_tokens=raw_usage.get("prompt_tokens", 0),
                output_tokens=raw_usage.get("completion_tokens", 0),
            )
        elif isinstance(raw_usage, int) and "prompt_eval_count" in data:
            usage = Usage(
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=raw_usage,
            )

        result = Message.assistant(content=content, tool_calls=parsed_tcs, usage=usage)
        if reasoning:
            result.reasoning = reasoning
        return result

    def _parse_chunk(
        self,
        data: dict,
        current_tool_calls: dict[int, dict],
        provider_options: dict[str, dict[str, Any]] | None = None,
        emitted_starts: set[tuple[str, str]] | None = None,
    ) -> list[StreamChunk]:
        """Parse a streaming chunk from Ollama Cloud native /api/chat.

        Emits block-structured events (tool_input_start/delta/end, text_delta,
        reasoning_delta) plus backward-compatible aliases (tool_start, ai_token, reasoning).
        The AgentLoop emits tool_result/tool_end after executing tools.
        """
        chunks: list[StreamChunk] = []
        msg = data.get("message", {})
        content = msg.get("content", "")
        thinking = msg.get("thinking", "")

        tool_calls = msg.get("tool_calls", [])
        for i, tc in enumerate(tool_calls):
            func = tc.get("function", {})
            tc_id = tc.get("id", f"call_{uuid4().hex[:8]}")
            name = func.get("name", "")
            args_str = func.get("arguments", {})

            if i not in current_tool_calls:
                current_tool_calls[i] = {
                    "id": tc_id,
                    "name": name,
                    "arguments": "",
                }
                # Dedup: skip tool_input_start for duplicate (name, args) pairs
                # that the MiniMax reasoning model emits multiple times.
                start_key = (name or "", str(args_str)[:200])
                if name and (emitted_starts is None or start_key not in emitted_starts):
                    if emitted_starts is not None:
                        emitted_starts.add(start_key)
                    chunks.append(
                        StreamChunk.tool_input_start(
                            tool=name,
                            call_id=tc_id,
                        )
                    )
                    chunks.append(
                        StreamChunk.tool_start(
                            tool=name,
                            call_id=tc_id,
                        )
                    )

            entry = current_tool_calls[i]
            if name:
                entry["name"] = name
            if tc_id:
                entry["id"] = tc_id
            if isinstance(args_str, str) and args_str:
                entry["arguments"] += args_str
                chunks.append(
                    StreamChunk.tool_input_delta(
                        call_id=tc_id,
                        content=args_str,
                    )
                )
            elif isinstance(args_str, dict) and args_str:
                arg_json = json.dumps(args_str)
                entry["arguments"] += arg_json
                chunks.append(
                    StreamChunk.tool_input_delta(
                        call_id=tc_id,
                        content=arg_json,
                    )
                )

        if data.get("done", False):
            for entry in current_tool_calls.values():
                chunks.append(
                    StreamChunk.tool_input_end(
                        call_id=entry["id"],
                        tool=entry["name"],
                    )
                )
            current_tool_calls.clear()

            raw_usage = data.get("usage") or {}
            if raw_usage:
                chunks.append(
                    StreamChunk.usage_event(
                        Usage(
                            input_tokens=raw_usage.get(
                                "prompt_tokens", data.get("prompt_eval_count", 0)
                            ),
                            output_tokens=raw_usage.get(
                                "completion_tokens", data.get("eval_count", 0)
                            ),
                        )
                    )
                )
            elif "prompt_eval_count" in data or "eval_count" in data:
                chunks.append(
                    StreamChunk.usage_event(
                        Usage(
                            input_tokens=data.get("prompt_eval_count", 0),
                            output_tokens=data.get("eval_count", 0),
                        )
                    )
                )

            chunks.append(StreamChunk.done(content=content))
        else:
            if thinking:
                chunks.append(StreamChunk.reasoning_delta(content=thinking))
                chunks.append(StreamChunk.reasoning(content=thinking))
            if content:
                chunks.append(StreamChunk.text_delta(content=content))
                chunks.append(StreamChunk.ai_token(content=content))

        return chunks

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Message:
        model = model or self.model
        payload = self._build_payload(
            messages, tools, model, stream=False, provider_options=provider_options, **kwargs
        )
        client = self._get_client()
        response = await client.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        return self._parse_response(response.json())

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        model = model or self.model
        payload = self._build_payload(
            messages, tools, model, stream=True, provider_options=provider_options, **kwargs
        )
        client = self._get_client()
        current_tool_calls: dict[int, dict] = {}
        emitted_starts: set[tuple[str, str]] = set()
        async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for chunk in self._parse_chunk(data, current_tool_calls, provider_options, emitted_starts):
                    yield chunk

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return max(1, len(text) // 4)

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(id=model, name=model, provider_id="ollama-cloud", context_window=128000)
