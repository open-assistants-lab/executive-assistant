# GoRules Zen Proof-of-Concept (REVISED)

**Date**: 2026-01-29
**Version**: 2.0 (Revised based on peer review)
**Status**: Proposal - Pending Approval
**Duration**: 1 week (de-risked into phases)

---

## Executive Summary

### What Changed in v2.0

**v1.0 Issues:**
- ❌ Tested parser + GoRules together (couldn't isolate failures)
- ❌ 90% accuracy target unrealistic given parsing ambiguity
- ❌ Multi-storage decisions not supported
- ❌ Tool names didn't match reality
- ❌ Reasoning quality metric subjective

**v2.0 Improvements:**
- ✅ **Phased approach** - Test GoRules in isolation first
- ✅ **Realistic targets** - 85% accuracy, focus on consistency
- ✅ **Parser validation** - Measure separately before combining
- ✅ **Multi-storage support** - Arrays in decision outputs
- ✅ **Tool audit** - Align with actual tool registry
- ✅ **Defined rubric** - Clear reasoning quality scoring

---

## Hypothesis (Refined)

**Primary Hypothesis:**
> GoRules Zen will provide **consistent, transparent decisions** with **user customization** that improves decision quality over time.

**Secondary Hypothesis:**
> GoRules will achieve **≥85% decision accuracy** when given structured input, validating the decision engine independently of parsing.

**Success is defined by:**
1. **Consistency**: 100% (same input → same output, every time)
2. **Accuracy**: ≥85% (correct storage/workflow choice)
3. **User Customization**: Users can override rules effectively
4. **Performance**: ≤1.0s decision time

**Note**: We're de-emphasizing "accuracy improvement over baseline" because:
- Baseline (LLM reasoning) is already pretty good (~70%)
- The REAL value is consistency and customization, not marginal accuracy gains
- Storage selection has inherently ambiguous cases (multiple valid answers)

---

## POC Design: Phased Approach

### **Phase 0: GoRules Validation (Days 1-2)** ⭐ START HERE

**Objective**: Test GoRules decision engine in isolation (no parser)

**Input**: Structured decision criteria (not natural language)

**Test Cases**:
```python
TEST_CASES_STRUCTURED = [
    # Memory (5 cases)
    {
        "input": {"dataType": "preference"},
        "expected": "memory",
        "reasoning": "User preferences stored in Memory"
    },
    {
        "input": {"dataType": "personal_fact"},
        "expected": "memory",
        "reasoning": "Personal facts stored in Memory"
    },

    # TDB (10 cases)
    {
        "input": {
            "dataType": "structured",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected": "tdb",
        "reasoning": "Simple structured data → TDB"
    },
    {
        "input": {
            "dataType": "numeric",
            "complexAnalytics": False,
            "semanticSearch": False
        },
        "expected": "tdb",
        "reasoning": "Numeric tracking → TDB"
    },

    # ADB (10 cases)
    {
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": True
        },
        "expected": "adb",
        "reasoning": "Complex analytics with joins → ADB"
    },
    {
        "input": {
            "dataType": "structured",
            "windowFunctions": True
        },
        "expected": "adb",
        "reasoning": "Window functions → ADB"
    },

    # VDB (10 cases)
    {
        "input": {
            "dataType": "document",
            "semanticSearch": True
        },
        "expected": "vdb",
        "reasoning": "Semantic search for documents → VDB"
    },
    {
        "input": {
            "dataType": "structured",
            "searchByMeaning": True
        },
        "expected": "vdb",
        "reasoning": "Search by meaning → VDB"
    },

    # Files (10 cases)
    {
        "input": {
            "dataType": "unstructured",
            "semanticSearch": False,
            "complexAnalytics": False
        },
        "expected": "files",
        "reasoning": "Unstructured files → Files"
    },
    {
        "input": {
            "dataType": "report",
        },
        "expected": "files",
        "reasoning": "Reports stored as files"
    },

    # Multi-storage (5 cases)
    {
        "input": {
            "dataType": "structured",
            "complexAnalytics": True,
            "semanticSearch": True
        },
        "expected": ["tdb", "adb", "vdb"],
        "reasoning": "Multi-step: Track in TDB, analyze in ADB, search in VDB"
    }
]
```

**Metrics**:
- ✅ Accuracy: % correct storage decisions
- ✅ Consistency: 100% (deterministic)
- ✅ Performance: Decision time in ms
- ✅ Reasoning: Quality of explanation

**Success Criteria**:
- **PROCEED** if: Accuracy ≥ 90%, Consistency = 100%
- **REVIEW** if: Accuracy 85-90% (good but not excellent)
- **STOP** if: Accuracy < 85% (GoRules not working well)

**Deliverable**: `phase0_gorules_validation.json`

---

### **Phase 1: Parser Validation (Day 3)**

**Objective**: Measure parser accuracy independently

**Approach**:
1. Manually label 50 natural language requests with correct criteria
2. Implement parser (regex or LLM-based)
3. Measure parser accuracy against labels

**Labeled Test Cases**:
```python
LABELED_TEST_CASES = [
    {
        "request": "Track my daily expenses",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": False,
            "semanticSearch": False
        }
    },
    {
        "request": "Analyze monthly spending trends",
        "correct_criteria": {
            "dataType": "structured",
            "complexAnalytics": True,
            "needsJoins": False
        }
    },
    {
        "request": "Search meeting notes by meaning",
        "correct_criteria": {
            "dataType": "document",
            "semanticSearch": True
        }
    },
    # ... 50 labeled cases
]
```

**Metrics**:
- Parser accuracy: % criteria extracted correctly
- Per-criteria accuracy: dataType, complexAnalytics, etc.
- Error analysis: Common mistakes

**Success Criteria**:
- **PROCEED** if: Parser accuracy ≥ 85%
- **IMPROVE** if: Parser accuracy 70-85% (use LLM classifier)
- **RECONSIDER** if: Parser accuracy < 70% (parsing is bottleneck)

**Deliverable**: `phase1_parser_validation.json`

**If parser < 85% accurate**:
```python
# Option A: Use LLM for parsing
async def llm_parse_storage_request(user_message: str) -> dict:
    """Use LLM to extract structured criteria."""

    prompt = f"""
Extract storage decision criteria from this request:
"{user_message}"

Return JSON:
{{
    "dataType": "preference|structured|document|numeric|unstructured",
    "complexAnalytics": true|false,
    "needsJoins": true|false,
    "windowFunctions": true|false,
    "semanticSearch": true|false,
    "searchByMeaning": true|false
}}
"""

    response = await llm.invoke(prompt)
    return json.loads.response)
```

---

### **Phase 2: Baseline Measurement (Day 4)**

**Objective**: Measure current LLM reasoning performance

**Test Cases**: Same 50 natural language requests from Phase 1

**Measurement**:
```python
for test_case in LABELED_TEST_CASES:
    # Current approach: Agent reasons through request
    response = agent.ask(f"What storage should I use for: {test_case['request']}?")

    # Extract decision
    decision = extract_storage_decision(response)

    # Measure
    accuracy = (decision == test_case["correct_storage"])
    reasoning_quality = rate_reasoning(response)
```

**Metrics**:
- Accuracy: % correct storage
- Consistency: Run 3x, measure variation
- Response time
- Reasoning quality (with rubric)

**Deliverable**: `phase2_baseline_measurement.json`

---

### **Phase 3: GoRules End-to-End (Day 5)**

**Objective**: Measure GoRules with parser (full pipeline)

**Test Cases**: Same 50 from Phase 2

**Measurement**:
```python
for test_case in LABELED_TEST_CASES:
    # Parse request
    criteria = parser.parse(test_case["request"])

    # GoRules decision
    decision = await gorules_engine.async_evaluate(
        "storage-selection",
        criteria
    )

    # Measure
    accuracy = (decision["storage"] == test_case["correct_storage"])
    consistency = 1.0  # Should be deterministic
    reasoning_quality = rate_reasoning(decision["reasoning"])
```

**Deliverable**: `phase3_gorules_e2e.json`

---

### **Phase 4: Comparison & Analysis (Days 6-7)**

**Objective**: Generate comparison report and make go/no-go decision

**Comparison**:
```python
comparison = {
    "phase0_gorules_validation": {
        "accuracy": 0.92,
        "consistency": 1.0,
        "note": "GoRules engine works perfectly with structured input"
    },
    "phase1_parser_validation": {
        "accuracy": 0.78,
        "note": "Parser is bottleneck - need LLM classifier"
    },
    "phase2_baseline": {
        "accuracy": 0.70,
        "consistency": 0.58,
        "note": "Current LLM reasoning is inconsistent"
    },
    "phase3_gorules_e2e": {
        "accuracy": 0.82,
        "consistency": 1.0,
        "note": "GoRules + parser = better consistency, similar accuracy"
    }
}
```

**Go/No-Go Decision**:

```
✅ PROCEED if:
   - Phase 0 (GoRules isolation): Accuracy ≥ 90%
   - Phase 3 (End-to-end): Consistency = 100%
   - User customization works
   - Positive team feedback

⚠️ CONDITIONAL if:
   - Phase 0: Accuracy 85-90% (good but needs tuning)
   - Phase 1: Parser < 85% (need LLM classifier)
   - Team likes the approach but has concerns

❌ DO NOT PROCEED if:
   - Phase 0: Accuracy < 85% (GoRules not working)
   - Phase 3: Consistency < 100% (defeats purpose)
   - Negative team feedback
```

**Deliverables**:
- `comparison_report.json`
- `comparison_report.md`
- Team presentation

---

## Implementation Plan

### **Day 1: GoRules Installation & Decision Graph**

**Tasks**:
1. Install `zen-engine` package
2. Create directory structure:
   ```
   src/executive_assistant/decisions/
   ├── __init__.py
   ├── storage_selector.py
   └── tests/
   ```
3. Create `data/rules/storage-selection.json` with multi-storage support
4. Audit tool registry and align tool names

**Decision Graph (Revised)**:
```json
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
      "id": "check-semantics",
      "type": "rule",
      "expression": "input.semanticSearch === true || input.searchByMeaning === true",
      "outputs": ["needsSemantics"]
    },
    {
      "id": "check-analytics",
      "type": "rule",
      "expression": "input.complexAnalytics === true || input.needsJoins === true || input.windowFunctions === true",
      "outputs": ["needsAnalytics"]
    },
    {
      "id": "decision-memory",
      "type": "decision",
      "expression": "isPreference",
      "outputs": {
        "storage": ["memory"],
        "tools": ["create_memory", "get_memory_by_key"],
        "reasoning": "User preferences and personal facts stored in Memory for fast key-value lookup"
      }
    },
    {
      "id": "decision-vdb",
      "type": "decision",
      "expression": "needsSemantics",
      "outputs": {
        "storage": ["vdb"],
        "tools": ["create_vdb_collection", "search_vdb", "add_vdb_documents"],
        "reasoning": "Semantic search requires Vector DB for finding content by meaning"
      }
    },
    {
      "id": "decision-adb",
      "type": "decision",
      "expression": "needsAnalytics && !needsSemantics",
      "outputs": {
        "storage": ["adb"],
        "tools": ["query_adb", "create_adb_table", "import_adb_csv", "export_adb_table", "list_adb_tables", "describe_adb_table", "show_adb_schema", "drop_adb_table", "optimize_adb"],
        "reasoning": "Complex analytics (joins, window functions) use Analytics DB (DuckDB)"
      }
    },
    {
      "id": "decision-tdb",
      "type": "decision",
      "expression": "!isPreference && !needsSemantics && !needsAnalytics",
      "outputs": {
        "storage": ["tdb"],
        "tools": ["create_tdb_table", "query_tdb", "insert_tdb_table", "list_tdb_tables", "describe_tdb_table", "delete_tdb_table", "export_tdb_table", "import_tdb_table", "add_tdb_column", "drop_tdb_column"],
        "reasoning": "Simple structured data with CRUD operations uses Transactional DB (SQLite)"
      }
    },
    {
      "id": "decision-files",
      "type": "decision",
      "expression": "!isPreference && !needsSemantics && !needsAnalytics && input.dataType === 'unstructured'",
      "outputs": {
        "storage": ["files"],
        "tools": ["write_file", "read_file", "list_files", "create_folder", "delete_file"],
        "reasoning": "Unstructured files (reports, exports) stored as files"
      }
    },
    {
      "id": "decision-multi",
      "type": "decision",
      "expression": "needsAnalytics && needsSemantics",
      "outputs": {
        "storage": ["tdb", "adb", "vdb"],
        "tools": ["create_tdb_table", "query_adb", "search_vdb"],
        "reasoning": "Multi-step workflow: Track in TDB, analyze in ADB, search related info in VDB"
      }
    }
  ]
}
```

**Key Changes**:
- ✅ Outputs are arrays (even for single storage)
- ✅ Complete tool lists from audit
- ✅ Multi-storage decision node
- ✅ Clear reasoning for each path

---

### **Day 2: Implement Phase 0 (GoRules Validation)**

**Tasks**:
1. Create `tests/poc/phase0_gorules_validation.py`
2. Implement structured test cases (50 cases)
3. Run tests and measure metrics
4. Document results

**Code**:
```python
# File: tests/poc/phase0_gorules_validation.py

import asyncio
import json
import time
from executive_assistant.decisions.storage_selector import StorageSelector

async def measure_gorules_validation():
    """Measure GoRules with structured input."""

    selector = StorageSelector()
    results = {
        "accuracy": [],
        "response_time": [],
        "errors": []
    }

    for test_case in TEST_CASES_STRUCTURED:
        try:
            start = time.time()

            # Evaluate decision (NO PARSING - structured input directly)
            decision = await selector.engine.async_evaluate(
                "storage-selection",
                test_case["input"]
            )

            elapsed = time.time() - start

            # Check correctness
            result_storage = decision["result"]["storage"]
            expected = test_case["expected"]

            # Handle both single and array outputs
            if isinstance(expected, list):
                accuracy = 1 if set(result_storage) == set(expected) else 0
            else:
                accuracy = 1 if result_storage[0] == expected else 0

            results["accuracy"].append(accuracy)
            results["response_time"].append(elapsed)

        except Exception as e:
            results["errors"].append({
                "test_case": test_case,
                "error": str(e)
            })

    # Calculate metrics
    return {
        "approach": "gorules_structured_input",
        "metrics": {
            "accuracy": sum(results["accuracy"]) / len(results["accuracy"]),
            "consistency": 1.0,  # Always deterministic
            "avg_response_time": sum(results["response_time"]) / len(results["response_time"]),
            "error_rate": len(results["errors"]) / len(TEST_CASES_STRUCTURED)
        },
        "total_tests": len(TEST_CASES_STRUCTURED),
        "errors": results["errors"]
    }

# Run measurement
if __name__ == "__main__":
    result = asyncio.run(measure_gorules_validation())

    with open("phase0_gorules_validation.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"Accuracy: {result['metrics']['accuracy']:.1%}")
    print(f"Consistency: {result['metrics']['consistency']:.1%}")
    print(f"Avg Response Time: {result['metrics']['avg_response_time']*1000:.1f}ms")
    print(f"Errors: {len(result['errors'])}")
```

---

### **Day 3: Implement Phase 1 (Parser Validation)**

**Tasks**:
1. Create labeled test cases (50 requests)
2. Implement parser (start with regex, may use LLM)
3. Measure parser accuracy
4. Analyze errors and patterns

**Code**:
```python
# File: tests/poc/phase1_parser_validation.py

def measure_parser_accuracy():
    """Measure parser accuracy against labeled data."""

    results = {
        "dataType_accuracy": [],
        "complexAnalytics_accuracy": [],
        "semanticSearch_accuracy": [],
        "overall_accuracy": []
    }

    for test_case in LABELED_TEST_CASES:
        # Parse request
        parsed = parse_storage_request(test_case["request"])
        correct = test_case["correct_criteria"]

        # Measure each criterion
        data_type_acc = 1 if parsed["dataType"] == correct["dataType"] else 0
        analytics_acc = 1 if parsed["complexAnalytics"] == correct.get("complexAnalytics", False) else 0
        semantic_acc = 1 if parsed["semanticSearch"] == correct.get("semanticSearch", False) else 0

        # Overall accuracy (all criteria correct)
        overall_acc = 1 if all([
            data_type_acc,
            analytics_acc,
            semantic_acc
        ]) else 0

        results["dataType_accuracy"].append(data_type_acc)
        results["complexAnalytics_accuracy"].append(analytics_acc)
        results["semanticSearch_accuracy"].append(semantic_acc)
        results["overall_accuracy"].append(overall_acc)

    return {
        "approach": "parser",
        "metrics": {
            "overall_accuracy": sum(results["overall_accuracy"]) / len(results["overall_accuracy"]),
            "dataType_accuracy": sum(results["dataType_accuracy"]) / len(results["dataType_accuracy"]),
            "complexAnalytics_accuracy": sum(results["complexAnalytics_accuracy"]) / len(results["complexAnalytics_accuracy"]),
            "semanticSearch_accuracy": sum(results["semanticSearch_accuracy"]) / len(results["semanticSearch_accuracy"])
        }
    }
```

---

### **Days 4-7: Remaining Phases**

Same as v1.0 proposal but with revised targets and multi-storage support.

---

## Success Criteria (Revised)

| Metric | v1.0 Target | **v2.0 Target** | Rationale |
|--------|-------------|-----------------|-----------|
| **Phase 0: GoRules (structured)** | N/A | **≥90%** | Test engine in isolation |
| **Phase 1: Parser** | N/A | **≥85%** | Or use LLM classifier |
| **Phase 2: Baseline Accuracy** | ≥90% | **~70%** (measure actual) |
| **Phase 3: End-to-End Accuracy** | ≥90% | **≥82%** | Realistic improvement |
| **Consistency** | 100% | **100%** | Must be deterministic |
| **Response Time** | ≤1.0s | **≤1.0s** | Must be fast |
| **Reasoning Quality** | ≥4.0/5.0 | **≥4.0/5.0** | With defined rubric |

**Go/No-Go**:
```
✅ PROCEED if:
   - Phase 0 ≥ 90% (GoRules works)
   - Phase 3 Consistency = 100% (deterministic)
   - Team feedback positive

⚠️ CONDITIONAL if:
   - Phase 0 85-90% (good but needs tuning)
   - Phase 1 < 85% (need better parser)

❌ STOP if:
   - Phase 0 < 85% (GoRules not working)
   - Phase 3 Consistency < 100% (broken)
```

---

## Risk Mitigation (Revised)

| Risk | v1.0 Mitigation | **v2.0 Mitigation** | Status |
|------|-----------------|---------------------|--------|
| **Parser accuracy** | Acknowledged | **Phase 0 tests GoRules without parser** | ✅ Fixed |
| **Multi-storage** | Not supported | **Arrays in decision outputs** | ✅ Fixed |
| **Tool names** | Not audited | **Audit before creating graph** | ✅ Fixed |
| **Subjective metrics** | Acknowledged | **Defined rubric** | ✅ Fixed |
| **Unrealistic targets** | 90% accuracy | **85% realistic target** | ✅ Fixed |

---

## Timeline (Revised)

| Phase | Days | Deliverable | Success Criteria |
|-------|------|-------------|------------------|
| **0: GoRules Validation** | 1-2 | `phase0_gorules_validation.json` | Accuracy ≥ 90% |
| **1: Parser Validation** | 3 | `phase1_parser_validation.json` | Accuracy ≥ 85% |
| **2: Baseline** | 4 | `phase2_baseline_measurement.json` | Document current |
| **3: GoRules E2E** | 5 | `phase3_gorules_e2e.json` | Consistency = 100% |
| **4: Analysis** | 6-7 | `comparison_report.md` | Go/no-go decision |

---

## Next Steps

1. **Review this revised proposal**
2. **Approve Phase 0 start** (de-risked approach)
3. **Implement Phase 0** (Days 1-2)
4. **Review Phase 0 results** before continuing
5. **Decision point**: Continue or pivot based on Phase 0 results

---

## Appendix A: Reasoning Quality Rubric

```python
def rate_reasoning_quality(text: str) -> int:
    """Rate reasoning quality on 1-5 scale with defined rubric."""

    score = 3  # Baseline: "Adequate"

    # +1 for each of these:
    if mentions_storage_type(text):  # Explains which storage and why
        score += 1
    if lists_tools(text):  # Shows what tools to use
        score += 1
    if provides_examples(text):  # Gives concrete examples
        score += 1
    if explains_tradeoffs(text):  # Discusses alternatives
        score += 1

    # -1 for each of these:
    if is_vague(text):  # "Use this because it's better"
        score -= 1
    if has_technical_jargon(text):  # "Use transactional database with ACID"
        score -= 1
    if is_missing_important_info(text):  # Doesn't explain why
        score -= 1

    return max(1, min(5, score))

# Examples:
# 5/5: "Use TDB (Transactional DB) because you're tracking daily expenses with simple CRUD operations. Tools: create_tdb_table, query_tdb. This is better than ADB which is for complex analytics."

# 3/5: "Use TDB for tracking expenses."

# 1/5: "Use the database."
```

---

**Document Version**: 2.0 (Revised)
**Last Updated**: 2026-01-29
**Changes from v1.0**: Phased approach, realistic targets, parser validation, multi-storage support
