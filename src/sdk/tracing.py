"""Structured tracing for the agent SDK.

Provides span-based tracing with pluggable processors.
Spans form a tree (via parent_id) and track timing + metadata for:
    - Agent runs
    - LLM calls
    - Tool executions
    - Handoffs
    - Guardrail checks
    - Middleware hooks
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class SpanType(StrEnum):
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_EXECUTION = "tool_execution"
    HANDOFF = "handoff"
    GUARDRAIL = "guardrail"
    MIDDLEWARE = "middleware"


class Span(BaseModel):
    """A single traced span within an agent execution."""

    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    type: SpanType
    name: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        start = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=UTC)
        end = self.ended_at if self.ended_at.tzinfo else self.ended_at.replace(tzinfo=UTC)
        delta = end - start
        return delta.total_seconds() * 1000

    def finish(self) -> Span:
        self.ended_at = datetime.now(UTC)
        return self


class SpanContext:
    """Context manager for an active span."""

    def __init__(self, span: Span, provider: TraceProvider) -> None:
        self.span = span
        self._provider = provider

    @property
    def ended_at(self) -> datetime | None:
        return self.span.ended_at

    @property
    def metadata(self) -> dict[str, Any]:
        return self.span.metadata

    async def __aenter__(self) -> SpanContext:
        await self._provider._on_span_start(self.span)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.span.finish()
        await self._provider._on_span_end(self.span)

    def set_meta(self, key: str, value: Any) -> None:
        self.span.metadata[key] = value


class TraceProcessor(ABC):
    """Base class for trace processors."""

    @abstractmethod
    async def on_span_start(self, span: Span) -> None: ...

    @abstractmethod
    async def on_span_end(self, span: Span) -> None: ...


class ConsoleTraceProcessor(TraceProcessor):
    """Prints span events to the console."""

    def __init__(self, indent: int = 2) -> None:
        self._indent = indent
        self._depth: dict[str, int] = {}

    async def on_span_start(self, span: Span) -> None:
        depth = 0
        if span.parent_id and span.parent_id in self._depth:
            depth = self._depth[span.parent_id] + 1
        self._depth[span.span_id] = depth
        prefix = " " * (depth * self._indent)
        print(f"{prefix}▶ [{span.type.value}] {span.name}")

    async def on_span_end(self, span: Span) -> None:
        depth = self._depth.get(span.span_id, 0)
        prefix = " " * (depth * self._indent)
        duration = f"{span.duration_ms:.1f}ms" if span.duration_ms is not None else "?"
        print(f"{prefix}◀ [{span.type.value}] {span.name} ({duration})")
        self._depth.pop(span.span_id, None)


class JsonTraceProcessor(TraceProcessor):
    """Writes span events to a JSONL file."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            from src.storage.paths import get_paths

            self._path = get_paths().traces_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def on_span_start(self, span: Span) -> None:
        pass

    async def on_span_end(self, span: Span) -> None:
        line = json.dumps(span.model_dump(), default=str) + "\n"
        self._path.write_text(self._path.read_text() + line if self._path.exists() else line)


class TraceProvider:
    """Central trace provider that dispatches to processors."""

    def __init__(self) -> None:
        self._processors: list[TraceProcessor] = []
        self._current_parent: str | None = None

    def add_processor(self, processor: TraceProcessor) -> None:
        self._processors.append(processor)

    def start_span_sync(
        self, type: SpanType, name: str, parent_id: str | None = None, **meta: Any
    ) -> Span:
        """Start a span synchronously (no context manager). Call end_span() to finish."""
        span = Span(
            type=type,
            name=name,
            parent_id=parent_id or self._current_parent,
            metadata=meta,
        )
        return span

    def end_span(self, span: Span) -> Span:
        """Finish a span started with start_span_sync."""
        span.finish()
        return span

    @asynccontextmanager
    async def start_span(
        self, type: SpanType, name: str, parent_id: str | None = None, **meta: Any
    ) -> AsyncIterator[SpanContext]:
        """Start a traced span as an async context manager."""
        span = Span(
            type=type,
            name=name,
            parent_id=parent_id or self._current_parent,
            metadata=meta,
        )
        old_parent = self._current_parent
        self._current_parent = span.span_id
        ctx = SpanContext(span, self)
        try:
            async with ctx:
                yield ctx
        finally:
            self._current_parent = old_parent

    async def _on_span_start(self, span: Span) -> None:
        for proc in self._processors:
            try:
                await proc.on_span_start(span)
            except Exception:
                pass

    async def _on_span_end(self, span: Span) -> None:
        for proc in self._processors:
            try:
                await proc.on_span_end(span)
            except Exception:
                pass
