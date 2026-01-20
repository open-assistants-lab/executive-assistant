# Plan: Introduce LangChain Agent Runtime (Keep Custom Graph)

## Goal
Adopt the **native LangChain agent** (and its middleware features) as the primary runtime **without removing** the existing custom LangGraph agent. The custom agent remains available for fallback or future comparison. A/B routing is **disabled** for now.

## Non-Goals
- Do not delete or refactor the existing custom graph (`src/executive_assistant/agent/graph.py`).
- No A/B testing or multi-agent routing in this phase.
- No change to storage paths or tool semantics.

## High-Level Approach
1) Add a LangChain agent builder (`create_langchain_agent`) using `langchain.agents.create_agent`.
2) Add a runtime selector (`AGENT_RUNTIME=langchain|custom`) with **default = langchain**.
3) Keep the current graph as a fallback (`AGENT_RUNTIME=custom`).
4) Make middleware features configurable via environment flags (summary, call limits, retries).
5) Ensure the runtime returns the same event shape expected by `stream_agent_response`.
6) Archive Orchestrator/Worker agents (disable tools and scheduled job execution).

---

## Implementation Status (2026-01-16)

Completed work mapped to this plan:
- **Runtime selection**: `AGENT_RUNTIME`/`AGENT_RUNTIME_FALLBACK` wired in `src/executive_assistant/main.py` with per-channel prompts; custom graph retained as fallback.
- **LangChain agent builder**: `src/executive_assistant/agent/langchain_agent.py` added with middleware support and fail-fast import of `langchain.agents.create_agent`.
- **Middleware config**: `MW_*` settings added in `src/executive_assistant/config/settings.py` and documented in `.env.example`/`README.md`. (`MW` = middleware.)
- **Event compatibility**: stream normalization helper added in `src/executive_assistant/channels/base.py` to handle `messages`, `agent.messages`, `output.messages`, and `final.messages`.
- **Runtime-aware state**: `BaseChannel` only injects custom state fields for `AGENT_RUNTIME=custom`; LangChain runtime sends only `messages`.
- **Dev server**: `src/executive_assistant/dev_server.py` respects `AGENT_RUNTIME` (LangChain vs custom).
- **Docs**: updated `README.md` with runtime + middleware notes and integration test instructions; updated `docs/langgraph-studio-setup.md` with runtime selection.
- **Dependencies**: added `langgraph-prebuilt` (required for `langchain.agents.create_agent`), bumped `langchain-community` to `>=0.4.1` and `langchain-mcp-adapters` to `>=0.2.1`; updated `uv.lock`.
- **Testing scaffold (LangChain reference)**:
  - Unit test for LangChain runtime tool call: `tests/test_langchain_agent_unit.py` (uses fake model + tool).
  - Event normalization test: `tests/test_event_normalization.py`.
  - Live integration test (AgentEvals + VCR): `tests/test_langchain_agent_integration.py` (skips unless `RUN_LIVE_LLM_TESTS=1` and API key set).
  - VCR config: `tests/conftest.py`.
  - Tool contract suite: `tests/test_tool_contracts.py`.
  - Cassette recording helper: `scripts/pytest_record_cassettes.sh`.
- **Orchestrator/Worker archived**:
  - Tools disabled and removed from registry; scheduled jobs now mark due entries failed (archived).
  - Cron parsing moved to shared utility (`src/executive_assistant/utils/cron.py`) for reminders.
  - Orchestrator/worker tests skipped; doc annotated as archived.

Test results (local):
- `tests/test_langchain_agent_unit.py`: PASS
- `tests/test_event_normalization.py`: PASS
- `tests/test_langchain_agent_integration.py`: SKIP (requires live LLM + key)
- `tests/test_tool_contracts.py`: PASS

Known gaps:
- Live integration tests are gated (`RUN_LIVE_LLM_TESTS=1` + provider API key); no cassette has been recorded yet.
- Summarization parity between custom structured summary and LangChain middleware is not validated in tests.
- Orchestrator/Worker agents are archived; scheduled jobs are disabled until re-enabled.

Next steps:
- Record the first VCR cassette via `./scripts/pytest_record_cassettes.sh` to lock a baseline trajectory.
- Add a focused regression test for summarization behavior (LangChain middleware vs custom) once desired behavior is finalized.
- Decide whether to enable LangSmith evals for trajectory logging in CI (optional).
- If re-enabling Orchestrator/Worker: remove archive guards, restore tool registry entries, and unskip worker/orchestrator tests.

---

## Post-Implementation Issues & Fixes (2026-01-16)

### Issue 1: Checkpoint Schema Missing `checkpoint_ns` Column

**Error**:
```
column "checkpoint_ns" does not exist
```

**Root Cause**: `langgraph-checkpoint-postgres` 2.x introduced a `checkpoint_ns` (namespace) column to support multiple isolated checkpoint states per thread. The existing schema was based on 1.x.

**Fix**: Updated `migrations/001_initial_schema.sql` to add `checkpoint_ns` to all checkpoint tables (init script remains non-destructive; it uses `CREATE TABLE IF NOT EXISTS` only).

```sql
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',  -- NEW: namespace column
    checkpoint_id TEXT NOT NULL,
    -- ...
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',  -- NEW
    -- ...
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',  -- NEW
    -- ...
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```

**What `checkpoint_ns` does**: Allows multiple isolated checkpoint states within the same thread. For example, you could have separate states for "draft" vs "published" versions, or different subagent states within a single conversation thread.

**Note on existing DBs**: The init script will not drop or alter existing tables. For a fresh DB it will build the required empty schema. For existing installations, a manual migration (ALTERs) or a controlled reset is required to add `checkpoint_ns`.

### Issue 2: Import Path Changed in langgraph-checkpoint-postgres 2.x

**Error**:
```
ModuleNotFoundError: No module named 'langgraph.checkpoint.postgres'
```

**Root Cause**: Version 2.x of `langgraph-checkpoint-postgres` changed the module name from dot-notation to underscore-notation (PEP 8 compliance).

**Fix**: Updated `src/executive_assistant/storage/checkpoint.py` to try the new import first, with fallback:

```python
# langgraph-checkpoint-postgres 2.x uses underscore naming
try:
    from langgraph_checkpoint_postgres import PostgresSaver
except ImportError:
    # Fallback to old import path for 1.x
    from langgraph.checkpoint.postgres import PostgresSaver
```

### Issue 3: LangChain Agent Event Format Not Recognized

**Error**: Executive Assistant showed "typing..." for a few seconds then returned "I didn't generate a response. Please try again."

**Root Cause**: The LangChain agent (via `create_agent`) emits events in a different format than expected:
- Expected: `{"messages": [AIMessage(...)]}`
- Actual: `{"model": {"messages": [AIMessage(...)]}}`

The `_extract_messages_from_event` method in `src/executive_assistant/channels/base.py` was only checking for direct `messages` keys or nested under `agent`, `output`, `final`—but not `model`.

**Fix**: Extended the event extraction logic to check the `model` key:

```python
def _extract_messages_from_event(self, event: Any) -> list[BaseMessage]:
    """Extract messages from LangGraph/LangChain stream events."""
    if not isinstance(event, dict):
        return []

    # Direct messages array
    if isinstance(event.get("messages"), list):
        return event["messages"]

    # LangChain agent middleware events
    for key in ("model", "agent", "output", "final"):  # Added "model"
        value = event.get(key)
        if isinstance(value, dict) and isinstance(value.get("messages"), list):
            return value["messages"]

    return []
```

**Debug logging added**: To catch such issues earlier, added event logging in `stream_agent_response`:

```python
async for event in self.agent.astream(state, config):
    event_count += 1
    if event_count <= 5:  # Log first 5 events for debugging
        print(f"[DEBUG] Event {event_count}: {type(event).__name__} = {event!s}")
    # ...
```

---

## Detailed Implementation Steps

### 1) Configuration Switch (Disable A/B)
**Files:** `src/executive_assistant/config/settings.py`, `.env.example`, `README.md`

Add settings:
- `AGENT_RUNTIME` (default: `langchain`, allowed: `langchain`, `custom`)
- `AGENT_RUNTIME_FALLBACK` (optional: `custom`)
- **Explicitly disable A/B**: set `AB_ENABLED=false` (or ignore AB settings when `AGENT_RUNTIME=langchain`)

### 2) LangChain Agent Builder
**New file:** `src/executive_assistant/agent/langchain_agent.py`

Implement:
- `async def create_langchain_agent(model, tools, checkpointer, system_prompt) -> Runnable`
  - Use `langchain.agents.create_agent` (primary and only path)
  - **Dev validation:** verify the class exists in Python at runtime; if missing, fail fast with a clear error
  - Provide `model`, `tools`, `system_prompt`
  - Attach middleware (see Step 3)
  - Ensure checkpointer is wired for persistence (aligns with LangGraph best practices)

### 3) Middleware Options (LangChain-native)
**Files:** `src/executive_assistant/agent/langchain_agent.py`, `src/executive_assistant/config/settings.py`

Config toggles:
- `MW_SUMMARIZATION_ENABLED` + thresholds
- `MW_MODEL_CALL_LIMIT` (max LLM calls)
- `MW_TOOL_CALL_LIMIT` (max tool calls)
- `MW_TOOL_RETRY` (retry policy)
- `MW_MODEL_RETRY` (retry policy)
- (Optional) `MW_HITL_ENABLED` for human approval

Map toggles to LangChain middleware classes per `docs/middleware.md`.

#### 3a) Summarization Strategy: LangChain Middleware + mem_db Complement
**Docs:** `docs/structured-summary-fixes-implementation.md`, `docs/middleware.md`, `docs/kb/langchain-middleware.md`

**Decision**: Use LangChain's `SummarizationMiddleware` in LangChain runtime mode.

**Rationale**:
- LangChain's `SummarizationMiddleware` is a production-tested, token-reduction middleware
- It integrates seamlessly with the agent lifecycle and checkpointing
- Reduces engineering overhead of maintaining custom summarization logic

**Implementation**:
- **LangChain runtime default:** enable `MW_SUMMARIZATION_ENABLED=true`
- **Disable custom structured summary** when `AGENT_RUNTIME=langchain` to avoid double summarization
- Custom structured summary features (KB-first routing, topic isolation, context contamination fixes) remain active ONLY in `AGENT_RUNTIME=custom` mode

**mem_db as Complementary Memory Layer**:

The existing `mem_db` (DuckDB-based, `src/executive_assistant/storage/mem_storage.py`) serves a different purpose than summarization:

| Feature | SummarizationMiddleware | mem_db |
|---------|------------------------|--------|
| Purpose | Token reduction for context window | Persistent memory across sessions |
| Scope | Single thread (checkpointer) | Cross-thread, user-scoped |
| Storage | Compressed checkpoints | Structured facts, preferences, tasks |
| Search | None | FTS (BM25), confidence scoring |
| Latency | Inline with agent turns | On-demand retrieval |

**mem_db improvements** (future work):
- Better integration with LangChain runtime via custom tool
- Semantic search on top of existing FTS
- Memory consolidation from SummarizationMiddleware output
- Cross-thread memory sharing for user preferences

**Key insight**: SummarizationMiddleware compresses conversation history; mem_db stores persistent facts. They complement, not replace, each other.

### 4) Runtime Selection
**File:** `src/executive_assistant/main.py`

Change startup:
- If `AGENT_RUNTIME=langchain`, build LangChain agent.
- If `AGENT_RUNTIME=custom`, build existing graph.
- Keep both code paths; do not delete custom graph.

#### 4a) Subagent Scope (Executive Assistant vs Orchestrator/Workers)
**Doc:** `docs/subagent_architecture.md`

Orchestrator/Workers are archived in this phase to avoid cascading runtime changes.
Only Executive Assistant uses LangChain runtime for now.

### 5) Event Shape Compatibility
**File:** `src/executive_assistant/channels/base.py` (or adapter module)

Validate that the LangChain agent emits events compatible with the current streaming logic:
- Expected event keys: `messages` or `agent.messages` (current logic handles both).
- If necessary, add a thin adapter that normalizes the stream into the same shape.

### 6) Studio + Dev Server
**File:** `src/executive_assistant/dev_server.py`

Make the dev server respect `AGENT_RUNTIME` so Studio shows the same agent used in testing.

### 7) Documentation
**Files:** `README.md`, `docs/langgraph-studio-setup.md`

Update docs:
- Explain `AGENT_RUNTIME` and default behavior.
- Note that A/B is disabled for now.
- Call out middleware flags and when to use them.
- Document the structured-summary vs middleware summarization decision.

### 8) Tests (Minimal)
**File:** `tests/test_langchain_agent_runtime.py`

Add minimal tests to:
- Ensure `create_langchain_agent` builds successfully.
- Ensure a simple message returns at least one `AIMessage`.
- Ensure the runtime switch selects the correct agent.

---

## LangGraph Best-Practice Alignment (From docs/)
- **Compile once, reuse** (`docs/langgraph_introduction.md`, `docs/langgraph_agents_tutorial.md`): build the LangChain agent at startup.
- **Stable thread_id** (`docs/langgraph_agents_tutorial.md`): pass `thread_id` via config for checkpointed state.
- **Controlled loops** (`docs/middleware.md`): use middleware call limits rather than custom counters when in LangChain mode.
- **ReAct loop ownership** (`docs/react_agent_from_scratch_langgraph.md`): do not reimplement the agent↔tools loop when using `create_agent`.
- **Subagent boundaries** (`docs/subagent_architecture.md`): keep Orchestrator/Workers unchanged in this phase.

---

## Deployment: FastAPI (Not LangGraph Up)

**Decision**: Deploy via FastAPI instead of `langgraph up` to avoid platform costs.

### Current Infrastructure

**PostgreSQL Setup** (from `docker-compose.yml`):
- `postgres:18-alpine` image
- Custom schema with LangGraph checkpoint tables
- Audit tables (conversations, messages, user_registry, file_paths, db_paths)
- Init script: `migrations/001_initial_schema.sql`
- Data volume: `pgdata:/var/lib/postgresql`

**Note**: Keep the old init script handy for rollback (rename to `.backup` before migration).

### Do We Need Redis?

**Short answer: No, Redis is NOT required for basic operation.**

| Use Case | Required? | Alternative |
|----------|-----------|-------------|
| Checkpointer persistence | No | PostgreSQL sufficient |
| Session storage | No | PostgreSQL with checkpointer |
| Rate limiting | Optional | In-memory or Postgres-based |
| Caching | Optional | Postgres or skip initially |
| Pub/Sub (multi-instance) | Optional | Skip for single-instance |

**Recommendation**: Skip Redis for initial FastAPI deployment. Add later if needed for:
- Horizontal scaling (multiple instances)
- Aggressive caching
- Real-time pub/sub features

### FastAPI Deployment Architecture (Use Existing Entrypoint)

```yaml
# Updated docker-compose.yml (add FastAPI service)
services:
  postgres_db:
    # ... existing config ...

  executive_assistant_api:
    build: .
    command: uv run executive_assistant
    environment:
      - EXECUTIVE_ASSISTANT_CHANNELS=http
      - AGENT_RUNTIME=${AGENT_RUNTIME:-langchain}
    ports:
      - "8000:8000"
    depends_on:
      - postgres_db
```

### Postgres Checkpointer Setup

Use the existing implementation in `src/executive_assistant/storage/checkpoint.py` (no new checkpointer module needed).

### Fresh Start: Wiping Volumes

To start with fresh checkpointer data:

```bash
# Stop and remove volume
docker-compose down -v

# Or clear specific tables
docker exec -it executive_assistant-postgres_db-1 psql -U executive_assistant -d executive_assistant_db -c "TRUNCATE checkpoint_blobs, checkpoint_writes, checkpoints CASCADE;"

# Restart
docker-compose up -d
```

**Keep backup of old schema**:
```bash
cp migrations/001_initial_schema.sql migrations/001_initial_schema.sql.backup
```

---

## Additional Knowledge Base Files Created

**Location**: `docs/kb/`

**LangChain topics**:
- `langchain-agents.md` - create_agent API, tools, system prompts
- `langchain-middleware.md` - All built-in middleware (10 types)
- `langchain-streaming.md` - Token streaming, SSE, WebSocket patterns
- `langchain-structured-output.md` - Pydantic schemas, ToolStrategy, ProviderStrategy
- `langchain-guardrails.md` - Input/output validation, LLM-based safety
- `langchain-context-engineering.md` - Write, Select, Compress, Isolate strategies

**LangGraph topics**:
- `langgraph-mcp.md` - Model Context Protocol integration
- `langgraph-human-in-the-loop.md` - Interrupts, approval workflows
- `langgraph-multi-agents.md` - Supervisor, collaboration, hierarchical patterns
- `langgraph-persistence.md` - Checkpointers, thread-based persistence
- `langgraph-retrieval.md` - RAG, vector stores, agentic retrieval
- `langgraph-long-term-memory.md` - Store API, cross-thread memory
- `langgraph-subgraphs.md` - Nested graphs, modular composition

---

## Open Questions (Updated)
1) ~~Which middleware do you want enabled **by default**?~~ **RESOLVED**: Summarization, call limits, retries all enabled by default.
2) ~~Should `AGENT_RUNTIME=langchain` become the default immediately?~~ **RESOLVED**: User chose `langchain` as default.
3) Should `dev_server.py` always use `langchain` for Studio, or respect `AGENT_RUNTIME`? **PENDING**
4) ~~Memory choice: mem_db or LangGraph Store?~~ **RESOLVED**: mem_db is complementary to SummarizationMiddleware, not a replacement. Keep mem_db for persistent facts; improve integration later.

---

## Review: Technical & Approach Comments (Updated 2025-01-16)

*Reviewer: Claude (Agent) | Research based on: `docs/kb/*.md`*

### Overall Assessment

**The approach is sound.** Key updates from research:
1. **FastAPI deployment** (not LangGraph Up) avoids platform costs
2. **Redis is optional** for initial deployment
3. **Postgres checkpointer** is production-ready and sufficient
4. **13 new KB files** cover additional topics for future use

### Deployment Architecture Notes

1. **FastAPI over LangGraph Up**: Correct decision for cost control
   - Keep existing `docker-compose.yml` with PostgreSQL
   - Add FastAPI service container
   - No dependency on LangGraph Cloud infrastructure

2. **PostgreSQL as single source of truth**:
   - Checkpointer tables (already in schema)
   - Audit tables (conversations, messages)
   - Future: Store tables for long-term memory
   - No Redis needed initially

3. **Volume wipe strategy**:
   - Backup `migrations/001_initial_schema.sql`
   - Can use `TRUNCATE` on checkpoint tables to restart fresh
   - Keep old schema file for rollback reference

---

### Strengths of the Plan

1. **Non-destructive migration**: Keeping `src/executive_assistant/agent/graph.py` intact means we can always revert if issues arise.

2. **Clear separation of concerns**: Recognizing that `SummarizationMiddleware` ≠ structured summary is crucial. Your structured pipeline has:
   - Topic-based context preservation
   - KB-first routing logic
   - Context-contamination fixes
   These remain available in `AGENT_RUNTIME=custom` mode.

3. **Complementary memory architecture**: SummarizationMiddleware handles token reduction within threads; mem_db handles persistent facts across sessions. They serve different purposes.

4. **Subagent scope decision**: Keeping Orchestrator/Workers on custom graph prevents cascading changes. This is wise—let Executive Assistant be the canary.

5. **Configuration-driven middleware**: Environment flags (`MW_*`) allow tuning without code changes.

---

### Technical Considerations & Recommendations

#### 1. Import Path Verification (Step 2)

The plan references:
```python
from langchain.agents import create_agent
```

**Verify this import path**—documentation shows `create_agent` as the main entrypoint, but confirm the exact module in LangChain 1.0+. It may be:
- `langchain.agents.create_agent` (function)
- `langchain.agents` module with `create_agent` function
- A builder pattern in a different location

#### 2. Event Shape Compatibility (Step 5) - Critical

The current streaming logic in `src/executive_assistant/channels/base.py` expects events with keys like `messages` or `agent.messages`.

**LangChain's `create_agent` returns a LangGraph `Runnable`, which should emit compatible events** (state updates with `messages` key). However, verify the exact shape:

```python
# Expected current shape:
event = {"messages": [HumanMessage(), AIMessage()]}

# Verify LangChain agent emits same, not:
event = {"output": ..., "messages": ...}  # Different shape
```

**Recommendation**: Add a thin adapter function `normalize_langchain_event()` if shapes differ.

#### 3. Thread ID Persistence Pattern

The plan correctly identifies the need for stable `thread_id`. Based on `docs/kb/langgraph-persistence.md`:

**Current custom graph likely uses**:
```python
config = {"configurable": {"thread_id": thread_id}}
```

**Ensure LangChain agent receives identical config structure**—this should work seamlessly since `create_agent` builds a LangGraph graph.

**Best practice for thread_id format** (from KB):
```python
# User-scoped, channel-prefixed
thread_id = f"{channel_id}:{user_id}:main"  # or ":conv:{conv_id}"

# Avoid per-request UUIDs—these break persistence
thread_id = f"request-{uuid.uuid4()}"  # WRONG
```

#### 4. Middleware Defaults (Updated)

**Recommended defaults** based on production patterns:
- `MW_MODEL_CALL_LIMIT=50` (prevent runaway loops)
- `MW_TOOL_CALL_LIMIT=100` (per thread)
- `MW_TOOL_RETRY_ENABLED=true` (resilience)
- `MW_MODEL_RETRY_ENABLED=true` (resilience)
- `MW_SUMMARIZATION_ENABLED=true` (use LangChain SummarizationMiddleware; mem_db complements for persistent facts)
- `MW_HITL_ENABLED=false` (unless approval workflows exist)

**Summarization thresholds** (when `MW_SUMMARIZATION_ENABLED=true`):
- `MW_SUMMARIZATION_MAX_TOKENS=10000` (trigger summarization when context exceeds this)
- `MW_SUMMARIZATION_TARGET_TOKENS=2000` (compress to this size)

#### 5. Default Runtime (Open Question #2)

**Recommendation**: Keep `AGENT_RUNTIME=langchain` as the **default** (per user decision), with `custom` available as a fallback.

**Rationale**: This aligns the runtime with the desired LangChain feature set while preserving the custom graph as a safe fallback for regressions.

#### 6. Dev Server Behavior (Open Question #3)

**Recommendation**: `dev_server.py` should **respect `AGENT_RUNTIME`** rather than hardcoding `langchain`.

**Rationale**: Studio debugging should reflect the actual runtime used in production. If `AGENT_RUNTIME=custom` in prod, Studio should show the custom graph.

---

### Potential Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Event shape incompatibility breaks streaming | Add adapter in Step 5; test early with simple message |
| LangChain agent lacks custom graph features | Custom runtime remains available via `AGENT_RUNTIME=custom` |
| thread_id format breaks persistence | Follow `kb/langgraph-persistence.md` patterns |
| SummarizationMiddleware is too aggressive | Tune `MW_SUMMARIZATION_MAX_TOKENS` and `MW_SUMMARIZATION_TARGET_TOKENS` |
| mem_db not used in LangChain runtime | Future: add custom tool for mem_db access; mem_db already used via tools |

---

### Implementation Order Suggestion

1. **First**: Implement Step 2 (LangChain agent builder) with minimal middleware (just call limits).
2. **Second**: Implement Step 5 (event shape validation)—catch incompatibilities early.
3. **Third**: Add runtime switch (Step 4) and test both paths.
4. **Fourth**: Add remaining middleware configuration (Step 3).
5. **Last**: Update docs and tests.

---

### Missing Considerations

1. **Error handling divergence**: LangChain's `ModelRetryMiddleware` may intercept errors before Executive Assistant's custom error handlers. Ensure error observability isn't lost.

2. **Metrics/observability**: If Executive Assistant emits custom metrics (LLM calls, tool timings, etc.), ensure LangChain runtime provides equivalent hooks or add custom middleware for this.

3. **Store vs checkpointer confusion**: The plan mentions `store` parameter in `create_agent` API. Clarify:
   - **Checkpointer**: Thread-local state (conversation history)
   - **Store**: Cross-thread shared data (user preferences)
   These serve different purposes—don't conflate them.

---

### Final Verdict (Updated 2025-01-16)

**Proceed with the plan as written**, with these adjustments based on user decisions:

1. **Deployment**: Use FastAPI, not LangGraph Up (cost avoidance) ✓
2. **Redis**: Skip for initial deployment; add later if scaling needed ✓
3. **Import path**: Verify `create_agent` import location in LangChain 1.0+ ✓
4. **Event shape adapter**: Add proactively for streaming compatibility ✓
5. **Default runtime**: `AGENT_RUNTIME=langchain` (user's choice; custom available as fallback)
6. **Middleware**: `MW_SUMMARIZATION_ENABLED=true` by default (use LangChain SummarizationMiddleware)
7. **mem_db**: Keep as complementary layer for persistent facts; NOT a replacement for summarization
8. **Custom structured summary**: Remains active ONLY in `AGENT_RUNTIME=custom` mode
9. **Dev server**: Should respect `AGENT_RUNTIME` setting (TBD)
10. **Schema backup**: Keep `migrations/001_initial_schema.sql` before any checkpointer migration ✓

**Knowledge Base Ready**: 13 new KB files cover all major LangChain/LangGraph topics for future reference.

**Summary of Key Decisions**:
- Accept LangChain's `SummarizationMiddleware` for token reduction
- Custom structured summary (KB-first routing, topic isolation) remains in custom runtime only
- mem_db complements summarization by storing persistent facts across sessions
- Future work: improve mem_db integration with LangChain runtime via custom tool

The plan is well-structured and aligns with LangChain/LangGraph best practices.
