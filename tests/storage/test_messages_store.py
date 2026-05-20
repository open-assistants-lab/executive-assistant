"""Tests for MessageStore."""

from __future__ import annotations

import tempfile
from datetime import UTC, date, datetime
from unittest import mock

from src.sdk.hybrid_db import HybridDB
from src.storage.messages import MessageStore


def _store() -> MessageStore:
    temp_dir = tempfile.TemporaryDirectory()
    store = MessageStore("test_user", base_dir=temp_dir.name)
    store._temp_dir = temp_dir
    return store


def test_get_messages_with_summary_respects_limit() -> None:
    store = _store()
    store.add_message("user", "before")
    store.add_summary_message("summary")
    for i in range(5):
        store.add_message("user", f"after-{i}")

    messages = store.get_messages_with_summary(limit=2)

    assert [m.content for m in messages] == ["summary", "after-4"]


def test_get_messages_with_summary_zero_limit_returns_empty() -> None:
    store = _store()
    store.add_summary_message("summary")

    assert store.get_messages_with_summary(limit=0) == []


def test_add_message_with_embedding_uses_supplied_embedding() -> None:
    store = _store()
    calls: list[str] = []

    def embedding_fn(text: str) -> list[float]:
        calls.append(text)
        return [0.0] * 384

    store.db._embedding_fn = embedding_fn

    store.add_message_with_embedding("user", "precomputed", [1.0] * 384)

    assert calls == []


def test_add_message_with_embedding_uses_public_hybriddb_hooks() -> None:
    store = _store()

    with (
        mock.patch.object(store.db, "vector_upsert", wraps=store.db.vector_upsert) as vector_upsert,
        mock.patch.object(store.db, "row_to_metadata", wraps=store.db.row_to_metadata) as row_to_metadata,
    ):
        store.add_message_with_embedding("user", "precomputed", [1.0] * 384)

    assert vector_upsert.called
    assert row_to_metadata.called


def test_search_hybrid_uses_supplied_query_embedding() -> None:
    store = _store()
    store.add_message_with_embedding("user", "precomputed", [1.0] * 384)
    calls: list[str] = []

    def embedding_fn(text: str) -> list[float]:
        calls.append(text)
        return [0.0] * 384

    store.db._embedding_fn = embedding_fn

    results = store.search_hybrid("precomputed", query_embedding=[1.0] * 384)

    assert results
    assert calls == []


def test_clear_removes_more_than_default_query_limit() -> None:
    store = _store()
    with store.db._connect() as cur:
        cur.execute("DELETE FROM messages")
        cur.execute(
            """
            WITH RECURSIVE cnt(x) AS (
                SELECT 1 UNION ALL SELECT x + 1 FROM cnt WHERE x < 100001
            )
            INSERT INTO messages (ts, role, content, metadata)
            SELECT '2026-01-01T00:00:00+00:00', 'user', 'm' || x, NULL FROM cnt
            """
        )

    store.clear()

    assert store.count_messages() == 0


def test_clear_refreshes_duckdb_without_reregistering_schema() -> None:
    store = _store()
    store.add_message("user", "hello")

    with (
        mock.patch.object(store.db, "register_duckdb_table", wraps=store.db.register_duckdb_table) as register,
        mock.patch.object(store.db, "sync_duckdb_table", wraps=store.db.sync_duckdb_table) as sync,
    ):
        store.clear()

    assert not register.called
    sync.assert_called_once_with("messages")


def test_message_table_has_chronological_indexes() -> None:
    store = _store()

    indexes = store.db.raw_query("PRAGMA index_list(messages)")
    names = {idx["name"] for idx in indexes}

    assert "idx_messages_ts" in names
    assert "idx_messages_role" in names


def test_message_store_initializes_when_duckdb_unavailable() -> None:
    def disable_duckdb(db: HybridDB) -> None:
        db._duckdb_path = ""
        db._duckdb_synced_tables = {}
        db._duckdb_conn = None

    with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
        HybridDB, "_init_duckdb", disable_duckdb
    ):
        store = MessageStore("test_user", base_dir=temp_dir)

        row_id = store.add_message("user", "hello")

    assert row_id > 0


def test_has_summary_uses_count_not_full_row_query() -> None:
    store = _store()
    store.add_summary_message("summary")

    with mock.patch.object(store.db, "query", wraps=store.db.query) as query:
        assert store.has_summary()

    assert not query.called


def test_search_hybrid_can_disable_recency_weight() -> None:
    store = _store()

    with mock.patch.object(store.db, "search", return_value=[]) as search:
        store.search_hybrid("topic", recency_weight=0.0)

    assert search.call_args.kwargs["recency_weight"] == 0.0


def test_date_filters_use_utc_bounds() -> None:
    store = _store()

    with mock.patch.object(store.db, "query", return_value=[]) as query:
        store.get_messages(start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))

    assert query.call_args.kwargs["params"] == (
        datetime.combine(date(2026, 5, 4), datetime.min.time(), tzinfo=UTC).isoformat(),
        datetime.combine(date(2026, 5, 5), datetime.max.time(), tzinfo=UTC).isoformat(),
    )
