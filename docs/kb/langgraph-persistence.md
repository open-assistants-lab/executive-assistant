# LangGraph Persistence - Knowledge Base

## Overview

LangGraph provides a built-in persistence layer through **checkpointers**. When a graph is compiled with a checkpointer, the graph state is automatically saved after each step, enabling:
- Conversation memory across invocations
- Pause/resume workflows
- Time travel debugging
- State replay

## Checkpointer Types

### MemorySaver (In-Memory)

Non-persistent checkpointer for development and testing.

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

graph = create_graph(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
)
```

**Use cases**:
- Development/testing
- Short-lived demo applications
- State resets on restart

### Postgres Checkpointer (Production)

Persistent checkpointer using PostgreSQL.

```python
from langgraph_checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")

graph = create_graph(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
)
```

**Use cases**:
- Production deployments
- Multi-instance deployments
- Persistent conversation memory

### Other Checkpointers

- `AsyncPostgresSaver` - Async PostgreSQL checkpointer
- `CheckpointSaver` - Base class for custom implementations

## Thread-Based Persistence

### Config Pattern

State is persisted per-thread using the `config` parameter:

```python
config = {
    "configurable": {
        "thread_id": "user-123-conversation-456"
    }
}

result = graph.invoke(
    {"messages": [{"role": "user", "content": "Hello"}]},
    config=config
)
```

**Key points**:
- `thread_id` must be **stable** across all requests in a conversation
- Each `thread_id` gets its own isolated state
- State is automatically saved after each step

### Best Practices for thread_id

1. **Use meaningful identifiers**:
   ```python
   # Good
   thread_id = f"user-{user_id}-conv-{conversation_id}"

   # Bad (changes each request)
   thread_id = f"request-{uuid.uuid4()}"
   ```

2. **Make thread_id user-scoped**:
   - Include user/channel identifier
   - Separate thread_id per conversation context
   - Reuse thread_id for continued conversations

3. **For multi-user systems**:
   ```python
   def get_thread_id(user_id: str, channel_id: str) -> str:
       # User's main conversation thread
       return f"{channel_id}:{user_id}:main"

   def get_thread_id_conversation(user_id: str, channel_id: str, conv_id: str) -> str:
       # Specific conversation thread
       return f"{channel_id}:{user_id}:conv:{conv_id}"
   ```

## Invocation with Checkpointer

### Basic Pattern

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = create_graph(..., checkpointer=checkpointer)

# First message
config = {"configurable": {"thread_id": "conv-1"}}
response1 = graph.invoke({"messages": [{"role": "user", "content": "Hi"}]}, config=config)

# Second message (continues conversation)
response2 = graph.invoke({"messages": [{"role": "user", "content": "How are you?"}]}, config=config)
```

### Streaming with Checkpointer

```python
config = {"configurable": {"thread_id": "conv-1"}}

for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Search"}]},
    config=config,
    stream_mode="values"
):
    # State automatically checkpointed after each step
    pass
```

### Getting Full State

```python
config = {"configurable": {"thread_id": "conv-1"}}

# Get current state
state = graph.get_state(config)
print(state.values["messages"])

# Get state history
for checkpoint in graph.get_state_history(config):
    print(checkpoint)
```

## State Snapshot Management

### Viewing State History

```python
config = {"configurable": {"thread_id": "conv-1"}}

# Get all checkpoints
for state in graph.get_state_history(config):
    print(f"Step: {state.next}")
    print(f"Messages: {len(state.values['messages'])}")
```

### Time Travel

Replay from a previous checkpoint:

```python
config = {"configurable": {"thread_id": "conv-1"}}

# Revert to specific checkpoint
graph.update_state(config, state_snapshot)

# Continue from that point
result = graph.invoke({"messages": [...]}, config=config)
```

## Multi-Thread Considerations

### Thread Isolation

Each `thread_id` has completely isolated state:

```python
# User A's conversation
config_a = {"configurable": {"thread_id": "user-a:main"}}
result_a = graph.invoke({"messages": [...]}, config=config_a)

# User B's conversation (separate state)
config_b = {"configurable": {"thread_id": "user-b:main"}}
result_b = graph.invoke({"messages": [...]}, config=config_b)

# States are completely isolated
```

### Cross-Thread Data

For data shared across threads (e.g., user preferences), use a **Store**:

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# Put data (across threads)
store.put(["user", "user-123"], "preferences", {"theme": "dark"})

# Get data
prefs = store.get(["user", "user-123"], "preferences")
```

## Checkpointer with create_agent

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

agent = create_agent(
    model="gpt-4o",
    tools=[search_tool],
    checkpointer=MemorySaver(),
)

# Invocation with thread_id
config = {"configurable": {"thread_id": "user-123"}}
result = agent.invoke({"messages": [{"role": "user", "content": "Search"}]}, config=config)
```

## Production Configuration

### PostgreSQL Connection String

```python
# Single variable
DATABASE_URL = "postgresql://user:pass@localhost:5432/dbname"

# Or individual components
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_USER = "executive_assistant"
POSTGRES_PASSWORD = "password"
POSTGRES_DB = "executive_assistant_db"
```

### Async Pattern

```python
from langgraph_checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)

async def get_response(thread_id: str, message: str):
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config
    )
    return result
```

## Troubleshooting

### State Not Persisting

**Problem**: Conversation not remembered between requests.

**Solutions**:
1. Ensure `thread_id` is consistent across requests
2. Verify checkpointer is passed to `create_agent` or graph compilation
3. Check database connection for PostgresSaver

### Thread Conflicts

**Problem**: Different conversations mixing state.

**Solution**: Ensure each user/conversation has a unique `thread_id`:
```python
# Include user and conversation identifiers
thread_id = f"{platform}:{user_id}:{conversation_id}"
```

### MemorySaver Data Loss

**Problem**: State lost on restart.

**Solution**: This is expected behavior. Use PostgresSaver for production.

## Best Practices Summary

1. **Always use a consistent `thread_id`** per conversation
2. **Include user/channel context** in `thread_id`
3. **Use MemorySaver for development**, PostgresSaver for production
4. **Enable checkpointer** for human-in-the-loop middleware
5. **Use Store** for cross-thread shared data (not checkpointer)

## References

- [Persistence Documentation](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Memory Overview](https://docs.langchain.com/oss/python/langgraph/memory)
- [Checkpoint Reference](https://reference.langchain.com/python/langgraph/checkpoint/)
