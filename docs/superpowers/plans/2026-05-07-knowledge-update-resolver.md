# Knowledge Update Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared deterministic resolver that helps production memory search answer “current/latest/updated value” questions from raw snippets instead of trusting stale facts or contradictory model synthesis.

**Architecture:** Create a focused pure-Python resolver in `src/sdk/knowledge_update.py` that detects update-like queries, extracts candidate values from retrieved snippets, scores them using cue-based rules, and returns a compact resolution. Integrate it into `memory_search` output as an advisory section so the existing agent can use it without adding a new tool or changing provider APIs.

**Tech Stack:** Python 3.11+, SDK `SearchResult` objects, existing `memory_search` tool, pytest, ruff.

---

### Task 1: Shared Resolver

**Files:**
- Create: `src/sdk/knowledge_update.py`
- Test: `tests/sdk/test_knowledge_update.py`

- [ ] Write failing tests for the three known LongMemEval knowledge-update failures: `25:50` personal best beats `27:12` goal confusion, `$400,000` wins when directly supported despite `$350,000` conflict, and `the suburbs` is not replaced by broader `Chicago`.
- [ ] Run `uv run pytest tests/sdk/test_knowledge_update.py -q` and confirm failures are missing-module/function failures.
- [ ] Implement dataclasses `KnowledgeUpdateCandidate` and `KnowledgeUpdateResolution` plus `resolve_knowledge_update(query: str, snippets: list[str]) -> KnowledgeUpdateResolution | None`.
- [ ] Run `uv run pytest tests/sdk/test_knowledge_update.py -q` and confirm all resolver tests pass.

### Task 2: Production `memory_search` Integration

**Files:**
- Modify: `src/sdk/tools_core/memory.py`
- Test: `tests/unit/test_memory_and_other_tools.py`

- [ ] Write a failing test that patches conversation search results containing conflicting values and asserts `memory_search` includes a `KNOWLEDGE-UPDATE RESOLUTION` section.
- [ ] Run the focused test and confirm it fails because no resolver section exists.
- [ ] Import `resolve_knowledge_update` in `memory.py`, pass grouped result previews into it for update-like queries, and prepend the resolver section before normal search results.
- [ ] Run the focused test and confirm it passes.

### Task 3: Verification

**Files:**
- Verify: `src/sdk/knowledge_update.py`, `src/sdk/tools_core/memory.py`, `tests/sdk/test_knowledge_update.py`, `tests/unit/test_memory_and_other_tools.py`

- [ ] Run `uv run pytest tests/sdk/test_knowledge_update.py tests/unit/test_memory_and_other_tools.py -q`.
- [ ] Run `uv run ruff check src/sdk/knowledge_update.py src/sdk/tools_core/memory.py tests/sdk/test_knowledge_update.py tests/unit/test_memory_and_other_tools.py`.
- [ ] Recompute saved May 7 evaluation with hardened scorer for reporting context only.

---

Self-review: This plan is scoped to a shared production resolver plus memory-search integration. It does not add a new tool, alter model/provider behavior, or implement the separate multi-session aggregation mode.
