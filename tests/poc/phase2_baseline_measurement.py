#!/usr/bin/env python3
"""Phase 2: Baseline Measurement (Current LLM-Based Storage Selection)

This module measures the end-to-end accuracy of the CURRENT system approach:
- Direct LLM-based storage selection (without GoRules)
- Same 50 natural language test cases
- Establishes baseline for comparison with GoRules + Parser approach
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Set
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from executive_assistant.config.llm_factory import create_model
from executive_assistant.config.settings import settings


# ============================================================================
# TEST CASES WITH EXPECTED STORAGE SELECTIONS
# ============================================================================

TEST_CASES: List[Dict[str, Any]] = [
    # Memory (5 cases)
    {
        "request": "Remember that I prefer dark mode",
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "request": "I live in Australia timezone",
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "request": "My email is john@example.com",
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "request": "I prefer concise responses",
        "expected_storage": ["memory"],
        "category": "memory"
    },
    {
        "request": "Remember I'm a vegetarian",
        "expected_storage": ["memory"],
        "category": "memory"
    },

    # TDB (10 cases)
    {
        "request": "Track my daily expenses",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "I need a timesheet table",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Create todo list",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Add task to my todos",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Track project milestones",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Maintain customer list",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Keep inventory records",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Store user preferences",
        "expected_storage": ["memory"],
        "category": "tdb"
    },
    {
        "request": "Track habits",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },
    {
        "request": "Monitor daily tasks",
        "expected_storage": ["tdb"],
        "category": "tdb"
    },

    # ADB (10 cases)
    {
        "request": "Analyze monthly spending trends",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Join sales and expenses tables",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Calculate running totals",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Aggregate data by month",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Compare year-over-year metrics",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Perform complex analytics",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Use window functions",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Create pivot tables",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Calculate moving averages",
        "expected_storage": ["adb"],
        "category": "adb"
    },
    {
        "request": "Rank items by score",
        "expected_storage": ["adb"],
        "category": "adb"
    },

    # VDB (10 cases)
    {
        "request": "Search meeting notes by meaning",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Find documentation about APIs",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Look for similar content",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Semantic search in documents",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Find related notes",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Search by context not keywords",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Find discussions about topic",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Retrieve relevant documentation",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Search knowledge base",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },
    {
        "request": "Find articles about concept",
        "expected_storage": ["vdb"],
        "category": "vdb"
    },

    # Files (10 cases)
    {
        "request": "Generate a PDF report",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Export data to CSV",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Save markdown document",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Write configuration file",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Create log file",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Save code snippet",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Export to Excel",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Generate summary document",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Save chart as image",
        "expected_storage": ["files"],
        "category": "files"
    },
    {
        "request": "Write JSON output",
        "expected_storage": ["files"],
        "category": "files"
    },

    # Multi-storage (5 cases)
    {
        "request": "Track expenses and analyze trends",
        "expected_storage": ["adb"],
        "category": "multi",
        "note": "Complex analytics triggers ADB (includes TDB in decision graph)"
    },
    {
        "request": "Track data but also search it semantically",
        "expected_storage": ["tdb", "vdb"],
        "category": "multi",
        "note": "Multi-storage: TDB for tracking + VDB for search"
    },
    {
        "request": "Export report and analyze it",
        "expected_storage": ["files", "adb"],
        "category": "multi",
        "note": "Sequential: Files for export + ADB for analysis"
    },
    {
        "request": "Save preferences and also query them",
        "expected_storage": ["memory"],
        "category": "multi",
        "note": "Memory supports both create and query"
    },
    {
        "request": "Generate report from search results",
        "expected_storage": ["vdb", "files"],
        "category": "multi",
        "note": "Sequential: VDB for search + Files for report"
    }
]


# ============================================================================
# BASELINE: DIRECT LLM STORAGE SELECTION (WITHOUT GoRules)
# ============================================================================

async def baseline_llm_select_storage(request: str, llm) -> Set[str]:
    """
    Direct LLM-based storage selection (CURRENT SYSTEM APPROACH).

    This simulates how the current system works - LLM directly selects storage
    without using GoRules decision engine.

    Args:
        request: Natural language request
        llm: Language model instance

    Returns:
        Set of storage types (e.g., {"tdb"}, {"vdb"}, {"tdb", "vdb"})
    """
    prompt = f"""You are a storage selection expert. Choose the appropriate storage system(s) for this request.

AVAILABLE STORAGE SYSTEMS:

1. **memory** (Key-Value Storage)
   - Use for: User preferences, personal facts, settings, timezone, email
   - Fast key-value lookup
   - Short-lived user data
   - Examples: "Remember I prefer dark mode", "My email is john@example.com"

2. **tdb** (Transactional Database - SQLite)
   - Use for: Simple structured data with CRUD operations
   - Daily tracking: timesheets, expenses, habits, todos, customer lists
   - Frequent updates, simple queries
   - Examples: "Track my daily expenses", "Create todo list"

3. **adb** (Analytics Database - DuckDB)
   - Use for: Complex analytics, aggregations, joins, window functions
   - Monthly/yearly reports, trends analysis
   - Complex SQL operations, pivot tables
   - Examples: "Analyze monthly spending trends", "Join sales and expenses"

4. **vdb** (Vector Database)
   - Use for: Semantic search, finding content by meaning
   - Documents, meeting notes, knowledge base
   - Search by context, not keywords
   - Examples: "Find documentation about APIs", "Semantic search in documents"

5. **files** (File Storage)
   - Use for: Unstructured content, exports, reports, documents
   - PDF reports, CSV exports, markdown files, config files
   - Generated content, code snippets
   - Examples: "Generate a PDF report", "Export data to CSV"

MULTI-STORAGE RULES:
- If request needs BOTH tracking AND analytics → Use "adb" (includes tdb capabilities)
- If request needs tracking AND semantic search → Use both "tdb" and "vdb"
- If request needs export AND analysis → Use "files" and "adb"
- If request needs search AND report → Use "vdb" and "files"

YOUR TASK:
Request: "{request}"

Return ONLY a JSON array of storage systems (no markdown, no explanation):
["memory"] or ["tdb"] or ["adb"] or ["vdb"] or ["files"] or ["tdb", "vdb"] or ["vdb", "files"] etc

JSON:"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        # Parse JSON array from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        storage_list = json.loads(json_str)

        # Normalize to set
        if isinstance(storage_list, list):
            return set(storage_list)
        else:
            return {storage_list}

    except Exception as e:
        print(f"⚠️  Baseline LLM failed for '{request}': {e}")
        return {"unknown"}


# ============================================================================
# GORULES-BASED APPROACH (IMPROVED PARSER + GoRules ENGINE)
# ============================================================================

async def llm_parse_storage_request_improved(request: str, llm) -> Dict[str, Any]:
    """Parse natural language to structured criteria (from Phase 1 improved)."""
    prompt = f"""You are a storage classification expert. Extract storage decision criteria from the user's request.

IMPORTANT RULES:

1. **dataType classification** (based on STORAGE INTENT, not content semantics):
   - "preference": User settings, likes/dislikes, configuration choices
   - "personal_fact": Personal information (email, timezone, birthday, etc.)
   - "structured": General structured data with CRUD operations (default for database storage)
   - "numeric": Numbers, quantities, amounts, metrics
   - "tabular": Spreadsheet/tabular data explicitly mentioned
   - "unstructured": File storage, exports, reports, documents (default for files)
   - "report": Generated reports, summaries

   SPECIAL CASES:
   - File exports (CSV, Excel, JSON, etc.) → Always use "unstructured" (it's a file)
   - Document storage (markdown, config, etc.) → Always use "unstructured" (it's a file)

2. **complexAnalytics** (ONLY if explicitly mentioned):
   - TRUE: "analyze", "aggregate", "pivot", "compare", "trends", "analytics"
   - FALSE: "track", "monitor", "maintain", "keep" (these are CRUD, not analytics)

3. **needsJoins** (ONLY if explicitly mentioned):
   - TRUE: "join", "combine", "merge", "relate" multiple tables

4. **windowFunctions** (ONLY if explicitly mentioned):
   - TRUE: "running total", "moving average", "rank", "lag", "lead"

5. **semanticSearch** vs **searchByMeaning**:
   - semanticSearch=TRUE: Explicit "semantic" keyword or "context" search
   - searchByMeaning=TRUE: "find", "search", "look for", "similar", "related"

Request: "{request}"

Return ONLY a JSON object (no markdown, no explanation):
{{
  "dataType": "preference|personal_fact|structured|numeric|tabular|unstructured|report",
  "complexAnalytics": true|false,
  "needsJoins": true|false,
  "windowFunctions": true|false,
  "semanticSearch": true|false,
  "searchByMeaning": true|false
}}"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        return json.loads(json_str)

    except Exception as e:
        print(f"⚠️  Parsing failed for '{request}': {e}")
        return {
            "dataType": "unknown",
            "complexAnalytics": False,
            "needsJoins": False,
            "windowFunctions": False,
            "semanticSearch": False,
            "searchByMeaning": False
        }


async def gorules_select_storage(criteria: Dict[str, Any]) -> Set[str]:
    """
    GoRules-based storage selection (from decision graph).

    This simulates the GoRules decision engine based on the JDM rules
    in data/rules/storage-selection.json.

    Args:
        criteria: Structured decision criteria

    Returns:
        Set of storage types
    """
    data_type = criteria.get("dataType", "")
    complex_analytics = criteria.get("complexAnalytics", False)
    needs_joins = criteria.get("needsJoins", False)
    window_functions = criteria.get("windowFunctions", False)
    semantic_search = criteria.get("semanticSearch", False)
    search_by_meaning = criteria.get("searchByMeaning", False)

    # Rule priorities (from decision graph)

    # R1: Memory (preference, personal_fact)
    if data_type in ["preference", "personal_fact"]:
        return {"memory"}

    # R2: Multi-storage (structured + analytics + semantic)
    if (data_type in ["structured", "numeric", "tabular"] and
        complex_analytics and semantic_search):
        return {"tdb", "adb", "vdb"}

    # R3: VDB (structured/tabular + semantic search only)
    if (data_type in ["structured", "numeric", "tabular"] and
        not complex_analytics and not needs_joins and
        not window_functions and semantic_search):
        return {"vdb"}

    # R5: ADB (structured + complex analytics)
    if (data_type in ["structured", "numeric", "tabular"] and
        complex_analytics):
        return {"adb"}

    # R6: ADB (structured + needs joins)
    if (data_type in ["structured", "numeric", "tabular"] and
        needs_joins):
        return {"adb"}

    # R7: ADB (structured + window functions)
    if (data_type in ["structured", "numeric", "tabular"] and
        window_functions):
        return {"adb"}

    # R8: TDB (structured/tabular/numeric - default)
    if data_type in ["structured", "numeric", "tabular"]:
        return {"tdb"}

    # R9: VDB (semantic search - any data type)
    if semantic_search:
        return {"vdb"}

    # R10: VDB (search by meaning - any data type)
    if search_by_meaning:
        return {"vdb"}

    # R11: Files (unstructured, report)
    if data_type in ["unstructured", "report"]:
        return {"files"}

    # Default: Files
    return {"files"}


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

def normalize_storage(storage_set: Set[str]) -> Set[str]:
    """Normalize storage names for comparison."""
    normalized = set()
    for s in storage_set:
        s_lower = s.lower().strip()
        normalized.add(s_lower)
    return normalized


def storage_matches(predicted: Set[str], expected: Set[str]) -> bool:
    """
    Check if predicted storage matches expected storage.

    For multi-storage, we accept if:
    - Exact match, OR
    - Predicted is a superset of expected (being conservative is OK)
    """
    pred_norm = normalize_storage(predicted)
    exp_norm = normalize_storage(expected)

    # Exact match
    if pred_norm == exp_norm:
        return True

    # Predicted includes all expected (conservative approach)
    if exp_norm.issubset(pred_norm):
        return True

    return False


async def measure_baseline_accuracy(llm) -> Dict[str, Any]:
    """
    Measure baseline accuracy (direct LLM storage selection).

    Args:
        llm: Language model instance

    Returns:
        Dict with metrics and detailed results
    """
    results = {
        "correct": [],
        "incorrect": [],
        "errors": [],
        "details": []
    }

    print(f"\n{'='*80}")
    print(f"PHASE 2: Baseline Measurement (Direct LLM Storage Selection)")
    print(f"{'='*80}")
    print(f"Total test cases: {len(TEST_CASES)}")
    print(f"\nRunning baseline LLM (direct storage selection)...\n")

    for i, test_case in enumerate(TEST_CASES, 1):
        try:
            # Direct LLM storage selection
            predicted_storage = await baseline_llm_select_storage(test_case["request"], llm)
            expected_storage = set(test_case["expected_storage"])

            # Check if correct
            is_correct = storage_matches(predicted_storage, expected_storage)

            results["correct" if is_correct else "incorrect"].append(i)

            # Log result
            status = "✅" if is_correct else "❌"
            print(f"{status} Test {i:2d}/{len(TEST_CASES)}: {test_case['request']}")
            print(f"   Expected: {sorted(expected_storage)}")
            print(f"   Got:      {sorted(predicted_storage)}")

            # Store details
            results["details"].append({
                "request": test_case["request"],
                "category": test_case["category"],
                "expected_storage": sorted(expected_storage),
                "predicted_storage": sorted(predicted_storage),
                "correct": is_correct
            })

        except Exception as e:
            print(f"❌ Test {i:2d}/{len(TEST_CASES)}: {test_case['request']}")
            print(f"   ERROR: {e}")
            results["errors"].append({
                "test_case": test_case,
                "error": str(e)
            })

    # Calculate metrics
    total_tests = len(TEST_CASES)
    correct_count = len(results["correct"])
    baseline_accuracy = correct_count / total_tests if total_tests > 0 else 0

    return {
        "approach": "baseline_llm_direct",
        "phase": "2",
        "timestamp": int(time.time()),
        "ollama_mode": settings.OLLAMA_MODE,
        "metrics": {
            "accuracy": baseline_accuracy,
            "correct": correct_count,
            "incorrect": len(results["incorrect"]),
            "total_tests": total_tests,
            "error_rate": len(results["errors"]) / total_tests if total_tests > 0 else 0
        },
        "by_category": _calculate_category_accuracy(results["details"]),
        "total_tests": total_tests,
        "errors": results["errors"],
        "test_details": results["details"]
    }


async def measure_gorules_accuracy(llm) -> Dict[str, Any]:
    """
    Measure GoRules-based accuracy (Parser + GoRules Engine).

    Args:
        llm: Language model instance

    Returns:
        Dict with metrics and detailed results
    """
    results = {
        "correct": [],
        "incorrect": [],
        "errors": [],
        "details": []
    }

    print(f"\n{'='*80}")
    print(f"PHASE 2: GoRules-Based Measurement (Parser + Decision Engine)")
    print(f"{'='*80}")
    print(f"Total test cases: {len(TEST_CASES)}")
    print(f"\nRunning improved parser + GoRules engine...\n")

    for i, test_case in enumerate(TEST_CASES, 1):
        try:
            # Step 1: Parse request to criteria
            criteria = await llm_parse_storage_request_improved(test_case["request"], llm)

            # Step 2: GoRules decision engine
            predicted_storage = await gorules_select_storage(criteria)
            expected_storage = set(test_case["expected_storage"])

            # Check if correct
            is_correct = storage_matches(predicted_storage, expected_storage)

            results["correct" if is_correct else "incorrect"].append(i)

            # Log result
            status = "✅" if is_correct else "❌"
            print(f"{status} Test {i:2d}/{len(TEST_CASES)}: {test_case['request']}")
            print(f"   Criteria: {criteria}")
            print(f"   Expected: {sorted(expected_storage)}")
            print(f"   Got:      {sorted(predicted_storage)}")

            # Store details
            results["details"].append({
                "request": test_case["request"],
                "category": test_case["category"],
                "criteria": criteria,
                "expected_storage": sorted(expected_storage),
                "predicted_storage": sorted(predicted_storage),
                "correct": is_correct
            })

        except Exception as e:
            print(f"❌ Test {i:2d}/{len(TEST_CASES)}: {test_case['request']}")
            print(f"   ERROR: {e}")
            results["errors"].append({
                "test_case": test_case,
                "error": str(e)
            })

    # Calculate metrics
    total_tests = len(TEST_CASES)
    correct_count = len(results["correct"])
    gorules_accuracy = correct_count / total_tests if total_tests > 0 else 0

    return {
        "approach": "gorules_based",
        "phase": "2",
        "timestamp": int(time.time()),
        "ollama_mode": settings.OLLAMA_MODE,
        "metrics": {
            "accuracy": gorules_accuracy,
            "correct": correct_count,
            "incorrect": len(results["incorrect"]),
            "total_tests": total_tests,
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


def print_comparison_results(baseline: Dict[str, Any], gorules: Dict[str, Any]) -> None:
    """Print comparison between baseline and GoRules-based approaches."""
    baseline_metrics = baseline["metrics"]
    gorules_metrics = gorules["metrics"]

    print(f"\n{'='*80}")
    print(f"PHASE 2 RESULTS: BASELINE COMPARISON")
    print(f"{'='*80}")

    print(f"\n📊 Overall Accuracy Comparison:")
    print(f"   Baseline (Direct LLM):         {baseline_metrics['accuracy']:.1%} ({baseline_metrics['correct']}/{baseline_metrics['total_tests']})")
    print(f"   GoRules-Based (Parser + Engine): {gorules_metrics['accuracy']:.1%} ({gorules_metrics['correct']}/{gorules_metrics['total_tests']})")

    difference = gorules_metrics['accuracy'] - baseline_metrics['accuracy']
    if difference > 0:
        print(f"   Improvement:                    +{difference:.1%} ✅")
    elif difference < 0:
        print(f"   Regression:                     {difference:.1%} ❌")
    else:
        print(f"   Difference:                     0.0% ➡️")

    print(f"\n📈 By Category:")
    print(f"   {'Category':<12} {'Baseline':<12} {'GoRules':<12} {'Difference'}")
    print(f"   {'-'*50}")
    for category in sorted(set(baseline["by_category"].keys()) | set(gorules["by_category"].keys())):
        baseline_acc = baseline["by_category"].get(category, 0)
        gorules_acc = gorules["by_category"].get(category, 0)
        diff = gorules_acc - baseline_acc
        diff_str = f"{diff:+.1%}"
        if diff > 0:
            diff_str += " ✅"
        elif diff < 0:
            diff_str += " ❌"
        print(f"   {category:<12} {baseline_acc:<12.1%} {gorules_acc:<12.1%} {diff_str}")

    # Success criteria
    print(f"\n{'─'*80}")
    print(f"SUCCESS CRITERIA:")

    baseline_acc = baseline_metrics['accuracy']
    gorules_acc = gorules_metrics['accuracy']

    print(f"\n   Baseline (Direct LLM): {baseline_acc:.1%}")
    if baseline_acc >= 0.70:
        print(f"   ✅ Current system already meets ≥70% threshold")
    elif baseline_acc >= 0.60:
        print(f"   ⚠️  Current system in 60-70% range (acceptable for POC)")
    else:
        print(f"   ❌ Current system below 60% (needs improvement)")

    print(f"\n   GoRules-Based: {gorules_acc:.1%}")
    if gorules_acc >= 0.70:
        print(f"   ✅ GoRules-based system meets ≥70% threshold")
        if gorules_acc > baseline_acc:
            print(f"   🎉 GoRules-based approach improves upon current system!")
    elif gorules_acc >= 0.60:
        print(f"   ⚠️  GoRules-based in 60-70% range (acceptable for POC)")
    else:
        print(f"   ❌ GoRules-based below 60% (needs more work)")

    print(f"\n{'─'*80}")
    print(f"RECOMMENDATION:")

    if gorules_acc >= baseline_acc:
        improvement = gorules_acc - baseline_acc
        print(f"   ✅ GoRules-based approach matches or exceeds baseline")
        print(f"   Improvement: {improvement:.1%}")
        if gorules_acc >= 0.70:
            print(f"   🎉 READY FOR PRODUCTION - Proceed to Phase 3 (Implementation)")
        else:
            print(f"   💡 ACCEPTABLE FOR POC - Consider improvements before production")
    else:
        regression = baseline_acc - gorules_acc
        print(f"   ❌ GoRules-based approach performs worse than baseline")
        print(f"   Regression: {regression:.1%}")
        print(f"   💡 RECOMMENDATION: Improve parser before proceeding")

    print(f"{'='*80}\n")


async def main():
    """Main entry point for Phase 2 baseline measurement."""

    print("="*80)
    print("PHASE 2: BASELINE MEASUREMENT")
    print("Comparing Direct LLM vs GoRules-Based Storage Selection")
    print("="*80)

    # Check Ollama Cloud configuration
    print(f"\n🔍 OLLAMA_MODE: {settings.OLLAMA_MODE}")
    if settings.OLLAMA_MODE == "cloud" and settings.OLLAMA_CLOUD_API_KEY:
        print(f"   ✅ Using Ollama Cloud")
    else:
        print(f"   ⚠️  Check configuration")

    # Initialize LLM
    print(f"\n🔄 Initializing LLM...")
    try:
        llm = create_model(provider="ollama", model="default")
        print("   ✅ Connected")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return

    # Measure baseline (direct LLM)
    baseline_results = await measure_baseline_accuracy(llm)

    # Measure GoRules-based
    gorules_results = await measure_gorules_accuracy(llm)

    # Print comparison
    print_comparison_results(baseline_results, gorules_results)

    # Save results
    output_path = Path("tests/poc/phase2_baseline_measurement.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    combined_results = {
        "baseline": baseline_results,
        "gorules_based": gorules_results,
        "comparison": {
            "baseline_accuracy": baseline_results["metrics"]["accuracy"],
            "gorules_accuracy": gorules_results["metrics"]["accuracy"],
            "difference": gorules_results["metrics"]["accuracy"] - baseline_results["metrics"]["accuracy"]
        }
    }

    with open(output_path, "w") as f:
        json.dump(combined_results, f, indent=2)

    print(f"💾 Results saved to: {output_path}")

    return combined_results


if __name__ == "__main__":
    asyncio.run(main())
