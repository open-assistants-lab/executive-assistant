# Streaming & Todo Display Fixes

**Date:** 2025-01-20
**Status:** 🔧 Implementation in progress

---

## Issue 1: Messages Batched (Not Streaming)

### Problem
All messages arrive in one batch after agent completes, not progressively as generated.

### Root Cause
`src/cassey/channels/base.py` accumulates all messages before sending:

```python
# Line 367-398
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        messages.append(msg)  # ← Accumulating
return messages  # ← Only returns AFTER agent finishes

# Line 206-208
for msg in messages:  # ← Sends everything at once
    await self.send_message(message.conversation_id, msg.content)
```

### Solution
Send messages immediately as they arrive:

```python
# In handle_message()
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        if hasattr(msg, 'content') and msg.content:
            await self.send_message(message.conversation_id, msg.content)
```

**Note:** This requires refactoring `stream_agent_response()` to yield messages instead of accumulating them.

---

## Issue 2: Todo List Only Shows at End

### Problem
Todo list appears with final answer, not during execution.

### Root Cause
`src/cassey/agent/todo_display.py` checks `state["todos"]` in `aafter_model()`, but the state update from `write_todos` hasn't been applied yet when the hook runs.

**Timeline:**
1. LLM calls `write_todos([{"content": "Understand", ...}])`
2. `write_todos` returns `Command(update={"todos": [...]})`
3. `TodoDisplayMiddleware.aafter_model()` runs → checks `state["todos"]` → NOT FOUND (state not updated yet)
4. `aafter_agent()` runs → state NOW has todos → sends todo list (too late!)

### Solution
Read todos directly from the tool call arguments:

```python
async def aafter_model(self, state, runtime):
    messages = state.get("messages", [])
    last_ai_msg = next((msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None)

    if last_ai_msg and last_ai_msg.tool_calls:
        # Find write_todos call
        write_todos_calls = [
            tc for tc in last_ai_msg.tool_calls
            if tc.get("name") == "write_todos"
        ]
        if write_todos_calls:
            # Extract todos from tool call args (don't wait for state update)
            todos = write_todos_calls[0].get("args", {}).get("todos", [])
            if todos:
                await self._send_todo_list(todos)

    return None
```

---

## Implementation Plan

### Fix 1: Streaming
**File:** `src/cassey/channels/base.py`

1. Remove `messages` list accumulation
2. Send immediately in the loop
3. Update `handle_message()` to use new pattern
4. Keep message logging for audit

### Fix 2: Todo Display
**File:** `src/cassey/agent/todo_display.py`

1. Read from `tool_call["args"]` instead of `state["todos"]`
2. Keep fallback to `state["todos"]` for `aafter_agent()`
3. Test that todos appear during execution, not at end

---

## Testing

### Test Streaming:
```
User: "What time is it?"

Expected (progressive):
[Thinking...]
[Tool 1: write_todos]
[✅ write_todos (0.1s)]
[Tool 2: get_current_time]
[✅ get_current_time (0.5s)]
[📋 Tasks (2/2): ✅ Understand request, ✅ Get current time]
"The current time is..."
```

### Test Todo Display:
```
User: "Plan my week"

Expected (during execution):
📋 Tasks (0/4): ⏳ Check calendar
[Working...]
📋 Tasks (1/4): ✅ Check calendar, ⏳ Get deadlines
[Working...]
📋 Tasks (2/4): ✅ Check calendar, ✅ Get deadlines, ⏳ Identify priorities
```

---

## Priority

1. **HIGH:** Fix todo display (blocks core feature)
2. **HIGH:** Fix streaming (major UX improvement)

Both fixes should be implemented together for best user experience.
