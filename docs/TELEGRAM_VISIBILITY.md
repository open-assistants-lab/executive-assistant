# Telegram Bot Visibility

## Overview

The Telegram bot provides real-time visibility into agent operations through message editing. All Telegram-specific formatting logic is in `src/telegram/formatters.py`.

## Features

### ✅ Tool Call Visibility
- Shows which tools are being used in real-time
- Updates the status message as each tool is invoked
- Displays tool arguments in the final response

### ✅ Todo List Visibility
- Shows the agent's plan as it develops
- Updates the status message when todos change
- Displays todos in the final response

### ✅ Typing Indicator
- Shows "typing..." status while the agent is processing
- Updates every 3 seconds to keep the indicator alive
- Gives users visual feedback that the bot is working

### ✅ Message Editing
- Edits the status message to show progress
- Replaces the status with the final response
- Falls back to sending a new message if editing fails

## Architecture

### Telegram-Specific Formatters

All formatting logic is in `src/telegram/formatters.py`:

- **`MessageFormatter`**: Formats messages for Telegram display
  - `format_processing_status()` - Status during processing
  - `format_final_response()` - Final response with tool/todos summary
  - `format_done_message()` - Done message when no text response

- **`MessageUpdater`**: Handles message updates
  - `update_processing_status()` - Update status with tools/todos
  - `update_final_response()` - Update with final response
  - `update_done_message()` - Update with done status

### Usage

```python
from src.telegram.formatters import MessageUpdater

# Send initial status message
status_message = await update.effective_message.reply_text("⏳ Processing...")
updater = MessageUpdater(status_message)

# Update during processing
await updater.update_processing_status(tool_calls, todos)

# Update with final response
await updater.update_final_response(tool_calls, content, todos)
```

## What You See

### Example 1: Time Query
```
You: what's the time now?

Bot: ⏳ Processing...

Bot: ⏳ Processing...

🔧 **Tools used:**
• get_current_time

Bot: 🔧 **Tools used:**
• get_current_time (timezone: 'UTC')

The current time is 16:42:15 UTC on Monday, February 16, 2026.
```

### Example 2: Complex Task with Planning
```
You: Search for Python updates and summarize them

Bot: ⏳ Processing...

📋 **Plan:**
• Search for latest Python version
• Check Python release notes
• Summarize key features

Bot: ⏳ Processing...

📋 **Plan:**
• Search for latest Python version
• Check Python release notes
• Summarize key features

🔧 **Tools used:**
• web_search

Bot: 📋 **Plan:**
• Search for latest Python version
• Check Python release notes
• Summarize key features

🔧 **Tools used:**
• web_search (query: 'latest Python version 2024')

Based on my search, Python 3.13.1 is the latest stable release...
```

### Background (Logs)
```
INFO:__main__:Tool call: get_current_time
INFO:httpx:HTTP Request: POST .../bot.../getUpdates "HTTP/1.1 200 OK"
```

## Implementation Details

### Message Flow

1. **Initial Status**: Send "⏳ Processing..." message
2. **Keep Typing**: Background task sends typing action every 3 seconds
3. **Track Progress**: Stream agent execution, collect tools/todos
4. **Update Status**: Edit message to show tools/todos as they appear
5. **Final Response**: Edit message with complete response + summary

### Streaming with LangGraph

```python
async for chunk in agent.astream(
    {"messages": [HumanMessage(content=user_message)]},
    config={"configurable": {"thread_id": thread_id}},
    stream_mode="values",
):
    # Extract tool calls from messages
    if "messages" in chunk and chunk["messages"]:
        last_msg = chunk["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            # Track and display tool calls

    # Extract todos from state
    if "todos" in chunk and chunk["todos"]:
        # Track and display todos
```

## For Full Visibility

If you want even more visibility:
- 🔧 Tool calls with full arguments
- 📋 Todo list updates in real-time
- 💬 Step-by-step progress

Use the **HTTP API streaming endpoint** instead:

```python
# examples/test_stream_visibility.py
import asyncio
import httpx

async def stream_agent_response():
    url = "http://localhost:8000/api/v1/message/stream"
    payload = {"message": "What time is it?"}

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["type"] == "tool_call":
                        print(f"Tool: {data['tool']}")
```

See `docs/STREAMING_VISIBILITY.md` for HTTP API streaming details.

---

## Benefits

### Real-time Feedback
- See exactly which tools are being used
- Understand the agent's planning process (todos)
- No black box - full transparency

### Clean User Experience
- Single message that gets updated
- No spam with multiple progress messages
- Final response includes complete summary

### Reliability
- Handles Telegram's editing time limits
- Falls back to new message if editing fails
- Consistent behavior

### Maintainability
- All Telegram-specific formatting in `formatters.py`
- Easy to update message formats
- Separation of concerns (presentation vs. logic)

---

## Configuration

Todo list visibility requires `TodoListMiddleware` to be enabled. Configure in `/data/config.yaml`:

```yaml
middleware:
  todo_list:
    enabled: true
    max_todos: 100
```

---

## Future Enhancements

Potential improvements:

1. **Markdown Formatting**: Use MarkdownV2 for richer formatting
2. **Inline Buttons**: Quick actions without typing
3. **Web Interface**: Build a web UI that connects to the bot
4. **Status Channel**: Separate channel for detailed updates

The current implementation provides good UX with real-time tool and todo visibility.
