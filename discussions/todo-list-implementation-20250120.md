# Todo List Display Implementation

**Date:** 2025-01-20
**Status:** ✅ Implemented and deployed
**Related:** LangChain's native TodoListMiddleware + custom TodoDisplayMiddleware

---

## Overview

Cassey now displays her internal todo list to users in real-time, showing planned tasks and progress as she works. This uses **two complementary middlewares**:

1. **TodoListMiddleware** (LangChain native) - Adds `write_todos` tool and manages state
2. **TodoDisplayMiddleware** (custom) - Displays todos via status updates

---

## Architecture

### Component Interaction Flow

```
User Message
    ↓
Agent starts (abefore_agent)
    ↓
[StatusUpdateMiddleware] → "🤔 Thinking..."
    ↓
[TodoListMiddleware] → Injects system prompt about write_todos
    ↓
[TodoListMiddleware] → Adds write_todos tool to available tools
    ↓
LLM decides whether to create todos
    ↓
┌─────────────────────────────────────┐
│ IF multi-step task (3+ steps):        │
│   LLM calls: write_todos([...])      │
│ ELSE:                                 │
│   Skip todos, do task directly       │
└─────────────────────────────────────┘
    ↓
[TodoDisplayMiddleware.aafter_model] → Detects write_todos call
    ↓
[TodoDisplayMiddleware] → Formats todos: "📋 Tasks (1/5): ⏳ Task 1..."
    ↓
[StatusUpdateMiddleware] → Sends status update to Telegram
    ↓
Agent executes tools
    ↓
LLM updates todos: write_todos([...updated...])
    ↓
[TodoDisplayMiddleware] → Detects change, sends updated status
    ↓
[StatusUpdateMiddleware] → Edits previous status message
    ↓
Agent completes
    ↓
[TodoDisplayMiddleware.aafter_agent] → Final todo list state
```

---

## Middleware 1: TodoListMiddleware (LangChain Native)

**Source:** `langchain.agents.middleware.todo`

**Purpose:** Adds todo list planning capability to the agent

### What It Does

1. **Adds `write_todos` tool** to agent's available tools
2. **Injects system prompt** explaining when/how to use todos
3. **Adds `todos` field** to agent state (PlanningState)
4. **Validates** only one `write_todos` call per model turn

### The `write_todos` Tool

```python
@tool
def write_todos(todos: list[Todo]) -> Command:
    """
    Create and manage a structured task list for your current work session.

    Args:
        todos: List of Todo items with content and status

    Todo item structure:
        {
            "content": "Check calendar for this week",
            "status": "pending"  # "pending" | "in_progress" | "completed"
        }
    """
    return Command(update={"todos": todos, ...})
```

### System Prompt Injection

TodoListMiddleware automatically adds this to the system prompt:

```
## `write_todos`

You have access to the `write_todos` tool to help you manage and plan complex objectives.
Use this tool for complex objectives to ensure that you are tracking each necessary step
and giving the user visibility into your progress.

[... detailed usage instructions ...]
```

### State Schema

```python
class PlanningState(AgentState):
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput]
```

Our `AgentState` now includes:
```python
class AgentState(TypedDict):
    messages: ...
    todos: NotRequired[list[Todo]]  # Added from PlanningState
    ...
```

---

## Middleware 2: TodoDisplayMiddleware (Custom)

**Source:** `src/cassey/agent/todo_display.py`

**Purpose:** Displays the agent's todo list to users via status updates

### What It Does

1. **Monitors state** for changes to `todos` field
2. **Formats todos** for display (with status indicators)
3. **Sends status updates** via channel's `send_status()` method
4. **Rate limits** updates to avoid spam
5. **Handles channel capabilities** (graceful fallback if no status support)

### Key Methods

#### `abefore_agent(state, runtime)`
```python
# Initialize tracking
self.last_todos = []
self.current_conversation_id = get_thread_id()

# Show existing todos if this is a resumed conversation
if "todos" in state:
    await self._send_todo_list(state["todos"])
```

#### `aafter_model(state, runtime)`
```python
# Check if write_todos was called in this model turn
messages = state["messages"]
last_ai_msg = last AIMessage in reversed(messages)

if last_ai_msg has write_todos tool call:
    if "todos" in state:
        await self._send_todo_list(state["todos"])
```

#### `aafter_agent(state, runtime)`
```python
# Send final todo list state
if "todos" in state:
    await self._send_todo_list(state["todos"])
```

### Formatting

**Standard format** (default):
```
📋 Tasks (2/5 complete):
  ✅ Check calendar for this week
  ⏳ Get all pending tasks from database
  ⏳ Identify high-priority items
  ⏳ Create daily schedule
  ⏳ Format as markdown
```

**Progress bar format** (optional):
```
📋 Progress: [████░░░░] 40%

⏳ Working on:
  • Get all pending tasks from database
  • Identify high-priority items

⏭ Up next:
  • Create daily schedule
  • Format as markdown
```

---

## How They Work Together

### Scenario 1: First Message (No Todos)

```
User: "Help me plan my week"
```

**Flow**:
1. `StatusUpdateMiddleware.abefore_agent()` → "🤔 Thinking..."
2. `TodoListMiddleware` → Adds write_todos tool, injects prompt
3. LLM sees multi-step task, decides to create todos
4. LLM calls: `write_todos([{"content": "Check calendar", "status": "pending"}, ...])`
5. `TodoListMiddleware` → Validates single call, updates state
6. `TodoDisplayMiddleware.aafter_model()` → Detects `todos` in state
7. `TodoDisplayMiddleware` → Formats and sends: "📋 Tasks (0/5): ⏳ Check calendar..."
8. `StatusUpdateMiddleware` → Sends to Telegram (edits "Thinking..." message)
9. Agent proceeds with tasks

---

### Scenario 2: Updating Todo Status

```
# Agent is working on task 1
```

**Flow**:
1. LLM calls tool: `query_database(...)`
2. `StatusUpdateMiddleware.awrap_tool_call()` → "⚙️ Tool 1: query_database"
3. Tool completes
4. `StatusUpdateMiddleware.awrap_tool_call()` → "✅ query_database (0.5s)"
5. LLM marks task 1 complete: `write_todos([{"content": "Check calendar", "status": "completed"}, {"content": "Get tasks", "status": "in_progress"}, ...])`
6. `TodoDisplayMiddleware.aafter_model()` → Detects todos changed
7. `TodoDisplayMiddleware._todos_changed()` → Returns True (status changed)
8. `TodoDisplayMiddleware._should_send_update()` → Returns True (0.5s passed)
9. `TodoDisplayMiddleware` → Formats: "📋 Tasks (1/5): ✅ Check calendar, ⏳ Get tasks..."
10. `StatusUpdateMiddleware` → Edits previous todo status message

---

### Scenario 3: Rate Limiting

```
# Agent completes tasks quickly (within 0.3s)
```

**Flow**:
1. LLM completes task 1, calls `write_todos([...])`
2. `TodoDisplayMiddleware.aafter_model()` → Wants to send update
3. `TodoDisplayMiddleware._should_send_update()` → Returns False (only 0.3s passed, needs 0.5s)
4. Update is skipped (prevents spam)
5. LLM completes task 2, calls `write_todos([...])`
6. Still within rate limit, update skipped
7. Eventually 0.5s passes, next update is sent

---

## Configuration

### Settings (`config.yaml`)

```yaml
middleware:
  # Todo List Middleware (native)
  todo_list_enabled: true

  # Todo List Display Middleware
  todo_list_display:
    max_display: 10          # Max todos to show
    update_interval: 0.5     # Min seconds between updates
    show_progress_bar: false # Use progress bar format
```

### Environment Variables (`.env`)

```bash
MIDDLEWARE_TODO_LIST_ENABLED=true
MIDDLEWARE_TODO_LIST_MAX_DISPLAY=10
MIDDLEWARE_TODO_LIST_UPDATE_INTERVAL=0.5
MIDDLEWARE_TODO_LIST_SHOW_PROGRESS_BAR=false
```

---

## Files Created/Modified

### Created Files

| File | Purpose |
|------|---------|
| `src/cassey/agent/todo_display.py` | TodoDisplayMiddleware implementation |

### Modified Files

| File | Changes |
|------|---------|
| `src/cassey/agent/state.py` | Added `todos: NotRequired[list[Todo]]` field |
| `src/cassey/config/settings.py` | Added MW_TODO_LIST_* settings |
| `src/cassey/agent/langchain_agent.py` | Integrated TodoDisplayMiddleware |
| `config.yaml` | Added todo_list_display configuration |

---

## Key Design Decisions

### Decision 1: Separate Middlewares

**Why two middlewares instead of one?**

- **Separation of concerns**: TodoListMiddleware handles **logic**, TodoDisplayMiddleware handles **display**
- **Reusability**: TodoListMiddleware can work without TodoDisplayMiddleware (e.g., for logging only)
- **Testing**: Can test each middleware independently
- **LangChain compatibility**: Using native middleware ensures future compatibility

---

### Decision 2: Status-Based Updates

**Why detect write_todos calls instead of polling?**

- **Event-driven**: Updates happen immediately when todos change
- **Efficient**: No need to poll state continuously
- **Accurate**: Updates are synchronized with LLM's todo management

---

### Decision 3: Rate Limiting

**Why limit update frequency?**

- **Prevent spam**: Too many status edits is annoying
- **API limits**: Telegram has rate limits on message edits
- **Performance**: Fewer status sends = faster agent execution

---

### Decision 4: Optional Display

**What if channel doesn't support status updates?**

```python
if hasattr(self.channel, "send_status"):
    await self.channel.send_status(...)
else:
    logger.warning("Channel doesn't support status updates")
```

Graceful degradation - no crashes, just no todo display on unsupported channels.

---

## Example Conversation

### User Request

```
User: Help me plan my week, check my calendar, identify deadlines, and create a schedule
```

### What Happens (Behind Scenes)

1. **Status update**: "🤔 Thinking..."
2. **LLM creates todos**:
   ```python
   write_todos([
     {"content": "Query calendar for this week", "status": "in_progress"},
     {"content": "Get pending deadlines from database", "status": "pending"},
     {"content": "Identify high-priority tasks", "status": "pending"},
     {"content": "Create daily schedule", "status": "pending"}
   ])
   ```
3. **Status update**: "📋 Tasks (0/4): ⏳ Query calendar for this week"
4. **LLM executes**: `query_database(...)` → "⚙️ Tool 1: query_database" → "✅ query_database (0.5s)"
5. **LLM updates todos**:
   ```python
   write_todos([
     {"content": "Query calendar for this week", "status": "completed"},
     {"content": "Get pending deadlines from database", "status": "in_progress"},
     {"content": "Identify high-priority tasks", "status": "pending"},
     {"content": "Create daily schedule", "status": "pending"}
   ])
   ```
6. **Status update**: "📋 Tasks (1/4): ✅ Query calendar for this week, ⏳ Get pending deadlines from database"
7. **LLM executes**: `query_database(...)` → "⚙️ Tool 2: query_database" → "✅ query_database (0.3s)"
8. **Process continues** for remaining tasks...

### Final Result

```
✅ Done in 8.2s

Cassey: Here's your weekly plan...

📋 Tasks (4/4 complete):
  ✅ Query calendar for this week
  ✅ Get pending deadlines from database
  ✅ Identify high-priority tasks
  ✅ Create daily schedule
```

---

## LangChain's Native Todo System

### Todo Schema

```python
class Todo(TypedDict):
    content: str  # Task description
    status: Literal["pending", "in_progress", "completed"]  # Task state
```

### Usage Guidance (from system prompt)

**When to use write_todos**:
1. ✅ Complex multi-step tasks (3+ steps)
2. ✅ Non-trivial tasks requiring planning
3. ✅ User explicitly requests todo list
4. ✅ User provides multiple tasks at once

**When NOT to use**:
1. ❌ Single straightforward task
2. ❌ Trivial tasks (< 3 steps)
3. ❌ Purely conversational requests

**Best practices** (from system prompt):
- Mark task as `in_progress` BEFORE starting
- Mark task as `completed` IMMEDIATELY after finishing
- Don't batch completions (update in real-time)
- Always have at least one task `in_progress` if work remains
- Remove irrelevant tasks, add newly discovered tasks

---

## Testing

### Manual Test Steps

1. **Test simple task** (should NOT show todos):
   ```
   User: "What time is it?"
   Expected: No todo list, direct answer
   ```

2. **Test multi-step task** (should show todos):
   ```
   User: "Plan my week, check calendar, identify deadlines, create schedule"
   Expected: Todo list appears, updates as tasks complete
   ```

3. **Test todo updates**:
   ```
   User: "Help me refactor my codebase"
   Expected: Initial todo list → Status updates as tasks complete → Final state
   ```

4. **Test rate limiting**:
   ```
   User: "Do 5 quick database queries"
   Expected: Not every update triggers status refresh (rate limited)
   ```

### Verification Commands

```bash
# Check Cassey is running
ps aux | grep cassey

# Check logs for middleware loading
tail -100 /tmp/cassey.log | grep -i "todo\|middleware"

# Check tool count (should be 55 now, was 51)
grep "Loaded.*tools" /tmp/cassey.log
```

---

## Benefits

### For Users

1. **Transparency**: See what Cassey is planning to do
2. **Progress tracking**: Know how much is left
3. **Trust building**: Understand Cassey's thought process
4. **Expectation setting**: Know what's coming next

### For Developers

1. **Debugging**: See Cassey's internal planning
2. **Testing**: Verify task execution flow
3. **Optimization**: Identify slow steps
4. **Monitoring**: Track agent behavior patterns

---

## Future Enhancements

### Potential Improvements

1. **Interactive todos**: Allow users to approve/reject todo items
2. **Todo categories**: Group todos by type (research, execution, reporting)
3. **Time estimates**: Show estimated vs actual time per task
4. **Persistent todos**: Save todos across conversations
5. **User preferences**: Allow users to disable todo display
6. **Smart formatting**: Adapt format based on list length

---

## Troubleshooting

### Issue: Todos Not Appearing

**Check**:
1. Is `MW_TODO_LIST_ENABLED=true`?
2. Is `MW_STATUS_UPDATE_ENABLED=true`?
3. Is task complex enough (3+ steps)?
4. Check logs: `grep todo /tmp/cassey.log`

---

### Issue: Todos Not Updating

**Check**:
1. Is LLM calling `write_todos` multiple times? (Check in logs)
2. Rate limit too high? (Check `MW_TODO_LIST_UPDATE_INTERVAL`)
3. Channel supports status edits? (Telegram yes, HTTP no)

---

### Issue: Too Many Status Updates

**Solution**: Increase `MW_TODO_LIST_UPDATE_INTERVAL` to 1.0 or 2.0 seconds

---

## Summary

**What was implemented:**
- ✅ Integrated LangChain's native TodoListMiddleware
- ✅ Created custom TodoDisplayMiddleware for real-time display
- ✅ Added todos field to AgentState
- ✅ Added configuration settings
- ✅ Works with Telegram status updates

**How it works:**
1. TodoListMiddleware gives Cassey the ability to create/manage todos
2. TodoDisplayMiddleware shows those todos to users in real-time
3. Status update mechanism provides the delivery channel
4. Rate limiting prevents spam

**Result:** Users can now see Cassey's planned tasks and track progress as she works, building trust through transparency.

---

**Status:** ✅ Complete and deployed

**Next:** Test with real user requests to verify todo list appears and updates correctly
