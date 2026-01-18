# Telegram /debug Command

**Date:** 2025-01-19
**Status:** ✅ Implemented & Deployed
**Author:** @claude
**Reviewers:** *(pending)*

---

## Overview

Added a `/debug` command to Telegram that toggles **verbose status mode** per chat. This allows users to see all LLM calls and tool executions as separate messages instead of having them edited in place.

---

## Problem Statement

Currently, status updates are sent to Telegram but they're **edited in place**, meaning:
1. "Thinking..." → replaced by → "Tool 1: search_web" → replaced by → "✅ Done in 56.1s"
2. User only sees the final message, missing intermediate progress
3. LLM timing (the slowest part!) is only visible in server logs

---

## Proposed Solution

Add a `/debug` command that toggles **verbose status mode** per Telegram chat.

### Behavior

**Default mode (debug off):**
- Status messages are edited in place (current behavior)
- Clean, minimal clutter

**Verbose mode (debug on):**
- Each status update sent as a new message
- All updates preserved and visible
- Includes LLM timing + token usage

---

## Usage

```
/debug          - Show current debug status
/debug on       - Enable verbose status (see all updates)
/debug off      - Disable (clean mode, edits in place)
/debug toggle   - Toggle debug mode
```

---

## Implementation Details

### Files Modified

1. **`src/cassey/channels/telegram.py`**
   - Added `_debug_chats: set[int]` to track chats with verbose mode
   - Added `_debug_command()` handler
   - Updated `send_status()` to check verbose mode
   - Updated `/help` command

2. **`src/cassey/agent/status_middleware.py`**
   - Added `record_llm_call()` function
   - Added `_llm_timing` context variable
   - Updated `aafter_agent()` to include LLM timing in summary

3. **`src/cassey/agent/nodes.py`**
   - Added call to `record_llm_call()` after each LLM invocation

### Code Changes

#### 1. Debug State Storage (telegram.py)

```python
def __init__(self, ...):
    ...
    self._debug_chats: set[int] = set()  # chat IDs with verbose mode enabled
```

#### 2. Command Handler (telegram.py)

```python
async def _debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /debug command to toggle verbose status mode."""
    chat_id = update.effective_chat.id
    args = context.args if context.args else []

    if not args:
        is_debug = chat_id in self._debug_chats
        status = "✅ ON (verbose)" if is_debug else "❌ OFF (default)"
        await update.message.reply_text(
            f"🔍 *Debug Status*: {status}\n\n"
            f"Usage:\n"
            f"• `/debug on` - Enable verbose status\n"
            f"• `/debug off` - Disable\n"
            f"• `/debug toggle` - Toggle",
            parse_mode="Markdown"
        )
        return

    command = args[0].lower()
    if command in ("on", "enable", "1", "true"):
        self._debug_chats.add(chat_id)
        await update.message.reply_text("✅ *Verbose debug enabled*", parse_mode="Markdown")
    elif command in ("off", "disable", "0", "false"):
        self._debug_chats.discard(chat_id)
        await update.message.reply_text("❌ *Verbose debug disabled*", parse_mode="Markdown")
    # ... handle toggle, etc.
```

#### 3. Status Update Behavior (telegram.py)

```python
async def send_status(self, conversation_id: str, message: str, update: bool = True):
    chat_id = int(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # Check if this chat has verbose debug mode enabled
    verbose_mode = chat_id in self._debug_chats

    if verbose_mode:
        # Verbose mode: always send new messages (don't edit)
        msg = await self.application.bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"[VERBOSE] Sent status to {chat_id}: {message}")
        return

    # Normal mode: try to edit existing message
    # ... existing edit logic ...
```

#### 4. LLM Timing Recording (status_middleware.py)

```python
_llm_timing: contextvars.ContextVar[dict | None] = contextvars.ContextVar("_llm_timing", default=None)

def record_llm_call(elapsed: float, tokens: dict | None = None) -> None:
    """Record an LLM call for status reporting in verbose mode."""
    current = _llm_timing.get() or {"count": 0, "total_time": 0, "calls": []}
    current["count"] += 1
    current["total_time"] += elapsed
    current["calls"].append({"elapsed": elapsed, "tokens": tokens})
    _llm_timing.set(current)
```

#### 5. LLM Call Recording (nodes.py)

```python
# After LLM invocation
llm_elapsed = time.time() - llm_start
token_dict = {"in": input_tokens, "out": output_tokens, "total": total_tokens}

# Record LLM timing for status middleware (shows in verbose mode)
record_llm_call(llm_elapsed, token_dict)
```

---

## Behavior Comparison

### Normal Mode (debug off - default)
Status messages are **edited in place**:
```
🤔 Thinking...
↓ (replaced)
⚙️ Tool 1: list_files
↓ (replaced)
✅ list_files (0.1s)
↓ (replaced)
✅ Done in 12.5s
```
User only sees the final message.

### Verbose Mode (debug on)
Each status update is a **new message**:
```
🤔 Thinking...
⚙️ Tool 1: list_files
✅ list_files (0.1s)
✅ Done in 12.5s | LLM: 1 call (12.3s)
```
All updates are preserved and visible.

---

## Example Output

### Enabling Debug Mode
```
User: /debug on
Bot: ✅ Verbose debug enabled

     All LLM calls and tool executions will be shown as separate messages.

     Use /debug off to disable.
```

### Simple Query (with debug on)
```
User: tell me about python
Bot: 🤔 Thinking...
Bot: ✅ Done in 15.2s | LLM: 1 call (15.0s)
```

### Query with Tools (with debug on)
```
User: what files do I have?
Bot: 🤔 Thinking...
Bot: ⚙️ Tool 1: list_files
Bot: ✅ list_files (0.1s)
Bot: ✅ Done in 3.5s | LLM: 1 call (3.3s)
```

---

## Testing

### Test Steps

1. **Check current status:**
   ```
   /debug
   ```

2. **Enable verbose mode:**
   ```
   /debug on
   ```

3. **Send a query that uses tools:**
   ```
   list my files
   ```

4. **Observe the separate status messages**

5. **Disable verbose mode:**
   ```
   /debug off
   ```

6. **Compare the difference**

### Expected Results

- Normal mode: Single status message, edited in place
- Verbose mode: Multiple status messages, all visible
- Final summary includes LLM timing: `| LLM: X call (Y.Ys)`

---

## Server Logs

When verbose mode is active, logs show `[VERBOSE]` prefix:
```
[VERBOSE] Sent status to 6282871705: 🤔 Thinking...
[VERBOSE] Sent status to 6282871705: ⚙️ Tool 1: list_files
[VERBOSE] Sent status to 6282871705: ✅ list_files (0.1s)
[VERBOSE] Sent status to 6282871705: ✅ Done in 12.5s | LLM: 1 call (12.3s)
```

---

## Design Decisions

### In-Memory State
- Debug state is **not persisted** (survives only until restart)
- Keeps implementation simple
- Users can re-enable after restart

### Per-Chat Isolation
- Each chat has independent debug setting
- Uses `chat_id` (int) as key
- No cross-contamination between users

### Context Variable for LLM Timing
- Uses `contextvars.ContextVar` for thread-safe timing sharing
- `record_llm_call()` called from `nodes.py`
- Status middleware reads timing for final summary

---

## Future Enhancements

- [ ] Persist debug state in database (survives restarts)
- [ ] Add timing breakdown (show each LLM call separately in verbose mode)
- [ ] Add token usage display in verbose mode
- [ ] Add filter by duration (only show >X seconds)

---

## Related Files

- Status middleware: `src/cassey/agent/status_middleware.py`
- LLM timing: `src/cassey/agent/nodes.py`
- Telegram channel: `src/cassey/channels/telegram.py`

---

## Checklist

- [x] Design approved
- [x] Implementation complete
- [x] Help text updated
- [x] Manual testing done
- [ ] Peer review
- [ ] Screenshots added
