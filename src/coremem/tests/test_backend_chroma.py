"""Tests for ChromaBackend."""

from coremem.backends.chroma import ChromaBackend
from coremem.types import Memory, SearchQuery


def test_ingest_and_count(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="Hello world", role="user"))
    be.ingest(Memory(id="m2", content="I like pizza", role="user"))
    assert be.count() == 2


def test_search_returns_results(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="I love building model kits", role="user"))
    be.ingest(Memory(id="m2", content="My favorite food is pizza", role="user"))

    results = be.search(SearchQuery(text="model kits", limit=5))
    assert len(results) > 0
    assert any("model" in r.memory.content.lower() for r in results)


def test_search_filters_by_wing(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be._collection.add(
        ids=["m1"], documents=["I like chess"],
        metadatas=[{"wing": "hobbies", "room": "games", "role": "user"}],
    )
    be._collection.add(
        ids=["m2"], documents=["I enjoy painting"],
        metadatas=[{"wing": "arts", "room": "painting", "role": "user"}],
    )

    results = be.search(SearchQuery(text="hobby", limit=5, wing="hobbies"))
    assert len(results) > 0
    assert all("chess" in r.memory.content.lower() or "hobbies" in str(r.memory.session_id or "")
               for r in results)


def test_get_recent(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    for i in range(5):
        be.ingest(Memory(id=f"m{i}", content=f"Memory {i}", role="user"))
    recent = be.get_recent(limit=3)
    assert len(recent) <= 3


def test_clear(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="test", role="user"))
    assert be.count() == 1
    be.clear()
    assert be.count() == 0
