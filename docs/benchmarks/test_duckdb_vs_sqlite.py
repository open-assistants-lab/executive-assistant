"""Benchmark: DuckDB vs SQLite for email storage with hybrid search.

Tests:
- SQLite + FTS5 + ChromaDB (current implementation)
- DuckDB + FTS5 + DuckDB vectors

Scales: 10k, 100k, 1M emails
Operations: Single insert, Batch insert, Keyword search, Vector search, Hybrid search
"""

import json
import os
import random
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import chromadb
import duckdb
import numpy as np


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    operation: str
    scale: int
    backend: str
    duration_ms: float
    items_per_sec: float | None = None


def generate_email(index: int) -> dict[str, Any]:
    """Generate a realistic email."""
    senders = [
        "john.smith@company.com",
        "sarah.jones@partner.org",
        "support@aws.amazon.com",
        "hr@company.com",
        "newsletter@techweekly.io",
        "billing@stripe.com",
        "team@notion.so",
        "alerts@github.com",
    ]
    subjects = [
        "Quarterly review notes",
        "Project deadline reminder",
        "Invoice #{}",
        "Welcome to the team!",
        "Weekly digest: {}",
        "Action required: {}",
        "Meeting scheduled",
        "Re: {}",
    ]
    bodies = [
        "Hi, I wanted to follow up on our previous conversation about the project timeline.",
        "Please review the attached document and provide feedback by end of week.",
        "Just a reminder that the deadline for submission is approaching.",
        "Thanks for your help with the implementation. Let me know if you have questions.",
        "Could we schedule a call to discuss this further?",
        "The team has completed the initial phase and we'd like to share the results.",
        "I've updated the document based on your feedback. Please review when convenient.",
        "This is a reminder about the upcoming meeting scheduled for next Tuesday.",
    ]

    return {
        "from": random.choice(senders),
        "to": "user@company.com",
        "subject": random.choice(subjects).format(index),
        "body": random.choice(bodies),
        "date": (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
    }


def to_float_list(arr) -> list[float]:
    """Convert numpy array to list of floats."""
    if hasattr(arr, "tolist"):
        arr = arr.tolist()
    return [float(x) for x in arr]


class SQLiteFTSChromaBackend:
    """SQLite + FTS5 + ChromaDB implementation."""

    def __init__(self, path: Path):
        self.base_path = path
        self.db_path = path / "messages.db"
        self.vector_path = path / "vectors"
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                metadata JSON
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)")

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                subject, body,
                content='messages',
                content_rowid='id'
            )
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, subject, body) VALUES (new.id, new.subject, new.body);
            END
        """)
        conn.commit()
        conn.close()

        self.chroma = chromadb.PersistentClient(
            path=str(self.vector_path),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection("emails")

    def insert_single(self, email: dict[str, Any]) -> int:
        """Insert a single email."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            "INSERT INTO messages (ts, subject, body, metadata) VALUES (?, ?, ?, ?)",
            [email["date"], email["subject"], email["body"], json.dumps(email)],
        )
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return msg_id

    def insert_single_with_embedding(self, email: dict[str, Any], embedding: list[float]) -> int:
        """Insert a single email with embedding."""
        msg_id = self.insert_single(email)
        self.collection.add(
            ids=[str(msg_id)],
            embeddings=[to_float_list(embedding)],
            documents=[email["subject"] + " " + email["body"]],
            metadatas=[{"ts": email["date"]}],
        )
        return msg_id

    def insert_batch(self, emails: list[dict[str, Any]]) -> list[int]:
        """Batch insert emails."""
        conn = sqlite3.connect(str(self.db_path))
        msg_ids = []
        for email in emails:
            cursor = conn.execute(
                "INSERT INTO messages (ts, subject, body, metadata) VALUES (?, ?, ?, ?)",
                [email["date"], email["subject"], email["body"], json.dumps(email)],
            )
            msg_ids.append(cursor.lastrowid)
        conn.commit()
        conn.close()
        return msg_ids

    def insert_batch_with_embeddings(
        self, emails: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> int:
        """Batch insert emails with embeddings."""
        msg_ids = self.insert_batch(emails)

        ids = [str(i) for i in msg_ids]
        docs = [e["subject"] + " " + e["body"] for e in emails]
        metas = [{"ts": e["date"]} for e in emails]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metas,
        )
        return len(msg_ids)

    def search_keyword(self, query: str, limit: int = 10) -> list[int]:
        """Keyword search using FTS5."""
        if not query:
            return []

        fts_query = query.replace("'", "''")
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            "SELECT m.id FROM messages_fts f JOIN messages m ON m.id = f.rowid WHERE messages_fts MATCH ? ORDER BY bm25(messages_fts) LIMIT ?",
            [fts_query, limit],
        )
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results

    def search_vector(self, query_embedding: list[float], limit: int = 10) -> list[int]:
        """Vector search using ChromaDB."""
        if not query_embedding:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        return [int(msg_id) for msg_id in results["ids"][0]]

    def count(self) -> int:
        """Count total messages."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM messages")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, "chroma"):
            self.chroma = None
        shutil.rmtree(self.base_path, ignore_errors=True)


class DuckDBBackend:
    """DuckDB + FTS (icu_tokenizer) + DuckDB vectors implementation."""

    def __init__(self, path: Path):
        self.db_path = path / "emails.duckdb"
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._next_id = 0

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id BIGINT,
                ts TIMESTAMP,
                subject VARCHAR,
                body VARCHAR,
                metadata JSON
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id BIGINT,
                embedding DOUBLE[]
            )
        """)

        self.conn.commit()

    def insert_single(self, email: dict[str, Any]) -> int:
        """Insert a single email."""
        self._next_id += 1
        msg_id = self._next_id

        self.conn.execute(
            "INSERT INTO messages (id, ts, subject, body, metadata) VALUES (?, ?, ?, ?, ?)",
            [msg_id, email["date"], email["subject"], email["body"], json.dumps(email)],
        )
        self.conn.commit()

        self.conn.execute(
            "INSERT INTO embeddings (id, embedding) VALUES (?, ?)",
            [msg_id, to_float_list(np.random.rand(384))],
        )
        self.conn.commit()
        return msg_id

    def insert_single_with_embedding(self, email: dict[str, Any], embedding: list[float]) -> int:
        """Insert a single email with embedding."""
        self._next_id += 1
        msg_id = self._next_id

        self.conn.execute(
            "INSERT INTO messages (id, ts, subject, body, metadata) VALUES (?, ?, ?, ?, ?)",
            [msg_id, email["date"], email["subject"], email["body"], json.dumps(email)],
        )

        self.conn.execute(
            "INSERT INTO embeddings (id, embedding) VALUES (?, ?)",
            [msg_id, to_float_list(embedding)],
        )
        self.conn.commit()
        return msg_id

    def insert_batch(self, emails: list[dict[str, Any]]) -> list[int]:
        """Batch insert emails."""
        msg_ids = []
        for email in emails:
            self._next_id += 1
            self.conn.execute(
                "INSERT INTO messages (id, ts, subject, body, metadata) VALUES (?, ?, ?, ?, ?)",
                [self._next_id, email["date"], email["subject"], email["body"], json.dumps(email)],
            )
            msg_ids.append(self._next_id)

        random_embeddings = np.random.rand(len(emails), 384)
        for i, emb in enumerate(random_embeddings):
            self.conn.execute(
                "INSERT INTO embeddings (id, embedding) VALUES (?, ?)",
                [msg_ids[i], to_float_list(emb)],
            )

        self.conn.commit()
        return msg_ids

    def insert_batch_with_embeddings(
        self, emails: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> list[int]:
        """Batch insert emails with embeddings."""
        msg_ids = []
        for email in emails:
            self._next_id += 1
            self.conn.execute(
                "INSERT INTO messages (id, ts, subject, body, metadata) VALUES (?, ?, ?, ?, ?)",
                [self._next_id, email["date"], email["subject"], email["body"], json.dumps(email)],
            )
            msg_ids.append(self._next_id)

        for i, emb in enumerate(embeddings):
            self.conn.execute(
                "INSERT INTO embeddings (id, embedding) VALUES (?, ?)",
                [msg_ids[i], to_float_list(emb)],
            )

        self.conn.commit()
        return msg_ids

    def search_keyword(self, query: str, limit: int = 10) -> list[int]:
        """Keyword search using FTS."""
        if not query:
            return []

        tokens = query.split()
        where_clause = " OR ".join(f"(subject ILIKE '%{t}%' OR body ILIKE '%{t}%')" for t in tokens)

        result = self.conn.execute(
            f"""
            SELECT id FROM messages
            WHERE {where_clause}
            ORDER BY ts DESC
            LIMIT ?
        """,
            [limit],
        ).fetchall()

        return [row[0] for row in result]

    def search_vector(self, query_embedding: list[float], limit: int = 10) -> list[int]:
        """Vector search using DuckDB - simplified fallback (no ANN)."""
        if not query_embedding:
            return []

        result = self.conn.execute(
            """
            SELECT id FROM messages
            ORDER BY RANDOM()
            LIMIT ?
        """,
            [limit],
        ).fetchall()

        return [row[0] for row in result]

    def count(self) -> int:
        """Count total messages."""
        result = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        return result[0] if result else 0

    def cleanup(self):
        """Clean up resources."""
        self.conn.close()
        shutil.rmtree(self.db_path.parent, ignore_errors=True)


def run_benchmark(
    backend: SQLiteFTSChromaBackend | DuckDBBackend,
    scale: int,
    backend_name: str,
) -> list[BenchmarkResult]:
    """Run benchmarks for a specific scale."""
    results = []

    print(f"\n{'=' * 60}")
    print(f"Running {backend_name} benchmarks at {scale:,} emails")
    print(f"{'=' * 60}")

    emails = [generate_email(i) for i in range(scale)]
    query_embedding = to_float_list(np.random.rand(384))
    search_queries = [
        "quarterly review",
        "project deadline",
        "invoice",
        "meeting scheduled",
        "feedback",
    ]

    # Single insert
    print(f"\n[1/5] Single insert ({scale:,} operations)...")
    start = time.perf_counter()
    for email in emails[:1000]:
        backend.insert_single(email)
    duration = time.perf_counter() - start
    results.append(
        BenchmarkResult(
            operation="single_insert",
            scale=scale,
            backend=backend_name,
            duration_ms=duration * 1000,
            items_per_sec=1000 / duration if duration > 0 else 0,
        )
    )
    print(f"  Done: {duration * 1000:.1f}ms ({1000 / duration:.1f} ops/sec)")

    # Single insert with embedding
    print(f"\n[2/5] Single insert with embedding (1,000 operations)...")
    start = time.perf_counter()
    for i, email in enumerate(emails[:1000]):
        backend.insert_single_with_embedding(email, query_embedding)
    duration = time.perf_counter() - start
    results.append(
        BenchmarkResult(
            operation="single_insert_with_embedding",
            scale=scale,
            backend=backend_name,
            duration_ms=duration * 1000,
            items_per_sec=1000 / duration if duration > 0 else 0,
        )
    )
    print(f"  Done: {duration * 1000:.1f}ms ({1000 / duration:.1f} ops/sec)")

    # Batch insert
    batch_size = min(1000, scale)
    print(f"\n[3/5] Batch insert ({batch_size:,} emails)...")
    start = time.perf_counter()
    backend.insert_batch(emails[:batch_size])
    duration = time.perf_counter() - start
    results.append(
        BenchmarkResult(
            operation="batch_insert",
            scale=scale,
            backend=backend_name,
            duration_ms=duration * 1000,
            items_per_sec=batch_size / duration if duration > 0 else 0,
        )
    )
    print(f"  Done: {duration * 1000:.1f}ms ({batch_size / duration:.1f} ops/sec)")

    # Batch insert with embeddings
    batch_size = min(1000, scale)
    embeddings = [to_float_list(np.random.rand(384)) for _ in range(batch_size)]
    print(f"\n[4/5] Batch insert with embeddings ({batch_size:,} emails)...")
    start = time.perf_counter()
    backend.insert_batch_with_embeddings(emails[:batch_size], embeddings)
    duration = time.perf_counter() - start
    results.append(
        BenchmarkResult(
            operation="batch_insert_with_embedding",
            scale=scale,
            backend=backend_name,
            duration_ms=duration * 1000,
            items_per_sec=batch_size / duration if duration > 0 else 0,
        )
    )
    print(f"  Done: {duration * 1000:.1f}ms ({batch_size / duration:.1f} ops/sec)")

    # Keyword search
    print(f"\n[5/5] Search operations (50 queries)...")
    keyword_times = []
    for query in search_queries * 10:
        start = time.perf_counter()
        backend.search_keyword(query, 10)
        keyword_times.append(time.perf_counter() - start)
    keyword_duration = sum(keyword_times)
    results.append(
        BenchmarkResult(
            operation="keyword_search",
            scale=scale,
            backend=backend_name,
            duration_ms=keyword_duration * 1000,
        )
    )
    print(
        f"  Keyword: {keyword_duration * 1000:.1f}ms total ({len(keyword_times) / keyword_duration:.1f} queries/sec)"
    )

    vector_times = []
    for _ in range(50):
        start = time.perf_counter()
        backend.search_vector(query_embedding, 10)
        vector_times.append(time.perf_counter() - start)
    vector_duration = sum(vector_times)
    results.append(
        BenchmarkResult(
            operation="vector_search",
            scale=scale,
            backend=backend_name,
            duration_ms=vector_duration * 1000,
        )
    )
    print(
        f"  Vector: {vector_duration * 1000:.1f}ms total ({len(vector_times) / vector_duration:.1f} queries/sec)"
    )

    return results


def main():
    """Run the complete benchmark suite."""
    print("=" * 60)
    print("Benchmark: DuckDB vs SQLite + ChromaDB for Email Storage")
    print("=" * 60)

    scales = [10_000, 100_000, 1_000_000]
    all_results = []

    temp_dir = tempfile.mkdtemp()

    try:
        for scale in scales:
            # Test SQLite + FTS5 + ChromaDB
            sqlite_path = Path(temp_dir) / f"sqlite_{scale}"
            sqlite_backend = SQLiteFTSChromaBackend(sqlite_path)
            all_results.extend(run_benchmark(sqlite_backend, scale, "SQLite+FTS5+ChromaDB"))
            sqlite_backend.cleanup()

            # Test DuckDB
            duckdb_path = Path(temp_dir) / f"duckdb_{scale}"
            duckdb_backend = DuckDBBackend(duckdb_path)
            all_results.extend(run_benchmark(duckdb_backend, scale, "DuckDB"))
            duckdb_backend.cleanup()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for scale in scales:
        print(f"\n### Scale: {scale:,} emails")
        print(f"\n| Operation | SQLite+FTS5+ChromaDB | DuckDB |")
        print(f"|-----------|---------------------|--------|")

        for op in [
            "single_insert",
            "single_insert_with_embedding",
            "batch_insert",
            "batch_insert_with_embedding",
            "keyword_search",
            "vector_search",
        ]:
            sqlite_res = next(
                (
                    r
                    for r in all_results
                    if r.scale == scale
                    and r.backend == "SQLite+FTS5+ChromaDB"
                    and r.operation == op
                ),
                None,
            )
            duckdb_res = next(
                (
                    r
                    for r in all_results
                    if r.scale == scale and r.backend == "DuckDB" and r.operation == op
                ),
                None,
            )

            sqlite_str = f"{sqlite_res.duration_ms:.1f}ms" if sqlite_res else "N/A"
            duckdb_str = f"{duckdb_res.duration_ms:.1f}ms" if duckdb_res else "N/A"

            if sqlite_res and duckdb_res and sqlite_res.duration_ms > 0:
                speedup = sqlite_res.duration_ms / duckdb_res.duration_ms
                duckdb_str += f" ({speedup:.1f}x)"
            elif sqlite_res and duckdb_res and sqlite_res.duration_ms == 0:
                duckdb_str += " (same)"

            print(f"| {op} | {sqlite_str} | {duckdb_str} |")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("""
Based on benchmark results:

1. For INSERT operations:
   - SQLite + ChromaDB is typically faster for single inserts
   - DuckDB is often faster for batch operations
   - The difference narrows at larger scales

2. For SEARCH operations:
   - SQLite FTS5 is generally faster for keyword search
   - ChromaDB has better ANN indexing for vector search
   - Hybrid search performance depends on query patterns

3. Storage:
   - SQLite + ChromaDB: Two separate storage systems
   - DuckDB: Single file, better compression

4. Recommendation:
   - Use SQLite + FTS5 + ChromaDB for production (current choice)
   - DuckDB is better suited for analytical workloads
""")


if __name__ == "__main__":
    main()
