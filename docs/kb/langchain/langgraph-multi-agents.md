# LangGraph Multi-Agent Systems - Knowledge Base

## Overview

Multi-agent systems divide complex problems into tractable units handled by specialized agents. Each agent can have its own prompt, LLM, tools, and context window, working together under coordination patterns.

## Multi-Agent Patterns

### 1. Supervisor Pattern

A central supervisor agent routes to specialized sub-agents:

```python
from langgraph.graph import StateGraph, MessagesState, END, START
from typing import Literal, TypedDict

# Define agents
def research_agent(state: MessagesState):
    """Research specialist."""
    return {"messages": research_model.invoke(state["messages"])}

def coding_agent(state: MessagesState):
    """Coding specialist."""
    return {"messages": coding_model.invoke(state["messages"])}

def writing_agent(state: MessagesState):
    """Writing specialist."""
    return {"messages": writing_model.invoke(state["messages"])}

# Supervisor decides which agent to call
def supervisor_node(state: MessagesState) -> Literal["research", "coding", "writing", "end"]:
    """Route to appropriate agent."""
    response = supervisor_model.invoke(
        f"Given this state: {state['messages']}\n"
        "Which agent should act next? Choose: research, coding, writing, or end"
    )
    return response.content

# Build graph
workflow = StateGraph(MessagesState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("research", research_agent)
workflow.add_node("coding", coding_agent)
workflow.add_node("writing", writing_agent)

# Each agent reports back to supervisor
workflow.add_edge("research", "supervisor")
workflow.add_edge("coding", "supervisor")
workflow.add_edge("writing", "supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    supervisor_node,
    {
        "research": "research",
        "coding": "coding",
        "writing": "writing",
        "end": END
    }
)

workflow.add_edge(START, "supervisor")
graph = workflow.compile()
```

### 2. Collaboration Pattern (Shared Scratchpad)

Agents work on a shared message list:

```python
from langgraph.graph import StateGraph

class CollaborativeState(TypedDict):
    messages: list  # All agents see all messages
    agent_assignments: dict

def agent_a(state: CollaborativeState):
    """Agent A contributes to shared state."""
    # Sees all previous messages
    # Adds its contribution to shared list
    return {
        "messages": [AIMessage(content="Agent A's analysis...")]
    }

def agent_b(state: CollaborativeState):
    """Agent B sees Agent A's work."""
    # Can see Agent A's messages
    # Adds its contribution
    return {
        "messages": [AIMessage(content="Agent B's response to A...")]
    }

workflow = StateGraph(CollaborativeState)
workflow.add_node("agent_a", agent_a)
workflow.add_node("agent_b", agent_b)

# Agents work sequentially on shared state
workflow.add_edge(START, "agent_a")
workflow.add_edge("agent_a", "agent_b")
workflow.add_edge("agent_b", END)
```

### 3. Hierarchical Teams

Agents that are themselves graphs:

```python
# Sub-agent: Research team
def build_research_team():
    """Build a sub-graph for research."""
    subworkflow = StateGraph(MessagesState)
    subworkflow.add_node("web_search", web_search_node)
    subworkflow.add_node("paper_search", paper_search_node)
    # ... more research nodes
    return subworkflow.compile()

research_team = build_research_team()

# Sub-agent: Writing team
def build_writing_team():
    """Build a sub-graph for writing."""
    subworkflow = StateGraph(MessagesState)
    subworkflow.add_node("draft", draft_node)
    subworkflow.add_node("edit", edit_node)
    # ... more writing nodes
    return subworkflow.compile()

writing_team = build_writing_team()

# Main supervisor
def supervisor(state):
    """Route to sub-team."""
    # Decide research vs writing
    pass

workflow = StateGraph(MessagesState)
workflow.add_node("supervisor", supervisor)
workflow.add_node("research_team", research_team)
workflow.add_node("writing_team", writing_team)
```

## Multi-Agent Communication

### Message Passing

```python
class AgentMessage(TypedDict):
    sender: str  # Which agent sent this
    recipient: str  # Which agent should receive
    content: str
    timestamp: str

class MultiAgentState(TypedDict):
    messages: list[AgentMessage]
    agent_states: dict  # Per-agent state

def agent_send(state: MultiAgentState):
    """Agent sends a message to another."""
    return {
        "messages": [{
            "sender": "agent_a",
            "recipient": "agent_b",
            "content": "Here's what I found...",
            "timestamp": "..."
        }]
    }

def agent_receive(state: MultiAgentState):
    """Agent processes messages meant for it."""
    my_messages = [
        m for m in state["messages"]
        if m["recipient"] == "agent_b"
    ]
    # Process only messages meant for this agent
```

### Broadcast vs Point-to-Point

```python
# Broadcast: All agents see all messages
class BroadcastState(TypedDict):
    messages: list  # Shared by all

# Point-to-point: Agents have private messages
class PrivateState(TypedDict):
    shared_context: dict  # Everyone sees this
    agent_a_inbox: list
    agent_b_inbox: list
```

## Multi-Agent Libraries

### langgraph-supervisor-py

```python
from langgraph_supervisor import Supervisor, create_supervisor_graph

# Define agents
researcher = create_agent("gpt-4o", tools=[search, web_scraper])
coder = create_agent("gpt-4o", tools=[execute_code, read_file])
writer = create_agent("gpt-4o", tools=[write_file])

# Create supervisor
supervisor = Supervisor(
    name="coordinator",
    agents=[researcher, coder, writer],
    prompt="You coordinate between research, coding, and writing agents."
)

# Compile into graph
graph = create_supervisor_graph(supervisor)
```

### langgraph-swarm-py

```python
from langgraph_swarm import create_swarm, Agent

# Define specialized agents
agents = [
    Agent(
        name="researcher",
        instructions="You research topics using web search.",
        tools=[search]
    ),
    Agent(
        name="coder",
        instructions="You write and execute code.",
        tools=[python_repl]
    ),
    Agent(
        name="writer",
        instructions="You write documentation.",
        tools=[]
    )
]

# Swarm coordinates handoffs
swarm = create_swarm(agents)
result = swarm.run("Research and document the Python asyncio library")
```

## Multi-Agent Considerations

### Token Usage

Multi-agent systems can use significantly more tokens:

```python
# Estimate token usage before running
def estimate_tokens(state: MultiAgentState):
    """Estimate total tokens across all agents."""
    total = 0
    for agent_messages in state["agent_states"].values():
        total += sum(count_tokens(m) for m in agent_messages)
    return total

# Add guardrail
def token_guard(state: MultiAgentState):
    """Prevent excessive token usage."""
    if estimate_tokens(state) > MAX_TOKENS:
        return {"error": "Token limit exceeded"}
    return state
```

### Coordination Challenges

```python
# Add coordination metadata
class CoordinatedState(TypedDict):
    messages: list
    current_agent: str
    handoff_history: list  # Track who talked to whom

def handoff(state: CoordinatedState, next_agent: str):
    """Hand off from current agent to next."""
    return {
        "handoff_history": [{
            "from": state["current_agent"],
            "to": next_agent,
            "timestamp": "..."
        }],
        "current_agent": next_agent
    }
```

### Parallel Execution

```python
from langgraph.graph import Send

# Parallel branch execution
def map_parallel_work(state):
    """Fan out to multiple agents in parallel."""
    items = state["items_to_process"]
    # Send each item to a separate agent instance
    return [Send("agent_node", {"item": item}) for item in items]

workflow.add_conditional_edges(
    "start",
    map_parallel_work,
    ["agent_node"]
)
```

## When to Use Multi-Agent

| Single Agent | Multi-Agent |
|--------------|-------------|
| Simple, focused tasks | Complex, multi-step problems |
| Small tool set | Many specialized tools |
| Low token budget | Sufficient budget for overhead |
| Sequential reasoning | Parallel exploration possible |

## Best Practices

1. **Start simple**: Begin with single agent, add more as needed
2. **Clear responsibilities**: Each agent should have a clear purpose
3. **Minimal shared state**: Reduces confusion and token usage
4. **Monitor handoffs**: Track how agents coordinate
5. **Test incrementally**: Add agents one at a time

## References

- [Multi-Agent Workflows](https://blog.langchain.com/langgraph-multi-agent-workflows/)
- [Multi-Agent Examples](https://github.com/langchain-ai/langgraph/tree/main/examples/multi_agent)
- [langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py)
