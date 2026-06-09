# Migrate EA Observation/Reflection to CoreMem Pipelines

**Date:** 2026-06-09
**Status:** Draft
**Motivation:** EA vendors two custom observation/reflection files (`src/storage/memory.py`, `src/sdk/middleware_observation.py`, `src/sdk/tools_core/observation.py`) that duplicate CoreMem's `ObserverPipeline` and `ReflectorPipeline` with worse defaults, no alignment gate, no classification, no dedup, and no hybrid reflector trigger.

---

## 1. Current Architecture (To Be Removed)

```
MessageStore (MemoryCore @ conversation/)
  └── messages table

MemoryStore (HybridDB @ memory/)         ← CUSTOM, to DELETE
  ├── observations table (custom schema)
  └── reflections table (custom schema)

ObservationMiddleware (custom trigger)
  ├── _fire_observer() → run_observer()
  │     └── single LLM call, 8K threshold, 3-turn debounce
  └── _fire_reflector() → run_reflector()
        └── single LLM call, 24h-only trigger

memory_profile / memory_reflection tools
  └── read from MemoryStore
```

**3 files to delete:**
- `src/storage/memory.py` (MemoryStore, `get_memory_store`, `clear_memory_store_cache`)
- `src/sdk/tools_core/observation.py` (run_observer, run_reflector, prompts)
- `src/sdk/middleware_observation.py` (ObservationMiddleware)

---

## 2. Target Architecture

```
MessageStore (MemoryCore @ conversation/)
  ├── messages table
  ├── observations table (CoreMem _OBSERVATIONS_SCHEMA)
  ├── observation_events table
  ├── observation_conflicts table
  └── reflections table (CoreMem _REFLECTIONS_SCHEMA)

No separate MemoryStore. No separate DB for memory.

ObservationMiddleware — rewritten to use:
  └── coremem.observer.ObserverPipeline
        ├── token_threshold=100 (instead of 8000)
        ├── min_turns=1 (instead of 3)
        ├── 5 parallel LFs (entities, actions, preferences, temporal, sentiment)
        ├── alignment-gated source quotes
        ├── optional classification + durability filter
        └── semantic dedup + merge

ReflectorMiddleware — rewritten to use:
  └── coremem.reflector.ReflectorPipeline
        ├── interval_hours=24 (unchanged)
        ├── trigger_every_n_observations=50 (new — hybrid OR trigger)
        ├── min_observations=10 (unchanged)
        ├── priority sampling at >200 obs
        └── cosine similarity dedup quality gate

memory_profile / memory_reflection tools
  └── read from MemoryCore via MessageStore._core
```

---

## 3. Schema Changes

### 3.1 New tables (auto-created by MemoryCore)

Observations (`_OBSERVATIONS_SCHEMA` — 21 columns):

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | uuid |
| `kind` | TEXT | 'fact' or 'entity' |
| `content` | LONGTEXT | The fact text |
| `source_quote` | TEXT | Verbatim quote from conversation |
| `source_fact_ids` | TEXT | JSON array |
| `source_message_ids` | TEXT | JSON array |
| `referenced_date` | TEXT | Extracted date reference |
| `observation_ts` | TEXT | When observed (ISO) |
| `user_id` | TEXT | Who this is about |
| `agent_id` | TEXT | Which agent observed |
| `session_id` | TEXT | Conversation session |
| `alignment_tier` | TEXT | EXACT / FUZZY / NONE |
| `alignment_confidence` | REAL | 0.0-1.0 |
| `importance` | REAL | 0.0-1.0 (replaces emoji priority) |
| `confidence` | REAL | Default 0.800 |
| `memory_type` | TEXT | profile / preference / project / ... |
| `durability` | TEXT | durable / temporary |
| `sensitivity` | TEXT | normal / personal / sensitive |
| `status` | TEXT | candidate / active / superseded / archived |
| `valid_from` | TEXT | Temporal validity start |
| `valid_to` | TEXT | Temporal validity end |
| `superseded_by` | TEXT | ID of superseding observation |
| `entities` | TEXT | JSON array |
| `reflected` | INTEGER | 0 or 1 |
| `embedding` | TEXT | JSON float array |

Reflections (`_REFLECTIONS_SCHEMA` — 7 columns):

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | uuid |
| `content` | LONGTEXT | Synthesized insight |
| `domain` | TEXT | Category label |
| `linked_observation_ids` | TEXT | JSON array |
| `score` | REAL | Confidence (replaces EA's confidence+decay_rate) |
| `embedding` | TEXT | For cosine similarity dedup |
| `user_id` | TEXT | |
| `session_id` | TEXT | |

Plus `observation_events` and `observation_conflicts` tables.

### 3.2 EA columns dropped

| EA Column | Replaced By |
|-----------|-------------|
| `priority` (emoji: 🔴🟡🟢) | `importance` (float 0.0-1.0) |
| `relative_date` | `referenced_date` (already exists) |
| `source_message_range` | `source_message_ids` + `source_quote` |
| `confidence` (reflections, 0.6) | `score` (reflections, 1.0) |
| `decay_rate` (reflections, 0.05) | CoreMem's built-in `apply_decay` (half-life model) |
| `access_count` / `last_accessed_at` | Not needed — CoreMem doesn't boost on access |
| `updated_at` | Not needed — observations are append-only with supersede |

### 3.3 Data migration

Existing `memory/app.db` needs to be migrated into `conversation/app.db`:

1. Copy observations: `INSERT INTO conversation.observations SELECT ... FROM memory.observations` with schema adaptation (emoji priority → importance, drop decay-only columns)
2. Copy reflections: same with `memory_type`/`domain` mapping
3. After migration, delete `memory/app.db` (or keep for rollback)

---

## 4. Detailed Changes

### 4.1 MessageStore changes (`src/storage/messages.py`)

- `MemoryCore` constructor gets `enable_observations=True`, `enable_reflections=True`
- Add a migration step `_migrate_memory_store(base_path)` that copies data from `data/users/{user_id}/memory/app.db` into `data/users/{user_id}/conversation/app.db` (run once)
- Expose `MemoryCore.observations()` / `.reflections()` / `.get_pending_reflections()` / `.extract_observations()` / `.reflect()` for tools and middleware
- The `observer_pipeline` and `reflector_pipeline` fields need to be accessible (or the middleware creates them)

### 4.2 ObservationMiddleware rewritten (`src/sdk/middleware_observation.py`)

```python
class ObservationMiddleware(Middleware):
    def __init__(self, user_id, workspace_id, session_id, ...):
        # Get MessageStore's MemoryCore
        store = get_message_store(user_id, workspace_id)
        core = store._core  # MemoryCore with enable_observations=True

        self._observer = ObserverPipeline(
            memory=core,
            session_id=session_id,
            user_id=user_id,
            token_threshold=100,
            min_turns=1,
            enable_classification=True,
            enable_dedup=True,
        )
        self._reflector = ReflectorPipeline(
            memory=core,
            user_id=user_id,
            interval_hours=24,
            min_observations=10,
            trigger_every_n_observations=50,
        )

    def after_agent(self, state):
        # Fire-and-forget observer
        asyncio.create_task(self._observer.extract())
        # Fire-and-forget reflector (hybrid trigger)
        asyncio.create_task(self._reflector.maybe_run())
        return None
```

### 4.3 Delete `src/storage/memory.py`

- `MemoryStore` class removed
- `get_memory_store()` and `clear_memory_store_cache()` removed
- All callers switch to `MessageStore` + `MemoryCore` methods

### 4.4 Delete `src/sdk/tools_core/observation.py`

- `run_observer`, `run_reflector`, prompts removed

### 4.5 Memory tools updated (`src/sdk/tools_core/memory.py`)

- `memory_profile` reads from `MessageStore._core.observations(query=None, limit=50)` instead of `MemoryStore.get_recent_observations()`
- `memory_reflection` reads from `MessageStore._core.reflections(query=query, limit=limit)` instead of `MemoryStore.search_reflections()`
- Remove `store.boost_reflection()` calls — CoreMem doesn't boost on access

### 4.6 HTTP router updated (`src/http/routers/memories.py`)

- Replace `get_memory_store(user_id, workspace_id)` with `get_message_store(user_id, workspace_id)._core`
- Map CoreMem observation columns to response schema

### 4.7 Coordinator updated (`src/sdk/coordinator.py`)

- `ObservationMiddleware` construction adjusted for new signature (needs `session_id`)

### 4.8 Runner updated (`src/sdk/runner.py`)

- Construction site of `ObservationMiddleware` adjusted

### 4.9 Test updates

- `tests/sdk/test_observations.py` (if it exists) updated for new schema
- `tests/sdk/test_reflections.py` (if it exists) updated for new schema
- Remove tests for deleted `storage/memory.py` code

---

## 5. File Manifest

| Action | File | Reason |
|--------|------|--------|
| DELETE | `src/storage/memory.py` (244 lines) | Entirely replaced by MemoryCore |
| DELETE | `src/sdk/tools_core/observation.py` (187 lines) | Replaced by ObserverPipeline |
| REWRITE | `src/sdk/middleware_observation.py` (164 → ~80 lines) | Create pipeline, trigger `.extract()`/`.maybe_run()` |
| MODIFY | `src/storage/messages.py` | Enable observations on MemoryCore + migration |
| MODIFY | `src/sdk/tools_core/memory.py` (~95 lines) | Switch to core.observations()/reflections() |
| MODIFY | `src/http/routers/memories.py` | Replace get_memory_store → MessageStore._core |
| MODIFY | `src/sdk/coordinator.py` | Adjust ObservationMiddleware construction |
| MODIFY | `src/sdk/runner.py` | Adjust ObservationMiddleware construction |
| MODIFY | Tests | Update for new schema and pipeline behavior |

---

## 6. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Schema migration fails for existing users | Low | Keep old DB file, add rollback flag |
| CoreMem ObserverPipeline blocks on long runs | Low | It uses asyncio.gather with return_exceptions |
| Different observation format breaks tools | Medium | CoreMem observations have more fields; tools that read them must handle both |
| `importance` vs emoji priority breaks formatting | Low | Convert: 0.7+ → 🟢, 0.4-0.7 → 🟡, <0.4 → 🟢 in display code |
| `score` vs `confidence` breaks reflection output | Low | Show as percentage either way |

---

## 7. Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Observation trigger threshold | 8K tokens / 3 turns | 100 tokens / 1 turn |
| Observation LLM calls per turn | 1 call (single-pass) | 5 parallel LFs + batched relations |
| Dedup strategy | Prompt-based ("don't repeat") | Semantic dedup + merge (duplicate/refine/supersede) |
| Source quote verification | None | 3-tier alignment gate (EXACT/FUZZY/NONE) |
| Classification | None | 12 memory_types + durability + sensitivity |
| Reflector trigger | 24h only | 24h OR 50 unreflected facts |
| Reflector quality gate | None | Cosine similarity dedup |
| Duplicate observation code | 595 lines | 0 lines (deleted) |
| Data DBs per user | 2 (messages + memory) | 1 (messages only) |

---

## 8. Implementation Order

1. **Schema migration** — Add `_migrate_memory_store()` to `MessageStore.__init__`, copy data from old `memory/app.db` to `conversation/app.db`
2. **Enable observations on MemoryCore** — `enable_observations=True, enable_reflections=True` in `MessageStore`
3. **Rewrite ObservationMiddleware** — Use `ObserverPipeline` + `ReflectorPipeline`
4. **Update memory tools** — Switch from `MemoryStore` to `MemoryCore`
5. **Delete old files** — `storage/memory.py`, `tools_core/observation.py`, `old_middleware_observation.py`
6. **Fix callers** — `coordinator.py`, `runner.py`, `memories.py` router
7. **Update tests**
8. **Run validation** — Ensure `memory_profile` and `memory_reflection` tools work end-to-end