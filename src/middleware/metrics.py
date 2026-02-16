"""Middleware metrics collection and reporting.

Track:
- Token usage (before/after middleware)
- Memory hit rate
- Extraction accuracy
- Rate limit effectiveness
- Performance overhead

Usage:
    from src.middleware.metrics import MetricsCollector

    collector = MetricsCollector()

    # Record middleware execution
    collector.record_execution(
        middleware_name="memory_context",
        duration_ms=45.2,
        tokens_before=1000,
        tokens_after=1200,  # Context added tokens
    )

    # Get aggregated report
    report = collector.get_report()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from collections import defaultdict


@dataclass
class MiddlewareMetrics:
    """Metrics for a middleware instance.

    Tracks execution statistics and token usage.
    """

    name: str
    enabled: bool
    execution_count: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    last_execution: datetime | None = None
    token_usage: dict[str, float] = field(default_factory=dict)
    custom_metrics: dict[str, Any] = field(default_factory=dict)

    def record_execution(
        self,
        duration_ms: float,
        tokens_before: int | None = None,
        tokens_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Record a middleware execution.

        Args:
            duration_ms: Execution duration in milliseconds
            tokens_before: Token count before middleware (optional)
            tokens_after: Token count after middleware (optional)
            **kwargs: Custom metrics specific to middleware type
        """
        self.execution_count += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.execution_count
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.last_execution = datetime.now(timezone.utc)

        # Track token usage
        if tokens_before is not None:
            self.token_usage["before"] = self.token_usage.get("before", 0) + tokens_before
        if tokens_after is not None:
            self.token_usage["after"] = self.token_usage.get("after", 0) + tokens_after

        # Track custom metrics
        for key, value in kwargs.items():
            if key not in self.custom_metrics:
                self.custom_metrics[key] = []
            self.custom_metrics[key].append(value)


class MetricsCollector:
    """Collect and aggregate middleware metrics.

    Tracks performance and effectiveness across all middleware executions.

    Example:
        ```python
        collector = MetricsCollector()

        # Record execution
        collector.record_execution(
            "memory_context",
            duration_ms=45.2,
            tokens_before=1000,
            tokens_after=1200,
            memories_found=3,
        )

        # Get report
        report = collector.get_report()
        ```
    """

    def __init__(self) -> None:
        self._middlewares: dict[str, MiddlewareMetrics] = {}
        self._start_time: datetime = datetime.now(timezone.utc)

    def register_middleware(self, name: str, enabled: bool = True) -> MiddlewareMetrics:
        """Register a middleware for metrics collection.

        Args:
            name: Middleware name
            enabled: Whether middleware is enabled

        Returns:
            MiddlewareMetrics instance for the middleware
        """
        if name not in self._middlewares:
            self._middlewares[name] = MiddlewareMetrics(name=name, enabled=enabled)
        return self._middlewares[name]

    def record_execution(
        self,
        middleware_name: str,
        duration_ms: float,
        tokens_before: int | None = None,
        tokens_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Record a middleware execution.

        Args:
            middleware_name: Name of the middleware
            duration_ms: Execution duration in milliseconds
            tokens_before: Token count before middleware
            tokens_after: Token count after middleware
            **kwargs: Custom metrics (e.g., memories_found, summaries_created)
        """
        metrics = self._middlewares.get(middleware_name)
        if metrics is None:
            metrics = self.register_middleware(middleware_name)

        metrics.record_execution(
            duration_ms=duration_ms,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            **kwargs,
        )

    def get_middleware_metrics(self, middleware_name: str) -> MiddlewareMetrics | None:
        """Get metrics for a specific middleware.

        Args:
            middleware_name: Name of the middleware

        Returns:
            MiddlewareMetrics instance or None if not found
        """
        return self._middlewares.get(middleware_name)

    def get_report(self) -> dict[str, Any]:
        """Get aggregated metrics report.

        Returns:
            Dictionary with metrics for all middlewares and summary statistics
        """
        report: dict[str, Any] = {
            "collector_start_time": self._start_time.isoformat(),
            "collector_duration_seconds": (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds(),
            "middlewares": {},
            "summary": {
                "total_executions": sum(m.execution_count for m in self._middlewares.values()),
                "total_duration_ms": sum(m.total_duration_ms for m in self._middlewares.values()),
                "enabled_count": sum(1 for m in self._middlewares.values() if m.enabled),
            },
        }

        for name, metrics in self._middlewares.items():
            middleware_report = {
                "enabled": metrics.enabled,
                "execution_count": metrics.execution_count,
                "total_duration_ms": metrics.total_duration_ms,
                "avg_duration_ms": metrics.avg_duration_ms,
                "min_duration_ms": metrics.min_duration_ms,
                "max_duration_ms": metrics.max_duration_ms,
                "last_execution": (
                    metrics.last_execution.isoformat() if metrics.last_execution else None
                ),
                "token_usage": metrics.token_usage,
                "custom_metrics": self._aggregate_custom_metrics(metrics.custom_metrics),
            }

            # Calculate token delta if both before/after available
            if "before" in metrics.token_usage and "after" in metrics.token_usage:
                before_total = metrics.token_usage["before"]
                after_total = metrics.token_usage["after"]
                middleware_report["token_delta"] = after_total - before_total
                middleware_report["token_delta_percent"] = (
                    ((after_total - before_total) / before_total * 100) if before_total > 0 else 0
                )

            report["middlewares"][name] = middleware_report

        return report

    def _aggregate_custom_metrics(self, custom_metrics: dict[str, list]) -> dict[str, Any]:
        """Aggregate custom metrics (lists of values).

        Args:
            custom_metrics: Dict of metric name -> list of values

        Returns:
            Dict with aggregated values (min, max, avg, count)
        """
        aggregated = {}
        for key, values in custom_metrics.items():
            if not values:
                continue

            if isinstance(values, list) and len(values) > 0:
                try:
                    numeric_values = [float(v) for v in values if isinstance(v, (int, float))]
                    if numeric_values:
                        aggregated[key] = {
                            "count": len(numeric_values),
                            "min": min(numeric_values),
                            "max": max(numeric_values),
                            "avg": sum(numeric_values) / len(numeric_values),
                            "total": sum(numeric_values),
                        }
                except (ValueError, TypeError):
                    # Non-numeric metrics, just store count
                    aggregated[key] = {"count": len(values)}

        return aggregated

    def reset(self) -> None:
        """Reset all metrics."""
        self._middlewares.clear()
        self._start_time = datetime.now(timezone.utc)

    def get_effectiveness_metrics(self) -> dict[str, Any]:
        """Calculate effectiveness metrics from collected data.

        Returns:
            Dictionary with effectiveness metrics for each middleware
        """
        effectiveness = {}

        for name, metrics in self._middlewares.items():
            middleware_effectiveness = {}

            # Memory context effectiveness
            if name == "memory_context":
                # Memory hit rate from custom metrics
                if "memories_found" in metrics.custom_metrics:
                    found = metrics.custom_metrics["memories_found"]
                    if isinstance(found, list) and len(found) > 0:
                        avg_found = sum(found) / len(found)
                        middleware_effectiveness["avg_memories_found"] = avg_found

                # Token efficiency
                if "before" in metrics.token_usage and "after" in metrics.token_usage:
                    before = metrics.token_usage["before"]
                    after = metrics.token_usage["after"]
                    if before > 0:
                        # Lower ratio = better (less overhead)
                        overhead_ratio = (after - before) / before
                        middleware_effectiveness["token_overhead_ratio"] = overhead_ratio

            # Memory learning effectiveness
            if name == "memory_learning":
                # Extraction success rate
                if "memories_extracted" in metrics.custom_metrics:
                    extracted = metrics.custom_metrics["memories_extracted"]
                    if isinstance(extracted, list) and len(extracted) > 0:
                        avg_extracted = sum(extracted) / len(extracted)
                        middleware_effectiveness["avg_memories_extracted"] = avg_extracted

                # Confidence distribution
                if "extraction_confidence" in metrics.custom_metrics:
                    confidences = metrics.custom_metrics["extraction_confidence"]
                    if isinstance(confidences, list) and len(confidences) > 0:
                        avg_confidence = sum(confidences) / len(confidences)
                        middleware_effectiveness["avg_confidence"] = avg_confidence

            # Summarization effectiveness
            if name == "summarization":
                # Compression ratio
                if "compression_ratio" in metrics.custom_metrics:
                    ratios = metrics.custom_metrics["compression_ratio"]
                    if isinstance(ratios, list) and len(ratios) > 0:
                        avg_compression = sum(ratios) / len(ratios)
                        middleware_effectiveness["avg_compression_ratio"] = avg_compression

                # Information retention
                if "retention_rate" in metrics.custom_metrics:
                    rates = metrics.custom_metrics["retention_rate"]
                    if isinstance(rates, list) and len(rates) > 0:
                        avg_retention = sum(rates) / len(rates)
                        middleware_effectiveness["avg_retention_rate"] = avg_retention

            # Rate limit effectiveness
            if name == "rate_limit":
                # Block rate
                if "blocked" in metrics.custom_metrics:
                    blocked_list = metrics.custom_metrics["blocked"]
                    if isinstance(blocked_list, list):
                        total_requests = metrics.execution_count
                        blocked_count = sum(1 for b in blocked_list if b)
                        if total_requests > 0:
                            block_rate = blocked_count / total_requests
                            middleware_effectiveness["block_rate"] = block_rate

            # Performance metrics (all middlewares)
            if metrics.execution_count > 0:
                middleware_effectiveness["performance"] = {
                    "avg_duration_ms": metrics.avg_duration_ms,
                    "max_duration_ms": metrics.max_duration_ms,
                    "p95_duration_ms": self._calculate_percentile(
                        metrics.custom_metrics.get("durations", [])
                    ),
                }

            if middleware_effectiveness:
                effectiveness[name] = middleware_effectiveness

        return effectiveness

    def _calculate_percentile(self, values: list[float], percentile: float = 95) -> float:
        """Calculate percentile value from a list.

        Args:
            values: List of numeric values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]


# Global metrics collector instance
_global_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        MetricsCollector instance
    """
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector."""
    global _global_collector
    _global_collector = None
