# System Patterns (Agent Self-Improvement)

Description: Meta-patterns for how the agent learns, adapts, and improves over time

Tags: core, system, meta, learning, evolution

---

## Overview

Unlike user-facing patterns in `common_patterns.md`, these patterns describe **how the agent itself works** and improves over time.

These patterns are **not direct workflows** but architectural principles that guide:
- How the agent learns from interactions
- How it adapts to user preferences
- How it optimizes its own behavior
- How it manages computational resources

---

## Pattern 1: Observer → Evolve (Learning Loop)

### Concept

The agent continuously learns from interactions by observing patterns and evolving its behavior.

```
┌─────────────────────────────────────────────────────────────┐
│                    Observer → Evolve Pipeline                 │
│                                                               │
│  Interactions → Observer → Memory → Rollups → Evolve → Skills│
│       │           │          │         │        │         │
│   User acts   Tracks    Stores   Summarizes  Promotes  Auto  │
│               patterns   raw      time-     stable   rules  │
│                         data     tiers    patterns        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### How It Works

**1. Observe** (Real-time)
```python
# Agent tracks patterns during conversations
observations = [
    "User said 'add X' 10 times, 9x meant 'add to todos'",
    "User prefers concise responses (detected in 80% of interactions)",
    "User timezone: Australia/Sydney (from 50 confirmations)"
]
```

**2. Store in Memory** (Raw)
```python
create_memory(
    content="User said: 'add milk' → created todo (not reminder)",
    memory_type="pattern",
    key="add_intent_todo"
)
```

**3. Rollup** (Time-based aggregation)
- **4h rollups**: Recent patterns ("User in 'todo mode' last 4 hours")
- **Daily rollups**: Daily patterns ("User adds 5-10 todos/day on weekdays")
- **Weekly rollups**: Stable patterns ("User always prefers todos over reminders for 'add X'")
- **Monthly rollups**: Long-term traits ("User is task-oriented, uses todos daily")

**4. Evolve** (Pattern promotion)
```python
# When confidence > 85%, promote to user prompt
if weekly_rollup.confidence > 0.85:
    user_prompt = f"When user says 'add X', default to todos (confidence: {weekly_rollup.confidence})"
    # Save to user's custom prompt
```

**5. Apply** (Automatic personalization)
```python
# Future conversations start with:
# "User eddy@telegram: Prefers todos over reminders when saying 'add X'"
```

### Examples

**Learning User's Communication Style:**
```
Observation: User says "add X" → Agent interprets as reminder
Correction: User says "no, just on my todo"
Pattern detected: "add X" for this user = todos (not reminders)
Confidence: Increases each time this pattern repeats
```

**Learning User's Preferences:**
```
Observation: User consistently chooses concise responses
Rollup (weekly): "User prefers concise (95% of responses)"
Evolve: Add to user profile: "Response style: concise"
Result: Agent automatically adapts response length
```

### Time-Tiers Benefits

| Tier | Purpose | Example | Retention |
|------|---------|---------|-----------|
| **Raw** | Immediate context | "User just said 'add milk'" | 14-30 days |
| **4h** | Recent patterns | "User in task-mode (added 5 todos)" | 90 days |
| **Daily** | Daily habits | "User adds todos Mon-Fri mornings" | 1 year |
| **Weekly** | Stable patterns | "User prefers todos > reminders" | Permanent |
| **Monthly** | Core traits | "User is task-oriented, organized" | Permanent |

### Implementation Status

**✅ Implemented:**
- `create_memory`, `search_memories` - Store observations
- `get_memory_by_key` - Retrieve specific patterns

**🚧 Planned (see `/features/memory_time_tiers_plan.md`):**
- Memory rollups table (4h/daily/weekly/monthly)
- Rollup worker (cron job)
- Observer → Evolve pipeline
- User prompt auto-generation

---

## Pattern 2: Token Budget Management

### Concept

Dynamically allocate tokens across middleware features based on budget and priority.

```
Token Budget (e.g., 100K tokens per turn)
│
├─ Context (60K): User messages, conversation history
├─ System Prompt (15K): Skills, instructions
├─ Memory Injection (10K): User preferences, patterns
├─ Tools (10K): Tool definitions, descriptions
└─ Safety Margin (5K): Buffer for unexpected growth
```

### How It Works

**1. Summarization Middleware** (Context reduction)
- Triggers when approaching token limit
- Preserves key information: decisions, outcomes, next steps
- Discards: tool errors, retries, debug logs

**2. Context Editing Middleware** (Tool use reduction)
- Removes redundant tool calls from history
- Keeps: unique tool use patterns
- Discards: repeated failed attempts

**3. Memory Prioritization**
- Inject high-confidence memories first
- Skip low-confidence observations
- Time-tiered retrieval (recent > stable)

---

## Pattern 3: Middleware Stack Order

### Concept

Middleware execution order matters - earlier middleware affects later ones.

```
┌─────────────────────────────────────────────┐
│  Middleware Stack (Execution Order)          │
│                                              │
│  1. ThreadContextMiddleware                 │
│     → Propagates ContextVars to tools        │
│                                              │
│  2. TodoListMiddleware                      │
│     → Manages agent's internal todos         │
│                                              │
│  3. StatusUpdateMiddleware                  │
│     → Sends real-time progress updates       │
│                                              │
│  4. TodoDisplayMiddleware                   │
│     → Displays agent todos to user           │
│                                              │
│  5. SummarizationMiddleware                 │
│     → Reduces context when needed            │
│                                              │
│  6. ContextEditingMiddleware                │
│     → Removes redundant tool calls           │
└─────────────────────────────────────────────┘
```

### Key Interactions

- **ThreadContextMiddleware MUST be first** → Propagates thread_id to all tools
- **TodoListMiddleware before TodoDisplayMiddleware** → Creates todos before displaying them
- **StatusUpdateMiddleware throughout** → Provides visibility at each step
- **Summarization and ContextEditing last** → Optimize after execution

---

## Pattern 4: Context Propagation

### Concept

Python ContextVars don't automatically propagate across async boundaries.

**Problem:**
```python
# ContextVar set in main thread
thread_id.set("telegram:123")

# Lost in async tool call!
async def some_tool():
    print(get_thread_id())  # None! ❌
```

**Solution: ThreadContextMiddleware**
```python
# Middleware saves and restores context
async def awrap_tool_call(...):
    # Save context before tool
    saved_ctx = get_thread_id()

    # Call tool
    result = await handler(request)

    # Restore context after tool
    set_thread_id(saved_ctx)
    return result
```

---

## When System Patterns Matter

**These patterns help when:**

1. **Agent is confused** → Observer-Evolve learns and adapts
2. **Token limits hit** → Token Budget Management prioritizes what to keep
3. **Context lost in tools** → ThreadContextMiddleware propagates context
4. **Wrong execution order** → Middleware Stack Order fixes it

**User-facing patterns in `common_patterns.md` help when:**

1. **Choosing storage** → Decision tree (TDB vs ADB vs VDB)
2. **Combining tools** → Workflow patterns (Query → Analyze → Report)
3. **Avoiding mistakes** → Anti-patterns

---

## Quick Reference

| Pattern | Purpose | Status |
|---------|---------|--------|
| **Observer → Evolve** | Learn and adapt from interactions | 🚧 Planned |
| **Token Budget** | Manage context size efficiently | ✅ Active |
| **Middleware Stack** | Order of middleware execution | ✅ Active |
| **Context Propagation** | ThreadContextMiddleware | ✅ Active |

---

## See Also

- `common_patterns.md` - User-facing workflow patterns
- `quick_reference.md` - Tool reference
- `decision_tree.md` - Storage decision guide
- `/features/memory_time_tiers_plan.md` - Observer-Evolve implementation
- `/features/` - Architectural documentation
