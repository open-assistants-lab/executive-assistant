# Persistence in LangGraph

LangGraph has a built-in persistence layer implemented through checkpointers. When you compile a graph with a checkpointer, it saves a checkpoint of the graph state at every super-step to a thread.

## Core Concepts

### Threads

A thread is a unique ID assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of runs. When invoking a graph with a checkpointer, you **must** specify a `thread_id`:

```python
config = {"configurable": {"thread_id": "1"}}
```

### Checkpoints

A checkpoint is a snapshot of the graph state saved at each super-step, represented by a `StateSnapshot` object with properties:

* `config`: Config associated with this checkpoint
* `metadata`: Metadata associated with this checkpoint
* `values`: Values of the state channels at this point in time
* `next`: Tuple of node names to execute next
* `tasks`: Tuple of PregelTask objects with information about next tasks

## Basic Usage

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing_extensions import TypedDict

class State(TypedDict):
    foo: str
    bar: list[str]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}

workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": "", "bar": []}, config)
```

## State Operations

### Get State

Retrieve the latest state snapshot for a thread:

```python
config = {"configurable": {"thread_id": "1"}}
state_snapshot = graph.get_state(config)
```

### Get State History

Get full history of graph execution for a thread:

```python
config = {"configurable": {"thread_id": "1"}}
history = list(graph.get_state_history(config))
```

### Update State

Edit graph state at a checkpoint:

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    foo: int
    bar: Annotated[list[str], add]

# Current state: {"foo": 1, "bar": ["a"]}
graph.update_state(config, {"foo": 2, "bar": ["b"]})
# New state: {"foo": 2, "bar": ["a", "b"]}
```

The `as_node` parameter controls which node executes next:

```python
graph.update_state(config, values, as_node="node_name")
```

### Replay

Replay a prior graph execution from a specific checkpoint:

```python
config = {
    "configurable": {
        "thread_id": "1",
        "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"
    }
}
graph.invoke(None, config=config)
```

## Memory Store

For sharing information across threads, use the `Store` interface:

```python
from langgraph.store.memory import InMemoryStore

in_memory_store = InMemoryStore()
user_id = "1"
namespace = (user_id, "memories")

# Save memory
memory_id = str(uuid.uuid4())
memory = {"food_preference": "I like pizza"}
in_memory_store.put(namespace, memory_id, memory)

# Search memories
memories = in_memory_store.search(namespace)
```

### Semantic Search

Enable semantic search with embeddings:

```python
from langchain.embeddings import init_embeddings

store = InMemoryStore(
    index={
        "embed": init_embeddings("openai:text-embedding-3-small"),
        "dims": 1536,
        "fields": ["food_preference", "$"]
    }
)

# Semantic search
memories = store.search(
    namespace,
    query="What does the user like to eat?",
    limit=3
)
```

### Using in LangGraph

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = graph.compile(
    checkpointer=checkpointer,
    store=in_memory_store
)

def call_model(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    namespace = (user_id, "memories")

    memories = store.search(
        namespace,
        query=state["messages"][-1].content,
        limit=3
    )
    info = "\n".join([d.value["memory"] for d in memories])

    # Use memories in model call
```

## Checkpointer Libraries

* **langgraph-checkpoint**: Base interface + InMemorySaver (included)
* **langgraph-checkpoint-sqlite**: SQLite implementation
* **langgraph-checkpoint-postgres**: Postgres implementation (production-ready)
* **langgraph-checkpoint-cosmosdb**: Azure Cosmos DB implementation

## Serialization

Default serializer uses JsonPlusSerializer. For pickle fallback:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

checkpointer = InMemorySaver(
    serde=JsonPlusSerializer(pickle_fallback=True)
)
```

## Encryption

Encrypt persisted state using EncryptedSerializer:

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

serde = EncryptedSerializer.from_pycryptodome_aes()  # reads LANGGRAPH_AES_KEY
checkpointer = SqliteSaver(conn, serde=serde)
```

## Capabilities

### Human-in-the-Loop
Checkpointers allow humans to inspect, interrupt, and approve graph steps.

### Memory
Retain conversation state across interactions within a thread.

### Time Travel
Replay prior graph executions and fork state at arbitrary checkpoints.

### Fault-Tolerance
Restart graph from last successful step if nodes fail. Pending writes from successful nodes are preserved.
