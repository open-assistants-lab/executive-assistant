# Streaming & Context Issues Investigation

**Date:** 2025-01-20
**Status:** 🔍 Root causes identified, fixes proposed

---

## Issues Found

### 1. Messages Batched (Not Real-Time Streaming)

**Symptom:** User receives all messages in one batch after 144s, not progressively.

**Root Cause:** `src/executive_assistant/channels/base.py` accumulates all messages before sending:

```python
# Line 367-398 in stream_agent_response()
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        messages.append(msg)  # ← Accumulating, not sending!
return messages  # ← Only returns AFTER agent finishes

# Line 206-208 in handle_message()
for msg in messages:  # ← Sends everything at once
    await self.send_message(message.conversation_id, msg.content)
```

**Problem:** The streaming is fake - it waits for full agent completion, then sends all messages.

**Fix:** Send messages immediately as they arrive:

```python
# In handle_message(), change to:
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        if msg.content:
            await self.send_message(message.conversation_id, msg.content)
```

---

### 2. Todo List Only Shows at End

**Symptom:** Todo list appears with final answer, not during execution.

**Root Cause:** TodoDisplayMiddleware.aafter_model() can't find `state["todos"]` when write_todos is called.

**Analysis:**
- write_todos tool returns: `Command(update={"todos": [...]})`
- This Command is applied AFTER middleware hooks run
- TodoDisplayMiddleware.aafter_model() checks: `if "todos" in state`
- But todos aren't in state yet when hook runs!

**Evidence from logs:**
```
10:51:48 - write_todos called
10:51:50 - TodoDisplayMiddleware.after_model: None (no todos found)
...
10:54:00 - TodoDisplayMiddleware.after_agent: "Sending todo list" (found!)
```

**Possible Fixes:**

**Option A:** Detect write_todos tool call directly (don't wait for state update):

```python
async def aafter_model(self, state, runtime):
    last_ai_msg = next((msg for msg in reversed(state["messages"])
                        if isinstance(msg, AIMessage)), None)

    if last_ai_msg and last_ai_msg.tool_calls:
        write_todos_calls = [tc for tc in last_ai_msg.tool_calls
                             if tc.get("name") == "write_todos"]
        if write_todos_calls:
            # Extract todos from tool call args
            todos = write_todos_calls[0].get("args", {}).get("todos", [])
            await self._send_todo_list(todos)
```

**Option B:** Move TodoDisplayMiddleware to run after state is updated
- Use `awrap_tool_call()` hook instead of `aafter_model()`
- This runs after tool executes AND state updates

**Option C:** Check BOTH tool call AND state

---

### 3. Old Database Context Bleeding In

**Symptom:** For "What time is it?", LLM tries to create database tables repeatedly.

**Root Cause:** LLM is seeing old conversation context about database creation.

**Evidence:**
- Summarization log: "Summarized: 29→28 msgs, 2545→2415 tokens"
- 29 messages in context = previous conversation history
- SummarizationMiddleware triggers at 10,000 tokens
- Current context is 2,545 tokens (below threshold)

**Problem:** Old messages aren't being summarized/aggressively enough.

**Current Configuration:**
```yaml
middleware:
  summarization:
    enabled: true
    max_tokens: 10000      # Trigger summarization at 10k tokens
    target_tokens: 2000    # Target size after summarization
```

**Analysis:**
- 2,545 tokens is well below 10,000 threshold
- LLM sees full 29-message conversation history
- Database creation instructions from old conversation are still visible
- LLM thinks it should continue the database task

**Possible Fixes:**

**Option A:** Lower summarization threshold
```yaml
max_tokens: 3000  # Summarize more aggressively
target_tokens: 1000
```

**Option B:** Clear conversation after task completion
- Add explicit "task complete" marker
- Summarize immediately when task done

**Option C:** Check if there are OTHER summarization mechanisms
- Search codebase for "summarize" or "summary"
- Check if there's a separate summarization system

**Option D:** Improve system prompt clarity
- Add: "Each request is independent. Don't continue previous tasks unless explicitly asked."

---

## Investigation Needed

### 1. Are There Other Summarization Systems?

Search for:
- `SummarizeMiddleware` (different from `SummarizationMiddleware`)
- Custom summarization in `src/executive_assistant/agent/summary_extractor.py`
- Manual summarization calls

### 2. Check Checkpointer Behavior

- Does Postgres checkpointer keep full history?
- Should we be using `recursion_limit` to limit context window?
- Are there checkpoint config options we're missing?

### 3. Review Token Counting

- Is 2,545 tokens accurate for 29 messages?
- Or is token counting broken?
- Are we including system prompt tokens?

---

## Priority Order

1. **HIGH:** Fix streaming (Issue 1) - affects UX significantly
2. **HIGH:** Fix todo display timing (Issue 2) - core feature not working
3. **MEDIUM:** Investigate context bleeding (Issue 3) - need to understand scope
4. **LOW:** Adjust summarization settings - can be tuned later

---

## Next Steps

1. Fix streaming in `base.py` to send messages immediately
2. Fix todo display to read from tool_call args instead of state
3. Search for other summarization mechanisms
4. Test with clean conversation to confirm context issue
5. Adjust summarization thresholds if needed
