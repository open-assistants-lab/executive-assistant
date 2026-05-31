"""Non-invasive performance instrumentation for the memory pipeline.

Wraps key methods with timing decorators without modifying source files.
Outputs structured JSONL timing data for analysis.

Usage:
    from tests.perf.perf_instrument import instrument_memory_pipeline, get_timings
    instrument_memory_pipeline()
    # ... run memory operations ...
    timings = get_timings()
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimingRecord:
    component: str
    operation: str
    start_ms: float
    elapsed_ms: float
    extra: dict[str, Any] = field(default_factory=dict)


_session_timings: list[TimingRecord] = []
_instrumented: set[str] = set()


def reset_timings() -> None:
    _session_timings.clear()


def get_timings() -> list[TimingRecord]:
    return list(_session_timings)


@contextmanager
def timed(component: str, operation: str, **extra: Any):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        elapsed_ms = elapsed * 1000
        _session_timings.append(
            TimingRecord(
                component=component,
                operation=operation,
                start_ms=start * 1000,
                elapsed_ms=elapsed_ms,
                extra=extra,
            )
        )


def wrap_method(obj: Any, method_name: str, component: str, operation: str | None = None):
    """Monkey-patch a method with timing instrumentation."""
    op = operation or method_name
    original = getattr(obj, method_name)

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            _session_timings.append(
                TimingRecord(
                    component=component,
                    operation=op,
                    start_ms=start * 1000,
                    elapsed_ms=elapsed * 1000,
                )
            )

    setattr(obj, method_name, _wrapped)


def instrument_memory_middleware(mw: Any) -> None:
    """Instrument MemoryMiddleware methods."""
    wrap_method(mw, "_get_relevant_memory_context", "middleware", "get_relevant_context")
    wrap_method(mw, "_get_baseline_memory_context", "middleware", "baseline_context")
    wrap_method(mw, "_get_planner_memory_context", "middleware", "planner_context")
    wrap_method(mw, "_get_ranked_memory_context", "middleware", "ranker_context")
    wrap_method(mw, "_should_extract", "middleware", "should_extract")


def instrument_memory_store(store: Any) -> None:
    """Instrument MemoryStore methods."""
    wrap_method(store, "search_hybrid", "store", "search_hybrid")
    wrap_method(store, "search_facts", "store", "search_facts")
    wrap_method(store, "find_facts_for_query", "store", "find_facts")
    wrap_method(store, "find_fact_history_for_query", "store", "find_fact_history")
    wrap_method(store, "get_memory_context", "store", "get_context")
    wrap_method(store, "list_memories", "store", "list_memories")
    wrap_method(store, "upsert_fact_memory", "store", "upsert_fact")
    wrap_method(store, "add_memory", "store", "add_memory")
    wrap_method(store, "search_all", "store", "search_all")


def instrument_hybrid_db(db: Any) -> None:
    """Instrument HybridDB search methods."""
    wrap_method(db, "search", "hybrid_db", "search")
    wrap_method(db, "search_all", "hybrid_db", "search_all")
    wrap_method(db, "_fts_search", "hybrid_db", "fts_search")
    wrap_method(db, "_vector_search", "hybrid_db", "vector_search")
    wrap_method(db, "_get_embedding", "hybrid_db", "get_embedding")
    wrap_method(db, "_process_journal", "hybrid_db", "process_journal")


def instrument_embedding() -> None:
    """Instrument the embedding generation function."""
    try:
        from src.sdk.tools_core import apps as apps_mod

        original = apps_mod.get_embedding

        def _timed_embedding(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                _session_timings.append(
                    TimingRecord(
                        component="embedding",
                        operation="encode",
                        start_ms=start * 1000,
                        elapsed_ms=elapsed * 1000,
                        extra={"text_len": len(str(args[0])) if args else 0},
                    )
                )

        apps_mod.get_embedding = _timed_embedding
        _instrumented.add("embedding")
    except Exception:
        pass


def instrument_all() -> None:
    """Instrument the full memory pipeline (non-invasive monkey-patching)."""
    reset_timings()

    instrument_embedding()

    try:
        from hybriddb import HybridDB

        _original_init = HybridDB.__init__

        def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
            _original_init(self, *args, **kwargs)
            key = str(self._db_path)
            if key not in _instrumented:
                instrument_hybrid_db(self)
                _instrumented.add(key)

        HybridDB.__init__ = _patched_init
    except Exception:
        pass

    try:
        from src.storage.memory import MemoryStore

        _orig_init = MemoryStore.__init__

        def _patched_memstore_init(self: Any, *args: Any, **kwargs: Any) -> None:
            _orig_init(self, *args, **kwargs)
            key = f"memstore:{self.user_id}"
            if key not in _instrumented:
                instrument_memory_store(self)
                _instrumented.add(key)

        MemoryStore.__init__ = _patched_memstore_init
    except Exception:
        pass

    try:
        from src.sdk.middleware_memory import MemoryMiddleware

        _orig_init = MemoryMiddleware.__init__

        def _patched_mw_init(self: Any, *args: Any, **kwargs: Any) -> None:
            _orig_init(self, *args, **kwargs)
            key = f"mw:{self.user_id}"
            if key not in _instrumented:
                instrument_memory_middleware(self)
                _instrumented.add(key)

        MemoryMiddleware.__init__ = _patched_mw_init
    except Exception:
        pass
