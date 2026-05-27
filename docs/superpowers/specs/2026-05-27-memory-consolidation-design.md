# Memory Consolidation — Design Spec

**Author:** Eddy  
**Date:** 2026-05-27  
**Status:** Approved

---

## 0. Motivation

The current memory system has three overlapping storage layers (MessageStore, ObservationStore, MemoryStore) with cross-store side-push dependencies, a disabled LLM extraction pipeline (proved actively harmful: -35pp accuracy), and confused tool naming (`memory_search` searches conversations, not memories). Industry converges on observation-based memory (Mastra OM at 94.87% LongMemEval, Mem0 V3 at 94.8%) with text-first storage and background-agents for extraction.

This design consolidates observation, memory, and insight into a unified pipeline and store.

---

## 1. Tool Renames (MessageStore Tools)

Tools that read from `MessageStore` (raw conversations) are renamed from `memory_*` to `message_*`. Implementation unchanged — rename only.

| Old Name | New Name | Reads From |
|----------|----------|-----------|
| `memory_search` | `message_search` | MessageStore via memcore (hybrid + heuristics) |
| `memory_count` | `message_count` | MessageStore via hybrid search + entity counting |
| `memory_get_history` | `message_history` | MessageStore date range queries |

These move from `src/sdk/tools_core/memory.py` to new file `src/sdk/tools_core/message.py`.

Registration changes in `src/sdk/native_tools.py`.

---

## 2. Unified MemoryStore

Merge `ObservationStore` (182 lines) and `MemoryStore` (1882 lines) into a single `MemoryStore` with four tables in one HybridDB. Uses `paths.user_memory_dir()` → `~/Executive Assistant/Memory/global/` (same path as current MemoryStore, consistent with existing `user_memory_dir()`).

### 2.1 Schema

**`observations`** — Episodic text records produced by Observer

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | `obs_{uuid12}` |
| `content` | LONGTEXT | Factual text, one fact per observation |
| `priority` | TEXT | 🔴 (high/precise), 🟡 (medium/preference), 🟢 (low/skipped) |
| `observation_ts` | TEXT | ISO timestamp when Observer created this |
| `referenced_date` | TEXT | Date mentioned in the content, or empty |
| `relative_date` | TEXT | Computed relative offset, or empty |
| `source_message_range` | TEXT | Message IDs this observation covers |
| `created_at` | TEXT | ISO timestamp |

**`reflections`** — Condensed observation summaries produced by Reflector

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | `refl_{uuid12}` |
| `content` | LONGTEXT | Condensed text preserving all key facts |
| `source_observation_range` | TEXT | Observation IDs condensed |
| `observation_count` | INTEGER | Number of observations condensed |
| `token_count` | INTEGER | Estimated tokens in content |
| `created_at` | TEXT | ISO timestamp |

**`facts`** — Lightweight entity/attribute/value index produced by Observer

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | `fact_{sha256_16}` |
| `fact_key` | TEXT | `{scope}:{entity}:{attribute}` normalized |
| `entity` | TEXT | Subject (e.g., "user", "spouse") |
| `attribute` | TEXT | Property (e.g., "location", "role") |
| `value` | TEXT | Exact value from observation |
| `observation_id` | TEXT | FK back to source observation (text is authoritative) |
| `updated_at` | TEXT | ISO timestamp |

Indexes: `fact_key`, `fact_key + updated_at`, `entity`, `attribute`, `value`.

No confidence. No decay. No supersession. The observation text is the source of truth.

**Fact cleanup on reflection**: When Reflector produces `dropped_observation_ids` (superseded observations), the corresponding facts rows (where `observation_id` is in the dropped set) are also deleted from the facts table. This keeps the index clean.

**`insights`** — Synthesized patterns produced by Reflector and Insight Generator

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | `ins_{uuid12}` |
| `content` | LONGTEXT | Synthesized pattern or prediction |
| `domain` | TEXT | Category (preference, career, lifestyle, etc.) |
| `linked_observation_ids` | JSON | Observation IDs contributing to this insight |
| `linked_reflection_ids` | JSON | Reflection IDs that led to this insight |
| `source` | TEXT | `reflector` or `insight_generator` |
| `confidence` | REAL | 0.0–1.0, boosted on access |
| `decay_rate` | REAL | Weekly decay multiplier |
| `access_count` | INTEGER | Times accessed via `memory_insights` |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |
| `last_accessed_at` | TEXT | ISO timestamp |

Confidence model:
- Initial: 0.6 when created
- Access boost: `c + 0.1 * (1 - c)` on each access
- Weekly decay: `c - decay_rate * weeks` (decay_rate = 0.05)
- Soft-delete: `confidence <= 0.1` (filtered from queries; row remains)

### 2.2 Key Methods

```
insert_observations(observations: list[dict]) → int
    Stores observations in observations table.
    Side-effect: stores facts_extracted in facts table.
    No cross-store dependency — everything in one HybridDB.

get_recent_observations(days=7, limit=50) → list[dict]
get_all_observations() → list[dict]

get_latest_reflection() → dict | None
insert_reflection(reflection: dict) → str
    Stores reflection in reflections table.
    Side-effect: stores patterns_identified as insights (source=reflector).

insert_insights(insights: list[dict]) → int
    Stores insight generator outputs (source=insight_generator).

search_observations(query, limit) → list[dict]
search_reflections(query, limit) → list[dict]
search_insights(query, method, limit) → list[dict]
    method: fts | semantic | hybrid (default)

find_facts(entity=None, attribute=None, limit=10) → list[dict]
    Indexed lookup by entity/attribute.
    Uses fact_key index for fast retrieval.
    Falls back to observation full-text search if fact index misses.

boost_insight(insight_id) → None
    Access-based confidence reinforcement.
```

### 2.3 What Gets Retired

| File | Lines | Fate |
|------|-------|------|
| `src/storage/memory.py` | 1882 | Rewritten (same file, new content) |
| `src/storage/observation.py` | 182 | Merged into new memory.py |
| `src/storage/consolidation.py` | 393 | Merged into Reflector + Insight Generator |
| `src/sdk/memory_planner.py` | 271 | Deleted (no longer needed) |
| `src/sdk/memory_ranker.py` | 413 | Deleted (no longer needed) |
| `src/sdk/middleware_memory.py` | 960 | Deleted (already disabled, now removed permanently) |

Removed concepts: `Memory` dataclass (trigger/action pairs, 20 fields), `Connection` dataclass (graph edges), `Insight` dataclass (replaced by table rows), confidence chains, supersession tracking, memory graph, access_count on facts.

---

## 3. Pipeline — Observer, Reflector, Insight Generator

Three background agents, one pipeline, all reading `MessageStore` and writing to unified `MemoryStore`.

### 3.1 Observer

**When**: Fires when cumulative unobserved tokens since last Observer run exceed 8K AND at least 3 turns have passed. Cumulative — uses `_count_unobserved_tokens()` (same as current summarization trigger pattern). Never blocks the main agent.

**Input**: Last 30 days / 500 messages from `MessageStore`, plus previous observations (for dedup).

**Output**: JSON array of observations + facts_extracted.

**Model**: `OBSERVER_MODEL` env var, defaults to `DEFAULT_MODEL`. Flash-tier recommended.

**Prompt**: `OBSERVER_PROMPT` in `src/sdk/tools_core/observation.py`. Extracts one fact per observation, exact values only, 🔴🟡🟢 priorities.

### 3.2 Reflector

**When**: Fires when reflections table token count exceeds 16K tokens. Cumulative — checks `get_latest_reflection().token_count` on each `after_agent()`.

**Input**: All observations since last reflection.

**Output**: JSON with `reflection_text`, `dropped_observation_ids`, `contradictions_resolved`, `patterns_identified`.

`patterns_identified` is stored as `insights` rows with `source=reflector` and `confidence=0.6`.

**Model**: `REFLECTOR_MODEL` env var, defaults to `DEFAULT_MODEL`. Balanced model — requires reasoning capability.

**Scope**: Batch-scoped. Reflector only sees observations within its current cycle. Its insights are intra-cycle patterns (contradictions resolved, merged topics).

### 3.3 Insight Generator

**When**: Nightly cron or every N reflection cycles (configurable). Runs as a scheduled background task.

**Input**: ALL reflections from `MemoryStore` + their `source=reflector` insights. Cross-cycle scope — sees patterns no single Reflector batch can detect.

**Output**: Deep insights stored in `insights` table with `source=insight_generator` and `confidence=0.6`.

**What it discovers**: Career arcs, core value patterns, predicted future needs, cross-cycle contradictions that individual Reflector batches missed.

**Model**: `INSIGHT_MODEL` env var, defaults to `DEFAULT_MODEL`. Best model available — offline, latency doesn't matter.

**Scope**: Cross-cycle. Reads ALL reflections + insights to detect multi-cycle patterns.

### 3.4 The Three Stages — Concrete Distinction

| | Observer | Reflector | Insight Generator |
|---|---|---|---|
| **Scope** | This turn's messages | One reflection cycle (~50 observations) | Multiple cycles (weeks/months) |
| **What it does** | Extracts individual facts | Compresses + detects intra-cycle patterns | Discovers cross-cycle arcs |
| **Example output** | "lives in Denver" | "User decided to stay in Denver after considering Boulder" | "User relocated twice in 3 years for family reasons; may value proximity to good schools above all else" |
| **Analogy** | Writing a diary entry | Re-reading the week's diary | Re-reading months of diaries, seeing the arc of a life |
| **Runs** | Every ~8K tokens | When observations exceed ~16K tokens | Nightly / every N reflections |
| **Model** | Cheap (flash tier) | Balanced (reasoning-capable) | Best (offline) |
| **Cost** | Frequent, cheap calls | Infrequent, moderate calls | Rare, expensive calls |

### 3.5 No Auto-Injection

The ObservationMiddleware `before_agent()` (working memory injection) is **removed**. The agent must explicitly call:
- `memory_profile` for user context (recent observations + latest reflection + top insights)
- `memory_insights` for deep pattern search
- `message_search` for raw conversation lookup

Observer, Reflector, and Insight Generator continue running silently in background.

---

## 4. Tool API

### 4.1 Message Tools (`src/sdk/tools_core/message.py`)

```
message_search(query, limit=5) → str
    Reads MessageStore via memcore. Hybrid search + heuristics.
    Annotations: read_only=True, idempotent=True

message_count(query) → str
    Reads MessageStore via hybrid. Deterministic entity extraction + counting.
    Annotations: read_only=True, idempotent=True

message_history(days=7, date_str=None) → str
    Reads MessageStore date range queries.
    Annotations: read_only=True, idempotent=True
```

### 4.2 Memory Tools (`src/sdk/tools_core/memory.py`)

```
memory_profile() → str
    Returns: recent observations (7d) + latest reflection + top 3 insights (by confidence).
    Annotations: read_only=True, idempotent=True

memory_insights(query, method="hybrid", limit=5) → str
    Searches insights table. FTS, semantic, or hybrid.
    Boosts accessed insights' confidence on read.
    Annotations: read_only=True, idempotent=True
```

### 4.3 Retired Tools

| Tool | Reason |
|------|--------|
| `memory_search_all` | Cross-store aggregation — no longer needed with unified store |
| `memory_search_all_workspaces` | Can be re-added later if cross-workspace insight search is needed |
| `memory_connect` | Was for Memory object graph edges; no graph in new design |

---

## 5. Storage Layout

```
~/Executive Assistant/
├── Conversation/
│   └── app.db              # MessageStore (HybridDB) — unchanged
├── Memory/
│   └── global/
│       ├── app.db          # MemoryStore (HybridDB) — unified, replaces old stores
│       │   Tables: observations, reflections, facts, insights
│       └── vectors/        # ChromaDB for insights semantic search
└── Workspaces/{workspace_id}/
    └── conversation.app.db # Workspace MessageStore — unchanged
```

Memory uses `paths.user_memory_dir()` (`~/Executive Assistant/Memory/global/`). This replaces both the old `MemoryStore` path and the old `ObservationStore` path (`Workspaces/{id}/Memory/observations/`). Observations and insights are global, not per-workspace.

---

## 6. Files to Create / Modify / Delete

### Create
- `src/sdk/tools_core/message.py` — `message_search`, `message_count`, `message_history`

### Modify
- `src/storage/memory.py` — rewritten: unified MemoryStore (4 tables, ~400 lines)
- `src/sdk/tools_core/memory.py` — rewritten: `memory_profile`, `memory_insights`
- `src/sdk/tools_core/observation.py` — add Insight Generator prompt (`INSIGHT_PROMPT`) and `run_insight_generator()`
- `src/sdk/middleware_observation.py` — remove `before_agent()`; add Insight Generator trigger to `after_agent()`
- `src/sdk/native_tools.py` — update registration: message tools from message.py, memory tools from memory.py, Insight Generator runner

### Delete
- `src/storage/observation.py` — merged into new memory.py
- `src/storage/consolidation.py` — merged into Reflector + Insight Generator
- `src/sdk/memory_planner.py` — no longer needed
- `src/sdk/memory_ranker.py` — no longer needed
- `src/sdk/middleware_memory.py` — already disabled, permanently removed

---

## 7. Migration

1. Create new MemoryStore in `src/storage/memory.py` (new file, no migration needed — old data not compatible)
2. Move message tools to `src/sdk/tools_core/message.py`, rename to `message_*`
3. Rewrite memory tools in `src/sdk/tools_core/memory.py`
4. Update `ObservationMiddleware` — remove `before_agent`, add Insight Generator
5. Update `native_tools.py` registrations
6. Delete old files
7. Run tests: `uv run pytest tests/sdk/ -v`

No data migration. The trigger/action Memory model is incompatible with observation-based memory. Fresh start.
