"""SDK conformance tests.

These tests verify that any agent loop implementation (LangChain or our custom SDK)
produces the same observable behavior. They serve as regression guards during
the SDK migration (Phases 1-7).

Currently INCOMPLETE - these are stubs that will be filled in during Phase 0.2-0.5.
To run against the current LangChain implementation, set SDK_IMPL=langchain.
To run against the new SDK, set SDK_IMPL=sdk.
"""

import os
import pytest

# Marker to distinguish conformance tests that need a live LLM
# vs. tests that can run with mocked responses
needs_llm = pytest.mark.skipif(
    os.environ.get("SKIP_LLM_TESTS", "1") == "1",
    reason="Set SKIP_LLM_TESTS=0 to run LLM-dependent tests",
)


class TestMessageContracts:
    """Verify message type contracts are met by both implementations."

    These tests ensure that the output of the agent loop (regardless of
    implementation) conforms to the expected message structure:
    - Messages have: role, content, tool_calls (optional), tool_call_id (optional)
    - Tool calls have: id, name, arguments (dict)
    - Streaming yields: ai_token, tool_start, tool_end, done events
    """

    def test_message_has_role(self):
        """Every message must have a 'role' field."""
        # TODO: Phase 0.2 - implement with actual agent invocation
        pass

    def test_message_has_content(self):
        """Every message must have a 'content' field (may be empty string)."""
        pass

    def test_ai_message_may_have_tool_calls(self):
        """AI messages may include tool_calls list."""
        pass

    def test_tool_result_has_call_id(self):
        """Tool result messages must reference the tool_call_id."""
        pass


class TestToolCallingContracts:
    """Verify tool calling behavior is consistent."""

    def test_tool_call_includes_name_and_args(self):
        """Tool calls must include name (str) and arguments (dict)."""
        pass

    def test_tool_result_matches_call_id(self):
        """Tool result message must have tool_call_id matching the call."""
        pass

    def test_multiple_tool_calls_sequential(self):
        """When the model makes multiple tool calls, results are returned in order."""
        pass


class TestStreamingContracts:
    """Verify streaming event format consistency."""

    def test_stream_emits_ai_tokens(self):
        """Streaming must emit ai_token events with content."""
        pass

    def test_stream_emits_done(self):
        """Streaming must end with a 'done' event."""
        pass

    def test_stream_emits_tool_events(self):
        """Tool calls must produce tool_start and tool_end events."""
        pass

    def test_stream_events_are_json(self):
        """All stream events must be valid JSON with a 'type' field."""
        pass


class TestMiddlewareContracts:
    """Verify middleware execution order and output consistency."""

    def test_memory_middleware_runs_before_agent(self):
        """MemoryMiddleware must inject context before the agent processes messages."""
        pass

    def test_skill_middleware_injects_prompt(self):
        """SkillMiddleware must add skill prompt to the system message."""
        pass

    def test_middleware_order_is_memory_then_skill_then_summarization(self):
        """Middlewares must run in order: Memory → Skill → Summarization."""
        pass


class TestErrorHandling:
    """Verify error handling consistency."""

    def test_llm_error_returns_error_message(self):
        """When LLM fails, return error message (not crash)."""
        pass

    def test_tool_error_returns_result_string(self):
        """When a tool raises, return error as string result."""
        pass

    def test_max_iterations_exits_gracefully(self):
        """Agent must stop after max_iterations without crashing."""
        pass
