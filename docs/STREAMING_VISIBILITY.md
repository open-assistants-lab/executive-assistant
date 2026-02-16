# Streaming Visibility: Tool Calls, Todos & Planning

## Overview

The Executive Assistant now provides real-time visibility into its internal operations through streaming. This includes:

- **🔧 Tool Calls**: See which tools the agent is using (web search, memory, time, etc.)
- **📋 Todo List**: Track planning and task breakdown
- **💬 AI Response**: Stream the agent's thinking and responses
- **🧵 Thread Management**: Track conversation threads

---

## API: Streaming Endpoint

### HTTP Endpoint
```
POST /api/v1/message/stream
```

### Request Body
```json
{
  "message": "What time is it and search for Python updates?",
  "user_id": "user-123",
  "thread_id": "optional-thread-id"
}
```

### Response Format (Server-Sent Events)

The endpoint returns Server-Sent Events (SSE) with structured JSON data:

#### 1. Tool Call Event
```json
{
  "type": "tool_call",
  "tool": "get_current_time",
  "args": {"timezone": "UTC"},
  "id": "tool_call_123"
}
```

#### 2. Content Event
```json
{
  "type": "content",
  "content": "The current time is...",
  "is_tool_result": false
}
```

#### 3. Todos Event
```json
{
  "type": "todos",
  "todos": ["Search for Python updates", "Check current time"]
}
```

#### 4. Thread Event
```json
{
  "type": "thread",
  "thread_id": "user-123-default"
}
```

#### 5. Done Event
```json
{
  "type": "done"
}
```

---

## Example: Python Client

```python
import asyncio
import json
from datetime import datetime

import httpx


async def stream_agent_response():
    url = "http://localhost:8000/api/v1/message/stream"
    payload = {
        "message": "What time is it? Also search for the latest Python version.",
        "user_id": "test-user",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    event_type = data.get("type", "unknown")

                    if event_type == "tool_call":
                        print(f"🔧 Tool: {data['tool']}")
                        print(f"   Args: {data['args']}\n")

                    elif event_type == "todos":
                        print(f"📋 Todos: {data['todos']}\n")

                    elif event_type == "content" and not data.get("is_tool_result"):
                        print(f"💬 AI: {data['content']}\n")

                    elif event_type == "done":
                        print("✅ Complete!")


asyncio.run(stream_agent_response())
```

**Output:**
```
🔧 Tool: get_current_time
   Args: {"timezone": "UTC"}

💬 AI: The current time is 16:38:59 UTC.

🔧 Tool: web_search
   Args: {"query": "latest Python version 2024"}

✅ Tool result received (content hidden)

💬 AI: The latest stable Python version is 3.13.1...

✅ Complete!
```

---

## API: Non-Streaming Endpoint

### HTTP Endpoint
```
POST /api/v1/message
```

### Response (Enhanced)
```json
{
  "content": "The latest stable Python version is 3.13.1...",
  "thread_id": "user-123-default",
  "tool_calls": [
    {
      "id": "call_abc123",
      "name": "get_current_time",
      "args": {"timezone": "UTC"}
    },
    {
      "id": "call_def456",
      "name": "web_search",
      "args": {"query": "latest Python version"}
    }
  ],
  "todos": []
}
```

---

## Telegram Bot: Enhanced Visibility

### Features

The Telegram bot now shows:

1. **Typing Indicator**: Shows "typing..." while processing
2. **Tool Call Updates**: Updates message when tools are being used
3. **Real-time Updates**: Message edits as agent progresses

### Example Conversation

**User**: `What time is it?`

**Bot** (while processing):
```
⏳ Processing...
🔧 Using: get_current_time...
[Typing...]
```

**Bot** (final response):
```
The current time is 16:38:59 UTC on Monday, February 16, 2026.
```

---

## Implementation Details

### Streaming Mode
The agent uses LangGraph's `astream()` with `stream_mode="values"` to get intermediate states:

```python
async for chunk in agent.astream(
    {"messages": [HumanMessage(content=message)]},
    config={"configurable": {"thread_id": thread_id}},
    stream_mode="values",
):
    # Process chunk to extract:
    # - Tool calls from messages
    # - Todos from state
    # - Content from messages
```

### State Structure

Each chunk contains:
```python
{
    "messages": [...],        # Conversation history
    "todos": [...],           # Todo list (if TodoMiddleware enabled)
    # ... other middleware state
}
```

### Tool Call Detection

Tool calls are extracted from AI messages:
```python
if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
    for tool_call in last_msg.tool_calls:
        tool_event = {
            "type": "tool_call",
            "tool": tool_call.get("name"),
            "args": tool_call.get("args"),
            "id": tool_call.get("id"),
        }
```

---

## Configuration

### Enable Todo List Visibility

Todo list visibility requires `TodoListMiddleware` to be enabled. Configure in `/data/config.yaml`:

```yaml
middleware:
  todo_list:
    enabled: true
    max_todos: 100
```

### Disable Tool Call Visibility

Tool calls are always visible in streaming mode (cannot be disabled).

---

## Testing

### Test Streaming API
```bash
# Run the test script
python examples/test_stream_visibility.py
```

### Test Telegram Bot
1. Send a message to your bot
2. Watch for "⏳ Processing..." indicator
3. See tool calls as "🔧 Using: tool_name"
4. Receive final response

---

## Benefits

### 1. **Debugging**
See exactly which tools the agent is using and in what order.

### 2. **Transparency**
Users can understand the agent's reasoning process.

### 3. **Planning Visibility**
See how the agent breaks down complex tasks (via todos).

### 4. **Performance Monitoring**
Track how long each tool call takes.

### 5. **Learning**
Understand agent behavior for improvement.

---

## Future Enhancements

Potential additions:

- **Thinking/Reasoning**: If using o1 or models with explicit thinking
- **Subagent Delegation**: Show when subagents (coder, researcher, planner) are invoked
- **Memory Access**: Show which memories were retrieved
- **Middleware Metrics**: Display performance metrics for each middleware

---

## Comparison: Before vs After

### Before
```
User: "What time is it and search for Python updates?"
Bot: [Long pause]
Bot: "The time is 16:38 UTC and Python 3.13.1 is latest..."
```

### After (Streaming)
```
User: "What time is it and search for Python updates?"
Bot: ⏳ Processing...
Bot: 🔧 Using: get_current_time...
Bot: 🔧 Using: web_search...
Bot: "The time is 16:38 UTC and Python 3.13.1 is latest..."
```

The user sees exactly what's happening in real-time!

---

## Troubleshooting

### Issue: No tool calls visible
**Check**: Ensure `stream_mode="values"` is being used in the API endpoint.

### Issue: Todos not appearing
**Check**: Ensure `TodoListMiddleware` is enabled in `/data/config.yaml`.

### Issue: Telegram bot doesn't show typing
**Check**: Ensure bot has permission to send chat actions (should be automatic).

---

## See Also

- `MIDDLEWARE.md` - Middleware configuration including TodoListMiddleware
- `examples/test_stream_visibility.py` - Working example
- `docs/LANGFUSE_INTEGRATION_*.md` - Langfuse observability setup
