# Context Editing Middleware Implementation

## Goal

Add LangChain's `ContextEditingMiddleware` to automatically trim large tool outputs when context pressure is high. This is a safety net alongside summarization middleware.

## Non-Goals

- Do NOT replace summarization middleware
- Do NOT remove user-visible messages or system prompts
- Do NOT mutate tool results outside of explicit context pressure triggers

## Approach

Use LangChain's `ContextEditingMiddleware` with `ClearToolUsesEdit` to:
- Trigger only when context reaches 100K tokens (high threshold)
- Keep only the last 3 tool uses (conservative)
- Run as a safety net behind summarization

## Files to Modify

| File | Change |
|------|--------|
| `src/executive_assistant/agent/langchain_agent.py` | Import and add ContextEditingMiddleware |
| `src/executive_assistant/config/settings.py` | Add MW_CONTEXT_* settings |
| `.env.example` | Document new settings |
| `tests/test_langchain_agent.py` | Add middleware test |

---

## Implementation Steps

### 1. Add Settings (settings.py)

```python
# Context Editing (MW_CONTEXT_EDITING_ENABLED=False by default)
MW_CONTEXT_EDITING_ENABLED: bool = False
MW_CONTEXT_EDITING_TRIGGER_TOKENS: int = 100_000
MW_CONTEXT_EDITING_KEEP_TOOL_USES: int = 3
```

### 2. Import ContextEditingMiddleware (langchain_agent.py)

Add to imports in `_build_middleware`:
```python
from langchain.agents.middleware import (
    SummarizationMiddleware,
    ContextEditingMiddleware,  # ADD THIS
    ModelCallLimitMiddleware,
    # ... rest
)
```

### 3. Wire Up Middleware (langchain_agent.py)

Add in `_build_middleware` after summarization:
```python
if settings.MW_CONTEXT_EDITING_ENABLED:
    from langchain.agents.middleware import ClearToolUsesEdit
    middleware.append(
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=("tokens", settings.MW_CONTEXT_EDITING_TRIGGER_TOKENS),
                    keep=("tool_uses", settings.MW_CONTEXT_EDITING_KEEP_TOOL_USES),
                )
            ]
        )
    )
```

### 4. Update .env.example

```bash
# Context Editing Middleware (disabled by default)
MW_CONTEXT_EDITING_ENABLED=false
MW_CONTEXT_EDITING_TRIGGER_TOKENS=100000
MW_CONTEXT_EDITING_KEEP_TOOL_USES=3
```

### 5. Add Test

```python
def test_context_editing_middleware_when_enabled():
    """Verify ContextEditingMiddleware is included when enabled."""
    # Settings override or mock
    middleware = _build_middleware(model)
    assert any(m.__class__.__name__ == "ContextEditingMiddleware" for m in middleware)
```

---

## Rollout Plan

1. **Stage 1**: Add toggles, keep disabled (`MW_CONTEXT_EDITING_ENABLED=false`)
2. **Stage 2**: Enable in dev for long-running conversation testing
3. **Stage 3**: Enable for selected channels/users if stable

---

## Verification

1. Start Executive Assistant with `MW_CONTEXT_EDITING_ENABLED=true`
2. Run a long conversation that generates 100K+ tokens of tool output
3. Verify older tool outputs are trimmed (check logs or state inspection)
4. Confirm conversation still functions correctly after trimming

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Removing tool outputs needed later | High trigger (100K) + small keep (3) + keep summarization on |
| Breaking existing conversations | Default disabled, gradual rollout |
| Performance impact | Minimal - middleware only evaluates at trigger points |

## Implementation (Completed)
- `src/executive_assistant/config/settings.py`: added `MW_CONTEXT_EDITING_ENABLED`, `MW_CONTEXT_EDITING_TRIGGER_TOKENS`, `MW_CONTEXT_EDITING_KEEP_TOOL_USES`.
- `.env.example`: documented the new context-editing settings.
- `src/executive_assistant/agent/langchain_agent.py`: added `ContextEditingMiddleware` with `ClearToolUsesEdit`, gated by `MW_CONTEXT_EDITING_ENABLED`.
- `tests/test_langchain_agent_unit.py`: added coverage for enabling and disabling context editing middleware.
- `MW_CONTEXT_EDITING_KEEP_TOOL_USES` default updated to 10 in `src/executive_assistant/config/settings.py` and `.env.example`.

## Test Results
- `uv run pytest tests/test_langchain_agent_unit.py -k context_editing -v`
- Tests: `test_context_editing_middleware_enabled`, `test_context_editing_middleware_disabled`
- Result: 2 passed.

---

## Peer Review (2026-01-16)

### ✅ Implementation Correctness
| File | Plan | Actual | Status |
|------|------|--------|--------|
| `settings.py` | Add 3 new settings | ✅ All 3 added | Pass |
| `langchain_agent.py` | Import + wire middleware | ✅ Correct import and wiring | Pass |
| `.env.example` | Document new settings | ✅ All 3 documented | Pass |
| `tests/` | Add middleware test | ✅ 2 tests added (enabled + disabled) | Pass |

### ✅ Code Quality
- Default disabled (safe) ✅
- High trigger threshold (100K tokens) ✅
- Properly gated by setting ✅
- Lazy import of `ClearToolUsesEdit` ✅
- Middleware positioned correctly (after summarization, before limits) ✅
- Tests use `isinstance` for type checking ✅
- Both enabled and disabled paths tested ✅

### 📋 Deviation from Plan
- `MW_CONTEXT_EDITING_KEEP_TOOL_USES` changed from 3 → 10 (more conservative, keeps more recent tool uses)

### 📊 Overall Assessment
| Criterion | Rating |
|-----------|--------|
| Plan adherence | ✅ Excellent |
| Code quality | ✅ Good |
| Test coverage | ✅ Complete (both enabled/disabled) |
| Safety | ✅ Excellent (disabled by default, high threshold) |

**Verdict: LGTM - Ready for Stage 2 rollout (enable in dev for testing)**
