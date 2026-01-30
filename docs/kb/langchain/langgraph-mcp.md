# LangGraph MCP (Model Context Protocol) - Knowledge Base

## Overview

The **Model Context Protocol (MCP)** is an open protocol for describing tools and data sources in a model-agnostic format. LangGraph Agent Server implements MCP, allowing agents to be exposed as MCP tools for use with any MCP-compliant client.

## What is MCP?

MCP enables:
- **Tool Discovery**: LLMs can discover available tools dynamically
- **Standardized Interface**: Model-agnostic tool descriptions
- **Composability**: Chain multiple MCP servers together
- **Protocol Flexibility**: Supports multiple transports (stdio, HTTP, SSE)

## LangGraph MCP Server

### Enabling MCP

MCP is automatically enabled when using `langgraph-api >= 0.2.3`:

```bash
pip install "langgraph-api>=0.2.3" "langgraph-sdk>=0.1.61"
```

The MCP endpoint becomes available at `/mcp` on your Agent Server.

### Exposing an Agent as MCP Tool

Define your agent in `langgraph.json`:

```json
{
  "graphs": {
    "my_agent": {
      "path": "./my_agent/agent.py:graph",
      "title": "My Agent",
      "description": "A helpful agent that does X"
    }
  },
  "env": ".env"
}
```

When deployed, the agent appears as an MCP tool with:
- **Tool name**: Agent's graph name
- **Tool description**: From langgraph.json
- **Input schema**: Agent's input schema

### Custom Schema for MCP

Define explicit input/output schemas for clean MCP integration:

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# Clear input schema
class InputState(TypedDict):
    question: str

# Clear output schema
class OutputState(TypedDict):
    answer: str

# Combined state
class OverallState(InputState, OutputState):
    pass

def answer_node(state: InputState):
    return {"answer": f"Answer to: {state['question']}"}

# Build with explicit schemas
builder = StateGraph(
    OverallState,
    input_schema=InputState,
    output_schema=OutputState
)
builder.add_node("answer", answer_node)
builder.add_edge(START, "answer")
builder.add_edge("answer", END)

graph = builder.compile()
```

## MCP Clients

### JavaScript/TypeScript Client

```javascript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

async function connectClient(url) {
    const client = new Client({
        name: 'my-client',
        version: '1.0.0'
    });

    const transport = new StreamableHTTPClientTransport(new URL(url));
    await client.connect(transport);

    // List available tools
    const tools = await client.listTools();
    console.log(tools);

    return client;
}

const serverUrl = "http://localhost:2024/mcp";
connectClient(serverUrl);
```

### Python Client (using langchain-mcp-adapters)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

server_params = {
    "url": "https://my-agent.example.com/mcp",
    "headers": {"X-Api-Key": "your-api-key"}
}

async def main():
    async with streamablehttp_client(**server_params) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Load remote agent as tools
            tools = await load_mcp_tools(session)

            # Use in local agent
            agent = create_agent("gpt-4o", tools)
            response = await agent.ainvoke({
                "messages": "Use the remote agent to..."
            })
            print(response)

asyncio.run(main())
```

## User-Scoped MCP Tools

Grant users access to their own MCP tools (e.g., GitHub, Google Drive):

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

def mcp_tools_node(state, config):
    """Node that loads user-scoped MCP tools."""
    # Get authenticated user from config
    user = config["configurable"].get("langgraph_auth_user", {})

    # Create client with user's credentials
    client = MultiServerMCPClient({
        "github": {
            "transport": "streamable_http",
            "url": "https://github-mcp-server.com/mcp",
            "headers": {
                "Authorization": f"Bearer {user['github_token']}"
            }
        }
    })

    # Get user's tools
    tools = await client.get_tools()

    # Use tools in agent
    return {"available_tools": tools}
```

**Prerequisites**: Custom auth middleware that populates `langgraph_auth_user`.

## MCP Transport Types

| Transport | Description | Use Case |
|-----------|-------------|----------|
| `stdio` | Standard input/output | Local CLI tools |
| `streamable_http` | HTTP with streaming | Remote servers, web apps |
| `sse` | Server-Sent Events | Real-time updates |

LangGraph Agent Server supports `streamable_http`.

## Disabling MCP

If you don't want to expose MCP:

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "http": {
    "disable_mcp": true
  }
}
```

## MCP Authentication

The `/mcp` endpoint uses the same authentication as the LangGraph API:

```python
# Custom auth middleware
def custom_auth_middleware(request):
    # Validate API key or JWT
    api_key = request.headers.get("X-Api-Key")
    user = validate_api_key(api_key)

    # Make user available in graph config
    request.state.auth_user = user
    return request
```

## MCP vs Direct Tool Calling

| Aspect | MCP | Direct Tool Calling |
|--------|-----|-------------------|
| **Discovery** | Dynamic tool listing | Hardcoded tool list |
| **Transport** | Protocol-agnostic | Framework-specific |
| **Composability** | Easy chaining | Manual orchestration |
| **Auth** | Built-in to protocol | Custom implementation |

## Use Cases

1. **Agent Composition**: Chain multiple agents together via MCP
2. **Tool Federation**: Share tools across multiple agents
3. **Multi-Tenant**: Each tenant has their own MCP server
4. **Hybrid Architectures**: Mix local and remote tools seamlessly

## Best Practices

1. **Define clear schemas**: Use explicit input/output types
2. **Document tools well**: Tool descriptions are all the LLM sees
3. **Scope appropriately**: Use user-scoped tools for personal data
4. **Handle errors gracefully**: MCP tools can fail independently
5. **Monitor usage**: Track which MCP tools are called most

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [LangGraph MCP Server Docs](https://docs.langchain.com/langsmith/server-mcp)
- [MCP SDK (TypeScript)](https://github.com/modelcontextprotocol/typescript-sdk)
- [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
