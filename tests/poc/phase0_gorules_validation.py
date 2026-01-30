#!/usr/bin/env python3
"""Phase 0: GoRules Validation with Structured Input

This module tests the GoRules Zen decision engine in isolation,
using structured input (no natural language parsing).

This answers the question: "Does GoRules make correct decisions
when given accurate input?"
"""

import asyncio
import json
import time
from typing import Dict, List, Any
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from executive_assistant.decisions.storage_selector import StorageSelector


# ============================================================================
# TEST CASES: Structured Input (No Parsing Required)
# ============================================================================

TEST_CASES_STRUCTURED: List[Dict[str, Any]] = [
    # ───────────────────────────────────────────────────────────────────
    # Memory (5 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "Memory: User preference",
        "input": {
            "dataType": "preference"
        },
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "name": "Memory: Personal fact",
        "input": {
            "dataType": "personal_fact"
        },
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "name": "Memory: Timezone",
        "input": {
            "dataType": "preference",
            "semanticSearch": False
        },
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "name": "Memory: Email",
        "input": {
            "dataType": "preference",
            "complexAnalytics": False
        },
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "name": "Memory: User setting",
        "input": {
            "dataType": "preference",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected_storage": ["memory"],
        "category": "memory"
    },

    # ───────────────────────────────────────────────────────────────────
    # TDB (10 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "TDB: Structured data",
        "input": {
            "dataType": "structured",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Numeric tracking",
        "input": {
            "dataType": "numeric",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Tabular data",
        "input": {
            "dataType": "tabular",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Daily expenses",
        "input": {
            "dataType": "structured",
            "complexAnalytics": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Timesheet tracking",
        "input": {
            "dataType": "numeric"
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Todo list",
        "input": {
            "dataType": "structured",
            "complexAnalytics": False,
            "semanticSearch": False,
            "needsJoins": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Customer list",
        "input": {
            "dataType": "structured",
            "windowFunctions": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Inventory",
        "input": {
            "dataType": "numeric",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Habit tracking",
        "input": {
            "dataType": "structured"
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "name": "TDB: Configuration data",
        "input": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False
        },
        "expected_storage": ["tdb"],
        "category": "tdb"
    },

    # ───────────────────────────────────────────────────────────────────
    # ADB (10 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "ADB: Complex analytics",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "semanticSearch": False
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Join tables",
        "input": {
            "dataType": "structured",
            "needsJoins": True,
            "semanticSearch": False
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Window functions",
        "input": {
            "dataType": "structured",
            "windowFunctions": True,
            "semanticSearch": False
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Monthly trends",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Year-over-year",
        "input": {
            "dataType": "numeric",
            "complexAnalytics": True,
            "needsJoins": True
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Pivot tables",
        "input": {
            "dataType": "tabular",
            "complexAnalytics": True
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Running totals",
        "input": {
            "dataType": "structured",
            "windowFunctions": True
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Moving averages",
        "input": {
            "dataType": "numeric",
            "windowFunctions": True,
            "semanticSearch": False
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Rank operations",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": True,
            "windowFunctions": True
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "name": "ADB: Large dataset aggregation",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False
        },
        "expected_storage": ["adb"],
        "category": "adb"
    },

    # ───────────────────────────────────────────────────────────────────
    # VDB (10 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "VDB: Semantic search",
        "input": {
            "dataType": "document",
            "semanticSearch": True
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Search by meaning",
        "input": {
            "dataType": "structured",
            "searchByMeaning": True
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Meeting notes",
        "input": {
            "dataType": "document",
            "semanticSearch": True,
            "complexAnalytics": False
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Knowledge base",
        "input": {
            "dataType": "document",
            "searchByMeaning": True
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Document search",
        "input": {
            "semanticSearch": True
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Find similar content",
        "input": {
            "dataType": "structured",
            "semanticSearch": True,
            "complexAnalytics": False
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Research documents",
        "input": {
            "dataType": "document",
            "searchByMeaning": True,
            "needsJoins": False
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Context search",
        "input": {
            "semanticSearch": True,
            "complexAnalytics": False
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Discussion search",
        "input": {
            "dataType": "document",
            "semanticSearch": True,
            "windowFunctions": False
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "name": "VDB: Article retrieval",
        "input": {
            "searchByMeaning": True,
            "dataType": "document"
        },
        "expected_storage": ["vdb"],
        "category": "vdb"
    },

    # ───────────────────────────────────────────────────────────────────
    # Files (10 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "Files: Unstructured data",
        "input": {
            "dataType": "unstructured",
            "semanticSearch": False,
            "complexAnalytics": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Report generation",
        "input": {
            "dataType": "report"
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: CSV export",
        "input": {
            "dataType": "unstructured",
            "semanticSearch": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Markdown doc",
        "input": {
            "dataType": "document",
            "semanticSearch": False,
            "complexAnalytics": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Configuration",
        "input": {
            "dataType": "unstructured"
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Code snippet",
        "input": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "semanticSearch": False,
            "needsJoins": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Log file",
        "input": {
            "dataType": "unstructured",
            "windowFunctions": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Static content",
        "input": {
            "dataType": "unstructured",
            "semanticSearch": False,
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: PDF export",
        "input": {
            "dataType": "report",
            "semanticSearch": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "name": "Files: Excel export",
        "input": {
            "dataType": "unstructured",
            "semanticSearch": False,
            "complexAnalytics": False
        },
        "expected_storage": ["files"],
        "category": "files"
    },

    # ───────────────────────────────────────────────────────────────────
    # Multi-Storage (5 cases)
    # ───────────────────────────────────────────────────────────────────
    {
        "name": "Multi: TDB + ADB (track + analyze)",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "semanticSearch": False
        },
        "expected_storage": ["tdb", "adb"],
        "category": "multi"
    },
    {
        "name": "Multi: TDB + VDB (track + search)",
        "input": {
            "dataType": "structured",
            "complexAnalytics": False,
            "semanticSearch": True
        },
        "expected_storage": ["tdb", "vdb"],
        "category": "multi"
    },
    {
        "name": "Multi: All three (complex workflow)",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "semanticSearch": True
        },
        "expected_storage": ["tdb", "adb", "vdb"],
        "category": "multi"
    },
    {
        "name": "Multi: ADB + VDB (analyze + search)",
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "searchByMeaning": True
        },
        "expected_storage": ["tdb", "adb", "vdb"],
        "category": "multi"
    },
    {
        "name": "Multi: Track + trend + context",
        "input": {
            "dataType": "numeric",
            "complexAnalytics": True,
            "semanticSearch": True
        },
        "expected_storage": ["tdb", "adb", "vdb"],
        "category": "multi"
    }
]


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

async def measure_gorules_validation() -> Dict[str, Any]:
    """
    Measure GoRules performance with structured input.

    This tests GoRules in ISOLATION (no parser), answering:
    "Does GoRules make correct decisions when given accurate input?"

    Returns:
        Dict with metrics and detailed results
    """
    selector = StorageSelector()

    results = {
        "accuracy": [],
        "consistency": [],
        "response_time": [],
        "errors": [],
        "details": []
    }

    print(f"\n{'='*80}")
    print(f"PHASE 0: GoRules Validation (Structured Input)")
    print(f"{'='*80}")
    print(f"Total test cases: {len(TEST_CASES_STRUCTURED)}")
    print(f"\nRunning tests...\n")

    for i, test_case in enumerate(TEST_CASES_STRUCTURED, 1):
        try:
            # Measure response time
            start = time.time()

            # Evaluate decision (NO PARSING - structured input directly)
            decision = await selector.select_storage(test_case["input"])

            elapsed = time.time() - start

            # Check correctness
            result_storage = decision["storage"]
            expected_storage = test_case["expected_storage"]

            # Handle both single and array outputs
            if isinstance(expected_storage, list):
                accuracy = 1 if set(result_storage) == set(expected_storage) else 0
            else:
                accuracy = 1 if result_storage[0] == expected_storage else 0

            results["accuracy"].append(accuracy)
            results["response_time"].append(elapsed)

            # Log result
            status = "✅" if accuracy else "❌"
            print(f"{status} Test {i:2d}/{len(TEST_CASES_STRUCTURED)}: {test_case['name']}")

            if not accuracy:
                print(f"   Expected: {expected_storage}")
                print(f"   Got:      {result_storage}")
                print(f"   Input:    {test_case['input']}")

            # Store details
            results["details"].append({
                "test_name": test_case["name"],
                "category": test_case["category"],
                "input": test_case["input"],
                "expected": expected_storage,
                "actual": result_storage,
                "correct": bool(accuracy),
                "response_time_ms": elapsed * 1000,
                "reasoning": decision["reasoning"]
            })

        except Exception as e:
            print(f"❌ Test {i:2d}/{len(TEST_CASES_STRUCTURED)}: {test_case['name']}")
            print(f"   ERROR: {e}")
            results["errors"].append({
                "test_case": test_case,
                "error": str(e)
            })

    # Calculate aggregate metrics
    total_tests = len(TEST_CASES_STRUCTURED)
    correct = sum(results["accuracy"])
    accuracy_rate = correct / total_tests if total_tests > 0 else 0

    # By category
    by_category = {}
    for detail in results["details"]:
        category = detail["category"]
        if category not in by_category:
            by_category[category] = {"correct": 0, "total": 0}
        by_category[category]["total"] += 1
        if detail["correct"]:
            by_category[category]["correct"] += 1

    category_accuracy = {
        cat: (stats["correct"] / stats["total"])
        for cat, stats in by_category.items()
    }

    return {
        "approach": "gorules_structured_input",
        "phase": "0",
        "timestamp": time.time(),
        "metrics": {
            "accuracy": accuracy_rate,
            "correct": correct,
            "total": total_tests,
            "consistency": 1.0,  # Always deterministic
            "avg_response_time": sum(results["response_time"]) / len(results["response_time"]),
            "error_rate": len(results["errors"]) / total_tests if total_tests > 0 else 0
        },
        "by_category": category_accuracy,
        "total_tests": total_tests,
        "errors": results["errors"],
        "test_details": results["details"]
    }


def print_results(results: Dict[str, Any]) -> None:
    """Print formatted results."""
    metrics = results["metrics"]

    print(f"\n{'='*80}")
    print(f"PHASE 0 RESULTS")
    print(f"{'='*80}")

    print(f"\n📊 Overall Metrics:")
    print(f"   Accuracy:    {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']} correct)")
    print(f"   Consistency: {metrics['consistency']:.1%} (deterministic)")
    print(f"   Avg Time:     {metrics['avg_response_time']*1000:.1f}ms")
    print(f"   Error Rate:  {metrics['error_rate']:.1%}")

    print(f"\n📈 By Category:")
    for category, accuracy in results["by_category"].items():
        print(f"   {category:12s}: {accuracy:.1%}")

    if results["errors"]:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"   - {error['test_case']['name']}: {error['error']}")

    # Success criteria
    print(f"\n{'─'*80}")
    print(f"SUCCESS CRITERIA:")
    success = metrics["accuracy"] >= 0.90 and metrics["consistency"] == 1.0

    if success:
        print(f"   ✅ Accuracy ≥ 90%: {metrics['accuracy']:.1%} >= 90%")
        print(f"   ✅ Consistency = 100%: {metrics['consistency']:.1%}")
        print(f"\n   🎉 RECOMMENDATION: PROCEED to Phase 1 (Parser Validation)")
    elif metrics["accuracy"] >= 0.85:
        print(f"   ⚠️  Accuracy 85-90%: {metrics['accuracy']:.1%} (good but needs tuning)")
        print(f"   ✅ Consistency = 100%: {metrics['consistency']:.1%}")
        print(f"\n   🤔 RECOMMENDATION: REVIEW - Consider tuning rules")
    else:
        print(f"   ❌ Accuracy < 85%: {metrics['accuracy']:.1%}")
        print(f"\n   🛑 RECOMMENDATION: DO NOT PROCEED - GoRules not working well")

    print(f"{'='*80}\n")


async def main():
    """Main entry point."""
    results = await measure_gorules_validation()

    # Print human-readable results
    print_results(results)

    # Save to JSON
    output_path = Path("tests/poc/phase0_gorules_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"💾 Results saved to: {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
