"""Search benchmarks: keyword, vector, hybrid on TEXT and LONGTEXT columns."""

import pytest

from .helpers import SearchMode, generate_docs

pytest.importorskip("sentence_transformers")

TEXT_COLUMNS = [{"name": "content", "type": "TEXT"}]
LONGTEXT_COLUMNS = [{"name": "content", "type": "LONGTEXT"}]


def _expected_ids_for_query(db, table: str, query: str) -> set[str]:
    """Return row IDs containing the query keyword via DB query (handles autoincrement mapping)."""
    q = query.lower()
    rows = db.raw_query(f"SELECT id, content FROM {table}")
    return {str(r["id"]) for r in rows if q in (r.get("content") or "").lower()}


def _insert_docs(db, table: str, docs: list[dict]):
    """Insert docs in batch using HybridDB insert_batch (sync True for Chroma)."""
    db.insert_batch(table, docs, sync=True)


def _prepare_text_db(db, scale, columns, table: str = "bench_search"):
    docs = generate_docs(scale.n_docs, columns)
    db.create_table(table, {c["name"]: c["type"] for c in columns})
    _insert_docs(db, table, docs)
    return docs


# ---- TEXT column benchmarks ----


def test_keyword_search_text(benchmark, db, scale):
    _prepare_text_db(db, scale, TEXT_COLUMNS)
    query = "fox"

    def _search():
        return db.search("bench_search", "content", query, mode=SearchMode.KEYWORD)

    result = benchmark(_search)
    assert len(result) > 0
    for r in result:
        assert r["_score"] < 0, "BM25 score should be negative"


def test_keyword_search_longtext(benchmark, db, scale):
    _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "hello"

    def _search():
        return db.search("bench_search", "content", query, mode=SearchMode.KEYWORD)

    result = benchmark(_search)
    assert len(result) > 0
    for r in result:
        assert r["_score"] < 0, "BM25 score should be negative"
    assert any("hello" in r.get("content", "").lower() for r in result), "Query term should appear in results"


def test_vector_search_longtext(benchmark, db, scale):
    _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "search performance benchmark"

    def _search():
        return db.search("bench_search", "content", query, mode=SearchMode.SEMANTIC)

    result = benchmark(_search)
    assert len(result) > 0
    for r in result:
        assert r["_search_mode"] == "semantic"


def test_hybrid_search_longtext(benchmark, db, scale):
    _prepare_text_db(db, scale, LONGTEXT_COLUMNS)
    query = "database benchmark"

    def _search():
        return db.search("bench_search", "content", query, mode=SearchMode.HYBRID)

    result = benchmark(_search)
    assert len(result) > 0
    for r in result:
        assert r["_search_mode"] == "hybrid"









