# Memory System Redesign — MemPalace-Inspired Architecture

**Date:** 2026-05-06  
**Status:** Draft — pending review  
**Motivation:** LongMemEval multi-session QA accuracy is capped at ~20% despite retrieval finding all relevant messages. The bottleneck is not the model — it's the architecture.

---

## 1. Current Architecture & Failure Points

### 1.1 What works

- **HybridDB (FTS5 + ChromaDB)**: Direct diagnostic confirmed hybrid search finds all 5 model kit mentions at limit ≥ 50.
- **Planner**: Correctly routes queries to aggregation, search_evidence, current_fact, etc.
- **Ranker**: Deterministic scoring with dedup, recency, and aggregation-aware penalties.

### 1.2 What fails

| Problem | Root cause | Consequence |
|---------|-----------|-------------|
| Agent sees 15 B-29 messages, 2 Camaro messages, 0 Tiger messages | No session grouping. Results are a flat list of individual messages. Same-session messages dominate the top ranks. | Agent counts 3 model kits instead of 5 |
| `user.model_kits = 3` stored as a fact | LLM extraction hallucinates a count from partial context | Even with perfect retrieval, the stored fact is wrong |
| "Where did I live in March?" returns "New York" | Facts are overwritten, not versioned. No temporal validity. | Temporal-reasoning questions fail |
| Cross-workspace search triggers unreliably | Threshold is `len(all_results) < 5` — fragile heuristic | Workspace isolation becomes a search silo |
| `_mempalace_boost` re-ranks results inconsistently | Different scoring than the ranker injection path | Agent receives different context from tool vs injected context |

### 1.3 The core structural problem

The current system stores **extracted facts** (entity/attribute/value triples) alongside **raw messages**, with the facts taking priority. But the facts are lossy — the LLM compresses "Revell F-15, Tamiya Spitfire, Tiger I, B-29, Camaro" into `user.model_kits = 3`. Once the fact is stored, the agent trusts it over the raw messages that would have given the correct answer.

---

## 2. Target Architecture

### 2.1 Core principles

1. **Verbatim-first, structure-later**: Store exact text. Never derive counts or aggregates from LLM summaries.
2. **Session as the retrieval unit**: Group messages into sessions. Return sessions, not individual messages.
3. **Temporal validity**: Every fact carries `valid_from` and `valid_until`. Nothing is overwritten.
4. **Deterministic aggregation**: Counting, deduplication, and temporal reasoning happen in code, not in the LLM.
5. **Unified search path**: The `memory_search` tool and the ranker injection use the same pipeline.

### 2.2 System diagram

```
┌──────────────────────────────────────────────────────────────┐
│  IMPORT                                                       │
│  Raw messages → Tag with session_id                           │
│  → Store verbatim in MessageStore                             │
│  → When session closes → create SessionDigest                 │
│    (compressed summary: topics discussed, entities mentioned) │
├──────────────────────────────────────────────────────────────┤
│  STORE                                                        │
│  messages table (verbatim, FTS5-indexed, ChromaDB-vectored)   │
│    - id, ts, role, content, session_id, workspace_id          │
│                                                               │
│  session_digests table (one row per session)                  │
│    - id, session_id, digest_text, entity_list, date_range     │
│    - FTS5 + ChromaDB indexed                                  │
│                                                               │
│  temporal_facts table (derived facts with validity windows)   │
│    - id, entity, attribute, value                              │
│    - evidence (verbatim quote), source_msg_id                  │
│    - valid_from, valid_until (NULL = current)                 │
│    - workspace_id                                              │
├──────────────────────────────────────────────────────────────┤
│  INDEX (two-tier)                                             │
│  Tier 1: session_digests → fast semantic + keyword search     │
│  Tier 2: messages (within session) → detailed lookup          │
├──────────────────────────────────────────────────────────────┤
│  RETRIEVE                                                     │
│  memory_search(q):                                            │
│    1. Search Tier 1 (session digests) → ranked sessions       │
│    2. Group by session, one representative entry per session  │
│    3. If cross-workspace → tag each session with source ws    │
│    4. Return: "N sessions found across M workspaces"          │
│                                                               │
│  memory_get_session(session_id):                              │
│    Return all raw messages from one session                   │
│                                                               │
│  memory_count(q):                                             │
│    1. Same search → extract entities from matched digests     │
│    2. Deduplicate programmatically                             │
│    3. Return: "X distinct items: item1, item2, ..."           │
│    NO LLM COUNTING. Purely deterministic.                     │
├──────────────────────────────────────────────────────────────┤
│  AGGREGATION                                                  │
│  For "how many X":                                            │
│    Search temporal_facts for matching entity/attribute         │
│    Filter by valid_from/valid_until for time-bound queries    │
│    Return unique values + evidence                            │
├──────────────────────────────────────────────────────────────┤
│  GRAPH (temporal facts)                                       │
│  Each entity is a node. Each attribute=value is a fact.       │
│  Edges: corrections, time-succession, topic-similarity.       │
│  On retrieval failure → traverse graph to related facts.      │
│  Validity windows eliminate "which version is current?" guess │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 How this fixes each failure point

| Old Problem | New Architecture |
|-------------|-----------------|
| 15 B-29 messages flood top-K | Session grouping → one entry per session. B-29, Camaro, Tiger each get one slot. |
| `user.model_kits = 3` hallucinated | No LLM extraction of counts. `memory_count` does deterministic regex entity extraction. |
| "Where did I live in March?" returns wrong city | `temporal_facts` table with `valid_from/valid_until`. March falls in Denver's window. |
| Cross-workspace search unreliable | Sessions explicitly tagged with workspace. Multi-workspace search is a natural grouping dimension. |
| `_mempalace_boost` vs ranker divergence | Single unified pipeline. Same scoring, same formatting, both paths. |

---

## 3. Data Model

### 3.1 `messages` table (enhanced)

```sql
-- Existing columns: id, ts, role, content, metadata
-- New columns:
session_id   TEXT NOT NULL DEFAULT '',      -- groups messages into sessions
workspace_id TEXT NOT NULL DEFAULT 'personal'
```

### 3.2 `session_digests` table (new)

```sql
CREATE TABLE session_digests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL UNIQUE,
    workspace_id TEXT NOT NULL DEFAULT 'personal',
    digest_text TEXT NOT NULL,              -- compressed summary (first 500 chars of session)
    entity_list TEXT,                       -- JSON array of extracted entities
    topic_words TEXT,                       -- space-separated keywords for FTS5
    message_count INTEGER DEFAULT 0,
    date_start  TEXT,                       -- earliest message timestamp
    date_end    TEXT,                       -- latest message timestamp
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Full-text search on digest content
CREATE VIRTUAL TABLE session_digests_fts USING fts5(digest_text, topic_words, content='session_digests');

-- ChromaDB collection: session_digests_digest_text (indexed by HybridDB journal)
```

### 3.3 `temporal_facts` table (new — replaces current fact extraction)

```sql
CREATE TABLE temporal_facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity      TEXT NOT NULL,              -- "user", "project_x", "team_y"
    attribute   TEXT NOT NULL,              -- "city", "job_title", "status"
    value       TEXT NOT NULL,              -- "Denver", "Engineer", "active"
    evidence    TEXT NOT NULL,              -- verbatim quote from source message
    source_msg  INTEGER,                    -- FK to messages.id
    session_id  TEXT,                       -- which session this came from
    workspace_id TEXT NOT NULL DEFAULT 'personal',
    valid_from  TEXT NOT NULL,              -- ISO date "2024-01-15"
    valid_until TEXT,                       -- ISO date or NULL (NULL = still valid)
    confidence  REAL DEFAULT 1.0,           -- 0-1, derived from source reliability
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT,

    FOREIGN KEY (source_msg) REFERENCES messages(id)
);

CREATE INDEX idx_temporal_facts_entity ON temporal_facts(entity, attribute);
CREATE INDEX idx_temporal_facts_validity ON temporal_facts(entity, attribute, valid_from, valid_until);
CREATE INDEX idx_temporal_facts_workspace ON temporal_facts(workspace_id);
```

### 3.4 Data flow

```
Message arrives → stored in `messages` (verbatim) → tagged with session_id
                                                    → HybridDB auto-vectors via journal

Session ends → `session_digests` row created:
    1. Concatenate first 500 chars of conversation
    2. Extract entities via regex (capitalized noun phrases)
    3. Extract keywords for FTS5
    4. HybridDB auto-vectors digest_text

Facts are derived from explicit user statements only:
    User: "I moved from Denver to New York"
    → temporal_fact: entity=user, attribute=city, value=New York
      evidence="I moved from Denver to New York"
      valid_from=timestamp of this message, valid_until=NULL

    → Update previous Denver fact: valid_until=same timestamp
```

---

## 4. Retrieval Pipeline

### 4.1 Unified search function

```python
def unified_search(query, user_id, workspace_id, cross_workspace=False):
    """
    Single retrieval entry point used by both memory_search tool
    and ranker injection middleware.
    """
    plan = plan_memory_query(query)

    # Tier 1: search session digests
    digests = search_digests(query, workspace_id, cross_workspace)

    # Group by session (already one digest per session)
    # Apply scoring
    ranked = rank_memory_candidates(query, digests)  # unified ranker

    # Format: one entry per session
    return format_session_results(ranked, plan)
```

### 4.2 `memory_search` output format

```
Found 4 sessions matching "model kits":

1. [work] Session s1 (34 msgs, Jan 3-15)
   Topics: B-29 bomber, Revell F-15 Eagle, photo-etching

2. [work] Session s2 (29 msgs, Jan 16-20)
   Topics: Camaro model, engine wiring, soldering

3. [personal] Session s3 (41 msgs, Feb 1-10)
   Topics: Tiger I tank, dioramas, weathering

4. [work] Session s4 (18 msgs, Feb 12-14)
   Topics: Tamiya Spitfire, painting metal surfaces

→ 4 distinct model kits across 2 workspaces (work, personal)
```

### 4.3 `memory_count` output

```
memory_count("model kits")

Searched 2 workspaces (work, personal)
Found 5 distinct model kits:

1. Revell F-15 Eagle (work/s1)
2. B-29 bomber (work/s1)
3. 69 Camaro (personal/s2)
4. Tiger I tank (work/s3)
5. Tamiya Spitfire Mk.V (work/s4)

Total: 5
```

### 4.4 `memory_get_session` output

```
memory_get_session("s1")

Session s1 (34 messages, Jan 3-15)

[user] Jan 3: I'm looking for some tips on photo-etching for my new 1/72 scale B-29 bomber model kit...
[assistant] Jan 3: Photo-etching can be a bit intimidating at first...
[user] Jan 5: I've been thinking about trying out some wire details on my B-29 model...
...
[user] Jan 15: I also started working on a Revell F-15 Eagle kit that I picked up on a whim...
```

### 4.5 Temporal fact querying

```python
def memory_when(entity, attribute, at_date=None):
    """
    Query temporal facts with validity windows.
    Equivalent to MemPalace's temporal entity-relationship graph.
    """
    if at_date:
        # Point-in-time query
        return temporal_facts.where(
            entity=entity, attribute=attribute,
            valid_from <= at_date,
            valid_until IS NULL OR valid_until >= at_date
        )
    else:
        # Current value
        return temporal_facts.where(
            entity=entity, attribute=attribute,
            valid_until IS NULL
        )

def memory_timeline(entity, attribute):
    """Full history of a fact with validity windows."""
    return temporal_facts.where(
        entity=entity, attribute=attribute
    ).order_by(valid_from ASC)
```

---

## 5. Workspace Model Integration

Sessions belong to exactly one workspace. Workspaces become a grouping dimension — same way a session groups messages, a workspace groups sessions.

### 5.1 Per-workspace search (default)

```
memory_search("quarterly review", workspace_id="work")
  → Only work workspace sessions
```

### 5.2 Cross-workspace search

```
memory_search("quarterly review", cross_workspace=True)
  work      / Session A — Q4 review meeting (45 msgs)
  personal  / Session B — Review notes from home (12 msgs)
  finance   / Session C — Budget review deck (28 msgs)
```

### 5.3 Cross-workspace counting

```
memory_count("projects", cross_workspace=True)
  work      / CRM migration, API redesign (2 projects)
  personal  / Home renovation (1 project)
  → 3 distinct projects across 2 workspaces
```

### 5.4 Graph scope

- **Within a workspace**: Graph edges connect sessions by shared entities and temporal proximity.
- **Cross-workspace**: Each workspace's graph is traversed independently. Results merge with workspace tags.
- **Global graph**: Deferred — not needed for initial accuracy lift.

---

## 6. Phased Rollout

### Phase 1: Session grouping in `memory_search` output

**No schema changes. Pure output formatting.**

Group raw search results by computed session IDs (from message metadata). Show one representative entry per session with message count and topic hint.

- **Changes**: `memory_search` output formatter only (20 lines)
- **Risk**: Zero — no data change, no API change
- **Expected lift**: 20% → 35-45%

### Phase 2: Session dedup + deterministic counting

**Schema: one new `session_digests` table.**

Compute session digests at session close (first 500 chars + auto-extracted entities). HybridDB auto-vectors. Add `memory_count` tool with deterministic entity extraction.

- **Changes**: New table + `memory_count` tool + digest computation (120 lines)
- **Risk**: Low — additive, no existing data migration
- **Expected lift**: 45% → 60-70%

### Phase 3: Temporal validity facts

**Schema: one new `temporal_facts` table.**

Replace current fact extraction with temporal validity windows. Add `memory_when` and `memory_timeline` tools. No LLM extraction — facts are derived from explicit statements with source quoting.

- **Changes**: New table + two new tools + fact creation logic (150 lines)
- **Risk**: Medium — replaces fact extraction pipeline
- **Expected lift**: 70% → 80-85%

### Phase 4: Graph traversal integration

**Schema: existing graph tables, now wired into retrieval.**

Wire `traverse()` into the retrieval path. When search returns low-confidence results, expand via graph edges. Connect sessions by shared entities and temporal proximity.

- **Changes**: Retrieval integration + graph edge creation (100 lines)
- **Risk**: Low — additive, uses existing graph infrastructure
- **Expected lift**: 85% → 90%+

---

## 7. What We Keep

| Component | Fate |
|-----------|------|
| `HybridDB` (FTS5 + ChromaDB) | Unchanged — backbone of search |
| `MessageStore` | Enhanced with `session_id` column |
| `MemoryStore` | Repurposed to store digests + temporal facts |
| `memory_planner` | Unchanged — routes queries correctly |
| `memory_ranker` | Simplified to rank sessions instead of individual messages |
| `_mempalace_boost` | Absorbed into unified ranker |
| Workspaces | Enhanced as a grouping dimension |
| Cross-workspace search (`_search_all_workspaces`) | Integrated into unified pipeline |

## 8. What We Remove

| Component | Reason |
|-----------|--------|
| LLM-based fact extraction (`_do_extract`, `EXTRACTION_TURN_INTERVAL`) | Replaced by deterministic entity extraction from verbatim text |
| Entity/attribute/value triple storage as primary fact format | Replaced by temporal_facts with validity windows |
| Dual search paths (tool vs ranker injection) | Merged into `unified_search` |
| `MemoryMiddleware.extract_from_messages()` | No longer needed — facts are not LLM-extracted |

---

## 9. Migration Path

Phase 1 is a pure code change — no migration needed. Phases 2-4 are additive (new tables, new tools). Existing data in `messages` and `memory_facts` is preserved but gradually superseded by the new architecture. No forced migration.

---

## 10. Success Criteria

| Metric | Current | Target (Phase 4) |
|--------|---------|-------------------|
| LongMemEval multi-session | ~20% | ≥ 85% |
| LongMemEval single-session | ~53% | ≥ 80% |
| LongMemEval temporal-reasoning | ~27% | ≥ 80% |
| Cross-workspace search latency | N/A (not measured) | < 500ms for 5 workspaces |
| Deterministic counting accuracy | N/A | 100% (code, not model) |
