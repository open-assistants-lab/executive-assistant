"""Shared helpers for HybridDB benchmarks: data generation, embedding cache, scale."""

import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from hybriddb import SearchMode  # noqa: F401 — re-exported for test files


class Scale(NamedTuple):
    n_docs: int
    n_graph_nodes: int
    n_graph_edges: int
    n_analytics_rows: int
    concurrent_duration_s: int


SMOKE = Scale(
    n_docs=100,
    n_graph_nodes=100,
    n_graph_edges=500,
    n_analytics_rows=1_000,
    concurrent_duration_s=2,
)

FULL = Scale(
    n_docs=100_000,
    n_graph_nodes=10_000,
    n_graph_edges=50_000,
    n_analytics_rows=1_000_000,
    concurrent_duration_s=30,
)

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"


def archive_results(json_path: str) -> Path:
    """Copy benchmark JSON to timestamped archive and update latest."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    githash = git_hash()
    archive_name = f"{timestamp}-{githash}.json"
    archive_path = RESULTS_DIR / archive_name
    latest_path = RESULTS_DIR / "latest.json"
    src = Path(json_path)
    if src.exists():
        import shutil
        shutil.copy2(src, archive_path)
        shutil.copy2(src, latest_path)
    return archive_path


def _random_title(rng: random.Random) -> str:
    adjectives = ["quick", "lazy", "happy", "sad", "bright", "dark", "fast", "slow"]
    nouns = ["fox", "dog", "cat", "bird", "fish", "tree", "car", "book"]
    return f"The {rng.choice(adjectives)} {rng.choice(nouns)}"


def _random_body(rng: random.Random, length: str = "medium") -> str:
    words = [
        "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
        "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
        "et", "dolore", "magna", "aliqua", "hello", "world", "test", "search",
        "hybrid", "vector", "keyword", "database", "performance", "benchmark",
    ]
    n_words = 50 if length == "medium" else 500
    return " ".join(rng.choice(words) for _ in range(n_words))


def generate_docs(
    n: int,
    columns: list[dict[str, str]],
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate n documents with specified column definitions.

    Each column dict: {"name": str, "type": "TEXT"|"LONGTEXT"}
    """
    rng = random.Random(seed)
    docs: list[dict[str, Any]] = []
    for i in range(n):
        doc: dict[str, Any] = {"id": str(i)}
        for col in columns:
            if col["type"] == "LONGTEXT":
                doc[col["name"]] = _random_body(rng, length="long")
            else:
                doc[col["name"]] = f"{_random_title(rng)} — doc {i}"
        docs.append(doc)
    return docs


def generate_analytics_data(
    n: int,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate analytics data with category columns and numeric measures."""
    rng = random.Random(seed)
    categories = ["A", "B", "C", "D", "E"]
    regions = ["NA", "EU", "APAC", "LATAM"]
    rows: list[dict[str, Any]] = []
    for i in range(n):
        rows.append({
            "id": i,
            "category": rng.choice(categories),
            "region": rng.choice(regions),
            "value": round(rng.uniform(10.0, 1000.0), 2),
            "quantity": rng.randint(1, 100),
            "timestamp": f"2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        })
    return rows


def generate_graph_data(
    n_nodes: int,
    n_edges: int,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate graph nodes and edges with random connectivity."""
    rng = random.Random(seed)
    node_types = ["person", "document", "event", "organization"]
    nodes = [
        {"id": f"n{i}", "type": rng.choice(node_types), "label": f"Node {i}"}
        for i in range(n_nodes)
    ]
    edges: list[dict[str, Any]] = []
    target_nodes = [n["id"] for n in nodes]
    for i in range(n_edges):
        source = rng.choice(target_nodes)
        target = rng.choice(target_nodes)
        if source == target:
            continue
        edges.append({
            "id": f"e{i}",
            "source_id": source,
            "target_id": target,
            "type": "related",
            "weight": round(rng.uniform(0.1, 1.0), 2),
        })
    return nodes, edges


def compute_recall(
    result_ids: list[str],
    expected_ids: set[str],
    k: int = 10,
) -> float:
    """Fraction of expected_ids found in top-k of result_ids."""
    if not expected_ids:
        return 1.0
    top_k = result_ids[:k]
    found = sum(1 for rid in top_k if rid in expected_ids)
    return found / len(expected_ids)
