#!/usr/bin/env python3
"""Phase 1: LLM-Based Parser Validation (Ollama Cloud)

This module tests an Ollama Cloud-based LLM parser for extracting structured decision criteria
from natural language requests.
"""

import asyncio
import json
import time
from typing import Dict, List, Any
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from executive_assistant.config.llm_factory import create_model
from executive_assistant.config.settings import settings


# ============================================================================
# LABELED TEST CASES (Same as before)
# ============================================================================

LABELED_TEST_CASES: List[Dict[str, Any]] = [
    # Memory (5 cases)
    {
        "request": "Remember that I prefer dark mode",
        "correct_criteria": {
            "dataType": "preference",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "memory"
    },
    {
        "request": "I live in Australia timezone",
        "correct_criteria": {
            "dataType": "personal_fact",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "memory"
    },
    {
        "request": "My email is john@example.com",
        "correct_criteria": {
            "dataType": "personal_fact",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "memory"
    },
    {
        "request": "I prefer concise responses",
        "correct_criteria": {
            "dataType": "preference",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "memory"
    },
    {
        "request": "Remember I'm a vegetarian",
        "correct_criteria": {
            "dataType": "personal_fact",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "memory"
    },

    # TDB (10 cases)
    {
        "request": "Track my daily expenses",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "I need a timesheet table",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Create todo list",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Add task to my todos",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Track project milestones",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Maintain customer list",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Keep inventory records",
        "correct_criteria": {
            "dataType": "numeric",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Store user preferences",
        "correct_criteria": {
            "dataType": "preference",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Track habits",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },
    {
        "request": "Monitor daily tasks",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "tdb"
    },

    # ADB (10 cases)
    {
        "request": "Analyze monthly spending trends",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Join sales and expenses tables",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": True,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Calculate running totals",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": True,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Aggregate data by month",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Compare year-over-year metrics",
        "correct_criteria": {
            "dataType": "numeric",
            "complexAnalytics": True,
            "needsJoins": True,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Perform complex analytics",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Use window functions",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": True,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Create pivot tables",
        "correct_criteria": {
            "dataType": "tabular",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Calculate moving averages",
        "correct_criteria": {
            "dataType": "numeric",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": True,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },
    {
        "request": "Rank items by score",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": True,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "adb"
    },

    # VDB (10 cases)
    {
        "request": "Search meeting notes by meaning",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": True,
            "searchByMeaning": False
        },
        "category": "vdb"
    },
    {
        "request": "Find documentation about APIs",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Look for similar content",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Semantic search in documents",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": True,
            "searchByMeaning": False
        },
        "category": "vdb"
    },
    {
        "request": "Find related notes",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Search by context not keywords",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": True,
            "searchByMeaning": False
        },
        "category": "vdb"
    },
    {
        "request": "Find discussions about topic",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Retrieve relevant documentation",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Search knowledge base",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },
    {
        "request": "Find articles about concept",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "vdb"
    },

    # Files (10 cases)
    {
        "request": "Generate a PDF report",
        "correct_criteria": {
            "dataType": "report",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Export data to CSV",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Save markdown document",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Write configuration file",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Create log file",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Save code snippet",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Export to Excel",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Generate summary document",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Save chart as image",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },
    {
        "request": "Write JSON output",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "files"
    },

    # Multi-storage (5 cases)
    {
        "request": "Track expenses and analyze trends",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "multi"
    },
    {
        "request": "Track data but also search it semantically",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": True,
            "searchByMeaning": False
        },
        "category": "multi"
    },
    {
        "request": "Export report and analyze it",
        "correct_criteria": {
            "dataType": "unstructured",
            "complexAnalytics": True,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "multi"
    },
    {
        "request": "Save preferences and also query them",
        "correct_criteria": {
            "dataType": "preference",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        },
        "category": "multi"
    },
    {
        "request": "Generate report from search results",
        "correct_criteria": {
            "dataType": "document",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": True
        },
        "category": "multi"
    }
]


# ============================================================================
# LLM-BASED PARSER (Ollama)
# ============================================================================

async def llm_parse_storage_request(request: str, llm) -> Dict[str, Any]:
    """
    Use Ollama LLM to extract structured criteria from natural language.

    Args:
        request: Natural language request string
        llm: Ollama chat model instance

    Returns:
        Dict with decision criteria
    """
    prompt = f"""You are a storage classification expert. Extract storage decision criteria from this request:

Request: "{request}"

Return ONLY a JSON object (no markdown, no explanation) with these exact fields:
{{
  "dataType": "preference|personal_fact|structured|numeric|tabular|document|unstructured|report|unknown",
  "complexAnalytics": true|false,
  "needsJoins": true|false,
  "windowFunctions": true|false,
  "semanticSearch": true|false,
  "searchByMeaning": true|false
}}

Rules:
- dataType "preference": user settings, likes/dislikes, configuration choices
- dataType "personal_fact": personal information (email, timezone, birthday, etc.)
- dataType "structured": general structured data with CRUD operations
- dataType "numeric": numbers, quantities, amounts, metrics
- dataType "tabular": tabular/spreadsheet data
- dataType "document": documents, notes, articles, knowledge base content
- dataType "unstructured": files, reports, exports, code snippets
- dataType "report": generated reports, summaries, documents
- complexAnalytics true: analyze, aggregate, pivot, compare trends
- needsJoins true: join, combine, merge, relate multiple tables
- windowFunctions true: running totals, moving averages, rank, lag/lead
- semanticSearch true: semantic search, search by meaning, context search
- searchByMeaning true: find similar, find related, search by concept

JSON:"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        # Parse JSON from response
        # Handle both raw JSON and markdown code blocks
        if "```json" in content:
            # Extract from markdown code block
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            # Extract from markdown code block (no language specified)
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            # Raw JSON
            json_str = content.strip()

        return json.loads(json_str)

    except Exception as e:
        print(f"⚠️  LLM parsing failed for '{request}': {e}")
        # Return default fallback
        return {
            "dataType": "unknown",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        }


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

async def measure_llm_parser_accuracy(llm) -> Dict[str, Any]:
    """
    Measure LLM parser accuracy against labeled test cases.

    Args:
        llm: Language model instance

    Returns:
        Dict with metrics and detailed results
    """
    results = {
        "dataType_accuracy": [],
        "complexAnalytics_accuracy": [],
        "needsJoins_accuracy": [],
        "windowFunctions_accuracy": [],
        "semanticSearch_accuracy": [],
        "searchByMeaning_accuracy": [],
        "overall_accuracy": [],
        "errors": [],
        "details": []
    }

    print(f"\n{'='*80}")
    print(f"PHASE 1: LLM-Based Parser Validation (Ollama Cloud)")
    print(f"Mode: {settings.OLLAMA_MODE}")
    print(f"{'='*80}")
    print(f"Total test cases: {len(LABELED_TEST_CASES)}")
    print(f"\nRunning LLM parser (this may take a few minutes)...\n")

    for i, test_case in enumerate(LABELED_TEST_CASES, 1):
        try:
            # Parse request using LLM
            parsed = await llm_parse_storage_request(test_case["request"], llm)
            correct = test_case["correct_criteria"]

            # Measure each criterion
            data_type_acc = 1 if parsed["dataType"] == correct["dataType"] else 0
            analytics_acc = 1 if parsed["complexAnalytics"] == correct.get("complexAnalytics", False) else 0
            joins_acc = 1 if parsed["needsJoins"] == correct.get("needsJoins", False) else 0
            window_acc = 1 if parsed["windowFunctions"] == correct.get("windowFunctions", False) else 0
            semantic_acc = 1 if parsed["semanticSearch"] == correct.get("semanticSearch", False) else 0
            meaning_acc = 1 if parsed["searchByMeaning"] == correct.get("searchByMeaning", False) else 0

            # Overall accuracy (all criteria correct)
            overall_acc = 1 if all([
                data_type_acc,
                analytics_acc,
                joins_acc,
                window_acc,
                semantic_acc,
                meaning_acc
            ]) else 0

            results["dataType_accuracy"].append(data_type_acc)
            results["complexAnalytics_accuracy"].append(analytics_acc)
            results["needsJoins_accuracy"].append(joins_acc)
            results["windowFunctions_accuracy"].append(window_acc)
            results["semanticSearch_accuracy"].append(semantic_acc)
            results["searchByMeaning_accuracy"].append(meaning_acc)
            results["overall_accuracy"].append(overall_acc)

            # Log result
            status = "✅" if overall_acc else "❌"
            print(f"{status} Test {i:2d}/{len(LABELED_TEST_CASES)}: {test_case['request']}")

            if not overall_acc:
                print(f"   Expected: {correct}")
                print(f"   Got:      {parsed}")

            # Store details
            results["details"].append({
                "request": test_case["request"],
                "category": test_case["category"],
                "expected": correct,
                "actual": parsed,
                "correct": bool(overall_acc),
                "per_field": {
                    "dataType": bool(data_type_acc),
                    "complexAnalytics": bool(analytics_acc),
                    "needsJoins": bool(joins_acc),
                    "windowFunctions": bool(window_acc),
                    "semanticSearch": bool(semantic_acc),
                    "searchByMeaning": bool(meaning_acc)
                }
            })

        except Exception as e:
            print(f"❌ Test {i:2d}/{len(LABELED_TEST_CASES)}: {test_case['request']}")
            print(f"   ERROR: {e}")
            results["errors"].append({
                "test_case": test_case,
                "error": str(e)
            })

    # Calculate aggregate metrics
    total_tests = len(LABELED_TEST_CASES)
    overall_accuracy = sum(results["overall_accuracy"]) / total_tests if total_tests > 0 else 0

    return {
        "approach": "llm_parser_ollama_cloud",
        "phase": "1",
        "timestamp": int(time.time()),
        "ollama_mode": settings.OLLAMA_MODE,
        "metrics": {
            "overall_accuracy": overall_accuracy,
            "dataType_accuracy": sum(results["dataType_accuracy"]) / len(results["dataType_accuracy"]),
            "complexAnalytics_accuracy": sum(results["complexAnalytics_accuracy"]) / len(results["complexAnalytics_accuracy"]),
            "needsJoins_accuracy": sum(results["needsJoins_accuracy"]) / len(results["needsJoins_accuracy"]),
            "windowFunctions_accuracy": sum(results["windowFunctions_accuracy"]) / len(results["windowFunctions_accuracy"]),
            "semanticSearch_accuracy": sum(results["semanticSearch_accuracy"]) / len(results["semanticSearch_accuracy"]),
            "searchByMeaning_accuracy": sum(results["searchByMeaning_accuracy"]) / len(results["searchByMeaning_accuracy"]),
            "total_tests": total_tests,
            "correct": sum(results["overall_accuracy"]),
            "error_rate": len(results["errors"]) / total_tests if total_tests > 0 else 0
        },
        "by_category": _calculate_category_accuracy(results["details"]),
        "total_tests": total_tests,
        "errors": results["errors"],
        "test_details": results["details"]
    }


def _calculate_category_accuracy(details: List[Dict]) -> Dict[str, float]:
    """Calculate accuracy by category."""
    by_category = {}
    for detail in details:
        category = detail["category"]
        if category not in by_category:
            by_category[category] = {"correct": 0, "total": 0}
        by_category[category]["total"] += 1
        if detail["correct"]:
            by_category[category]["correct"] += 1

    return {
        cat: (stats["correct"] / stats["total"])
        for cat, stats in by_category.items()
    }


def print_results(results: Dict[str, Any]) -> None:
    """Print formatted results."""
    metrics = results["metrics"]

    print(f"\n{'='*80}")
    print(f"PHASE 1 RESULTS (LLM Parser - Ollama Cloud)")
    print(f"Mode: {results.get('ollama_mode', 'unknown')}")
    print(f"{'='*80}")

    print(f"\n📊 Overall Metrics:")
    print(f"   Overall Accuracy:   {metrics['overall_accuracy']:.1%} ({metrics['correct']}/{metrics['total_tests']} correct)")
    print(f"   Error Rate:         {metrics['error_rate']:.1%}")

    print(f"\n📈 Per-Field Accuracy:")
    print(f"   dataType:           {metrics['dataType_accuracy']:.1%}")
    print(f"   complexAnalytics:   {metrics['complexAnalytics_accuracy']:.1%}")
    print(f"   needsJoins:         {metrics['needsJoins_accuracy']:.1%}")
    print(f"   windowFunctions:    {metrics['windowFunctions_accuracy']:.1%}")
    print(f"   semanticSearch:     {metrics['semanticSearch_accuracy']:.1%}")
    print(f"   searchByMeaning:    {metrics['searchByMeaning_accuracy']:.1%}")

    print(f"\n📈 By Category:")
    for category, accuracy in results["by_category"].items():
        print(f"   {category:12s}: {accuracy:.1%}")

    if results["errors"]:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"   - {error['test_case']['request']}: {error['error']}")

    # Success criteria
    print(f"\n{'─'*80}")
    print(f"SUCCESS CRITERIA:")

    accuracy = metrics['overall_accuracy']

    if accuracy >= 0.85:
        print(f"   ✅ Parser Accuracy ≥ 85%: {accuracy:.1%}")
        print(f"\n   🎉 RECOMMENDATION: PROCEED to Phase 2 (Baseline Measurement)")
    elif accuracy >= 0.70:
        print(f"   ⚠️  Parser Accuracy 70-85%: {accuracy:.1%}")
        print(f"   ✅ RECOMMENDATION: ACCEPTABLE - LLM parser meets minimum threshold")
    else:
        print(f"   ❌ Parser Accuracy < 70%: {accuracy:.1%}")
        print(f"\n   🛑 RECOMMENDATION: RECONSIDER - Parser is still a bottleneck")

    print(f"{'='*80}\n")


async def main():
    """Main entry point for Ollama Cloud-based LLM parser validation."""

    print("="*80)
    print("PHASE 1: LLM-Based Parser Validation (Ollama Cloud)")
    print("="*80)

    # Check Ollama Cloud configuration
    print(f"\n🔍 Checking Ollama Cloud configuration...")
    print(f"   OLLAMA_MODE: {settings.OLLAMA_MODE}")

    if settings.OLLAMA_MODE == "cloud":
        if not settings.OLLAMA_CLOUD_API_KEY:
            print("❌ OLLAMA_CLOUD_API_KEY not set for cloud mode!")
            print("   Set OLLAMA_CLOUD_API_KEY in your .env file or environment")
            print("   Or use OLLAMA_MODE=local for local Ollama (no API key required)")
            return
        print(f"   OLLAMA_CLOUD_URL: {settings.OLLAMA_CLOUD_URL}")
        print(f"   ✅ API key configured")
    else:
        print(f"   OLLAMA_LOCAL_URL: {settings.OLLAMA_LOCAL_URL}")
        print(f"   ℹ️  Local mode - make sure Ollama is running locally")

    # Get model name for Ollama
    try:
        from executive_assistant.config.llm_factory import _get_model_config, _get_ollama_config
        model_name = _get_model_config("ollama", "default")
        base_url, _, api_key = _get_ollama_config("default")
        print(f"\n📦 Model configuration:")
        print(f"   Model: {model_name}")
        print(f"   Base URL: {base_url}")
        if api_key:
            print(f"   API Key: {'*' * 20}{api_key[-4:]}")
    except Exception as e:
        print(f"⚠️  Could not determine model configuration: {e}")
        print("   Using default configuration...")
        model_name = "llama3.2"

    # Initialize Ollama LLM using factory
    print(f"\n🔄 Initializing Ollama LLM ({model_name})...")
    try:
        llm = create_model(provider="ollama", model="default")
        # Test connection with a simple call
        print("   Testing connection...")
        test_response = await llm.ainvoke("Respond with just 'OK':")
        if "OK" not in test_response.content:
            print("⚠️  Warning: Ollama not responding as expected")
        else:
            print("   ✅ Connection successful")
    except Exception as e:
        print(f"❌ Failed to initialize Ollama: {e}")
        if settings.OLLAMA_MODE == "local":
            print("   Make sure Ollama is running: ollama serve")
        else:
            print("   Check your OLLAMA_CLOUD_API_KEY and network connection")
        return

    results = await measure_llm_parser_accuracy(llm)

    # Print human-readable results
    print_results(results)

    # Save to JSON
    output_path = Path("tests/poc/phase1_llm_parser_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"💾 Results saved to: {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
