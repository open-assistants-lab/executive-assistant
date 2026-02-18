# Progressive Disclosure on Checkpoints: Technical Feasibility Analysis

## Executive Summary

**Verdict:** ✅ **FEASIBLE** via thread-per-day approach

Progressive disclosure on checkpoints IS technically feasible, but ONLY with separate thread_ids for each time period. You CANNOT partially load a single checkpoint.

---

## How LangGraph Checkpoints Work

### Checkpoint Loading Flow

```python
# When you invoke an agent:
result = await agent.ainvoke(
    {"messages": [HumanMessage("Hello")]},
    config={"configurable": {"thread_id": "user-123"}}
)

# LangGraph internally does:
checkpointer.get_tuple(config)
→ Loads checkpoint from Postgres for thread_id "user-123"
→ Returns CheckpointTuple with ALL state (messages, channel_values, etc.)
→ channels_from_checkpoint() reconstructs full state
→ Agent proceeds with full context
```

**Key constraint:** Loading is **all-or-nothing** per thread_id.

---

## Checkpoint API

### 1. Get Checkpoint (Single Thread)

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(db_uri) as checkpointer:
    config = {"configurable": {"thread_id": "user-123"}}
    checkpoint_tuple = checkpointer.get_tuple(config)

    # Returns:
    # CheckpointTuple(
    #     config={"configurable": {"thread_id": "user-123", "checkpoint_id": "..."}},
    #     checkpoint={"v": 2, "id": "...", "channel_values": {"messages": [...]}, ...},
    #     metadata={"source": "loop", "step": 5},
    #     parent_config=None,
    #     pending_writes=None
    # )
```

**Critical:** This loads the **entire checkpoint state** for that thread_id.

---

### 2. List Checkpoints (With Filtering)

```python
with PostgresSaver.from_conn_string(db_uri) as checkpointer:
    config = {"configurable": {"thread_id": "user-123"}}

    # List all checkpoints for a thread (most recent first)
    for checkpoint_tuple in checkpointer.list(config, limit=10):
        print(checkpoint_tuple.config["configurable"]["checkpoint_id"])
        print(checkpoint_tuple.checkpoint["channel_values"]["messages"])
```

**Important:** You can filter by:
- `thread_id` - Required, scopes to a specific thread
- `filter` - Metadata filtering (e.g., source, step)
- `before` - Checkpoints before a specific ID
- `limit` - Max number to return

**But you CANNOT:**
- Filter by message count (e.g., "last 50 messages")
- Partially load messages
- Load checkpoint without replaying all messages

---

### 3. Database Schema

```sql
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    blob JSONB NOT NULL,
    version TEXT NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, channel)
);
```

**Key insight:** Checkpoints are **versioned** (parent → child), not filtered by content.

---

## What IS NOT Feasible

### ❌ Single Thread + Selective Loading

```python
# This doesn't exist:
config = {"configurable": {
    "thread_id": "user-123",
    "message_limit": 50,  # ← Not supported
    "message_offset": 100  # ← Not supported
}}
```

**Why:**
- LangGraph checkpoints store **graph state**, not just messages
- To replay graph execution, you need the full state snapshot
- Partial state would break graph execution guarantees

### ❌ Partial Message Replay

```python
# You can't do:
checkpointer.get(config, last_n_messages=50)
checkpointer.get(config, messages_after_step=10)
```

**Why:**
- Checkpoints are immutable snapshots
- No slicing or filtering API
- Messages are part of channel_values (all-or-nothing)

### ❌ Lazy Loading Within Thread

```python
# You can't do:
for msg in checkpointer.stream_messages(config):
    # Process one at a time
    pass
```

**Why:**
- No streaming API for checkpoint content
- Loading returns full Checkpoint object
- Lazy loading would break graph replay

---

## What IS Feasible: Progressive Disclosure via Multiple Threads

### ✅ Architecture: Thread Per Day

```python
# Day 1
thread_id = "user-123-2026-02-17"
config = {"configurable": {"thread_id": thread_id}}
result1 = await agent.ainvoke({"messages": [HumanMessage("Hello")]}, config)
# → Creates checkpoint with ~50-100 messages

# Day 2 (different thread!)
thread_id = "user-123-2026-02-18"
config = {"configurable": {"thread_id": thread_id}}
result2 = await agent.ainvoke({"messages": [HumanMessage("Continue")]}, config)
# → Creates NEW checkpoint with ~50-100 messages
```

**Why this works:**
- Each day is a **separate thread_id**
- Each checkpoint is **independently loadable**
- Loading is **explicit** (choose which thread to load)

---

### ✅ Progressive Disclosure Tools

```python
from langchain_core.tools import tool

@tool
def history_list(days: int = 7) -> str:
    """List available conversation checkpoints by date."""
    # Query thread metadata (you'd create this table)
    threads = db.query("""
        SELECT thread_id, date, message_count, title
        FROM thread_metadata
        WHERE user_id = $1
          AND date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY date DESC
    """, (user_id,))

    return "\n".join([
        f"- {t['date']}: {t['title']} ({t['message_count']} messages)"
        for t in threads
    ])

@tool
def history_load(date: str) -> str:
    """Load full conversation from specific date."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # Different thread_id = different checkpoint
    thread_id = f"{user_id}-{date}"
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpoint_tuple = await checkpointer.aget_tuple(config)

        if not checkpoint_tuple:
            return "No conversation found for this date"

        # Extract messages from checkpoint
        checkpoint = checkpoint_tuple.checkpoint
        channel_values = checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])

        # Format for agent
        return format_conversation(messages)

@tool
def history_search(query: str, days: int = 30) -> str:
    """Search across conversation threads."""
    # Search thread metadata titles
    threads = db.query("""
        SELECT thread_id, date, title
        FROM thread_metadata
        WHERE user_id = $1
          AND title ILIKE $2
          AND date >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY date DESC
    """, (user_id, f"%{query}%"))

    return "\n".join([
        f"- {t['date']}: {t['title']}"
        for t in threads
    ])
```

**This IS progressive disclosure because:**
1. **Layer 1:** `history_list()` - Compact index (~50 tokens)
2. **Layer 2:** `history_load(date)` - Load specific checkpoint on demand (~5,000 tokens)
3. **Agent decides** when to load which checkpoint

---

## Implementation Details

### Thread Metadata Storage

```sql
CREATE TABLE thread_metadata (
    user_id TEXT NOT NULL,
    thread_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    message_count INTEGER DEFAULT 0,
    title TEXT,
    first_message_at TEXT,
    last_message_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_thread_metadata_user_date
    ON thread_metadata(user_id, date DESC);
```

### Daily Thread ID Logic

```python
def get_thread_id(user_id: str) -> str:
    """Get thread ID for current date."""
    from datetime import datetime

    # Simple: thread per day
    date_key = datetime.now().strftime("%Y-%m-%d")
    return f"{user_id}-{date_key}"

    # Alternative: thread per week
    # week_key = datetime.now().strftime("%Y-W%U")
    # return f"{user_id}-{week_key}"

    # Alternative: thread per month
    # month_key = datetime.now().strftime("%Y-%m")
    # return f"{user_id}-{month_key}"
```

### Thread Title Generation

```python
def generate_thread_title(messages: list) -> str:
    """Generate brief title from first few messages."""
    # Option 1: Use first user message
    first_user_msg = next(
        (m.content for m in messages if m.type == "human"),
        "Conversation"
    )
    return first_user_msg[:50] + ("..." if len(first_user_msg) > 50 else "")

    # Option 2: Use LLM (more expensive but better)
    # summary = llm.invoke(f"Summarize in 5 words: {messages[:3]}")
    # return summary.content
```

---

## Token Cost Analysis

### Current Architecture (Single Thread)

```
Checkpoint after 1 year (365 days × 50 msgs/day = 18,250 messages):
- Resume: Load 18,250 messages → ~9 seconds
- Token cost: ~1,000 (SummarizationMiddleware handles this)
```

### Progressive Disclosure Architecture (Thread Per Day)

```
Current day checkpoint:
- Resume: Load 50-100 messages → ~100ms ✅
- Token cost: ~1,000 ✅

User asks "What did we work on yesterday?":
- Agent: history_load("2026-02-17") → Load 50-100 messages → ~5,000 tokens ⚠️
- BUT: Only when user explicitly asks about old context ✅

User asks "What did we decide about tech stack?":
- Agent: Searches memory (already indexed) → ~200 tokens ✅
- OR: history_search("tech stack") → ~100 tokens ✅
- Only loads checkpoint if memory insufficient ✅
```

**Result:** Most queries use memory (~200 tokens), occasional checkpoint load (~5,000 tokens) when needed.

---

## Critical Feasibility Constraints

| Constraint | Status | Notes |
|------------|--------|-------|
| **Multiple checkpoints** | ✅ Supported | One per thread_id |
| **List checkpoints** | ✅ Supported | With filtering by thread_id |
| **Get specific checkpoint** | ✅ Supported | By thread_id + checkpoint_id |
| **Partial checkpoint load** | ❌ Not supported | All-or-nothing per thread |
| **Message filtering** | ❌ Not supported | Can't load last N messages |
| **Lazy loading** | ❌ Not supported | Must load full checkpoint |

---

## Recommended Implementation

### Option A: Daily Threads (Simple, Feasible)

```python
# 1. Thread ID generation
def get_thread_id(user_id: str) -> str:
    return f"{user_id}-{datetime.now().strftime('%Y-%m-%d')}"

# 2. Thread metadata tracking
async def track_thread(user_id: str, thread_id: str, messages: list):
    await db.execute("""
        INSERT INTO thread_metadata (user_id, thread_id, date, message_count, title)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (thread_id) DO UPDATE SET
            message_count = $4,
            last_message_at = NOW()
    """, (user_id, thread_id, datetime.now().date(), len(messages), generate_title(messages)))

# 3. Progressive disclosure tools
@tool
def history_list(days: int = 7) -> str:
    """List recent conversations."""
    ...

@tool
def history_load(date: str) -> str:
    """Load conversation from specific date."""
    ...

# 4. System prompt update
system_prompt = f"""
You have access to past conversations via progressive disclosure:
- history_list(days) → See available dates
- history_load(date) → Load full conversation from that date
- history_search(query) → Search across conversations

Recent context (today) is automatically available.
For older conversations, use history_list() first, then history_load() if needed.
"""
```

---

## Conclusion

**Progressive disclosure on checkpoints IS feasible**, but:

1. ✅ **Must use separate thread_ids** (one per day/week/month)
2. ✅ **Loading is all-or-nothing per thread** (can't partially load)
3. ✅ **Progressive disclosure via multiple checkpoints** (not within single checkpoint)
4. ❌ **Cannot filter messages within checkpoint** (must load entire state)

**This matches Option A** (Daily Checkpoints + Progressive Disclosure Tools).

**The implementation is straightforward** and uses standard LangGraph checkpoint APIs.

---

## References

- LangGraph Checkpoint API: `langgraph/checkpoint/base/__init__.py`
- PostgresSaver Implementation: `langgraph/checkpoint/postgres/__init__.py`
- Pregel (Agent) Checkpoint Usage: `langgraph/pregel/main.py`
- Database Schema: `checkpoints` and `checkpoint_blobs` tables
