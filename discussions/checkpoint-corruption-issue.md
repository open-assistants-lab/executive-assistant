# LangGraph Checkpoint Corruption - Review & Remediation Plan

**Status:** Implemented (2025-01-16)
**First Observed:** 2025-01-15
**Affects:** Telegram channel, ReAct agent with tool calls

## Summary
Checkpoint corruption occurs when an AI message with `tool_calls` is persisted without the required follow-up `ToolMessage` responses. On the next request, OpenAI rejects the message history with a 400 error. Current mitigations reduce frequency but do not eliminate the core window where partial state can be saved.

## Symptoms
- OpenAI 400 errors: "An assistant message with 'tool_calls' must be followed by tool messages"
- Similar tool-calling validation errors can occur on Anthropic and other providers
- Automatic conversation resets
- Lost context for the user

## Root Cause
LangGraph checkpoints after each node execution. When the agent node returns an `AIMessage` with `tool_calls`, that partial state can be persisted before tool execution completes. Any interruption in the window between:

1) Agent node returns `AIMessage(tool_calls=[...])`
2) Tools node emits `ToolMessage` responses

leaves a checkpoint in an invalid state.

Additional risk factors:
- Process crash/restart between agent and tools
- Exceptions in tool execution before `ToolMessage` is emitted
- Concurrent handling of multiple messages for the same thread

## Implementation (2025-01-16)

### Step 1: SanitizingCheckpointSaver Wrapper
**File:** `src/cassey/storage/checkpoint.py`

Added `SanitizingCheckpointSaver` class that wraps the base checkpointer and automatically sanitizes checkpoints on load:
- Detects orphaned `tool_calls` in `AIMessage`
- Removes only corrupted messages, preserves valid ones
- Applied by default via `get_async_checkpointer(sanitize=True)`

**Flow:**
```
Old: Detect corruption → Delete entire checkpoint (hard reset)
New: Detect corruption → Sanitize (remove only corrupted messages) → Continue
     If sanitization fails → Then reset
```

### Step 2: Telegram Channel Error Handling
**File:** `src/cassey/channels/telegram.py`

Changes:
- **Per-thread locks**: Added `_thread_locks` dict with `_get_thread_lock()` method to serialize concurrent messages per thread
- **Targeted resets**: Changed from "reset on any error" to "reset only on corruption errors"
- New `_is_corruption_error()` helper to detect tool-call related errors
- Removed aggressive startup cleanup and pre-check (now handled by wrapper)

### Step 3: Data Migration
**Files:** `src/cassey/config/settings.py`, `src/cassey/storage/*.py`, `scripts/migrate_data.py`

Consolidated per-thread data structure:
```
data/
  users/{thread_id}/
    files/
    db/main.db
    kb/main.db
```

With backward compatibility fallback to old paths.

## Expected Outcome
- No more OpenAI 400s from orphaned tool_calls
- Fewer hard resets; state preserved for most errors
- Reduced user-facing disruptions even under crashes or timeouts

---

## Reviewer Observations (2025-01-15)

### Code Review Findings

**Existing utilities in `checkpoint_utils.py` are solid:**

The file contains three well-implemented functions:

1. `detect_corrupted_messages()` - Scans message list for orphaned tool_calls
2. `sanitize_corrupted_messages()` - Removes only corrupted messages, preserves valid ones
3. `validate_and_recover_checkpoint()` - Main entry point for detection + recovery

**Critical Gap - Sanitization Not Wired:**

Current code in `telegram.py`:
- ✅ Imports `detect_corrupted_messages` (lines 84, 501)
- ✅ Uses it for startup cleanup (`_cleanup_corrupted_checkpoints`)
- ✅ Uses it for pre-check (`_check_checkpoint_corruption`)
- ❌ **Never calls `validate_and_recover_checkpoint()`**
- ❌ **Never calls `sanitize_corrupted_messages()`**

**Current Flow:**
```
Detect corruption → Delete entire checkpoint (hard reset)
```

**What It Should Be:**
```
Detect corruption → Sanitize (remove only corrupted messages) → Continue
If sanitization fails → Then reset
```

### Impact

**Current behavior loses:**
- All valid conversation history when corruption is detected
- User context on non-corruption errors (reset-on-any-error)

**Proposed change preserves:**
- Valid messages before/after the corrupted section
- Conversation continuity for transient errors

### Recommended First Step

**Step 1 (Highest Value/Lowest Risk):** Wire `validate_and_recover_checkpoint()` before `stream_agent_response()`.

```python
# In telegram.py handle_message():
from cassey.agent.checkpoint_utils import validate_and_recover_checkpoint

# Load checkpoint state
state = await load_checkpoint_state(thread_id)

# Sanitize before processing
sanitized_state, actions = await validate_and_recover_checkpoint(state)

if "Could not auto-recover" in actions:
    # Only then clear checkpoint
    await self._clear_checkpoint(thread_id)
else:
    # Continue with sanitized state
    await self.stream_agent_response(message_with_sanitized_state)
```

This single change would:
- Prevent most 400 errors from reaching OpenAI
- Preserve valid conversation context
- Maintain user experience without hard resets

## Proposed Solutions

### Short-Term (low risk)
1) **Sanitize on load before calling the model**
   - Use `validate_and_recover_checkpoint()` to remove orphaned tool_calls or inject placeholder ToolMessages.
   - If sanitization succeeds, continue without user-visible reset.
   - If it fails, fall back to reset.

2) **Targeted reset instead of reset-on-any-error**
   - Only clear checkpoints on tool-call mismatch errors or failed sanitization.
   - Preserve state for transient send/network errors.

3) **Per-thread message lock**
   - Serialize handling per `thread_id` to prevent interleaving tool calls.
   - Keep a small in-memory lock map with TTL to avoid leaks.

### Medium-Term (structural fixes)
4) **Resume pending tool_calls on reload**
   - If a checkpoint has `tool_calls` without responses, re-run those tool calls.
   - Restrict to idempotent tools; require confirmation for side-effect tools.

5) **Safe checkpoint boundary**
   - Persist checkpoints only after tool responses exist (agent+tools as a single node), or
   - Use a custom saver that skips saving states with unresponded tool_calls.

6) **Write-ahead marker**
   - Record "pending tool_calls" separately. On reload, either complete or discard them explicitly.

## Recommended Path
1) Wire `validate_and_recover_checkpoint()` into the request flow and stop resetting on any error.
2) Add per-thread lock for Telegram to avoid concurrent tool-call interleaving.
3) Consider safe checkpoint boundaries or pending tool-call replay as a follow-up.

## Detailed Fix Path (Concrete Steps)

### Step 1: Sanitize before OpenAI call (no reset unless needed)
**Goal:** Prevent 400 errors without discarding state.

Implementation outline:
- In Telegram (or BaseChannel), replace `_check_checkpoint_corruption()` with a **sanitize-first** flow:
  1) Load checkpoint via `checkpointer.aget_tuple(config)`.
  2) Run `validate_and_recover_checkpoint(state)`.
  3) If sanitized, continue; if not salvageable, reset.
- **Important:** Sanitization must be applied to what the agent actually uses:
  - Option A (preferred): wrap `checkpointer.get/aget` to sanitize on load so LangGraph sees the cleaned state.
  - Option B: persist the sanitized state back into the checkpoint before calling the agent.

Where to integrate:
- `src/cassey/channels/telegram.py` before `stream_agent_response()`.
- Or in `BaseChannel.stream_agent_response()` as a channel-agnostic hook.

### Step 2: Stop reset-on-any-error
**Goal:** Avoid losing context for transient or unrelated errors.

Implementation outline:
- Only clear checkpoints on:
  - Tool-call mismatch errors (OpenAI 400 with missing tool_call_ids), or
  - Sanitization failure (cannot recover a valid message sequence).
- Keep existing markdown fallbacks and network errors from triggering a reset.
- Prefer provider-agnostic validation of message history (local check) over error-string matching.

Where to change:
- `src/cassey/channels/telegram.py` in the `except` path of `handle_message()`.

### Step 3: Add per-thread message lock
**Goal:** Prevent concurrent message handling from interleaving tool calls.

Implementation outline:
- Maintain a `dict[thread_id, asyncio.Lock]` in the channel.
- Wrap `handle_message()` body in `async with lock`.
- Use TTL or weakref cleanup to avoid leak.
- Note: in multi-process deployments, use a distributed lock or a per-thread queue instead.

Where to change:
- `src/cassey/channels/telegram.py` (or in `BaseChannel` for all channels).

### Step 4 (Optional): Safe checkpoint saver guard
**Goal:** Avoid saving invalid checkpoints at the source.

Implementation outline:
- Wrap the checkpointer `put()` to **skip saving** if the last AIMessage has `tool_calls`
  without corresponding ToolMessages.
- This preserves earlier valid checkpoints and eliminates the corruption window.
- Trade-off: the tool-call request may be lost after a crash; decide if correctness > continuity.

Where to change:
- `src/cassey/storage/checkpoint.py` (wrap `AsyncPostgresSaver`).

### Step 5 (Optional): Replay pending tool calls
**Goal:** Complete partial state instead of dropping it.

Implementation outline:
- If a checkpoint has tool_calls without ToolMessages, re-run those tools on load.
- Only allow idempotent tools; require confirmation for side-effect tools.

Where to change:
- `src/cassey/agent/checkpoint_utils.py` plus a small dispatcher in channel or agent startup.

## Expected Outcome
- No more OpenAI 400s from orphaned tool_calls.
- Fewer hard resets; state preserved for most errors.
- Reduced user-facing disruptions even under crashes or timeouts.

## Verification Plan
- Force crash after agent tool_calls and confirm sanitization prevents 400 errors.
- Simulate concurrent messages in the same thread and verify no orphaned tool_calls.
- Ensure tool-call mismatch no longer triggers full context loss by default.

## Related Files
- `src/cassey/agent/nodes.py`
- `src/cassey/agent/graph.py`
- `src/cassey/agent/checkpoint_utils.py`
- `src/cassey/channels/telegram.py`
- `src/cassey/storage/checkpoint.py`
