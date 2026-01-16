# LangGraph Long-Term Memory - Knowledge Base

## Overview

LangGraph's long-term memory enables agents to remember information **across conversation sessions** (threads), unlike short-term memory (checkpointer) which only persists within a single thread.

## Memory Types

| Type | Description | Scope | Implementation |
|------|-------------|-------|----------------|
| **Short-term** | Conversation history within a session | Single thread | Checkpointer (MemorySaver, PostgresSaver) |
| **Long-term** | Persistent facts, preferences, memories | Cross-thread | Store (InMemoryStore, PostgresStore) |

## The Store API

LangGraph's `Store` is a simple document store for cross-thread persistence:

```python
from langgraph.store import BaseStore
from langgraph.store.postgres import PostgresStore
from langgraph.store.memory import InMemoryStore

# For development
store = InMemoryStore()

# For production
store = PostgresStore.from_conn_string("postgresql://...")
```

### Basic Store Operations

```python
from langgraph.store import BaseStore

# In a node function
def memory_node(state, config: dict, store: BaseStore):
    user_id = config["configurable"]["user_id"]

    # PUT: Save memory
    store.put(
        namespace=["user", user_id],
        key_name="preferences",
        value={"theme": "dark", "language": "python"}
    )

    # GET: Retrieve memory
    prefs = store.get(
        namespace=["user", user_id],
        key_name="preferences"
    )
    print(prefs.value)  # {"theme": "dark", "language": "python"}

    # SEARCH: Find memories by query
    results = store.search(
        namespace=["user", user_id],
        query="programming",
        limit=5
    )

    # DELETE: Remove memory
    store.delete(
        namespace=["user", user_id],
        key_name="old_key"
    )

    return state
```

## Store in Graph Compilation

```python
from langgraph.graph import StateGraph
from langgraph.store.postgres import PostgresStore

# Create store
store = PostgresStore.from_conn_string(DATABASE_URL)

# Compile with store
graph = workflow.compile(
    checkpointer=checkpointer,  # Short-term memory
    store=store  # Long-term memory
)

# Both available in nodes
def my_node(state, config, store):
    # store is injected automatically
    pass
```

## Memory Namespaces

Organize memories using hierarchical namespaces:

```python
# User-scoped memories
store.put(namespace=["user", "123"], key_name="profile", value={...})

# Conversation-specific memories
store.put(namespace=["conv", "abc"], key_name="summary", value={...})

# Document memories
store.put(namespace=["doc", "xyz"], key_name="metadata", value={...})

# Application-level memories
store.put(namespace=["app", "global"], key_name="config", value={...})
```

## Memory Patterns

### 1. User Profile Memory

```python
class MemoryState(TypedDict):
    messages: list
    user_profile: dict | None

def load_profile(state: MemoryState, config: dict, store: BaseStore):
    """Load user profile from long-term memory."""
    user_id = config["configurable"]["user_id"]

    profile = store.get(
        namespace=["users"],
        key_name=f"profile_{user_id}"
    )

    if profile:
        return {"user_profile": profile.value}
    return {"user_profile": None}

def save_profile(state: MemoryState, config: dict, store: BaseStore):
    """Save/update user profile."""
    user_id = config["configurable"]["user_id"]

    # Extract profile info from conversation
    profile_data = extract_profile_from_messages(state["messages"])

    store.put(
        namespace=["users"],
        key_name=f"profile_{user_id}",
        value=profile_data
    )

    return state
```

### 2. Episodic Memory

```python
def save_episodic_memory(state: MessagesState, config: dict, store: BaseStore):
    """Save conversation episode as memory."""
    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]

    # Summarize the conversation
    summary = model.invoke(
        f"Summarize this conversation: {state['messages']}"
    )

    # Save as episodic memory
    store.put(
        namespace=["episodes", user_id],
        key_name=thread_id,  # Use thread_id as key
        value={
            "summary": summary.content,
            "timestamp": "2024-01-01",
            "topic": extract_topic(state["messages"])
        }
    )

    return state
```

### 3. Semantic Memory Search

```python
def recall_relevant_memories(state: MessagesState, config: dict, store: BaseStore):
    """Retrieve memories relevant to current query."""
    user_id = config["configurable"]["user_id"]
    query = state["messages"][-1].content

    # Semantic search over memories
    memories = store.search(
        namespace=["memories", user_id],
        query=query,
        limit=3
    )

    # Inject into context
    memory_context = "\n".join(m.value for m in memories)

    return {
        "messages": [
            SystemMessage(content=f"Relevant memories:\n{memory_context}")
        ]
    }
```

### 4. Procedural Memory (Instructions)

```python
def save_procedural_memory(state: MessagesState, config: dict, store: BaseStore):
    """Save learned instructions/rules."""
    user_id = config["configurable"]["user_id"]

    # Extract instructions from feedback
    instructions = extract_instructions_from_feedback(state["messages"])

    # Append to existing procedural memory
    existing = store.get(namespace=["procedures", user_id], key_name="rules")
    current_rules = existing.value if existing else []

    updated_rules = current_rules + instructions

    store.put(
        namespace=["procedures", user_id],
        key_name="rules",
        value=updated_rules
    )

    return state

def apply_procedural_memory(state: MessagesState, config: dict, store: BaseStore):
    """Apply learned rules to current behavior."""
    user_id = config["configurable"]["user_id"]

    rules = store.get(namespace=["procedures", user_id], key_name="rules")
    if rules:
        # Prepend rules to system prompt
        rule_text = "\n".join(f"- {r}" for r in rules.value)
        return {
            "messages": [
                SystemMessage(content=f"Remember these rules:\n{rule_text}"),
                *state["messages"]
            ]
        }
    return state
```

## Store vs Checkpointer Decision Guide

| Question | Use Checkpointer | Use Store |
|----------|------------------|-----------|
| **Scope** | Single conversation | Across conversations |
| **Purpose** | Continue threads | Remember facts/preferences |
| **Data** | Message history | Structured documents |
| **Access** | `graph.get_state(config)` | `store.put/get/search()` |
| **Expiration** | TTL based | Manual or TTL |

## Postgres Store Configuration

```python
from langgraph.store.postgres import PostgresStore

# Connection string
DATABASE_URL = "postgresql://user:pass@host:5432/dbname"

# Create store
store = PostgresStore.from_conn_string(DATABASE_URL)

# Or with individual components
store = PostgresStore(
    conn=asyncpg.connect(DSN),
    table_name="store"  # Default table name
)

# With custom pool
import asyncpg

pool = await asyncpg.create_pool(DSN)
store = PostgresStore(pool)
```

## Store Schema

The Store uses a simple table structure:

```sql
-- Postgres store table (auto-created)
CREATE TABLE store (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (namespace, key)
);

-- For semantic search (optional extension)
CREATE TABLE store_embeddings (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    embedding vector(1536),
    FOREIGN KEY (namespace, key) REFERENCES store(namespace, key)
);
```

## Long-Term Memory with Feedback

```python
def learn_from_feedback(state: MessagesState, config: dict, store: BaseStore):
    """Agent learns from user feedback."""
    user_id = config["configurable"]["user_id"]

    # Check for user feedback
    for msg in state["messages"]:
        if msg.type == "human" and "feedback" in msg.content.lower():
            # Extract learning
            lesson = model.invoke(f"""
            Extract the lesson from this feedback:
            {msg.content}
            """)

            # Save as procedural memory
            store.put(
                namespace=["lessons", user_id],
                key_name=str(uuid.uuid4()),
                value={"lesson": lesson.content, "context": msg.content}
            )

    return state
```

## Best Practices

1. **Namespace hierarchically**: Use `["level1", "level2", "id"]` patterns
2. **Set TTLs**: Auto-expire old memories
3. **Compress large values**: Don't store huge objects directly
4. **Index for search**: Use embeddings for semantic retrieval
5. **Back up Store**: Treat as critical data

## Replacing mem_db with Store

If migrating from a custom memory database:

```python
# Old: custom mem_db
# memory = mem_db.get(user_id)

# New: LangGraph Store
memory = store.get(namespace=["users"], key_name=user_id)

# Migration helper
def migrate_to_store(mem_db, store: BaseStore):
    """Migrate from custom mem_db to LangGraph Store."""
    for user_id, data in mem_db.list_all():
        store.put(
            namespace=["users"],
            key_name=user_id,
            value=data
        )
```

## References

- [Long-Term Memory Announcement](https://blog.langchain.com/launching-long-term-memory-support-in-langgraph/)
- [Store API Reference](https://langchain-ai.github.io/langgraph/reference/store/)
- [Memory Concepts](https://langchain-ai.github.io/langgraph/concepts/memory/)
