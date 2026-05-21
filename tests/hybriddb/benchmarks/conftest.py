"""conftest for HybridDB benchmarks — in-repo variant."""

import platform
from functools import lru_cache
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


@pytest.fixture(scope="session")
def embedding_fn():
    """Session-scoped SentenceTransformer model — loaded once, LRU-cached."""
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    @lru_cache(maxsize=50000)
    def _embed(text: str) -> list[float]:
        return model.encode(text).tolist()

    return _embed


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
        path = getattr(json_path, "name", json_path)
        if path and Path(path).exists():
            archive_results(path)


def pytest_benchmark_update_json(config, benchmarks, output_json):
    """Attach platform metadata to benchmark JSON for cross-machine comparison."""
    output_json["machine_info"] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
