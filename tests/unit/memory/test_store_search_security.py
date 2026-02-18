from __future__ import annotations

from pathlib import Path

from src.memory import MemoryCreate, MemorySearchParams, MemoryStore, MemoryType


def test_search_project_filter_is_parameterized(tmp_path: Path) -> None:
    store = MemoryStore(user_id="test-user", data_path=tmp_path)
    try:
        store.add(
            MemoryCreate(
                title="Roadmap planning",
                type=MemoryType.CONTEXT,
                narrative="Planning notes for Q2",
                project="alpha",
            )
        )
        store.add(
            MemoryCreate(
                title="Budget review",
                type=MemoryType.CONTEXT,
                narrative="Budget notes for Q2",
                project="beta",
            )
        )

        injected_project = "alpha' OR 1=1 --"
        results = store.search(
            MemorySearchParams(
                project=injected_project,
                limit=20,
            )
        )

        assert results == []
    finally:
        store.close()


def test_search_handles_invalid_fts_query_without_crashing(tmp_path: Path) -> None:
    store = MemoryStore(user_id="test-user", data_path=tmp_path)
    try:
        store.add(
            MemoryCreate(
                title="Architecture decision",
                type=MemoryType.DECISION,
                narrative="Use PostgreSQL for checkpoints",
                project="core",
            )
        )

        # Invalid FTS syntax should not raise; fallback phrase search should handle it.
        results = store.search(
            MemorySearchParams(
                query='postgresql "unterminated',
                limit=20,
            )
        )

        assert isinstance(results, list)
    finally:
        store.close()
