# Cassey Findings and Repairs

## Context
The reported issues included:
- Call limit errors that persisted across threads/runs.
- SQLite "one statement at a time" errors when attempting to create tables and insert data in a single call.
- Local run instructions requiring `uv run cassey` and `docker compose up -d postgres`.

This document summarizes the findings and the repairs applied.

---

## Findings

### 1) Model call limit applied across thread instead of per run
**Observed behavior**
- The agent returned messages such as: `Model call limits exceeded: thread limit (50/50)`.
- This indicates the thread-level counter persisted across runs, blocking new requests even when the user expected per-run limits.

**Root cause**
- `ModelCallLimitMiddleware` tracks:
  - `thread_model_call_count` (persisted across runs)
  - `run_model_call_count` (per invocation)
- In `src/cassey/channels/base.py` and `src/cassey/channels/telegram.py`, the state was built as:
  - `{"messages": [...]}`
- Because the per-run counter was not initialized, the middleware used the persisted thread counter, causing the limit to behave like a thread limit.

### 2) Tool call limit persisted across threads/runs
**Observed behavior**
- Similar to model limits, tool limits accumulated across runs and blocked subsequent tool usage.

**Root cause**
- `ToolCallLimitMiddleware` tracks:
  - `thread_tool_call_count` (persisted across runs)
  - `run_tool_call_count` (per invocation)
- The per-run tool counters were not initialized in the run state.

### 3) SQLite "You can only execute one statement at a time"
**Observed behavior**
- A single `query_db` call containing multiple SQL statements failed with:
  - `Error executing SQL: You can only execute one statement at a time.`

**Root cause**
- `query_db` uses `sqlite3.Connection.execute`, which only allows one statement at a time.
- The workflow needed to create a table and insert dummy rows in a single tool call (to avoid thread/context issues), but the tool rejected multi-statement SQL.

### 4) Local run instructions mismatch
**Observed behavior**
- The project docs used `docker-compose up -d postgres_db`, while the request was to use `docker compose up -d postgres`.

**Root cause**
- The service name in `docker-compose.yml` was `postgres_db`, and docs used the legacy `docker-compose` command, not the new `docker compose` command and service name expected by the user.

---

## Repairs Applied

### 1) Reset run counters per invocation
**What changed**
- Initialize per-run counters in the state at the start of each request:
  - `run_model_call_count = 0`
  - `run_tool_call_count = {}`

**Files updated**
- `src/cassey/channels/base.py`
- `src/cassey/channels/telegram.py`

**Why this works**
- `ModelCallLimitMiddleware` now reads a fresh per-run counter, so limits apply per run (invocation) instead of persisting across the thread.
- `ToolCallLimitMiddleware` now uses a per-run tool call map and does not block future runs.

---

### 2) Allow multi-statement SQL in `query_db`
**What changed**
- `query_db` now supports multiple statements by splitting SQL safely on semicolons that are not inside quotes.
- Statements are executed sequentially and the result is returned from the last statement.

**Files updated**
- `src/cassey/storage/db_tools.py`

**Why this works**
- Enables workflows that need `CREATE TABLE` + `INSERT` in a single tool call.
- Avoids multi-thread or multi-call coordination issues while still using SQLite safely.

---

### 3) Align docker service name and docs
**What changed**
- Renamed the Postgres service to `postgres` and updated `POSTGRES_HOST` accordingly.
- Updated docs to reference `docker compose` and the `postgres` service.

**Files updated**
- `docker-compose.yml`
- `README.md`
- `claude.md`

**Why this works**
- Matches the requested local run instructions:
  - `docker compose up -d postgres`
  - `uv run cassey`

---

## How to Verify

1) Start Postgres:
```bash
docker compose up -d postgres
```

2) Run Cassey locally:
```bash
uv run cassey
```

3) Exercise a multi-statement DB call (example):
```sql
CREATE TABLE IF NOT EXISTS timesheets (id INTEGER PRIMARY KEY, date TEXT, task TEXT, hours REAL);
INSERT INTO timesheets (date, task, hours) VALUES ('2025-01-20', 'Dummy task', 2.0);
SELECT * FROM timesheets;
```

4) Confirm call limits apply per run:
- Repeating requests should not permanently exhaust model/tool limits unless the per-run limit itself is exceeded.

---

## Files Changed Summary
- `src/cassey/channels/base.py`
- `src/cassey/channels/telegram.py`
- `src/cassey/storage/db_tools.py`
- `docker-compose.yml`
- `README.md`
- `claude.md`

---

## Notes
- This repair does not remove thread-level limits; it ensures run-level counters are initialized per invocation so run limits are enforced as intended.
- Multi-statement SQL results only return the last statement output by design.
