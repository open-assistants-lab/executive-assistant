# LangChain Agents - Knowledge Base

## Overview

LangChain agents combine language models with tools to create systems that can reason about tasks, decide which tools to use, and iteratively work towards solutions. The `create_agent` function provides a production-ready agent implementation built on LangGraph.

## Key Concepts

### Agent Loop

The agent follows the ReAct ("Reasoning + Acting") pattern:

1. **Reasoning**: LLM decides what action to take
2. **Acting**: Execute tool(s) with appropriate parameters
3. **Observation**: Process tool results
4. **Iteration**: Repeat until final answer or stop condition

### Graph-Based Runtime

`create_agent` builds a **graph-based agent runtime** using LangGraph. A graph consists of:
- **Nodes**: Processing steps (model node, tools node, middleware)
- **Edges**: Connections between nodes

The agent moves through this graph, executing nodes until a stop condition is met.

## create_agent API

```python
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-4o",                    # or ChatOpenAI(...)
    tools=[tool1, tool2],              # tools for agent to use
    system_prompt="You are helpful",   # optional system prompt
    middleware=[...],                  # optional middleware
    checkpointer=MemorySaver(),        # optional state persistence
    response_format=...,               # optional structured output
    state_schema=...,                  # optional custom state
    context_schema=...,                # optional runtime context
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str \| BaseChatModel` | Required | Model identifier or instance |
| `tools` | `Sequence[Tool]` | `None` | Tools for agent to use |
| `system_prompt` | `str \| SystemMessage` | `None` | Optional system prompt |
| `middleware` | `Sequence[AgentMiddleware]` | `()` | Middleware to apply |
| `checkpointer` | `Checkpointer` | `None` | State persistence (e.g., MemorySaver) |
| `response_format` | `ResponseFormat \| type` | `None` | Structured output configuration |
| `state_schema` | `type[AgentState]` | `None` | Custom state schema (TypedDict) |
| `context_schema` | `type` | `None` | Runtime context schema |
| `store` | `BaseStore` | `None` | Cross-thread persistence |

## Model Selection

### Static Model
```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,
    max_tokens=1000,
)

agent = create_agent(model, tools=tools)
```

### Dynamic Model (via Middleware)
```python
from langchain.agents.middleware import wrap_model_call, ModelRequest

basic_model = ChatOpenAI(model="gpt-4o-mini")
advanced_model = ChatOpenAI(model="gpt-4o")

@wrap_model_call
def dynamic_model(request: ModelRequest, handler):
    if len(request.state["messages"]) > 10:
        return handler(request.override(model=advanced_model))
    return handler(request.override(model=basic_model))

agent = create_agent(
    model=basic_model,
    tools=tools,
    middleware=[dynamic_model_selection]
)
```

## Tools

Tools can be specified as:
- Plain Python functions
- Async functions
- Functions decorated with `@tool`

```python
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def get_weather(location: str) -> str:
    """Get weather information."""
    return f"Weather in {location}: Sunny, 72°F"

agent = create_agent(model, tools=[search, get_weather])
```

### Tool Error Handling

Use `@wrap_tool_call` decorator for custom error handling:

```python
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

@wrap_tool_call
def handle_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception as e:
        return ToolMessage(
            content=f"Tool error: {e}",
            tool_call_id=request.tool_call["id"]
        )

agent = create_agent(
    model,
    tools=[search, get_weather],
    middleware=[handle_tool_errors]
)
```

## System Prompt

### Static System Prompt
```python
agent = create_agent(
    model,
    tools,
    system_prompt="You are a helpful assistant. Be concise."
)
```

### Dynamic System Prompt (via Middleware)
```python
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dynamic_prompt
def user_role_prompt(request: ModelRequest) -> str:
    user_role = request.runtime.context.get("user_role", "user")
    base = "You are a helpful assistant."

    if user_role == "expert":
        return f"{base} Provide technical responses."
    elif user_role == "beginner":
        return f"{base} Explain simply."
    return base

agent = create_agent(
    model="gpt-4o",
    tools=[search],
    middleware=[user_role_prompt],
    context_schema=Context  # TypedDict with user_role
)
```

## Memory and State

### Short-term Memory
Agents maintain conversation history through the message state automatically.

### Custom State
Extend `AgentState` to track additional information:

```python
from langchain.agents import AgentState
from typing import TypedDict

class CustomState(AgentState):
    user_preferences: dict

agent = create_agent(
    model,
    tools=[tool1, tool2],
    state_schema=CustomState
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "Hi"}],
    "user_preferences": {"style": "technical"}
})
```

## Invocation

```python
# Single invocation
result = agent.invoke({
    "messages": [{"role": "user", "content": "What's the weather?"}]
})

# Streaming
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "Search news"}]},
    stream_mode="values"
):
    latest_message = chunk["messages"][-1]
    print(f"Agent: {latest_message.content}")
```

## Structured Output

### ToolStrategy (works with any model with tool calling)
```python
from pydantic import BaseModel
from langchain.agents.structured_output import ToolStrategy

class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str

agent = create_agent(
    model="gpt-4o-mini",
    tools=[search_tool],
    response_format=ToolStrategy(ContactInfo)
)
```

### ProviderStrategy (provider-native, more reliable)
```python
from langchain.agents.structured_output import ProviderStrategy

agent = create_agent(
    model="gpt-4o",
    response_format=ProviderStrategy(ContactInfo)
)
```

## Best Practices

1. **Compile once, reuse** - Build the agent at startup, not per request
2. **Stable thread_id** - Pass consistent `thread_id` via config for checkpointed state
3. **Controlled loops** - Use middleware call limits rather than custom counters
4. **Don't reimplement ReAct** - Let `create_agent` handle the tool loop

## References

- [Agents Documentation](https://docs.langchain.com/oss/python/langchain/agents)
- [API Reference](https://reference.langchain.com/python/langchain/agents/)
