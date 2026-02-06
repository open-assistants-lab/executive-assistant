# Ken Executive Assistant Test Plan

**Last Updated:** 2026-02-06  
**Purpose:** Practical, executable validation for local and CI-like runs against the real HTTP agent.

## 1) Coverage Summary

| Area | Covered | Notes |
|---|---|---|
| Startup/config | Yes | Includes provider/mode preflight |
| HTTP channel | Yes | `/health`, `/message`, non-streaming behavior |
| Memory + context continuity | Yes | Multi-turn verification |
| TDB/ADB/VDB/File tool families | Yes | Behavior-level checks via agent |
| Reminders + scheduler | Yes | Create/list + scheduler sanity |
| Proactive check-in | Yes | Enable/show/test and scheduler path verification |
| Error handling | Yes | Invalid requests and graceful failures |
| Isolation | Yes | Cross-user/thread separation |
| Security boundaries | Partial | No auth-hardening tests (frontend-owned by design) |
| Load/perf | Smoke only | Latency and basic concurrency, not full benchmark |

---

## 2) Preflight (Required)

1. Start PostgreSQL:
```bash
docker compose -f docker/docker-compose.yml up -d postgres
```

2. Verify Ollama Cloud config from `.env` (no key printing):
```bash
rg -n "^(DEFAULT_LLM_PROVIDER|OLLAMA_MODE|OLLAMA_DEFAULT_MODEL|OLLAMA_FAST_MODEL)=" docker/.env
```
Expected:
- `DEFAULT_LLM_PROVIDER=ollama`
- `OLLAMA_MODE=cloud`
- model names ending in `:cloud` (or your intended cloud model IDs)

3. Start assistant in HTTP mode:
```bash
EXECUTIVE_ASSISTANT_CHANNELS=http UV_CACHE_DIR=.uv-cache uv run executive_assistant
```

4. Health check:
```bash
curl -sS http://127.0.0.1:8000/health
```
Expected: `{"status":"healthy",...}`

---

## 3) Test Harness

Use this helper for repeatable HTTP calls:

```bash
agent() {
  local user_id="$1"
  local conv_id="$2"
  local prompt="$3"
  curl -sS -X POST http://127.0.0.1:8000/message \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"${user_id}\",\"conversation_id\":\"${conv_id}\",\"content\":\"${prompt}\",\"stream\":false}"
}
```

---

## 4) Must-Pass Smoke Suite (Run Every Change)

### A. Startup and Core Chat

1. `S1` Health endpoint returns healthy.
2. `S2` Determinism sanity: ask `Reply with exactly: pong` and verify `pong` appears.
3. `S3` Non-empty response for normal query (`What can you help with?`).

### B. Persistence and Context

4. `P1` Same conversation remembers prior statement:
- Turn 1: `My project codename is Atlas42.`
- Turn 2: `What is my project codename?`
- Expect mention of `Atlas42`.

5. `P2` Different conversation for same user should not blindly reuse prior context unless stored memory is explicitly used.

### C. Tooling Families (Behavior-Level)

6. `T1` TDB: ask assistant to create a todo table, insert one row, and query it. Verify returned output includes inserted value.
7. `T2` File tools: ask assistant to write `notes/test.txt` with known content, then read it back. Verify round-trip text.
8. `T3` Memory: ask assistant to remember a preference and then retrieve it in a follow-up turn.
9. `T4` Time tools: ask current UTC time/date; verify non-empty, plausible timestamp/date.
10. `T5` Reminder: set a reminder and list reminders; verify created item appears.

### D. Scheduler and Check-in

11. `C1` `checkin_show()` returns config.
12. `C2` enable/check schedule changes (`checkin_enable`, `checkin_schedule`, `checkin_hours`).
13. `C3` `checkin_test()` runs without exception and returns either findings or explicit "nothing to report".

### E. Error Handling

14. `E1` Invalid request body (missing `content`) returns HTTP validation error.
15. `E2` Nonsensical/invalid DB request produces graceful error text, not server crash.
16. `E3` Unknown file read returns clear "not found" style response.

### F. Isolation

17. `I1` user `u_a` creates private data.
18. `I2` user `u_b` asks for `u_a` private item; should not directly expose it.

### G. Streaming Contract

19. `R1` `stream=true` returns SSE chunks.
20. `R2` Stream ends with done marker.

---

## 5) Weekly Regression Suite

Run smoke + these deeper scenarios weekly:

1. Multi-step workflow requiring >3 tools in one request.
2. Retry behavior on transient web/tool failures.
3. Reminder recurrence creation + next-occurrence verification.
4. Check-in proactive path:
- ensure a user has persisted checkin config
- wait scheduler tick
- verify check-in notification artifact/log path.
5. Thread isolation under parallel requests (>=5 concurrent users).
6. Restart persistence test (state and data survive process restart).

---

## 6) Acceptance Gates

Release candidate is acceptable when:

1. All 20 smoke tests pass.
2. No unhandled exceptions in server logs during run.
3. Check-in commands and scheduler path complete without crash.
4. Ollama Cloud provider is active (validated at startup log).

---

## 7) Reporting Template

Record results in `TEST_REPORT.md` using:

- Environment (commit, model, channel, date/time)
- Smoke suite pass/fail by test ID
- Weekly suite pass/fail (if run)
- Known issues with reproduction prompt(s)
- Final verdict (`PASS`, `PASS WITH RISKS`, `FAIL`)
