# LangGraph Context Engineering - Knowledge Base

## Overview

Context engineering is the art and science of filling the context window with just the right information at each step of an agent's trajectory. As Karpathy puts it: *"the delicate art and science of filling the context window with just the right information for the next step."*

## Four Context Engineering Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| **Write** | Save context outside the window | Scratchpads, long-term memory |
| **Select** | Pull relevant context into window | RAG, memory retrieval |
| **Compress** | Retain only required tokens | Summarization, trimming |
| **Isolate** | Split context across boundaries | Multi-agent, sandboxes |

## 1. Write Context

### Scratchpads (Short-Term)

Save information during a session:

```python
from langgraph.graph import StateGraph, MessagesState
from typing import TypedDict

class AgentState(MessagesState):
    """State with scratchpad field."""
    scratchpad: str  # Persistent notes during session

def thinking_node(state: AgentState):
    """Agent writes thoughts to scratchpad."""
    current_thought = model.invoke(
        f"Context: {state['scratchpad']}\n"
        f"Latest: {state['messages'][-1].content}\n\n"
        "Write your plan:"
    )

    # Update scratchpad
    new_scratchpad = f"{state.get('scratchpad', '')}\n{current_thought.content}"

    return {
        "scratchpad": new_scratchpad,
        "messages": [current_thought]
    }
```

### Long-Term Memory (Cross-Thread)

Persist across sessions using LangGraph Store:

```python
from langgraph.store import BaseStore

# In node function
def save_memory_node(state: AgentState, config: dict, store: BaseStore):
    """Save important information to long-term memory."""
    user_id = config["configurable"]["user_id"]

    # Save to store (cross-thread memory)
    store.put(
        namespace=["user", user_id],
        key_name="preferences",
        value={"theme": "dark", "language": "python"}
    )

    return state

def recall_memory_node(state: AgentState, config: dict, store: BaseStore):
    """Recall from long-term memory."""
    user_id = config["configurable"]["user_id"]

    # Retrieve from store
    prefs = store.get(namespace=["user", user_id], key_name="preferences")

    if prefs:
        # Inject into context
        return {
            "messages": [
                SystemMessage(content=f"User preferences: {prefs.value}")
            ]
        }
    return state
```

## 2. Select Context

### Semantic Retrieval (RAG)

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

# Setup vectorstore
vectorstore = InMemoryVectorStore(embedding=OpenAIEmbeddings())

def retrieve_context_node(state: AgentState):
    """Select relevant context via semantic search."""
    query = state["messages"][-1].content

    # Retrieve top-k relevant documents
    docs = vectorstore.similarity_search(query, k=3)

    # Format as context
    context = "\n\n".join(doc.page_content for doc in docs)

    # Add as system message
    return {
        "messages": [
            SystemMessage(content=f"Relevant context:\n{context}")
        ]
    }
```

### Memory Selection

```python
from langgraph.store import BaseStore

def select_memories(state: AgentState, config: dict, store: BaseStore):
    """Select relevant memories for current task."""
    user_id = config["configurable"]["user_id"]
    query = state["messages"][-1].content

    # Search memories by embedding similarity
    memories = store.search(
        namespace=["user", user_id],
        query=query,
        limit=5
    )

    # Format relevant memories
    memory_context = "\n".join(m.value for m in memories)

    return {
        "messages": [
            SystemMessage(content=f"Relevant memories:\n{memory_context}")
        ]
    }
```

### Tool Selection

Reduce tool overload:

```python
from langchain.tools import tool

# Define many tools
@tool
def search_web(query: str) -> str:
    """Search the web."""
    pass

@tool
def search_docs(query: str) -> str:
    """Search documentation."""
    pass

# LLM selects relevant tools
def select_tools_node(state: AgentState):
    """Use LLM to select relevant tools."""
    all_tools = [search_web, search_docs, ...]  # 50+ tools

    query = state["messages"][-1].content

    # Use embeddings to select top 5 tools
    tool_descriptions = [t.name + ": " + t.description for t in all_tools]

    # Semantic search over tool descriptions
    selected_tools = select_top_k_tools(query, tool_descriptions, k=5)

    return {"available_tools": selected_tools}
```

## 3. Compress Context

### Summarization

```python
def summarize_node(state: AgentState):
    """Compress message history when too long."""
    messages = state["messages"]

    # Check token count (rough estimate)
    total_chars = sum(len(m.content) for m in messages)
    if total_chars < 50000:
        return state  # No compression needed

    # Summarize older messages
    recent = messages[-10:]
    older = messages[:-10]

    summary_prompt = f"""
    Summarize these messages concisely:
    {format_messages(older)}
    """

    summary = model.invoke(summary_prompt)

    # Replace old messages with summary
    return {
        "messages": [
            SystemMessage(content=f"Previous conversation summary: {summary.content}"),
            *recent
        ]
    }
```

### Context Trimming

```python
from langchain_core.messages import trim_messages

def trim_context_node(state: AgentState):
    """Trim messages to fit context window."""
    messages = state["messages"]

    # Keep last N tokens, system messages, and last human message
    trimmed = trim_messages(
        messages,
        max_tokens=4000,
        strategy="last",
        token_counter=model.count_tokens,
        include_system=True,
        allow_partial=False
    )

    return {"messages": trimmed}
```

### Tool Result Compression

```python
def compress_tool_results(state: AgentState):
    """Summarize verbose tool outputs."""
    for msg in state["messages"]:
        if msg.type == "tool" and len(msg.content) > 5000:
            # Compress large tool outputs
            summary = model.invoke(
                f"Summarize this tool result:\n{msg.content[:4000]}"
            )
            msg.content = f"[Summary]: {summary.content}"

    return state
```

## 4. Isolate Context

### Multi-Agent Isolation

```python
from langgraph.graph import StateGraph

# Define specialized agents
def researcher_agent(state):
    """Research-focused agent with its own context."""
    # Has access to research tools only
    return research_model.invoke(state["messages"])

def writer_agent(state):
    """Writer-focused agent with its own context."""
    # Receives summarized research, not raw context
    research_summary = state.get("research_summary", "")
    prompt = f"Based on this research: {research_summary}\n\nWrite about: {state['topic']}"

    return writer_model.invoke(prompt)

# Supervisor coordinates
def supervisor_node(state: AgentState):
    """Route to appropriate sub-agent."""
    query = state["messages"][-1].content.lower()

    if "research" in query:
        return "researcher"
    elif "write" in query:
        return "writer"
    return "supervisor"
```

### State Schema Isolation

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph

class IsolatedState(TypedDict):
    """State with isolated context fields."""
    messages: list  # What LLM sees
    internal_data: dict  # Internal tracking, not exposed to LLM
    metadata: dict  # Metadata for routing/decisions

def agent_node(state: IsolatedState):
    """LLM only sees 'messages' field."""
    # internal_data and metadata are hidden from LLM
    return {
        "messages": [model.invoke(state["messages"])],
        "internal_data": {"step_count": state["internal_data"].get("step_count", 0) + 1}
    }
```

### Sandbox Isolation

```python
# Using E2B or similar for code execution
from e2b import Sandbox

def code_execution_node(state: AgentState):
    """Execute code in isolated sandbox."""
    code = state["messages"][-1].content

    with Sandbox() as sandbox:
        # Run code in isolated environment
        result = sandbox.run_code(code)

        # Only pass back selected results
        output = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            # Don't pass back full environment
        }

    return {
        "messages": [ToolMessage(content=str(output), tool_call_id=...)]
    }
```

## Context Engineering Patterns

### Pattern: Hierarchical Summarization

```python
def hierarchical_summarize(state: AgentState):
    """Summarize at multiple levels."""
    messages = state["messages"]

    if len(messages) > 100:
        # Level 1: Summarize earliest 50 messages
        early_summary = model.summarize(messages[:50])
        # Level 2: Summarize middle 50 messages
        middle_summary = model.summarize(messages[50:100])
        # Level 3: Keep last 20 messages as-is

        return {
            "messages": [
                SystemMessage(content=f"Early context: {early_summary}"),
                SystemMessage(content=f"Middle context: {middle_summary}"),
                *messages[-20:]
            ]
        }
```

### Pattern: Sliding Window

```python
def sliding_window_context(state: AgentState):
    """Maintain sliding window of recent context."""
    all_messages = state["messages"]

    # Always keep: system, last 3 turns, and any flagged important messages
    important = [m for m in all_messages if m.metadata.get("important")]
    recent = all_messages[-6:]

    return {"messages": important + recent}
```

## Best Practices

1. **Measure before optimizing**: Track token usage at each step
2. **Layer your strategies**: Combine write, select, compress, isolate
3. **Test compression impact**: Verify summarization doesn't lose key info
4. **Use embeddings for selection**: Better than keyword matching
5. **Consider agent needs**: Different agents need different context strategies

## References

- [Context Engineering Blog](https://blog.langchain.com/context-engineering-for-agents/)
- [LangGraph Memory Concepts](https://langchain-ai.github.io/langgraph/concepts/memory/)
