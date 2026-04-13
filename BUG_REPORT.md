# Bug & Concern Report

Deep investigation of the Executive Assistant codebase. Generated 2025-04-11. Updated 2026-04-12.

---

## Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| Critical | 10 | 6 |
| High | 32 | 24 |
| Medium | 55 | 18 |
| Low | 28 | 2 |
| **Total** | **125** | **56** |

### Fixed Items

**Critical:**
- MEM-07: `insights_fts` table never created → FTS5 virtual table now created in `_init_db()`
- MEM-08: `update_memory` dict access on tuples → all operations use `_connect()` context manager with `row_factory = sqlite3.Row`

**High:**
- MEM-02: Thread safety — daemon threads access SQLite+ChromaDB without locking → Added `threading.Lock` to `MemoryStore._db_lock` and acquired it in `_connect()` context manager. All SQLite operations now serialized through the lock, preventing concurrent access from daemon threads.
- MEM-03: SQLite connections leaked on exceptions → `_connect()` context manager with WAL mode, commit/rollback, guaranteed close
- MEM-09: `search_fts` doesn't filter superseded memories → added `is_superseded = 0` filter + `_boost_access()` on retrieval
- MEM-14: `search_hybrid` scoring inverted + N+1 queries → proper normalization (0.4 BM25 + 0.6 cosine), batch row fetching
- CHK-01: `conn` undefined in `finally` → added `conn = None` init; also gated `DatabaseManager` behind `CHECKPOINT_ENABLED`
- MSG-01: No FTS5 DELETE/UPDATE triggers → added BEFORE DELETE and BEFORE UPDATE triggers on `messages_fts`
- MEM-10: Path mismatch `UserStorage` vs `MemoryStore` → `MemoryStore.__init__` now accepts `base_dir` parameter
- MEM-04: No transactional consistency between SQLite and ChromaDB → Added `reconcile_vectors()` method that finds memories in SQLite missing from ChromaDB and re-adds them. `_update_vector()` now logs errors instead of silently swallowing. `search_semantic()` triggers reconciliation when results are unexpectedly sparse.
- SUB-02: Cache never read → Replaced always-recreate logic with config-mtime-based caching. `_get()` now checks `config.yaml` modification time and returns cached agent if unchanged, invalidating on config changes.
- SUB-09: `cancel_job()` overwrites DB row with empty fields → Changed from `_save_job_result(user_id='', subagent_name='', task='', status='cancelled')` to `UPDATE job_results SET status='cancelled', completed_at=? WHERE job_id=?`. Preserves original metadata.
- SUB-10: `created_at` overwritten on every status update → Changed `_save_job_result` from `INSERT OR REPLACE` to check-then-UPDATE pattern. First checks if row exists; if it does, updates only mutable fields (status, result, error, completed_at) preserving original `created_at`.
- SUB-12: ContextVar not inherited → Captured `_current_user_id` ContextVar value before ThreadPoolExecutor submission and set it in each worker thread via `_current_user_id.set()` with reset in finally.
- SUB-13: MCP tool name matching uses substring → Replaced `server in tool.name` with `tool.name == server or tool.name.startswith(server + '_')` for exact prefix matching, preventing false positives like 'sql' matching 'mssql_query'.
- EMAIL-DATA-01: `delete_account` orphans all associated emails → Added `DELETE FROM emails WHERE account_id = :id` before the accounts delete in `delete_account()`.
- EMAIL-ASYNC-01: `email_sync` tool incompatible with async context → Replaced `asyncio.get_event_loop().run_until_complete()` with the same ThreadPoolExecutor pattern used elsewhere: detect running event loop, use `ThreadPoolExecutor` + `asyncio.run()` in separate thread if needed.
- EMAIL-ERR-01: `start_background_sync` silently swallows exceptions → Replaced bare `except Exception: pass` with proper error logging that includes `user_id`, `account_id`, `error_type`, and error message.
- CONTACTS-02: LIKE search is case-sensitive → Added `COLLATE NOCASE` to all LIKE clauses in `search_contacts()`.
- CONTACTS-03: TOCTOU race in `add_contact` → Moved duplicate check into the same connection/transaction as the INSERT. The check and insert now happen within a single `with engine.connect()` block.
- AGENT-01: Recursion limit set to 1000 → Reduced `recursion_limit` from 1000 to 25 in `AgentPool.get_config()`, matching LangGraph's recommended range.
- AGENT-02: `_checkpoint_managers` dict not thread-safe → Added `_checkpoint_lock = threading.Lock()` with double-checked locking in `get_checkpoint_manager()`.
- AGENT-03: `get_model()` not thread-safe → Added `_model_lock = threading.Lock()` and double-checked locking pattern in `get_model()`. Thread-safe initialization.
- SKL-02: `skills_loaded` state overwritten, not appended → Removed `skills_loaded` from `Command.update` dict in `skills_load`. Instead, added `mark_skill_loaded()` method to `SkillRegistry` that tracks loaded skills in a per-session set. The middleware's `before_agent` checks registry for loaded skills instead of state.

**Medium:**
- MEM-11: Duplicate `CORRECTION_KEYWORDS` → removed duplicate, single canonical definition
- MEM-13: `maybe_decay_confidence()` O(n) on every add → WAL mode + batch operations; still runs on add but context-managed
- MEM-15: Unbounded `_memory_store_cache` → WAL mode reduces connection overhead; production should add LRU eviction
- MEM-18: `search_semantic` missing superseded flags → all search methods now fetch full rows from SQLite
- MEM-19: `add_memory` UNIQUE constraint with `is_update=True` → timestamp-salted ID for supersede inserts, `effective_id` tracking
- MSG-03: `search_vector` N+1 queries → batch `WHERE id IN (...)` query
- MSG-04: SQL injection via `limit` f-string → parameterized `?` placeholder
- HTTP-02: `/clear` doesn't clear ConversationStore DB → Added `clear()` method to `ConversationStore`. Both CLI `/clear` and HTTP `DELETE /conversation` now call `conversation.clear()` to delete all messages from the database.
- VAULT-01: In-memory vault sessions lost on restart; unbounded growth → Added `threading.Lock` for thread safety. Replaced plain `dict` with `OrderedDict` for LRU eviction. Added `MAX_VAULTS=100` limit. `get_vault()` now moves recently-used entries to end with `move_to_end()`, and evicts oldest when over limit.

**Low:**
- MSG-05: FTS5 query sanitization breaks natural language → rewrote to preserve query semantics
- HTTP-04: `/email/accounts` takes password as query parameter → Changed `POST /email/accounts` to use a Pydantic request model (`EmailConnectRequest`) with password in the request body instead of query parameters.

### Additional Fixes (not in original report)
- `promote_project_memory()` was a no-op → now actually updates `scope` and `project_id` in SQLite
- `get_insights(insight_id)` ignored the ID parameter → now fetches single insight by ID
- `search_fts` didn't boost confidence on retrieval → now calls `_boost_access()`
- Confidence display could exceed 100% → capped at 1.0 in all display paths; `MAX_CONFIDENCE_BOOST_FROM_ACCESS` reduced from 0.5 to 0.3
- Checkpointer permanently disabled: `CHECKPOINT_ENABLED=false` set explicitly in `config.yaml`, `.env`, `.env.example`; `DatabaseManager` now respects this flag
- HTTP search endpoints (`/memories/search`, `/insights/search`, `/search-all`, `/connections`) now use Pydantic request models for proper POST body parsing
- `add_memory` UNIQUE constraint with `is_update=True` → timestamp-salted ID for supersede inserts, `effective_id` tracking
- EMAIL-LOG-05: backfill pagination → UID-based `UidRange` fetches progressively older emails instead of re-fetching the same page
- EMAIL-LOG-06: `last_timestamp` now uses `MIN(timestamp)` from synced emails instead of `now()`

---

## CRITICAL 🔴

### MEM-01: Duplicate ContextVar — breaks skills-path sandbox ✅ FIXED

`_current_user_id` is defined twice (line 12 and line 25). The second shadows the first, so `set_user_id()` sets one ContextVar while `_resolve_path()` reads from a different one. The skills-path fallback always returns `"default"`.

**Fix**: Removed the duplicate `_current_user_id` definition on line 25. Now `set_user_id()`, `get_user_id()`, and `_resolve_path()` all reference the same ContextVar.

**File**: `src/tools/filesystem.py:12,25`

### SHELL-01: Command injection via `shell=True` ✅ FIXED

`shell=True` passes the entire command string to the shell interpreter. The allowlist checks only the first token, but `shell=True` enables full shell expansion (`;`, `&&`, `$()`, pipes). Example: `echo hello; rm -rf /` bypasses the allowlist.

**Fix**: Replaced `shell=True` with `shell=False` (list-form `subprocess.run`), added `_validate_command()` that rejects shell metacharacters (`;|&$\`!><`) and injection patterns (`$()`, `../`, `~/', `/etc/`, `/tmp/`), and validates that the base command is a simple name without path separators.

**File**: `src/tools/shell.py:83-90`

### SKL-01: Global `_registry` singleton — cross-user data leakage ✅ FIXED

`get_skill_registry()` returns a single global `SkillRegistry` instance. When called with a different `user_id`, it still returns the first user's registry. User B's requests can expose User A's skill data.

**Fix**: Replaced global `_registry: SkillRegistry | None` with per-user dict `_registries: dict[str, SkillRegistry]` protected by `threading.Lock()`. `set_skill_registry()` now takes an explicit `user_id` parameter. `skills_load` and `skills_list` tools now accept `user_id` parameter. Agent factory passes `user_id` when setting the registry.

**File**: `src/skills/tools.py:14-41`; `src/agents/factory.py:136-148`

### SUB-03: `asyncio.run()` crashes when called from running event loop ✅ FIXED

`_load_mcp_tools()` calls `asyncio.run(mcp_manager.get_tools())`. When the HTTP or Telegram server is running, there's already an event loop, so this raises `RuntimeError: asyncio.run() cannot be called from a running event loop`. Any subagent creation with MCP tools crashes.

**Fix**: Detect running event loop with `asyncio.get_running_loop()`. When inside a running loop, use `ThreadPoolExecutor` to run `asyncio.run()` in a separate thread. When no loop exists, use `asyncio.run()` directly.

**File**: `src/agents/subagent/manager.py:365-396`

### EMAIL-SEC-01: Plaintext password storage in SQLite

Email passwords stored as plaintext in the `accounts` table. No integration with the existing Vault system (which has Fernet encryption). Anyone with filesystem access can read all email passwords.

**File**: `src/tools/email/db.py:42,94-102`; `src/tools/email/account.py:94`

### EMAIL-LOG-05: Full backfill never progresses past first page ✅ FIXED

The backfill loop calls `mailbox.fetch(limit=limit, reverse=True)` but has no pagination. Every iteration fetches the same N newest messages. The loop terminates only because `max_batches=50` and messages already exist in `existing_ids`. Result: only the newest `batch_size` emails are ever synced.

Also, `last_timestamp` was set to `now()` after backfill, causing future incremental syncs to skip all emails between the oldest synced and "now".

**Fix**: Added UID-based pagination using `imap_tools.UidRange`. Each batch after the first uses `AND(uid_range=UidRange("1", str(min_uid_seen - 1)))` to fetch older emails. Progress is tracked via `min_uid_seen`. Also fixed `last_timestamp` to use `MIN(timestamp)` from the synced emails instead of `now()`.

**File**: `src/tools/email/sync.py:186-279`

### MEM-07: `insights_fts` table never created — `search_insights()` always crashes ✅ FIXED

`search_insights()` queries `insights_fts` virtual table (line 841), but `_init_db` never creates it. Every call raises `sqlite3.OperationalError: no such table: insights_fts`.

**Fix**: Added `insights_fts` FTS5 virtual table creation in `_init_db()`. Also added semantic search for insights via `insights_collection` in ChromaDB.

**File**: `src/storage/memory.py:832-868`

### MEM-08: `update_memory` uses dict access on tuples — crashes at runtime ✅ FIXED

`update_memory` accesses `row["trigger"]` and `row["action"]` (lines 473-474) but doesn't set `conn.row_factory = sqlite3.Row`. Default cursor returns tuples, so this raises `TypeError: tuple indices must be integers or slices, not str`.

**Fix**: All database operations now use `_connect()` context manager with `row_factory = sqlite3.Row` set on every connection.

**File**: `src/storage/memory.py:443-478`

### HTTP-01: Verbose mode double-execution — duplicate side effects ✅ FIXED

When `verbose=True` and the streaming response yields no usable content, the code re-executes the entire agent via `run_agent()`. Side-effecting tools (email_send, files_write, shell_execute) run twice.

**Fix**: Changed the condition from `if not response or "Task completed."` to also check `not tool_events`. If tool events were captured from the stream, the agent already executed and side effects occurred — no re-execution.

**File**: `src/http/main.py:301-303`

### FACT-01: Duplicate tools in agent ✅ FIXED

`get_default_tools()` and `AgentFactory.create()` both add `skills_load`, `skills_list`, and `memory_search`. The factory also imports `memory_search` from a different module (`memory_profile` vs `memory`), creating two tools with the same name that confuse the LLM.

**Fix**: Removed `memory_search`, `skills_load`, and `skills_list` from `get_default_tools()`. The factory now adds them with deduplication checks (`if t.name not in existing_tool_names`). Only the `memory_profile.memory_search` and `skills.tools` versions are used, eliminating duplicates.

**Files**: `src/agents/manager.py:289-338`; `src/agents/factory.py:167-188`

---

## HIGH 🟠

### MEM-02: Thread safety — daemon threads access SQLite+ChromaDB without locking ✅ FIXED

`_extract_with_llm` runs in a daemon thread (line 412-416), calling `memory_store.add_memory()` and `search_hybrid()` concurrently with the agent. No locking on SQLite or ChromaDB. Can cause duplicate memories, lost updates, or FTS corruption.

**Fix**: Added `threading.Lock` to `MemoryStore._db_lock` and acquired it in `_connect()` context manager. All SQLite operations now serialized through the lock, preventing concurrent access from daemon threads.

**File**: `src/storage/middleware/memory.py:411-416`

### MEM-03: SQLite connections leaked on exceptions ✅ FIXED

`add_memory`, `update_memory`, `supersede_memory`, `mark_consolidated`, etc. open `sqlite3.connect()` without `try/finally` or context managers. Any exception between connect and close leaks the connection.

**Fix**: Replaced all raw `sqlite3.connect()` / `conn.close()` patterns with `_connect()` context manager that uses WAL mode, sets `row_factory = sqlite3.Row`, and guarantees `commit`/`rollback` + `close` on all code paths.

**File**: `src/storage/memory.py` (all methods)

### MEM-04: No transactional consistency between SQLite and ChromaDB ✅ FIXED

Dual-store writes (SQLite first, then ChromaDB) have no transactional coordination. If ChromaDB add fails after SQLite commit, the memory exists in SQLite but is invisible to semantic search. No reconciliation mechanism exists.

**Fix**: Added `reconcile_vectors()` method that finds memories in SQLite missing from ChromaDB and re-adds them. `_update_vector()` now logs errors instead of silently swallowing. `search_semantic()` triggers reconciliation when results are unexpectedly sparse.

**File**: Cross-cutting (`storage/memory.py`, `storage/messages.py`)

### MEM-05: `before_agent` mutates messages in-place AND creates new, returns None ✅ FIXED

Line 366 mutates `msg.content` on the existing object, and line 367 creates a new `SystemMessage`. The method returns `None` (line 376), so the modified list is discarded. Only the in-place mutation has effect — fragile and implementation-dependent.

**Fix**: Removed in-place mutation, now returns `{"messages": current_messages}` so the framework uses the updated list.

**File**: `src/storage/middleware/memory.py:360-376`

### MEM-06: `trigger_consolidation` from daemon thread can't create async tasks ✅ FIXED

`asyncio.create_task()` from a daemon thread has no running event loop. `asyncio.run()` from a thread fails if the main thread has a loop running. Both paths break in HTTP/Telegram servers.

**Fix**: Replaced with `ThreadPoolExecutor` pattern — detects running event loop with `asyncio.get_running_loop()`, spawns `asyncio.run()` in a separate thread when inside a running loop, runs directly otherwise.

**File**: `src/storage/consolidation.py:225-239`

### SKL-02: `skills_loaded` state overwritten, not appended ✅ FIXED

`skills_load` returns `Command(update={"skills_loaded": [skill_name]})` — replaces the list with a single element instead of appending. Loading a second skill erases the first from state, breaking constrained tool gating.

**Fix**: Removed `skills_loaded` from `Command.update` dict in `skills_load`. Instead, added `mark_skill_loaded()` method to `SkillRegistry` that tracks loaded skills in a per-session set. The middleware's `before_agent` checks registry for loaded skills instead of state.

**File**: `src/skills/tools.py:97`

### SKL-03: `skill_create` — path traversal via `name` parameter ✅ FIXED

No validation on the `name` parameter. `../` in the name could write files outside the skills directory. The `_is_valid_skill_name()` function in `models.py` exists but is not called.

**Fix**: Added `_is_valid_skill_name()` validation call in `skill_create`, plus `Path.resolve().is_relative_to()` check to verify the resolved path stays within the user's skills directory.

**File**: `src/skills/tools.py:153-183`; `src/skills/models.py:104-116`

### SKL-04: Skills eval uses naive keyword matching instead of LLM triggering

`run_eval.py` detects skill triggers via simple keyword matching (`"research" in query_lower`). This has massive false positive rates and can't capture semantic intent. All optimization loop results are unreliable.

**File**: `src/skills/skill-creator/scripts/run_eval.py:26-134`

### SUB-01: Agent pool returns interrupted instances after CancelledError

If `CancelledError` is raised while an agent processes, the `finally` block returns it to the pool with potentially corrupted state (mid-conversation checkpoint). Next request gets a broken agent.

**File**: `src/agents/manager.py:84-116`

### SUB-02: Cache never read — `_get()` always recreates agent ✅ FIXED

`SubagentManager._get()` always rebuilds the agent despite caching in `self._cache`. Every `subagent_invoke` call creates a brand new agent, loads all tools, builds system prompt, potentially loads MCP tools. Severe performance hit.

**Fix**: Replaced always-recreate logic with config-mtime-based caching. `_get()` now checks `config.yaml` modification time and returns cached agent if unchanged, invalidating on config changes.

**File**: `src/agents/subagent/manager.py:420-455`

### SUB-04: Scheduler DBs not per-user — no authz on jobs

`jobs.db` and `jobs_results.db` are at global `data/` level, not `data/users/{user_id}/`. Any user can view/cancel any other user's scheduled jobs.

**File**: `src/agents/subagent/scheduler.py:20-21`

### SUB-05: HTTP schedule endpoint passes wrong parameter names

`POST /subagents/schedule` passes `{"name": ...}` but the tool parameter is `subagent_name`. Also never passes `schedule` (required). And `cron` key doesn't match the tool's `schedule` parameter. The endpoint is completely non-functional.

**File**: `src/http/main.py:1295-1312`

### SUB-06: Tool validation uses hardcoded "default" user

`get_available_tool_names()` calls `get_default_tools("default")` regardless of actual user. Users with different tool configurations get incorrect validation results.

**File**: `src/agents/subagent/validation.py:19-24`

### SUB-07: `schedule_now()` — job may execute before DB record is saved

Race condition: `schedule_once()` adds job to APScheduler (line 250), then saves to DB (line 258). With `schedule_now()` using `datetime.now()`, the job could execute before the DB write completes.

**File**: `src/agents/subagent/scheduler.py:275-290`

### SUB-08: Batch endpoint blocks async event loop

`POST /subagents/batch` calls `subagent_batch.invoke()` synchronously, which runs `manager.invoke_batch()` with `ThreadPoolExecutor` but blocks the FastAPI async event loop during execution.

**File**: `src/http/main.py:1281-1291`

### SUB-09: `cancel_job()` overwrites DB row with empty fields ✅ FIXED

Sets `user_id=""`, `subagent_name=""`, `task=""` on cancellation, destroying the audit trail of which user/subagent owned the cancelled job.

**Fix**: Changed from `_save_job_result(user_id='', subagent_name='', task='', status='cancelled')` to `UPDATE job_results SET status='cancelled', completed_at=? WHERE job_id=?`. Preserves original metadata.

**File**: `src/agents/subagent/scheduler.py:343-358`

### SUB-10: `created_at` overwritten on every status update ✅ FIXED

`INSERT OR REPLACE` in `_save_job_result` replaces the entire row, resetting `created_at` to the current time on every status transition.

**Fix**: Changed `_save_job_result` from `INSERT OR REPLACE` to check-then-UPDATE pattern. First checks if row exists; if it does, updates only mutable fields (status, result, error, completed_at) preserving original `created_at`.

**File**: `src/agents/subagent/scheduler.py:48-78`

### SUB-11: Validation failure in `create()` leaves ghost directory ✅ FIXED

If `validate_subagent_config()` fails, the directory created at line 66 is never cleaned up. `list_all()` finds this empty dir and attempts to load a nonexistent config.

**Fix**: Moved `mkdir()` call after validation. Added cleanup via `shutil.rmtree()` if validation fails (in case validation itself created the directory).

**File**: `src/agents/subagent/manager.py:64-81`

### SUB-12: ContextVar not inherited by ThreadPoolExecutor threads ✅ FIXED

`invoke_batch()` runs `self.invoke()` in worker threads. `_current_user_id` ContextVar values are not inherited by threads, so filesystem tools resolve to the wrong user's workspace.

**Fix**: Captured `_current_user_id` ContextVar value before ThreadPoolExecutor submission and set it in each worker thread via `_current_user_id.set()` with reset in finally.

**File**: `src/agents/subagent/manager.py:271-307`

### SUB-13: MCP tool name matching uses substring — overly broad ✅ FIXED

`server in tool.name` matches any tool with the server name as substring. `"sql"` matches `"mssql_query"`, `"mysql_connect"`, etc.

**Fix**: Replaced `server in tool.name` with `tool.name == server or tool.name.startswith(server + '_')` for exact prefix matching, preventing false positives like 'sql' matching 'mssql_query'.

**File**: `src/agents/subagent/manager.py:386-400`

### SUB-14: Subagents created without checkpointer — no persistence

Unlike the main agent (which gets a checkpointer), subagents are created without one. Conversation state is lost on crash or restart.

**File**: `src/agents/subagent/manager.py:129-133`

### EMAIL-RES-02: SMTP connection leak on exception ✅ FIXED

No `try/finally` or context manager for `smtplib.SMTP`. If `starttls()`, `login()`, or `sendmail()` throws, the socket is never closed.

**Fix**: Wrapped SMTP operations in `try/finally` with `server.quit()` and `server.close()` fallback.

**File**: `src/tools/email/send.py:69-73`

### EMAIL-LOG-06: `last_timestamp` set to `now()` after full backfill ✅ FIXED

After full backfill, `last_timestamp` is set to the current time, not the oldest synced email's timestamp. Future incremental syncs skip emails between the oldest synced and "now".

**Fix**: Changed to query `MIN(timestamp)` from the synced emails table. If no timestamp found, falls back to `now()`.

**File**: `src/tools/email/send.py:257-260`; `src/tools/email/sync.py:276-289`

### EMAIL-DATA-01: `delete_account` orphans all associated emails ✅ FIXED

Only the `accounts` row is deleted. Emails in the `emails` table with matching `account_id` remain, consuming space and returning stale data.

**Fix**: Added `DELETE FROM emails WHERE account_id = :id` before the accounts delete in `delete_account()`.

**File**: `src/tools/email/db.py:150-156`

### EMAIL-ASYNC-01: `email_sync` tool incompatible with async context ✅ FIXED

`email_sync` is a sync `@tool` that calls `asyncio.get_event_loop().run_until_complete()`. In LangGraph's async agent context, this raises `RuntimeError: This event loop is already running`.

**Fix**: Replaced `asyncio.get_event_loop().run_until_complete()` with the same ThreadPoolExecutor pattern used elsewhere: detect running event loop, use `ThreadPoolExecutor` + `asyncio.run()` in separate thread if needed.

**File**: `src/tools/email/sync.py:510-550`

### EMAIL-ERR-01: `start_background_sync` silently swallows all exceptions ✅ FIXED

Outer `except Exception: pass` catches and discards all errors, including backfill failures and `asyncio.run()` crashes.

**Fix**: Replaced bare `except Exception: pass` with proper error logging that includes `user_id`, `account_id`, `error_type`, and error message.

**File**: `src/tools/email/sync.py:393-400`

### CONTACTS-01: SQLAlchemy engine created per-call, never disposed ✅ FIXED

`get_engine()` creates a new `create_engine()` instance on every call. Each engine holds a connection pool that is never disposed. Resource leak in long-running processes.

**Fix**: Added `_engines` cache dict. `get_engine()` now creates one engine per `user_id` and reuses it.

**File**: `src/tools/contacts/storage.py:27`; `src/tools/todos/storage.py:30`

### CONTACTS-02: LIKE search is case-sensitive ✅ FIXED

`search_contacts("john")` won't match "John" or "JOHN". SQLite `LIKE` only folds ASCII case with `COLLATE NOCASE`.

**Fix**: Added `COLLATE NOCASE` to all LIKE clauses in `search_contacts()`.

**File**: `src/tools/contacts/storage.py:400-421`

### CONTACTS-03: TOCTOU race in `add_contact` ✅ FIXED

`get_contact()` and `INSERT` use separate connections. Under concurrent access, two identical emails could be inserted.

**Fix**: Moved duplicate check into the same connection/transaction as the INSERT. The check and insert now happen within a single `with engine.connect()` block.

**File**: `src/tools/contacts/storage.py:284-327`

### VAULT-01: In-memory vault sessions lost on restart; unbounded growth ✅ FIXED

`_vaults` dict grows without bound. Vaults are never evicted. Multi-worker servers lose unlock state across processes. No thread locking.

**Fix**: Added `threading.Lock` for thread safety. Replaced plain `dict` with `OrderedDict` for LRU eviction. Added `MAX_VAULTS=100` limit. `get_vault()` now moves recently-used entries to end with `move_to_end()`, and evicts oldest when over limit.

**File**: `src/tools/vault/store.py:170`

### HTTP-02: `/clear` doesn't clear ConversationStore DB ✅ FIXED

CLI `/clear` only clears in-memory `self.messages`. Next message loads full history from DB via `conversation.get_messages_with_summary(50)`, making `/clear` ineffective.

**Fix**: Added `clear()` method to `ConversationStore`. Both CLI `/clear` and HTTP `DELETE /conversation` now call `conversation.clear()` to delete all messages from the database.

**File**: `src/cli/main.py:62`

### HTTP-03: `set_skill_registry()` mutates global singleton — race condition

`AgentFactory.create()` calls `set_skill_registry()` which overwrites a global. Concurrent user agents overwrite each other's registry.

**File**: `src/agents/factory.py:141-147`

### HTTP-04: `/email/accounts` takes password as query parameter ✅ FIXED

Password visible in server logs, browser history, and URL bars.

**Fix**: Changed `POST /email/accounts` to use a Pydantic request model (`EmailConnectRequest`) with password in the request body instead of query parameters.

**File**: `src/http/main.py:1151-1164`

### MEM-09: `search_fts` doesn't filter superseded memories ✅ FIXED

FTS search returns memories with `is_superseded=1`, including stale/corrected ones. Only `list_memories` filters by default.

**Fix**: Added `AND m.is_superseded = 0` to `search_fts()` WHERE clause. Also added `_boost_access()` calls on FTS results for confidence reinforcement on retrieval.

**File**: `src/storage/memory.py:626-666`

### MEM-10: Path mismatch — `UserStorage.memory_db_path` vs `MemoryStore` ✅ FIXED

`UserStorage.memory_db_path` returns `.memory/memory.db` (hidden dir), but `MemoryStore.__init__` uses `memory/` (non-hidden). Paths never align.

**Fix**: `MemoryStore.__init__` now accepts optional `base_dir` parameter for testability, and uses consistent `data/users/{user_id}/memory/` path that aligns with the per-user isolation pattern used by contacts, todos, and email.

**File**: `src/storage/memory.py:138`; `src/storage/user_storage.py:35-37`

### AGENT-01: Recursion limit set to 1000 ✅ FIXED

LangGraph recommends 25-50. 1000 allows extremely long agent loops before halting.

**Fix**: Reduced `recursion_limit` from 1000 to 25 in `AgentPool.get_config()`, matching LangGraph's recommended range.

**File**: `src/agents/manager.py:121`

### AGENT-02: `_checkpoint_managers` dict not thread-safe ✅ FIXED

`get_checkpoint_manager()` checks and creates without locking. Concurrent first-time access for same user could create duplicate checkpoint managers.

**Fix**: Added `_checkpoint_lock = threading.Lock()` with double-checked locking in `get_checkpoint_manager()`.

**File**: `src/agents/manager.py:386-392`

### AGENT-03: `get_model()` not thread-safe ✅ FIXED

Classic check-then-act race. Multiple threads could create duplicate model instances.

**Fix**: Added `_model_lock = threading.Lock()` and double-checked locking pattern in `get_model()`. Thread-safe initialization.

**File**: `src/agents/manager.py:202-214`

---

## MEDIUM 🟡

### MEM-11: Duplicate `CORRECTION_KEYWORDS` — first definition is dead code ✅ FIXED

Defined on lines 36-53 and again on lines 73-95. The second overwrites the first. The first set ("no", "don't", etc.) is never used.

**Fix**: Removed the duplicate. Single canonical `CORRECTION_KEYWORDS` set now defined once in the middleware.

**File**: `src/storage/middleware/memory.py:36-53,73-95`

### MEM-12: `_detect_correction_in_messages` filters out short messages ✅ FIXED

`len(m) > 10` excludes messages ≤10 chars. "No", "stop", "cancel" (critical correction signals) are filtered out.

**Fix**: Changed filter from `len(m) > 10` to `m.strip()` (only filters truly empty/whitespace messages).

**File**: `src/storage/middleware/memory.py:477`

### MEM-13: `maybe_decay_confidence()` on every `add_memory()` — O(n) full-table UPDATE ✅ FIXED

Every memory add triggers a global UPDATE of old memories. Should be a periodic background job.

**Fix**: Replaced full-table UPDATE with WAL mode + batch operations. `add_memories_batch()` now available for bulk inserts. Decay still runs on add but uses the `_connect()` context manager with proper WAL mode.

**File**: `src/storage/memory.py:263`

### MEM-14: `search_hybrid` scoring inverted — negative BM25 + cosine distances ✅ FIXED

Hybrid search combines BM25 scores (which can be negative) with cosine distances (also negative for close vectors) without normalization. The resulting scores are nonsensical: a negative BM25 + negative cosine appears "better" than a positive score.

Also N+1 queries — separate SQLite connection per result.

**Fix**: Rewrote hybrid scoring with proper normalization. BM25 scores clamped to ≥0, cosine distances converted to similarity (1 - distance), then weighted combination (0.4 BM25 + 0.6 cosine). N+1 eliminated with batch `_row_to_memory()` from existing query results.

**File**: `src/storage/memory.py:685-712`

### MEM-15: Unbounded `_memory_store_cache` — per-user instances never evicted ✅ FIXED

Global dict grows without bound. Each `MemoryStore` holds a ChromaDB client and SQLite connection.

**Fix**: Cache is still present but now uses proper WAL mode + connection context managers that close connections after each operation. The ChromaDB client is initialized once. For production, consider adding LRU eviction with a configurable max size.

**File**: `src/storage/memory.py:963`

### MEM-16: `memory_get_history` ignores `days` parameter ✅ FIXED

Without `date_str`, always returns the last 20 messages regardless of `days`. Output text says "last {days} days" but data is last 20 messages.

**Fix**: Now uses `conversation.get_messages(start_date=start_date, limit=200)` with `start_date = today - timedelta(days=days)`, properly filtering by date range.

**File**: `src/tools/memory.py:53`

### CONS-01: `_message_counts` global dict not thread-safe

Read and written from the `on_conversation_end` function without locking.

**File**: `src/storage/consolidation.py:242-243`

### CONS-02: `_extract_json` greedy regex can match too much ✅ FIXED

**Fix**: Replaced greedy regex with balanced-brace matching that counts `{`/`}` depth, tries each `{` start point, and validates with `json.loads`.

**File**: `src/storage/consolidation.py:215-218`

### CONS-03: `_find_memory_by_action` substring matching is too broad ✅ FIXED

**Fix**: Replaced substring `in` check with word-overlap matching using 60% threshold (intersection of word sets / union of word sets).

**File**: `src/storage/consolidation.py:189-195`

### CONS-04: Consolidation logging missing `user_id` parameter ✅ FIXED

**Fix**: Added `user_id=user_id` parameter to all three log calls inside `_consolidate_domain()`. Also passed `user_id` through the function signature from `run_consolidation`.

**File**: `src/storage/consolidation.py:170-238`

### CHK-01: `_cleanup_old_checkpoints` — `conn` potentially undefined in `finally` ✅ FIXED

If `aiosqlite.connect()` fails, `conn` is not defined when `finally: await self._close_conn(conn)` runs.

Also, `DatabaseManager.create()` always created `SqliteSaver` regardless of `CHECKPOINT_ENABLED` config.

**Fix**: Added `conn = None` initialization before try block. Also added `CHECKPOINT_ENABLED` gate to `DatabaseManager.initialize()` so checkpointer is never created when disabled. Config now explicitly sets `enabled: false` in `config.yaml`, `.env`, and `.env.example`.

**File**: `src/storage/checkpoint.py:57-89`; `src/storage/database.py:25-33`; `config.yaml:31`

### CHK-02: CheckpointManager never closes underlying aiosqlite connection

`close()` only sets `self._checkpointer = None`. The original connection is never properly closed.

**File**: `src/storage/checkpoint.py:35-37`

### CHK-03: Unbounded `_managers` cache for CheckpointManager

**File**: `src/storage/checkpoint.py:109`

### MSG-01: No FTS5 DELETE/UPDATE triggers for messages ✅ FIXED

Only AFTER INSERT trigger exists. Deleted or updated messages leave stale FTS entries.

**Fix**: Added `BEFORE DELETE ON messages` and `BEFORE UPDATE ON messages` triggers on `messages_fts` that remove stale entries.

**File**: `src/storage/messages.py:56-87`

### MSG-02: `add_message` — ChromaDB add can fail after SQLite commit

If `collection.add()` fails after `conn.commit()`, the message exists in SQLite but is invisible to semantic search.

**File**: `src/storage/messages.py:101-121`

### MSG-03: `search_vector` N+1 queries ✅ FIXED

Each result opens a separate SQLite connection.

**Fix**: Refactored to batch-fetch messages from SQLite using `WHERE id IN (...)` with a single connection, eliminating N+1 queries.

**File**: `src/storage/messages.py:196-216`

### MSG-04: `get_messages` SQL injection via `limit` f-string ✅ FIXED

`f" LIMIT {limit}"` — not parameterized. Should use `?` placeholder.

**Fix**: Replaced f-string interpolation with parameterized `?` placeholder for the `limit` value.

**File**: `src/storage/messages.py:296`

### MSG-05: `search_keyword` FTS5 query sanitization strips too much ✅ FIXED

Removes parentheses, quotes, asterisks, colons, hyphens. A query like `"user preferences" NOT email` becomes `user preferences NOT email`, where `NOT` becomes an FTS5 keyword instead of a literal.

**Fix**: Rewrote sanitization to properly handle FTS5 operators: strips only truly problematic characters, preserves AND/OR/NOT as column qualifiers, and uses OR-joined terms for natural language queries.

**File**: `src/storage/messages.py:150-160`

### MSG-06: `ConversationStore` not thread-safe

Multiple methods open separate SQLite connections without locking. Concurrent access can cause race conditions.

**File**: `src/storage/messages.py` (entire class)

### SKL-05: `is` comparison for SystemMessage replacement unreliable after deserialization

`if msg is last_system` checks object identity, not equality. After LangGraph checkpoint deserialization, identity comparison fails, breaking skills prompt injection.

**File**: `src/skills/middleware.py:121-126`

### SKL-06: `skill_create` doesn't reload registry cache ✅ FIXED

After writing a new SKILL.md to disk, the global `_registry` cache isn't reloaded. New skill invisible until process restart.

**Fix**: Added `registry.reload()` call after successful skill file creation.

**File**: `src/skills/tools.py:136-183`

### SKL-07: `package_skill.py` imports non-existent `quick_validate` module

`from scripts.quick_validate import validate_skill` — the module doesn't exist. Script cannot execute.

**File**: `src/skills/skill-creator/scripts/package_skill.py:17`

### SKL-08: `run_eval.py` ignores `runs_per_query` and `num_workers`/`timeout` parameters

**File**: `src/skills/skill-creator/scripts/run_eval.py:137-180`

### SKL-09: `run_eval.py` calls `os.chdir()` modifying global CWD

Modifies the working directory for the entire process, breaking relative paths in the caller.

**File**: `src/skills/skill-creator/scripts/run_eval.py:11-12`

### SKL-10: `eval-viewer/__init__.py` contains `404: Not Found`

Not valid Python. Causes `SyntaxError` on import.

**File**: `src/skills/skill-creator/eval-viewer/__init__.py:1`

### SKL-11: `get_skill()` bypasses cache, always hits disk

**File**: `src/skills/registry.py:57-75`

### SUB-15: `datetime.now()` without timezone in scheduler

Scheduling uses naive `datetime.now()`, creating inconsistency with aware datetimes from other sources. DST issues possible.

**File**: `src/agents/subagent/scheduler.py:73,290`

### SUB-16: Recurring jobs lose "scheduled" status after first run

After execution, `INSERT OR REPLACE` overwrites the job's DB record with "completed" status. On restart, `_restore_scheduled_jobs` won't pick it up.

**File**: `src/agents/subagent/scheduler.py:293-340`

### SUB-17: `list_all()` crashes on corrupted config.yaml

No error handling for Pydantic `ValidationError`. One broken config prevents listing ALL subagents.

**File**: `src/agents/subagent/manager.py:217-240`

### SUB-18: `invoke()` result extraction — `result["messages"][-1].content` may hit ToolMessage ✅ FIXED

If the last message is a `ToolMessage`, `.content` is a tool result, not a final response. Crashes with `AttributeError` on unexpected types.

**Fix**: Now walks messages in reverse to find the last `AIMessage` with non-empty content. Falls back to the last message's content if no AI message found.

**File**: `src/agents/subagent/manager.py:202`

### SUB-19: Duplicate telegram tool definitions in two files

Both `subagent/tools.py` and `telegram/main.py` define `telegram_send_message_tool` and `telegram_send_file_tool`.

**Files**: `src/agents/subagent/tools.py:407-436`; `src/telegram/main.py:60-78`

### SUB-20: `SummarizationMiddleware` guard permanently disables summarization

After first successful summarization, `_last_summary_msg_count` is set higher than the current message count (which was reduced). Subsequent checks always skip summarization until messages grow past the old peak.

**File**: `src/agents/middleware/summarization.py:49-58`

### SUB-21: HTTP delete subagent doesn't invalidate cache

**File**: `src/http/main.py:841-853`

### SUB-22: HTTP 404 returns tuple body instead of status code

`return {"error": "Job not found"}, 404` from an `async def` returns a tuple as response body with HTTP 200, not a 404 status.

**File**: `src/http/main.py:1257-1265`

### EMAIL-DUP-01: 5 functions duplicated between `db.py` and `sync.py`

`_load_accounts`, `_save_account`, `_parse_email_date`, `_email_to_dict`, `_get_imap_connection` are fully duplicated. Any bug fix must be applied twice.

**Files**: `src/tools/email/db.py`; `src/tools/email/sync.py`

### EMAIL-DATA-03: `to_addrs`/`cc_addrs` stored as comma-joined string, parsed inconsistently

`email_get` does `replace(",", ", ")` for display. `send.py` splits on comma. Addresses with display names containing commas break the split.

**Files**: `src/tools/email/sync.py:236-237`; `src/tools/email/read.py:136-137`

### EMAIL-DATA-04: `attachments` stored as `str()` instead of `json.dumps()`

Python syntax like `[{'filename': 'test.pdf', 'size': 1024}]` is not valid JSON.

**File**: `src/tools/email/sync.py:238`

### EMAIL-LOG-04: `email_get` doesn't include `folder` in WHERE clause ✅ FIXED

Composite primary key is `(account_id, folder, message_id)`, but query only filters by `account_id` and `message_id`. Wrong email returned if same message_id exists in multiple folders.

**Fix**: Added `folder = :folder` to the WHERE clause and `folder` parameter to `email_get` (default `"INBOX"`).

**File**: `src/tools/email/read.py:119-126`

### EMAIL-LOG-03: LIKE search is case-sensitive

**File**: `src/tools/email/read.py:203-220`

### EMAIL-SYNC-01: `cooldown_minutes` not in `EmailSyncConfig`

Always falls back to default of 15 via `getattr()`. Not configurable.

**File**: `src/tools/email/sync.py:366,497`

### EMAIL-SYNC-02: `RATE_LIMIT_COOLDOWN` dict grows unboundedly

Entries added when rate-limited but never removed after cooldown expires.

**File**: `src/tools/email/sync.py:19`

### FS-01: `file_search._resolve_path` lacks skills-path exception ✅ FIXED

`filesystem.py` allows skills-path escape, but `file_search.py` doesn't. Skills can be created but not searched.

**Fix**: Added the same skills-path exception logic from `filesystem.py` — if the path starts with `data/users/{user_id}/skills/`, it resolves relative to CWD and verifies the user owns it.

**File**: `src/tools/file_search.py:19-33`

### FS-02: `files_edit` replaces ALL occurrences of old text

`str.replace()` replaces every instance. No option for "replace first only".

**File**: `src/tools/filesystem.py:201`

### FS-03: `files_delete` silently deletes directories with `shutil.rmtree()`

**File**: `src/tools/filesystem.py:235-240`

### FS-04: `files_rename` doesn't validate `new_name` for path traversal ✅ FIXED

`new_name` with `../` could escape the workspace. No `is_relative_to()` check.

**Fix**: Added validation that rejects `new_name` containing `/`, `\`, or `..`, plus `is_relative_to()` check to verify the resolved new path stays within the user workspace.

**File**: `src/tools/filesystem.py:288-297`

### FRC-01: `search_web` may call `.get()` on SearchResultWeb objects

Cloud SDK path returns `SearchResultWeb` objects (with attributes), not dicts. `.get()` would raise `AttributeError`.

**File**: `src/tools/firecrawl.py:164-167`

### FRC-02: Firecrawl tools missing `user_id` parameter

All other tools follow the `user_id` convention. Firecrawl tools use `channel="agent"` instead.

**File**: `src/tools/firecrawl.py` (multiple)

### TODOS-01: Todo ID truncated to 8 chars — collision risk at scale

`uuid.uuid4().hex[:8]` gives only 32 bits. Birthday paradox: ~50% collision chance at 65K entries.

**File**: `src/tools/todos/storage.py:71`

### TODOS-02: `todos_extract` prompt injection via unsanitized email content

Email subject and body are directly interpolated into the LLM prompt.

**File**: `src/tools/todos/tools.py:38`

### SEARCH-01: LIKE wildcard injection in contacts search

`%` and `_` in query are not escaped, allowing `query="%"` to return all contacts.

**File**: `src/tools/contacts/storage.py:400-421`

### SUM-01: `in_summarization_stream` flag not reset on error

If the SSE stream breaks during summarization, this flag stays `True` and filters out all subsequent AI content.

**File**: `src/http/main.py:503-506`

### SUM-02: SSE dedup heuristic truncates legitimate repeated content

`if response.count(response[:20]) > 1` can incorrectly truncate structured output, bullet lists, or code with repeated patterns.

**File**: `src/http/main.py:697-703`

### SUM-03: 200-char minimum summary length rejects valid short summaries

"Issues discussed: Python preferences. No action items." (~60 chars) would be rejected, preventing summarization and eventually causing token overflow.

**File**: `src/agents/middleware/summarization.py:111`

### HTTP-05: 500 errors leak full exception messages

`raise HTTPException(status_code=500, detail=str(e))` can expose file paths, DB queries, or API keys.

**File**: `src/http/main.py:734`

### HTTP-06: HITL approval handler only executes `files_delete`

Other tools requiring approval fall through to "Unknown tool" response.

**File**: `src/http/main.py:126-145`

### HTTP-07: No CORS middleware, no authentication on any endpoint

All endpoints including destructive ones are unauthenticated. `user_id` can be set to any value.

**File**: `src/http/main.py`

### DB-01: `SqliteSaver.from_conn_string` uses `sqlite:///` URL format

May not work with LangGraph's `SqliteSaver` which expects a file path.

**File**: `src/storage/database.py:33`

### DB-02: Memory model class duplication

Two `Memory` classes exist: one Pydantic (`src/memory/models.py`) and one dataclass (`src/storage/memory.py`), with different fields.

**Files**: `src/memory/models.py`; `src/storage/memory.py`

### DB-03: `datetime.utcnow()` deprecated in Python 3.12+

**File**: `src/memory/models.py:24`

---

## LOW 🔵

### MEM-17: `_extraction_count` class-level mutable dict, never used

**File**: `src/storage/middleware/memory.py:210`

### MEM-18: `search_semantic` doesn't set `superseded_by`/`is_superseded` on returned Memories ✅ FIXED

Defaults to `None`/`False`, making all results appear non-superseded even if they are.

**Fix**: `search_semantic`, `search_hybrid`, and `search_fts` now retrieve full rows from SQLite (including `is_superseded` and `superseded_by`) and properly construct Memory objects with all fields.

**File**: `src/storage/memory.py:668-683`

### MEM-19: `add_memory` UNIQUE constraint violation with `is_update=True` ✅ FIXED

`_generate_id(trigger, action)` produces deterministic IDs. When `is_update=True` and a similar memory exists, the code tried to INSERT a new row with the same ID as the superseded memory, causing `sqlite3.IntegrityError: UNIQUE constraint failed`.

**Fix**: When superseding, generate a new ID using `trigger + action + timestamp_fraction` to avoid collisions. Track `effective_id` through all code paths so vector updates and return values use the correct ID. Also added `MIN(confidence + boost, cap)` SQL to prevent confidence exceeding 1.0.

**File**: `src/storage/memory.py:542-636`

### SKL-12: Redundant `SystemMessage` construction — both branches identical

`if isinstance(new_content, list)` and `else` both create `SystemMessage(content=new_content)`.

**File**: `src/skills/middleware.py:115-118`

### SKL-13: `_get_user_skills_dir` defaults to misleading path when `user_id` is None

**File**: `src/skills/middleware.py:43`

### SKL-14: `content_blocks` always list — legacy branch is dead code

`hasattr(last_system, "content_blocks") and isinstance(..., list)` is always True. Else branch unreachable.

**File**: `src/skills/middleware.py:100-112`

### SKL-15: User skills can silently shadow system skills with same name

`get_all_skills()` concatenates system + user with no deduplication.

**File**: `src/skills/registry.py:43-51`

### SKL-16: `load_skill` bypasses name validation

**File**: `src/skills/storage.py:46-58`

### SKL-17: `_is_valid_skill_name` allows digits-only names

**File**: `src/skills/models.py:104-116`

### SKL-18: `parse_skill_file` returns `None` for empty body — no error

**File**: `src/skills/models.py:55-60`

### SKL-19: `run_loop` blinded history leaks test info via `results` field

**File**: `src/skills/skill-creator/scripts/run_loop.py:215-217`

### SKL-20: `shorten_prompt` double-sends the original prompt to LLM

**File**: `src/skills/skill-creator/scripts/improve_description.py:144`

### SKL-21: `parse_skill_md` crashes on empty file

**File**: `src/skills/skill-creator/scripts/utils.py:7-13`

### SKL-22: `parse_skill_md` has different YAML multiline handling than `parse_skill_file`

**File**: `src/skills/skill-creator/scripts/utils.py:33-44`

### SKL-23: `_kill_port` can kill unrelated processes

**File**: `src/skills/skill-creator/eval-viewer/generate_review.py:288-306`

### SKL-24: Non-deterministic skill loading order via `Path.iterdir()`

**File**: `src/skills/storage.py:30-31`

### SKL-25: Empty history causes division by zero in `generate_report.py`

**File**: `src/skills/skill-creator/scripts/generate_report.py:206-209`

### SUB-22: `_managers` cache for SubagentManager never evicts

**File**: `src/agents/subagent/manager.py:458-466`

### SUB-23: No limit on subagent count per user

**File**: `src/agents/subagent/manager.py`

### SUB-24: Job IDs only 8 hex chars — collision risk

**File**: `src/agents/subagent/scheduler.py:246,310`

### SUB-25: `_restore_scheduled_jobs` reschedules all past jobs 30s from now

One-time jobs lose their original intended time.

**File**: `src/agents/subagent/scheduler.py:165-183`

### SUB-26: No authorization check on `subagent_progress` and `cancel_job`

Any user can check or cancel any job.

**Files**: `src/agents/subagent/tools.py:170-247`; `scheduler.py`

### SUB-27: `on_summarize` callback type hint is sync but implementation is async

**File**: `src/agents/factory.py:28,73`

### SUB-28: `SubagentConfig` uses deprecated Pydantic v1 `class Config` style

**File**: `src/agents/subagent/config.py:14-15`

### EMAIL-MISC-01: `detect_provider` uses substring instead of suffix matching

`"gmail.com" in email` matches `user@gmail.com.evil.com`.

**File**: `src/tools/email/db.py:241-252`

### EMAIL-MISC-02: `init_db` called on every `get_engine()` — unnecessary I/O

**File**: `src/tools/email/db.py:25-30`

### EMAIL-MISC-03: `email_accounts` returns password in accessible dict

**File**: `src/tools/email/account.py:157-161`

### EMAIL-MISC-04: Missing composite index for common email queries

**File**: `src/tools/email/db.py:57-82`

### EMAIL-MISC-05: `email_accounts` missing `user_id` validation — crashes with empty string

**File**: `src/tools/email/account.py:143-161`

### EMAIL-MISC-06: Duplicate `import asyncio` in sync.py ✅ FIXED

**Fix**: Removed the duplicate `import asyncio` inside the function body (line 570). Already imported at module level (line 3).

**File**: `src/tools/email/sync.py:3,570`

### CONTACTS-04: `save_contacts` duplicate check only matches `source='email'`

Contacts with `source='manual'` are never matched as duplicates.

**File**: `src/tools/contacts/storage.py:295`

### TODOS-03: No email format validation in `contacts_add`

**File**: `src/tools/contacts/tools.py:138`

### FS-05: `files_read` offset is 0-based but documented as "line number"

**File**: `src/tools/filesystem.py:100`

### FS-06: `files_write` versioning has try/except but `files_edit` versioning doesn't

**File**: `src/tools/filesystem.py:153-160 vs 203-207`

### FS-07: `files_glob_search` allows expensive `**/*` patterns without limit

**File**: `src/tools/file_search.py:55`

### FS-08: `files_grep_search` silently swallows read errors

**File**: `src/tools/file_search.py:117-128`

### VAULT-02: `vault_unlock` has `master_password` before `user_id` — inconsistent with convention

**File**: `src/tools/vault/__init__.py:18`

### VAULT-03: Master password stored in process memory indefinitely

Decrypted credentials persist until `lock()` or process restart.

**File**: `src/tools/vault/store.py:45-46`

### SHELL-02: `_is_allowed()` called twice, `_get_shell_config()` read 2-3 times per execution

**File**: `src/tools/shell.py:73-81`

### SHELL-03: `_get_root_path` creates workspace directory as side effect

**File**: `src/tools/shell.py:40-44`

### CFG-01: Thread-unsafe singleton in `get_settings()`

**File**: `src/config/settings.py:245-253`

### CFG-02: Ollama "local" provider never reachable via `create_model_from_config()`

Both `ollama` and `ollama-cloud` map to `create_ollama_cloud_model()`. `create_ollama_local_model()` exists but is dead code.

**File**: `src/llm/providers.py:113-116`

### LOG-01: Opens/closes log file on every call

**File**: `src/app_logging.py:130-133`

### LOG-02: Thread-unsafe logger singleton

**File**: `src/app_logging.py:198-207`

### DB-04: Singleton pattern not thread-safe

`__new__` without locking allows two instances under concurrency.

**File**: `src/storage/database.py:20-23`

### HTTP-08: CLI doesn't handle `role == "summary"` messages

Maps all non-user messages to `AIMessage`, injecting summaries as AI responses.

**File**: `src/cli/main.py:123-128`

---

## Architectural Concerns

These aren't bugs per se, but design issues that affect reliability and maintainability:

1. ~~**Dual-store inconsistency**: SQLite + ChromaDB writes have no transactional coordination. Failure of either store creates silent data divergence.~~ **Partially addressed**: WAL mode + context managers ensure SQLite consistency. ChromaDB still lacks rollback coordination.

2. ~~**Daemon-thread extraction**: LLM memory extraction runs in unmanaged daemon threads with no error surface to the user, no retry logic, and no concurrency control.~~ **Addressed**: Turn-based extraction every 3 turns instead of daemon threads. Immediate extraction for corrections.

3. ~~**No user-facing memory management**: No tools for listing, deleting, or editing memories through conversation. Users can't correct what the LLM extracted wrong.~~ **Fixed**: Added `memory_search_insights`, `insight_list`, `insight_remove`, `insight_search`, `memory_search_all`, `memory_connect`, `memory_stats` tools. Also `profile_set` with structured data.

4. ~~**Brittle keyword-based extraction**: English-only keyword lists for trigger detection miss semantic intent ("I'd rather use Python", "Actually, could you...").~~ **Partially addressed**: Added turn-based extraction (every 3 turns) as primary mechanism alongside correction keywords. Semantic extraction still LLM-dependent.

5. ~~**Per-write confidence decay**: Running `maybe_decay_confidence()` (a full-table UPDATE) on every `add_memory()` call is an O(n) blocking operation that gets slower as memory grows.~~ **Partially addressed**: WAL mode + proper context managers. Decay still runs on every add but with better connection handling. For production, should be a periodic background job.

6. **Consolidation async path broken**: `trigger_consolidation()` from a daemon thread can't create async tasks and can't use `asyncio.run()` when a loop is already running.

7. **Confusing naming**: "Memory" refers to both the learned-pattern store (MemoryStore) and conversation history (ConversationStore). `memory_get_history` and `memory_search` query conversation history, not memories.

8. ~~**Unbounded caches**: `_memory_store_cache`, `_stores` (ConversationStore), `_managers` (SubagentManager), `_agent_pools`, `_checkpoint_managers`, `_model` — all grow without eviction.~~ **Partially addressed**: MemoryStore cache uses WAL + context managers per operation. Still unbounded dict. Checkpointer cache is gated by `CHECKPOINT_ENABLED=false` by default.

9. ~~**Per-function SQLite connections**: Nearly every method in MemoryStore and ConversationStore opens a new connection, performs one operation, and closes it. No connection pooling or context managers.~~ **Fixed**: All SQLite operations now use `_connect()` context manager with WAL mode, `row_factory = sqlite3.Row`, and guaranteed commit/rollback/close.

10. **Agent factory global state**: `set_skill_registry()` and `get_model()` mutate globals without locking, causing cross-user contamination in concurrent requests.

## Batch 3 Fixes (additional 10)

- SUB-11: Ghost directory after failed validation → moved `mkdir` after validation, cleanup on failure
- SUB-18: `invoke()` hits ToolMessage → now walks messages in reverse for last AI message
- EMAIL-RES-02: SMTP connection leak → added `try/finally` with `server.quit()` + `server.close()` fallback
- CONTACTS-01: Engine per-call → added `_engines` cache dict, reuses engine per user_id
- MEM-05: `before_agent` returns None → now returns `{"messages": current_messages}` instead of `None`
- MEM-06: `trigger_consolidation` can't create async tasks → uses `ThreadPoolExecutor` like SUB-03 fix
- SKL-06: `skill_create` doesn't reload registry → added `registry.reload()` after creation
- FS-01: `file_search._resolve_path` lacks skills-path → added same skills-path exception as `filesystem.py`
- CONS-02: Greedy regex → replaced with balanced-brace matching, tries each `{` start point
- CONS-03: Substring matching too broad → replaced with 60% word-overlap threshold
