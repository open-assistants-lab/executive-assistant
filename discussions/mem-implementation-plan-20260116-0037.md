# Embedded Memory (mem.db) Implementation Plan (2026-01-16 00:37)

## 1) Decisions + Config
- Storage: `data/users/{thread_id}/mem/mem.db`
- Indexing: **FTS only**
- Extraction triggers:
  - `/remember` command
  - user says "remember ..."
  - optional auto‑extract after each user message (`MEM_AUTO_EXTRACT=true`)
- Settings to add:
  - `MEM_AUTO_EXTRACT`
  - `MEM_CONFIDENCE_MIN`
  - `MEM_MAX_PER_TURN`
  - `MEM_EXTRACT_MODEL`
  - `MEM_EXTRACT_PROVIDER`
  - `MEM_EXTRACT_TEMPERATURE=0`

## 2) Storage Helper
- New `mem_storage.py` modeled after `db_storage.py` / `kb_storage.py`:
  - `get_mem_db_path(thread_id)` → `data/users/{thread_id}/mem/mem.db`
  - `get_connection(thread_id)` returns DuckDB connection

## 3) Schema
```
memories(
  id UUID,
  owner_type TEXT,      -- thread|user
  owner_id TEXT,
  memory_type TEXT,     -- profile|preference|fact|task|note
  key TEXT,             -- normalized key for conflicts (timezone, language, role)
  content TEXT,
  confidence REAL,
  status TEXT,          -- active|deprecated|deleted
  source_message_id TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```
- FTS index on `content` (and optionally `key`)

## 4) Tools (verb‑first)
- `create_memory`, `update_memory`, `delete_memory`
- `list_memories`, `search_memory`
- `forget_memory` (alias to delete/deprecate)
- Scope tools to `thread_id` first; switch to `user_id` after merge

## 5) Extraction Pipeline (detailed)
**Trigger detection**
- `/remember`: treat remainder as explicit memory input
- "remember ...": treat as explicit memory input
- If `MEM_AUTO_EXTRACT=true`, run extraction for every user message

**Auto extraction flow**
1) Rule‑gate: stable indicators only (timezone, language, role, preferences)
2) Call **small extraction LLM** (separate instance) to return JSON:
   ```
   [{"memory_type":"preference","key":"language","content":"User prefers English","confidence":0.92}]
   ```
3) Normalize + dedupe:
   - if same `key`, mark old row `deprecated`, insert new
4) Persist + update FTS
5) Update FTS index after inserts/updates

## 6) Retrieval Injection
- On each user request, query `search_memory` using the latest message
- Inject top 2–5 memories into prompt as:
  ```
  [User Memory]
  - ...
  ```
- Only include `status=active` and `confidence>=threshold`

## 7) Merge Behavior
- On thread merge → set `owner_type=user`, `owner_id=user_id`
- Dedupe by `key` + latest `updated_at`

## 8) Privacy / Safety
- Sensitive filter (PII/credentials) requires explicit `/remember`
- Provide `forget_memory` for user deletions

## 9) Tests
- Path resolution for `mem.db` (thread‑scoped)
- CRUD tool tests + FTS search
- Auto extraction with stub LLM
- `/remember` command test

## 10) Docs
- Document `mem/` folder, tools, `/remember`, and auto‑extract flag
