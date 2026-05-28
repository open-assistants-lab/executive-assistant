"""Tests for MemoryCore with ChromaBackend."""

from coremem.backends.chroma import ChromaBackend
from coremem.core import MemoryCore


def test_core_ingest_and_search(chroma_tmp_path, sample_messages):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest_many(sample_messages)
    assert core.count() == len(sample_messages)

    results = core.search("model kits", limit=10)
    assert len(results) > 0
    assert any("model" in r.memory.content.lower() for r in results)


def test_core_ingest_single(chroma_tmp_path):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    mid = core.ingest("user", "Hello world")
    assert mid
    assert core.count() == 1


def test_core_wake_up(chroma_tmp_path, sample_messages):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest_many(sample_messages)

    ctx = core.wake_up(user_id="alice")
    assert "[L0: Identity]" in ctx
    assert "alice" in ctx
    assert "[L1: Essential]" in ctx


def test_core_deep_search_context(chroma_tmp_path, sample_messages):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest_many(sample_messages)

    ctx = core.deep_search_context("model kits")
    assert ctx is not None
    assert "model kits" in ctx


def test_core_search_result_boosts_heuristics(chroma_tmp_path):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest("user", "I love building model kits. Finished a Revell F-15 Eagle.")
    core.ingest("user", "My favorite food is pizza.")

    results = core.search("how many model kits", limit=5)
    assert len(results) > 0

    model_result = next((r for r in results if "model" in r.memory.content.lower()), None)
    assert model_result is not None
    assert model_result.score > 0.0


def test_core_clear(chroma_tmp_path, sample_messages):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest_many(sample_messages)
    assert core.count() == len(sample_messages)
    core.clear()
    assert core.count() == 0


def test_model_kits_counting_scenario(chroma_tmp_path):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest("user", "I recently finished a Revell F-15 Eagle model kit")
    core.ingest("user", "Started a Tamiya 1/48 scale Spitfire Mk.V")
    core.ingest("user", "Just bought a 1/72 scale B-29 bomber")
    core.ingest("user", "Also got a 1/24 scale '69 Camaro kit")
    core.ingest("user", "My current project is a Tiger I tank")

    results = core.search("How many model kits have I worked on or bought?", limit=10)
    assert len(results) > 0

    kit_results = [r for r in results if "kit" in r.memory.content.lower()
                   or "spitfire" in r.memory.content.lower()
                   or "f-15" in r.memory.content.lower()
                   or "model" in r.memory.content.lower()]
    assert len(kit_results) >= 1


def test_knowledge_update_temporal(chroma_tmp_path):
    core = MemoryCore(backend=ChromaBackend(path=chroma_tmp_path))
    core.ingest("user", "I just ran a 5K in 30:00")
    core.ingest("user", "New personal best: 25:50 at the charity run")
    core.ingest("user", "My name is Alice")

    results = core.search("What is my current 5K time?", limit=5)
    assert len(results) > 0
    assert any("25:50" in r.memory.content for r in results)
