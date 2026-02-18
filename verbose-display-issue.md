# Verbose Display & Checkpoint Issue

## Current Issue

### Problem Summary
When user sends a simple message like "hello", they see:
1. **Old plan/todos from previous session** - These persist in checkpoint even for new conversations
2. **Combined tool call message format** - Not showing separate messages for thinking (🤔), tool calls (🔧), tool results (✅)

### Root Causes
1. **Checkpoint persistence** - LangGraph checkpoints store the entire agent state (messages, todos, tool calls). When user sends "hello", it loads the old checkpoint which includes old todos from previous sessions.
2. **Thread isolation** - Currently using single `thread_id` per user (e.g., "user-123"), so all conversations share state.
3. **Verbose mode not loading** - `app.display.verbose: true` in config.yaml may not be loading properly into settings.

---

## Checkpoint Design Intent

### How LangGraph Checkpoints Work

```python
# When invoking an agent:
result = await agent.ainvoke(
    {"messages": [HumanMessage("Hello")]},
    config={"configurable": {"thread_id": "user-123"}}
)

# LangGraph internally:
checkpointer.get_tuple(config)
→ Loads checkpoint from Postgres for thread_id "user-123"
→ Returns CheckpointTuple with ALL state (messages, channel_values, etc.)
→ Agent proceeds with full context
```

**Key constraint:** Loading is **all-or-nothing** per thread_id.

### Database Schema

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

CREATE TABLE checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    idx INTEGER NOT NULL,
    value JSONB NOT NULL,
    version TEXT NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, channel, idx)
);
```

### What's Stored in Checkpoints

The checkpoint JSONB contains:
- `channel_values` - Includes `messages` array, `todos` array, `agent_outcome`, etc.
- `channels` - Internal LangGraph state
- `pending_writes` - Tool outputs awaiting commit

This is why old todos persist - they're stored in the checkpoint's `channel_values.todos`.

---

## Our Needs (Single Thread)

### Current Architecture
- One thread_id per user (e.g., "user-123")
- All conversations share checkpoint state
- No automatic cleanup between sessions

### What We Need

1. **Clean slate for each conversation**
   - When user starts a new conversation, no old todos should appear
   - Current: Old todos load from checkpoint
   - Need: Either clear checkpoint or use fresh thread_id

2. **Verbose display mode**
   - Show thinking (🤔) as separate message
   - Show tool call (🔧) with args as separate message  
   - Show tool result (✅) as separate message
   - Config: `app.display.verbose: true` in config.yaml

3. **Proper config loading**
   - `app.display.verbose: true` should enable verbose mode
   - Need to verify config flows from config.yaml → settings → bot

### Why Single Thread is Problematic

With single thread_id per user:
```
User: "hello" (Feb 17)
→ Creates checkpoint with messages + todos

User: "hello" (Feb 18)  
→ Loads checkpoint from Feb 17
→ Sees old todos from previous day
```

The checkpoint contains ALL state from previous sessions.

---

## Solutions

### Option 1: Clear Checkpoint Between Sessions (Quick Fix)
```python
# Before processing new message, clear old checkpoint
checkpointer.delete(config)  # Delete old checkpoint
```

### Option 2: Use Thread-Per-Day (Design Intent)
```python
# Day 1: thread_id = "user-123-2026-02-17"
# Day 2: thread_id = "user-123-2026-02-18"
# Each day is separate, no cross-contamination
```

### Option 3: Checkpoint Cleanup Middleware
- Already exists: `checkpoint_cleanup` middleware
- Currently enabled, but may not be clearing todos

---

## Next Steps

1. **Clear checkpoint data** - Delete all rows from `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` for test user
2. **Verify config loading** - Add logging to confirm `display.verbose` loads properly
3. **Test verbose display** - Send message and verify separate messages appear
4. **Consider thread-per-day** - If single-thread issue persists, implement proper isolation
