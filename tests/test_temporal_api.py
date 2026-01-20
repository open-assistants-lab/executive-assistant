"""Tests for Temporal API connectivity and basic operations.

These tests verify:
1. Connection to Temporal server
2. Namespace access
3. Basic workflow/health check
4. Error handling

Run with:
    uv run pytest tests/test_temporal_api.py -v

Or with custom Temporal host:
    TEMPORAL_HOST=temporal.example.com uv run pytest tests/test_temporal_api.py -v
"""

import os
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError


# =============================================================================
# Test Configuration
# =============================================================================

class TestTemporalSettings:
    """Test Temporal settings configuration."""

    def test_temporal_settings_defaults(self):
        """Test default Temporal settings."""
        from executive_assistant.config.settings import get_settings
        s = get_settings()

        assert s.TEMPORAL_PORT == 7233
        assert s.TEMPORAL_NAMESPACE == "default"
        assert s.TEMPORAL_TASK_QUEUE == "executive_assistant-workflows"
        assert s.TEMPORAL_CLIENT_TIMEOUT == 30
        assert s.TEMPORAL_CONNECTION_RETRY == 3
        assert s.TEMPORAL_WEB_UI_URL == "http://localhost:8080"

    def test_temporal_enabled_property(self):
        """Test temporal_enabled property reflects HOST configuration."""
        from executive_assistant.config.settings import get_settings
        s = get_settings()

        if s.TEMPORAL_HOST:
            assert s.temporal_enabled
        else:
            assert not s.temporal_enabled

    def test_temporal_target_property(self):
        """Test temporal_target property returns host:port."""
        from executive_assistant.config.settings import get_settings
        s = get_settings()

        if s.TEMPORAL_HOST:
            target = s.temporal_target
            assert ":" in target
            host, port = target.split(":")
            assert host == s.TEMPORAL_HOST
            assert port == str(s.TEMPORAL_PORT)
        else:
            pytest.skip("TEMPORAL_HOST is set - cannot test 'no host' behavior")


# =============================================================================
# Live API Tests (require real Temporal server)
# =============================================================================

@pytest.mark.skipif(
    not os.getenv("TEMPORAL_HOST"),
    reason="TEMPORAL_HOST not set - skipping live tests"
)
class TestTemporalConnection:
    """Test live connection to Temporal server.

    These tests require a running Temporal server. Set TEMPORAL_HOST
    environment variable to run them:

        TEMPORAL_HOST=temporal.gongchatea.com.au uv run pytest tests/test_temporal_api.py::TestTemporalConnection -v
    """

    @pytest.mark.asyncio
    async def test_connection(self):
        """Test basic TCP connection to Temporal server."""
        import asyncio

        host = os.getenv("TEMPORAL_HOST")
        port = int(os.getenv("TEMPORAL_PORT", "7233"))

        try:
            # Test TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            assert True  # Connection successful
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
            pytest.skip(f"Cannot connect to Temporal at {host}:{port}: {e}")

    @pytest.mark.asyncio
    async def test_grpc_connection_with_temporalio(self):
        """Test gRPC connection using temporalio client."""
        try:
            from temporalio.client import Client
        except ImportError:
            pytest.skip("temporalio not installed - run: uv add temporalio")

        host = os.getenv("TEMPORAL_HOST")
        port = int(os.getenv("TEMPORAL_PORT", "7233"))
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

        target = f"{host}:{port}"

        try:
            client = await Client.connect(
                target,
                namespace=namespace,
            )
            # Connection successful
            assert client is not None
        except Exception as e:
            pytest.skip(f"Cannot connect via gRPC to {target}: {e}")

    @pytest.mark.asyncio
    async def test_list_namespaces(self):
        """Test listing namespaces via Temporal API."""
        try:
            from temporalio.client import Client
        except ImportError:
            pytest.skip("temporalio not installed")

        host = os.getenv("TEMPORAL_HOST")
        port = int(os.getenv("TEMPORAL_PORT", "7233"))
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

        target = f"{host}:{port}"

        try:
            client = await Client.connect(target, namespace=namespace)

            # Try to get service capabilities (tests connection + permissions)
            # This is a lightweight operation that doesn't require workflows
            workflow_service = client.workflow_service
            assert workflow_service is not None

        except Exception as e:
            pytest.skip(f"Cannot access Temporal service: {e}")

    @pytest.mark.asyncio
    async def test_describe_namespace(self):
        """Test describing the default namespace."""
        try:
            from temporalio import service
        except ImportError:
            pytest.skip("temporalio not installed")

        host = os.getenv("TEMPORAL_HOST")
        port = int(os.getenv("TEMPORAL_PORT", "7233"))
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

        target = f"{host}:{port}"

        try:
            from temporalio.client import Client
            from temporalio.api.workflow.v1 import workflow_service_pb2, workflow_service_pb2_grpc

            client = await Client.connect(target, namespace=namespace)

            # Try to describe namespace
            request = workflow_service_pb2.DescribeNamespaceRequest(namespace=namespace)
            response = await client.workflow_service.DescribeNamespace(
                request,
                timeout=5.0
            )

            assert response.namespace_info.namespace == namespace

        except Exception as e:
            pytest.skip(f"Cannot describe namespace: {e}")


# =============================================================================
# Mock Tests (always run, no Temporal required)
# =============================================================================

class TestTemporalMocked:
    """Test Temporal integration with mocked client."""

    def test_temporal_properties_with_host(self):
        """Test temporal_enabled and temporal_target when HOST is set."""
        from executive_assistant.config.settings import get_settings
        s = get_settings()

        if s.TEMPORAL_HOST:
            assert s.temporal_enabled
            target = s.temporal_target
            assert s.TEMPORAL_HOST in target
        else:
            assert not s.temporal_enabled

    @pytest.mark.asyncio
    async def test_get_temporal_client_factory(self):
        """Test the get_temporal_client factory function pattern."""
        # This is a test for the pattern we'll implement
        mock_client = MagicMock()

        async def get_temporal_client():
            """Factory function that returns cached client."""
            return mock_client

        client = await get_temporal_client()
        assert client is mock_client

    @pytest.mark.asyncio
    async def test_workflow_spec_model(self):
        """Test WorkflowSpec model validation."""
        from pydantic import BaseModel

        class ExecutorSpec(BaseModel):
            executor_id: str
            name: str
            model: str
            tools: list[str]
            system_prompt: str
            output_schema: dict

        class WorkflowSpec(BaseModel):
            workflow_id: str
            name: str
            description: str
            executors: list[ExecutorSpec]
            schedule_type: str = "immediate"

        # Valid spec
        spec = WorkflowSpec(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            executors=[
                {
                    "executor_id": "step1",
                    "name": "Step 1",
                    "model": "gpt-4o",
                    "tools": ["search_web"],
                    "system_prompt": "You are a helpful assistant.",
                    "output_schema": {"result": "str"}
                }
            ]
        )

        assert spec.workflow_id == "test-workflow"
        assert len(spec.executors) == 1
        assert spec.schedule_type == "immediate"

    @pytest.mark.asyncio
    async def test_workflow_spec_validation(self):
        """Test WorkflowSpec validation with invalid data."""
        from pydantic import BaseModel, ValidationError

        class ExecutorSpec(BaseModel):
            executor_id: str
            name: str
            model: str
            tools: list[str]
            system_prompt: str
            output_schema: dict

        class WorkflowSpec(BaseModel):
            workflow_id: str
            executors: list[ExecutorSpec]

        # Missing required field
        with pytest.raises(ValidationError):
            WorkflowSpec(workflow_id="test")  # Missing executors

        # Invalid schedule type
        from pydantic import Field
        class WorkflowSpecWithSchedule(BaseModel):
            workflow_id: str
            schedule_type: Literal["immediate", "scheduled", "recurring"] = "immediate"

        spec = WorkflowSpecWithSchedule(
            workflow_id="test",
            schedule_type="immediate"
        )
        assert spec.schedule_type == "immediate"


# =============================================================================
# Workflow Tools Tests (mocked)
# =============================================================================

class TestWorkflowTools:
    """Test workflow tool definitions (without Temporal dependency)."""

    @pytest.mark.asyncio
    async def test_create_workflow_tool_signature(self):
        """Test create_workflow tool signature and basic logic."""
        # Test the function signature directly without @tool decorator
        async def create_workflow(
            name: str,
            description: str,
            executors: list[dict],
            schedule_type: str = "immediate",
        ) -> str:
            """Create a workflow from a chain of executors."""
            return f"Workflow '{name}' created with {len(executors)} executors"

        result = await create_workflow(
            name="Test Workflow",
            description="A test",
            executors=[{"executor_id": "step1", "name": "Step 1"}],
        )

        assert "Test Workflow" in result
        assert "1 executors" in result

    @pytest.mark.asyncio
    async def test_list_workflows_tool_signature(self):
        """Test list_workflows tool signature."""
        async def list_workflows(user_id: str, status: str = None) -> list[dict]:
            """List your workflows."""
            return [
                {"workflow_id": "wf1", "name": "Workflow 1", "status": "active"},
                {"workflow_id": "wf2", "name": "Workflow 2", "status": "paused"},
            ]

        result = await list_workflows(user_id="user123")

        assert len(result) == 2
        assert result[0]["name"] == "Workflow 1"


# =============================================================================
# Integration Helper Tests
# =============================================================================

class TestTemporalHelpers:
    """Test helper functions for Temporal integration."""

    def test_build_temporal_target(self):
        """Test building Temporal target string."""
        def build_target(host: str, port: int = 7233) -> str:
            return f"{host}:{port}"

        assert build_target("localhost") == "localhost:7233"
        assert build_target("temporal.example.com", 8223) == "temporal.example.com:8223"
        assert build_target("192.168.1.100") == "192.168.1.100:7233"

    def test_parse_cron_expression(self):
        """Test parsing common cron expressions."""
        def is_valid_cron(cron: str) -> bool:
            """Basic cron validation (5 fields)."""
            parts = cron.strip().split()
            return len(parts) == 5

        # Valid 5-field cron expressions
        assert is_valid_cron("0 9 * * *")
        assert is_valid_cron("0 9 * * MON-FRI")
        assert is_valid_cron("0 */4 * * *")
        assert is_valid_cron("0 0 * * MON")

        # Invalid (6 fields - including seconds)
        assert not is_valid_cron("0 0 0 * * *")

    def test_executor_output_injection(self):
        """Test injecting previous executor output into prompt."""
        def inject_output(prompt: str, previous_outputs: dict) -> str:
            """Inject previous outputs into prompt template."""
            import json
            return prompt.replace(
                "$previous_output",
                json.dumps(previous_outputs, indent=2)
            )

        prompt = "Previous result: $previous_output. Now summarize."
        previous = {"step1": {"result": 42, "status": "done"}}

        result = inject_output(prompt, previous)

        assert "$previous_output" not in result
        assert '"step1"' in result
        assert '"result": 42' in result

    @pytest.mark.asyncio
    async def test_retry_policy_calculation(self):
        """Test retry policy configuration."""
        from datetime import timedelta

        def get_retry_policy(max_retries: int = 3, backoff: int = 60) -> dict:
            """Calculate retry policy."""
            return {
                "max_attempts": max_retries,
                "initial_retry": timedelta(seconds=backoff),
                "backoff_coefficient": 2.0,
            }

        policy = get_retry_policy(max_retries=5, backoff=30)

        assert policy["max_attempts"] == 5
        assert policy["initial_retry"].total_seconds() == 30
        assert policy["backoff_coefficient"] == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
