"""CLI for running LongMemEval benchmark."""

import asyncio
import json
import time
from pathlib import Path

import click


@click.group()
def cli():
    """LongMemEval benchmark runner - QA mode using direct context."""
    pass


@cli.command()
@click.option(
    "--variant",
    type=click.Choice(["small", "medium", "oracle"]),
    default="small",
    help="Dataset variant to use",
)
@click.option(
    "--max-instances",
    type=int,
    default=None,
    help="Limit number of instances to evaluate (default: all)",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for results JSON",
)
@click.option(
    "--no-gpt4o-judge",
    is_flag=True,
    help="Skip GPT-4o judge (use exact match only - not recommended)",
)
@click.option(
    "--rate-limit",
    type=int,
    default=60,
    help="Rate limit for agent calls (requests per minute, default: 60)",
)
def run(
    variant: str,
    max_instances: int | None,
    output: Path | None,
    no_gpt4o_judge: bool,
    rate_limit: int,
):
    """Run LongMemEval QA benchmark.

    This runs the standard QA evaluation using direct context mode.
    Each question is answered by providing the full conversation history
    directly to the agent, then comparing the answer with GPT-4o judge.
    """
    asyncio.run(_run_async(variant, max_instances, output, not no_gpt4o_judge, rate_limit))


async def _run_async(
    variant: str,
    max_instances: int | None,
    output: Path | None,
    use_gpt4o: bool,
    rate_limit: int,
):
    """Async implementation of benchmark runner."""
    from tests.benchmarks.longmemeval import LongMemEvalDataset, LongMemEvalRunner
    from tests.benchmarks.longmemeval.judge import judge_results

    print(f"Loading LongMemEval {variant} dataset...")
    dataset = LongMemEvalDataset()
    instances = dataset.load(variant)

    stats = dataset.get_stats(instances)
    print(f"Dataset: {stats['total_instances']} instances ({stats['answerable_count']} answerable)")
    print(f"Question types: {', '.join(stats['type_counts'].keys())}")
    print()

    if max_instances:
        instances = instances[:max_instances]
        print(f"Limited to {max_instances} instances")

    runner = LongMemEvalRunner(
        user_id="benchmark",
        agent_user_id="benchmark",
        skip_abstention=True,
    )

    print("Running QA evaluation (direct context mode)...")
    print(f"Rate limit: {rate_limit} req/min")
    print()

    t0 = time.time()
    results = await runner.run_evaluation(
        instances,
        use_direct_context=True,
        rate_limit_rpm=rate_limit,
    )
    elapsed = time.time() - t0

    print("\n=== AGENT ANSWERS COLLECTED ===")
    print(f"Total: {len(results.results)}")
    print(f"Errors: {results.errors}")
    print(f"Time: {elapsed:.1f}s ({elapsed / len(results.results):.1f}s per instance)")
    print()

    results_dict = results.to_dict()

    if use_gpt4o:
        print("\n=== JUDGING WITH GPT-4O ===")
        results_with_judgment = await judge_results(results_dict["results"], use_gpt4o=True)
    else:
        print("=== JUDGING WITH EXACT MATCH ===")
        results_with_judgment = await judge_results(results_dict["results"], use_gpt4o=False)

    correct = sum(1 for r in results_with_judgment if r.get("is_correct") is True)
    incorrect = sum(1 for r in results_with_judgment if r.get("is_correct") is False)
    skipped = sum(1 for r in results_with_judgment if r.get("is_correct") is None)
    total = correct + incorrect

    print()
    print("=" * 50)
    print("LONGMEMEVAL QA RESULTS")
    print("=" * 50)
    print("Mode:          Direct Context (QA)")
    print(f"Dataset:       {variant} ({len(results.results)} instances)")
    print(f"Judge:         {'GPT-4o' if use_gpt4o else 'Exact Match'}")
    print("-" * 50)
    print(
        f"Accuracy:      {correct / total * 100:.1f}% ({correct}/{total})"
        if total > 0
        else "Accuracy:      N/A"
    )
    print(f"Correct:       {correct}")
    print(f"Incorrect:     {incorrect}")
    print(f"Skipped:       {skipped}")
    print(f"Total Time:    {elapsed:.1f}s")
    print(f"Per Instance:  {elapsed / len(results.results):.1f}s")
    print("=" * 50)

    # Per-type breakdown
    print()
    print("PER-TYPE ACCURACY:")
    type_results: dict[str, dict] = {}
    for r in results_with_judgment:
        qt = r["question_type"]
        if qt not in type_results:
            type_results[qt] = {"correct": 0, "total": 0}
        type_results[qt]["total"] += 1
        if r.get("is_correct"):
            type_results[qt]["correct"] += 1

    for qt, data in sorted(type_results.items()):
        acc = data["correct"] / data["total"] * 100 if data["total"] > 0 else 0
        bar = "█" * int(acc / 10) + "░" * (10 - int(acc / 10))
        print(f"  {qt:30s} {bar} {data['correct']:3d}/{data['total']:3d} ({acc:.0f}%)")

    # Save results
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        final_results = {
            **results_dict,
            "results": results_with_judgment,
            "final_accuracy": correct / total if total > 0 else 0,
            "judge_mode": "gpt-4o" if use_gpt4o else "exact_match",
        }
        with open(output, "w") as f:
            json.dump(final_results, f, indent=2)
        print(f"\nResults saved to {output}")


@cli.command()
@click.option(
    "--variant",
    type=click.Choice(["small", "medium", "oracle"]),
    default="small",
    help="Dataset variant to download",
)
def download(variant: str):
    """Download LongMemEval dataset."""
    from tests.benchmarks.longmemeval import LongMemEvalDataset

    dataset = LongMemEvalDataset()
    path = dataset.download(variant)
    print(f"Downloaded to: {path}")


@cli.command()
@click.option(
    "--variant",
    type=click.Choice(["small", "medium", "oracle"]),
    default="small",
    help="Dataset variant to inspect",
)
def inspect(variant: str):
    """Inspect LongMemEval dataset structure."""
    from tests.benchmarks.longmemeval import LongMemEvalDataset

    dataset = LongMemEvalDataset()
    instances = dataset.load(variant)

    stats = dataset.get_stats(instances)

    print(f"LongMemEval {variant} Dataset")
    print("=" * 40)
    print(f"Total instances: {stats['total_instances']}")
    print(f"Answerable (non-abstention): {stats['answerable_count']}")
    print(f"Abstention: {stats['abstention_count']}")
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Avg sessions per instance: {stats['avg_sessions_per_instance']:.1f}")
    print()
    print("Question types:")
    for qtype, count in stats["type_counts"].items():
        print(f"  {qtype}: {count}")

    if instances:
        print()
        print("Sample instance:")
        sample = instances[0]
        print(f"  ID: {sample.question_id}")
        print(f"  Type: {sample.question_type}")
        print(f"  Question: {sample.question[:100]}...")
        print(f"  Expected Answer: {sample.answer[:100]}...")
        print(f"  Sessions: {len(sample.haystack_sessions)}")


if __name__ == "__main__":
    cli()
