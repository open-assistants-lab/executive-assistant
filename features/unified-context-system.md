# Unified Context System: Four-Pillar Architecture

**Status**: Week 1 Implementation Complete (Memory Fix)
**Date**: 2026-02-04
**Principle**: One embedded system per pillar, maximize SQLite, minimize dependencies

---

## Overview

Complete contextual understanding of the user through four complementary pillars:

1. **Memory**: "Who you are" (Declarative knowledge)
2. **Journal**: "What you did" (Episodic knowledge)
3. **Instincts**: "How you behave" (Procedural knowledge)
4. **Goals**: "Why/Where" (Future intentions)

---

## Progress

### ✅ Week 1: Memory Bug Fix (COMPLETE)

**Problem**: Memory retrieval failed in new conversations
- `_get_relevant_memories()` used semantic search for all queries
- General queries like "What do you remember?" didn't match profile content
- Profile memories (name, role, etc.) were never retrieved

**Solution**: Always load profile memories using `list_memories()`
- Added `_is_general_query()` helper for query detection
- For general queries: return all memories
- For specific queries: combine profile + search results

**Files Changed**:
- `src/executive_assistant/channels/base.py`: Memory retrieval fix
- `tests/test_memory_retrieval_fix.py`: 7 unit tests demonstrating bug and fix
- `tests/test_memory_integration.py`: 5 integration tests

**Tests**: 12/12 passing (tested with Ollama Cloud deepseek-v3.2:cloud)

---

### 🔄 Week 2: Instincts Migration (NEXT)

**Current**: JSON-based storage (instincts.jsonl + instincts.snapshot.json)
**Target**: SQLite-based storage (instincts.db)

**Migration Plan**:
1. Create SQLite schema for instincts
2. Write migration script from JSON to SQLite
3. Update instincts storage to use SQL queries
4. Maintain observer/injector patterns (they work well!)
5. Add journal integration
6. Add memory integration
7. Add projects domain

**Schema**:
```sql
CREATE TABLE instincts (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    action TEXT NOT NULL,
    domain TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT,
    occurrence_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 1.0,
    last_triggered TEXT,
    status TEXT DEFAULT 'active',
    base_confidence REAL,
    frequency_boost REAL,
    staleness_penalty REAL,
    final_confidence REAL,
    created_at TEXT,
    updated_at TEXT
);

CREATE VIRTUAL TABLE instincts_fts USING fts5(trigger, action);
```

---

### 📋 Week 3: Journal System (PENDING)

**Current**: Not implemented
**Target**: SQLite + sqlite-vss for vector search

**Features**:
- Time-series entries with automatic rollups
- Semantic search with embeddings
- Keyword search with FTS5
- Time-range queries
- Rollup chain: hourly → daily → weekly → monthly → yearly

**Schema**:
```sql
CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    content TEXT NOT NULL,
    entry_type TEXT NOT NULL,  -- 'raw', 'hourly_rollup', etc.
    timestamp TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    metadata JSON,
    embedding BLOB,
    parent_id TEXT,
    rollup_level INTEGER,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (parent_id) REFERENCES journal_entries(id)
);

CREATE VIRTUAL TABLE journal_fts USING fts5(content);
CREATE VIRTUAL TABLE journal_vss USING vss0(journal_entries(embedding));
```

**Validation Criteria**:
- Vector search quality > 0.7 relevance
- Search performance < 100ms
- Scalability: 10K entries < 200ms

**Fallback**: ChromaDB embedded (if sqlite-vss insufficient)

---

### 📋 Week 4: Goals System (PENDING)

**Current**: Not implemented
**Target**: SQLite-based goal tracking

**Features**:
- Goal creation and management
- Progress tracking
- Change detection (5 mechanisms)
- Version history
- Dependency tracking

**Schema**:
```sql
CREATE TABLE goals (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,  -- 'short_term', 'medium_term', 'long_term'
    target_date TEXT,
    status TEXT DEFAULT 'planned',
    progress REAL DEFAULT 0.0,
    priority INTEGER NOT NULL,
    importance INTEGER NOT NULL,
    parent_goal_id TEXT,
    related_projects JSON,
    depends_on JSON,
    tags JSON,
    notes JSON,
    FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
);

CREATE TABLE goal_progress (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    progress REAL NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE goal_versions (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot JSON NOT NULL,
    change_type TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);
```

**Change Detection**:
1. Explicit statements: "I changed my mind about X"
2. Journal stagnation: No progress for 2+ weeks
3. Progress stalls: Stuck at same percentage for 1+ week
4. Target dates: Approaching deadline with low progress
5. Contradictions: New actions conflict with goal

---

## Tech Stack

### Unified SQLite Approach

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

### Benefits

**Simplicity**: Same system for all pillars
- One query language (SQL)
- One backup strategy (copy .db files)
- One maintenance pattern

**Performance**: Proven, battle-tested
- SQLite: ACID compliant, embedded
- Vector search: sqlite-vss extension
- Single file = fast I/O

**Reliability**: No server failures
- Embedded = no network overhead
- Single file = no corruption complexity
- Battle-tested in production

**Portability**: No vendor lock-in
- Cross-platform compatible
- Easy to migrate/export
- Open source

---

## File System Layout

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

---

## How All Four Work Together

### Example: "Create a sales report"

```
User: "Create a sales report"

↓ Memory loads (instant)
✅ User: Alice, PM at Acme
✅ Domain: Sales analytics
✅ Preference: Brief responses

↓ Journal searches (on-demand)
✅ [Daily] Yesterday: Analyzed Q4 sales data
✅ [Weekly] Working on sales dashboard project
✅ [Recent] Created work_log table

↓ Instincts matches (automatic)
✅ Pattern: "User asks for report"
✅ Rule: Use bullet points, keep brief
✅ Confidence: 0.9 (learned from 5 interactions)

↓ Goals checks (context)
✅ [Active] Launch dashboard by end of month
✅ [Priority] High (8/10)
✅ [Progress] 60% complete

↓ Agent combines ALL FOUR

"Here's your Q4 sales report, Alice:

• Total revenue: $1.2M (+15% YoY)
• Top product: Widget A (42% of sales)
• Key insight: Enterprise segment growing fastest
• Next action: Follow up with top 10 customers

I kept it brief as you prefer. Want me to expand on any section?"
```

**Breakdown**:
- **Memory**: Identified user (Alice), domain (sales), style (brief)
- **Journal**: Provided context (Q4 data, recent work)
- **Instincts**: Guided format (bullet points, concise)
- **Goals**: Added relevant context (dashboard launch, progress tracking)
- **Goals**: Added relevant context (dashboard launch)

---

## Implementation Roadmap

### Phase 1: Memory Fix ✅ (COMPLETE)
- ✅ Fix memory retrieval (search_memories issue)
- ✅ Add general query detection
- ✅ Verify memory system works perfectly
- ✅ Tests: 12/12 passing

### Phase 2: Instincts Migration (Week 2)
- [ ] Migrate JSON → SQLite
- [ ] Update queries to use SQL
- [ ] Maintain observer/injector patterns
- [ ] Add journal integration
- [ ] Add memory integration
- [ ] Add projects domain
- [ ] Test compatibility

### Phase 3: Journal System (Week 3)
- [ ] Validate sqlite-vss (quality, performance, scalability)
- [ ] Build journal system with SQLite
- [ ] Add sqlite-vss for semantic search
- [ ] Implement time-rollups
- [ ] Test vector search quality
- [ ] Fallback to ChromaDB if needed

### Phase 4: Goals System (Week 4)
- [ ] Build goals system with SQLite
- [ ] Add progress tracking
- [ ] Implement change detection
- [ ] Add journal integration
- [ ] Add memory integration
- [ ] Version history and conflict resolution

---

## Success Criteria

### Memory System ✅
- ✅ Profile memories always retrieved
- ✅ Cross-conversation memory retrieval works
- ✅ General queries return all memories
- ✅ Specific queries combine profile + search
- ✅ No cross-contamination between users
- ✅ Tests passing: 12/12

### Instincts System
- Pattern matching < 10ms
- Auto-learning from conversations
- Reinforcement/decay mechanisms
- Integration with journal (learn from patterns)
- Integration with memory (informed by facts)

### Journal System
- Vector search quality > 0.7 relevance
- Search performance < 100ms
- Scalability: 10K entries < 200ms
- Automatic rollups working
- Time-range queries fast
- Semantic + keyword search

### Goals System
- Change detection accuracy > 80%
- Progress tracking working
- Version history maintained
- Journal integration (detect changes)
- Memory integration (informed by facts)

---

## Next Steps

1. ✅ **COMPLETE**: Memory bug fix (Week 1)
2. **NEXT**: Migrate instincts to SQLite (Week 2)
3. **THEN**: Implement journal system (Week 3)
4. **FINALLY**: Implement goals system (Week 4)

All four pillars working harmoniously! 🎯
