# Verdict: CheckpointCleanupMiddleware

## Executive Summary

**Recommendation: Deprecate and remove CheckpointCleanupMiddleware in favor of pagination-based architecture.**

---

## Background

The `CheckpointCleanupMiddleware` was created to solve checkpoint bloat after the deepagents `SummarizationMiddleware` summarizes conversation history. However, after analyzing deepagents internals (v0.4.1), the middleware is fundamentally flawed and over-engineered.

---

## DeepAgents Architecture Analysis

### What SummarizationMiddleware Actually Does

The deepagents `SummarizationMiddleware`:

1. **Does NOT modify checkpoint** - Only modifies messages sent to LLM
2. **Persists full history** to backend file: `/conversation_history/{thread_id}.md`
3. **Tracks summarization** via `_summarization_event` in state
4. **Uses `_get_effective_messages()`** to reconstruct: `[summary_message] + messages[cutoff_index:]`

### The "Bloat" Is By Design

The checkpoint containing all messages is intentional in deepagents. The middleware reduces:
- ✅ Token usage on LLM calls (what matters)
- ❌ Checkpoint size (not their concern)

---

## Why CheckpointCleanupMiddleware Fails

### 1. Timing Issues

- `after_agent` runs after agent completes, but before state is committed
- `_summarization_event` may not be visible in state at this point
- The `Command(update={...})` return may not apply to checkpoint

### 2. Coupling to DeepAgents Internals

- Depends on `_summarization_event` structure (can change)
- Depends on specific middleware execution order
- Hooks into internal deepagents behavior

### 3. Over-Engineering

- Solves a problem that has a simpler solution (pagination)
- Fragile - breaks when deepagents updates
- Hard to debug - relies on timing/ordering

---

## Real Impact of Checkpoint Growth

LangGraph uses **incremental checkpointing** (like Git):
- Not exponential growth - stores diffs
- Linear growth: each message = new diff entry
- Main issue: **resume time**, not storage size

| Messages | Resume Impact |
|----------|---------------|
| 100 | Fast |
| 1,000 | Noticeable lag |
| 10,000 | Very slow |

---

## Conclusion

CheckpointCleanupMiddleware should be **deprecated and removed** because:

1. ❌ **Fragile** - depends on deepagents internals
2. ❌ **Buggy** - timing/state visibility issues
3. ❌ **Over-engineered** - simpler solution exists
4. ❌ **High maintenance** - breaks on deepagents updates

### Alternative: Pagination Architecture

The proper solution is to switch threads periodically:
- Keep each checkpoint chain short (e.g., 500 messages)
- Store full history externally (your own DB)
- Switch thread when threshold reached

See: `pagination-external-history.md`

---

## If We Want to Improve CheckpointCleanupMiddleware

### Root Cause of Failure

The current implementation uses `after_agent` hook, which runs AFTER the agent completes but BEFORE the state is committed to the checkpoint. At this point:
- `_summarization_event` may not be visible in state
- The `Command(update={...})` return is not reliably applied

### Recommended Fix: Use `wrap_model_call` Pattern

Instead of `after_agent`, the middleware should use the same pattern as deepagents `SummarizationMiddleware` - intercept the model call and return an `ExtendedModelResponse` with state updates:

```python
from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.summarization import ExtendedModelResponse

class ImprovedCheckpointCleanupMiddleware(AgentMiddleware):
    """Clean up checkpoint by removing summarized messages."""
    
    def wrap_model_call(self, request, handler):
        # Get state from request
        state = request.state
        summarization_event = state.get("_summarization_event")
        
        if summarization_event is None:
            return handler(request)
        
        # Same cleanup logic as current after_agent
        cutoff_index = summarization_event.get("cutoff_index")
        messages = state.get("messages", [])
        
        if cutoff_index and cutoff_index < len(messages):
            cleaned_messages = self._clean_messages(messages, cutoff_index)
            
            # Return ExtendedModelResponse with state update
            return ExtendedModelResponse(
                model_response=handler(request),  # Original response
                command=Command(update={"messages": cleaned_messages})
            )
        
        return handler(request)
```

### Alternative: Use LangGraph's StateModifier

LangGraph supports state modifiers that run before checkpoint:

```python
from langgraph.checkpoint.base import BaseCheckpointSaver

class CheckpointWithTruncation(BaseCheckpointSaver):
    """Wrapper that truncates state before saving."""
    
    def put(self, config, checkpoint, metadata, new_version):
        # Truncate messages before saving
        checkpoint = self._truncate_messages(checkpoint)
        return super().put(config, checkpoint, metadata, new_version)
```

### Best Fix: Move to Application Layer

Instead of middleware, handle at application level:

```python
# After each agent invoke, manually manage state
async def invoke_agent(agent, input_data, thread_id):
    result = await agent.ainvoke(input_data, config={"thread_id": thread_id})
    
    # Check message count, archive if needed
    message_count = len(result.get("messages", []))
    if message_count > THRESHOLD:
        # Archive current thread, start new
        await archive_thread(thread_id)
        thread_id = create_new_thread()
    
    return result, thread_id
```

---

## Recommendation

| Approach | Effort | Reliability | Maintainability |
|----------|--------|-------------|-----------------|
| Fix middleware | Medium | Medium | Low |
| StateModifier | Low | Unknown | Medium |
| Application layer | Low | High | High |

**Best choice**: Fix at application layer (last option) - simplest, most reliable, no deepagents coupling.

If fixing middleware is required, use `wrap_model_call` pattern (first option) - consistent with deepagents architecture.

---

## Action Items

### Option A: Remove (Recommended)
1. [ ] Disable CheckpointCleanupMiddleware in config
2. [ ] Implement thread pagination logic (see pagination-external-history.md)
3. [ ] Store summaries in external DB for context
4. [ ] Remove CheckpointCleanupMiddleware code

### Option B: Fix
1. [ ] Refactor to use `wrap_model_call` pattern
2. [ ] Add debug logging for state visibility
3. [ ] Test with actual summarization
4. [ ] Verify Command(update={...}) applies correctly

---

## References

- DeepAgents v0.4.1: `deepagents/middleware/summarization.py`
- LangGraph checkpointing: Official LangGraph documentation
