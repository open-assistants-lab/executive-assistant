# KB/DB Prompting + Legacy Summary Removal + Checkpoint Centralization (2026-01-16 01:01)

**Status:** ⚠️ Needs corrections (2026-01-16)

## Summary

This plan is mostly complete, but the legacy summary removal section is overstated. KB/DB intent routing remains deferred as optional (slash commands provide explicit access). Checkpoint recovery is complete.

## 1) Prompting for KB/DB Split
**Status:** Deferred (optional)

**Original Goal:** Only ask the user when intent is ambiguous; otherwise route automatically.

**Routing rules:**
- Default to **KB** for: find/lookup/explain/definition/clauses/"what does X say".
- Default to **DB** for: list/calc/report/aggregate/build table/update rows.
- If confidence low, ask once: "Use KB (text search) or DB (tabular)?" and show the inferred default.

**Reason for deferral:** Users now have `/kb` and `/db` slash commands for explicit access, and the agent can route based on natural language context. Intent classifier is a nice-to-have UX enhancement but not critical.

## 2) Retire Legacy Summary Column (No Backward Compatibility)
**Status:** ⚠️ Partially complete (2026-01-16)

**Original Goal:** Use structured_summary only, drop legacy summary column & state.

**Implementation completed:**
- ✅ Removed `summary` field from `AgentState` in `src/cassey/agent/state.py`
- ✅ Removed legacy summary fallback in `call_model` function in `src/cassey/agent/nodes.py`
- ✅ Removed legacy summary generation in `summarize_conversation` function
- ✅ Removed `update_summary()` method from `UserRegistry` in `src/cassey/storage/user_registry.py`
- ✅ Removed `summary` field from `ConversationLog` dataclass
- ✅ Created migration `006_drop_legacy_summary.sql` to drop database column

**Still remaining (code references):**
- `src/cassey/tools/orchestrator_tools.py` still builds state with `"summary": ""`
- `tests/test_summarization.py` still sets `"summary": ""` in a test state

**Files modified:**
- `src/cassey/agent/state.py`
- `src/cassey/agent/nodes.py`
- `src/cassey/storage/user_registry.py`
- `tests/test_summarization.py`
- `tests/test_user_registry.py`
- `tests/test_reviewer_fixes.py`
- `migrations/006_drop_legacy_summary.sql`

## 3) Centralized Checkpoint Recovery
**Status:** ✅ Complete (implemented 2025-01-16 via checkpoint-corruption-issue.md)

**Original Goal:** Sanitize state in one place and avoid reset-on-any-error.

**Implementation completed:**

### SanitizingCheckpointSaver Wrapper
**File:** `src/cassey/storage/checkpoint.py`

The `SanitizingCheckpointSaver` class wraps the base checkpointer and automatically sanitizes checkpoints on load:
- Detects orphaned `tool_calls` in `AIMessage`
- Removes only corrupted messages, preserves valid ones
- Applied by default via `get_async_checkpointer(sanitize=True)`

**Flow (actual):**
```
Old: Detect corruption → Delete entire checkpoint (hard reset)
New: Detect corruption → Sanitize (remove only corrupted messages) → Continue
     If sanitization fails → Log and return unsanitized state (no automatic reset)
```

### Telegram Channel Error Handling
**File:** `src/cassey/channels/telegram.py`

- **Per-thread locks**: Added `_thread_locks` dict with `_get_thread_lock()` method to serialize concurrent messages per thread
- **Targeted resets**: Changed from "reset on any error" to "reset only on corruption errors"
- New `_is_corruption_error()` helper to detect tool-call related errors
- Removed aggressive startup cleanup and pre-check (now handled by wrapper)

### Test Results
- All summarization tests pass (9/9)
- All user registry tests pass (12/12)

## Overall Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| KB/DB Intent Routing | Deferred | Slash commands `/kb` and `/db` provide explicit access |
| Legacy Summary Removal | ⚠️ Partial | Core agent flow cleaned; residual summary fields remain in orchestrator/tests |
| Checkpoint Sanitization | ✅ Complete | Wrapper + targeted resets |
| Per-thread Locks | ✅ Complete | Prevents concurrent message interleaving |

## Conclusion

Most planned items have been implemented:
- Checkpoint corruption fixes are in place with sanitization wrapper
- Legacy summary has been removed from core agent flow, but residual summary fields remain in orchestrator/tests
- Migration created to drop the database column (006_drop_legacy_summary.sql)
- Structured summary (JSONB) is now the single source of truth

**Recommendation:** Mark as mostly complete. Remove residual `summary` fields in orchestrator/test scaffolding, then apply migration 006_drop_legacy_summary.sql to production databases when ready.

**Note:** KB/DB intent routing remains as an optional future enhancement. Users can explicitly access KB and DB via `/kb` and `/db` slash commands.
