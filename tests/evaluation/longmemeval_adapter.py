"""LongMemEval benchmark adapter for Executive Assistant.

Downloads the longmemeval_s dataset from HuggingFace, ingests sessions
incrementally through the agent's HTTP API, and scores responses against
ground truth using LLM-as-judge (GPT-4o).

Usage:
    uv run python tests/evaluation/longmemeval_adapter.py --limit 10
    uv run python tests/evaluation/longmemeval_adapter.py --question-types single-session-user
    uv run python tests/evaluation/longmemeval_adapter.py --full  # all 500 questions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import aiohttp
from dotenv import load_dotenv

try:
    from tests.evaluation.longmemeval_synthesis import synthesize_answer
except ModuleNotFoundError:
    from longmemeval_synthesis import synthesize_answer

# Load .env for OPENAI_API_KEY before module-level constants are read.
load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

HTTP_BASE_URL = "http://localhost:8080"
JUDGE_MODEL = os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4o")
JUDGE_API_KEY = os.environ.get("OPENAI_API_KEY", "")
JUDGE_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
USER_ID = "lme_eval_user"
MAX_CONCURRENT = 3  # parallel questions (sessions are sequential per question)
MEMORY_SEARCH_INSTRUCTION = ""


# ── Dataset ──────────────────────────────────────────────────────────────────

def load_dataset() -> list[dict[str, Any]]:
    """Download and load the longmemeval_s_cleaned dataset from HuggingFace."""
    cache_dir = Path("/tmp/lme_cache")
    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id="LIXINYI33/longmemeval-s",
            filename="longmemeval_s_cleaned.json",
            repo_type="dataset",
            cache_dir=str(cache_dir),
        )
    except Exception:
        # Fallback: use pre-downloaded file
        path = None
        for p in cache_dir.rglob("longmemeval_s_cleaned.json"):
            path = p
            break
        if path is None:
            raise RuntimeError(
                "Could not download longmemeval_s_cleaned.json. "
                "Ensure huggingface_hub is installed and internet is available."
            )

    with open(path) as f:
        data = json.load(f)

    print(f"Loaded {len(data)} questions")
    return data if isinstance(data, list) else list(data.values())


# ── Agent Interaction ────────────────────────────────────────────────────────

async def send_message(
    session: aiohttp.ClientSession,
    message: str,
    user_id: str = USER_ID,
    workspace_id: str = "personal",
    return_details: bool = False,
) -> str | dict[str, Any]:
    """Send a single message to the agent and return the response text."""
    details = await send_message_details(
        session, message, user_id=user_id, workspace_id=workspace_id, return_details=return_details
    )
    if return_details:
        return details
    return str(details.get("response", ""))


async def send_message_details(
    session: aiohttp.ClientSession,
    message: str,
    user_id: str = USER_ID,
    workspace_id: str = "personal",
    return_details: bool = True,
) -> dict[str, Any]:
    """Send a verbose message and return response plus tool diagnostics."""
    prompted_message = message
    if "Use message_search before answering" not in prompted_message:
        prompted_message = f"{MEMORY_SEARCH_INSTRUCTION}{message}"
    payload = {
        "message": prompted_message,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "verbose": return_details,
    }
    try:
        async with session.post(
            f"{HTTP_BASE_URL}/message", json=payload, timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                raw_body = ""
                try:
                    raw_body = await resp.text()
                except Exception:
                    raw_body = ""
                return {
                    "response": "",
                    "tool_calls": [],
                    "tool_events": [],
                    "http_status": resp.status,
                    "error": f"http_{resp.status}",
                    "raw_body": raw_body,
                }
            data = await resp.json()
            verbose_data = data.get("verbose_data") or {}
            return {
                "response": data.get("response", ""),
                "tool_calls": data.get("tool_calls") or [],
                "tool_events": verbose_data.get("tool_events") or [],
                "http_status": resp.status,
                "error": data.get("error"),
                "raw_body": "",
            }
    except Exception as e:
        return {
            "response": "",
            "tool_calls": [],
            "tool_events": [],
            "http_status": None,
            "error": f"{type(e).__name__}: {e}",
            "raw_body": "",
        }


async def ingest_sessions_fast(
    session: aiohttp.ClientSession,
    haystack_sessions: list[list[dict]],
    user_id: str,
    workspace_id: str = "personal",
    batch_size: int = 10,
    verbose: bool = False,
) -> int:
    """Pre-load sessions incrementally with memory extraction between batches.

    Import sessions in batches, trigger memory extraction/consolidation
    between batches, so the agent benefits from compressed memory.
    This matches EA's real-world behavior: conversations trigger memory
    extraction, and the agent searches memory when asked questions.
    """
    total_turns = 0
    for batch_start in range(0, len(haystack_sessions), batch_size):
        batch = haystack_sessions[batch_start:batch_start + batch_size]
        batch_turns = []
        for si, sesh in enumerate(batch):
            for turn in sesh:
                content = turn.get("content", "")
                role = turn.get("role", "user")
                if content.strip():
                    batch_turns.append({
                        "role": role,
                        "content": content,
                        "metadata": {"session_id": f"session_{batch_start + si:04d}"},
                    })
                    total_turns += 1

        # Import batch
        payload = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "messages": batch_turns,
        }
        try:
            async with session.post(
                f"{HTTP_BASE_URL}/conversation/import",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    if verbose:
                        print(f"  import failed ({resp.status})", flush=True)
        except Exception as e:
            if verbose:
                print(f"  import error: {e}", flush=True)

        # NOTE: Memory extraction skipped — using retrieval-only mode
        # (raw message search + ranker heuristics, no lossy LLM extraction)

        if verbose and (batch_start + batch_size) % 20 == 0:
            print(f"    {batch_start + len(batch)}/{len(haystack_sessions)} sessions, "
                  f"{total_turns} turns", flush=True)

    if verbose:
        print(f"    Imported {total_turns} turns in {len(haystack_sessions)} sessions", flush=True)
    return total_turns


# ── LLM-as-Judge Scoring ─────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an evaluator for a long-term memory benchmark.
Compare the agent's answer to the ground truth answer.

Ground Truth: {ground_truth}
Agent Response: {agent_response}

Determine if the agent's response is semantically equivalent to the ground truth.
The response does NOT need to be word-for-word identical.
If the agent provides the correct factual information, mark as CORRECT.
If the agent provides wrong information, refuses to answer, or says "I don't know", mark as INCORRECT.

Output ONLY one word: CORRECT or INCORRECT."""


async def score_response(
    ground_truth: str, agent_response: str, judge_session: aiohttp.ClientSession
) -> bool:
    """Score agent response against ground truth using GPT-4o judge."""
    if not agent_response.strip():
        return False
    if _requires_exact_value_match(ground_truth) and not _fuzzy_match(
        ground_truth, agent_response
    ):
        return False

    prompt = JUDGE_PROMPT.format(ground_truth=ground_truth, agent_response=agent_response)

    payload = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 10,
    }
    headers = {"Authorization": f"Bearer {JUDGE_API_KEY}", "Content-Type": "application/json"}

    try:
        async with judge_session.post(
            f"{JUDGE_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                # Fallback: fuzzy string match
                return _fuzzy_match(ground_truth, agent_response)
            data = await resp.json()
            text = data["choices"][0]["message"]["content"].strip().upper()
            if "INCORRECT" in text:
                return False
            return "CORRECT" in text
    except Exception:
        return _fuzzy_match(ground_truth, agent_response)


def _fuzzy_match(ground_truth: str | int | float, agent_response: str) -> bool:
    """Strict fallback scorer — only counts as correct if the agent clearly knows."""
    gt_lower = str(ground_truth).lower().strip()
    agent_lower = agent_response.lower().strip()

    # Reject "I don't know" / "I couldn't find" responses
    if any(phrase in agent_lower for phrase in [
        "i don't have", "i couldn't find", "i don't know",
        "i'm unable to determine", "no specific information",
        "i'm sorry, but i couldn't", "it seems that i don't",
        "i'm missing specific information",
        "doesn't seem to have", "it appears that i don't",
        "it looks like i don't",
    ]):
        return False

    expected_numbers = _extract_expected_numbers(gt_lower)
    if expected_numbers:
        expected_currency = _extract_currency_values(gt_lower)
        if expected_currency:
            response_currency = _extract_currency_values(agent_lower)
            if response_currency and response_currency[-1] not in expected_currency:
                return False
        if _expected_time_only_in_goal_context(gt_lower, agent_lower):
            return False
        response_numbers = set(_extract_response_numbers(agent_lower))
        return bool(expected_numbers & response_numbers)

    if re.search(rf"\b{re.escape(gt_lower)}\b", agent_lower):
        return True
    gt_words = set(gt_lower.split())
    agent_words = set(agent_lower.split())
    if not gt_words:
        return False
    if len(gt_words) <= 3:
        return False
    overlap = len(gt_words & agent_words) / len(gt_words)
    return overlap >= 0.5


_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def _requires_exact_value_match(ground_truth: str | int | float) -> bool:
    text = str(ground_truth).lower()
    return bool(_extract_expected_numbers(text)) or len(text.split()) <= 3


def _extract_expected_numbers(text: str) -> set[int]:
    values = set(_extract_response_numbers(text))
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            values.add(value)
    return values


def _extract_response_numbers(text: str) -> list[int]:
    values = []
    for match in re.finditer(r"(?<![\w.])\$?([0-9][0-9,]*(?:\.[0-9]+)?)(?![\w.])", text):
        raw = match.group(1).replace(",", "")
        try:
            values.append(int(float(raw)))
        except ValueError:
            continue
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            values.append(value)
    return values


def _extract_currency_values(text: str) -> list[int]:
    values = []
    for match in re.finditer(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text):
        raw = match.group(1).replace(",", "")
        try:
            values.append(int(float(raw)))
        except ValueError:
            continue
    return values


def _expected_time_only_in_goal_context(ground_truth: str, agent_response: str) -> bool:
    expected_times = set(re.findall(r"\b\d{1,2}:\d{2}\b", ground_truth))
    if not expected_times:
        return False
    for sentence in re.split(r"[.!?]\s+", agent_response):
        if expected_times & set(re.findall(r"\b\d{1,2}:\d{2}\b", sentence)):
            if not re.search(r"\b(goal|hope|hoping|aim|aiming|beat)\b", sentence):
                return False
    return True


# ── Benchmark Runner ─────────────────────────────────────────────────────────

async def run_single_question(
    q: dict[str, Any],
    session: aiohttp.ClientSession,
    judge_session: aiohttp.ClientSession | None,
    idx: int,
    total: int,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run a single LongMemEval question: ingest sessions → ask → score."""
    question = q["question"]
    ground_truth = q["answer"]
    question_type = q["question_type"]
    haystack_sessions = q["haystack_sessions"]
    question_id = q["question_id"]
    uid = f"{USER_ID}_{idx}"
    ws = f"lme_eval_{idx}"

    t0 = time.monotonic()

    # Step 1: Ingest all sessions into isolated workspace
    if verbose:
        print(
            f"  [{idx}/{total}] {question_type}: {question[:60]}... ({len(haystack_sessions)} sessions)",
            flush=True,
        )
    turns_ingested = await ingest_sessions_fast(
        session, haystack_sessions, uid, workspace_id=ws
    )

    # Step 2: Ask the question
    message_result = await send_message(
        session, question, user_id=uid, workspace_id=ws, return_details=True
    )
    if isinstance(message_result, dict):
        agent_response = str(message_result.get("response", ""))
        tool_calls = message_result.get("tool_calls") or []
        tool_events = message_result.get("tool_events") or []
        http_status = message_result.get("http_status")
        error = message_result.get("error")
        raw_body = message_result.get("raw_body", "")
    else:
        agent_response = str(message_result)
        tool_calls = []
        tool_events = []
        http_status = None
        error = None
        raw_body = ""
    t1 = time.monotonic()

    synthesis = None
    synthesized_answer = synthesize_answer(question, tool_events)
    if synthesized_answer is not None:
        agent_response = synthesized_answer
        synthesis = "deterministic"

    # Step 3: Score
    scorer = "judge" if judge_session else "fuzzy"
    if judge_session:
        correct = await score_response(ground_truth, agent_response, judge_session)
    else:
        correct = _fuzzy_match(ground_truth, agent_response)

    duration = t1 - t0
    if verbose:
        status = "✅" if correct else "❌"
        print(
            f"    {status} {duration:.1f}s | turns={turns_ingested} | "
            f"response={agent_response[:60]}...",
            flush=True,
        )

    return {
        "question_id": question_id,
        "question_type": question_type,
        "question": question,
        "correct": correct,
        "duration_s": round(duration, 1),
        "turns_ingested": turns_ingested,
        "user_id": uid,
        "workspace_id": ws,
        "scorer": scorer,
        "synthesis": synthesis,
        "agent_response_full": agent_response,
        "agent_response": agent_response[:500],
        "tool_calls": tool_calls,
        "tool_events": tool_events,
        "http_status": http_status,
        "error": error,
        "raw_body": raw_body[:1000] if isinstance(raw_body, str) else str(raw_body)[:1000],
        "ground_truth": ground_truth,
    }


async def run_benchmark(
    questions: list[dict[str, Any]],
    question_types: list[str] | None = None,
    limit: int | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the full LongMemEval benchmark."""
    # Filter questions
    if question_types:
        questions = [q for q in questions if q["question_type"] in question_types]
    if limit:
        questions = questions[:limit]

    total = len(questions)
    print(f"\nRunning LongMemEval benchmark: {total} questions\n")

    results: list[dict] = []
    async with aiohttp.ClientSession() as agent_session:
        # Create judge session if API key available
        judge_session = None
        if JUDGE_API_KEY:
            judge_session = aiohttp.ClientSession()
        else:
            print("⚠️  No OPENAI_API_KEY set — using fuzzy match fallback.\n")

        try:
            # Process questions sequentially (sessions are stateful per question)
            for i, q in enumerate(questions):
                result = await run_single_question(
                    q,
                    agent_session,
                    judge_session,
                    i + 1,
                    total,
                    verbose=verbose,
                )
                # Override user_id to prevent session mixing
                results.append(result)
                # Rate-limit breathing room between questions
                await asyncio.sleep(3)
        finally:
            if judge_session:
                await judge_session.close()

    # Compute metrics
    return _compute_metrics(results, total)


def _compute_metrics(results: list[dict], total: int) -> dict[str, Any]:
    """Compute per-category and overall metrics."""
    correct = sum(1 for r in results if r["correct"])
    accuracy = (correct / total * 100) if total else 0

    # Per-category
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_type[r["question_type"]].append(r)

    type_metrics = {}
    for qt, items in sorted(by_type.items()):
        c = sum(1 for it in items if it["correct"])
        type_metrics[qt] = {
            "correct": c,
            "total": len(items),
            "accuracy": round(c / len(items) * 100, 1) if items else 0,
        }

    durations = [r["duration_s"] for r in results]
    durations.sort()

    return {
        "overall": {
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy, 1),
        },
        "by_type": type_metrics,
        "timing": {
            "avg_s": round(sum(durations) / len(durations), 1) if durations else 0,
            "p50_s": durations[len(durations) // 2] if durations else 0,
            "p95_s": durations[int(len(durations) * 0.95)] if durations else 0,
        },
        "results": results,
    }


# ── Report ───────────────────────────────────────────────────────────────────

LEADERBOARD = {
    "Mastra OM (gpt-5-mini)": 94.87,
    "Mastra OM (gemini-3-pro)": 93.27,
    "Hindsight (gemini-3-pro)": 91.40,
    "Mastra OM (gemini-3-flash)": 89.20,
    "EmergenceMem Internal (gpt-4o)": 86.00,
    "Supermemory (gemini-3-pro)": 85.20,
    "Mastra OM (gpt-4o)": 84.23,
    "EmergenceMem Simple (gpt-4o)": 82.40,
    "Oracle (gpt-4o)": 82.40,
    "Supermemory (gpt-4o)": 81.60,
    "Mastra RAG topK20 (gpt-4o)": 80.05,
    "Zep (gpt-4o)": 71.20,
    "Full context (gpt-4o)": 60.20,
}


def print_report(metrics: dict[str, Any]) -> None:
    """Print benchmark report."""
    m = metrics["overall"]
    by_type = metrics["by_type"]
    timing = metrics["timing"]

    print(f"\n{'='*70}")
    print("LongMemEval Benchmark Results — Executive Assistant")
    print(f"{'='*70}")
    print(f"Overall: {m['correct']}/{m['total']} = {m['accuracy']}%")
    print(f"Timing:  avg={timing['avg_s']}s p50={timing['p50_s']}s p95={timing['p95_s']}s")
    print()

    print("By question type:")
    for qt, tm in sorted(by_type.items()):
        bar = "█" * int(tm["accuracy"] / 5) + "░" * (20 - int(tm["accuracy"] / 5))
        print(f"  {qt:<28s} {tm['accuracy']:5.1f}% {bar} ({tm['correct']}/{tm['total']})")

    print(f"\n{'='*70}")
    print("Leaderboard (overall accuracy)")
    print(f"{'='*70}")
    all_scores = sorted(LEADERBOARD.items(), key=lambda x: -x[1])
    ea_inserted = False
    for name, score in all_scores:
        if not ea_inserted and m["accuracy"] > score:
            print(f"  {m['accuracy']:5.1f}%  EA (this run) ←")
            ea_inserted = True
        print(f"  {score:5.1f}%  {name}")
    if not ea_inserted:
        print(f"  {m['accuracy']:5.1f}%  EA (this run) ←")
    print()

    # Save results
    output_path = Path(f"data/evaluations/longmemeval_{time.strftime('%Y%m%d_%H%M%S')}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Results saved to: {output_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LongMemEval benchmark for EA")
    parser.add_argument(
        "--limit", type=int, default=None, help="Max questions to run (default: all 500)"
    )
    parser.add_argument(
        "--question-types",
        nargs="*",
        default=None,
        choices=[
            "single-session-user",
            "single-session-assistant",
            "single-session-preference",
            "multi-session",
            "knowledge-update",
            "temporal-reasoning",
        ],
        help="Filter by question type(s)",
    )
    parser.add_argument("--full", action="store_true", help="Run all 500 questions")
    parser.add_argument("--verbose", action="store_true", default=True, help="Verbose output")
    args = parser.parse_args()

    if args.full:
        args.limit = None

    questions = load_dataset()

    # Check backend
    try:
        import urllib.request
        urllib.request.urlopen(f"{HTTP_BASE_URL}/health", timeout=5).read()
    except Exception:
        print("❌ Backend not reachable at", HTTP_BASE_URL)
        print("   Start with: uv run ea http")
        sys.exit(1)

    metrics = asyncio.run(
        run_benchmark(
            questions,
            question_types=args.question_types,
            limit=args.limit,
            verbose=args.verbose,
        )
    )

    print_report(metrics)


if __name__ == "__main__":
    main()
