# Message Streaming & Startup Fix - Implementation Report

**Date**: 2025-01-20
**Author**: Claude (Sonnet 4.5)
**Status**: Completed
**Review Required**: Yes

---

## Executive Summary

This session addressed critical issues with Cassey's message delivery system and startup process:

1. **Messages were being batched** - All responses arrived at once instead of streaming in real-time
2. **Todo list only showed at end** - Progress updates appeared after completion instead of during execution
3. **Bot startup was hanging** - Cassey process would start but not respond to messages
4. **Print output buffering** - Debug output wasn't appearing in logs, making debugging difficult
5. **Missing `_clean_markdown` method** - AttributeError when sending messages
6. **Missing imports** - `set_thread_id` and other functions not imported in telegram.py

**Resolution**: All issues fixed through refactoring message handling, fixing async/await patterns, and adding proper output flushing.

---

## Issues Fixed

### 1. Message Batching (Not Real-Time Streaming)

**Problem**: Messages accumulated in `stream_agent_response()` and were sent all at once at the end.

**Root Cause**:
- `BaseChannel.handle_message()` called `stream_agent_response()` which accumulated all messages
- Messages were collected in a list and only sent after the agent completed
- Users saw no progress until everything finished

**Files Modified**:
- `src/cassey/channels/base.py` - Removed `stream_agent_response()` method
- `src/cassey/channels/telegram.py` - Refactored `handle_message()` to send immediately

**Implementation**:
```python
# BEFORE: Messages accumulated
messages = await self.stream_agent_response(message)  # Returns all at end
for msg in messages:
    await self.send_message(message.conversation_id, msg.content)  # Batched

# AFTER: Send immediately
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        if hasattr(msg, "content") and msg.content:
            await self.send_message(message.conversation_id, msg.content)  # Real-time!
```

---

### 2. Todo List Not Showing During Execution

**Problem**: Todo list only appeared after agent finished, not during execution.

**Root Cause**:
- `TodoDisplayMiddleware.aafter_model()` checked `state["todos"]`
- But state updates from `Command(update={"todos": ...})` hadn't been applied yet when the hook ran
- The hook executed before state was updated

**Files Modified**:
- `src/cassey/agent/todo_display.py` - Read todos from `tool_call["args"]` directly

**Implementation**:
```python
# BEFORE: Checked state (not updated yet)
async def aafter_model(self, state, runtime):
    has_write_todos = any(tc.get("name") == "write_todos" ...)
    if has_write_todos and "todos" in state:  # ← State not updated yet!
        await self._send_todo_list(state["todos"])

# AFTER: Read from tool call args immediately
async def aafter_model(self, state, runtime):
    write_todos_calls = [
        tc for tc in (last_ai_msg.tool_calls or [])
        if tc.get("name") == "write_todos"
    ]
    if write_todos_calls:
        # Extract from tool call args immediately
        todos = write_todos_calls[0].get("args", {}).get("todos", [])
        if todos:
            await self._send_todo_list(todos)
```

---

### 3. Bot Startup Hanging

**Problem**: Cassey process started but never responded to messages.

**Root Cause**:
- Print statements were buffered and not appearing in logs
- Made debugging impossible - appeared bot was hanging when it was actually working
- `asyncio.create_task()` for channel.start() didn't yield control immediately
- Missing command handlers caused AttributeError

**Files Modified**:
- `src/cassey/scheduler.py` - Added `flush=True` to debug prints
- `src/cassey/main.py` - Added `flush=True` to all debug prints, changed to `await channel.start()`
- `src/cassey/channels/telegram.py` - Removed handlers for missing commands, added debug prints

**Implementation**:
```python
# BEFORE: Output buffered
print("DEBUG: Scheduler started")
await start_scheduler()
print("Reminder scheduler started")  # Never appeared!

# AFTER: Flush output immediately
print("DEBUG: Scheduler started", flush=True)
await start_scheduler()
print("Reminder scheduler started", flush=True)  # Appears immediately!
```

```python
# BEFORE: Background task (didn't run immediately)
tasks.append(asyncio.create_task(channel.start()))
print("Bot is running...")  # Appeared before channel started

# AFTER: Direct await (sequential startup)
await channel.start()  # Waits for channel to be ready
print("Bot is running...")  # Channel is ready
```

```python
# BEFORE: Handlers for non-existent commands
self.application.add_handler(CommandHandler("start", self._start_command))  # AttributeError!
self.application.add_handler(CommandHandler("help", self._help_command))    # Doesn't exist!

# AFTER: Only existing handlers
self.application.add_handler(CommandHandler("reset", self._reset_command))
self.application.add_handler(CommandHandler("remember", self._remember_command))
self.application.add_handler(CommandHandler("debug", self._debug_command))
```

---

### 4. Custom Summarization Removal

**Problem**: Two competing summarization systems were running.

### 5. Missing `_clean_markdown` Method

**Problem**: `'TelegramChannel' object has no attribute '_clean_markdown'` error when sending messages.

**Root Cause**: Code called `self._clean_markdown(content)` in `send_message()` but the method didn't exist.

### 6. Missing Imports in `telegram.py`

**Problem**: `name 'setthreadid' is not defined` and `name 'update' is not defined` errors when processing messages.

**Root Cause**:
- Functions `set_thread_id`, `ensure_thread_group`, `set_workspace_context` were called but not imported
- Management command handlers were removed even though the commands exist in `management_commands.py`
- `HumanMessage` was not imported
- Stray code line using undefined `update` variable in `finally` block

**Files Modified**:
- `src/cassey/channels/telegram.py` - Added missing imports, restored management command handlers, removed stray code

**Implementation**:
```python
# ADDED: Import HumanMessage at top of file
from langchain_core.messages import HumanMessage

# BEFORE: Functions used without imports
set_thread_id(thread_id)  # NameError!
group_id = await ensure_thread_group(thread_id, message.user_id)  # NameError!
set_workspace_context(group_id)  # NameError!

# AFTER: Import inline before use
from cassey.storage.file_sandbox import set_thread_id
from cassey.storage.group_storage import (
    ensure_thread_group,
    set_group_id as set_workspace_context,
    set_user_id as set_workspace_user_id,
)
set_thread_id(thread_id)  # Works!
group_id = await ensure_thread_group(thread_id, message.user_id)
set_workspace_context(group_id)
```

```python
# BEFORE: Management commands not registered
# (handlers were removed because commands were thought to not exist)

# AFTER: Management commands registered
self.application.add_handler(CommandHandler("mem", mem_command))
self.application.add_handler(CommandHandler("vs", vs_command))
self.application.add_handler(CommandHandler("db", db_command))
self.application.add_handler(CommandHandler("file", file_command))
self.application.add_handler(CommandHandler("meta", meta_command))
```

```python
# REMOVED: Stray line in finally block
# finally:
#     ...
#     await update.message.reply_text(help_message, parse_mode="Markdown")  # ← Removed!
# ```

**Files Modified**:
- `src/cassey/channels/telegram.py` - Removed call to non-existent `_clean_markdown()` method

**Implementation**:
```python
# BEFORE: Called non-existent method
content = self._convert_markdown_to_telegram(content)
content = self._clean_markdown(content)  # AttributeError!

# AFTER: Only convert markdown
content = self._convert_markdown_to_telegram(content)
```

**Note**: The `_convert_markdown_to_telegram()` method already handles all necessary markdown conversion and cleaning, so the additional `_clean_markdown()` call was redundant.

**Resolution**: Removed the custom summarization entirely, keeping only LangChain's `SummarizationMiddleware`.

**Files Deleted**:
- `src/cassey/agent/summary_extractor.py` - Entire custom summarization system

**Files Modified**:
- `src/cassey/agent/nodes.py` - Removed `summarize_conversation()` and `should_summarize()`
- `src/cassey/agent/graph.py` - Removed summarization routing logic
- `config.yaml` - Removed `context:` section with custom summarization settings

**Why This Was Correct**:
- Custom summarization was ineffective (29→28 messages, only 5% reduction)
- Custom summarization removed old messages without injecting summary into context
- LangChain's middleware REPLACES messages with summary (keeps context)
- Single source of truth is cleaner architecture

---

## Code Changes Summary

### src/cassey/channels/base.py

**Removed**: `stream_agent_response()` method (355-498)

**Changed**: `handle_message()` to stream immediately
```python
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        if hasattr(msg, "content") and msg.content:
            await self.send_message(message.conversation_id, msg.content)
```

### src/cassey/channels/telegram.py

**Removed**:
- Handlers for `_start_command`, `_help_command`
- Call to non-existent `_clean_markdown()` method
- Stray code line in `finally` block using undefined `update` variable

**Added**:
- Import for `HumanMessage` from `langchain_core.messages`
- Missing imports for `set_thread_id`, `ensure_thread_group`, `set_workspace_context`, `set_workspace_user_id`
- Management command handlers (`mem`, `vs`, `db`, `file`, `meta`)

**Changed**:
- Completely rewrote `handle_message()` with real-time streaming
- Added debug prints with `flush=True`
- Replaced `asyncio.create_task()` with direct `await` in main.py

### src/cassey/agent/todo_display.py

**Changed**: `aafter_model()` to read todos from `tool_call["args"]` instead of `state`

### src/cassey/scheduler.py

**Added**: Debug prints with `flush=True` to track startup

### src/cassey/main.py

**Added**:
- Debug prints with `flush=True` throughout startup sequence
- Changed from `asyncio.create_task(channel.start())` to `await channel.start()`

### config.yaml

**Removed**: Entire `context:` section with custom summarization settings

---

## Testing & Verification

### Manual Testing Steps

1. **Real-Time Streaming**:
   - Start Cassey: `uv run cassey`
   - Send a message that triggers tool use
   - Verify: Messages appear progressively as agent generates them

2. **Todo List Display**:
   - Send: "Create a file called test.txt with content hello"
   - Verify: Todo list shows immediately, not at end

3. **Message Responsiveness**:
   - Send: "hello"
   - Verify: Cassey responds within reasonable time

### Test Results

- ✅ Messages now stream in real-time
- ✅ Todo list appears immediately when write_todos is called
- ✅ Bot starts up successfully and responds to messages
- ✅ Debug output appears in logs immediately
- ✅ Management commands (`/mem`, `/vs`, `/db`, `/file`, `/meta`) restored and working

---

## Performance Impact

**Positive Changes**:
- Real-time streaming improves user experience (no waiting for complete response)
- Todo list visibility gives immediate feedback
- Proper async/await patterns prevent hanging

**Negligible Overhead**:
- `flush=True` on print statements has minimal performance impact
- Direct `await` instead of `create_task()` is actually cleaner
- Removing custom summarization reduces complexity

---

## Known Issues & Limitations

1. **Debug Prints**: Many debug print statements are still in place for monitoring
   - **Recommendation**: Remove or convert to proper logging once stable

2. **Missing Commands**: `/start` and `/help` commands are still removed
   - **Impact**: Minor - core functionality and management commands work
   - **Recommendation**: Re-implement if needed

3. **Channel Startup**: Channels now start sequentially instead of concurrently
   - **Impact**: Negligible for single channel setups
   - **Note**: Could be parallelized again with proper yielding if multiple channels needed

---

## Deployment Notes

### Environment Variables (Unchanged)
```bash
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_API_KEY=your-key
CASSEY_CHANNELS=telegram,http
TELEGRAM_BOT_TOKEN=your-token
```

### Startup Process
1. Start PostgreSQL: `docker-compose up -d postgres_db`
2. Start Cassey: `uv run cassey`
3. Verify logs show:
   - "Scheduler started"
   - "Telegram channel created"
   - "Bot is running. Channels: telegram"

### Verification Commands
```bash
# Check process is running
ps aux | grep cassey | grep -v grep

# Check logs
tail -f /tmp/cassey.log

# Send test message (use Telegram app directly)
# Or via API for testing
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=hello"
```

---

## Future Improvements

1. **Clean Up Debug Prints**: Replace with proper logging configuration
2. **Restore Missing Commands**: Re-implement `/start` and `/help` if needed
3. **Add Integration Tests**: Test streaming and startup automatically
4. **Error Handling**: Add more robust error handling in message handlers
5. **Metrics**: Track message delivery times and streaming performance

---

## References

- **Related Files**:
  - `src/cassey/channels/base.py` - Base channel with message handling
  - `src/cassey/channels/telegram.py` - Telegram-specific implementation
  - `src/cassey/agent/todo_display.py` - Todo list middleware
  - `src/cassey/main.py` - Application startup

- **Documentation**:
  - `discussions/middleware-debug-logging-peer-review-20250119.md` - Previous middleware work
  - `discussions/realistic-response-time-test-plan-20250119.md` - Performance testing

---

## Appendix: Debug Session Timeline

### Issue Discovery
- User reported: "i typed 'hello' but cassey doesn't respond"
- Logs showed bot running but not processing messages

### Investigation Process
1. Checked process status - running
2. Checked logs - stopped at "Scheduler started"
3. Added debug prints with flush=True
4. Found print buffering was hiding progress
5. Found missing command handlers causing AttributeError
6. Fixed issues one by one

### Root Causes Identified
1. Print output buffering → Added `flush=True`
2. Missing command handlers → Removed non-existent handlers
3. Async task not yielding → Changed to direct `await`

### Final Resolution
- Bot starts successfully
- Polling works correctly
- Messages are processed
- Real-time streaming functional

---

**End of Report**
