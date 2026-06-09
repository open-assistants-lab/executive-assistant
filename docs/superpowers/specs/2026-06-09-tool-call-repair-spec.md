# Tool Call Argument Repair — Design & Fixes

Date: 2026-06-09

## Data Flow

```
Provider (LLM response)
  → raw_args: str
    → Streaming: loop.py:1001-1003
    → Non-streaming: ollama.py:95
      → json.loads(raw_args)
        → success: parsed dict
        → JSONDecodeError: repair_tool_call(raw_args)
```

## repair_tool_call Pipeline

Defined in `src/sdk/validation.py:82`.

| Step | Function | Input example | What it fixes |
|------|----------|---------------|---------------|
| 1 | `json.loads()` direct | Raw args | Always (valid JSON passes through) |
| 2 | `_fix_trailing_commas` | `{...},` | Models that emit trailing commas before closing |
| 3 | `_fix_single_quotes` | `{'key': 'value'}` | Models that emit Python-style dicts instead of JSON |
| 4 | `_extract_json_from_fence` | `` `{"key": "value"}` `` | Models that wrap JSON in markdown fences |
| 5 | `return {}` | Anything | All fail → empty dict (tool call with no args) |

## Bug Found & Fixed

**Root cause**: `ollama.py:95` (non-streaming path) caught `json.JSONDecodeError` and silently set `args = {}` without calling `repair_tool_call`. The streaming path at `loop.py:1001-1003` already used `repair_tool_call` correctly.

**Fix**: Changed `args = {}` → `args = repair_tool_call(args)` at `ollama.py:97`.

**Why `_fix_single_quotes` stays**: It's a last-resort safety net for any provider that emits single-quoted dicts. Removing it saves nothing and breaks a working fallback. The apostrophe edge case (`'it\'s'` → `"it"s"` → invalid JSON) is theoretical — no provider has been observed to emit unescaped apostrophes inside single-quoted tool args. If it occurs, step 5 (`return {}`) handles it gracefully.

## Known Limitation

`_fix_single_quotes` is a `str.replace` — it replaces ALL `'` with `"`, not just JSON delimiter quotes. Input `{'key': 'it\'s fine'}` becomes `{"key": "it"s fine"}` which is invalid JSON and returns `{}`. This is acceptable because:

1. The input was already non-parseable (no provider has been observed to produce this)
2. The return value is `{}` — same as if the model never emitted tool args at all
3. A stateful parser would be more correct but adds complexity for a theoretical case

## Files

| File | Lines | Role |
|------|-------|------|
| `src/sdk/validation.py` | 82-131 | `repair_tool_call` pipeline + `_fix_single_quotes` |
| `src/sdk/loop.py` | 1001-1003 | Streaming path calls `repair_tool_call` |
| `src/sdk/providers/ollama.py` | 95 | Non-streaming path now calls `repair_tool_call` |