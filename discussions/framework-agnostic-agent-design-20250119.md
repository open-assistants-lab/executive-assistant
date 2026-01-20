# Framework Agnostic Agent Runtime Design

**Date:** 2026-01-19
**Status:** Design Discussion
**Priority:** Medium

## Motivation

Executive Assistant is currently tightly coupled to LangChain/LangGraph for its agent runtime. This creates:
- **Vendor lock-in** - Hard to switch to newer/better frameworks
- **Dependency bloat** - Full LangChain install even for simple use cases
- **Framework limitations** - Constrained by LangChain's design decisions

Goal: Enable swapping agent frameworks via config (like we swap LLM providers).

## Current LangChain Dependencies

### 1. Tools (~1000 lines)
All tools use `@tool` decorator from `langchain_core.tools`:
```python
from langchain_core.tools import tool

@tool
def search_web(query: str, num_results: int = 5) -> str:
    """Search the web using SearXNG."""
    ...
```

**Impact:** Medium - need decorator/adapter layer

### 2. Agent Runtime (~200 lines)
`src/executive_assistant/agent/langchain_agent.py`:
```python
from langchain.agents import create_agent
from langgraph.types import Runnable

def create_langchain_agent(model, tools, checkpointer, system_prompt, channel):
    agent = create_agent(
        model,
        tools,
        prompt=system_prompt,
        middleware=[...],
        checkpointer=checkpointer,
    )
    return agent.compile()
```

**Impact:** High - core replacement needed

### 3. Middleware (~500 lines)
LangChain's middleware system:
- `SummarizationMiddleware`
- `ModelCallLimitMiddleware`
- `ToolCallLimitMiddleware`
- `ToolRetryMiddleware`
- `ModelRetryMiddleware`
- `TodoListMiddleware`
- `ContextEditingMiddleware`

**Impact:** High - rebuild or adapter layer

### 4. Checkpoint/State (~300 lines)
`BaseCheckpointSaver` for conversation persistence:
```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

checkpointer = PostgresSaver.from_conn_string(psycopg_conn_string)
```

**Impact:** High - state management core

### 5. Message Types (~50 lines)
```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
```

**Impact:** Medium - format differences

### 6. Streaming (~100 lines)
Channels consume LangGraph event stream:
```python
async for event in self.agent.astream(state, config):
    for msg in self._extract_messages_from_event(event):
        messages.append(msg)
```

**Impact:** Medium - parsing differences

## Proposed Architecture

### Common Agent Interface

Create an abstraction layer that all frameworks must implement:

```python
# src/executive_assistant/agent/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class AgentFramework(ABC):
    """Abstract base for agent framework implementations."""

    @abstractmethod
    async def astream(
        self,
        messages: list[BaseMessage],
        config: dict,
    ) -> AsyncIterator[AgentEvent]:
        """Stream agent execution events."""
        pass

    @abstractmethod
    def get_checkpoint_saver(self) -> BaseCheckpointSaver:
        """Get framework's checkpoint saver."""
        pass

    @abstractmethod
    def adapt_tools(self, tools: list[Callable]) -> list[Any]:
        """Convert our tools to framework's format."""
        pass
```

### Framework Implementations

```
src/executive_assistant/agent/
├── base.py              # Common interface
├── langchain_runtime.py # LangChain implementation (current)
├── agno_runtime.py      # Agno implementation (future)
└── factory.py           # Create based on AGENT_RUNTIME setting
```

### Tool Adapter Layer

```python
# src/executive_assistant/tools/adapter.py
from typing import Callable, Any

class ToolAdapter:
    """Adapt our tools to different frameworks."""

    @staticmethod
    def to_langchain(fn: Callable) -> BaseTool:
        from langchain_core.tools import tool
        return tool(fn)

    @staticmethod
    def to_agno(fn: Callable) -> Any:
        from agno import Tool
        return Tool.from_function(fn)
```

### Checkpoint Abstraction

```python
# src/executive_assistant/storage/checkpoint.py
class CheckpointSaver(ABC):
    @abstractmethod
    async def get(self, thread_id: str) -> dict | None:
        pass

    @abstractmethod
    async def put(self, thread_id: str, state: dict) -> None:
        pass

class PostgresCheckpointSaver(CheckpointSaver):
    # Framework-agnostic PostgreSQL implementation
```

## Implementation Estimate

| Component | Lines | Effort | Notes |
|-----------|-------|--------|-------|
| Agent interface (base.py) | ~100 | 1 day | Define contracts |
| LangChain adapter | ~200 | 2 days | Wrap current code |
| Tool adapters | ~100 | 1 day | Decorator layer |
| Checkpoint abstraction | ~300 | 3-5 days | Serialize/deserialize state |
| Agno runtime (new) | ~800 | 1-2 weeks | Full implementation |
| Middleware adapters | ~500 | 5-7 days | Bridge framework differences |
| Channel updates | ~100 | 1 day | Use common interface |
| Testing | ~500 | 5-10 days | Comprehensive coverage |

**Total: 3-5 weeks for full migration**

## Phased Approach

### Phase 1: Abstraction Layer (1 week)
- Create `AgentFramework` base class
- Wrap current LangChain code as `LangChainRuntime`
- Create tool adapter interface
- No behavior changes

### Phase 2: Checkpoint Abstraction (1 week)
- Create `CheckpointSaver` interface
- Implement `PostgresCheckpointSaver`
- Migrate existing checkpoints
- Test data integrity

### Phase 3: First Alternative (2-3 weeks)
- Implement `AgnoRuntime`
- Port middleware concepts
- Test feature parity
- Performance comparison

### Phase 4: Hardening (1 week)
- Comprehensive testing
- Documentation
- Migration guide

## Benefits

1. **Flexibility** - Switch frameworks without rewriting tools/storage
2. **Testing** - A/B test different frameworks
3. **Future-proof** - Adopt new frameworks as they emerge
4. **Optimization** - Use lighter framework for simple use cases

## Risks

1. **Least common denominator** - Abstraction may limit framework features
2. **Maintenance burden** - Multiple implementations to maintain
3. **Debugging complexity** - More layers to troubleshoot
4. **Partial implementation** - Some features may not translate

## Alternatives Considered

### Alternative 1: Keep LangChain Only
- **Pros:** Simple, well-supported, mature
- **Cons:** Vendor lock-in, heavy dependencies

### Alternative 2: Fork LangChain
- **Pros:** Full control, can strip unused features
- **Cons:** Maintenance burden, miss upstream improvements

### Alternative 3: Minimal Custom Agent
- **Pros:** Zero dependencies, full control
- **Cons:** Reimplement wheels (middleware, streaming, etc.)

## Recommendation

**Proceed with Phase 1 only initially:**
1. Create abstraction layer
2. Wrap current LangChain implementation
3. Validate the approach

Then reassess based on:
- Clear pain points with LangChain
- Maturity of alternatives (Agno, etc.)
- Team bandwidth

## Alternative Frameworks to Consider

Beyond Agno, here are other AI agent frameworks worth evaluating for 2025:

### Framework Comparison Matrix

| Framework | Language | Core Paradigm | MCP Support | Summarization | Best For |
|-----------|----------|---------------|-------------|---------------|----------|
| **LangGraph** | Python | Graph-based workflows | Via adapter | Middleware-based | Complex enterprise workflows |
| **Agno** | Python | Lightweight agent | ✅ Native | ✅ Built-in | Fast iteration, MCP-heavy apps |
| **PydanticAI** | Python | Type-safe agents | Via adapter | Manual | Production type safety |
| **CrewAI** | Python | Role-based teams | Via adapter | Basic | Multi-agent collaboration |
| **AutoGen** | Python | Conversational multi-agent | Via adapter | Manual | Complex multi-agent dialogues |
| **Smolagents** | Python | Code-centric | Via adapter | Basic | Minimal, code-first workflows |
| **OpenAI Agents SDK** | Python | OpenAI-native | Via adapter | Native | OpenAI ecosystem users |
| **Semantic Kernel** | Python/C# | Enterprise plugin | Via adapter | Manual | Microsoft/.NET shops |
| **LlamaIndex Agents** | Python | RAG-focused | Via adapter | RAG-native | Data-intensive applications |
| **Strands Agents** | Python | Model-agnostic | Via adapter | Manual | AWS-integrated apps |

---

### Detailed Analysis

#### 1. PydanticAI (by Modal)
**GitHub:** https://github.com/pydantic-ai/pydantic-ai

**Strengths:**
- **Type safety**: Pydantic-powered validation for agent inputs/outputs
- **Production-ready**: FastAPI-style developer experience
- **Clean DX**: Minimal boilerplate, excellent error messages
- **Structured outputs**: First-class support for structured responses

**Weaknesses:**
- Newer project (smaller community)
- Less built-in middleware than LangChain
- MCP support requires adapter

**Code Example:**
```python
from pydantic_ai import Agent

agent = Agent(
    'openai:gpt-4o',
    system_prompt='You are a helpful assistant',
)

result = agent.run_sync('What is the capital of France?')
```

**When to consider:** If type safety and production robustness are top priorities, and you're okay with a smaller ecosystem.

---

#### 2. CrewAI
**GitHub:** https://github.com/crewAIInc/crewAI

**Strengths:**
- **Role-based agents**: Define agents with specific roles/personas
- **Multi-agent orchestration**: Built-in support for agent teams
- **Process flows**: Sequential, hierarchical, or consensus-based execution
- **Visual debugger**: GUI for watching agent collaboration

**Weaknesses:**
- Heavier weight (not minimal)
- Less flexible for single-agent use cases
- MCP requires adapter

**Code Example:**
```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role='Researcher',
    goal='Find information',
    backstory='You are an expert researcher',
)

task = Task(description='Research AI trends')
crew = Crew(agents=[researcher], tasks=[task])
crew.kickoff()
```

**When to consider:** If you need multiple specialized agents collaborating (researcher + writer + reviewer pattern).

---

#### 3. AutoGen (Microsoft)
**GitHub:** https://github.com/microsoft/autogen

**Strengths:**
- **Microsoft-backed**: Active development, enterprise support
- **Conversational agents**: Agents talk to each other naturally
- **Code execution**: Built-in safe code execution environments
- **Human-in-the-loop**: Easy human approval/feedback patterns

**Weaknesses:**
- Verbose API (lots of boilerplate)
- Originally synchronous (async support is newer)
- MCP requires adapter

**Code Example:**
```python
from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent(
    name="assistant",
    llm_config={"model": "gpt-4"},
)

user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="NEVER",
)
user_proxy.initiate_chat(assistant, message="Hello!")
```

**When to consider:** If you need complex multi-agent conversations with Microsoft ecosystem integration.

---

#### 4. Smolagents (HuggingFace)
**GitHub:** https://github.com/huggingface/smolagents

**Strengths:**
- **Minimal**: ~500 lines of core code
- **Code-centric**: Agents write and execute Python code
- **HuggingFace integration**: Direct access to HF models/tools
- **Fast**: Very low overhead

**Weaknesses:**
- Code execution focus (not for all use cases)
- Limited middleware ecosystem
- Requires safe execution environment

**Code Example:**
```python
from smolagents import CodeAgent

agent = CodeAgent(
    model="HuggingFaceH4/zephyr-7b-beta",
    tools=[web_search_tool],
)
agent.run("Find the latest AI news")
```

**When to consider:** For code-generation agents or when minimal dependencies are critical.

---

#### 5. OpenAI Agents SDK
**Docs:** https://platform.openai.com/docs/agents

**Strengths:**
- **Official OpenAI**: First-class access to new features
- **Native tools**: Direct integration with OpenAI's tools ecosystem
- **Built-in summarization**: Native conversation summarization
- **Optimized for GPT-4**: Best performance on OpenAI models

**Weaknesses:**
- OpenAI vendor lock-in
- Not model-agnostic
- Limited non-OpenAI tool support

**When to consider:** If you're fully committed to OpenAI's ecosystem and don't need multi-model support.

---

#### 6. Semantic Kernel (Microsoft)
**GitHub:** https://github.com/microsoft/semantic-kernel

**Strengths:**
- **Enterprise-grade**: Microsoft's production framework
- **Multi-language**: Python, C#, Java
- **Plugin system**: Extensive enterprise plugin ecosystem
- **Azure integration**: Deep Azure services integration

**Weaknesses:**
- .NET-first (Python is secondary)
- Verbose configuration
- Heavier weight

**When to consider:** For enterprise .NET shops or Azure-heavy deployments.

---

#### 7. LlamaIndex Agents
**Docs:** https://docs.llamaindex.ai/

**Strengths:**
- **RAG-native**: Built for retrieval-augmented generation
- **Data connectors**: 100+ data source integrations
- **Vector store abstraction**: Clean vector database abstraction
- **Index-based**: Optimized for knowledge-intensive tasks

**Weaknesses:**
- RAG-focused (less general-purpose)
- More complexity for simple agents
- MCP via adapter

**When to consider:** If your use case is primarily RAG / knowledge base querying.

---

#### 8. Strands Agents
**Docs:** https://docs.strands.ai/

**Strengths:**
- **Model-agnostic**: Easy model swapping
- **AWS integration**: Bedrock, Lambda, etc.
- **Clean abstractions**: Simple mental model
- **Production-focused**: Built for production workloads

**Weaknesses:**
- Smaller community
- Less mature than LangChain
- Commercial product (not fully open)

**When to consider:** If you're on AWS and want a production-focused framework.

---

### Selection Criteria

| Criteria | Weight | Notes |
|----------|--------|-------|
| **MCP Support** | High | Executive Assistant uses MCP heavily; native support preferred |
| **Summarization** | High | Critical for long conversations |
| **Type Safety** | Medium | Production robustness |
| **Community** | Medium | Documentation, examples, troubleshooting |
| **Performance** | Medium | Speed, memory usage |
| **Learning Curve** | Low | Team onboarding time |

### Quick Recommendations

| If you want... | Consider... |
|----------------|-------------|
| Drop-in LangChain replacement | **Agno** |
| Type safety + production | **PydanticAI** |
| Multi-agent teams | **CrewAI** or **AutoGen** |
| RAG-heavy apps | **LlamaIndex Agents** |
| Azure/.NET focus | **Semantic Kernel** |
| OpenAI-only | **OpenAI Agents SDK** |
| Minimal dependencies | **Smolagents** |

---

## Research Sources

- LangWatch AI Agents Survey: https://langwatch.ai/blog/ai-agents-landscape-2025
- Langfuse Framework Comparison: https://langfuse.com/blog/agent-frameworks
- ZenML Agent Orchestrator Research: https://blog.zenml.io/agent-frameworks
- Framework official documentation (linked above)

## References

- LangChain Agents: https://python.langchain.com/docs/tutorials/agents
- Agno Framework: https://github.com/emrgnt-cmplxty/agno (if applicable)
- Current implementation: `src/executive_assistant/agent/langchain_agent.py`
