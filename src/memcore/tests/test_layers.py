"""Tests for L0-L3 wake-up context stack."""

from memcore.backends.chroma import ChromaBackend
from memcore.types import Memory
from memcore.layers import WakeUpContext


def test_essential_builds_l0_l1(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="I live in Denver", role="user"))
    be.ingest(Memory(id="m2", content="I love model kits", role="user"))

    ctx = WakeUpContext(be)
    result = ctx.essential(user_id="alice")
    assert "[L0: Identity]" in result
    assert "alice" in result
    assert "[L1: Essential]" in result


def test_session_context_filters_by_session(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="Hello from sess A", role="user", session_id="A"))
    be.ingest(Memory(id="m2", content="Hello from sess B", role="user", session_id="B"))

    ctx = WakeUpContext(be)
    result = ctx.session(session_id="A")
    assert result is not None
    assert "[L2: On-Demand]" in result
    assert "A" in result
    assert "B" not in result


def test_session_returns_none_for_unknown(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    ctx = WakeUpContext(be)
    assert ctx.session(session_id="nonexistent") is None


def test_deep_search_formats_results(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    be.ingest(Memory(id="m1", content="I built a Spitfire model kit", role="user"))
    be.ingest(Memory(id="m2", content="I love pizza", role="user"))

    ctx = WakeUpContext(be)
    result = ctx.deep_search(query="model kits", limit=5)
    assert result is not None
    assert "[L3: Deep Search]" in result
    assert "model kits" in result


def test_deep_search_returns_none_for_empty(chroma_tmp_path):
    be = ChromaBackend(path=chroma_tmp_path)
    ctx = WakeUpContext(be)
    assert ctx.deep_search(query="nonexistent", limit=5) is None
