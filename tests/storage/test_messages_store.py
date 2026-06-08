"""Tests for MessageStore (CoreMem adapter)."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from unittest import mock

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

    rid = store.add_message_with_embedding("user", "precomputed", [1.0] * 384)

    assert rid != ""
    messages = store.get_recent_messages(count=1)
    assert messages[0].content == "precomputed"


def test_add_message_with_embedding_bypasses_default_embedding() -> None:
    store = _store()
    calls: list[str] = []

    original_ingest = store._core.ingest

    def tracking_ingest(role, content, embedding=None, **kw):
        if embedding is not None:
            calls.append("custom_embedding_provided")
        return original_ingest(role, content, embedding=embedding, **kw)

    store._core.ingest = tracking_ingest

    store.add_message_with_embedding("user", "custom-vec", [0.5] * 384)

    assert "custom_embedding_provided" in calls


def test_search_hybrid_basic() -> None:
    store = _store()
    store.add_message("user", "I love building model kits")

    results = store.search_hybrid("model kits")

    assert len(results) > 0
    assert results[0].content == "I love building model kits"


def test_clear_removes_more_than_default_query_limit() -> None:
    store = _store()
    for i in range(100):
        store.add_message("user", f"msg-{i}")

    store.clear()

    assert store.count_messages() == 0


def test_clear_works_when_empty() -> None:
    store = _store()
    store.clear()
    assert store.count_messages() == 0


def test_message_table_has_chronological_indexes() -> None:
    store = _store()

    indexes = store._core._db.raw_query("PRAGMA index_list(messages)")
    names = {idx["name"] for idx in indexes}

    assert "idx_messages_ts" in names
    assert "idx_messages_role" in names


def test_message_store_initializes_when_duckdb_unavailable() -> None:
    from hybriddb import HybridDB

    def disable_duckdb(db):
        db._duckdb_path = ""
        db._duckdb_synced_tables = {}
        db._duckdb_conn = None

    with mock.patch.object(HybridDB, "_init_duckdb", disable_duckdb):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MessageStore("test_user", base_dir=temp_dir)
            row_id = store.add_message("user", "hello")

    assert row_id != ""


def test_has_summary_true() -> None:
    store = _store()
    store.add_summary_message("summary text")

    assert store.has_summary()


def test_has_summary_false_when_no_summary() -> None:
    store = _store()
    store.add_message("user", "no summary here")

    assert not store.has_summary()


def test_search_hybrid_returns_empty_for_empty_query() -> None:
    store = _store()
    store.add_message("user", "something")

    assert store.search_hybrid("") == []


def test_date_filters_work() -> None:
    store = _store()
    store.add_message("user", "message-1")
    messages = store.get_messages()
    assert len(messages) >= 1
    ts = messages[0].ts

    filtered = store.get_messages(start_date=ts.date())
    assert len(filtered) >= 1

    filtered = store.get_messages(end_date=ts.date())
    assert len(filtered) >= 1

    filtered = store.get_messages(start_date=ts.date() + timedelta(days=1))
    assert len(filtered) == 0
