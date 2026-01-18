# Debug Logging Improvements Plan

**Date:** 2025-01-18
**Status:** 🚧 In Progress (1 item completed)
**Priority:** High (Developer Experience)

---

## Progress Tracking

| Task | Status | Date |
|------|--------|------|
| ✅ Millisecond timestamps in logs | Done | 2025-01-19 |
| ⏳ Message logging (Base Channel) | Todo | - |
| ⏳ Tool call logging (Middleware) | Todo | - |
| ⏳ Storage operation logging | Todo | - |
| ⏳ Error context enhancement | Todo | - |

---

## Completed Changes

### 2025-01-19: Millisecond Timestamps

**File:** `src/cassey/logging.py`
**Change:** Added milliseconds to timestamp format for precise timing measurements

```python
# Before: {time:YYYY-MM-DD HH:mm:ss}
# After:  {time:YYYY-MM-DD HH:mm:ss.SSS}
```

**Example output:**
```
2026-01-19 01:27:06.123 | INFO | ...
```

This allows measuring task duration with millisecond precision from logs.

---

## Problem Statement

Currently, even with `LOG_LEVEL=DEBUG`, the logs don't provide sufficient visibility into:

1. **User's messages** - What did the user send?
2. **Cassey's responses** - What did the agent say?
3. **Status progress** - "Thinking...", "Tool 1: search_web", etc.
4. **Tool calls** - Which tool, what args, what result?
5. **Database operations** - Which tables were read/written/created/deleted?
6. **Vector store operations** - Which collections were searched/updated?
7. **File operations** - Which files were read/written/listed?
8. **Errors** - Full context, stack traces, what went wrong?

This makes debugging difficult when things go wrong.

---

## Current State Analysis

### Logging Setup

**File:** `src/cassey/logging.py`
- Uses Loguru for structured logging
- Configurable via `config.yaml` → `logging.level`
- Default: `INFO`
- Console + optional file logging

**Config:**
```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: null   # Optional log file path
```

### Existing DEBUG Logs

| Location | What It Logs |
|----------|-------------|
| `channels/base.py:340` | First 5 stream events (limited) |
| `channels/base.py:357` | Stream summary (event count, message count) |
| `channels/http.py:240` | Status updates (but using stdlib logging, not Loguru) |
| `storage/group_storage.py` | Permission check debug logs |

### What's Missing

| Category | Current Behavior | Desired Behavior |
|----------|-----------------|------------------|
| User messages | ❌ Not logged | ✅ Log content, user_id, conversation_id at DEBUG |
| Cassey responses | ❌ Not logged | ✅ Log full AI responses at DEBUG |
| Status updates | ⚠️ Only in Telegram (HTTP logs to stdlib) | ✅ All status updates at DEBUG |
| Tool calls | ❌ Not logged | ✅ Log tool name, args, result, timing at DEBUG |
| Database operations | ❌ Not logged | ✅ Log DB read/write/create/delete at DEBUG |
| Vector store operations | ❌ Not logged | ✅ Log VS create/add/search at DEBUG |
| File operations | ❌ Not logged | ✅ Log file read/write/list at DEBUG |
| Errors | ⚠️ Some logged, limited context | ✅ Full stack + context + request details at ERROR |
| LangChain events | ❌ Not logged | ✅ Log model calls, tokens, reasoning at DEBUG |

---

## Design Goals

1. **No performance impact** when `LOG_LEVEL=INFO` or higher
2. **Complete visibility** when `LOG_LEVEL=DEBUG`
3. **Structured logs** using Loguru's binding/context features
4. **Consistent format** across all components
5. **Easy filtering** by log level and component

---

## Proposed Solution

### Approach: Structured Debug Logging with Context Binding

Use Loguru's `bind()` to attach context to all logs within a request lifecycle.

#### Architecture

```
User Message Received
    ↓
Bind context: user_id, conversation_id, channel, message_id
    ↓
Log: 📥 USER: {content}
    ↓
Agent Processing (with middleware)
    ├─ Log: 🤔 Thinking...
    ├─ Log: 🔧 TOOL: {tool_name} with {args}
    ├─ Log: ✅ TOOL RESULT: {result} ({duration}s)
    │
    ├─ Storage Operations (when tools execute)
    │   ├─ Log: 💾 DB_READ: {table} WHERE {conditions}
    │   ├─ Log: 💾 DB_WRITE: {table} {rows} rows
    │   ├─ Log: 🔍 VS_SEARCH: {collection} "{query}" → {count} results
    │   ├─ Log: 📄 VS_ADD: {collection} {count} documents
    │   ├─ Log: 📖 FILE_READ: {path} ({size} bytes)
    │   ├─ Log: ✏️ FILE_WRITE: {path} ({size} bytes)
    │   └─ Log: 📁 FILE_LIST: {pattern} → {count} files
    │
    └─ Log: ❌ ERROR: {error} + context
    ↓
AI Response Generated
    ↓
Log: 📤 AI: {content}
    ↓
Send to user
    ↓
Unbind context
```

---

## Implementation Plan

### Phase 1: Message Logging (Base Channel)

**File:** `src/cassey/channels/base.py`

#### Add Debug Logging to `stream_agent_response()`

```python
# Bind context for all logs in this request
request_logger = logger.bind(
    user_id=message.user_id,
    conversation_id=message.conversation_id,
    thread_id=thread_id,
    channel=channel,
    message_id=message.message_id,
)

# DEBUG: Log incoming message
request_logger.debug(
    "📥 USER_MESSAGE: {content}",
    content=message.content[:200] + "..." if len(message.content) > 200 else message.content,
)

# DEBUG: Log outgoing AI response
for msg in messages:
    if hasattr(msg, "content") and msg.content:
        request_logger.debug(
            "📤 AI_RESPONSE: {content}",
            content=msg.content[:500] + "..." if len(msg.content) > 500 else msg.content,
        )
```

### Phase 2: Tool Call Logging (Middleware)

**File:** `src/cassey/agent/status_middleware.py`

#### Add Debug Logging for Tool Calls

```python
async def awrap_tool_call(self, request, handler):
    tool_name = request.tool_call.get("name", "unknown")
    tool_args = request.tool_call.get("args", {})
    
    logger.debug(
        "🔧 TOOL_CALL: {name} args={args}",
        name=tool_name,
        args=self._sanitize_args(tool_args),
    )
    
    start = time.time()
    try:
        result = await handler(request)
        elapsed = time.time() - start
        
        logger.debug(
            "✅ TOOL_RESULT: {name} ({elapsed:.3f}s)",
            name=tool_name,
            elapsed=elapsed,
        )
        return result
    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            "❌ TOOL_ERROR: {name} ({elapsed:.3f}s): {error}",
            name=tool_name,
            elapsed=elapsed,
            error=str(e),
            exc_info=True,
        )
        raise
```

### Phase 3: Storage Operation Logging

**File:** `src/cassey/storage/db_tools.py`

#### Add Debug Logging for Database Operations

```python
@tool
def query_db(table: str, sql: str) -> str:
    logger.debug(
        "💾 DB_QUERY: {table} sql={sql}",
        table=table,
        sql=sql[:200],
    )
    # ... implementation ...
    logger.debug(
        "💾 DB_RESULT: {table} {rows} rows",
        table=table,
        rows=len(results),
    )
```

### Phase 4: Error Context Enhancement

**File:** `src/cassey/channels/base.py`

#### Add Error Context Logging

```python
except Exception as e:
    logger.error(
        "❌ AGENT_ERROR: {error} | user={user} conv={conv} thread={thread}",
        error=str(e),
        user=message.user_id,
        conv=message.conversation_id,
        thread=thread_id,
        exc_info=True,
    )
```

---

## Log Format

### Timestamp Format (UPDATED)

```python
{time:YYYY-MM-DD HH:mm:ss.SSS}
```

Example: `2026-01-19 01:27:06.123`

### Standard Format

```
YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line | message
```

### Emoji Prefix Convention

| Emoji | Meaning |
|-------|---------|
| 📥 | Incoming (user message) |
| 📤 | Outgoing (AI response) |
| 🤔 | Agent thinking |
| 🔧 | Tool call |
| ✅ | Success result |
| ❌ | Error |
| 💾 | Database operation |
| 🔍 | Vector store search |
| 📄 | Vector store add |
| 📖 | File read |
| ✏️ | File write |
| 📁 | File list |
| 🧠 | Memory retrieval |

---

## Configuration

### Enable Debug Logging

```yaml
# config.yaml
logging:
  level: DEBUG  # Set to DEBUG for verbose logging
  file: "cassey.log"  # Optional: log to file
```

### Environment Variable

```bash
export LOG_LEVEL=DEBUG
uv run cassey
```

---

## Testing

### Verify Debug Logging

1. Set `LOG_LEVEL=DEBUG`
2. Send a message via Telegram
3. Check console output for:
   - 📥 USER_MESSAGE
   - 🤔 Thinking...
   - 🔧 TOOL_CALL
   - ✅ TOOL_RESULT
   - 📤 AI_RESPONSE

### Verify Timestamps

```bash
# Should show millisecond precision
2026-01-19 01:27:06.123 | INFO | ...
```
