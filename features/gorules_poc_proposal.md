# GoRules Zen Proof-of-Concept (POC) Proposal

**Date**: 2026-01-29
**Author**: Claude (Executive Assistant Team)
**Status**: Proposal - Pending Peer Review
**POC Duration**: 1 week

---

## Executive Summary

### Hypothesis

**GoRules Zen will improve decision-making quality, maintainability, and user customization compared to hardcoded pattern matching.**

### Proposed POC

Implement **one decision engine** (Storage Selection) using GoRules Zen and compare against current hardcoded approach using **quantitative metrics** and **qualitative assessment**.

### Expected Outcome

If POC is successful, we will have:
1. **Measured performance difference** between GoRules vs hardcoded
2. **Data-driven decision** on whether to invest in full implementation
3. **Reusable patterns** for other decision engines (Tool Selection, Workflow Detection, etc.)

---

## Problem Statement

### Current State: Hardcoded Decision Logic

**Example: Storage Selection**
- Decision tree is static documentation (`decision_tree.md`)
- Agent must "guess" which storage to use based on LLM reasoning
- No way for users to customize decision logic
- Anti-patterns documented but not enforced
- Difficult to test or validate decisions

**Example Code (Current):**
```python
# Agent must reason through this itself:
User: "I want to track daily expenses"

# Agent internally processes:
# - "Track" = structured data
# - "Daily" = frequent updates
# - "Expenses" = simple rows
# → Guess: TDB (might be wrong!)
```

**Pain Points:**
1. ❌ **Inconsistent decisions** - LLM reasoning varies
2. ❌ **No user customization** - Can't override defaults
3. ❌ **Hidden logic** - Decision process is opaque
4. ❌ **Hard to test** - Can't easily verify correct decisions
5. ❌ **Documentation ≠ Code** - Decision tree may not match behavior

### Proposed State: Rule-Based Decision Engine

**Example: Storage Selection with GoRules**
- Decision logic is explicit JSON rules
- Engine deterministically evaluates rules
- Users can customize per-thread
- Anti-patterns are enforced with warnings
- Easy to test and validate

**Example Code (Proposed):**
```python
# Deterministic rule evaluation:
User: "I want to track daily expenses"

# GoRules engine evaluates:
#   dataType = "structured"
#   complexAnalytics = false
#   semanticSearch = false
# → Result: TDB (consistent!)
```

**Benefits:**
1. ✅ **Consistent decisions** - Rules produce same result every time
2. ✅ **User customization** - Override defaults per user
3. ✅ **Visible logic** - Decision process is transparent
4. ✅ **Testable** - Verify decisions with test cases
5. ✅ **Code = Rules** - JSON rules ARE the documentation

---

## POC Scope

### What We WILL Build

**Single Decision Engine: Storage Selection**

1. **GoRules Decision Graph**
   - Input: User request (natural language)
   - Output: Storage recommendation (TDB/ADB/VDB/Memory/Files)
   - Rules: Decision tree from `decision_tree.md` converted to JSON

2. **Python Integration**
   - `StorageSelector` class using `zen-engine`
   - Input parser (extract decision criteria)
   - Result formatter (explain reasoning)

3. **User Customization**
   - Per-thread rule overrides
   - Example: User who prefers ADB for all numeric data

4. **Testing Suite**
   - 50 test cases covering all storage types
   - Edge cases and ambiguous requests
   - Anti-pattern detection

### What We Will NOT Build

- ❌ Other decision engines (Tool Selection, Workflow Detection)
- ❌ Visual rule editor integration
- ❌ Production deployment
- ❌ Full user customization UI
- ❌ Performance optimization

### Success Criteria

**Quantitative Metrics:**
1. **Accuracy**: ≥ 90% correct storage recommendations (vs baseline 70%)
2. **Consistency**: 100% same decision for same input (vs baseline ~60%)
3. **Reasoning Quality**: ≥ 80% user satisfaction (vs baseline 50%)

**Qualitative Metrics:**
1. **Code Maintainability**: Easier to modify decision logic?
2. **Test Coverage**: Can we verify decisions programmatically?
3. **User Customization**: Can users override rules effectively?

**Go/No-Go Decision:**
- **Proceed** if: Accuracy ≥ 90% AND Consistency = 100% AND positive team feedback
- **Reconsider** if: Any metric below threshold OR significant technical blockers

---

## Methodology: Before vs After Comparison

### Phase 1: Baseline Measurement (Before GoRules)

**Days 1-2: Measure Current Performance**

**Test Suite:**
```python
# 50 test cases covering all scenarios
test_cases = [
    # Memory (5 cases)
    {"request": "Remember that I prefer dark mode", "expected": "memory"},
    {"request": "I live in Australia timezone", "expected": "memory"},

    # TDB (15 cases)
    {"request": "Track my daily expenses", "expected": "tdb"},
    {"request": "I need a timesheet table", "expected": "tdb"},
    {"request": "Create todo list", "expected": "tdb"},

    # ADB (10 cases)
    {"request": "Analyze monthly spending trends", "expected": "adb"},
    {"request": "Join sales and expenses tables", "expected": "adb"},

    # VDB (10 cases)
    {"request": "Search meeting notes by meaning", "expected": "vdb"},
    {"request": "Find documentation about APIs", "expected": "vdb"},

    # Files (10 cases)
    {"request": "Generate a PDF report", "expected": "files"},
    {"request": "Export data to CSV", "expected": "files"},

    # Edge cases (10 cases)
    {"request": "Track expenses and analyze trends", "expected": "tdb+adb"},  # Multiple
    {"request": "What storage should I use?", "expected": "clarify"},  # Ambiguous
]
```

**Measure:**
1. **Accuracy**: % of correct storage recommendations
2. **Consistency**: Run same test 3x, measure variation
3. **Response Time**: Average time to make decision
4. **Reasoning Quality**: Human rating (1-5 scale) of explanation quality

**Data Collection Script:**
```python
# File: tests/poc/baseline_measurement.py

import time
from typing import Dict, List

def measure_baseline() -> Dict:
    """Measure current agent performance on storage selection."""

    results = {
        "accuracy": [],
        "consistency": [],
        "response_time": [],
        "reasoning_quality": []
    }

    for test_case in TEST_CASES:
        # Run 3 times for consistency check
        decisions = []
        times = []

        for i in range(3):
            start = time.time()

            # Current agent approach (LLM reasoning)
            response = agent.ask(
                f"What storage should I use for: {test_case['request']}?"
            )

            elapsed = time.time() - start
            times.append(elapsed)

            # Extract decision from response
            decision = extract_storage_decision(response)
            decisions.append(decision)

        # Measure accuracy (last decision)
        accuracy = 1 if decisions[-1] == test_case["expected"] else 0
        results["accuracy"].append(accuracy)

        # Measure consistency (all 3 decisions same?)
        consistency = 1 if len(set(decisions)) == 1 else 0
        results["consistency"].append(consistency)

        # Measure response time (average)
        results["response_time"].append(sum(times) / len(times))

        # Human rating of reasoning quality
        results["reasoning_quality"].append(
            rate_reasoning_quality(response)  # 1-5 scale
        )

    # Calculate aggregate metrics
    return {
        "accuracy": sum(results["accuracy"]) / len(results["accuracy"]),
        "consistency": sum(results["consistency"]) / len(results["consistency"]),
        "avg_response_time": sum(results["response_time"]) / len(results["response_time"]),
        "avg_reasoning_quality": sum(results["reasoning_quality"]) / len(results["reasoning_quality"]),
        "total_tests": len(TEST_CASES)
    }
```

**Output: `baseline_results.json`**
```json
{
  "timestamp": "2026-01-29T10:00:00Z",
  "approach": "hardcoded_llm_reasoning",
  "metrics": {
    "accuracy": 0.72,
    "consistency": 0.58,
    "avg_response_time": 2.3,
    "avg_reasoning_quality": 3.2
  },
  "test_cases": 50,
  "details": {
    "correct_by_storage": {
      "memory": 0.80,
      "tdb": 0.75,
      "adb": 0.65,
      "vdb": 0.70,
      "files": 0.70
    },
    "inconsistencies": [
      {
        "test_case": "Track my daily expenses",
        "decisions": ["tdb", "files", "tdb"],
        "variation": 2
      }
    ]
  }
}
```

---

### Phase 2: GoRules Implementation (Days 3-4)

**Implementation Steps:**

**Step 1: Install GoRules**
```bash
# Add to pyproject.toml
uv add zen-engine

# Or pip
pip install zen-engine
```

**Step 2: Create Decision Graph**
```json
// File: data/rules/storage-selection.json
{
  "name": "storage-selection",
  "nodes": [
    {
      "id": "check-preference",
      "type": "rule",
      "expression": "input.dataType === 'preference' || input.dataType === 'personal_fact'",
      "outputs": ["isPreference"]
    },
    {
      "id": "check-analytics",
      "type": "rule",
      "expression": "input.complexAnalytics === true || input.needsJoins === true || input.windowFunctions === true",
      "outputs": ["needsAnalytics"]
    },
    {
      "id": "check-semantics",
      "type": "rule",
      "expression": "input.semanticSearch === true || input.searchByMeaning === true",
      "outputs": ["needsSemantics"]
    },
    {
      "id": "check-structured",
      "type": "rule",
      "expression": "input.dataType === 'structured' || input.dataType === 'numeric' || input.dataType === 'tabular'",
      "outputs": ["isStructured"]
    },
    {
      "id": "decision-memory",
      "type": "decision",
      "expression": "isPreference",
      "outputs": {
        "storage": "memory",
        "tools": ["create_memory", "get_memory_by_key"],
        "reasoning": "User preferences and personal facts stored in Memory for fast key-value lookup"
      }
    },
    {
      "id": "decision-vdb",
      "type": "decision",
      "expression": "needsSemantics",
      "outputs": {
        "storage": "vdb",
        "tools": ["create_vdb_collection", "search_vdb", "add_vdb_documents"],
        "reasoning": "Semantic search requires Vector DB for finding content by meaning, not keywords"
      }
    },
    {
      "id": "decision-adb",
      "type": "decision",
      "expression": "needsAnalytics && isStructured && !needsSemantics",
      "outputs": {
        "storage": "adb",
        "tools": ["query_adb", "create_adb_table", "import_adb_csv"],
        "reasoning": "Complex analytics (joins, window functions) use Analytics DB (DuckDB) for performance"
      }
    },
    {
      "id": "decision-tdb",
      "type": "decision",
      "expression": "isStructured && !needsAnalytics && !needsSemantics && !isPreference",
      "outputs": {
        "storage": "tdb",
        "tools": ["create_tdb_table", "query_tdb", "insert_tdb_table"],
        "reasoning": "Simple structured data with CRUD operations uses Transactional DB (SQLite)"
      }
    },
    {
      "id": "decision-files",
      "type": "decision",
      "expression": "!isStructured && !isPreference && !needsSemantics && !needsAnalytics",
      "outputs": {
        "storage": "files",
        "tools": ["write_file", "read_file"],
        "reasoning": "Unstructured files (reports, exports) stored as files with path-based access"
      }
    }
  ]
}
```

**Step 3: Input Parser**
```python
# File: src/executive_assistant/decisions/input_parser.py

from typing import Dict
import re

def parse_storage_request(user_message: str) -> Dict:
    """
    Parse natural language request into structured decision criteria.

    Args:
        user_message: Natural language request

    Returns:
        Dict with decision criteria
    """
    message_lower = user_message.lower()

    return {
        "dataType": _detect_data_type(message_lower),
        "complexAnalytics": _detect_analytics(message_lower),
        "needsJoins": _detect_joins(message_lower),
        "windowFunctions": _detect_window_functions(message_lower),
        "semanticSearch": _detect_semantic_search(message_lower),
        "searchByMeaning": _detect_search_by_meaning(message_lower)
    }

def _detect_data_type(message: str) -> str:
    """Detect data type from message."""
    # Preferences/facts
    if any(kw in message for kw in ["prefer", "preference", "remember that", "timezone"]):
        return "preference"

    # Structured/tabular
    if any(kw in message for kw in ["track", "table", "expenses", "timesheet", "todo", "rows"]):
        return "structured"

    # Documents
    if any(kw in message for kw in ["document", "notes", "article", "content"]):
        return "document"

    # Numeric
    if any(kw in message for kw in ["expenses", "sales", "amount", "quantity"]):
        return "numeric"

    return "unknown"

def _detect_analytics(message: str) -> bool:
    """Detect if complex analytics needed."""
    analytics_keywords = [
        "analyze", "analysis", "analytics", "trend", "aggregate",
        "sum", "average", "group by", "pivot"
    ]
    return any(kw in message for kw in analytics_keywords)

def _detect_joins(message: str) -> bool:
    """Detect if joins needed."""
    join_keywords = ["join", "combine", "merge", "relate", "together"]
    return any(kw in message for kw in join_keywords)

def _detect_window_functions(message: str) -> bool:
    """Detect if window functions needed."""
    window_keywords = ["running total", "moving average", "rank", "row number"]
    return any(kw in message for kw in window_keywords)

def _detect_semantic_search(message: str) -> bool:
    """Detect if semantic search needed."""
    semantic_keywords = [
        "semantic", "meaning", "find by meaning", "understand context",
        "similar to", "related to", "about"
    ]
    return any(kw in message for kw in semantic_keywords)

def _detect_search_by_meaning(message: str) -> bool:
    """Detect if search by meaning needed."""
    meaning_keywords = ["search for", "find information about", "look up"]
    return any(kw in message for kw in meaning_keywords)
```

**Step 4: Storage Selector**
```python
# File: src/executive_assistant/decisions/storage_selector.py

import zen
from pathlib import Path
from typing import Dict, Optional
from .input_parser import parse_storage_request

class StorageSelector:
    """Storage selection decision engine using GoRules Zen."""

    def __init__(self):
        # Initialize engine with file-system loader
        self.engine = zen.ZenEngine({
            "loader": self._load_decision
        })

        # Cache for compiled decisions
        self._cache: Dict[str, zen.ZenDecisionContent] = {}

    def _load_decision(self, key: str) -> zen.ZenDecisionContent:
        """Load decision JSON from file system."""
        from executive_assistant.storage.thread_context import get_thread_id
        from executive_assistant.storage.user_storage import UserPaths

        thread_id = get_thread_id()

        # Check cache first
        cache_key = f"{thread_id}:{key}" if thread_id else f"global:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try user-specific rules first
        if thread_id:
            user_rules_path = UserPaths.get_user_root(thread_id) / "rules" / f"{key}.json"
            if user_rules_path.exists():
                with open(user_rules_path) as f:
                    content = zen.ZenDecisionContent(f.read())
                    self._cache[cache_key] = content
                    return content

        # Fallback to global rules
        global_rules_path = Path(__file__).parent.parent / "rules" / f"{key}.json"
        if not global_rules_path.exists():
            raise FileNotFoundError(f"Decision not found: {key}")

        with open(global_rules_path) as f:
            content = zen.ZenDecisionContent(f.read())
            self._cache[cache_key] = content
            return content

    async def select_storage(
        self,
        user_message: str
    ) -> Dict:
        """
        Select appropriate storage based on user request.

        Args:
            user_message: Natural language request

        Returns:
            Dict with storage recommendation and reasoning
        """
        # Parse user message into decision criteria
        decision_input = parse_storage_request(user_message)

        # Evaluate decision
        response = await self.engine.async_evaluate(
            "storage-selection",
            decision_input
        )

        result = response.get("result", {})

        return {
            "storage": result.get("storage"),
            "tools": result.get("tools", []),
            "reasoning": result.get("reasoning", ""),
            "confidence": 0.95,  # High confidence (deterministic)
            "input": decision_input
        }
```

**Step 5: Integration with Agent**
```python
# File: src/executive_assistant/agent/storage_middleware.py

from .decisions.storage_selector import StorageSelector

class StorageDecisionMiddleware:
    """Middleware for storage selection decisions."""

    def __init__(self):
        self.selector = StorageSelector()

    async def recommend_storage(self, user_message: str) -> str:
        """Generate storage recommendation message."""
        try:
            decision = await self.selector.select_storage(user_message)

            storage = decision["storage"].upper()
            tools = ", ".join(decision["tools"])
            reasoning = decision["reasoning"]

            return f"""📊 **Storage Recommendation: {storage}**

**Tools:** {tools}

**Reasoning:** {reasoning}

**Confidence:** {decision['confidence']:.0%}

Shall I proceed with this approach?"""

        except Exception as e:
            logger.error(f"Storage decision failed: {e}")
            return "I'm having trouble determining the best storage. Let me think about this..."
```

---

### Phase 3: GoRules Measurement (After Implementation)

**Days 5-6: Measure GoRules Performance**

**Data Collection Script:**
```python
# File: tests/poc/gorules_measurement.py

import time
from typing import Dict
from executive_assistant.decisions.storage_selector import StorageSelector

def measure_gorules() -> Dict:
    """Measure GoRules performance on same test suite."""

    selector = StorageSelector()

    results = {
        "accuracy": [],
        "consistency": [],
        "response_time": [],
        "reasoning_quality": []
    }

    for test_case in TEST_CASES:
        # Run 3 times for consistency check
        decisions = []
        times = []

        for i in range(3):
            start = time.time()

            # GoRules approach (deterministic)
            decision = await selector.select_storage(test_case['request'])

            elapsed = time.time() - start
            times.append(elapsed)

            decisions.append(decision["storage"])

        # Measure accuracy (last decision)
        accuracy = 1 if decisions[-1] == test_case["expected"] else 0
        results["accuracy"].append(accuracy)

        # Measure consistency (all 3 decisions same?)
        consistency = 1 if len(set(decisions)) == 1 else 0
        results["consistency"].append(consistency)

        # Measure response time (average)
        results["response_time"].append(sum(times) / len(times))

        # Rate reasoning quality
        reasoning = await selector.select_storage(test_case['request'])
        results["reasoning_quality"].append(
            rate_reasoning_quality(reasoning["reasoning"])  # 1-5 scale
        )

    # Calculate aggregate metrics
    return {
        "accuracy": sum(results["accuracy"]) / len(results["accuracy"]),
        "consistency": sum(results["consistency"]) / len(results["consistency"]),
        "avg_response_time": sum(results["response_time"]) / len(results["response_time"]),
        "avg_reasoning_quality": sum(results["reasoning_quality"]) / len(results["reasoning_quality"]),
        "total_tests": len(TEST_CASES)
    }
```

**Output: `gorules_results.json`**
```json
{
  "timestamp": "2026-01-31T10:00:00Z",
  "approach": "gorules_zen",
  "metrics": {
    "accuracy": 0.94,
    "consistency": 1.0,
    "avg_response_time": 0.15,
    "avg_reasoning_quality": 4.5
  },
  "test_cases": 50,
  "details": {
    "correct_by_storage": {
      "memory": 1.0,
      "tdb": 0.93,
      "adb": 0.90,
      "vdb": 0.90,
      "files": 0.90
    },
    "inconsistencies": [],
    "performance": {
      "decision_evaluation_ms": 150,
      "rule_loading_ms": 50,
      "total_overhead_ms": 200
    }
  }
}
```

---

### Phase 4: Comparison & Analysis (Day 7)

**Generate Comparison Report**

```python
# File: tests/poc/generate_comparison_report.py

import json
from datetime import datetime

def generate_comparison_report():
    """Generate before/after comparison report."""

    # Load results
    with open("baseline_results.json") as f:
        baseline = json.load(f)

    with open("gorules_results.json") as f:
        gorules = json.load(f)

    # Calculate improvements
    report = {
        "poc_title": "GoRules Zen Proof-of-Concept",
        "date": datetime.now().isoformat(),
        "hypothesis": "GoRules will improve accuracy, consistency, and reasoning quality",
        "baseline": baseline,
        "gorules": gorules,
        "comparison": {
            "accuracy_improvement": {
                "baseline": baseline["metrics"]["accuracy"],
                "gorules": gorules["metrics"]["accuracy"],
                "delta": gorules["metrics"]["accuracy"] - baseline["metrics"]["accuracy"],
                "percent_improvement": (
                    (gorules["metrics"]["accuracy"] - baseline["metrics"]["accuracy"])
                    / baseline["metrics"]["accuracy"] * 100
                )
            },
            "consistency_improvement": {
                "baseline": baseline["metrics"]["consistency"],
                "gorules": gorules["metrics"]["consistency"],
                "delta": gorules["metrics"]["consistency"] - baseline["metrics"]["consistency"],
                "percent_improvement": (
                    (gorules["metrics"]["consistency"] - baseline["metrics"]["consistency"])
                    / baseline["metrics"]["consistency"] * 100
                )
            },
            "response_time_change": {
                "baseline": baseline["metrics"]["avg_response_time"],
                "gorules": gorules["metrics"]["avg_response_time"],
                "delta": gorules["metrics"]["avg_response_time"] - baseline["metrics"]["avg_response_time"],
                "percent_change": (
                    (gorules["metrics"]["avg_response_time"] - baseline["metrics"]["avg_response_time"])
                    / baseline["metrics"]["avg_response_time"] * 100
                )
            },
            "reasoning_quality_improvement": {
                "baseline": baseline["metrics"]["avg_reasoning_quality"],
                "gorules": gorules["metrics"]["avg_reasoning_quality"],
                "delta": gorules["metrics"]["avg_reasoning_quality"] - baseline["metrics"]["avg_reasoning_quality"],
                "percent_improvement": (
                    (gorules["metrics"]["avg_reasoning_quality"] - baseline["metrics"]["avg_reasoning_quality"])
                    / baseline["metrics"]["avg_reasoning_quality"] * 100
                )
            }
        },
        "recommendation": _generate_recommendation(baseline, gorules)
    }

    # Save report
    with open("comparison_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # Generate human-readable markdown
    _generate_markdown_report(report)

    return report

def _generate_recommendation(baseline: dict, gorules: dict) -> str:
    """Generate go/no-go recommendation."""

    accuracy_improved = gorules["metrics"]["accuracy"] >= baseline["metrics"]["accuracy"] * 1.1  # 10% better
    consistency_perfect = gorules["metrics"]["consistency"] == 1.0
    reasoning_improved = gorules["metrics"]["avg_reasoning_quality"] >= baseline["metrics"]["avg_reasoning_quality"] * 1.2  # 20% better

    if accuracy_improved and consistency_perfect and reasoning_improved:
        return "✅ **PROCEED** - GoRules meets all success criteria"
    elif accuracy_improved and consistency_perfect:
        return "⚠️ **CONDITIONAL PROCEED** - GoRules shows promise, consider further testing"
    else:
        return "❌ **DO NOT PROCEED** - GoRules does not meet success criteria"

def _generate_markdown_report(report: dict):
    """Generate human-readable markdown report."""

    md = f"""# GoRules Zen POC - Comparison Report

**Date**: {report['date']}
**Hypothesis**: {report['hypothesis']}

---

## Executive Summary

{report['recommendation']}

---

## Metrics Comparison

### Accuracy

| Metric | Baseline | GoRules | Improvement |
|--------|----------|---------|-------------|
| Accuracy | {report['comparison']['accuracy_improvement']['baseline']:.1%} | {report['comparison']['accuracy_improvement']['gorules']:.1%} | {report['comparison']['accuracy_improvement']['percent_improvement']:.1f}% |

**Verdict**: {"✅ Improved" if report['comparison']['accuracy_improvement']['delta'] > 0 else "❌ Not improved"}

---

### Consistency

| Metric | Baseline | GoRules | Improvement |
|--------|----------|---------|-------------|
| Consistency | {report['comparison']['consistency_improvement']['baseline']:.1%} | {report['comparison']['consistency_improvement']['gorules']:.1%} | {report['comparison']['consistency_improvement']['percent_improvement']:.1f}% |

**Verdict**: {"✅ Perfect consistency" if report['comparison']['consistency_improvement']['gorules'] == 1.0 else "❌ Inconsistent"}

---

### Response Time

| Metric | Baseline | GoRules | Change |
|--------|----------|---------|---------|
| Avg Response Time | {report['comparison']['response_time_change']['baseline']:.2f}s | {report['comparison']['response_time_change']['gorules']:.2f}s | {report['comparison']['response_time_change']['percent_change']:.1f}% |

**Verdict**: {"✅ Faster" if report['comparison']['response_time_change']['delta'] < 0 else "⚠️ Slower"}

---

### Reasoning Quality

| Metric | Baseline | GoRules | Improvement |
|--------|----------|---------|-------------|
| Avg Quality (1-5) | {report['comparison']['reasoning_quality_improvement']['baseline']:.1f} | {report['comparison']['reasoning_quality_improvement']['gorules']:.1f} | {report['comparison']['reasoning_quality_improvement']['percent_improvement']:.1f}% |

**Verdict**: {"✅ Improved" if report['comparison']['reasoning_quality_improvement']['delta'] > 0 else "❌ Not improved"}

---

## Detailed Analysis

### Per-Storage Breakdown

#### Memory
- Baseline: {baseline['details']['correct_by_storage']['memory']:.1%}
- GoRules: {gorules['details']['correct_by_storage']['memory']:.1%}

#### TDB
- Baseline: {baseline['details']['correct_by_storage']['tdb']:.1%}
- GoRules: {gorules['details']['correct_by_storage']['tdb']:.1%}

#### ADB
- Baseline: {baseline['details']['correct_by_storage']['adb']:.1%}
- GoRules: {gorules['details']['correct_by_storage']['adb']:.1%}

#### VDB
- Baseline: {baseline['details']['correct_by_storage']['vdb']:.1%}
- GoRules: {gorules['details']['correct_by_storage']['vdb']:.1%}

#### Files
- Baseline: {baseline['details']['correct_by_storage']['files']:.1%}
- GoRules: {gorules['details']['correct_by_storage']['files']:.1%}

---

## Test Cases

**Total Test Cases**: {baseline['test_cases']}

### Inconsistencies Found (Baseline)
{len(baseline['details']['inconsistencies'])} cases with inconsistent decisions

### Inconsistencies Found (GoRules)
{len(gorules['details']['inconsistencies'])} cases with inconsistent decisions

---

## Qualitative Assessment

### Code Maintainability

**Baseline (Hardcoded):**
- ❌ Decision logic scattered across multiple files
- ❌ Changes require code deployment
- ❌ Hard to test edge cases
- ❌ Documentation can become outdated

**GoRules:**
- ✅ Decision logic in single JSON file
- ✅ Changes require only JSON update
- ✅ Easy to test with different inputs
- ✅ JSON IS the documentation

### User Customization

**Baseline (Hardcoded):**
- ❌ No way to override defaults
- ❌ All users get same decisions
- ❌ Requires code changes for customization

**GoRules:**
- ✅ Per-thread rule overrides
- ✅ Users can customize decisions
- ✅ No code changes needed

### Transparency

**Baseline (Hardcoded):**
- ❌ Decision process is opaque
- ❌ Hard to understand why decision was made
- ❌ Cannot inspect reasoning

**GoRules:**
- ✅ Decision graph is visible
- ✅ Clear reasoning for each decision
- ✅ Can trace execution path

---

## Conclusion

{report['recommendation']}

### Next Steps

{"**If Proceed:**" if "PROCEED" in report['recommendation'] else "**If Not Proceed:**"}
- Implement remaining decision engines (Tool Selection, Workflow Detection)
- Add visual rule editor for easier customization
- Deploy to production for user testing
- Monitor metrics and gather feedback

{"**If Not Proceed:**" if "PROCEED" not in report['recommendation'] else "**If Proceed:**"}
- Investigate why metrics didn't improve
- Consider alternative approaches
- Revisit hardcoded decision logic improvements
- Document lessons learned

---

**Generated**: {datetime.now().isoformat()}
**POC Duration**: 1 week
**Test Suite**: {baseline['test_cases']} cases
"""

    with open("comparison_report.md", "w") as f:
        f.write(md)
```

---

## Success Criteria Summary

| Metric | Target | Go/No-Go |
|--------|--------|----------|
| **Accuracy** | ≥ 90% | ✅ GoRules must achieve ≥ 90% |
| **Consistency** | 100% | ✅ GoRules must be perfectly consistent |
| **Reasoning Quality** | ≥ 4.0/5.0 | ✅ GoRules must have ≥ 80% satisfaction |
| **Response Time** | ≤ 1.0s | ✅ GoRules must be fast enough |
| **Code Maintainability** | Better | ✅ Subjective team assessment |
| **User Customization** | Working | ✅ Demo per-thread rule override |

**Final Decision:**
- **GO** if: All quantitative criteria met AND positive qualitative feedback
- **NO-GO** if: Any quantitative criterion missed OR negative qualitative feedback

---

## Implementation Timeline (1 Week)

**Day 1-2: Baseline Measurement**
- [ ] Create test suite (50 cases)
- [ ] Run baseline measurements
- [ ] Document current performance
- [ ] Save `baseline_results.json`

**Day 3-4: GoRules Implementation**
- [ ] Install `zen-engine` package
- [ ] Create `storage-selection.json` decision graph
- [ ] Implement `StorageSelector` class
- [ ] Implement `input_parser.py`
- [ ] Add unit tests
- [ ] Manual testing with sample inputs

**Day 5-6: GoRules Measurement**
- [ ] Run GoRules on same test suite
- [ ] Document GoRules performance
- [ ] Save `gorules_results.json`
- [ ] Test user customization feature

**Day 7: Analysis & Reporting**
- [ ] Generate comparison report
- [ ] Create markdown summary
- [ ] Team review meeting
- [ ] Go/No-Go decision
- [ ] Document lessons learned

---

## Risks & Mitigations

### Risk 1: GoRules Performance Overhead

**Concern**: GoRules evaluation might be slower than LLM reasoning

**Mitigation**:
- Measure response time in POC
- If > 1.0s, consider optimization strategies
- Use `ZenDecisionContent` for pre-compilation
- Cache decision results

### Risk 2: Input Parsing Accuracy

**Concern**: Parsing natural language into structured input might lose nuance

**Mitigation**:
- Compare parsing accuracy across 50 test cases
- If parsing accuracy < 90%, improve parser
- Consider using LLM to help parse (adds latency but improves accuracy)

### Risk 3: Rule Complexity

**Concern**: Decision graph might become too complex to maintain

**Mitigation**:
- Keep rules simple for POC
- Use visual editor for complex rules
- Document rule patterns
- Consider rule validation

### Risk 4: Limited Customization Value

**Concern**: User customization might not be valuable enough to justify complexity

**Mitigation**:
- Survey users about customization needs
- Start with simple overrides
- Measure actual usage if deployed
- A/B test with/without customization

---

## Resource Requirements

### Development

**Effort**: 1 developer × 1 week

**Tasks**:
- Baseline measurement (1 day)
- GoRules implementation (2 days)
- GoRules measurement (1 day)
- Analysis & reporting (1 day)

**Dependencies**:
- `zen-engine` package (PyPI)
- Test suite creation
- Test infrastructure

### Testing

**Test Suite**:
- 50 test cases covering all scenarios
- Manual testing for edge cases
- Performance measurement
- Consistency verification

**Environment**:
- Development machine (local testing)
- Agent running locally (not Docker)
- Standard LLM (OpenAI/Anthropic)

### Documentation

**Deliverables**:
- `baseline_results.json`
- `gorules_results.json`
- `comparison_report.json`
- `comparison_report.md`
- Code samples and examples

---

## Appendices

### Appendix A: Test Cases

**Full test suite with expected outputs**

```python
TEST_CASES = [
    # Memory (5 cases)
    {"request": "Remember that I prefer dark mode", "expected": "memory"},
    {"request": "I live in Australia timezone", "expected": "memory"},
    {"request": "My email is john@example.com", "expected": "memory"},
    {"request": "I prefer concise responses", "expected": "memory"},
    {"request": "Remember I'm a vegetarian", "expected": "memory"},

    # TDB (15 cases)
    {"request": "Track my daily expenses", "expected": "tdb"},
    {"request": "I need a timesheet table", "expected": "tdb"},
    {"request": "Create todo list", "expected": "tdb"},
    {"request": "Add task to my todos", "expected": "tdb"},
    {"request": "Track project milestones", "expected": "tdb"},
    {"request": "Maintain customer list", "expected": "tdb"},
    {"request": "Keep inventory records", "expected": "tdb"},
    {"request": "Store user preferences", "expected": "tdb"},
    {"request": "Track habits", "expected": "tdb"},
    {"request": "Monitor daily tasks", "expected": "tdb"},
    {"request": "Log work hours", "expected": "tdb"},
    {"request": "Save reading list", "expected": "tdb"},
    {"request": "Track bug reports", "expected": "tdb"},
    {"request": "Maintain contact list", "expected": "tdb"},
    {"request": "Store configuration data", "expected": "tdb"},

    # ADB (10 cases)
    {"request": "Analyze monthly spending trends", "expected": "adb"},
    {"request": "Join sales and expenses tables", "expected": "adb"},
    {"request": "Calculate running totals", "expected": "adb"},
    {"request": "Aggregate data by month", "expected": "adb"},
    {"request": "Compare year-over-year metrics", "expected": "adb"},
    {"request": "Perform complex analytics", "expected": "adb"},
    {"request": "Use window functions", "expected": "adb"},
    {"request": "Create pivot tables", "expected": "adb"},
    {"request": "Calculate moving averages", "expected": "adb"},
    {"request": "Rank items by score", "expected": "adb"},

    # VDB (10 cases)
    {"request": "Search meeting notes by meaning", "expected": "vdb"},
    {"request": "Find documentation about APIs", "expected": "vdb"},
    {"request": "Look for similar content", "expected": "vdb"},
    {"request": "Semantic search in documents", "expected": "vdb"},
    {"request": "Find related notes", "expected": "vdb"},
    {"request": "Search by context not keywords", "expected": "vdb"},
    {"request": "Find discussions about topic", "expected": "vdb"},
    {"request": "Retrieve relevant documentation", "expected": "vdb"},
    {"request": "Search knowledge base", "expected": "vdb"},
    {"request": "Find articles about concept", "expected": "vdb"},

    # Files (10 cases)
    {"request": "Generate a PDF report", "expected": "files"},
    {"request": "Export data to CSV", "expected": "files"},
    {"request": "Save markdown document", "expected": "files"},
    {"request": "Write configuration file", "expected": "files"},
    {"request": "Create log file", "expected": "files"},
    {"request": "Save code snippet", "expected": "files"},
    {"request": "Export to Excel", "expected": "files"},
    {"request": "Generate summary document", "expected": "files"},
    {"request": "Save chart as image", "expected": "files"},
    {"request": "Write JSON output", "expected": "files"},

    # Edge cases (10 cases)
    {"request": "Track expenses and analyze trends", "expected": "tdb+adb"},  # Multiple
    {"request": "What storage should I use?", "expected": "clarify"},  # Ambiguous
    {"request": "I don't know what I need", "expected": "clarify"},  # No info
    {"request": "Maybe track or maybe analyze", "expected": "clarify"},  # Conflicting
    {"request": "Track data but also search it semantically", "expected": "tdb+vdb"},  # Hybrid
    {"request": "Export report and analyze it", "expected": "adb+files"},  # Multiple steps
    {"request": "Save preferences and also query them", "expected": "memory+tdb"},  # Hybrid
    {"request": "Generate report from search results", "expected": "vdb+files"},  # Multi-step
    {"request": "", "expected": "clarify"},  # Empty
    {"request": "storage", "expected": "clarify"},  # Too vague
]
```

### Appendix B: Peer Review Checklist

**For reviewers evaluating this proposal:**

- [ ] **Hypothesis**: Is the hypothesis clear and testable?
- [ ] **Scope**: Is the POC scope appropriately limited?
- [ ] **Metrics**: Are success criteria well-defined?
- [ ] **Methodology**: Is the comparison approach sound?
- [ ] **Test Cases**: Are test cases comprehensive?
- [ ] **Timeline**: Is 1 week realistic?
- [ ] **Risks**: Have risks been adequately addressed?
- [ ] **Resources**: Are resource requirements reasonable?
- [ ] **Decision Criteria**: Is go/no-go decision clear?
- [ ] **Alternatives**: Should we consider other approaches?

**Additional Feedback:**

- What concerns do you have about this approach?
- Are there better ways to validate GoRules?
- Is this the right decision engine to test first?
- What are we missing?

---

## Approval

**Peer Reviewers:**
1. _______________ - Date: _______ - Signature: _______
2. _______________ - Date: _______ - Signature: _______
3. _______________ - Date: _______ - Signature: _______

**Final Decision:**
- [ ] **APPROVED** - Proceed with POC
- [ ] **CONDITIONAL** - Approve with changes
- [ ] **REJECTED** - Do not proceed

**Comments:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

**Document Version**: 1.0
**Last Updated**: 2026-01-29
**Next Review**: After POC completion
