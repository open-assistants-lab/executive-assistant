# LangGraph Streaming - Knowledge Base

## Overview

LangGraph provides multiple ways to stream agent outputs, from individual tokens to full state updates. Streaming is essential for responsive user experiences in agentic applications.

## Stream Modes

LangGraph supports several `stream_mode` options when calling `graph.stream()` or `graph.astream()`:

| Mode | Description | Use Case |
|------|-------------|----------|
| `"values"` | Full state after each node completes | Debugging, state inspection |
| `"updates"` | Only the updated portion of state | Optimized state tracking |
| `"messages"` | Chat message updates only | Chat UIs |
| `"events"` | Raw LangGraph callback events | Advanced debugging |
| `"tokens"` | Individual LLM tokens (when supported) | Typing indicators |

## Basic Streaming

### Streaming Full State (values)

```python
from langgraph.graph import StateGraph

graph = workflow.compile()

# Stream full state after each node
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Hello"}]},
    stream_mode="values"
):
    print(chunk)
    # Output: {"messages": [HumanMessage(), AIMessage()]}
```

### Streaming State Updates (updates)

```python
# Stream only what changed in each step
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Hello"}]},
    stream_mode="updates"
):
    print(chunk)
    # Output: {"agent_node": {"messages": [AIMessage()]}}
```

### Streaming Messages Only

```python
# Stream only message updates
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Hello"}]},
    stream_mode="messages"
):
    latest_message = chunk[-1]
    print(f"Message: {latest_message.content}")
```

## Token Streaming

For real-time token-by-token output:

```python
async def stream_tokens(graph, query: str):
    """Stream LLM tokens as they are generated."""
    async for chunk in graph.astream(
        {"messages": [{"role": "user", "content": query}]},
        stream_mode="tokens"
    ):
        if chunk:
            print(chunk, end="", flush=True)
```

**Note**: Token streaming depends on model support. Not all models support true token streaming.

## Stream Events (Advanced)

`astream_events()` provides detailed event information including LLM callbacks:

```python
from langgraph.graph import StateGraph

async def stream_with_events(graph, query: str):
    """Stream with detailed event metadata."""
    async for event in graph.astream_events(
        {"messages": [{"role": "user", "content": query}]},
        version="v1"
    ):
        kind = event["event"]
        if kind == "on_chat_model_start":
            print(f"Model call started: {event['name']}")
        elif kind == "on_chat_model_stream":
            # Streaming tokens
            content = event["data"]["chunk"].content
            if content:
                print(content, end="", flush=True)
        elif kind == "on_chat_model_end":
            print(f"\nModel call finished. Tokens: {event['data'].get('token_usage')}")
```

## Streaming with FastAPI

### Server-Sent Events (SSE)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langgraph.graph import StateGraph

app = FastAPI()
graph = workflow.compile()

@app.post("/chat")
async def chat_endpoint(message: str):
    """Stream responses using Server-Sent Events."""
    async def generate():
        async for chunk in graph.astream(
            {"messages": [{"role": "user", "content": message}]},
            stream_mode="messages"
        ):
            # Yield SSE format
            latest = chunk[-1]
            if hasattr(latest, 'content'):
                yield f"data: {latest.content}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### WebSocket Streaming

```python
from fastapi import WebSocket
from typing import Dict, Any

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Stream responses over WebSocket."""
    await websocket.accept()
    graph = workflow.compile()

    while True:
        data = await websocket.receive_text()
        async for chunk in graph.astream(
            {"messages": [{"role": "user", "content": data}]},
            stream_mode="values"
        ):
            await websocket.send_json(chunk)
```

## Streaming with Checkpointers

Streaming works seamlessly with persistence:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-123"}}

for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Hello"}]},
    config=config,
    stream_mode="values"
):
    print(chunk)
    # State is checkpointed after each step
```

## Filtering Stream Output

### Stream Specific Nodes

```python
# Stream output from specific nodes only
for node_name, chunk in graph.stream(
    input_data,
    subgraphs=True
):
    if node_name == "research_node":
        print(f"Research: {chunk}")
```

### Stream Final Output Only

```python
# Get only the final result
final_state = graph.invoke(
    {"messages": [{"role": "user", "content": "Hello"}]}
)
print(final_state["messages"][-1].content)
```

## Handling Stream Errors

```python
async def safe_stream(graph, input_data):
    """Stream with error handling."""
    try:
        async for chunk in graph.astream(
            input_data,
            stream_mode="values"
        ):
            yield chunk
    except Exception as e:
        yield {"error": str(e)}
```

## Stream Metadata

Access metadata during streaming:

```python
async for event in graph.astream_events(input_data, version="v1"):
    # Event metadata
    event_kind = event["event"]
    event_parent = event.get("parent_ids", [])

    # For LLM events
    if "llm" in event_kind.lower():
        token_usage = event["data"].get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        print(f"Tokens: {prompt_tokens} + {completion_tokens}")
```

## Streaming Patterns

### Pattern 1: Progressive UI Updates

```python
async def stream_progressive(graph, query: str):
    """Stream with progressive UI updates."""
    status = "thinking"
    async for chunk in graph.astream(
        {"messages": [{"role": "user", "content": query}]},
        stream_mode="updates"
    ):
        for node_name, update in chunk.items():
            if node_name == "tools":
                status = "working"
            elif node_name == "agent":
                status = "responding"
            yield {"status": status, "update": update}
```

### Pattern 2: Tool-Aware Streaming

```python
async def stream_with_tools(graph, query: str):
    """Stream with tool execution visibility."""
    async for event in graph.astream_events(
        {"messages": [{"role": "user", "content": query}]},
        version="v1"
    ):
        if event["event"] == "on_tool_start":
            yield {"type": "tool_start", "tool": event["name"]}
        elif event["event"] == "on_tool_end":
            yield {"type": "tool_end", "tool": event["name"]}
        elif event["event"] == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield {"type": "token", "content": content}
```

## References

- [LangGraph Streaming Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api#streaming)
- [Streaming Events](https://docs.langchain.com/oss/python/langgraph/graph-api#streaming-events)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
