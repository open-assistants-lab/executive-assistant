"""LongMemEval R@k evaluation — tests retrieval pipeline in isolation.

Two metrics:
- Message R@k: answer in top-k individual messages (strict, current pipeline)
- Session R@k: answer anywhere in top-k sessions (broader, session-level context)

No HTTP API dependency. Creates temp HybridDB per question, searches via memcore.

Usage:
    uv run python tests/evaluation/longmemeval_retrieval.py --limit 20
    uv run python tests/evaluation/longmemeval_retrieval.py --full
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MEMORY_EXPANSION_MODEL", "")

try:
    from tests.evaluation.longmemeval_adapter import load_dataset
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from tests.evaluation.longmemeval_adapter import load_dataset


_PERSISTENT_TMP: str | None = None


def _reset_store(user_id: str):
    """Create or reset the persistent store for evaluation."""
    global _PERSISTENT_TMP
    from src.storage.messages import MessageStore, _stores
    from memcore.backends.hybrid import HybridBackend
    from memcore.core import MemoryCore
    from src.sdk.tools_core.message import _memcore_cache

    if _PERSISTENT_TMP is None:
        _PERSISTENT_TMP = tempfile.mkdtemp(prefix="lme_")
        store = MessageStore(user_id, base_dir=Path(_PERSISTENT_TMP))
        _stores[f"{user_id}:msgstore"] = store
        _memcore_cache[f"{user_id}:memcore"] = MemoryCore(backend=HybridBackend(path=_PERSISTENT_TMP))
    else:
        store = _stores.get(f"{user_id}:msgstore")
        with store.db._connect() as cur:
            for tbl in ("messages", "chroma_mappings", "duckdb_data"):
                try:
                    cur.execute(f"DELETE FROM {tbl}")
                except Exception:
                    pass
    return store


def _search_question(
    sessions: list[list[dict]],
    session_ids: list[str],
    question: str,
    k: int = 10,
) -> str:
    """Reuse persistent store, use real dataset session IDs."""
    uid = "lmeval"
    store = _reset_store(uid)

    for si, sesh in enumerate(sessions):
        sid = session_ids[si] if si < len(session_ids) else f"session_{si:04d}"
        for turn in sesh:
            if content := turn.get("content", ""):
                store.add_message(
                    turn.get("role", "user"), content.strip(),
                    metadata={"session_id": sid},
                )

    from src.sdk.tools_core.message import message_search as ms_tool
    return ms_tool.invoke({"query": question, "user_id": uid, "limit": k})


def _parse_session_ids(output: str) -> list[str]:
    """Extract session ID prefixes from message_search output."""
    import re as _re
    ids: list[str] = []
    for line in output.split("\n"):
        m = _re.match(r"── Session (\S{12,})\s*──", line)
        if m:
            ids.append(m.group(1))
    return ids


# ── Benchmark Runner ──────────────────────────────────────────────────────────

def run_single_question(
    q: dict[str, Any],
    idx: int,
    total: int,
    verbose: bool = False,
) -> dict[str, Any]:
    import math as _math

    question = q["question"]
    question_type = q["question_type"]
    haystack_sessions = q["haystack_sessions"]
    haystack_session_ids = q["haystack_session_ids"]
    answer_session_ids = q.get("answer_session_ids", [])
    question_id = q["question_id"]
    num_haystack = len(haystack_sessions)
    total_msgs = sum(1 for sesh in haystack_sessions for t in sesh if t.get("content", ""))
    num_answers = len(answer_session_ids)

    t0 = time.monotonic()
    if verbose:
        print(f"  [{idx}/{total}] {question_type}: {question[:60]}... ({num_haystack} sessions, {num_answers} answers)", flush=True)

    result = _search_question(haystack_sessions, haystack_session_ids, question, k=10)
    returned_ids = _parse_session_ids(result)

    def matches(returned_pref: str, answer_sid: str) -> bool:
        return answer_sid.startswith(returned_pref[:12]) or returned_pref.startswith(answer_sid[:12])

    # Which answer sessions are found in the top-k?
    found_at_5: list[str] = [a for a in answer_session_ids if any(matches(r, a) for r in returned_ids[:5])]
    found_at_10: list[str] = [a for a in answer_session_ids if any(matches(r, a) for r in returned_ids[:10])]

    # Find best rank of any answer session
    best_rank = 100
    for rank, rid in enumerate(returned_ids, 1):
        if any(matches(rid, a) for a in answer_session_ids):
            best_rank = rank
            break

    # Precision: % of top-k slots that are answer sessions (max 1 per slot)
    hits_at_5 = sum(1 for r in returned_ids[:5] for a in answer_session_ids if matches(r, a))
    hits_at_10 = sum(1 for r in returned_ids[:10] for a in answer_session_ids if matches(r, a))
    precision_5 = min(hits_at_5 / 5, 1.0) if returned_ids[:5] else 0.0
    precision_10 = min(hits_at_10 / 10, 1.0) if returned_ids[:10] else 0.0

    # Recall: % of answer sessions found in top-k
    recall_5 = len(found_at_5) / max(num_answers, 1)
    recall_10 = len(found_at_10) / max(num_answers, 1)
    recall_all = len(found_at_10) / max(num_answers, 1)  # alias for clarity

    # F1: harmonic mean of precision + recall
    def f1(p: float, r: float) -> float:
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

    f1_5 = f1(precision_5, recall_5)
    f1_10 = f1(precision_10, recall_10)

    # Legacy binary metrics (any answer in top-k)
    ses_r5 = best_rank <= 5
    ses_r10 = best_rank <= 10
    mrr = 1.0 / best_rank if best_rank <= 100 else 0.0
    ndcg_5 = 1.0 / (_math.log2(best_rank + 1)) if best_rank <= 5 else 0.0
    ndcg_10 = 1.0 / (_math.log2(best_rank + 1)) if best_rank <= 10 else 0.0

    duration = time.monotonic() - t0

    if verbose:
        def fmt(c): return "✅" if c else "❌"
        pool_size = max(len(returned_ids) if not returned_ids else 10, 10) * _get_multiplier()
        selectivity = pool_size / max(total_msgs, 1) * 100
        p5_str = f"P@5={precision_5:.2f}" if precision_5 < 1 else "P@5=1.0"
        r5_str = f"R@5={recall_5:.2f}" if recall_5 < 1 else "R@5=1.0"
        f1_str = f"F1@5={f1_5:.2f}" if f1_5 < 1 else "F1@5=1.0"
        print(f"    rank=#{best_rank if best_rank <= 100 else '∞'} | {p5_str} {r5_str} | "
              f"pool={pool_size}/{total_msgs}msgs ({selectivity:.0f}%) | "
              f"{duration:.1f}s", flush=True)

    return {
        "question_id": question_id,
        "question_type": question_type,
        "question": question,
        "best_rank": best_rank,
        "total_msgs": total_msgs,
        "num_haystack_sessions": num_haystack,
        "num_answers": num_answers,
        "num_returned": len(returned_ids),
        "found_at_5": len(found_at_5),
        "found_at_10": len(found_at_10),
        "ses_r@5": ses_r5,
        "ses_r@10": ses_r10,
        "mrr": mrr,
        "ndcg@5": ndcg_5,
        "ndcg@10": ndcg_10,
        "precision@5": precision_5,
        "precision@10": precision_10,
        "recall@5": recall_5,
        "recall@10": recall_10,
        "recall_all": recall_all,
        "f1@5": f1_5,
        "f1@10": f1_10,
        "duration_s": round(duration, 1),
    }


def run_benchmark(
    questions: list[dict[str, Any]],
    question_types: list[str] | None = None,
    limit: int | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    if question_types:
        questions = [q for q in questions if q["question_type"] in question_types]
    if limit and not question_types:
        # Evenly distribute limit across all question types
        by_type: dict[str, list[dict]] = defaultdict(list)
        for q in questions:
            by_type[q["question_type"]].append(q)
        types = sorted(by_type.keys())
        per_type = max(1, limit // len(types))
        remainder = limit - per_type * len(types)
        sampled: list[dict] = []
        for i, t in enumerate(types):
            n = per_type + (1 if i < remainder else 0)
            sampled.extend(by_type[t][:n])
        questions = sampled
    elif limit:
        questions = questions[:limit]

    total = len(questions)
    print(f"\nRunning LongMemEval R@k: {total} questions\n")

    results: list[dict] = []
    for i, q in enumerate(questions):
        result = run_single_question(q, i + 1, total, verbose=verbose)
        results.append(result)

    return _compute_metrics(results, total)


def _get_multiplier() -> int:
    from src.sdk.tools_core.message import _SEARCH_DEPTH_MULTIPLIER
    return _SEARCH_DEPTH_MULTIPLIER


def _compute_metrics(results: list[dict], total: int) -> dict[str, Any]:
    ses_r5 = sum(1 for r in results if r["ses_r@5"])
    ses_r10 = sum(1 for r in results if r["ses_r@10"])
    mrr = sum(r.get("mrr", 0) for r in results) / max(len(results), 1)
    ndcg_5 = sum(r.get("ndcg@5", 0) for r in results) / max(len(results), 1)
    ndcg_10 = sum(r.get("ndcg@10", 0) for r in results) / max(len(results), 1)

    precision_5 = sum(r.get("precision@5", 0) for r in results) / max(len(results), 1)
    precision_10 = sum(r.get("precision@10", 0) for r in results) / max(len(results), 1)
    recall_5 = sum(r.get("recall@5", 0) for r in results) / max(len(results), 1)
    recall_10 = sum(r.get("recall@10", 0) for r in results) / max(len(results), 1)
    recall_all = sum(r.get("recall_all", 0) for r in results) / max(len(results), 1)
    f1_5 = sum(r.get("f1@5", 0) for r in results) / max(len(results), 1)
    f1_10 = sum(r.get("f1@10", 0) for r in results) / max(len(results), 1)

    ranks = [r["best_rank"] for r in results if r["best_rank"] <= 100]
    mean_rank = sum(ranks) / len(ranks) if ranks else 0
    rank_dist: dict[str, int] = {"1": 0, "2-3": 0, "4-5": 0, "6-10": 0, ">10": 0}
    for rk in ranks:
        if rk == 1: rank_dist["1"] += 1
        elif rk <= 3: rank_dist["2-3"] += 1
        elif rk <= 5: rank_dist["4-5"] += 1
        elif rk <= 10: rank_dist["6-10"] += 1
        else: rank_dist[">10"] += 1

    pool_sizes = [max(r.get("num_returned", 1), 10) * _get_multiplier() for r in results]
    total_msgs = [r.get("total_msgs", 1) for r in results]
    selectivity = (sum(pool_sizes) / sum(total_msgs) * 100) if sum(total_msgs) else 0

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_type[r["question_type"]].append(r)

    type_metrics = {}
    for qt, items in sorted(by_type.items()):
        n = len(items)
        t_mrr = sum(it.get("mrr", 0) for it in items) / max(n, 1)
        t_prec5 = sum(it.get("precision@5", 0) for it in items) / max(n, 1)
        t_recl5 = sum(it.get("recall@5", 0) for it in items) / max(n, 1)
        t_recl_all = sum(it.get("recall_all", 0) for it in items) / max(n, 1)
        t_f1_5 = sum(it.get("f1@5", 0) for it in items) / max(n, 1)
        type_metrics[qt] = {
            "total": n,
            "ses_r@5": {"correct": sum(1 for it in items if it["ses_r@5"]), "accuracy": round(sum(1 for it in items if it["ses_r@5"]) / n * 100, 1) if n else 0},
            "ses_r@10": {"correct": sum(1 for it in items if it["ses_r@10"]), "accuracy": round(sum(1 for it in items if it["ses_r@10"]) / n * 100, 1) if n else 0},
            "mrr": round(t_mrr, 3),
            "precision@5": round(t_prec5, 3),
            "recall_all": round(t_recl_all, 3),
            "f1@5": round(t_f1_5, 3),
        }

    durations = sorted(r["duration_s"] for r in results)

    return {
        "overall": {
            "ses_r@5": {"correct": ses_r5, "total": total, "accuracy": round(ses_r5 / total * 100, 1) if total else 0},
            "ses_r@10": {"correct": ses_r10, "total": total, "accuracy": round(ses_r10 / total * 100, 1) if total else 0},
            "mrr": round(mrr, 3),
            "ndcg@5": round(ndcg_5, 3),
            "ndcg@10": round(ndcg_10, 3),
            "mean_rank": round(mean_rank, 1),
            "rank_distribution": rank_dist,
            "selectivity": round(selectivity, 1),
            "precision@5": round(precision_5, 3),
            "recall_all": round(recall_all, 3),
            "f1@5": round(f1_5, 3),
        },
        "by_type": type_metrics,
        "timing": {"avg_s": round(sum(durations) / len(durations), 1) if durations else 0, "p50_s": durations[len(durations) // 2] if durations else 0},
        "results": results,
    }


def print_report(metrics: dict[str, Any]) -> None:
    o = metrics["overall"]
    mult = _get_multiplier()

    print(f"\n{'='*60}")
    print(f"LongMemEval R@k Results — Retrieval Pipeline (×{mult})")
    print(f"{'='*60}")
    print(f"Session R@5:  {o['ses_r@5']['correct']}/{o['ses_r@5']['total']} = {o['ses_r@5']['accuracy']}%")
    print(f"Session R@10: {o['ses_r@10']['correct']}/{o['ses_r@10']['total']} = {o['ses_r@10']['accuracy']}%")
    print(f"MRR: {o['mrr']}  NDCG@5: {o['ndcg@5']}  NDCG@10: {o['ndcg@10']}  Mean rank: {o['mean_rank']}")
    print(f"P@5: {o['precision@5']}  R_all: {o['recall_all']}  F1@5: {o['f1@5']}  Selectivity: {o['selectivity']}%")
    print(f"Rank dist: #1={o['rank_distribution'].get('1',0)} #2-3={o['rank_distribution'].get('2-3',0)} #4-5={o['rank_distribution'].get('4-5',0)} #6-10={o['rank_distribution'].get('6-10',0)} >10={o['rank_distribution'].get('>10',0)}")

    print(f"\nBy question type:")
    print(f"  {'Type':<23s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s} {'P@5':>6s} {'R_all':>6s} {'F1@5':>6s}")
    print(f"  {'-'*23} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for qt, tm in sorted(metrics["by_type"].items()):
        print(f"  {qt:<23s} {tm['ses_r@5']['accuracy']:>5.0f}% {tm['ses_r@10']['accuracy']:>5.0f}% {tm['mrr']:>5.3f} {tm['precision@5']:>5.3f} {tm['recall_all']:>5.3f} {tm['f1@5']:>5.3f}")

    output_path = Path(f"data/evaluations/longmemeval_rk_{time.strftime('%Y%m%d_%H%M%S')}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="LongMemEval R@k for EA")
    parser.add_argument("--limit", type=int, default=None, help="Max questions")
    parser.add_argument("--depth-multiplier", type=int, default=None, help="Override _SEARCH_DEPTH_MULTIPLIER")
    parser.add_argument("--question-types", nargs="*", default=None, choices=[
        "single-session-user", "single-session-assistant",
        "single-session-preference", "multi-session",
        "knowledge-update", "temporal-reasoning",
    ])
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    if args.depth_multiplier is not None:
        import src.sdk.tools_core.message as msg_mod
        msg_mod._SEARCH_DEPTH_MULTIPLIER = args.depth_multiplier

    if args.full:
        args.limit = None

    questions = load_dataset()
    metrics = run_benchmark(questions, question_types=args.question_types, limit=args.limit, verbose=args.verbose)
    print_report(metrics)


if __name__ == "__main__":
    main()
