# LangGraph Subgraphs - Knowledge Base

## Overview

Subgraphs allow you to compose complex agents from reusable graph components. A subgraph is a LangGraph that can be called as a node within another graph, enabling modular design and code reuse.

## Basic Subgraph

### Defining a Subgraph

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# Subgraph state
class SubgraphState(TypedDict):
    input: str
    processed: list[str]
    output: str

# Subgraph nodes
def step_a(state: SubgraphState):
    return {"processed": state["processed"] + ["a"]}

def step_b(state: SubgraphState):
    return {"processed": state["processed"] + ["b"]}

def step_c(state: SubgraphState):
    return {
        "processed": state["processed"] + ["c"],
        "output": "done"
    }

# Build subgraph
sub_builder = StateGraph(SubgraphState)
sub_builder.add_node("a", step_a)
sub_builder.add_node("b", step_b)
sub_builder.add_node("c", step_c)
sub_builder.add_edge(START, "a")
sub_builder.add_edge("a", "b")
sub_builder.add_edge("b", "c")
sub_builder.add_edge("c", END)

subgraph = sub_builder.compile()
```

### Using Subgraph in Parent Graph

```python
# Parent graph state
class ParentState(TypedDict):
    query: str
    subgraph_result: str

# Add subgraph as a node
parent_builder = StateGraph(ParentState)
parent_builder.add_node("subtask", subgraph)  # Subgraph as node!

# Connect like any other node
parent_builder.add_edge(START, "subtask")
parent_builder.add_edge("subtask", END)

parent_graph = parent_builder.compile()
```

## State Mapping Between Graphs

### Input/Output Mapping

```python
from langgraph.graph import StateGraph

# Parent state
class ParentState(TypedDict):
    user_query: str
    research_result: dict

# Subgraph state (different structure)
class ResearchState(TypedDict):
    query: str
    sources: list
    answer: str

# Build subgraph
research_graph = StateGraph(ResearchState)
# ... add nodes ...

# Parent graph with state mapping
parent_graph = StateGraph(ParentState)

def call_research(state: ParentState):
    """Call subgraph with state mapping."""
    # Map parent state -> subgraph input
    sub_input = {"query": state["user_query"]}

    # Invoke subgraph
    sub_output = research_graph.invoke(sub_input)

    # Map subgraph output -> parent state
    return {"research_result": {"answer": sub_output["answer"]}}

parent_graph.add_node("research", call_research)
```

### Using send() for Dynamic Subgraph Calls

```python
from langgraph.graph import Send

def map_subtasks(state: ParentState):
    """Fan out to multiple subgraph instances."""
    items = state["items_to_process"]

    # Create dynamic subgraph calls
    return [
        Send(
            "subgraph_node",
            {"input": item}  # Subgraph input
        )
        for item in items
    ]

# Route to subgraph
parent_graph.add_conditional_edges(
    "start",
    map_subtasks,
    ["subgraph_node"]
)
```

## Nested Subgraphs

Subgraphs can contain other subgraphs:

```python
# Level 3: Innermost subgraph
level3 = StateGraph(State3)
# ... define ...
level3_graph = level3.compile()

# Level 2: Contains level 3
level2 = StateGraph(State2)
level2.add_node("inner", level3_graph)  # Nested!
level2_graph = level2.compile()

# Level 1: Contains level 2
level1 = StateGraph(State1)
level1.add_node("middle", level2_graph)  # Nested!
level1_graph = level1.compile()
```

## Modular Agent Patterns

### Pattern: Reusable Tool Wrapper

```python
def create_tool_subgraph(tool):
    """Create a subgraph that wraps a tool with validation."""
    class ToolState(TypedDict):
        input: dict
        output: Any
        validated: bool

    def validate(state: ToolState):
        # Validate input
        if not is_valid(state["input"]):
            raise ValueError("Invalid input")
        return state

    def execute(state: ToolState):
        # Execute tool
        result = tool(**state["input"])
        return {"output": result}

    def post_process(state: ToolState):
        # Post-process result
        return {"validated": True}

    builder = StateGraph(ToolState)
    builder.add_node("validate", validate)
    builder.add_node("execute", execute)
    builder.add_node("post_process", post_process)
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "execute")
    builder.add_edge("execute", "post_process")
    builder.add_edge("post_process", END)

    return builder.compile()

# Use in main graph
search_tool_subgraph = create_tool_subgraph(search_tool)
main_graph.add_node("search", search_tool_subgraph)
```

### Pattern: Conditional Subgraph Selection

```python
def route_to_subgraph(state: ParentState) -> str:
    """Select which subgraph to use."""
    task_type = state.get("task_type")

    if task_type == "research":
        return "research_subgraph"
    elif task_type == "write":
        return "write_subgraph"
    elif task_type == "code":
        return "code_subgraph"
    return "default"

# Add all subgraphs as nodes
parent_graph.add_node("research_subgraph", research_graph)
parent_graph.add_node("write_subgraph", write_graph)
parent_graph.add_node("code_subgraph", code_graph)
parent_graph.add_node("default", default_graph)

# Route to appropriate subgraph
parent_graph.add_conditional_edges(
    "router",
    route_to_subgraph,
    {
        "research_subgraph": "research_subgraph",
        "write_subgraph": "write_subgraph",
        "code_subgraph": "code_subgraph",
        "default": "default"
    }
)
```

## Subgraph Communication

### Shared State Across Subgraphs

```python
class SharedState(TypedDict):
    messages: list
    shared_context: dict  # Accessible to all subgraphs

def subgraph_a(state: SharedState):
    # Can read/write shared_context
    return {"shared_context": {"a_result": "done"}}

def subgraph_b(state: SharedState):
    # Sees what A wrote
    a_result = state["shared_context"].get("a_result")
    return {"shared_context": {"b_result": f"Based on {a_result}"}}
```

### Isolated Subgraph State

```python
# Each subgraph has private state
def subgraph_with_private_state(state: SharedState):
    # Parent state is accessible, but subgraph maintains private state internally
    pass
```

## Subgraph Best Practices

1. **Clear interfaces**: Define explicit input/output schemas
2. **Single responsibility**: Each subgraph does one thing well
3. **Test independently**: Subgraphs should be testable standalone
4. **Document contracts**: Clearly document expected inputs/outputs
5. **Limit nesting**: Deep nesting makes debugging hard

## Visualizing Subgraphs

```python
from IPython.display import Image, display

# Visualize parent graph with subgraphs
display(parent_graph.get_graph().draw_mermaid_png())

# Subgraphs show as nested nodes in visualization
```

## References

- [LangGraph Subgraphs](https://langchain-ai.github.io/langgraph/how-tos/subgraph/)
- [Graph API Reference](https://langchain-ai.github.io/langgraph/reference/graphs/)
