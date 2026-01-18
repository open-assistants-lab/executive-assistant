"""Temporal health check module.

This module provides health check functions for Temporal server connectivity.
Two levels of checks are provided:
1. TCP check - lightweight, no SDK required
2. gRPC check - full SDK connection with namespace verification
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from cassey.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: Literal["healthy", "unhealthy", "degraded"]
    message: str
    details: dict | None = None
    latency_ms: float | None = None


async def check_tcp_connection(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 5.0,
) -> HealthCheckResult:
    """Check TCP connectivity to Temporal server (no SDK required).

    Args:
        host: Temporal server host (defaults to settings.TEMPORAL_HOST).
        port: Temporal server port (defaults to settings.TEMPORAL_PORT).
        timeout: Connection timeout in seconds.

    Returns:
        HealthCheckResult with status and details.
    """
    target_host = host or settings.TEMPORAL_HOST
    target_port = port or settings.TEMPORAL_PORT

    if not target_host:
        return HealthCheckResult(
            status="unhealthy",
            message="TEMPORAL_HOST not configured",
            details={"host": None, "port": target_port}
        )

    import time
    start_time = time.time()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target_host, target_port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()

        latency_ms = (time.time() - start_time) * 1000

        return HealthCheckResult(
            status="healthy",
            message=f"TCP connection to {target_host}:{target_port} successful",
            details={"host": target_host, "port": target_port},
            latency_ms=round(latency_ms, 2)
        )
    except ConnectionRefusedError:
        return HealthCheckResult(
            status="unhealthy",
            message=f"Connection refused to {target_host}:{target_port}",
            details={"host": target_host, "port": target_port, "error": "ConnectionRefusedError"}
        )
    except asyncio.TimeoutError:
        return HealthCheckResult(
            status="unhealthy",
            message=f"Connection timeout to {target_host}:{target_port}",
            details={"host": target_host, "port": target_port, "timeout": timeout, "error": "TimeoutError"}
        )
    except OSError as e:
        return HealthCheckResult(
            status="unhealthy",
            message=f"OS error connecting to {target_host}:{target_port}: {e}",
            details={"host": target_host, "port": target_port, "error": str(e)}
        )


async def check_grpc_connection(
    namespace: str | None = None,
) -> HealthCheckResult:
    """Check gRPC connectivity to Temporal server with SDK.

    Args:
        namespace: Temporal namespace (defaults to settings.TEMPORAL_NAMESPACE).

    Returns:
        HealthCheckResult with status and details.
    """
    if not settings.temporal_enabled:
        return HealthCheckResult(
            status="unhealthy",
            message="TEMPORAL_HOST not configured",
            details={"host": None, "enabled": False}
        )

    try:
        from temporalio.client import Client
    except ImportError:
        return HealthCheckResult(
            status="degraded",
            message="temporalio SDK not installed",
            details={"error": "ImportError: temporalio not found"}
        )

    target_namespace = namespace or settings.TEMPORAL_NAMESPACE

    import time
    start_time = time.time()

    try:
        client = await Client.connect(
            settings.temporal_target,
            namespace=target_namespace,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Verify we can access the workflow service
        workflow_service = client.workflow_service

        return HealthCheckResult(
            status="healthy",
            message=f"gRPC connection to {settings.temporal_target} successful (namespace: {target_namespace})",
            details={
                "host": settings.TEMPORAL_HOST,
                "port": settings.TEMPORAL_PORT,
                "namespace": target_namespace,
                "workflow_service_available": workflow_service is not None,
            },
            latency_ms=round(latency_ms, 2)
        )
    except RuntimeError as e:
        return HealthCheckResult(
            status="unhealthy",
            message=f"gRPC connection failed to {settings.temporal_target}",
            details={
                "host": settings.TEMPORAL_HOST,
                "port": settings.TEMPORAL_PORT,
                "namespace": target_namespace,
                "error": str(e)
            }
        )
    except Exception as e:
        return HealthCheckResult(
            status="unhealthy",
            message=f"Unexpected error connecting to Temporal: {e}",
            details={
                "host": settings.TEMPORAL_HOST,
                "port": settings.TEMPORAL_PORT,
                "namespace": target_namespace,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


async def check_temporal_health() -> dict:
    """Run all Temporal health checks and return combined result.

    Returns:
        Dictionary with overall health status and individual check results.
    """
    results = {
        "configured": settings.temporal_enabled,
        "target": settings.temporal_target if settings.temporal_enabled else None,
        "tcp": None,
        "grpc": None,
    }

    if not settings.temporal_enabled:
        return {
            "status": "unhealthy",
            "message": "Temporal is not configured",
            "results": results
        }

    # Run TCP check (always)
    tcp_result = await check_tcp_connection()
    results["tcp"] = {
        "status": tcp_result.status,
        "message": tcp_result.message,
        "latency_ms": tcp_result.latency_ms,
    }

    # Run gRPC check (requires SDK)
    grpc_result = await check_grpc_connection()
    results["grpc"] = {
        "status": grpc_result.status,
        "message": grpc_result.message,
        "latency_ms": grpc_result.latency_ms,
    }

    # Determine overall status
    if tcp_result.status == "healthy" and grpc_result.status == "healthy":
        overall_status = "healthy"
        overall_message = f"Temporal is healthy at {settings.temporal_target}"
    elif tcp_result.status == "healthy":
        overall_status = "degraded"
        overall_message = f"TCP OK but gRPC failed: {grpc_result.message}"
    else:
        overall_status = "unhealthy"
        overall_message = f"Cannot connect to Temporal: {tcp_result.message}"

    return {
        "status": overall_status,
        "message": overall_message,
        "results": results
    }


def format_health_result(result: dict) -> str:
    """Format health check result for display.

    Args:
        result: Result dict from check_temporal_health().

    Returns:
        Formatted string for logging or display.
    """
    lines = [
        f"Temporal Health: {result['status'].upper()}",
        f"  Message: {result['message']}",
    ]

    if result["results"]["tcp"]:
        tcp = result["results"]["tcp"]
        latency = f" ({tcp['latency_ms']}ms)" if tcp.get("latency_ms") else ""
        lines.append(f"  TCP: {tcp['status']}{latency} - {tcp['message']}")

    if result["results"]["grpc"]:
        grpc = result["results"]["grpc"]
        latency = f" ({grpc['latency_ms']}ms)" if grpc.get("latency_ms") else ""
        lines.append(f"  gRPC: {grpc['status']}{latency} - {grpc['message']}")

    return "\n".join(lines)


async def main() -> None:
    """CLI entry point for health checks."""
    import sys

    result = await check_temporal_health()
    print(format_health_result(result))

    # Exit with appropriate code
    if result["status"] == "healthy":
        sys.exit(0)
    elif result["status"] == "degraded":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
