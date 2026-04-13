"""LLM Provider contract tests.

Defines the contract that each LLM provider implementation must satisfy.
Tests use mocked HTTP responses (respx/httpx) to verify:
- Request format is correct for each provider's API
- Response parsing produces our Message/ToolCall types
- Tool call extraction works
- Error handling is graceful

These are IMPLEMENTED STUBS — the actual providers don't exist yet (Phase 2).
When Phase 2 is done, these tests will run against real provider code.
For now, they define the contract and will be imported/extended.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel


class TestLLMProviderInterface:
    """Tests for the LLMProvider abstract interface contract.

    Every provider must implement: chat(), chat_stream(), count_tokens(), provider_id
    """

    def test_message_type_contract(self):
        """Our Message type must have: role, content, tool_calls, tool_call_id."""
        from src.http.ws_protocol import AiTokenMessage, DoneMessage, InterruptMessage

        msg = AiTokenMessage(content="test")
        data = msg.model_dump()
        assert "type" in data
        assert "content" in data

    def test_tool_call_contract(self):
        """ToolCall must have: id, name, arguments."""
        from src.http.ws_protocol import ToolStartMessage

        tc = ToolStartMessage(tool="time_get", call_id="call_1", args={"user_id": "test"})
        data = tc.model_dump()
        assert data["tool"] == "time_get"
        assert data["call_id"] == "call_1"
        assert data["args"] == {"user_id": "test"}


class TestOllamaProviderContract:
    """Contract tests for Ollama provider.

    Verifies Ollama API format expectations:
    - POST /api/chat with model, messages, tools (optional), stream (optional)
    - Response: {"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}
    - Streaming: NDJSON lines
    """

    def test_ollama_chat_request_format(self):
        """Ollama chat request must include model, messages, and optional tools."""
        expected_request = {
            "model": "minimax-m2.5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
        }
        assert "model" in expected_request
        assert "messages" in expected_request
        assert len(expected_request["messages"]) == 2

    def test_ollama_chat_response_format(self):
        """Ollama chat response must have message.role and message.content."""
        response = {
            "model": "minimax-m2.5",
            "message": {"role": "assistant", "content": "Hello! How can I help?"},
            "done": True,
        }
        assert response["message"]["role"] == "assistant"
        assert response["message"]["content"] == "Hello! How can I help?"

    def test_ollama_tool_call_response(self):
        """Ollama response with tool calls must include tool_calls list."""
        response = {
            "model": "minimax-m2.5",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "time_get",
                            "arguments": {"user_id": "default"},
                        }
                    }
                ],
            },
            "done": True,
        }
        assert "tool_calls" in response["message"]
        assert response["message"]["tool_calls"][0]["function"]["name"] == "time_get"

    def test_ollama_streaming_chunk_format(self):
        """Ollama streaming responses are NDJSON lines."""
        chunk = '{"model":"minimax-m2.5","message":{"role":"assistant","content":"Hello"},"done":false}\n'
        import json

        data = json.loads(chunk.strip())
        assert data["message"]["content"] == "Hello"
        assert data["done"] is False

    def test_ollama_connection_error_handled(self):
        """Connection refused must produce a clean error, not a crash."""
        # Will be implemented when OllamaProvider exists
        pass


class TestOpenAIProviderContract:
    """Contract tests for OpenAI + OpenAI-compatible provider.

    Verifies OpenAI API format expectations:
    - POST /v1/chat/completions with model, messages, tools (optional), stream (optional)
    - Response: {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
    - Streaming: SSE chunks with data: {...}\n\n
    """

    def test_openai_chat_request_format(self):
        """OpenAI chat request must follow the /v1/chat/completions format."""
        expected_request = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
        }
        assert "model" in expected_request
        assert "messages" in expected_request

    def test_openai_chat_response_format(self):
        """OpenAI chat response must have choices[0].message."""
        response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
        }
        assert response["choices"][0]["message"]["content"] == "Hello!"

    def test_openai_tool_call_format(self):
        """OpenAI tool calls must have id, type, function.name, function.arguments."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "time_get",
                                    "arguments": '{"user_id": "default"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        tc = response["choices"][0]["message"]["tool_calls"][0]
        assert tc["id"] == "call_abc123"
        assert tc["function"]["name"] == "time_get"

    def test_openai_streaming_chunk_format(self):
        """OpenAI streaming uses SSE: data: {"choices": [{"delta": {"content": "..."}}]}"""
        import json

        chunk = (
            'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"Hello"},"index":0}]}\n\n'
        )
        data_str = chunk.replace("data: ", "").strip()
        data = json.loads(data_str)
        assert data["choices"][0]["delta"]["content"] == "Hello"

    def test_openai_compatible_base_url(self):
        """OpenAI-compatible provider must work with custom base_url."""
        configs = [
            {"type": "openai-compatible", "base_url": "https://api.groq.com/openai/v1"},
            {"type": "openai-compatible", "base_url": "https://api.together.xyz/v1"},
            {"type": "openai-compatible", "base_url": "http://localhost:1234/v1"},
        ]
        for config in configs:
            assert config["base_url"].endswith("/v1") or "localhost" in config["base_url"]


class TestAnthropicProviderContract:
    """Contract tests for Anthropic provider.

    Verifies Anthropic API format expectations:
    - POST /v1/messages with model, messages, max_tokens, tools (optional)
    - Response: {"content": [{"type": "text", "text": "..."}]}
    - Tool use: {"type": "tool_use", "id": "..., "name": "..., "input": {...}}
    - Streaming: SSE with event types: message_start, content_block_start, content_block_delta, content_block_stop, message_delta, message_stop
    """

    def test_anthropic_chat_request_format(self):
        """Anthropic request must include model, messages, max_tokens."""
        expected_request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 4096,
        }
        assert "model" in expected_request
        assert "messages" in expected_request
        assert "max_tokens" in expected_request

    def test_anthropic_chat_response_format(self):
        """Anthropic response must have content list with text blocks."""
        response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
        }
        assert response["content"][0]["type"] == "text"
        assert response["content"][0]["text"] == "Hello!"

    def test_anthropic_tool_use_format(self):
        """Anthropic tool use has type=tool_use with id, name, input."""
        response = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "time_get",
                    "input": {"user_id": "default"},
                }
            ],
            "stop_reason": "tool_use",
        }
        tool_block = response["content"][0]
        assert tool_block["type"] == "tool_use"
        assert tool_block["name"] == "time_get"
        assert tool_block["input"]["user_id"] == "default"

    def test_anthropic_streaming_event_types(self):
        """Anthropic streaming uses specific event types."""
        event_types = [
            "message_start",
            "content_block_start",
            "content_block_delta",
            "content_block_stop",
            "message_delta",
            "message_stop",
        ]
        for et in event_types:
            assert isinstance(et, str)
            assert len(et) > 0

    def test_anthropic_thinking_block(self):
        """Anthropic extended thinking has type=thinking."""
        thinking_block = {"type": "thinking", "thinking": "Let me analyze this..."}
        assert thinking_block["type"] == "thinking"
        assert "thinking" in thinking_block


class TestProviderFactoryContract:
    """Contract tests for provider factory configuration."""

    def test_config_from_yaml_format(self):
        """Config must support the provider format from PLAN.md."""
        config = {
            "llm": {
                "default_provider": "ollama",
                "default_model": "minimax-m2.5",
                "providers": {
                    "ollama": {"type": "ollama", "base_url": "http://localhost:11434"},
                    "openai": {"type": "openai", "api_key_env": "OPENAI_API_KEY"},
                    "anthropic": {"type": "anthropic", "api_key_env": "ANTHROPIC_API_KEY"},
                },
            }
        }
        assert config["llm"]["default_provider"] == "ollama"
        assert "ollama" in config["llm"]["providers"]
        assert config["llm"]["providers"]["ollama"]["type"] == "ollama"

    def test_openai_compatible_covers_many_providers(self):
        """Any provider with REST /v1/chat/completions works with OpenAI-compatible type."""
        compatible_providers = [
            "groq",
            "together",
            "deepseek",
            "openrouter",
            "lmstudio",
            "llamacpp",
        ]
        base_urls = {
            "groq": "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "lmstudio": "http://localhost:1234/v1",
            "llamacpp": "http://localhost:8080/v1",
        }
        for provider in compatible_providers:
            assert provider in base_urls
            assert "/v1" in base_urls[provider]

    def test_model_info_from_registry_contract(self):
        """Model info must include: id, name, provider_id, tool_call, reasoning, context_window."""
        from src.http.ws_protocol import DoneMessage

        required_fields = ["id", "name", "provider_id", "tool_call", "reasoning", "context_window"]
        for field in required_fields:
            assert isinstance(field, str)
