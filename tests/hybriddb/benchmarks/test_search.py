"""Search benchmarks: keyword, vector, hybrid on TEXT and LONGTEXT columns."""

from typing import Any

import pytest

from .helpers import generate_docs, compute_recall


pytest.importorskip("sentence_transformers")

TEXT_COLUMNS = [{"name": "content", "type": "TEXT"}]
LONGTEXT_COLUMNS = [{"name": "content", "type": "LONGTEXT"}]


def _expected_ids_for_query(docs: list[dict[str, Any]], query: str) -> set[str]:
    """Return IDs of docs that contain the query keyword (for recall check)."""
    q = query.lower()
    return {d["id"] for d in docs if q in d.get("content", "").lower()}


def _insert_docs(db, table: str, docs: list[dict[str, Any]]):
    """Insert docs in batch using HybridDB insert_batch (sync True for Chroma)."""
    db.insert_batch(table, docs, sync=True)


def _prepare_text_db(db, scale, columns, table: str = "bench_search"):
    docs = generate_docs(scale.n_docs, columns)
    db.create_table(table, {c["name"]: c["type"] for c in columns})
    _insert_docs(db, table, docs)
    return docs


# ---- TEXT column benchmarks ----


def test_keyword_search_text(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, TEXT_COLUMNS)
    query = "hello"
    expected = _expected_ids_for_query(docs, query)

    def _search():
        return db.search("bench_search", query, search_type="keyword")

    result = benchmark(_search)
    recall = compute_recall([r["id"] for r in result], expected)
    assert recall >= 0.5 or not expected


def test_vector_search_text(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, TEXT_COLUMNS)
    query = "test search"

    def _search():
        return db.search("bench_search", query, search_type="vector")

    result = benchmark(_search)
    assert len(result) > 0


def test_hybrid_search_text(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, TEXT_COLUMNS)
    query = "hello world"

    def _search():
        return db.search("bench_search", query, search_type="hybrid")

    result = benchmark(_search)
    assert len(result) > 0


# ---- LONGTEXT column benchmarks ----


def test_keyword_search_longtext(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "hello"
    expected = _expected_ids_for_query(docs, query)

    def _search():
        return db.search("bench_search", query, search_type="keyword")

    result = benchmark(_search)
    recall = compute_recall([r["id"] for r in result], expected)
    assert recall >= 0.5 or not expected


def test_vector_search_longtext(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "search performance benchmark"

    def _search():
        return db.search("bench_search", query, search_type="vector")

    result = benchmark(_search)
    assert len(result) > 0


def test_hybrid_search_longtext(benchmark, db, scale):
    docs = _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "database benchmark"

    def _search():
        return db.search("bench_search", query, search_type="hybrid")

    result = benchmark(_search)
    assert len(result) > 0
