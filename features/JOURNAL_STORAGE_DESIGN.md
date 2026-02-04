# Journal Storage System Design

**Date**: 2026-02-04
**Goal**: Time-based rollup journal for long-term context retention

---

## Overview

### What Is Journal?

A **time-rollup journal system** that stores:
- Raw activity (24 hours)
- Hourly summaries (48 hours)
- Daily summaries (90 days)
- Weekly summaries (1 year)
- Monthly summaries (7 years)
- Yearly summaries (indefinite)

### Why Journal?

1. **Semantic search**: Vector embeddings for "What was I working on?"
2. **Time queries**: Natural time-based questions
3. **Context enrichment**: Automatic relevant context injection
4. **Trend analysis**: Progress tracking over time
5. **Storage efficiency**: 90% smaller than raw logs

---

## Storage Architecture

### Hybrid Storage: SQLite + Vector DB

```
Journal Entry
    ↓
    ├─→ SQLite (structured data)
    │   ├─ id, thread_id, content
    │   ├─ entry_type, timestamp
    │   ├─ period_start, period_end
    │   └─ metadata (JSON)
    │
    └─→ ChromaDB (semantic search)
        ├─ vector embedding
        ├─ content
        └─ metadata (thread_id, type, time)
```

### Why Hybrid?

| Aspect | SQLite | ChromaDB | Combined |
|--------|---------|----------|----------|
| **Structured queries** | ✅ Perfect | ❌ Limited | ✅ Best |
| **Semantic search** | ❌ No | ✅ Perfect | ✅ Best |
| **Time range queries** | ✅ Fast | ⚠️ Slow | ✅ Best |
| **Full-text search** | ✅ FTS5 | ⚠️ Limited | ✅ Best |
| **Storage cost** | ✅ Free | ✅ Free | ✅ Free |
| **Complexity** | ✅ Low | ⚠️ Medium | ⚠️ Medium |

---

## Database Schema

### SQLite Schema

```sql
-- Journal entries table
CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,              -- UUID
    thread_id TEXT NOT NULL,          -- Thread identifier
    content TEXT NOT NULL,            -- Entry content

    -- Entry classification
    entry_type TEXT NOT NULL,         -- 'raw', 'profile_snapshot', 'hourly_rollup',
                                      -- 'daily_rollup', 'weekly_rollup',
                                      -- 'monthly_rollup', 'yearly_rollup'

    -- Time period
    timestamp TEXT NOT NULL,          -- ISO 8601 UTC
    period_start TEXT NOT NULL,       -- Rollup period start
    period_end TEXT NOT NULL,         -- Rollup period end

    -- Metadata
    metadata JSON,                    -- Projects, tags, stats, source_entries

    -- Rollup chain
    parent_id TEXT,                   -- Parent entry (for rollup tracking)
    rollup_level INTEGER,             -- 0=raw, 1=hourly, 2=daily, 3=weekly,
                                      -- 4=monthly, 5=yearly

    -- Status
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'archived', 'deleted'

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Foreign keys
    FOREIGN KEY (parent_id) REFERENCES journal_entries(id)
);

-- Indexes for performance
CREATE INDEX idx_journal_thread ON journal_entries(thread_id);
CREATE INDEX idx_journal_type ON journal_entries(entry_type);
CREATE INDEX idx_journal_timestamp ON journal_entries(timestamp);
CREATE INDEX idx_journal_period ON journal_entries(period_start, period_end);
CREATE INDEX idx_journal_rollup ON journal_entries(thread_id, rollup_level);

-- Full-text search
CREATE VIRTUAL TABLE journal_fts USING fts5(
    content,
    content=journal_entries,
    content_rowid=rowid
);

-- Trigger to keep FTS in sync
CREATE TRIGGER journal_fts_insert AFTER INSERT ON journal_entries
BEGIN
    INSERT INTO journal_fts(rowid, content)
    VALUES (new.id, new.content);
END;

-- Trigger for updated
CREATE TRIGGER journal_fts_update AFTER UPDATE ON journal_entries
BEGIN
    UPDATE journal_fts SET content = new.content WHERE rowid = new.id;
END;
```

### ChromaDB Schema

```python
# Collection setup
import chromadb
from chromadb.config import Settings

client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./data/journal"
))

collection = client.get_or_create_collection(
    name="journal",
    metadata={
        "hnsw:space": "cosine",  # Cosine similarity
        "hnsw:M": 16,            # 16 connections per node
    }
)

# Document structure
{
    "id": "entry_123",
    "document": "Alice completed sales analysis dashboard",
    "embedding": [0.1, 0.2, ...],  # Auto-generated if omitted
    "metadata": {
        "thread_id": "http_http_alice",
        "entry_type": "daily_rollup",
        "timestamp": "2025-02-04T10:00:00Z",
        "period_start": "2025-02-04T00:00:00Z",
        "period_end": "2025-02-04T23:59:59Z",
        "rollup_level": 2,
        "projects": ["sales", "analytics"],
        "tags": ["completed", "dashboard"]
    }
}
```

---

## Entry Types & Retention

### Type Definitions

| Entry Type | Rollup Level | Retention | Purpose |
|------------|--------------|-----------|---------|
| **profile_snapshot** | 0 | Indefinite | User profile (name, role) |
| **raw** | 0 | 24 hours | Individual activities/messages |
| **hourly_rollup** | 1 | 48 hours | Hourly summary |
| **daily_rollup** | 2 | 90 days | Daily summary |
| **weekly_rollup** | 3 | 1 year | Weekly summary |
| **monthly_rollup** | 4 | 7 years | Monthly summary |
| **yearly_rollup** | 5 | Indefinite | Yearly summary |

### Retention Policy

```python
RETENTION_POLICY = {
    "raw": timedelta(hours=24),
    "hourly_rollup": timedelta(hours=48),
    "daily_rollup": timedelta(days=90),
    "weekly_rollup": timedelta(days=365),
    "monthly_rollup": timedelta(days=365 * 7),
    "yearly_rollup": None,  # Indefinite
    "profile_snapshot": None,  # Indefinite
}
```

---

## Storage Layout

### File System Structure

```
data/
├── users/
│   ├── http_http_alice/
│   │   ├── journal/
│   │   │   ├── journal.db           # SQLite database
│   │   │   ├── journal_vectors/     # ChromaDB storage
│   │   │   │   ├── chroma.sqlite3   # Vector index
│   │   │   │   └── data.parquet     # Embeddings
│   │   │   └── rollups.log         # Rollup audit log
│   │   └── ...
│   ├── http_http_bob/
│   │   └── journal/
│   │       └── ...
│   └── ...
```

### Per-User Isolation

**Each user has separate journal database** (same as memory system):
```
data/users/http_http_alice/journal/journal.db     # Alice's journal
data/users/http_http_bob/journal/journal.db       # Bob's journal
```

**Cross-user isolation enforced** at file system level.

---

## Journal Entry Schema

### Raw Entry

```python
{
    "id": "entry_abc123",
    "thread_id": "http_http_alice",
    "content": "Created work_log table with columns: date, task, duration",
    "entry_type": "raw",
    "timestamp": "2025-02-04T10:15:30Z",
    "period_start": "2025-02-04T10:00:00Z",
    "period_end": "2025-02-04T10:59:59Z",
    "metadata": {
        "source": "user_message",
        "message_id": "msg_456",
        "projects": ["work_log"],
        "action": "create_tdb_table",
        "tools_used": ["create_tdb_table"]
    },
    "rollup_level": 0,
    "status": "active"
}
```

### Hourly Rollup

```python
{
    "id": "rollup_hourly_20250204_10",
    "thread_id": "http_http_alice",
    "content": """
[10:00-11:00] Worked on database schema for sales analysis project.
Created work_log table with date, task, duration columns.
Added initial test entry for Q4 sales data.
""",
    "entry_type": "hourly_rollup",
    "timestamp": "2025-02-04T11:00:00Z",
    "period_start": "2025-02-04T10:00:00Z",
    "period_end": "2025-02-04T10:59:59Z",
    "metadata": {
        "source_entry_count": 3,
        "source_entries": ["entry_abc123", "entry_def456", "entry_ghi789"],
        "projects": ["sales", "analytics", "work_log"],
        "actions_taken": ["create_tdb_table", "insert_data"],
        "tools_used": ["create_tdb_table", "tdb_insert"],
        "llm_model": "claude-haiku-4-5",
        "rollup_cost_tokens": 250
    },
    "parent_id": None,
    "rollup_level": 1,
    "status": "active"
}
```

### Daily Rollup

```python
{
    "id": "rollup_daily_20250204",
    "thread_id": "http_http_alice",
    "content": """
**February 4, 2025**

Major progress on sales analysis infrastructure:
• Created complete work log tracking system
• Designed schema for customer data integration
• Successfully tested Q4 data pipeline
• Prepared for next phase: automation scripts

Key achievement: End-to-end pipeline from PostgreSQL to analysis ready.
Status: On track, ahead of schedule by 1 day.
""",
    "entry_type": "daily_rollup",
    "timestamp": "2025-02-04T23:59:59Z",
    "period_start": "2025-02-04T00:00:00Z",
    "period_end": "2025-02-04T23:59:59Z",
    "metadata": {
        "source_entry_count": 24,  # 24 hourly rollups
        "hours_worked": 6.5,
        "projects": ["sales", "analytics"],
        "tasks_completed": 5,
        "tasks_in_progress": 2,
        "blockers": None,
        "milestones": ["work_log_complete", "schema_finalized"],
        "sentiment": "positive",
        "productivity_score": 8.5,
        "llm_model": "claude-haiku-4-5",
        "rollup_cost_tokens": 850
    },
    "parent_id": None,
    "rollup_level": 2,
    "status": "active"
}
```

---

## Rollup System

### Rollup Hierarchy

```
Raw Entries (24h)
    ↓ [每小时触发]
Hourly Rollups (48h)
    ↓ [每天午夜触发]
Daily Rollups (90d)
    ↓ [每周一触发]
Weekly Rollups (1y)
    ↓ [每月1号触发]
Monthly Rollups (7y)
    ↓ [每年1月1号触发]
Yearly Rollups (∞)
```

### Rollup Triggers

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class JournalRollupManager:
    """Manages automatic rollup creation"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_triggers()

    def _setup_triggers(self):
        """Schedule rollup jobs"""

        # Hourly rollup (every hour at :00)
        self.scheduler.add_job(
            self._rollup_hourly,
            trigger='cron',
            minute=0,
            id='rollup_hourly'
        )

        # Daily rollup (every day at 00:05)
        self.scheduler.add_job(
            self._rollup_daily,
            trigger='cron',
            hour=0,
            minute=5,
            id='rollup_daily'
        )

        # Weekly rollup (every Monday at 00:10)
        self.scheduler.add_job(
            self._rollup_weekly,
            trigger='cron',
            day_of_week='mon',
            hour=0,
            minute=10,
            id='rollup_weekly'
        )

        # Monthly rollup (1st of month at 00:15)
        self.scheduler.add_job(
            self._rollup_monthly,
            trigger='cron',
            day=1,
            hour=0,
            minute=15,
            id='rollup_monthly'
        )

        # Yearly rollup (Jan 1st at 01:00)
        self.scheduler.add_job(
            self._rollup_yearly,
            trigger='cron',
            month=1,
            day=1,
            hour=1,
            minute=0,
            id='rollup_yearly'
        )

    async def _rollup_hourly(self):
        """Roll up raw entries to hourly summary"""
        # Get all threads with raw entries in last hour
        threads = await self._get_threads_with_raw_entries(hours=1)

        for thread_id in threads:
            # Get raw entries for this hour
            entries = await self._get_entries(
                thread_id=thread_id,
                entry_type='raw',
                period_start=utc_now() - timedelta(hours=1),
                period_end=utc_now()
            )

            if not entries:
                continue

            # Generate summary
            summary = await self._generate_summary(
                entries=entries,
                rollup_type='hourly'
            )

            # Save hourly rollup
            await self._save_rollup(
                thread_id=thread_id,
                content=summary,
                entry_type='hourly_rollup',
                period_start=entries[0]['timestamp'],
                period_end=entries[-1]['timestamp'],
                source_entries=entries
            )

            # Delete raw entries (retention policy)
            await self._delete_old_entries(
                thread_id=thread_id,
                entry_type='raw',
                older_than=timedelta(hours=24)
            )
```

---

## LLM Summarization

### Summary Prompt Templates

#### Hourly Summary

```python
HOURLY_PROMPT = """
Summarize these journal entries from the past hour into a concise hourly summary.

{entries}

Focus on:
1. Key actions taken
2. Projects worked on
3. Tools/features created or modified
4. Any issues encountered

Keep it under 100 words. Be specific and factual.
"""

# Example output
"""
[10:00-11:00] Created work_log table for sales analysis.
Added columns for date, task, duration, and status.
Successfully tested with sample Q4 data entry.
"""
```

#### Daily Summary

```python
DAILY_PROMPT = """
Summarize these hourly rollups into a comprehensive daily summary.

{hourly_rollups}

Include:
1. Major accomplishments (what got done)
2. Projects worked on (which areas)
3. Progress made (how far along)
4. Any blockers or issues (what's stuck)
5. Next steps (what's coming up)

Keep it under 200 words. Use bullet points for clarity.

Format:
**Date**: {date}

**Accomplishments**:
• ...

**Projects**: ...

**Progress**: ...

**Blockers**: (if any)

**Next Steps**: ...
"""

# Example output
"""
**February 4, 2025**

**Accomplishments**:
• Built complete work log tracking system
• Integrated customer data schema
• Validated Q4 sales data pipeline

**Projects**:
Sales analytics infrastructure (main focus)

**Progress**:
Phase 1 complete: Schema and basic CRUD
Phase 2 in progress: Data integration
Status: Ahead of schedule by 1 day

**Next Steps**:
Build automation scripts for daily reports
"""
```

#### Weekly Summary

```python
WEEKLY_PROMPT = """
Summarize these daily rollups into a weekly progress summary.

{daily_rollups}

Focus on:
1. Major milestones achieved
2. Project trajectories (accelerating? stalled?)
3. Productivity trends
4. Key learnings or insights
5. Week-over-week progress

Keep it under 300 words. Use weekly perspective.
"""

# Example output
"""
**Week of February 3, 2025**

**Major Achievements**:
Completed sales analytics infrastructure foundation.
Successfully deployed work log system with 80% team adoption.

**Project Status**:
Sales Analytics: ✅ Phase 1 complete, entering Phase 2
Timeline: On track
Velocity: 1.2x planned velocity (ahead of schedule)

**Key Wins**:
• Integrated customer data from CRM
• Automated daily data pipeline
• Zero critical bugs in production

**Learnings**:
User feedback loop is critical - caught 3 UX issues early through daily testing.

**Next Week**:
Focus on automation and reporting features.
Target: Beta release by Friday.
"""
```

### Model Selection for Rollups

| Rollup Type | Model | Tokens | Cost | Reason |
|-------------|-------|--------|------|--------|
| **Hourly** | claude-haiku-4-5 | ~250 | $0.00006 | Fast, cheap, concise |
| **Daily** | claude-haiku-4-5 | ~850 | $0.00021 | Good balance |
| **Weekly** | claude-sonnet-4-5 | ~2,000 | $0.00030 | Better reasoning |
| **Monthly** | claude-sonnet-4-5 | ~4,000 | $0.00060 | Deep analysis |
| **Yearly** | claude-sonnet-4-5 | ~8,000 | $0.00120 | Strategic overview |

**Annual cost per user**:
- Hourly: 365 × 24 × $0.00006 = $0.53
- Daily: 365 × $0.00021 = $0.08
- Weekly: 52 × $0.00030 = $0.02
- Monthly: 12 × $0.00060 = $0.01
- Yearly: 1 × $0.00120 = $0.00
- **Total**: ~$0.64/year/user ✅ **Negligible!**

---

## API Design

### Core Operations

```python
class JournalStorage:
    """Journal storage interface"""

    async def add_entry(
        self,
        thread_id: str,
        content: str,
        entry_type: str = "raw",
        metadata: dict | None = None,
    ) -> str:
        """
        Add a journal entry.

        Args:
            thread_id: Thread identifier
            content: Entry content
            entry_type: Entry type (raw, profile_snapshot, etc.)
            metadata: Optional metadata (projects, tags, etc.)

        Returns:
            Entry ID
        """

    async def search(
        self,
        thread_id: str,
        query: str,
        time_range: tuple[datetime, datetime] | None = None,
        entry_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Semantic + keyword search.

        Args:
            thread_id: Thread identifier
            query: Search query
            time_range: Optional (start, end) time filter
            entry_types: Optional entry type filters
            limit: Max results

        Returns:
            List of matching entries
        """

    async def get_time_range(
        self,
        thread_id: str,
        start: datetime,
        end: datetime,
        rollup_level: int | None = None,
    ) -> list[dict]:
        """
        Get entries in time range.

        Args:
            thread_id: Thread identifier
            start: Start time
            end: End time
            rollup_level: Optional rollup level filter

        Returns:
            List of entries in range
        """

    async def get_rollup(
        self,
        thread_id: str,
        period: str,  # "hourly", "daily", "weekly", "monthly", "yearly"
        timestamp: datetime | None = None,
    ) -> dict | None:
        """
        Get specific rollup.

        Args:
            thread_id: Thread identifier
            period: Rollup period type
            timestamp: Optional timestamp (defaults to current)

        Returns:
            Rollup entry or None
        """

    async def get_profile_snapshot(
        self,
        thread_id: str,
    ) -> dict | None:
        """
        Get user profile snapshot.

        Args:
            thread_id: Thread identifier

        Returns:
            Profile snapshot or None
        """
```

---

## Query Examples

### Natural Language Queries

```python
# What was I working on last week?
results = await journal.search(
    thread_id="http_http_alice",
    query="What was I working on?",
    time_range=(week_ago, now),
    entry_types=["weekly_rollup"]
)
# Returns: Weekly rollup summarizing work

# Show me my progress this month
results = await journal.get_time_range(
    thread_id="http_http_alice",
    start=month_start,
    end=now,
    rollup_level=4  # monthly_rollup
)
# Returns: All monthly rollups in range

# What did I accomplish in February?
results = await journal.search(
    thread_id="http_http_alice",
    query="accomplishments achievements completed",
    time_range=(feb_1, mar_1),
    entry_types=["monthly_rollup", "weekly_rollup"]
)
# Returns: February achievements

# How's my project going?
results = await journal.search(
    thread_id="http_http_alice",
    query="project status progress blockers issues",
    time_range=(week_ago, now),
    limit=5
)
# Returns: Recent project updates
```

---

## Integration with Memory System

### Phase 1: Parallel Systems

```python
# Keep existing memory system
create_memory(type="profile", content="Alice is PM")
create_memory(type="fact", content="Prefers brief responses")

# Add journal system
journal.add_entry(
    content="Alice is a product manager at Acme Corp",
    entry_type="profile_snapshot"
)

# Both work independently
```

### Phase 2: Journal As Memory Backend

```python
# Memory system uses journal as storage
def create_memory(content, type):
    journal.add_entry(
        content=content,
        entry_type="profile_snapshot" if type == "profile" else "raw",
        metadata={"memory_type": type}
    )

def list_memories():
    return journal.search(
        query="",
        entry_types=["profile_snapshot", "fact"]
    )
```

### Phase 3: Unified System

```python
# Journal becomes the single source of truth
# Old memory system deprecated/migrated
```

---

## Migration Strategy

### Step 1: Add Journal Alongside Memory (Week 1)

```python
# Existing code unchanged
memories = storage.list_memories(type="profile")

# New journal system
journal_entries = journal.search(query="profile snapshot")

# Combine both
context = memories + journal_entries
```

### Step 2: Migrate Profile Memories (Week 2)

```python
# One-time migration script
async def migrate_profile_memories():
    for thread_id in all_threads:
        # Get existing profile memories
        memories = storage.list_memories(
            thread_id=thread_id,
            memory_type="profile"
        )

        # Create profile snapshot in journal
        content = summarize_profile(memories)
        await journal.add_entry(
            thread_id=thread_id,
            content=content,
            entry_type="profile_snapshot",
            metadata={"migrated_from": "memory_system"}
        )
```

### Step 3: Gradual Migration (Week 3-4)

```python
# New conversations use journal
if is_new_conversation(thread_id):
    profile = journal.get_profile_snapshot(thread_id)
else:
    # Old conversations still use memory
    profile = storage.list_memories(type="profile")
```

### Step 4: Full Rollout (Month 2)

```python
# All conversations use journal
profile = journal.get_profile_snapshot(thread_id)

# Memory system deprecated (kept for read-only legacy)
```

---

## Performance Considerations

### Storage Growth

**Per user estimates**:
- Raw entries: 1,000/day = ~100KB/day = **36.5 MB/year**
- With rollups: ~10KB/day = **3.6 MB/year**

**Savings**: 90% reduction! ✅

### Query Performance

| Query | SQLite | ChromaDB | Hybrid |
|-------|--------|----------|--------|
| **Get by ID** | 1ms | 5ms | 1ms |
| **Time range** | 10ms | 50ms | 10ms |
| **Semantic search** | N/A | 20ms | 25ms |
| **Full-text search** | 5ms | N/A | 5ms |

### Index Strategy

```sql
-- Most common queries
SELECT * FROM journal_entries
WHERE thread_id = ?                    -- ✅ Indexed
  AND timestamp BETWEEN ? AND ?        -- ✅ Indexed
  AND rollup_level = ?                 -- ✅ Indexed
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Implementation Plan

### Week 1: Core Storage

- [ ] Create SQLite schema
- [ ] Set up ChromaDB collection
- [ ] Implement basic CRUD operations
- [ ] Add FTS indexing

### Week 2: Rollup System

- [ ] Implement rollup triggers
- [ ] Create LLM summarization
- [ ] Add rollup chain tracking
- [ ] Test retention policies

### Week 3: Search & Queries

- [ ] Implement semantic search
- [ ] Add time range queries
- [ ] Create query API
- [ ] Performance testing

### Week 4: Integration

- [ ] Integrate with message processing
- [ ] Add context injection
- [ ] Create migration scripts
- [ ] Update documentation

---

## Summary

### Storage: SQLite + ChromaDB

**Why hybrid?**
- SQLite: Fast time queries, structured data
- ChromaDB: Semantic search, vector similarity
- Combined: Best of both worlds

### Rollups: Automated & LLM-Powered

- **Hourly**: Concise activity log
- **Daily**: Daily accomplishments & progress
- **Weekly**: Milestones & trajectory
- **Monthly**: Strategic overview
- **Yearly**: Career/life summary

### Cost: Negligible

- **Storage**: ~3.6 MB/year/user (compressed)
- **LLM calls**: ~$0.64/year/user
- **Query latency**: 10-25ms average

### Benefits

1. ✅ Fixes semantic search (vector embeddings)
2. ✅ Natural time queries ("What was I working on last week?")
3. ✅ Automatic context enrichment
4. ✅ 90% storage reduction
5. ✅ Trend analysis & progress tracking

**Ready to implement?**

**Next step**: Build the core storage system (SQLite schema + ChromaDB setup).
