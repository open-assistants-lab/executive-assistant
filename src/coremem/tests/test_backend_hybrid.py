"""Tests for HybridBackend."""

import os
import shutil

import pytest
from coremem.types import Memory, SearchQuery


def _make_backend(path: str):
    from coremem.backends.hybrid import HybridBackend

    return HybridBackend(path=path)


@pytest.fixture
def hybrid_be(hybrid_tmp_path):
    be = _make_backend(hybrid_tmp_path)
    yield be
    if os.path.exists(hybrid_tmp_path):
        shutil.rmtree(hybrid_tmp_path, ignore_errors=True)


def test_ingest_and_count(hybrid_be):
    hybrid_be.ingest(Memory(id="m1", content="Hello world", role="user"))
    hybrid_be.ingest(Memory(id="m2", content="I like pizza", role="user"))
    assert hybrid_be.count() == 2


def test_ingest_batch(hybrid_be):
    ids = hybrid_be.ingest_batch([
        Memory(id="", content="One", role="user"),
        Memory(id="", content="Two", role="user"),
        Memory(id="", content="Three", role="user"),
    ])
    assert len(ids) == 3
    assert hybrid_be.count() == 3
    assert ids[0] != ids[1]


def test_search_returns_results(hybrid_be):
    hybrid_be.ingest(Memory(id="m1", content="I love building model kits", role="user"))
    hybrid_be.ingest(Memory(id="m2", content="My favorite food is pizza", role="user"))

    results = hybrid_be.search(SearchQuery(text="model kits", limit=5))
    assert len(results) > 0
    assert any("model" in r.memory.content.lower() for r in results)


def test_search_session_dedup(hybrid_be):
    hybrid_be.ingest(Memory(id="m1", content="I love building model kits", role="user", session_id="A"))
    hybrid_be.ingest(Memory(id="m2", content="I built a Spitfire kit today", role="user", session_id="A"))
    hybrid_be.ingest(Memory(id="m3", content="I enjoy painting miniatures", role="user", session_id="B"))

    results = hybrid_be.search(SearchQuery(text="model kit hobby", limit=5))
    assert len(results) > 0

    sessions = [r.memory.session_id for r in results]
    assert len(set(sessions)) == len(sessions)


def test_get_recent(hybrid_be):
    for i in range(5):
        hybrid_be.ingest(Memory(id=f"m{i}", content=f"Memory {i}", role="user"))
    recent = hybrid_be.get_recent(limit=3)
    assert len(recent) <= 3


def test_clear(hybrid_be):
    hybrid_be.ingest(Memory(id="m1", content="test", role="user"))
    assert hybrid_be.count() == 1
    hybrid_be.clear()
    assert hybrid_be.count() == 0


def test_fts_keyword_search(hybrid_be):
    hybrid_be.ingest(Memory(id="m1", content="I built a Revell F-15 Eagle model", role="user"))
    hybrid_be.ingest(Memory(id="m2", content="I enjoy painting watercolors", role="user"))

    results = hybrid_be.search(SearchQuery(text="Revell F-15 Eagle", limit=5))
    assert len(results) > 0
    assert any("Revell" in r.memory.content for r in results)
