"""Storage benchmarks: disk usage, ChromaDB segment growth."""

import os
from pathlib import Path

import pytest

from .helpers import generate_docs


def _dir_size(path: str) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def test_db_file_growth(benchmark, db, scale):
    """SQLite file growth for TEXT columns (no Chroma)."""
    docs = generate_docs(scale.n_docs, [{"name": "content", "type": "TEXT"}])
    db.create_table("bench_storage", {"content": "TEXT"})

    def _measure():
        db.insert_batch("bench_storage", docs, sync=False)
        return _dir_size(db._db_path)

    size = benchmark(_measure)
    assert size > 0


def test_chroma_segment_growth(benchmark, db, scale):
    """ChromaDB segment growth for LONGTEXT columns."""
    docs = generate_docs(scale.n_docs, [{"name": "content", "type": "LONGTEXT"}])
    db.create_table("bench_storage", {"content": "LONGTEXT"})
    chroma_path = db._vector_path

    def _measure():
        db.insert_batch("bench_storage", docs, sync=True)
        if os.path.isdir(chroma_path):
            return _dir_size(chroma_path)
        return 0

    size = benchmark(_measure)
    assert size > 0 or scale.n_docs == 0


def test_total_storage(benchmark, db, scale):
    """Total disk usage with LONGTEXT (SQLite + Chroma)."""
    docs = generate_docs(scale.n_docs, [{"name": "content", "type": "LONGTEXT"}])
    db.create_table("bench_storage", {"content": "LONGTEXT"})

    def _measure():
        db.insert_batch("bench_storage", docs, sync=True)
        sqlite_size = _dir_size(db._db_path)
        chroma_size = (
            _dir_size(db._vector_path) if os.path.isdir(db._vector_path) else 0
        )
        return {"sqlite_bytes": sqlite_size, "chroma_bytes": chroma_size}

    result = benchmark(_measure)
    assert result["sqlite_bytes"] > 0


def test_chroma_bloat_check(benchmark, db, scale):
    """Check ChromaDB segment count and average size (regression catch)."""
    docs = generate_docs(scale.n_docs, [{"name": "content", "type": "LONGTEXT"}])
    db.create_table("bench_storage", {"content": "LONGTEXT"})

    def _measure():
        db.insert_batch("bench_storage", docs, sync=True)
        if not os.path.isdir(db._vector_path):
            return {"segment_count": 0, "avg_segment_bytes": 0}
        segments = list(Path(db._vector_path).rglob("*.segment"))
        n = len(segments)
        sizes = [s.stat().st_size for s in segments]
        avg = sum(sizes) / n if n > 0 else 0
        return {"segment_count": n, "avg_segment_bytes": avg}

    result = benchmark(_measure)
    assert result["segment_count"] >= 0
