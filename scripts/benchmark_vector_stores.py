#!/usr/bin/env python3
"""Benchmark DuckDB vs LanceDB vector store performance.

Tests:
1. Document insertion speed
2. Vector search speed
3. Hybrid search speed (if applicable)
4. Memory usage
5. Storage footprint
"""

import gc
import json
import shutil
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import torch


# =============================================================================
# Benchmark Data Classes
# =============================================================================

@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    db_type: str  # "duckdb" or "lancedb"
    test_name: str
    num_documents: int
    insert_time_sec: float
    insert_throughput_docs_sec: float
    avg_vector_search_time_ms: float
    avg_hybrid_search_time_ms: float | None
    storage_mb: float
    peak_memory_mb: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "db_type": self.db_type,
            "test_name": self.test_name,
            "num_documents": self.num_documents,
            "insert_time_sec": round(self.insert_time_sec, 3),
            "insert_throughput_docs_sec": round(self.insert_throughput_docs_sec, 2),
            "avg_vector_search_time_ms": round(self.avg_vector_search_time_ms, 3),
            "avg_hybrid_search_time_ms": round(self.avg_hybrid_search_time_ms, 3) if self.avg_hybrid_search_time_ms else None,
            "storage_mb": round(self.storage_mb, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
        }


# =============================================================================
# Test Data Generation
# =============================================================================

def generate_test_documents(num_docs: int) -> list[dict[str, Any]]:
    """Generate synthetic test documents.

    Args:
        num_docs: Number of documents to generate.

    Returns:
        List of document dicts with 'content' and 'metadata'.
    """
    topics = [
        "machine learning", "deep learning", "neural networks",
        "natural language processing", "computer vision",
        "reinforcement learning", "transformers", "attention mechanisms",
        "gradient descent", "backpropagation", "convolutional networks",
        "recurrent networks", "GANs", "autoencoders", "transfer learning"
    ]

    verbs = [
        "enables", "improves", "accelerates", "optimizes", "simplifies",
        "revolutionizes", "transforms", "enhances", "facilitates", "automates"
    ]

    applications = [
        "image classification", "text generation", "speech recognition",
        "recommendation systems", "fraud detection", "autonomous vehicles",
        "medical diagnosis", "language translation", "sentiment analysis"
    ]

    documents = []
    for i in range(num_docs):
        topic = topics[i % len(topics)]
        verb = verbs[i % len(verbs)]
        app = applications[i % len(applications)]

        content = f"{topic.capitalize()} {verb} {app}. This technique has shown remarkable results in recent research. "
        content += f"Researchers have demonstrated that {topic} can significantly improve performance on {app} tasks. "
        content += f"The key insight is that {verb} the underlying architecture leads to better generalization."

        documents.append({
            "content": content,
            "metadata": {
                "topic": topic,
                "application": app,
                "doc_id": i,
            }
        })

    return documents


# =============================================================================
# DuckDB Benchmark
# =============================================================================

def benchmark_duckdb(
    num_docs: int,
    collection_name: str = "benchmark",
    storage_dir: Path = None
) -> BenchmarkResult:
    """Benchmark DuckDB vector store.

    Args:
        num_docs: Number of documents to insert.
        collection_name: Name of the collection.
        storage_dir: Directory for storage (default: temp directory).

    Returns:
        BenchmarkResult with metrics.
    """
    import duckdb
    from cassey.storage.chunking import get_embeddings

    if storage_dir is None:
        storage_dir = Path("/tmp/vs_benchmark_duckdb")
    else:
        storage_dir = storage_dir / "duckdb"

    # Clean start
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    db_path = storage_dir / "vs.db"
    conn = duckdb.connect(str(db_path))

    # Load extensions
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")
    conn.execute("SET hnsw_enable_experimental_persistence=true;")
    conn.execute("INSTALL fts;")
    conn.execute("LOAD fts;")

    # Create tables
    docs_table = f'"{collection_name}_docs"'
    vectors_table = f'"{collection_name}_vectors"'

    conn.execute(f"""
        CREATE TABLE {docs_table} (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR,
            content TEXT,
            metadata JSON DEFAULT '{{}}',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.execute(f"""
        CREATE TABLE {vectors_table} (
            id VARCHAR PRIMARY KEY,
            embedding FLOAT[384],
            FOREIGN KEY (id) REFERENCES {docs_table}(id)
        );
    """)

    # Create HNSW index
    conn.execute(f'CREATE INDEX vss_idx ON {vectors_table} USING HNSW (embedding);')

    # Generate test data
    documents = generate_test_documents(num_docs)

    # Prepare documents for insertion (chunking)
    from cassey.storage.chunking import prepare_documents_for_vs
    chunks = prepare_documents_for_vs(documents, auto_chunk=True)

    # Start memory tracking
    tracemalloc.start()
    process = psutil.Process()

    # Benchmark insertion
    gc.collect()
    start_time = time.time()
    start_mem = process.memory_info().rss / 1024 / 1024  # MB

    # Generate embeddings and insert
    texts = [c.content for c in chunks]
    embeddings = get_embeddings(texts)

    import uuid
    for chunk, emb in zip(chunks, embeddings):
        doc_id = str(uuid.uuid4())
        conn.execute(
            f"INSERT INTO {docs_table} (id, document_id, content, metadata) VALUES (?, ?, ?, ?)",
            [doc_id, chunk.metadata.get("document_id", ""), chunk.content, json.dumps(chunk.metadata)]
        )
        conn.execute(
            f"INSERT INTO {vectors_table} (id, embedding) VALUES (?, ?)",
            [doc_id, emb]
        )

    # Create FTS index after insertion
    conn.execute(f'PRAGMA create_fts_index(\'{collection_name}_docs\', \'id\', \'content\')')

    end_time = time.time()
    end_mem = process.memory_info().rss / 1024 / 1024  # MB
    peak_mem = tracemalloc.get_traced_memory()[1] / 1024 / 1024  # MB
    tracemalloc.stop()

    insert_time = end_time - start_time
    insert_throughput = len(chunks) / insert_time

    # Benchmark vector search
    search_queries = ["machine learning", "neural networks", "computer vision"]
    vector_times = []

    for query in search_queries:
        start = time.time()
        query_vec = get_embeddings([query])[0]
        results = conn.execute(f"""
            SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[384]) as distance
            FROM {docs_table} d
            JOIN {vectors_table} v ON d.id = v.id
            ORDER BY distance
            LIMIT 5
        """, [query_vec]).fetchall()
        end = time.time()
        vector_times.append((end - start) * 1000)  # ms

    avg_vector_search_time = sum(vector_times) / len(vector_times)

    # Benchmark hybrid search
    hybrid_times = []
    for query in search_queries:
        start = time.time()
        query_vec = get_embeddings([query])[0]
        try:
            results = conn.execute(f"""
                SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[384]) as distance
                FROM {docs_table} d
                JOIN {vectors_table} v ON d.id = v.id
                WHERE fts_main_{collection_name}_docs.match_bm25(d.id, ?) IS NOT NULL
                ORDER BY distance
                LIMIT 5
            """, [query_vec, query]).fetchall()
        except Exception:
            # Fallback to LIKE if FTS fails
            results = conn.execute(f"""
                SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[384]) as distance
                FROM {docs_table} d
                JOIN {vectors_table} v ON d.id = v.id
                WHERE d.content LIKE ?
                ORDER BY distance
                LIMIT 5
            """, [query_vec, f"%{query}%"]).fetchall()
        end = time.time()
        hybrid_times.append((end - start) * 1000)  # ms

    avg_hybrid_search_time = sum(hybrid_times) / len(hybrid_times)

    conn.close()

    # Calculate storage size
    storage_mb = sum(f.stat().st_size for f in storage_dir.rglob('*') if f.is_file()) / 1024 / 1024

    return BenchmarkResult(
        db_type="duckdb",
        test_name=f"duckdb_{num_docs}_docs",
        num_documents=len(chunks),
        insert_time_sec=insert_time,
        insert_throughput_docs_sec=insert_throughput,
        avg_vector_search_time_ms=avg_vector_search_time,
        avg_hybrid_search_time_ms=avg_hybrid_search_time,
        storage_mb=storage_mb,
        peak_memory_mb=peak_mem,
    )


# =============================================================================
# LanceDB Benchmark
# =============================================================================

def benchmark_lancedb(
    num_docs: int,
    collection_name: str = "benchmark",
    storage_dir: Path = None
) -> BenchmarkResult:
    """Benchmark LanceDB vector store.

    Args:
        num_docs: Number of documents to insert.
        collection_name: Name of the collection.
        storage_dir: Directory for storage (default: temp directory).

    Returns:
        BenchmarkResult with metrics.
    """
    import lancedb
    import pyarrow as pa
    from cassey.storage.chunking import get_embeddings

    if storage_dir is None:
        storage_dir = Path("/tmp/vs_benchmark_lancedb")
    else:
        storage_dir = storage_dir / "lancedb"

    # Clean start
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    db_path = storage_dir / ".lancedb"
    db = lancedb.connect(str(db_path))

    # Generate test data
    documents = generate_test_documents(num_docs)

    # Prepare documents for insertion (chunking)
    from cassey.storage.chunking import prepare_documents_for_vs
    chunks = prepare_documents_for_vs(documents, auto_chunk=True)

    # Define schema
    dimension = 384
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("document_id", pa.string()),
        pa.field("content", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), dimension)),
    ])

    # Create table
    table = db.create_table(
        collection_name,
        schema=schema,
        mode="overwrite"
    )

    # Start memory tracking
    tracemalloc.start()
    process = psutil.Process()

    # Benchmark insertion
    gc.collect()
    start_time = time.time()
    start_mem = process.memory_info().rss / 1024 / 1024  # MB

    # Generate embeddings and insert
    texts = [c.content for c in chunks]
    embeddings = get_embeddings(texts)

    import uuid
    data = []
    for chunk, emb in zip(chunks, embeddings):
        data.append({
            "id": str(uuid.uuid4()),
            "document_id": chunk.metadata.get("document_id", ""),
            "content": chunk.content,
            "metadata": json.dumps(chunk.metadata),
            "vector": emb,
        })

    table.add(data)

    # Create vector index
    try:
        table.create_index(
            "vector",
            index_type="IVF_PQ",
            num_partitions=256,
            num_sub_vectors=dimension // 4
        )
    except Exception:
        pass  # Index might already exist

    end_time = time.time()
    end_mem = process.memory_info().rss / 1024 / 1024  # MB
    peak_mem = tracemalloc.get_traced_memory()[1] / 1024 / 1024  # MB
    tracemalloc.stop()

    insert_time = end_time - start_time
    insert_throughput = len(chunks) / insert_time

    # Benchmark vector search
    search_queries = ["machine learning", "neural networks", "computer vision"]
    vector_times = []

    for query in search_queries:
        start = time.time()
        query_vec = get_embeddings([query])[0]
        results = table.search(query_vec).limit(5).to_pandas()
        end = time.time()
        vector_times.append((end - start) * 1000)  # ms

    avg_vector_search_time = sum(vector_times) / len(vector_times)

    # LanceDB doesn't have native FTS, so hybrid = vector
    avg_hybrid_search_time = avg_vector_search_time

    # Calculate storage size
    storage_mb = sum(f.stat().st_size for f in storage_dir.rglob('*') if f.is_file()) / 1024 / 1024

    return BenchmarkResult(
        db_type="lancedb",
        test_name=f"lancedb_{num_docs}_docs",
        num_documents=len(chunks),
        insert_time_sec=insert_time,
        insert_throughput_docs_sec=insert_throughput,
        avg_vector_search_time_ms=avg_vector_search_time,
        avg_hybrid_search_time_ms=avg_hybrid_search_time,
        storage_mb=storage_mb,
        peak_memory_mb=peak_mem,
    )


# =============================================================================
# Comparison & Reporting
# =============================================================================

def format_markdown_report(results: list[BenchmarkResult], output_path: Path):
    """Generate a markdown report comparing results.

    Args:
        results: List of BenchmarkResult objects.
        output_path: Path to save the markdown report.
    """
    lines = []
    lines.append("# Vector Store Performance Benchmark: DuckDB vs LanceDB\n")
    lines.append(f"**Benchmark Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    # Group by document count
    doc_counts = sorted(set(r.num_documents for r in results))

    for num_docs in doc_counts:
        lines.append(f"\n## {num_docs} Documents\n")

        duckdb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "duckdb"]
        lancedb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "lancedb"]

        if not duckdb_results or not lancedb_results:
            continue

        duckdb = duckdb_results[0]
        lancedb = lancedb_results[0]

        # Comparison table
        lines.append("### Performance Comparison\n")
        lines.append("| Metric | DuckDB | LanceDB | Winner |")
        lines.append("|--------|--------|---------|--------|")

        # Insert throughput
        duckdb_insert = f"{duckdb.insert_throughput_docs_sec:.2f} docs/sec"
        lancedb_insert = f"{lancedb.insert_throughput_docs_sec:.2f} docs/sec"
        insert_winner = "DuckDB" if duckdb.insert_throughput_docs_sec > lancedb.insert_throughput_docs_sec else "LanceDB"
        lines.append(f"| Insert Throughput | {duckdb_insert} | {lancedb_insert} | **{insert_winner}** |")

        # Vector search time
        duckdb_search = f"{duckdb.avg_vector_search_time_ms:.3f} ms"
        lancedb_search = f"{lancedb.avg_vector_search_time_ms:.3f} ms"
        search_winner = "DuckDB" if duckdb.avg_vector_search_time_ms < lancedb.avg_vector_search_time_ms else "LanceDB"
        lines.append(f"| Vector Search (avg) | {duckdb_search} | {lancedb_search} | **{search_winner}** |")

        # Storage
        duckdb_storage = f"{duckdb.storage_mb:.2f} MB"
        lancedb_storage = f"{lancedb.storage_mb:.2f} MB"
        storage_winner = "DuckDB" if duckdb.storage_mb < lancedb.storage_mb else "LanceDB"
        lines.append(f"| Storage Size | {duckdb_storage} | {lancedb_storage} | **{storage_winner}** |")

        # Memory
        duckdb_mem = f"{duckdb.peak_memory_mb:.2f} MB"
        lancedb_mem = f"{lancedb.peak_memory_mb:.2f} MB"
        mem_winner = "DuckDB" if duckdb.peak_memory_mb < lancedb.peak_memory_mb else "LanceDB"
        lines.append(f"| Peak Memory | {duckdb_mem} | {lancedb_mem} | **{mem_winner}** |")

        lines.append("\n### Detailed Results\n")

        # DuckDB details
        lines.append("#### DuckDB\n")
        lines.append(f"- **Insert Time:** {duckdb.insert_time_sec:.3f} sec")
        lines.append(f"- **Throughput:** {duckdb.insert_throughput_docs_sec:.2f} docs/sec")
        lines.append(f"- **Vector Search:** {duckdb.avg_vector_search_time_ms:.3f} ms (average)")
        lines.append(f"- **Hybrid Search:** {duckdb.avg_hybrid_search_time_ms:.3f} ms (average)")
        lines.append(f"- **Storage:** {duckdb.storage_mb:.2f} MB")
        lines.append(f"- **Peak Memory:** {duckdb.peak_memory_mb:.2f} MB")

        lines.append("\n#### LanceDB\n")
        lines.append(f"- **Insert Time:** {lancedb.insert_time_sec:.3f} sec")
        lines.append(f"- **Throughput:** {lancedb.insert_throughput_docs_sec:.2f} docs/sec")
        lines.append(f"- **Vector Search:** {lancedb.avg_vector_search_time_ms:.3f} ms (average)")
        lines.append(f"- **Storage:** {lancedb.storage_mb:.2f} MB")
        lines.append(f"- **Peak Memory:** {lancedb.peak_memory_mb:.2f} MB")

        lines.append("\n---\n")

    # Summary
    lines.append("## Summary\n")

    # Overall winners
    duckdb_wins = 0
    lancedb_wins = 0

    for num_docs in doc_counts:
        duckdb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "duckdb"]
        lancedb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "lancedb"]

        if duckdb_results and lancedb_results:
            duckdb = duckdb_results[0]
            lancedb = lancedb_results[0]

            # Compare metrics (lower is better for search/time, higher for throughput)
            if duckdb.avg_vector_search_time_ms < lancedb.avg_vector_search_time_ms:
                duckdb_wins += 1
            else:
                lancedb_wins += 1

            if duckdb.insert_throughput_docs_sec > lancedb.insert_throughput_docs_sec:
                duckdb_wins += 1
            else:
                lancedb_wins += 1

    lines.append(f"- **DuckDB Wins:** {duckdb_wins} metrics")
    lines.append(f"- **LanceDB Wins:** {lancedb_wins} metrics")

    lines.append("\n### Key Findings\n")

    # Analyze results
    for num_docs in doc_counts:
        duckdb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "duckdb"]
        lancedb_results = [r for r in results if r.num_documents == num_docs and r.db_type == "lancedb"]

        if duckdb_results and lancedb_results:
            duckdb = duckdb_results[0]
            lancedb = lancedb_results[0]

            speedup = lancedb.avg_vector_search_time_ms / duckdb.avg_vector_search_time_ms if duckdb.avg_vector_search_time_ms > 0 else 0
            throughput_diff = (duckdb.insert_throughput_docs_sec / lancedb.insert_throughput_docs_sec * 100) if lancedb.insert_throughput_docs_sec > 0 else 0

            lines.append(f"\n#### {num_docs} Documents:\n")

            if speedup > 1:
                lines.append(f"- DuckDB is **{speedup:.2f}x faster** on vector search")
            elif speedup < 1:
                lines.append(f"- LanceDB is **{1/speedup:.2f}x faster** on vector search")

            if throughput_diff > 100:
                lines.append(f"- DuckDB has **{throughput_diff:.1f}%** higher insert throughput")
            elif throughput_diff < 100:
                lines.append(f"- LanceDB has **{100/throughput_diff:.1f}%** higher insert throughput")

            storage_diff = ((duckdb.storage_mb - lancedb.storage_mb) / duckdb.storage_mb * 100) if duckdb.storage_mb > 0 else 0
            if storage_diff > 0:
                lines.append(f"- LanceDB uses **{storage_diff:.1f}%** less storage")
            elif storage_diff < 0:
                lines.append(f"- DuckDB uses **{-storage_diff:.1f}%** less storage")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))

    print(f"\n✅ Markdown report saved to: {output_path}")


def save_json_results(results: list[BenchmarkResult], output_path: Path):
    """Save benchmark results to JSON.

    Args:
        results: List of BenchmarkResult objects.
        output_path: Path to save the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "results": [r.to_dict() for r in results],
    }

    output_path.write_text(json.dumps(data, indent=2))
    print(f"✅ JSON results saved to: {output_path}")


# =============================================================================
# Main Benchmark Runner
# =============================================================================

def run_all_benchmarks(
    document_counts: list[int] = [100, 500, 1000],
    output_dir: Path = Path("./scripts/benchmark_results")
) -> list[BenchmarkResult]:
    """Run benchmarks for both databases at multiple scales.

    Args:
        document_counts: List of document counts to test.
        output_dir: Directory to save results.

    Returns:
        List of BenchmarkResult objects.
    """
    all_results = []

    print("=" * 60)
    print("Vector Store Performance Benchmark")
    print("DuckDB vs LanceDB")
    print("=" * 60)

    for num_docs in document_counts:
        print(f"\n{'=' * 60}")
        print(f"Benchmarking with {num_docs} documents...")
        print(f"{'=' * 60}\n")

        # DuckDB
        print("🦆 DuckDB Benchmark...")
        try:
            duckdb_result = benchmark_duckdb(num_docs, storage_dir=output_dir)
            all_results.append(duckdb_result)
            print(f"  ✓ Insert: {duckdb_result.insert_throughput_docs_sec:.2f} docs/sec")
            print(f"  ✓ Vector Search: {duckdb_result.avg_vector_search_time_ms:.3f} ms")
            print(f"  ✓ Storage: {duckdb_result.storage_mb:.2f} MB")
        except Exception as e:
            print(f"  ✗ DuckDB failed: {e}")

        # LanceDB
        print("\n🏹 LanceDB Benchmark...")
        try:
            lancedb_result = benchmark_lancedb(num_docs, storage_dir=output_dir)
            all_results.append(lancedb_result)
            print(f"  ✓ Insert: {lancedb_result.insert_throughput_docs_sec:.2f} docs/sec")
            print(f"  ✓ Vector Search: {lancedb_result.avg_vector_search_time_ms:.3f} ms")
            print(f"  ✓ Storage: {lancedb_result.storage_mb:.2f} MB")
        except Exception as e:
            print(f"  ✗ LanceDB failed: {e}")

    # Save results
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    json_path = output_dir / f"vector_store_benchmark_{timestamp}.json"
    md_path = output_dir / f"vector_store_benchmark_{timestamp}.md"

    save_json_results(all_results, json_path)
    format_markdown_report(all_results, md_path)

    print("\n" + "=" * 60)
    print("Benchmark complete!")
    print("=" * 60)

    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark DuckDB vs LanceDB vector stores")
    parser.add_argument(
        "--documents",
        nargs="+",
        type=int,
        default=[100, 500, 1000],
        help="Document counts to benchmark (default: 100 500 1000)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./scripts/benchmark_results"),
        help="Output directory for results"
    )

    args = parser.parse_args()

    run_all_benchmarks(
        document_counts=args.documents,
        output_dir=args.output_dir
    )
