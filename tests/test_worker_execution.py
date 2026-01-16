"""Unit tests for worker execution."""

import pytest

pytest.skip("Worker agents are archived.", allow_module_level=True)

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cassey.storage.file_sandbox import set_thread_id
from cassey.storage.workers import Worker
from cassey.tools.orchestrator_tools import execute_worker


@pytest.fixture
def sample_worker():
    """Create a sample worker for testing."""
    return Worker(
        id=1,
        user_id="test_user",
        thread_id="telegram:test_thread",
        name="test_worker",
        tools=["execute_python"],
        prompt="You are a test worker. Execute the given task.",
        status="active",
        created_at=datetime.now(),
        archived_at=None,
    )


@pytest.fixture
def mock_get_all_tools():
    """Mock get_all_tools to return test tools."""
    from langchain_core.tools import tool

    @tool
    def execute_python(code: str) -> str:
        """Execute Python code."""
        return f"Executed: {code}"

    @tool
    def read_file(path: str) -> str:
        """Read a file."""
        return f"Content of {path}"

    return [execute_python, read_file]


class TestExecuteWorker:
    """Test execute_worker function."""

    @pytest.mark.asyncio
    async def test_execute_worker_success(self, sample_worker, mock_get_all_tools):
        """Test successful worker execution."""
        set_thread_id(sample_worker.thread_id)

        # Mock the agent graph
        mock_agent = AsyncMock()
        mock_result = {
            "messages": [
                MagicMock(
                    content="Task completed successfully",
                    __class__="AIMessage",
                )
            ]
        }
        mock_agent.ainvoke.return_value = mock_result

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Test task",
                        flow="Simple flow",
                        thread_id=sample_worker.thread_id,
                        timeout=30,
                    )

        assert error is None
        assert result == "Task completed successfully"

    @pytest.mark.asyncio
    async def test_execute_worker_timeout(self, sample_worker, mock_get_all_tools):
        """Test worker execution timeout."""
        set_thread_id(sample_worker.thread_id)

        # Mock the agent to timeout - use a coroutine that takes too long
        async def timeout_invoke(*args, **kwargs):
            import asyncio
            await asyncio.sleep(5)  # Longer than timeout
            return {"messages": []}

        mock_agent = AsyncMock()
        mock_agent.ainvoke = timeout_invoke

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Test task",
                        flow="Long running flow",
                        thread_id=sample_worker.thread_id,
                        timeout=1,  # Very short timeout for testing
                    )

        assert result is None
        assert error is not None
        assert "timed out" in error.lower()

    @pytest.mark.asyncio
    async def test_execute_worker_exception(self, sample_worker, mock_get_all_tools):
        """Test worker execution with exception."""
        set_thread_id(sample_worker.thread_id)

        # Mock the agent to raise exception
        mock_agent = AsyncMock(side_effect=RuntimeError("Worker failed"))

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Test task",
                        flow="Failing flow",
                        thread_id=sample_worker.thread_id,
                        timeout=30,
                    )

        assert result is None
        assert error is not None
        assert "Worker execution failed" in error

    @pytest.mark.asyncio
    async def test_execute_worker_with_tools_subset(self, sample_worker, mock_get_all_tools):
        """Test that worker only gets assigned tools."""
        set_thread_id(sample_worker.thread_id)

        # Worker only has execute_python
        sample_worker.tools = ["execute_python"]

        mock_agent = AsyncMock()
        mock_result = {
            "messages": [MagicMock(content="Done", __class__="AIMessage")]
        }
        mock_agent.ainvoke.return_value = mock_result

        called_with_tools = []

        def capture_tools(model, tools, **kwargs):
            called_with_tools.extend([t.name for t in tools])
            # Return mock agent
            return mock_agent

        with patch("cassey.agent.graph.create_graph", side_effect=capture_tools):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Test",
                        flow="Flow",
                        thread_id=sample_worker.thread_id,
                        timeout=30,
                    )

        # Should only have execute_python, not read_file
        assert "execute_python" in called_with_tools
        assert "read_file" not in called_with_tools

    @pytest.mark.asyncio
    async def test_execute_worker_no_output(self, sample_worker, mock_get_all_tools):
        """Test worker execution with no output messages."""
        set_thread_id(sample_worker.thread_id)

        # Mock agent with no messages
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"messages": []}

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Test",
                        flow="Flow",
                        thread_id=sample_worker.thread_id,
                        timeout=30,
                    )

        assert error is None
        assert result == "Worker completed with no output"

    @pytest.mark.asyncio
    async def test_execute_worker_uses_prompt(self, sample_worker, mock_get_all_tools):
        """Test that worker's prompt is used."""
        set_thread_id(sample_worker.thread_id)

        custom_prompt = "You are a specialized calculator."

        sample_worker.prompt = custom_prompt

        mock_agent = AsyncMock()
        mock_result = {
            "messages": [MagicMock(content="Calculated", __class__="AIMessage")]
        }
        mock_agent.ainvoke.return_value = mock_result

        captured_prompt = []

        def capture_prompt(model, tools, checkpointer, system_prompt):
            captured_prompt.append(system_prompt)
            return mock_agent

        with patch("cassey.agent.graph.create_graph", side_effect=capture_prompt):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=sample_worker,
                        task="Calculate 2+2",
                        flow="Simple calculation",
                        thread_id=sample_worker.thread_id,
                        timeout=30,
                    )

        assert custom_prompt in captured_prompt


class TestWorkerIntegration:
    """Integration tests for worker execution patterns."""

    @pytest.mark.asyncio
    async def test_conditional_flow_worker(self, mock_get_all_tools):
        """Test worker with conditional flow logic."""
        worker = Worker(
            id=2,
            user_id="test_user",
            thread_id="telegram:test",
            name="conditional_worker",
            tools=["execute_python"],
            prompt="""You are a conditional worker.
Execute the flow with if/else logic as described.
If the condition is met, create a message file.
Otherwise, log to a file.""",
            status="active",
            created_at=datetime.now(),
            archived_at=None,
        )

        set_thread_id(worker.thread_id)

        mock_agent = AsyncMock()
        mock_result = {
            "messages": [
                MagicMock(
                    content="Condition was false, logged to file",
                    __class__="AIMessage",
                )
            ]
        }
        mock_agent.ainvoke.return_value = mock_result

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=worker,
                        task="Check if price < 100",
                        flow="If price < 100, create notification. Else, log to database.",
                        thread_id=worker.thread_id,
                        timeout=30,
                    )

        assert error is None
        assert "logged to file" in result.lower()

    @pytest.mark.asyncio
    async def test_loop_flow_worker(self, mock_get_all_tools):
        """Test worker with loop flow logic."""
        worker = Worker(
            id=3,
            user_id="test_user",
            thread_id="telegram:test",
            name="loop_worker",
            tools=["execute_python"],
            prompt="""You are a loop worker.
Execute the flow with for/while loop logic as described.
Process each item in the collection.""",
            status="active",
            created_at=datetime.now(),
            archived_at=None,
        )

        set_thread_id(worker.thread_id)

        mock_agent = AsyncMock()
        mock_result = {
            "messages": [
                MagicMock(
                    content="Processed 5 items, found 2 matches",
                    __class__="AIMessage",
                )
            ]
        }
        mock_agent.ainvoke.return_value = mock_result

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=worker,
                        task="Check all products",
                        flow="For each product: fetch price → if < $100 add to alerts",
                        thread_id=worker.thread_id,
                        timeout=30,
                    )

        assert error is None
        assert "Processed" in result

    @pytest.mark.asyncio
    async def test_retry_flow_worker(self, mock_get_all_tools):
        """Test worker with retry logic."""
        worker = Worker(
            id=4,
            user_id="test_user",
            thread_id="telegram:test",
            name="retry_worker",
            tools=["execute_python"],
            prompt="""You are a retry worker.
Execute with retry logic: if API call fails, retry up to 3 times.""",
            status="active",
            created_at=datetime.now(),
            archived_at=None,
        )

        set_thread_id(worker.thread_id)

        mock_agent = AsyncMock()
        mock_result = {
            "messages": [
                MagicMock(
                    content="API call succeeded on retry 2",
                    __class__="AIMessage",
                )
            ]
        }
        mock_agent.ainvoke.return_value = mock_result

        with patch("cassey.agent.graph.create_graph", return_value=mock_agent):
            with patch("cassey.tools.orchestrator_tools.create_model"):
                with patch("cassey.tools.orchestrator_tools.get_all_tools", return_value=mock_get_all_tools):
                    result, error = await execute_worker(
                        worker=worker,
                        task="Fetch data from API",
                        flow="Check API → if error retry 3x → if still fails, send alert",
                        thread_id=worker.thread_id,
                        timeout=30,
                    )

        assert error is None
        assert "retry" in result.lower()
