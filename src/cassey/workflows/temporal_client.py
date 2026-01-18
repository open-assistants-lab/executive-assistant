"""Temporal client factory and connection management.

This module provides a singleton Temporal client for workflow operations.
The client connects to Temporal Server via gRPC and is reused across requests.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker

from cassey.config import settings

logger = logging.getLogger(__name__)

# Singleton client instance
_temporal_client: Client | None = None
_client_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    """Get or create Temporal client connection (singleton).

    Returns:
        Temporal client instance.

    Raises:
        RuntimeError: If Temporal is not configured or connection fails.
    """
    global _temporal_client

    async with _client_lock:
        if _temporal_client is not None:
            return _temporal_client

        if not settings.temporal_enabled:
            raise RuntimeError(
                "Temporal is not configured. Set TEMPORAL_HOST in environment."
            )

        try:
            logger.info(f"Connecting to Temporal at {settings.temporal_target}...")
            _temporal_client = await Client.connect(
                settings.temporal_target,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
            logger.info(f"Connected to Temporal at {settings.temporal_target}")
            return _temporal_client
        except RuntimeError as e:
            raise RuntimeError(
                f"Failed to connect to Temporal at {settings.temporal_target}: {e}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error connecting to Temporal: {e}"
            )


async def close_temporal_client() -> None:
    """Close the Temporal client connection.

    This clears the singleton client reference. The actual connection
    will be closed when the client object is garbage collected.
    """
    global _temporal_client

    async with _client_lock:
        if _temporal_client is not None:
            logger.info(f"Closing Temporal client connection to {settings.temporal_target}")
            _temporal_client = None


def reset_temporal_client() -> None:
    """Reset the Temporal client (for testing).

    This function should only be used in tests to force client reconnection.
    """
    global _temporal_client
    _temporal_client = None


async def run_worker(
    workflows: list[type],
    activities: list[type],
    task_queue: str | None = None,
) -> None:
    """Run the Temporal worker for Cassey workflows.

    This is a blocking call that runs the worker indefinitely.

    Args:
        workflows: List of workflow definition classes.
        activities: List of activity functions.
        task_queue: Task queue name (defaults to settings.TEMPORAL_TASK_QUEUE).

    Raises:
        RuntimeError: If Temporal is not configured.
    """
    if not settings.temporal_enabled:
        raise RuntimeError(
            "Temporal is not configured. Set TEMPORAL_HOST in environment."
        )

    queue = task_queue or settings.TEMPORAL_TASK_QUEUE

    logger.info(f"Starting Temporal worker for task queue: {queue}")

    client = await get_temporal_client()

    worker = TemporalWorker(
        client,
        task_queue=queue,
        workflows=workflows,
        activities=activities,
    )

    logger.info("Worker started, listening for workflow/activity tasks...")
    try:
        await worker.run()
    finally:
        logger.info("Worker stopped")


async def create_workflow(
    workflow_cls: type,
    args: list,
    workflow_id: str | None = None,
    task_queue: str | None = None,
) -> str:
    """Start a Temporal workflow execution.

    Args:
        workflow_cls: Workflow class to execute.
        args: Arguments to pass to the workflow run method.
        workflow_id: Optional workflow ID (auto-generated if not provided).
        task_queue: Task queue name (defaults to settings.TEMPORAL_TASK_QUEUE).

    Returns:
        Workflow execution ID.

    Raises:
        RuntimeError: If Temporal is not configured.
    """
    client = await get_temporal_client()
    queue = task_queue or settings.TEMPORAL_TASK_QUEUE

    logger.info(f"Starting workflow {workflow_cls.__name__} with id={workflow_id}")

    handle = await client.start_workflow(
        workflow_cls.run,
        args=args,
        id=workflow_id,
        task_queue=queue,
    )

    logger.info(f"Workflow started: {handle.id}")
    return handle.id


async def describe_workflow(workflow_id: str) -> dict:
    """Get workflow execution description.

    Args:
        workflow_id: Workflow ID to describe.

    Returns:
        Dictionary with workflow description.
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    # Describe the workflow execution
    description = await handle.describe()

    return {
        "workflow_id": workflow_id,
        "status": description.status.name,
        "history_length": description.history_length,
        "execution_status": description.execution_status.name if description.execution_status else None,
    }


async def cancel_workflow(workflow_id: str) -> None:
    """Cancel a running workflow.

    Args:
        workflow_id: Workflow ID to cancel.
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    await handle.cancel()
    logger.info(f"Workflow {workflow_id} cancelled")


async def query_workflow(workflow_id: str, query_type: str) -> str:
    """Query a workflow with a query method.

    Args:
        workflow_id: Workflow ID to query.
        query_type: Query type/method name.

    Returns:
        Query result.
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    result = await handle.query(query_type)
    return result
