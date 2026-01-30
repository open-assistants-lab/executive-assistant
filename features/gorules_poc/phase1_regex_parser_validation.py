#!/usr/bin/env python3
"""Phase 1: Parser Validation

This module tests the parser's ability to extract structured decision criteria
from natural language requests, independent of the GoRules engine.

This answers the question: "Can we accurately parse natural language into
structured criteria for GoRules?"
"""

import json
import re
from typing import Dict, List, Any
from pathlib import Path


# ============================================================================
# LABELED TEST CASES: Natural Language → Structured Criteria
# ============================================================================

LABELED_TEST_CASES: List[Dict[str, Any]] = [
    # ───────────────────────────────────────────────────────────────────
    # Memory (5 cases)
    # ───────────────────────────────────────────────────────────────────
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

    # ───────────────────────────────────────────────────────────────────
    # TDB (10 cases)
    # ───────────────────────────────────────────────────────────────────
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

    # ───────────────────────────────────────────────────────────────────
    # ADB (10 cases)
    # ───────────────────────────────────────────────────────────────────
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

    # ───────────────────────────────────────────────────────────────────
    # VDB (10 cases)
    # ───────────────────────────────────────────────────────────────────
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

    # ───────────────────────────────────────────────────────────────────
    # Files (10 cases)
    # ───────────────────────────────────────────────────────────────────
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

    # ───────────────────────────────────────────────────────────────────
    # Multi-storage (5 cases)
    # ───────────────────────────────────────────────────────────────────
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
# PARSER IMPLEMENTATION
# ============================================================================

class StorageRequestParser:
    """Parser for extracting structured criteria from natural language requests."""

    def __init__(self):
        """Initialize the parser with keyword patterns."""
        # Keywords for different data types
        self.preference_keywords = [
            "prefer", "preference", "like", "love", "hate", "dark mode",
            "concise", "verbose", "short", "detailed"
        ]
        self.personal_fact_keywords = [
            "live in", "timezone", "email", "vegetarian", "allergies",
            "birthday", "address", "phone"
        ]
        self.structured_keywords = [
            "track", "table", "list", "maintain", "keep", "store", "monitor",
            "todo", "task", "customer", "inventory", "project", "milestone"
        ]
        self.numeric_keywords = [
            "expenses", "sales", "amount", "quantity", "price", "cost",
            "budget", "count", "number", "metrics"
        ]
        self.tabular_keywords = [
            "pivot", "table", "spreadsheet", "rows", "columns"
        ]
        self.document_keywords = [
            "document", "notes", "article", "content", "discussion", "knowledge"
        ]
        self.unstructured_keywords = [
            "file", "report", "export", "csv", "markdown", "pdf", "excel",
            "json", "snippet", "chart", "image", "log"
        ]
        self.report_keywords = ["report", "export", "generate", "create"]

        # Keywords for complex analytics
        self.analytics_keywords = [
            "analyze", "analysis", "analytics", "trends", "aggregate",
            "sum", "average", "group by", "pivot", "compare", "rank"
        ]
        self.join_keywords = [
            "join", "combine", "merge", "relate", "together", "link"
        ]
        self.window_keywords = [
            "running total", "moving average", "rank", "row number",
            "window function", "lag", "lead"
        ]

        # Keywords for semantic search
        self.semantic_keywords = [
            "semantic", "meaning", "context", "understand",
            "not keywords", "not just keywords"
        ]
        self.search_keywords = [
            "search", "find", "look for", "look up", "retrieve", "locate"
        ]
        self.by_meaning_keywords = [
            "by meaning", "by context", "similar", "related", "about",
            "relevant"
        ]

    def parse(self, request: str) -> Dict[str, Any]:
        """
        Parse natural language request into structured decision criteria.

        Args:
            request: Natural language request string

        Returns:
            Dict with decision criteria
        """
        message_lower = request.lower()

        return {
            "dataType": self._detect_data_type(message_lower),
            "complexAnalytics": self._detect_analytics(message_lower),
            "needsJoins": self._detect_joins(message_lower),
            "windowFunctions": self._detect_window_functions(message_lower),
            "semanticSearch": self._detect_semantic_search(message_lower),
            "searchByMeaning": self._detect_search_by_meaning(message_lower)
        }

    def _detect_data_type(self, message: str) -> str:
        """Detect data type from message."""
        # Check for preferences first
        if any(kw in message for kw in self.preference_keywords):
            return "preference"

        # Check for personal facts
        if any(kw in message for kw in self.personal_fact_keywords):
            return "personal_fact"

        # Check for documents (before structured, as documents can be structured too)
        if any(kw in message for kw in self.document_keywords):
            return "document"

        # Check for unstructured/reports
        if any(kw in message for kw in self.unstructured_keywords):
            return "unstructured"

        if any(kw in message for kw in self.report_keywords):
            return "report"

        # Check for numeric
        if any(kw in message for kw in self.numeric_keywords):
            return "numeric"

        # Check for tabular
        if any(kw in message for kw in self.tabular_keywords):
            return "tabular"

        # Check for structured (default for tracking/tables)
        if any(kw in message for kw in self.structured_keywords):
            return "structured"

        return "unknown"

    def _detect_analytics(self, message: str) -> bool:
        """Detect if complex analytics needed."""
        return any(kw in message for kw in self.analytics_keywords)

    def _detect_joins(self, message: str) -> bool:
        """Detect if joins needed."""
        return any(kw in message for kw in self.join_keywords)

    def _detect_window_functions(self, message: str) -> bool:
        """Detect if window functions needed."""
        return any(kw in message for kw in self.window_keywords)

    def _detect_semantic_search(self, message: str) -> bool:
        """Detect if semantic search needed."""
        return any(kw in message for kw in self.semantic_keywords)

    def _detect_search_by_meaning(self, message: str) -> bool:
        """Detect if search by meaning needed."""
        if not any(kw in message for kw in self.search_keywords):
            return False

        return any(kw in message for kw in self.by_meaning_keywords)


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

def measure_parser_accuracy() -> Dict[str, Any]:
    """
    Measure parser accuracy against labeled test cases.

    Returns:
        Dict with metrics and detailed results
    """
    parser = StorageRequestParser()

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
    print(f"PHASE 1: Parser Validation (Natural Language → Structured Criteria)")
    print(f"{'='*80}")
    print(f"Total test cases: {len(LABELED_TEST_CASES)}")
    print(f"\nRunning parser...\n")

    for i, test_case in enumerate(LABELED_TEST_CASES, 1):
        try:
            # Parse request
            parsed = parser.parse(test_case["request"])
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
        "approach": "regex_parser",
        "phase": "1",
        "timestamp": 0,  # Placeholder
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
    print(f"PHASE 1 RESULTS")
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
        print(f"   ⚠️  RECOMMENDATION: IMPROVE - Consider LLM classifier for better accuracy")
    else:
        print(f"   ❌ Parser Accuracy < 70%: {accuracy:.1%}")
        print(f"\n   🛑 RECOMMENDATION: RECONSIDER - Parser is bottleneck")

    print(f"{'='*80}\n")


def main():
    """Main entry point."""
    results = measure_parser_accuracy()

    # Print human-readable results
    print_results(results)

    # Save to JSON
    output_path = Path("tests/poc/phase1_parser_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"💾 Results saved to: {output_path}")

    return results


if __name__ == "__main__":
    main()
