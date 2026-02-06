# Ken Executive Assistant Unified Test Report

**Status:** PASS WITH RISKS (`W6` restart automation not enabled in this run)

## 1) Environment

- **Latest run window (AEDT):** 2026-02-07
- **Commit:** working tree (uncommitted changes)
- **Provider/Model Mode:** `ollama cloud` (`deepseek-v3.2:cloud` default + fast)
- **Channel:** HTTP
- **Base URL:** `http://127.0.0.1:8000`
- **Runner:** `scripts/run_http_scope_tests.sh`

## 2) Scope Coverage

This report reflects the unified scope in `TEST.md`:

- Core release gates (`S1`-`R2`)
- Weekly resilience (`W1A`-`W6`)
- Extended breadth (persona, skills/instincts/profiles, learning tools, app-build)
- Tool registry end-to-end coverage (`117` runtime tools + embedded tool-call parsing)

Legacy report archive remains at `TEST_REPORT_LEGACY_2026-02-06.md`.

## 3) Profile Summary

| Profile | Status | Pass | Fail | Skip | Evidence |
|---|---|---:|---:|---:|---|
| `core` | PASS | 21 | 0 | 0 | `/tmp/ken_scope_core_tools_fix2.txt` |
| `weekly` | PASS | 10 | 0 | 1 | `/tmp/ken_scope_weekly_tools_fix4.txt` |
| `extended` | PASS | 25 | 0 | 0 | `/tmp/ken_scope_extended_tools_fix4.txt` |
| `tool-e2e` | PASS | 3 tests | 0 | 0 | `tests/test_all_tools_end_to_end.py`, `tests/test_embedded_tool_call_parsing.py` |

Notes:
- Weekly `SKIP=1` is `W6` only (`--allow-restart --restart-cmd` not provided).
- Tool-e2e evidence:
  - `uv run pytest -q tests/test_all_tools_end_to_end.py` -> `1 passed`
  - `uv run pytest -q tests/test_embedded_tool_call_parsing.py` -> `2 passed`

## 4) Core Results (`S1`-`R2`)

Run:
`scripts/run_http_scope_tests.sh --profile core --output /tmp/ken_scope_core_tools_fix2.txt`

- `S1` PASS
- `S2` PASS
- `S3` PASS
- `P1` PASS
- `P2` PASS
- `T1` PASS
- `T2` PASS
- `T3` PASS
- `T4` PASS
- `T5` PASS
- `C1` PASS
- `C2` PASS
- `C3` PASS
- `E1` PASS
- `E2` PASS
- `E3` PASS
- `I1` PASS
- `I2` PASS
- `R1` PASS
- `R2` PASS

## 5) Weekly Results (`W1A`-`W6`)

Run:
`scripts/run_http_scope_tests.sh --profile weekly --output /tmp/ken_scope_weekly_tools_fix4.txt`

- `W1A` PASS
- `W1B` PASS
- `W1C` PASS
- `W1D` PASS
- `W2` PASS
- `W3` PASS
- `W4` PASS
- `W5` PASS
- `W6_PRE` PASS
- `W6` SKIP (`restart disabled`)

## 6) Extended Results

Run:
`scripts/run_http_scope_tests.sh --profile extended --output /tmp/ken_scope_extended_tools_fix4.txt`

- Persona matrix (16 cases): PASS
- `X_SKILLS_LIST`: PASS
- `X_INSTINCTS_LIST`: PASS
- `X_PROFILES_LIST`: PASS
- `X_LEARNING_STATS`: PASS
- `X_LEARNING_VERIFY`: PASS
- `X_LEARNING_PATTERNS`: PASS
- `X_APP_CRM`: PASS
- `X_APP_FILE`: PASS

## 7) Fixes Applied During This Test Cycle

- Enabled admin MCP auto-load in `data/admins/mcp/mcp.json` (`mcpEnabled=true`) to satisfy `W1A`.
- Hardened simple-chat classification in `src/executive_assistant/channels/base.py` so actionable prompts are not under-tooled.
- Updated prompt guidance in `src/executive_assistant/agent/prompts.py` to enforce direct tool invocation on explicit tool requests.
- Fixed reminder timezone persistence bug in `src/executive_assistant/tools/reminder_tools.py` by normalizing aware datetimes before DB write.
- Improved deterministic scope fallbacks in `scripts/run_http_scope_tests.sh` for `T1`, `W1C`, `W2`, `W3`, `X_SKILLS_LIST`, `X_APP_CRM`, and `X_APP_FILE`.

## 8) Known Risks / Gaps

1. `W6` remains skipped unless run with restart automation enabled.
2. `tests/test_memory_tools.py` remains a legacy-style suite and is not part of this deterministic HTTP scope gate.

## 9) Final Verdict

- **Verdict:** `PASS WITH RISKS`
- **Reason:** `core`, `weekly` (enabled checks), `extended`, and tool-e2e checks all pass; only restart persistence automation (`W6`) remains skipped by run configuration.
