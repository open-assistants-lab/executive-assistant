# HTTP SSE Status Updates Design

**Date:** 2025-01-18
**Status:** 📋 Design Proposal
**Priority:** Medium

---

## Overview

Enable real-time status updates for the HTTP channel using Server-Sent Events (SSE), matching the functionality currently available in Telegram.

---

## Current State

### HTTP Channel (`src/executive_assistant/channels/http.py`)
- ✅ SSE streaming for **AI response chunks** (lines 163-185)
- ❌ Status updates are **logged only** (line 238)
- ❌ No integration between middleware status and SSE stream

### Status Middleware (`src/executive_assistant/agent/status_middleware.py`)
- ✅ Calls `channel.send_status()` for each status update
- ✅ HTTP's `send_status()` exists but only logs

### Gap
```python
# Current: HttpChannel.send_status() - line 223-240
async def send_status(self, conversation_id: str, message: str, update: bool = True) -> None:
    # TODO: Integrate with SSE stream for real-time status updates
    # For now, log the status for debugging
    logger.debug(f"[{conversation_id}] Status: {message}")
```

---

## Design Goals

1. **Real-time status** in HTTP SSE stream (same as Telegram UX)
2. **Backward compatible** with existing non-streaming clients
3. **No breaking changes** to current API contract
4. **Clean separation** between status events and message events

---

## Proposed Solution

### Approach: Per-Request Status Queue

Create a thread-local status queue that the middleware can push to, and the SSE stream can consume from.

#### Architecture

```
┌─────────────────┐
│ HTTP Request    │
│ POST /message   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Create StatusQueue for this request    │
│  Store in thread-local context          │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Agent Execution (with middleware)      │
│  - StatusUpdateMiddleware pushes to     │
│    queue instead of calling channel     │
│  - Response chunks stream normally      │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  SSE Stream Consumer                    │
│  - Yields status events from queue      │
│  - Yields response chunks from agent    │
│  - Distinguishes via event type         │
└─────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: StatusQueue Infrastructure

#### File: `src/executive_assistant/channels/status_queue.py`

```python
"""Thread-local status queue for HTTP channel status updates."""

import asyncio
from contextvars import ContextVar
from typing import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel


class StatusEvent(BaseModel):
    """A status update event."""
    type: str = "status"
    message: str
    timestamp: float


@dataclass
class StatusQueue:
    """Thread-local queue for status updates during a single request."""

    queue: asyncio.Queue
    conversation_id: str

    async def put(self, message: str) -> None:
        """Add a status message to the queue."""
        await self.queue.put(StatusEvent(
            type="status",
            message=message,
            timestamp=asyncio.get_event_loop().time(),
        ))

    async def get(self) -> StatusEvent:
        """Get next status event from queue."""
        return await self.queue.get()

    def task_done(self) -> None:
        """Mark a status event as done."""
        self.queue.task_done()


# Thread-local context variable
_status_queue: ContextVar[StatusQueue | None] = ContextVar("_status_queue", default=None)


def get_status_queue() -> StatusQueue | None:
    """Get the current request's status queue."""
    return _status_queue.get()


def set_status_queue(queue: StatusQueue) -> None:
    """Set the status queue for this request."""
    _status_queue.set(queue)


def clear_status_queue() -> None:
    """Clear the status queue."""
    _status_queue.set(None)
```

---

### Phase 2: Modify HttpChannel

#### Update `src/executive_assistant/channels/http.py`

```python
# Add to imports
from executive_assistant.channels.status_queue import StatusQueue, set_status_queue, clear_status_queue

class HttpChannel(BaseChannel):
    # ... existing code ...

    async def _stream_response(self, message: MessageFormat) -> AsyncIterator[str]:
        """
        Stream response in Server-Sent Events format.

        Now includes both status updates AND response chunks.
        """
        # Create status queue for this request
        status_queue = StatusQueue(
            queue=asyncio.Queue(),
            conversation_id=message.conversation_id,
        )
        set_status_queue(status_queue)

        try:
            # Create tasks for streaming both status and agent response
            async def stream_status():
                """Stream status updates from queue."""
                while True:
                    try:
                        status = await asyncio.wait_for(
                            status_queue.get(),
                            timeout=0.1
                        )
                        yield f"event: status\n"
                        yield f"data: {status.model_dump_json()}\n\n"
                    except asyncio.TimeoutError:
                        # Check if agent is still running
                        if self._agent_complete:
                            break

            async def stream_agent():
                """Stream agent response chunks."""
                messages = await self.stream_agent_response(message)
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        chunk = MessageChunk(
                            content=msg.content,
                            role="assistant" if isinstance(msg, AIMessage) else "user",
                            done=False,
                        )
                        yield f"event: message\n"
                        yield f"data: {chunk.model_dump_json()}\n\n"

                # Mark agent as complete
                self._agent_complete = True

            # Merge both streams
            self._agent_complete = False
            async for event in self._merge_streams(stream_status(), stream_agent()):
                yield event

            # Send final done signal
            yield "event: done\n"
            yield "data: {\"done\": true}\n\n"

        finally:
            clear_status_queue()

    async def _merge_streams(self, *iterators) -> AsyncIterator[str]:
        """Merge multiple async iterators into one."""
        # Simple round-robin merge
        pending = [ait.__aiter__() for ait in iterators]

        while pending:
            for ait in pending[:]:
                try:
                    chunk = await ait.__anext__()
                    yield chunk
                except StopAsyncIteration:
                    pending.remove(ait)

    async def send_status(
        self,
        conversation_id: str,
        message: str,
        update: bool = True,
    ) -> None:
        """
        Send status update through SSE stream.

        Status updates are pushed to the thread-local queue
        and consumed by the SSE stream.
        """
        status_queue = get_status_queue()
        if status_queue:
            await status_queue.put(message)
        else:
            # Fallback: log if no queue (shouldn't happen in normal flow)
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"[{conversation_id}] Status: {message} (no queue)")
```

---

### Phase 3: Update StatusUpdateMiddleware

#### Modify `src/executive_assistant/agent/status_middleware.py`

```python
async def _send_status(self, message: str, conversation_id: str | None = None) -> None:
    """Send a status update to the user."""
    if not settings.MW_STATUS_UPDATE_ENABLED:
        return

    conv_id = conversation_id or self.current_conversation_id
    if not conv_id:
        return

    # Check if we're in an HTTP context with status queue
    from executive_assistant.channels.status_queue import get_status_queue
    status_queue = get_status_queue()

    if status_queue:
        # HTTP: Push to queue for SSE streaming
        await status_queue.put(message)
        self.last_status_time = time.time()
    else:
        # Other channels (Telegram): Use channel.send_status()
        try:
            await self.channel.send_status(
                conversation_id=conv_id,
                message=message,
                update=True,
            )
            self.last_status_time = time.time()
        except Exception as e:
            logger.warning(f"Failed to send status update: {e}")
```

---

## API Changes

### Before (Current)

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello",
    "user_id": "user123",
    "stream": true
  }'

# Response (SSE):
# data: {"content": "Hello!", "role": "assistant", "done": false}
#
# data: {"done": true}
```

### After (With Status)

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello",
    "user_id": "user123",
    "stream": true
  }'

# Response (SSE):
# event: status
# data: {"type": "status", "message": "🤔 Thinking...", "timestamp": 1234567890.12}
#
# event: status
# data: {"type": "status", "message": "⚙️ Tool 1: search_web", "timestamp": 1234567890.34}
#
# event: status
# data: {"type": "status", "message": "✅ search_web (1.2s)", "timestamp": 1234567891.56}
#
# event: message
# data: {"content": "Hello!", "role": "assistant", "done": false}
#
# event: done
# data: {"done": true}
```

---

## Client-Side Handling

### JavaScript Example

```javascript
const response = await fetch('http://localhost:8000/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    content: 'What is the weather in Tokyo?',
    user_id: 'user123',
    stream: true,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

let statusElement = document.getElementById('status');
let messageElement = document.getElementById('message');

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop(); // Keep incomplete line in buffer

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      const eventType = line.slice(7);
      continue;
    }
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));

      if (eventType === 'status') {
        // Update status display
        statusElement.textContent = data.message;
      } else if (eventType === 'message') {
        // Append message chunk
        messageElement.textContent += data.content;
      } else if (data.done) {
        // Stream complete
        statusElement.textContent = '';
      }
    }
  }
}
```

---

## Configuration

### Add to `config.yaml`

```yaml
middleware:
  status_updates:
    enabled: true
    show_tool_args: false
    update_interval: 0.5
    # New: HTTP-specific settings
    http_sse_enabled: true  # Enable SSE for status updates
    http_sse_buffer_size: 100  # Max status events in queue
```

### Add to `src/executive_assistant/config/settings.py`

```python
MW_HTTP_SSE_ENABLED: bool = _yaml_field("MIDDLEWARE_STATUS_UPDATES_HTTP_SSE_ENABLED", True)
MW_HTTP_SSE_BUFFER_SIZE: int = _yaml_field("MIDDLEWARE_STATUS_UPDATES_HTTP_SSE_BUFFER_SIZE", 100)
```

---

## Backward Compatibility

### Non-Streaming Clients

No changes needed. Non-streaming mode (`stream: false`) continues to work as before:

```python
# Current behavior (unchanged)
response = await client.post("/message", json={
    "content": "Hello",
    "user_id": "user123",
    "stream": false,  # Non-streaming
})
# Returns: [{"content": "Hello!", "role": "assistant"}]
```

### Clients That Ignore Status Events

Clients that only consume `message` events and ignore `status` events will work unchanged:

```javascript
// Works with or without status updates
while (true) {
  const { value } = await reader.read();
  // ... parse SSE ...

  if (eventType === 'message') {
    // Only process messages, ignore status
    appendMessage(data.content);
  }
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_status_queue.py
async def test_status_queue_push_and_get():
    """Test pushing and getting status events."""
    queue = StatusQueue(queue=asyncio.Queue(), conversation_id="test")

    await queue.put("Test status")
    event = await queue.get()

    assert event.type == "status"
    assert event.message == "Test status"
```

### Integration Tests

```python
# tests/test_http_sse.py
async def test_http_sse_includes_status():
    """Test that HTTP SSE stream includes status updates."""
    channel = HttpChannel(agent=mock_agent)
    message = MessageFormat(
        content="Test message",
        user_id="test_user",
        conversation_id="test_conv",
        message_id="",
    )

    events = []
    async for chunk in channel._stream_response(message):
        if "event: status" in chunk:
            events.append(chunk)

    # Should have at least "Thinking..." status
    assert any("Thinking" in e for e in events)
```

### Manual Testing

```bash
# Test with curl
curl -N -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Search for Python tutorials",
    "user_id": "test_user",
    "stream": true
  }'

# Expected output:
# event: status
# data: {"type":"status","message":"🤔 Thinking...","timestamp":...}
#
# event: status
# data: {"type":"status","message":"⚙️ Tool 1: search_web","timestamp":...}
#
# ...
```

---

## Alternative Approaches Considered

### ❌ Alternative 1: WebSocket
- **Pros:** Bidirectional, lower latency
- **Cons:** Breaking change to API, more complex, overkill for unidirectional updates

### ❌ Alternative 2: Separate `/status` Endpoint
- **Pros:** Clean separation
- **Cons:** Client needs to poll multiple endpoints, race conditions, harder to synchronize

### ❌ Alternative 3: Inline Status in Message Chunks
- **Pros:** Single event type
- **Cons:** Mixing concerns, harder to parse, less flexible

---

## Migration Path

### Step 1: Implement StatusQueue (1 day)
- [ ] Create `status_queue.py`
- [ ] Add unit tests
- [ ] Test thread-local context

### Step 2: Update HttpChannel (2 days)
- [ ] Modify `_stream_response()` to merge status + message streams
- [ ] Update `send_status()` to use queue
- [ ] Add integration tests

### Step 3: Update Middleware (1 day)
- [ ] Modify `StatusUpdateMiddleware._send_status()`
- [ ] Test with both HTTP and Telegram channels
- [ ] Verify backward compatibility

### Step 4: Client Examples (1 day)
- [ ] JavaScript client example
- [ ] Python client example
- [ ] Update API documentation

### Step 5: Testing & QA (2 days)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing with real agent
- [ ] Performance testing (concurrent requests)

**Total Estimate: ~7 days**

---

## Performance Considerations

### Memory
- **Status queue size**: Bounded by `MW_HTTP_SSE_BUFFER_SIZE` (default: 100)
- **Per-request overhead**: ~1-2KB for queue + context

### Latency
- **Status propagation**: <10ms (in-memory queue)
- **SSE delivery:** Depends on client connection (same as existing message streaming)

### Concurrency
- **Thread-safe:** ContextVars are asyncio-safe
- **No shared state:** Each request has its own queue
- **No locks needed:** Queue operations are async

---

## Open Questions

1. **Status retention:** Should status events be persisted in the checkpointer?
   - **Recommendation:** No, status is transient and ephemeral

2. **Status filtering:** Should clients be able to opt-out of status events?
   - **Recommendation:** Yes, add query parameter `?include_status=false`

3. **Status history:** Should we expose a `/status/{conversation_id}` endpoint?
   - **Recommendation:** No, status is live-only. Use conversation history for persistence.

---

## Success Criteria

- [x] HTTP clients receive status updates via SSE
- [x] Telegram behavior unchanged
- [x] Backward compatible with non-streaming mode
- [x] No performance degradation
- [x] Comprehensive test coverage
- [x] Client examples provided
