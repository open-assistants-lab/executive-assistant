"""LLM Provider contract tests.

These define the contract that each LLM provider (Ollama, OpenAI, Anthropic,
OpenAI-compatible) must fulfill. They use mocked HTTP responses to verify:
- Request format is correct
- Response parsing works
- Tool call extraction works
- Streaming chunk parsing works
- Error handling works

Currently STUBS - will be implemented in Phase 2 alongside the providers.
"""

import pytest


class TestLLMProviderBase:
    """Tests for the LLMProvider abstract interface.

    These define the contract that any provider implementation must satisfy.
    They should work with a MockProvider that inherits from LLMProvider.
    """

    def test_provider_has_chat_method(self):
        """Every provider must implement async chat()."""
        pass  # Phase 2: from src.sdk.providers.base import LLMProvider

    def test_provider_has_chat_stream_method(self):
        """Every provider must implement async chat_stream() returning AsyncIterator."""
        pass

    def test_provider_has_count_tokens_method(self):
        """Every provider must implement count_tokens()."""
        pass

    def test_provider_returns_message(self):
        """chat() must return a Message object with role, content, tool_calls."""
        pass

    def test_provider_stream_yields_chunks(self):
        """chat_stream() must yield StreamEvent objects with known types."""
        pass


class TestOllamaProvider:
    """Contract tests for Ollama provider.

    Verifies that HTTP requests to /api/chat are formatted correctly
    and responses are parsed into our Message/ToolCall format.
    """

    def test_chat_request_format(self):
        """Ollama chat request must include model, messages, and optional tools."""
        pass

    def test_chat_response_parsing(self):
        """Ollama chat response must be parsed into Message with content."""
        pass

    def test_tool_call_parsing(self):
        """Ollama tool calls must be parsed from the response."""
        pass

    def test_streaming_ndjson_parsing(self):
        """Ollama streaming must parse NDJSON lines into StreamEvents."""
        pass

    def test_connection_error_handling(self):
        """Ollama must handle connection refused gracefully."""
        pass

    def test_model_not_found_error(self):
        """Ollama must handle model not found error gracefully."""
        pass


class TestOpenAIProvider:
    """Contract tests for OpenAI + OpenAI-compatible provider."""

    def test_chat_request_format(self):
        """OpenAI chat request must include model, messages, and optional tools."""
        pass

    def test_chat_response_parsing(self):
        """OpenAI response must be parsed into Message."""
        pass

    def test_tool_call_parsing(self):
        """OpenAI tool_calls must be parsed from the response."""
        pass

    def test_streaming_sse_parsing(self):
        """OpenAI streaming must parse SSE chunks into StreamEvents."""
        pass

    def test_custom_base_url(self):
        """OpenAI-compatible provider must work with custom base_url."""
        pass

    def test_api_key_from_env(self):
        """Provider must read API key from environment variable."""
        pass


class TestAnthropicProvider:
    """Contract tests for Anthropic provider."""

    def test_chat_request_format(self):
        """Anthropic request must include model, messages, max_tokens, and optional tools."""
        pass

    def test_chat_response_parsing(self):
        """Anthropic response must be parsed into Message."""
        pass

    def test_tool_use_block_parsing(self):
        """Anthropic tool_use content blocks must be parsed into ToolCalls."""
        pass

    def test_streaming_event_parsing(self):
        """Anthropic streaming must parse message_start, content_block_start/delta/end, message_end events."""
        pass

    def test_thinking_block_handling(self):
        """Anthropic extended thinking blocks must be handled."""
        pass


class TestProviderFactory:
    """Contract tests for the provider factory."""

    def test_create_ollama_provider(self):
        """Factory must create OllamaProvider when type='ollama'."""
        pass

    def test_create_openai_provider(self):
        """Factory must create OpenAIProvider when type='openai'."""
        pass

    def test_create_anthropic_provider(self):
        """Factory must create AnthropicProvider when type='anthropic'."""
        pass

    def test_create_openai_compatible_provider(self):
        """Factory must create OpenAIProvider with custom base_url when type='openai-compatible'."""
        pass

    def test_unknown_provider_raises(self):
        """Factory must raise ValueError for unknown provider type."""
        pass

    def test_config_from_yaml(self):
        """Factory must read provider config from config.yaml."""
        pass
