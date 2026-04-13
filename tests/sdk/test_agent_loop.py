"""Agent Loop conformance tests.

These tests verify that the agent loop (whether LangChain's create_agent
or our custom AgentLoop) produces consistent observable behavior.

Currently STUBS - will be implemented as part of Phase 0.2.
"""

import pytest


class TestAgentLoopBasic:
    """Basic agent loop behavior that must be consistent across implementations."""

    def test_simple_query_returns_response(self):
        """A simple query must produce at least one AI message response."""
        pass

    def test_tool_call_triggers_execution(self):
        """When the model requests a tool call, it must be executed and result returned."""
        pass

    def test_multiple_tool_calls_in_sequence(self):
        """Multiple tool calls in a single turn must all be executed."""
        pass

    def test_loop_terminates_on_no_tool_calls(self):
        """Agent loop must terminate when model returns no tool calls."""
        pass

    def test_max_iterations_limit(self):
        """Agent loop must stop after max_iterations even if model keeps requesting tools."""
        pass


class TestAgentLoopStreaming:
    """Streaming behavior conformance."""

    def test_stream_produces_tokens(self):
        """Streaming must produce at least one ai_token event."""
        pass

    def test_stream_produces_done(self):
        """Streaming must end with a done event."""
        pass

    def test_stream_tool_events(self):
        """Tool calls must produce tool_start and tool_end events in stream."""
        pass


class TestAgentLoopErrorHandling:
    """Error handling conformance."""

    def test_tool_error_returns_string(self):
        """When a tool raises an exception, the result must be an error string."""
        pass

    def test_llm_error_graceful(self):
        """When the LLM fails, the agent must return an error message (not crash)."""
        pass

    def test_system_prompt_included(self):
        """The system prompt must be included as the first message."""
        pass
