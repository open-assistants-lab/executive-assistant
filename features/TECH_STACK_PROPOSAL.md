# Proposed Tech Stack: Four-Pillar Context System

**Date**: 2026-02-04
**Principle**: One embedded system per pillar, maximize SQLite, minimize dependencies

---

## Pillar 1: Memory ✅ Keep As-Is

### Current Implementation
```
Storage: SQLite
Location: data/users/http_{thread_id}/mem/mem.db
Size: ~10 KB per user
```

**Verdict**: **PERFECT** - Don't change it!

**Why**:
- ✅ One file per user (clean isolation)
- ✅ Key-value queries are instant
- ✅ SQLite is embedded, no dependencies
- ✅ Already working well

**Schema**:
```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    memory_type TEXT,
    key TEXT,
    content TEXT,
    confidence REAL,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

---

## Pillar 2: Journal - REDESIGN for Simplicity

### Current Proposal (Too Complex)
```
Storage: SQLite + ChromaDB hybrid
Files: journal.db + journal_vectors/ (2 systems)
Dependencies: chromadb + duckdb
```

### NEW Proposal: **SQLite Only + sqlite-vss**

```
Storage: SQLite with vector extensions
Location: data/users/http_{thread_id}/journal/journal.db
Files: ONE file per user
Dependencies: sqlite-vss (vector similarity search extension)
```

**Why sqlite-vss?**
- ✅ Single SQLite file per user
- ✅ Built-in vector similarity search
- ✅ Still has FTS5 for keyword search
- ✅ Time-based queries remain fast
- ✅ No external dependencies (pure SQLite)

**Installation**:
```bash
# Install sqlite-vss extension
# Load as extension in SQLite
```

**Schema**:
```sql
-- Main entries table
CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    content TEXT NOT NULL,
    entry_type TEXT NOT NULL,  -- 'raw', 'hourly_rollup', etc.
    timestamp TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    metadata JSON,

    -- Vector embedding (as BLOB)
    embedding BLOB,

    -- Rollup chain
    parent_id TEXT,
    rollup_level INTEGER,

    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT,

    FOREIGN KEY (parent_id) REFERENCES journal_entries(id)
);

-- Indexes
CREATE INDEX idx_journal_thread ON journal_entries(thread_id);
CREATE INDEX idx_journal_timestamp ON journal_entries(timestamp);
CREATE INDEX idx_journal_type ON journal_entries(entry_type);

-- FTS5 for keyword search
CREATE VIRTUAL TABLE journal_fts USING fts5(content);
CREATE TRIGGER journal_fts_insert AFTER INSERT ON journal_entries
BEGIN
    INSERT INTO journal_fts(rowid, content) VALUES (new.id, new.content);
END;

-- Virtual table for vector similarity (sqlite-vss)
CREATE VIRTUAL TABLE journal_vss USING vss0(
    journal_entries(embedding)
    WITH (
        vss_tokenizer(json('jieba'),  -- Chinese + English tokenization
        vss_embedding('mxbai-embeddings'),  -- Embedding function
        vss_flavor('sentence')
    )
);

-- Vector similarity search
CREATE VIRTUAL TABLE journal_search USING vss0(
    journal_entries(embedding)
    WITH (
        vss_tokenizer(json('jieba')),
        vss_embedding('mxbai-embeddings')
    );
```

**Query Examples**:
```python
# Semantic search
results = cursor.execute("""
    SELECT id, content, distance
    FROM journal_search
    WHERE vss_search(embedding, 'What was I working on?')
    ORDER BY distance
    LIMIT 10
""")

# Time range
results = cursor.execute("""
    SELECT * FROM journal_entries
    WHERE timestamp BETWEEN '2025-02-01' AND '2025-02-07'
    ORDER BY timestamp ASC
""")

# Combined (semantic + time)
results = cursor.execute("""
    SELECT * FROM journal_entries
    WHERE id IN (
        SELECT id FROM journal_search
        WHERE vss_search(embedding, 'sales analysis')
        ORDER BY distance
        LIMIT 50
    )
    AND timestamp >= '2025-02-01'
    ORDER BY timestamp DESC
""")
```

**Benefits**:
- ✅ Single file per user
- ✅ Semantic + keyword search
- ✅ Fast time-based queries
- ✅ Minimal dependencies
- ✅ 3-5 MB per user/year (compressed)

**Cost**: Zero dependencies (sqlite-vss is extension)

---

## Pillar 3: Instincts - REDESIGN for Consolidation

### Current Implementation
```
Storage: JSON files
Files: instincts.jsonl + instincts.snapshot.json
Location: data/users/http_{thread_id}/instincts/
```

### NEW Proposal: **Consolidate into SQLite**

```
Storage: SQLite
Location: data/users/http_{thread_id}/instincts/instincts.db
Files: ONE file per user
```

**Why consolidate?**
- ✅ One file per user (like memory/journal)
- ✅ Better querying (SQL vs JSON parsing)
- ✅ Consistent across all three pillars
- ✅ Easier backup/restore

**Schema**:
```sql
CREATE TABLE instincts (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,

    -- Core instinct
    trigger TEXT NOT NULL,
    action TEXT NOT NULL,
    domain TEXT NOT NULL,
    confidence REAL NOT NULL,

    -- Metadata
    source TEXT,
    occurrence_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 1.0,
    last_triggered TEXT,

    -- Status
    status TEXT DEFAULT 'active',  -- 'active', 'deprecated', 'archived'

    -- Confidence breakdown
    base_confidence REAL,
    frequency_boost REAL,
    staleness_penalty REAL,
    final_confidence REAL,

    -- Timestamps
    created_at TEXT,
    updated_at TEXT
);

-- Indexes
CREATE INDEX idx_instincts_thread ON instincts(thread_id);
CREATE INDEX idx_instincts_domain ON instincts(domain);
CREATE INDEX idx_instincts_confidence ON instincts(final_confidence);

-- For pattern matching searches
CREATE VIRTUAL TABLE instincts_fts USING fts5(
    trigger,
    action
);
```

**Migration**:
```python
# One-time migration from JSON to SQLite
def migrate_instincts_to_sqlite():
    for thread_id in all_threads:
        # Load from JSON
        jsonl_path = f"data/users/http_{thread_id}/instincts/instincts.jsonl"
        snapshot_path = f"data/users/http_{thread_id}/instincts/instincts.snapshot.json"

        # Migrate to SQLite
        sqlite_db = f"data/users/http_{thread_id}/instincts/instincts.db"
        # ... migration logic ...

        # Backup old JSON files
        shutil.copy(jsonl_path, f"{jsonl_path}.backup")
        shutil.copy(snapshot_path, f"{snapshot_path}.backup")
```

**Benefits**:
- ✅ Consistent with memory/journal (all SQLite)
- ✅ Better querying (SQL vs JSON)
- ✅ One file per user
- ✅ Faster (binary vs text parsing)

---

## Pillar 4: Goals - NEW System

### Proposed Implementation
```
Storage: SQLite
Location: data/users/http_{thread_id}/goals/goals.db
Files: ONE file per user
```

**Schema**:
```sql
CREATE TABLE goals (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,

    -- Goal content
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- 'short_term', 'medium_term', 'long_term'

    -- Time tracking
    target_date TEXT,
    created_at TEXT,
    completed_at TEXT,
    abandoned_at TEXT,

    -- Progress
    status TEXT DEFAULT 'planned',  -- 'planned', 'active', 'paused',
                                   -- 'completed', 'abandoned', 'archived'
    progress REAL DEFAULT 0.0,  -- 0.0 to 1.0

    -- Prioritization
    priority INTEGER,  -- 1-10
    importance INTEGER,  -- 1-10

    -- Relationships
    parent_goal_id TEXT,
    related_projects JSON,

    -- Dependencies
    depends_on JSON,

    -- Metadata
    tags JSON,
    notes JSON,

    FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
);

-- Progress history
CREATE TABLE goal_progress (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    progress REAL NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT,  -- 'manual', 'journal_detection', 'auto_update'
    notes TEXT,

    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

-- Goal versions (audit trail)
CREATE TABLE goal_versions (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    version INTEGER NOT NULL,

    -- Snapshot
    snapshot JSON,

    -- Change metadata
    change_type TEXT,
    change_reason TEXT,
    changed_at TEXT,

    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

-- Indexes
CREATE INDEX idx_goals_status ON goals(status);
CREATE INDEX idx_goals_target ON goals(target_date);
CREATE INDEX idx_goals_progress ON goals(progress);
```

**Benefits**:
- ✅ Same system as other pillars (SQLite)
- ✅ One file per user
- ✅ Progress tracking
- ✅ Version history
- ✅ Relationship tracking

---

## Final Unified Architecture

### File System Layout

```
data/users/http_http_alice/
├── mem/
│   └── mem.db                    # Memory (10 KB)
├── journal/
│   └── journal.db               # Journal (3-4 MB/year)
│       ├── journal_entries       # Time-series entries
│       ├── journal_fts           # FTS5 index
│       └── journal_vss           # Vector search
├── instincts/
│   └── instincts.db             # Instincts (50 KB)
│       ├── instincts             # Behavioral patterns
│       └── instincts_fts         # Pattern search
└── goals/
    └── goals.db                  # Goals (100 KB)
        ├── goals                 # Active/abandoned goals
        ├── goal_progress         # Progress tracking
        └── goal_versions        # Audit trail
```

**Total**: ~3.2-4.2 MB per user (with 1 year of journal)

**Per-pillar files**: 1 file each, all SQLite

---

## Dependencies Summary

### Before (Proposed Hybrid)

```
Memory:     ✅ SQLite (no extra deps)
Journal:    ❌ ChromaDB + DuckDB (heavy)
Instincts:   ✅ JSON files (no deps)
Goals:      ✅ SQLite (no extra deps)

Total: 2 extra dependencies (ChromaDB, DuckDB)
```

### After (Unified SQLite)

```
Memory:     ✅ SQLite + standard library
Journal:    ✅ SQLite + sqlite-vss extension
Instincts:   ✅ SQLite + standard library
Goals:      ✅ SQLite + standard library

Total: 1 extra dependency (sqlite-vss)
```

---

## Why This Approach is Better

### 1. Simplicity ✅
- Same system for all pillars (SQLite)
- Easier to maintain
- Easier to backup/restore
- Easier to query across pillars

### 2. Performance ✅
- SQLite: Proven, battle-tested
- sqlite-vss: Vector search at SQLite speed
- Single file = fast I/O
- No network overhead (embedded)

### 3. Reliability ✅
- SQLite: ACID compliant
- Single file per user = no corruption complexity
- Embedded = no server failures
- Battle-tested in production

### 4. Portability ✅
- All data in SQLite files
- Easy to migrate/export
- Cross-platform compatible
- No vendor lock-in

### 5. Cost ✅
- Zero licensing costs
- No infrastructure needed
- Minimal storage
- No API calls (embeddings generated locally)

---

## Alternative: ChromaDB Embedded (If sqlite-vss Doesn't Work)

If sqlite-vss proves immature or insufficient:

```python
# Use ChromaDB embedded
# Stores: DuckDB + Parquet files
# Location: data/users/http_{thread_id}/journal/chromadb/

from chromadb.config import Settings
client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./data/users/http_http_alice/journal/chromadb"
)
```

**Still**: One system (ChromaDB), embedded, no server needed
**Trade-off**: More mature than sqlite-vss, but heavier dependency

---

## Recommendation: SQLite-First Approach

### Phase 1: Validate sqlite-vss (Week 1)

```python
# Test sqlite-vss capabilities
# - Vector search quality
# - Performance benchmarks
# - Ease of integration
# - Compatibility with existing code
```

### Phase 2: Migrate Instincts (Week 2)

```python
# Migrate from JSON to SQLite
# Update instincts.py to use SQL queries instead of JSON
# Keep observer/injector patterns (they're good!)
```

### Phase 3: Implement Goals (Week 3)

```python
# Build goals system with SQLite
# Integrate with journal (learn from patterns)
# Integrate with memory (informed by facts)
```

### Phase 4: Integrate Journal with sqlite-vss (Week 4)

```python
# Implement journal system with sqlite-vss
# Test vector search quality
# If good, keep; if not, fall back to ChromaDB
```

---

## Migration Path

### Current → Proposed

```
Current:

Memory (SQLite) ✅ KEEP
  └── mem.db (10 KB)

Instincts (JSON) → Migrate to SQLite
  ├── instincts.jsonl → instincts.db
  └── instincts.snapshot.json

Journal (not built) → Build with SQLite + sqlite-vss
  └── journal.db (3-4 MB/year)
      ├── journal_entries
      ├── journal_fts
      └── journal_vss (vector search)

Goals (not built) → Build with SQLite
  └── goals.db (100 KB)
```

### Benefits of Migration

**Consistent Stack**:
- All pillars use SQLite
- Same backup/restore tools
- Same query language
- Single expertise

**Simplified Operations**:
- Backup: Copy all `*.db` files
- Restore: Restore `*.db` files
- Migrate: `ATTACH DATABASE` across SQLite files

**Cross-Pillar Queries**:
```sql
-- Search across all pillars
SELECT 'memory' as source, * FROM memories WHERE ...
UNION ALL
SELECT 'instinct' as source, * FROM instincts WHERE ...
UNION ALL
SELECT 'journal' as source, * FROM journal_entries WHERE ...
UNION ALL
SELECT 'goal' as source, * FROM goals WHERE ...
```

---

## Comparison

| Aspect | Before | After |
|--------|--------|-------|
| **Systems** | 3 different (SQLite, JSON, proposed hybrid) | 1 unified (SQLite) |
| **Dependencies** | ChromaDB + DuckDB (heavy) | sqlite-vss (light) |
| **Files per user** | 3-5 files | 4 files (all .db) |
| **Query languages** | SQL + JSON | SQL only |
| **Backup complexity** | Medium | Simple (copy .db files) |
| **Cross-pillar queries** | Hard | Easy (ATTACH DATABASE) |
| **Maintenance** | 3 different patterns | 1 pattern |

---

## Final Stack Summary

```
┌─────────────────────────────────────────────────┐
│                                                  │
│  All Pillars: SQLite + Standard Library         │
│  + Extensions: sqlite-vss (for vectors)         │
│                                                  │
│  Data:                                           │
│  data/users/http_http_alice/                     │
│  ├── mem/mem.db           (10 KB)                │
│  ├── journal/journal.db   (3-4 MB/year)          │
│  ├── instincts/instincts.db (50 KB)               │
│  └── goals/goals.db        (100 KB)                │
│                                                  │
│  Total: ~3.2-4.2 MB per user                         │
│                                                  │
│  Dependencies:                                     │
│  - sqlite3 (Python standard)                      │
│  - sqlite-vss (vector extension)                  │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Implementation Priority

### Week 1: Fix Memory Bug (Critical)
- ✅ Fix memory retrieval (search_memories issue)
- ✅ Add caching to minimize token usage
- ✅ Verify memory system works perfectly

### Week 2: Redesign Instincts
- ✅ Migrate JSON → SQLite
- ✅ Update queries to use SQL
- ✅ Maintain observer/injector patterns (they're good!)
- ✅ Test compatibility

### Week 3: Implement Journal
- ✅ Build journal system with SQLite
- ✅ Add sqlite-vss for semantic search
- ✅ Implement time-rollups
- ✅ Test vector search quality

### Week 4: Implement Goals
- ✅ Build goals system with SQLite
- ✅ Add progress tracking
- ✅ Implement change detection
- ✅ Add journal integration

---

## Validation Criteria

Before committing to sqlite-vss, validate:

```python
# Test 1: Vector search quality
queries = [
    "What was I working on?",
    "Sales dashboard progress",
    "Completed tasks"
]
for query in queries:
    results = sqlite_vss_search(query)
    assert len(results) > 0
    assert results[0]["relevance"] > 0.7

# Test 2: Performance
start = time()
results = sqlite_vss_search(query)
duration = time() - start
assert duration < 100  # Sub-100ms

# Test 3: Scalability
# Add 10K entries, test search performance
assert search_time < 200ms  # Still fast
```

**If sqlite-vss fails**: Fall back to ChromaDB embedded (still one system, just heavier)

---

## Summary: Unified Tech Stack

### Four Pillars, One System

| Pillar | Storage | Files Per User | Size | Dependencies |
|--------|--------|----------------|------|--------------|
| **Memory** | SQLite | 1 file (mem.db) | ~10 KB | None |
| **Journal** | SQLite + sqlite-vss | 1 file (journal.db) | ~3-4 MB/year | sqlite-vss |
| **Instincts** | SQLite | 1 file (instincts.db) | ~50 KB | None |
| **Goals** | SQLite | 1 file (goals.db) | ~100 KB | None |

**Total**: 4 files, ~3.2-4.2 MB per user (with 1 year journal)

**Dependencies**: 1 (sqlite-vss)

**Philosophy**: SQLite-first, add extensions only when needed

---

**This gives us**: Simple, fast, reliable, unified system with one query language, one backup strategy, one maintenance pattern.

**Ready to implement?**

1. Fix memory bug (critical, 2-4 hours)
2. Migrate instincts to SQLite (consolidation)
3. Build journal with sqlite-vss (validate first)
4. Implement goals with SQLite

All working harmoniously! 🎯
