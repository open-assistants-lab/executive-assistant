# SeekDB Research + KB Replacement Plan

## Sources Consulted
- https://github.com/oceanbase/seekdb (README, develop branch)
- https://github.com/oceanbase/pyseekdb (README, main branch)
- GitHub search metadata (seekdb/seekdb-doc/pyseekdb/mine-kb)

## Executive Summary
SeekDB (OceanBase seekdb) is an Apache 2.0, AI-native search database that supports embedded mode, full-text search, vector search, and hybrid search. The official Python SDK (`pyseekdb`) provides a collection-based API and supports embedded local storage via a filesystem path, plus server/OceanBase modes. For Executive Assistant, SeekDB can replace the DuckDB KB when hybrid search (vector + text) or embedded embeddings are important, but it introduces higher operational complexity and dependency weight compared to DuckDB FTS.

## Capability Fit for Executive Assistant
**Strengths**
- Embedded mode with local persistence (`pyseekdb.Client(path=...)`) fits per-thread KB files.
- Built-in hybrid search (`hybrid_search`) + full-text via `where_document` + vector kNN.
- SDK supports default local embeddings (all-MiniLM-L6-v2, 384 dims) and custom embeddings (e.g., OpenAI) without changing the KB interface.
- MySQL-compatible SQL for advanced use cases if needed later.
- Apache 2.0 license.

**Constraints / Risks**
- Heavier dependency footprint vs DuckDB; SeekDB is a C++ engine with its own runtime artifacts.
- Embedded mode still introduces a new storage stack; runtime behavior and thread-safety need validation.
- Default embedding requires local model files and may download assets at runtime.
- Different data model: collection-centric with one text per record; metadata is dict (vs string in current KB).
- Newer project; maturity/perf under real workload needs a PoC.

## Recommendation
Move ahead with SeekDB as the **default KB backend** (full replacement). No data migration is required—new KB data will live in SeekDB collections while DuckDB tables remain untouched, allowing a rollback by reverting to the previous commit/configuration if necessary (rather than re-enabling DuckDB at runtime).

## Integration Plan (Phased)

### Phase 0: PoC Bench
- Add a small PoC script (not part of runtime) to index a representative KB corpus.
- Compare:
  - Ingestion time (per 1K docs)
  - Search latency (FTS-only vs hybrid)
  - Memory + disk usage
  - Relevance on internal queries
- Decide whether SeekDB is a net upgrade.

### Phase 1: Add KB Backend Abstraction
- Introduce `KBBackend` interface in `src/executive_assistant/storage/kb_backend.py`:
  - `create_collection(name, documents, metadata)`
  - `add_documents(name, documents)`
  - `search(query, table_name, limit, mode)`
  - `list_tables()` / `describe_table()` / `delete_table()`
- Wire `KBStorage` to select backend via `KB_BACKEND=duckdb|seekdb`.

### Phase 2: SeekDB Backend Implementation
- New module: `src/executive_assistant/storage/seekdb_storage.py`.
- Per-thread database path: `data/users/{thread_id}/kb/seekdb/` (directory, not a single file).
- Initialize `pyseekdb.Client(path=..., database="kb")` per call (or pool per thread).
- Collection mapping:
  - KB table name -> SeekDB collection name.
  - `content` -> `documents`
  - `metadata` string -> metadata dict (e.g., `{ "metadata": "..." }`)
- Search behavior:
  - **FTS-only**: `collection.get(where_document={"$contains": query})` (limit N)
  - **Hybrid**: `collection.hybrid_search(query={...}, knn={query_texts=[query]}, rank={"rrf":{}})`
  - Add `search_mode` parameter or auto-hybrid if embedding_function is set.

### Phase 3: Tool Wiring (No API Break)
- Keep tool names and signatures (`create_kb_table`, `search_kb`, `kb_list`, `kb_describe`, `kb_delete`, `kb_add_documents`).
- Internally route to the selected backend.
- Convert output to current string response format to preserve UX.

### Phase 4: Configuration
- New settings:
- `KB_BACKEND=duckdb|seekdb` (default: seekdb for full replacement but duckdb stays as rollback config)
  - `SEEKDB_DATA_ROOT=./data/seekdb` (optional override)
  - `SEEKDB_EMBEDDING_MODE=default|local|api`
  - `SEEKDB_EMBEDDING_MODEL=all-MiniLM-L6-v2` (if local)
  - `SEEKDB_API_KEY` (if api)
- Ensure embedded SeekDB path resolves under `data/users/{thread_id}/kb/` by default.

### Phase 5: Migration + Rollback
- Migration script to read DuckDB KB tables and upsert into SeekDB collections.
- Keep both for one release; allow rollback by switching `KB_BACKEND`.
- Provide command to compare search results between backends for the same query.

### Phase 6: Tests + Observability
- Unit tests for SeekDB backend:
  - create/add/search/delete/list
  - hybrid search only if embedding_function set
- Integration test for backend switching (duckdb vs seekdb).
- Add basic metrics logging (index time, query time).

## Decision Checklist
- Does SeekDB improve relevance enough to justify new dependency?
- Does embedded mode handle 20–100 threads without locks or slowdowns?
- Is disk/CPU usage acceptable under 10GB per KB?
- Are default embeddings acceptable (quality + local runtime cost)?

## Next Actions (If You Approve)
1. Add backend abstraction + SeekDB backend module (no tool API change).
2. Implement config flags and minimal docs.
3. Build a PoC/migration script for side-by-side evaluation.
