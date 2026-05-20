#!/usr/bin/env python3
"""Compare two pytest-benchmark JSON results files and show deltas."""

import argparse
import json
import sys
from pathlib import Path

RESULTS_DIR = Path("results")


def load_benchmark_json(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    benchmarks = data.get("benchmarks", [])
    result = {}
    for b in benchmarks:
        name = b.get("name", "unknown")
        full_name = b.get("fullname", name)
        group = b.get("group", "")
        stats = b.get("stats", {})
        result[full_name] = {
            "name": name,
            "group": group,
            "min": stats.get("min", 0),
            "max": stats.get("max", 0),
            "mean": stats.get("mean", 0),
            "median": stats.get("median", 0),
            "stddev": stats.get("stddev", 0),
            "ops": stats.get("ops", 0),
        }
    return result


def format_time(ms: float) -> str:
    if ms < 1.0:
        return f"{ms*1000:.1f}µs"
    if ms < 1000:
        return f"{ms:.2f}ms"
    return f"{ms/1000:.2f}s"


def percent_change(old: float, new: float) -> str:
    if old == 0:
        return "N/A"
    pct = ((new - old) / old) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def render_table(before: dict, after: dict) -> str:
    all_keys = set(before.keys()) | set(after.keys())
    rows = []
    for key in sorted(all_keys):
        b = before.get(key)
        a = after.get(key)
        if b and a:
            delta = percent_change(b["mean"], a["mean"])
            rows.append(
                f"| {b['name']} | {format_time(b['mean'])} ± {format_time(b['stddev'])} "
                f"| {format_time(a['mean'])} ± {format_time(a['stddev'])} | {delta} |"
            )
        elif b and not a:
            rows.append(f"| {b['name']} | {format_time(b['mean'])} ± {format_time(b['stddev'])} | REMOVED | - |")
        else:
            rows.append(f"| {a['name']} | NEW | {format_time(a['mean'])} ± {format_time(a['stddev'])} | - |")

    header = "| Test | Before | After | Δ |"
    sep = "|------|--------|-------|-----|"
    return "\n".join([header, sep] + rows)


def main():
    parser = argparse.ArgumentParser(description="Compare pytest-benchmark JSON results")
    parser.add_argument("before", nargs="?", help="Path to before JSON (default: results/latest.json)")
    parser.add_argument("after", nargs="?", help="Path to after JSON (default: <before parent>/latest.json will be used if before is a specific file)")
    parser.add_argument("--markdown", action="store_true", help="Output markdown table")
    parser.add_argument("--diff", action="store_true", help="Compare latest.json with previous latest")
    args = parser.parse_args()

    if args.diff:
        archives = sorted(RESULTS_DIR.glob("*.json"))
        if len(archives) < 2:
            print("Need at least 2 archived results for --diff")
            sys.exit(1)
        before_path = archives[-2]
        after_path = archives[-1]
    elif args.before and args.after:
        before_path = Path(args.before)
        after_path = Path(args.after)
    elif args.before:
        before_path = Path(args.before)
        after_path = before_path.parent / "latest.json"
    else:
        latest = RESULTS_DIR / "latest.json"
        if not latest.exists():
            print("No results found. Run benchmarks first.")
            sys.exit(1)
        before_path = latest
        after_path = latest
        print("Only one result file. No comparison possible.")
        sys.exit(0)

    if not before_path.exists():
        print(f"Before file not found: {before_path}")
        sys.exit(1)
    if not after_path.exists():
        print(f"After file not found: {after_path}")
        sys.exit(1)

    before = load_benchmark_json(str(before_path))
    after = load_benchmark_json(str(after_path))

    if args.markdown:
        print(render_table(before, after))
    else:
        print(f"Comparing {before_path.name} → {after_path.name}")
        print(f"{'Test':<50} {'Before':<20} {'After':<20} {'Δ':<10}")
        print("-" * 100)
        all_keys = sorted(set(before.keys()) | set(after.keys()))
        for key in all_keys:
            b = before.get(key)
            a = after.get(key)
            if b and a:
                delta = percent_change(b["mean"], a["mean"])
                print(f"{b['name']:<50} {format_time(b['mean']):<20} {format_time(a['mean']):<20} {delta:<10}")
            elif b:
                print(f"{b['name']:<50} {format_time(b['mean']):<20} {'REMOVED':<20} {'-':<10}")
            else:
                print(f"{a['name']:<50} {'NEW':<20} {format_time(a['mean']):<20} {'-':<10}")


if __name__ == "__main__":
    main()
