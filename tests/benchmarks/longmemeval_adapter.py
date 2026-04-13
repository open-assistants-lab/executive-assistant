"""LongMemEval benchmark adapter for Executive Assistant memory system.

Evaluates retrieval recall@k using ConversationStore (FTS5 + ChromaDB)
against the LongMemEval benchmark.

Usage:
    # Quick test on oracle (3 sessions per question):
    uv run python tests/benchmarks/longmemeval_adapter.py --mode retrieval --data data/longmemeval_oracle.json --max-instances 20

    # Full oracle:
    uv run python tests/benchmarks/longmemeval_adapter.py --mode retrieval --data data/longmemeval_oracle.json

    # Full S set (requires more time/memory):
    uv run python tests/benchmarks/longmemeval_adapter.py --mode retrieval --data data/longmemeval_s_cleaned.json --max-instances 100
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.storage.messages import ConversationStore
from src.tools.apps.storage import get_embedding as _get_embedding_func

_embedding_cache: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float]:
    if text not in _embedding_cache:
        _embedding_cache[text] = _get_embedding_func(text)
    return _embedding_cache[text]


def ingest_instance(store: ConversationStore, instance: dict) -> None:
    """Ingest a single LongMemEval instance's sessions into ConversationStore."""
    for session_id, session, date_str in zip(
        instance["haystack_session_ids"],
        instance["haystack_sessions"],
        instance["haystack_dates"],
    ):
        for turn_idx, turn in enumerate(session):
            role = turn["role"]
            content = turn["content"]
            metadata = {
                "session_id": session_id,
                "turn_idx": str(turn_idx),
                "has_answer": str(turn.get("has_answer", False)).lower(),
                "date": date_str,
                "question_id": instance["question_id"],
                "question_type": instance["question_type"],
            }
            emb = get_embedding(content)
            store.add_message_with_embedding(
                role=role,
                content=content,
                embedding=emb,
                metadata=metadata,
            )


def get_session_ids_for_messages(store: ConversationStore, msg_ids: list[int]) -> list[str]:
    """Batch look up session_ids from the messages DB by message IDs."""
    if not msg_ids:
        return []
    conn = sqlite3.connect(store.messages_db_path)
    placeholders = ",".join("?" * len(msg_ids))
    rows = conn.execute(
        f"SELECT id, metadata FROM messages WHERE id IN ({placeholders})", msg_ids
    ).fetchall()
    conn.close()
    id_to_sid = {}
    for row in rows:
        try:
            meta = json.loads(row[1]) if row[1] else {}
            id_to_sid[row[0]] = meta.get("session_id", "")
        except (json.JSONDecodeError, TypeError):
            id_to_sid[row[0]] = ""
    return [id_to_sid.get(mid, "") for mid in msg_ids]
    return ""


def compute_recall_at_k(
    ranked_session_ids: list[str],
    answer_session_ids: set[str],
    ks: list[int],
) -> dict[str, float]:
    """Compute recall@k metrics."""
    results = {}
    for k in ks:
        top_k = set(ranked_session_ids[:k])
        if not answer_session_ids:
            results[f"recall_any@{k}"] = 0.0
            results[f"recall_all@{k}"] = 0.0
        else:
            results[f"recall_any@{k}"] = float(bool(top_k & answer_session_ids))
            results[f"recall_all@{k}"] = float(top_k >= answer_session_ids)
    return results


def evaluate_instance(
    instance: dict,
    search_methods: list[str],
    ks: list[int],
) -> dict:
    """Evaluate retrieval for a single LongMemEval instance."""
    question_id = instance["question_id"]
    question_type = instance["question_type"]
    question = instance["question"]
    answer_session_ids = set(instance.get("answer_session_ids", []))

    tmpdir = tempfile.mkdtemp(prefix=f"longmemeval_{question_id}_")
    results = {"question_id": question_id, "question_type": question_type}

    try:
        store = ConversationStore.__new__(ConversationStore)
        store.user_id = f"bench_{question_id}"
        base_path = Path(tmpdir) / "messages"
        base_path.mkdir(parents=True, exist_ok=True)
        store.messages_db_path = str((base_path / "messages.db").resolve())
        store.vector_path = str((base_path / "vectors").resolve())
        store._init_messages_db()
        store._init_vector_store()

        ingest_instance(store, instance)

        question_emb = get_embedding(question)

        for method in search_methods:
            method_results = {}
            try:
                if method == "keyword":
                    search_results = store.search_keyword(question, limit=max(ks))
                elif method == "semantic":
                    search_results = store.search_vector(question_emb, limit=max(ks))
                elif method == "hybrid":
                    search_results = store.search_hybrid(question, question_emb, limit=max(ks))
                else:
                    continue
            except Exception as e:
                for k in ks:
                    method_results[f"recall_any@{k}"] = 0.0
                    method_results[f"recall_all@{k}"] = 0.0
                results[method] = method_results
                continue

            ranked_session_ids = []
            seen_sessions = set()
            msg_ids = [r.id for r in search_results]
            session_ids = get_session_ids_for_messages(store, msg_ids)
            for sid in session_ids:
                if sid and sid not in seen_sessions:
                    ranked_session_ids.append(sid)
                    seen_sessions.add(sid)

            method_results = compute_recall_at_k(ranked_session_ids, answer_session_ids, ks)
            results[method] = method_results

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    _embedding_cache.clear()

    return results


def run_benchmark(
    data_file: str,
    max_instances: int | None = None,
    search_methods: list[str] | None = None,
    ks: list[int] | None = None,
) -> dict:
    """Run full retrieval benchmark."""
    if search_methods is None:
        search_methods = ["keyword", "semantic", "hybrid"]
    if ks is None:
        ks = [1, 3, 5, 10, 20, 50]

    with open(data_file) as f:
        data = json.load(f)

    if max_instances:
        data = data[:max_instances]

    # Filter out abstention questions
    eval_data = [d for d in data if not d["question_id"].endswith("_abs")]

    all_results = []
    per_type_results: dict[str, list[dict]] = defaultdict(list)
    type_counts: dict[str, int] = defaultdict(int)

    print(f"Loaded {len(data)} instances ({len(eval_data)} non-abstention) from {data_file}")
    print(f"Search methods: {search_methods}")
    print(f"K values: {ks}")
    print()

    for i, instance in enumerate(eval_data):
        qid = instance["question_id"]
        qtype = instance["question_type"]
        n_sessions = len(instance["haystack_sessions"])

        print(f"  [{i + 1}/{len(eval_data)}] {qid} (type={qtype}, sessions={n_sessions})", end="")

        result = evaluate_instance(instance, search_methods, ks)
        all_results.append(result)
        per_type_results[qtype].append(result)
        type_counts[qtype] += 1

        scores = []
        for method in search_methods:
            if method in result:
                scores.append(f"{method}: R@5={result[method].get('recall_any@5', 'N/A')}")
        print(f" => {', '.join(scores)}")

    overall = aggregate_results(all_results, search_methods, ks)
    by_type = {
        qt: aggregate_results(results, search_methods, ks)
        for qt, results in per_type_results.items()
    }

    return {
        "overall": overall,
        "by_type": by_type,
        "instances": len(all_results),
        "type_counts": dict(type_counts),
        "per_instance": all_results,
    }


def aggregate_results(results: list[dict], methods: list[str], ks: list[int]) -> dict:
    """Aggregate results, computing mean recall per method@k."""
    aggregated = {}
    for method in methods:
        for k in ks:
            any_key = f"recall_any@{k}"
            all_key = f"recall_all@{k}"
            any_vals = [
                r[method][any_key] for r in results if method in r and any_key in r.get(method, {})
            ]
            all_vals = [
                r[method][all_key] for r in results if method in r and all_key in r.get(method, {})
            ]

            if any_vals:
                aggregated[f"{method}_recall_any@{k}"] = round(float(np.mean(any_vals)), 4)
                aggregated[f"{method}_recall_all@{k}"] = round(float(np.mean(all_vals)), 4)
                aggregated[f"{method}_count@{k}"] = len(any_vals)
    return aggregated


def print_results(results: dict, title: str = "LongMemEval Retrieval Baseline") -> None:
    """Pretty-print results in a table."""
    print(f"\n{'=' * 90}")
    print(f"  {title}")
    print(f"{'=' * 90}")
    print(f"  Instances: {results['instances']}")
    print(f"  Type counts: {results['type_counts']}")
    print()

    methods = sorted(
        set(
            k.rsplit("_recall", 1)[0]
            for k in results["overall"].keys()
            if "_recall_" in k or "_recall_any" in k
        )
    )

    print(f"  {'Method':<15}", end="")
    for k in [1, 3, 5, 10, 20, 50]:
        print(f" {'R@' + str(k):>8}", end="")
    print()
    print(f"  {'-' * 63}")

    overall = results["overall"]
    for method in methods:
        print(f"  {method:<15}", end="")
        for k in [1, 3, 5, 10, 20, 50]:
            key = f"{method}_recall_any@{k}"
            val = overall.get(key, None)
            print(f" {val:>8}" if val is not None else f" {'N/A':>8}", end="")
        print()

    by_type = results.get("by_type", {})
    if by_type:
        print()
        print("  Per-Type Results (Recall_any@5):")
        print(f"  {'Type':<30} {'Keyword':>10} {'Semantic':>10} {'Hybrid':>10}")
        print(f"  {'-' * 60}")
        for qtype in sorted(by_type.keys()):
            row = f"  {qtype:<30}"
            for method in methods:
                key = f"{method}_recall_any@5"
                val = by_type[qtype].get(key, None)
                row += f" {val:>10}" if val is not None else f" {'N/A':>10}"
            print(row)


def main():
    parser = argparse.ArgumentParser(description="LongMemEval Benchmark Adapter")
    parser.add_argument("--mode", choices=["retrieval"], default="retrieval")
    parser.add_argument("--data", type=str, default="data/longmemeval_oracle.json")
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument(
        "--methods",
        nargs="+",
        default=["keyword", "semantic", "hybrid"],
        choices=["keyword", "semantic", "hybrid"],
    )
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parents[2] / "LongMemEval"
    data_path = data_dir / args.data

    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}")
        sys.exit(1)

    results = run_benchmark(
        data_file=str(data_path),
        max_instances=args.max_instances,
        search_methods=args.methods,
    )

    print_results(results, f"LongMemEval Retrieval - {args.data}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
