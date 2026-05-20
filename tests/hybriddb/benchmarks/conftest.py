"""conftest for HybridDB benchmarks — in-repo variant."""

from pathlib import Path

import pytest

from src.sdk.hybrid_db import HybridDB

from .helpers import FULL, SMOKE, Scale, archive_results


def pytest_addoption(parser):
    parser.addoption(
        "--benchmark-full",
        action="store_true",
        default=False,
        help="Run full-scale benchmarks (default: smoke)",
    )
    parser.addoption(
        "--precompute-embeddings",
        action="store_true",
        default=True,
        help="Pre-compute and cache embeddings (default: true)",
    )


@pytest.fixture(scope="session")
def embedding_fn():
    """Session-scoped SentenceTransformer model — loaded once."""
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return lambda text: model.encode(text).tolist()


@pytest.fixture
def scale(request) -> Scale:
    return FULL if request.config.getoption("--benchmark-full") else SMOKE


@pytest.fixture
def db(request, embedding_fn, tmp_path) -> HybridDB:
    h = HybridDB(
        path=str(tmp_path),
        embedding_fn=embedding_fn,
        embedding_model_name="all-MiniLM-L6-v2",
    )
    yield h
    try:
        h.close()
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    json_path = session.config.getoption("--benchmark-json")
    if json_path:
        archive_results(json_path)
