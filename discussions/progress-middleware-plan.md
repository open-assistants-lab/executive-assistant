# Progress Middleware - Real-Time Agent Visibility

**Problem:** Cassey takes 5+ minutes on complex tasks with no feedback. User sees "radio silence" and can't tell what's happening.

**Example:** User asks "find what langchain does, then save to vector store" → Cassey works for 5+ minutes with zero progress updates.

---

## Goal

Provide real-time visibility into:
1. **What** the agent is doing (tool calls, reasoning steps)
2. **How far** along it is (progress indication)
3. **How long** things are taking (timing info)

---

## Proposed Solution: Progress Middleware

Add a LangChain middleware that intercepts agent execution and sends progress updates to the user.

### Architecture

```
User Request
    ↓
Agent (with ProgressMiddleware)
    ↓
┌─────────────────────────────────────────┐
│  ProgressMiddleware                      │
│  ┌─────────────┐    ┌────────────────┐ │
│  │ on_start    │───▶│ Send "Starting..."│ │
│  │ on_tool     │───▶│ Send "Calling X" │ │
│  │ on_thought  │───▶│ Send "Thinking..."││
│  │ on_complete │───▶│ Send "Done"      │ │
│  └─────────────┘    └────────────────┘ │
└─────────────────────────────────────────┘
    ↓
Channel (Telegram/HTTP) sends update to user
```

---

## Implementation Plan

### Phase 1: Core Middleware (Quick Win)

**File:** `src/cassey/agent/progress_middleware.py`

```python
from langchain.agents.middleware import AgentMiddleware
from typing import Callable, TYPE_CHECKing

if TYPE_CHECKING:
    from cassey.channels.base import BaseChannel

class ProgressMiddleware(AgentMiddleware):
    """Sends progress updates to user during agent execution."""

    def __init__(self, channel: "BaseChannel"):
        self.channel = channel
        self.tool_count = 0
        self.start_time = None

    async def on_start(self, request: ModelRequest):
        """Called when agent starts processing."""
        self.start_time = time.time()
        self.tool_count = 0
        await self.channel.send_status("🤔 Thinking...")

    async def on_tool_start(self, tool_name: str, args: dict):
        """Called before tool execution."""
        self.tool_count += 1
        await self.channel.send_status(f"⚙️ Calling tool {self.tool_count}: {tool_name}")

    async def on_tool_end(self, tool_name: str, result: any):
        """Called after tool execution."""
        # Could summarize result briefly
        pass

    async def on_complete(self, response: ModelResponse):
        """Called when agent completes."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        await self.channel.send_status(f"✅ Completed in {elapsed:.1f}s")
```

### Phase 2: Channel Integration

**Update `src/cassey/channels/base.py`:**

```python
class BaseChannel(ABC):
    # ... existing ...

    async def send_status(self, message: str, update: bool = True):
        """Send a progress status update to the user.

        Args:
            message: Status message to send
            update: If True, edit previous message (Telegram) instead of new
        """
        raise NotImplementedError
```

**Implement in `src/cassey/channels/telegram.py`:**

```python
class TelegramChannel(BaseChannel):
    _last_status_message_id: dict[str, int] = {}  # thread_id -> message_id

    async def send_status(self, message: str, update: bool = True):
        """Send/edit status message."""
        thread_id = self.get_thread_id()

        if update and thread_id in self._last_status_message_id:
            # Edit existing message
            await self.bot.edit_message_text(
                chat_id=thread_id,
                message_id=self._last_status_message_id[thread_id],
                text=message,
            )
        else:
            # Send new message
            msg = await self.bot.send_message(chat_id=thread_id, text=message)
            self._last_status_message_id[thread_id] = msg.message_id
```

### Phase 3: Integration with Agent

**Update `src/cassey/agent/runtime.py` or wherever agent is created:**

```python
from cassey.agent.progress_middleware import ProgressMiddleware

# When creating agent for a request
async def create_agent_for_request(channel: BaseChannel, user_id: str):
    progress_mw = ProgressMiddleware(channel)

    agent = create_agent(
        model,
        system_prompt=...,
        middleware=[progress_mw, ...other_middleware],
        checkpointer=checkpointer,
    )
    return agent
```

---

## Message Examples

**User:** "find what langchain does, then save to vector store"

**What user would see:**

```
🤔 Thinking...
⚙️ Calling tool 1: search_web
⚙️ Calling tool 2: search_web
⚙️ Calling tool 3: create_vs_collection
⚙️ Calling tool 4: add_vs_documents
✅ Completed in 45.2s
```

**Result:** "I found that LangChain is... [saved to 'langchain_research' collection]"
---

## Configuration

Add to `.env`:

```bash
# Progress updates
PROGRESS_ENABLED=true
PROGRESS_UPDATE_FREQUENCY=1  # Update every N seconds max
PROGRESS_SHOW_TOOL_ARGS=false  # Hide sensitive args
```

---

## Alternatives Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **1. Progress Middleware** | Clean, reusable, centralized | Requires channel changes | ✅ **Recommended** |
| 2. Stream SSE to HTTP | Real-time, web-friendly | Doesn't work for Telegram | ❌ Limited to web |
| 3. Log everything then summarize | Complete audit trail | Still no real-time feedback | ❌ Doesn't solve UX |
| 4. LangSmith tracing | Detailed, external service | Requires external setup, paid tier | ❌ Overkill |

---

## Open Questions

1. **Should progress messages be ephemeral?** (auto-delete after response)
2. **Should we show tool arguments?** (might expose sensitive data)
3. **What about long LLM calls?** (show "Thinking..." with elapsed time?)
4. **Error handling?** (show "Tool X failed: reason")

---

## Timeline

| Phase | Effort | Deliverable |
|-------|--------|-------------|
| Phase 1 | 2-3 hours | ProgressMiddleware skeleton |
| Phase 2 | 1-2 hours | Channel integration (Telegram) |
| Phase 3 | 1 hour | Wire up to agent |
| **Total** | **4-6 hours** | Real-time progress visibility |

---

## Next Steps

1. Review and approve this plan
2. Create `src/cassey/agent/progress_middleware.py`
3. Add `send_status()` to BaseChannel
4. Implement in TelegramChannel
5. Wire up in agent creation
6. Test with user's example query

---

## Implementation Status (2025-01-18)

### ✅ Completed

### 📝 Peer Review Status (2025-01-18)

**Reviewed by:** Claude (Sonnet)
**Status:** ✅ **APPROVED**
**Review Document:** `discussions/progress-middleware-peer-review-20250118.md`

**Summary:**
- Implementation aligns well with original plan
- Code quality: ⭐⭐⭐⭐⭐ (5/5)
- All core features implemented with additional improvements
- Security properly handled (args sanitization, secure defaults)
- Error handling prevents agent crashes
- Recommended for merge

**Follow-up Items:**
- Add unit tests for `StatusUpdateMiddleware`
- Complete end-to-end testing with actual Telegram interaction
- Consider HTTP SSE streaming for web clients

**Note**: The implementation uses `StatusUpdateMiddleware` (following LangChain naming conventions) instead of `ProgressMiddleware`.

#### Files Created/Modified:

1. **`src/cassey/agent/status_middleware.py`** (NEW)
   - `StatusUpdateMiddleware` class using LangChain's `AgentMiddleware`
   - Hooks: `abefore_agent`, `awrap_tool_call`, `aafter_agent`
   - Features: tool counting, timing, error handling, args sanitization

2. **`src/cassey/channels/base.py`**
   - Added `send_status()` method with default implementation
   - Added `initialize_agent_with_channel()` for lazy agent initialization

3. **`src/cassey/channels/telegram.py`**
   - Implemented `send_status()` with message editing
   - Tracks `_status_messages` dict for edit capability

4. **`src/cassey/channels/http.py`**
   - Basic `send_status()` implementation (logs for now; full SSE TODO)

5. **`src/cassey/agent/langchain_agent.py`**
   - Updated `_build_middleware()` to accept `channel` parameter
   - Updated `create_langchain_agent()` to accept `channel` parameter
   - Status middleware added when channel is provided

6. **`src/cassey/config/settings.py`**
   - Added `MW_STATUS_UPDATE_ENABLED` (default: true)
   - Added `MW_STATUS_SHOW_TOOL_ARGS` (default: false)
   - Added `MW_STATUS_UPDATE_INTERVAL` (default: 0.5)

7. **`.env.example`**
   - Added status update configuration section

#### Key Implementation Details:

**LangChain Middleware Hooks Used:**
| Hook | Purpose |
|------|---------|
| `abefore_agent` | Send initial "Thinking..." |
| `awrap_tool_call` | Wrap tool execution for per-tool status |
| `aafter_agent` | Send completion with timing |

**Status Messages:**
```
🤔 Thinking...
⚙️ Tool 1: search_web
✅ search_web (2.3s)
⚙️ Tool 2: query_db
✅ query_db (0.5s)
✅ Done in 45.2s
```

**Error Handling:**
```
❌ search_web failed (5.1s): Network timeout
```

### Remaining Work

| Task | Status | Notes |
|------|--------|-------|
| HTTP SSE integration | ⏳ Pending | Currently logs; needs stream integration |
| Periodic LLM updates | ⏳ Optional | Could show "Still thinking... (30s)" |
| Ephemeral messages | ⏳ Optional | Auto-delete status after response |
| Testing | ⏳ Pending | End-to-end test with example query |

---

## Additional Fixes (2025-01-18)

### Channel Runtime Parameter Issue

**Problem:** After initial implementation, Cassey failed to start with:
```
TypeError: BaseChannel.__init__() got an unexpected keyword argument 'runtime'
```

**Root Cause:** Both `TelegramChannel` and `HttpChannel` had a `runtime` parameter that was being passed to `BaseChannel.__init__()` but `BaseChannel` didn't accept it.

**Fix Applied:**
- **`src/cassey/channels/telegram.py`**: Removed `runtime` parameter from `__init__` and `super().__init__()` call
- **`src/cassey/channels/http.py`**: Same fix applied

**Code Changes:**
```python
# Before
def __init__(self, token: str | None = None, agent: Runnable | None = None, runtime: str | None = None):
    ...
    super().__init__(agent, runtime=runtime)

# After
def __init__(self, token: str | None = None, agent: Runnable | None = None):
    ...
    super().__init__(agent)
```

**Status:** ✅ Cassey now starts successfully

### Configuration

```bash
# .env
MW_STATUS_UPDATE_ENABLED=true      # Enable/disable status updates
MW_STATUS_SHOW_TOOL_ARGS=false    # Show tool args (security risk)
MW_STATUS_UPDATE_INTERVAL=0.5     # Min seconds between updates
```