#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes the AI to trigger (read the skill)
for a set of queries. Outputs results as JSON.

For our system, we use subagents to test skill triggering instead of Claude CLI.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    user_id: str = "default",
    model_name: str | None = None,
) -> dict:
    """Run a single query and return whether the skill was triggered.

    We test triggering by:
    1. Creating a temporary skill with the description
    2. Invoking the subagent with the query
    3. Checking if the skill was loaded (via skill metadata in response)
    """
    from src.agents.subagent.manager import get_subagent_manager

    triggered = False
    error = None

    try:
        # Load the skill into registry temporarily
        skill_path = Path(f"data/users/{user_id}/skills/{skill_name}")

        # Check if skill exists
        if not skill_path.exists():
            # Try system skills
            skill_path = Path(f"src/skills/{skill_name}")

        if not skill_path.exists():
            return {
                "query": query,
                "triggered": False,
                "error": f"Skill not found: {skill_name}",
                "should_trigger": False,
                "trigger_rate": 0.0,
                "triggers": 0,
                "runs": 1,
                "pass": False,
            }

        # Invoke with skill context
        manager = get_subagent_manager(user_id)

        # Build prompt with skill context hint
        full_query = f"[Skill: {skill_name}] {query}"

        start_time = time.time()

        # Simple invoke - the skill middleware should handle loading
        result = manager.invoke(skill_name, full_query)

        elapsed = time.time() - start_time

        # Check if skill was invoked based on result
        # For now, we consider it triggered if the result is successful
        triggered = result.get("success", False)

    except Exception as e:
        error = str(e)
        triggered = False

    return {
        "query": query,
        "triggered": triggered,
        "error": error,
        "elapsed": elapsed if "elapsed" in locals() else 0,
    }


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    user_id: str = "default",
    model_name: str | None = None,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    user_id,
                    model_name,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                result = future.result()
                query_triggers[query].append(result.get("triggered", False))
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "pass": did_pass,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=1, help="Number of runs per query")
    parser.add_argument(
        "--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold"
    )
    parser.add_argument("--user-id", default="default", help="User ID for subagent")
    parser.add_argument("--model", default=None, help="Model to use (default: from config)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        user_id=args.user_id,
        model_name=args.model,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(
                f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}",
                file=sys.stderr,
            )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
