# Codebase Review Findings

## Findings

### ✅ 1) Instinct filtering not actually context-aware (RESOLVED)
`get_system_prompt` accepts `user_message` for context-aware instinct filtering, but the call site does not pass it. This means instincts are always injected from the broad pool rather than filtered by the current message. This can bloat prompts and misapply instincts.

**Fix Applied (2026-01-31):**
- Changed observer to use `message.content` (raw) instead of `enhanced_content` (with memory injection)
- Prevents false pattern detection from memory context
- Cleaner separation: observer learns from actual user behavior, not stored facts

- File: `src/executive_assistant/agent/prompts.py`
- File: `src/executive_assistant/channels/base.py` (line 319)

### ✅ 2) /adb create schema mismatch risk (RESOLVED)
`/adb create` uses `CREATE TABLE IF NOT EXISTS` and infers schema from the provided JSON. If the table already exists with a different schema, the insert can fail or behave unexpectedly without a clear message. Consider explicit schema validation or clearer error handling.

**Fix Applied (2026-01-31):**
- Added schema validation before table creation
- Checks if table exists with different schema using `PRAGMA table_info()`
- Provides detailed error message showing existing vs. requested schemas
- Suggests alternative actions (insert, drop, or use different name)

- File: `src/executive_assistant/channels/management_commands.py` (line 905)

### ✅ 3) /adb insert ignores extra keys silently (RESOLVED)
`/adb insert` derives columns from the first row only. If later rows contain extra keys, those values are silently dropped. This can cause data loss or confusion. Consider validating that all rows share the same keys or warn on mismatch.

**Fix Applied (2026-01-31):**
- Added column consistency validation before insert
- Compares all row columns against first row (reference)
- Reports specific mismatches: which rows have missing/extra columns
- Prevents data loss with clear error message

- File: `src/executive_assistant/channels/management_commands.py` (line 962)

## Notes
- ~~Observer should see both raw and memory-injected user inputs~~ (DECIDED: Observer should use raw input only to prevent false pattern detection from memory context)
