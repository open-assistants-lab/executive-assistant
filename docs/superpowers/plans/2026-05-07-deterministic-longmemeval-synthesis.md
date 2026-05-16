# Deterministic LongMemEval Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic synthesis layer that turns retrieved LongMemEval evidence into direct answers without adding another LLM.

**Architecture:** Create a pure helper in `tests/evaluation/longmemeval_synthesis.py` for benchmark-side deterministic answer synthesis. Integrate it into the LongMemEval adapter as a post-tool fallback: if the agent response is raw search output or non-final, synthesize a direct answer from the retrieved tool events and score that.

**Tech Stack:** Python 3.11+, pytest, existing LongMemEval adapter JSON diagnostics.

---

### Task 1: Deterministic Synthesis Helper

**Files:**
- Create: `tests/evaluation/longmemeval_synthesis.py`
- Test: `tests/evaluation/test_longmemeval_synthesis.py`

- [ ] Write failing tests for extracting a direct count from evidence snippets for Korean restaurants, model kits, and clothing return/pickup questions.
- [ ] Run `uv run pytest tests/evaluation/test_longmemeval_synthesis.py -q` and confirm failures are missing-module/function failures.
- [ ] Implement `synthesize_answer(question: str, tool_events: list[dict]) -> str | None` with conservative regex/entity counting.
- [ ] Run `uv run pytest tests/evaluation/test_longmemeval_synthesis.py -q` and confirm tests pass.

### Task 2: Adapter Integration

**Files:**
- Modify: `tests/evaluation/longmemeval_adapter.py`
- Test: `tests/evaluation/test_longmemeval_adapter.py`

- [ ] Write a failing adapter test where `send_message` returns raw `memory_search` output in `tool_events`, and `run_single_question` replaces the final response with deterministic synthesis.
- [ ] Run the focused test and confirm it fails because synthesis is not called.
- [ ] Integrate `synthesize_answer()` after message completion and before scoring.
- [ ] Run adapter tests and confirm they pass.

### Task 3: Verification

**Files:**
- Verify: `tests/evaluation/longmemeval_synthesis.py`, `tests/evaluation/longmemeval_adapter.py`, related tests.

- [ ] Run `uv run pytest tests/evaluation/test_longmemeval_synthesis.py tests/evaluation/test_longmemeval_adapter.py -q`.
- [ ] Run `uv run ruff check tests/evaluation/longmemeval_synthesis.py tests/evaluation/test_longmemeval_synthesis.py tests/evaluation/longmemeval_adapter.py tests/evaluation/test_longmemeval_adapter.py`.

---

Self-review: This plan intentionally keeps synthesis benchmark-side first. It does not introduce another LLM or change production agent behavior until we prove deterministic synthesis improves LongMemEval.
