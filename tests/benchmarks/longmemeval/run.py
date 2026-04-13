"""Run full LongMemEval QA benchmark.

Usage:
    python run.py                          # Run all 500 instances
    python run.py --max 100               # Run first 100 instances
    python run.py --output results.json   # Save results to file
"""

import asyncio
import json
import time
from pathlib import Path

import click

from tests.benchmarks.longmemeval import LongMemEvalDataset, LongMemEvalRunner
from tests.benchmarks.longmemeval.judge import judge_results


@click.command()
@click.option(
    "--max-instances",
    "-n",
    type=int,
    default=None,
    help="Max instances to evaluate (default: all 470 answerable)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output JSON file path",
)
@click.option(
    "--rate-limit",
    type=int,
    default=60,
    help="Agent rate limit (requests/minute)",
)
@click.option(
    "--variant",
    type=click.Choice(["small", "medium", "oracle"]),
    default="small",
    help="Dataset variant",
)
def main(max_instances, output, rate_limit, variant):
    """Run LongMemEval QA benchmark."""
    asyncio.run(
        _run(
            max_instances=max_instances,
            output=output,
            rate_limit=rate_limit,
            variant=variant,
        )
    )


async def _run(
    max_instances: int | None,
    output: Path | None,
    rate_limit: int,
    variant: str,
):
    """Run the benchmark."""
    print("=" * 60)
    print("LONGMEMEVAL QA BENCHMARK")
    print("=" * 60)
    print(f"Dataset: {variant}")
    print(f"Rate limit: {rate_limit} req/min")
    print()

    # Load dataset
    print("Loading dataset...")
    dataset = LongMemEvalDataset()
    instances = dataset.load(variant)

    # Filter to answerable only
    answerable = [i for i in instances if not i.is_abstention]
    if max_instances:
        answerable = answerable[:max_instances]

    print(f"Instances: {len(answerable)} (non-abstention)")
    print()

    # Run evaluation
    print("Running agent evaluation...")
    runner = LongMemEvalRunner(
        user_id="benchmark",
        agent_user_id="benchmark",
        skip_abstention=True,
    )

    t0 = time.time()
    results = await runner.run_evaluation(
        answerable,
        use_direct_context=True,
        rate_limit_rpm=rate_limit,
    )
    elapsed = time.time() - t0

    print(f"\nCollected {len(results.results)} answers in {elapsed:.1f}s")
    print(f"Errors: {results.errors}")
    print()

    # Judge with GPT-4o
    print("Judging with GPT-4o...")
    results_dict = results.to_dict()
    judged = await judge_results(results_dict["results"], use_gpt4o=True)

    # Calculate metrics
    correct = sum(1 for r in judged if r.get("is_correct") is True)
    incorrect = sum(1 for r in judged if r.get("is_correct") is False)
    skipped = sum(1 for r in judged if r.get("is_correct") is None)
    total = correct + incorrect

    # Per-type breakdown
    type_results: dict[str, dict] = {}
    for r in judged:
        qt = r["question_type"]
        if qt not in type_results:
            type_results[qt] = {"correct": 0, "total": 0}
        type_results[qt]["total"] += 1
        if r.get("is_correct"):
            type_results[qt]["correct"] += 1

    # Print results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Accuracy:      {correct / total * 100:6.1f}% ({correct}/{total})")
    print(f"Correct:      {correct}")
    print(f"Incorrect:    {incorrect}")
    print(f"Skipped:      {skipped}")
    print(f"Time:         {elapsed:.1f}s ({elapsed / len(judged):.1f}s/instance)")
    print()
    print("PER-TYPE ACCURACY:")
    print("-" * 60)
    for qt, data in sorted(
        type_results.items(), key=lambda x: -x[1]["correct"] / max(x[1]["total"], 1)
    ):
        acc = data["correct"] / max(data["total"], 1)
        bar = "█" * int(acc * 20) + "░" * (20 - int(acc * 20))
        pct = data["correct"] / max(data["total"], 1) * 100
        print(f"  {qt:32s} {bar} {pct:5.1f}% ({data['correct']}/{data['total']})")
    print("=" * 60)

    # Save to file
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        final = {
            **results_dict,
            "results": judged,
            "final_accuracy": correct / total if total > 0 else 0,
            "judge_mode": "gpt-4o",
        }
        with open(output, "w") as f:
            json.dump(final, f, indent=2)
        print(f"\nSaved to: {output}")


if __name__ == "__main__":
    main()
