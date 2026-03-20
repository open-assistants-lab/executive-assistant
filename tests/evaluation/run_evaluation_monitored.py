#!/usr/bin/env python3
"""Comprehensive evaluation runner with progress monitoring."""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread

import aiohttp

HTTP_BASE_URL = os.environ.get("EVAL_HTTP_URL", "http://localhost:8080")
EVAL_DIR = Path("data/evaluations")

PROGRESS_FILE = EVAL_DIR / "progress.json"
LOG_FILE = EVAL_DIR / f"full_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

PERSONAS = [
    "p1",
    "p2",
    "p3",
    "p4",
    "p5",
    "p6",
    "p7",
    "p8",
    "p9",
    "p10",
    "p11",
    "p12",
    "p13",
    "p14",
    "p15",
    "p16",
    "p17",
    "p18",
    "p19",
    "p20",
    "p21",
    "p22",
    "p23",
    "p24",
    "p25",
]

TOTAL_PERSONAS = 25
TOTAL_INTERACTIONS = 100


def log_message(msg: str, print_console: bool = True):
    """Log message to file and optionally console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"

    with open(LOG_FILE, "a") as f:
        f.write(full_msg + "\n")

    if print_console:
        print(full_msg)


def update_progress_file(
    completed_personas: int,
    current_persona: str,
    current_interaction: int,
    completed_interactions: int,
    total_interactions: int,
    avg_response_time: float,
    success_rate: float,
):
    """Update progress JSON file."""
    progress = {
        "started_at": datetime.now().isoformat(),
        "total_personas": TOTAL_PERSONAS,
        "total_interactions_per_persona": TOTAL_INTERACTIONS,
        "total_estimated": TOTAL_PERSONAS * TOTAL_INTERACTIONS,
        "completed_personas": completed_personas,
        "current_persona": current_persona,
        "current_interaction": current_interaction,
        "completed_interactions": completed_interactions,
        "remaining_interactions": TOTAL_PERSONAS * TOTAL_INTERACTIONS - completed_interactions,
        "avg_response_time_ms": avg_response_time,
        "success_rate": success_rate,
        "percent_complete": (completed_interactions / (TOTAL_PERSONAS * TOTAL_INTERACTIONS)) * 100,
    }

    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


async def test_http_connection() -> bool:
    """Test HTTP connection."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HTTP_BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


async def run_single_interaction(
    session: aiohttp.ClientSession, user_id: str, query: str, interaction_num: int
) -> dict:
    """Run a single interaction via HTTP."""
    payload = {
        "message": query,
        "user_id": user_id,
    }

    start_time = time.time()
    try:
        async with session.post(
            f"{HTTP_BASE_URL}/message", json=payload, timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            response_time_ms = int((time.time() - start_time) * 1000)
            if resp.status != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status}",
                    "response_time_ms": response_time_ms,
                    "tool_calls": 0,
                }

            data = await resp.json()
            response_text = data.get("response", "")
            error_text = data.get("error", "")

            return {
                "success": response_text.strip() != "" and not error_text,
                "response": response_text,
                "error": error_text,
                "response_time_ms": response_time_ms,
                "tool_calls": len(data.get("tool_calls", [])),
            }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Timeout",
            "response_time_ms": int((time.time() - start_time) * 1000),
            "tool_calls": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time_ms": int((time.time() - start_time) * 1000),
            "tool_calls": 0,
        }


async def run_persona_evaluation(
    session: aiohttp.ClientSession, persona_id: str, user_id: str, queries: list[str]
) -> dict:
    """Run evaluation for a single persona."""
    results = {
        "persona_id": persona_id,
        "interactions": [],
    }

    total_response_time = 0
    successful = 0

    for i, query in enumerate(queries):
        result = await run_single_interaction(session, user_id, query, i + 1)

        results["interactions"].append(
            {
                "query": query,
                "success": result["success"],
                "response_time_ms": result["response_time_ms"],
                "tool_calls": result.get("tool_calls", 0),
                "error": result.get("error"),
            }
        )

        total_response_time += result["response_time_ms"]
        if result["success"]:
            successful += 1

        await asyncio.sleep(0.1)

    results["successful"] = successful
    results["total"] = len(queries)
    results["success_rate"] = (successful / len(queries)) * 100 if queries else 0
    results["avg_response_time"] = total_response_time / len(queries) if queries else 0

    return results


def generate_test_queries():
    """Generate test queries that cover all tools."""
    from tests.evaluation.personas import generate_test_queries, PERSONAS

    all_queries = {}
    for persona in PERSONAS:
        all_queries[persona["id"]] = generate_test_queries(persona, TOTAL_INTERACTIONS)

    return all_queries


async def run_full_evaluation():
    """Run full evaluation across all personas."""
    log_message("=" * 80)
    log_message("STARTING FULL PERSONA EVALUATION")
    log_message(f"Personas: {TOTAL_PERSONAS}")
    log_message(f"Interactions per persona: {TOTAL_INTERACTIONS}")
    log_message(f"Total interactions: {TOTAL_PERSONAS * TOTAL_INTERACTIONS}")
    log_message(f"HTTP URL: {HTTP_BASE_URL}")
    log_message("=" * 80)

    if not await test_http_connection():
        log_message("ERROR: Cannot connect to HTTP server!")
        return

    log_message("HTTP connection OK")

    log_message("Generating test queries...")
    queries = generate_test_queries()
    log_message(f"Generated {len(queries)} query sets")

    all_results = []
    completed_interactions = 0

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        for persona_idx, persona_id in enumerate(PERSONAS):
            log_message(f"\n{'=' * 60}")
            log_message(f"EVALUATING: {persona_id.upper()}")
            log_message(f"Progress: {persona_idx + 1}/{TOTAL_PERSONAS}")
            log_message(f"{'=' * 60}")

            persona_start = time.time()

            results = await run_persona_evaluation(
                session, persona_id, f"eval_{persona_id}", queries[persona_id]
            )

            all_results.append(results)

            completed_interactions += results["total"]
            persona_time = time.time() - persona_start

            avg_response_time = results["avg_response_time"]
            success_rate = results["success_rate"]

            log_message(
                f"Completed {persona_id}: {results['successful']}/{results['total']} "
                f"({success_rate:.1f}%) - Avg: {avg_response_time:.0f}ms"
            )

            total_elapsed = time.time() - start_time
            avg_per_interaction = (
                total_elapsed / completed_interactions if completed_interactions > 0 else 0
            )
            remaining = (TOTAL_PERSONAS * TOTAL_INTERACTIONS) - completed_interactions
            eta_seconds = remaining * avg_per_interaction
            eta_minutes = eta_seconds / 60

            log_message(
                f"Total elapsed: {total_elapsed / 60:.1f} min | "
                f"ETA: {eta_minutes:.1f} min remaining"
            )

            update_progress_file(
                completed_personas=persona_idx + 1,
                current_persona=persona_id,
                current_interaction=results["total"],
                completed_interactions=completed_interactions,
                total_interactions=TOTAL_PERSONAS * TOTAL_INTERACTIONS,
                avg_response_time=avg_response_time,
                success_rate=success_rate,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = EVAL_DIR / f"result_{persona_id}_{timestamp}.json"
            with open(result_file, "w") as f:
                json.dump(results, f, indent=2)

    total_time = time.time() - start_time

    log_message("\n" + "=" * 80)
    log_message("EVALUATION COMPLETE")
    log_message(f"Total time: {total_time / 60:.1f} minutes")
    log_message("=" * 80)

    generate_summary(all_results, total_time)

    update_progress_file(
        completed_personas=TOTAL_PERSONAS,
        current_persona="DONE",
        current_interaction=TOTAL_INTERACTIONS,
        completed_interactions=TOTAL_PERSONAS * TOTAL_INTERACTIONS,
        total_interactions=TOTAL_PERSONAS * TOTAL_INTERACTIONS,
        avg_response_time=0,
        success_rate=sum(r["success_rate"] for r in all_results) / len(all_results),
    )


def generate_summary(results: list[dict], total_time: float):
    """Generate summary report."""
    from tests.evaluation.personas import PERSONAS

    report = []
    report.append("=" * 80)
    report.append("COMPREHENSIVE EVALUATION SUMMARY")
    report.append("=" * 80)
    report.append(f"Total Personas: {len(results)}")
    report.append(f"Interactions per Persona: {TOTAL_INTERACTIONS}")
    report.append(f"Total Interactions: {sum(r['total'] for r in results)}")
    report.append(f"Total Time: {total_time / 60:.1f} minutes")
    report.append("")

    total_successful = sum(r["successful"] for r in results)
    total_interactions = sum(r["total"] for r in results)
    overall_success = (total_successful / total_interactions * 100) if total_interactions > 0 else 0

    report.append(f"Overall Success Rate: {overall_success:.1f}%")
    report.append("")

    report.append("-" * 80)
    report.append("PERSONA BREAKDOWN")
    report.append("-" * 80)

    for result in results:
        persona_id = result["persona_id"]
        persona_info = next((p for p in PERSONAS if p["id"] == persona_id), {})
        name = persona_info.get("name", persona_id)
        style = persona_info.get("style", "")

        report.append(f"\n{name} ({persona_id}) - {style}:")
        report.append(
            f"  Success: {result['successful']}/{result['total']} ({result['success_rate']:.1f}%)"
        )
        report.append(f"  Avg Response Time: {result['avg_response_time']:.0f}ms")

    report.append("")
    report.append("-" * 80)
    report.append("TOOL COVERAGE CHECK")
    report.append("-" * 80)

    tool_keywords = {
        "email": ["email", "gmail", "inbox", "mail"],
        "contacts": ["contact", "address"],
        "todos": ["todo", "task", "reminder"],
        "files": ["file", "directory", "folder", "read", "write", "delete"],
        "shell": ["shell", "command", "execute"],
        "memory": ["memory", "history", "remember"],
        "time": ["time", "date"],
        "skills": ["skill", "load", "create"],
        "subagent": ["subagent", "agent", "create", "invoke"],
        "web": ["search", "scrape", "web", "crawl"],
    }

    all_queries = generate_test_queries()
    tool_coverage = {tool: False for tool in tool_keywords}

    for queries in all_queries.values():
        query_text = " ".join(queries).lower()
        for tool, keywords in tool_keywords.items():
            if any(kw in query_text for kw in keywords):
                tool_coverage[tool] = True

    for tool, covered in tool_coverage.items():
        status = "✓" if covered else "✗"
        report.append(f"  {status} {tool}: {'covered' if covered else 'NOT COVERED'}")

    summary_path = (
        EVAL_DIR / f"full_evaluation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(summary_path, "w") as f:
        f.write("\n".join(report))

    log_message(f"\nSummary saved to: {summary_path}")

    print("\n" + "\n".join(report))


if __name__ == "__main__":
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_full_evaluation())
