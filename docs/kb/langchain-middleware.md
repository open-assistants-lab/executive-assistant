# LangChain Middleware - Knowledge Base

## Overview

Middleware provides a way to tightly control what happens inside the agent at various execution stages. Middleware exposes hooks before and after each step in the agent loop.

## What Middleware Can Do

- **Tracking**: Logging, analytics, debugging
- **Transformation**: Prompt modification, tool selection, output formatting
- **Resilience**: Retries, fallbacks, early termination
- **Control**: Rate limits, guardrails, PII detection

## Adding Middleware

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
)

agent = create_agent(
    model="gpt-4o",
    tools=[...],
    middleware=[
        SummarizationMiddleware(...),
        HumanInTheLoopMiddleware(...),
        ModelCallLimitMiddleware(...),
    ],
)
```

## Middleware Flow

The agent loop involves: Model → Tools → Model → ... until done.

Middleware exposes hooks:
- `before_model` - Before model call
- `after_model` - After model response
- `before_tool` - Before tool execution
- `after_tool` - After tool execution

## Built-in Middleware

### 1. SummarizationMiddleware

Automatically summarizes conversation history when approaching token limits.

**Use cases**:
- Long-running conversations exceeding context windows
- Multi-turn dialogues with extensive history

```python
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-4o",
    tools=[...],
    middleware=[
        SummarizationMiddleware(
            model="gpt-4o-mini",
            trigger=("tokens", 4000),        # Trigger when >= 4000 tokens
            keep=("messages", 20),            # Keep last 20 messages
        ),
    ],
)
```

**Configuration**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str \| BaseChatModel` | Required | Model for generating summaries |
| `trigger` | `ContextSize \| list` | Required | When to summarize (tokens, fraction, messages) |
| `keep` | `ContextSize` | `('messages', 20)` | How much context to preserve |
| `token_counter` | `function` | char-based | Custom token counting function |

**Multiple trigger conditions** (OR logic):
```python
SummarizationMiddleware(
    model="gpt-4o-mini",
    trigger=[
        ("tokens", 3000),    # Trigger if >= 3000 tokens
        ("messages", 6),      # OR if >= 6 messages
    ],
    keep=("messages", 20),
)
```

### 2. HumanInTheLoopMiddleware

Pause execution for human approval of tool calls.

**Use cases**:
- High-stakes operations requiring approval
- Compliance workflows
- Long-running conversations with feedback

**Requires**: A checkpointer for state persistence

```python
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_agent(
    model="gpt-4o",
    tools=[send_email_tool, read_email_tool],
    checkpointer=MemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email_tool": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
                "read_email_tool": False,  # Don't interrupt
            }
        ),
    ],
)
```

### 3. ModelCallLimitMiddleware

Limit model calls to prevent excessive costs or infinite loops.

```python
from langchain.agents.middleware import ModelCallLimitMiddleware

agent = create_agent(
    model="gpt-4o",
    checkpointer=MemorySaver(),  # Required for thread limiting
    middleware=[
        ModelCallLimitMiddleware(
            thread_limit=10,    # Max across all runs in thread
            run_limit=5,        # Max per single invocation
            exit_behavior="end",  # "end" | "error"
        ),
    ],
)
```

### 4. ToolCallLimitMiddleware

Limit tool calls globally or for specific tools.

```python
from langchain.agents.middleware import ToolCallLimitMiddleware

agent = create_agent(
    model="gpt-4o",
    tools=[search_tool, database_tool],
    middleware=[
        # Global limit
        ToolCallLimitMiddleware(thread_limit=20, run_limit=10),
        # Tool-specific limit
        ToolCallLimitMiddleware(
            tool_name="search",
            thread_limit=5,
            run_limit=3,
        ),
    ],
)
```

**Exit behaviors**:
- `'continue'` (default) - Block exceeded calls, let agent continue
- `'error'` - Raise exception immediately
- `'end'` - Stop with ToolMessage + AI message (single-tool only)

### 5. ModelFallbackMiddleware

Automatically fallback to alternative models when primary fails.

```python
from langchain.agents.middleware import ModelFallbackMiddleware

agent = create_agent(
    model="gpt-4o",
    middleware=[
        ModelFallbackMiddleware(
            "gpt-4o-mini",              # First fallback
            "claude-3-5-sonnet-20241022",  # Second fallback
        ),
    ],
)
```

### 6. PIIMiddleware

Detect and handle PII in conversations.

```python
from langchain.agents.middleware import PIIMiddleware

agent = create_agent(
    model="gpt-4o",
    middleware=[
        PIIMiddleware("email", strategy="redact", apply_to_input=True),
        PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
    ],
)
```

**Strategies**:
- `'block'` - Raise exception
- `'redact'` - Replace with `[REDACTED_{TYPE}]`
- `'mask'` - Partially mask (e.g., `****-****-****-1234`)
- `'hash'` - Replace with deterministic hash

**Custom PII detector**:
```python
PIIMiddleware(
    "api_key",
    detector=r"sk-[a-zA-Z0-9]{32}",
    strategy="block",
)
```

### 7. ToolRetryMiddleware

Retry failed tool calls with exponential backoff.

```python
from langchain.agents.middleware import ToolRetryMiddleware

agent = create_agent(
    model="gpt-4o",
    tools=[search_tool, database_tool],
    middleware=[
        ToolRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            retry_on=(ConnectionError, TimeoutError),
            on_failure="return_message",  # or "raise" or custom
        ),
    ],
)
```

### 8. ModelRetryMiddleware

Retry failed model calls with exponential backoff.

```python
from langchain.agents.middleware import ModelRetryMiddleware

agent = create_agent(
    model="gpt-4o",
    middleware=[
        ModelRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            on_failure="continue",  # or "error"
        ),
    ],
)
```

### 9. LLMToolSelectorMiddleware

Use an LLM to select relevant tools before main model call.

**Use case**: Agents with many tools (10+) where most aren't relevant per query.

```python
from langchain.agents.middleware import LLMToolSelectorMiddleware

agent = create_agent(
    model="gpt-4o",
    tools=[tool1, tool2, tool3, ...],  # Many tools
    middleware=[
        LLMToolSelectorMiddleware(
            model="gpt-4o-mini",
            max_tools=3,
            always_include=["search"],  # Always include these
        ),
    ],
)
```

### 10. ContextEditingMiddleware

Manage conversation context by clearing older tool outputs when limits reached.

```python
from langchain.agents.middleware import (
    ContextEditingMiddleware,
    ClearToolUsesEdit,
)

agent = create_agent(
    model="gpt-4o",
    middleware=[
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=100000,  # Token threshold
                    keep=3,          # Keep N recent tool results
                ),
            ],
        ),
    ],
)
```

## Custom Middleware

### Using Decorators

```python
from langchain.agents.middleware import (
    before_model,
    after_model,
    wrap_model_call,
    ModelRequest,
    ModelResponse,
)

@before_model
def log_inputs(state, runtime):
    print(f"Before model: {len(state['messages'])} messages")
    return state  # Modify and return

@after_model
def log_outputs(state, runtime, result):
    print(f"After model: {result}")
    return result

@wrap_model_call
def timing_middleware(request: ModelRequest, handler) -> ModelResponse:
    import time
    start = time.time()
    response = handler(request)
    duration = time.time() - start
    print(f"Model call took {duration:.2f}s")
    return response
```

### Middleware Class

```python
from langchain.agents.middleware import AgentMiddleware
from typing import Any

class CustomMiddleware(AgentMiddleware):
    state_schema = CustomState  # Optional custom state
    tools = [custom_tool]           # Tools to attach

    def before_model(self, state, runtime) -> dict[str, Any] | None:
        """Called before model invocation."""
        # Modify state or return None to leave unchanged
        return None

    def after_model(self, state, runtime, result) -> dict[str, Any] | None:
        """Called after model invocation."""
        # Modify result or return None
        return None
```

## Middleware Configuration

### Environment Flags Pattern

```python
# In settings.py
MW_SUMMARIZATION_ENABLED = True
MW_SUMMARIZATION_TRIGGER_TOKENS = 4000
MW_SUMMARIZATION_KEEP_MESSAGES = 20
MW_MODEL_CALL_LIMIT = 50
MW_TOOL_CALL_LIMIT = 100
MW_TOOL_RETRY_ENABLED = True
MW_MODEL_RETRY_ENABLED = True

# In agent builder
middleware = []
if settings.MW_SUMMARIZATION_ENABLED:
    middleware.append(
        SummarizationMiddleware(
            trigger=("tokens", settings.MW_SUMMARIZATION_TRIGGER_TOKENS),
            keep=("messages", settings.MW_SUMMARIZATION_KEEP_MESSAGES),
        )
    )
if settings.MW_MODEL_CALL_LIMIT:
    middleware.append(ModelCallLimitMiddleware(thread_limit=settings.MW_MODEL_CALL_LIMIT))
# ... etc
```

## Important Notes

### Summarization vs Structured Summary

LangChain's `SummarizationMiddleware` is **different** from a custom structured summary pipeline:

| Aspect | SummarizationMiddleware | Structured Summary |
|--------|------------------------|-------------------|
| Purpose | Simple token reduction | Topics, intents, KB-first routing |
| Context preservation | Recent messages | Topic-based summary |
| KB awareness | None | Prioritizes KB over conversation |

**Do not enable both simultaneously** - choose one based on your needs.

## References

- [Middleware Overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- [Built-in Middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [Custom Middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
