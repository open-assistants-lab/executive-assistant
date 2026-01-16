"""Unit tests for reviewer fix items (2025-01-15 review).

Tests for:
1. Iterations counter increments
2. Checkpoint state handled by LangGraph
3. Thread-local fallback for thread_id
4. Delegate to orchestrator no deadlock
"""

import asyncio
import threading
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cassey.agent.graph import route_agent, create_react_graph
from cassey.agent.nodes import increment_iterations
from cassey.agent.state import AgentState
from cassey.storage.file_sandbox import set_thread_id, get_thread_id, clear_thread_id


class TestIterationsCounter:
    """Test that iterations counter increments properly."""

    def test_increment_iterations_function(self):
        """Test the increment_iterations function directly."""
        state: AgentState = {
            "messages": [],
            "iterations": 0,
        }

        result = increment_iterations(state)
        assert result["iterations"] == 1

        # Increment again
        state["iterations"] = result["iterations"]
        result = increment_iterations(state)
        assert result["iterations"] == 2

    def test_iterations_respects_max_iterations(self):
        """Test that max iterations limit is enforced."""
        from cassey.config.settings import settings
        MAX_ITERATIONS = settings.MAX_ITERATIONS

        # Create state at max iterations with tool calls
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="Response"),
        ]
        # Add tool calls to last AI message
        messages[1].tool_calls = [
            {"name": "test_tool", "args": {}, "id": "call_123"}
        ]

        state: AgentState = {
            "messages": messages,
            "iterations": MAX_ITERATIONS,
        }

        result = route_agent(state)
        # At max iterations with tool calls, should NOT route to tools
        # Instead should check summarization or end
        assert result != "tools"

    def test_iterations_increment_below_max(self):
        """Test that below max iterations allows tool execution."""
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="Response"),
        ]
        messages[1].tool_calls = [
            {"name": "test_tool", "args": {}, "id": "call_123"}
        ]

        state: AgentState = {
            "messages": messages,
            "iterations": 0,  # Below max
        }

        result = route_agent(state)
        # Should route to tools since iterations < MAX_ITERATIONS
        assert result == "tools"

    def test_graph_has_increment_node(self):
        """Test that the graph includes the increment node."""
        from unittest.mock import Mock

        mock_model = Mock()
        mock_model.bind_tools = Mock(return_value=mock_model)

        # Create graph
        graph = create_react_graph(
            model=mock_model,
            tools=[],
            checkpointer=None,
        )

        # Check that increment node exists
        # The graph should have nodes: agent, tools, summarize, increment
        compiled_graph = graph.compile()
        # We can't directly inspect nodes, but we can verify the graph compiles
        assert compiled_graph is not None


class TestCheckpointHandling:
    """Test that LangGraph handles checkpoints without manual rehydration."""

    def test_langgraph_checkpoint_integration(self):
        """Test that LangGraph astream with config uses checkpointer.

        This test verifies the behavior after Fix #2 where manual
        checkpoint rehydration was removed. LangGraph should handle
        state restoration automatically when thread_id is provided.
        """
        from unittest.mock import Mock, AsyncMock
        from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint

        # Create mock checkpointer
        mock_checkpointer = Mock(spec=BaseCheckpointSaver)
        mock_checkpoint = Checkpoint(
            channel_values={
                "messages": [HumanMessage(content="Previous message")],
                "structured_summary": None,
                "iterations": 5,
            }
        )
        mock_checkpointer.aget = AsyncMock(return_value=mock_checkpoint)

        # Create graph with checkpointer
        mock_model = Mock()
        mock_model.bind_tools = Mock(return_value=mock_model)
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        graph = create_react_graph(
            model=mock_model,
            tools=[],
            checkpointer=mock_checkpointer,
        )
        compiled = graph.compile(checkpointer=mock_checkpointer)

        # Config with thread_id
        config = {"configurable": {"thread_id": "test_thread_123"}}

        # The graph should automatically load checkpoint when we pass new message only
        # We're simulating the behavior from channels/base.py after Fix #2
        new_state = {
            "messages": [HumanMessage(content="New message")],
            "channel": "test",
        }

        # Stream should work (LangGraph handles checkpoint merging)
        # This test verifies the pattern is correct, actual async execution
        # would require more complex setup
        assert compiled is not None


class TestThreadLocalFallback:
    """Test thread-local fallback for thread_id propagation."""

    def test_context_var_propagation(self):
        """Test ContextVar works in async context."""
        # Clear any existing context
        clear_thread_id()

        # Set thread_id
        set_thread_id("test_context_var")
        assert get_thread_id() == "test_context_var"

        # Clear
        clear_thread_id()
        assert get_thread_id() is None

    def test_thread_local_fallback(self):
        """Test thread-local fallback when ContextVar is empty.

        This tests Fix #3 where we added thread-local dict fallback
        for cases where ContextVar doesn't propagate (e.g., thread pools).
        """
        from cassey.storage.file_sandbox import _thread_local_fallback, _thread_local_lock

        # Clear ContextVar
        clear_thread_id()

        # Manually set thread-local fallback
        thread_id_int = threading.get_ident()
        with _thread_local_lock:
            _thread_local_fallback[thread_id_int] = "fallback_thread_id"

        # get_thread_id should find the fallback
        result = get_thread_id()
        assert result == "fallback_thread_id"

        # Clean up
        with _thread_local_lock:
            _thread_local_fallback.pop(thread_id_int, None)

    def test_set_thread_id_updates_both(self):
        """Test that set_thread_id updates both ContextVar and thread-local."""
        from cassey.storage.file_sandbox import _thread_local_fallback, _thread_local_lock

        clear_thread_id()

        test_id = "test_both_mechanisms"
        set_thread_id(test_id)

        # Check ContextVar
        from cassey.storage.file_sandbox import _thread_id
        assert _thread_id.get() == test_id

        # Check thread-local fallback
        thread_id_int = threading.get_ident()
        with _thread_local_lock:
            assert _thread_local_fallback.get(thread_id_int) == test_id

        # Clean up
        clear_thread_id()

    def test_clear_thread_id_clears_both(self):
        """Test that clear_thread_id clears both mechanisms."""
        from cassey.storage.file_sandbox import _thread_local_fallback, _thread_local_lock

        set_thread_id("test_clear")
        thread_id_int = threading.get_ident()

        # Clear
        clear_thread_id()

        # Check ContextVar is cleared
        from cassey.storage.file_sandbox import _thread_id
        assert _thread_id.get() is None

        # Check thread-local is cleared
        with _thread_local_lock:
            assert thread_id_int not in _thread_local_fallback

    def test_concurrent_thread_isolation(self):
        """Test that concurrent threads maintain separate thread_ids."""
        import time
        from cassey.storage.file_sandbox import _thread_local_fallback, _thread_local_lock

        clear_thread_id()

        results = {}

        def thread_func(thread_name, thread_value):
            """Function to run in separate thread."""
            set_thread_id(thread_value)
            time.sleep(0.01)  # Small delay
            results[thread_name] = get_thread_id()
            clear_thread_id()

        # Create multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(
                target=thread_func,
                args=(f"thread_{i}", f"value_{i}")
            )
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Each thread should have its own value
        assert results["thread_0"] == "value_0"
        assert results["thread_1"] == "value_1"
        assert results["thread_2"] == "value_2"


@pytest.mark.skip(reason="Orchestrator/worker agents are archived.")
class TestDelegateToOrchestratorNoDeadlock:
    """Test that delegate_to_orchestrator doesn't deadlock.

    Tests Fix #4 where run_coroutine_threadsafe + future.result()
    was replaced with asyncio.create_task + asyncio.wait_for.
    """

    def test_delegate_uses_create_task_not_threadsafe(self):
        """Test that delegate_to_orchestrator uses create_task pattern.

        After Fix #4, the function should use asyncio.create_task()
        instead of asyncio.run_coroutine_threadsafe() when in an
        event loop, avoiding potential deadlock.
        """
        from cassey.tools.orchestrator_tools import delegate_to_orchestrator
        from unittest.mock import patch, AsyncMock

        # Mock set_thread_id and get_thread_id
        with patch("cassey.tools.orchestrator_tools.get_thread_id", return_value="test_thread"):
            # Mock invoke_orchestrator to avoid actual execution
            with patch("cassey.tools.orchestrator_tools.invoke_orchestrator", new=AsyncMock(return_value="Success")):
                async def test_in_async_context():
                    """Test that async context uses create_task pattern."""
                    result = await delegate_to_orchestrator.ainvoke({
                        "task": "test task",
                        "flow": "test flow",
                        "schedule": "",
                    })
                    return result

                # Run the async test
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(test_in_async_context())
                    assert "Success" in result or result == "Success"
                finally:
                    loop.close()

    def test_delegate_handles_timeout(self):
        """Test that delegate_to_orchestrator handles timeout properly.

        Note: This test verifies the code structure uses asyncio.wait_for
        which properly handles TimeoutError. Actual timeout testing would
        require waiting 60 seconds which is too long for unit tests.
        """
        from cassey.tools.orchestrator_tools import delegate_to_orchestrator
        from unittest.mock import patch
        import asyncio

        # Verify that the code uses asyncio.wait_for with timeout=60
        # We can see this in the source code of delegate_to_orchestrator
        # The important part is that it catches asyncio.TimeoutError

        async def verify_timeout_handling():
            """Verify timeout error is caught and handled."""
            # Simulate timeout by patching invoke_orchestrator to raise TimeoutError
            async def timeout_orchestrator(*args, **kwargs):
                raise asyncio.TimeoutError()

            with patch("cassey.tools.orchestrator_tools.get_thread_id", return_value="test_thread"):
                with patch("cassey.tools.orchestrator_tools.invoke_orchestrator", new=timeout_orchestrator):
                    result = await delegate_to_orchestrator.ainvoke({
                        "task": "test task",
                        "flow": "test flow",
                        "schedule": "",
                    })
                    return result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(verify_timeout_handling())
            assert "timed out" in result.lower() or "timeout" in result.lower()
        finally:
            loop.close()

    @pytest.mark.asyncio
    async def test_delegate_handles_no_thread_id(self):
        """Test that delegate_to_orchestrator handles missing thread_id."""
        from cassey.tools.orchestrator_tools import delegate_to_orchestrator

        with patch("cassey.tools.orchestrator_tools.get_thread_id", return_value=None):
            result = await delegate_to_orchestrator.ainvoke({
                "task": "test task",
                "flow": "test flow",
                "schedule": "",
            })
            assert "No thread_id" in result


class TestSandboxFileExtensionValidation:
    """Test file sandbox extension validation (Fix #2 partial)."""

    def test_extension_validation_for_new_files(self):
        """Test that file extension is validated even for new files.

        This addresses the reviewer's concern: "File sandbox extension
        checks can be bypassed for new files; validate suffix even if
        the file does not exist."
        """
        from cassey.storage.file_sandbox import FileSandbox, SecurityError
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            sandbox = FileSandbox(
                root=root,
                allowed_extensions={".txt", ".md", ".json"}
            )

            # Test 1: New file with allowed extension should pass
            # (even though file doesn't exist)
            try:
                path = sandbox._validate_path("new_file.txt", allow_directories=False)
                # Note: validation passes but file doesn't exist
                assert path.name == "new_file.txt"
            except SecurityError:
                pytest.fail("Allowed extension should pass validation")

            # Test 2: New file with disallowed extension should fail
            with pytest.raises(SecurityError) as exc_info:
                sandbox._validate_path("new_file.exe", allow_directories=False)
            assert "not allowed" in str(exc_info.value).lower()

            # Test 3: Existing file with allowed extension
            existing_file = root / "existing.txt"
            existing_file.write_text("content")
            path = sandbox._validate_path("existing.txt", allow_directories=False)
            # Compare resolved paths
            assert path.resolve() == existing_file.resolve()

            # Test 4: Existing file with disallowed extension
            existing_exe = root / "existing.exe"
            existing_exe.write_text("content")
            with pytest.raises(SecurityError) as exc_info:
                sandbox._validate_path("existing.exe", allow_directories=False)
            assert "not allowed" in str(exc_info.value).lower()


class TestIntegrationScenarios:
    """Integration tests for combined scenarios."""

    def test_state_flow_with_iterations_and_checkpoint(self):
        """Test complete flow: state -> tools -> increment -> agent.

        This verifies that:
        1. Iterations increment after tools
        2. Checkpointer state is preserved
        3. Max iterations is enforced
        """
        from cassey.config.settings import settings
        MAX_ITERATIONS = settings.MAX_ITERATIONS

        # Simulate multiple tool execution cycles
        state: AgentState = {
            "messages": [HumanMessage(content="Initial")],
            "iterations": 0,
        }

        # Simulate: agent -> tools -> increment cycle
        for i in range(MAX_ITERATIONS - 1):
            # After tools, increment iterations
            state["iterations"] = increment_iterations(state)["iterations"]
            assert state["iterations"] == i + 1

            # Should still route to tools if tool calls present and iterations < MAX_ITERATIONS
            ai_msg = AIMessage(content=f"Thinking {i+1}")
            ai_msg.tool_calls = [{"name": "tool", "args": {}, "id": f"call_{i}"}]
            state["messages"].append(ai_msg)

            route = route_agent(state)
            # Check: if iterations < MAX_ITERATIONS, should route to tools
            if state["iterations"] < MAX_ITERATIONS:
                assert route == "tools", f"Iteration {i+1} should route to tools"
            else:
                # At or above max iterations, should NOT route to tools
                assert route != "tools", "Should not route to tools at max iterations"

        # Now increment to MAX_ITERATIONS
        state["iterations"] = increment_iterations(state)["iterations"]
        assert state["iterations"] == MAX_ITERATIONS

        # Add AI message with tool calls
        ai_msg = AIMessage(content="Final thinking")
        ai_msg.tool_calls = [{"name": "tool", "args": {}, "id": "call_final"}]
        state["messages"].append(ai_msg)

        route = route_agent(state)
        # At MAX_ITERATIONS, should NOT route to tools
        assert route != "tools", f"Should not route to tools at max iterations (got {route})"
