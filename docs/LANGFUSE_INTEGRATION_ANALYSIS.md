# Langfuse Integration Analysis

## Executive Summary

**Date:** 2026-02-16
**Status:** ⚠️ Integration Incomplete
**API Endpoint:** https://langfuse.gongchatea.com.au

### Key Findings:
- ✅ Langfuse API keys are correctly configured
- ✅ Langfuse SDK authenticates successfully
- ✅ Test traces can be created via API
- ❌ **LLM calls are NOT being traced** (integration gap)
- ❌ **Wrapper code uses incorrect API** (needs fix)

---

## Current Implementation

### Files Involved:

1. **`src/observability/langfuse.py`** - Langfuse client wrapper
2. **`src/llm/factory.py`** - LLM factory (creates LLM instances)
3. **`src/llm/providers/*.py`** - LLM provider implementations (OpenAI, Anthropic, etc.)
4. **`src/agent/factory.py`** - Agent factory (uses LLMs)

### Configuration (`.env`):
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-***
LANGFUSE_SECRET_KEY=sk-lf-***
LANGFUSE_HOST=https://langfuse.gongchatea.com.au
LANGFUSE_ENABLED=true
```

---

## The Problem: Why No Traces Appear

### Root Cause: Integration Gap

**The Issue:**

1. **Langfuse client wrapper exists** (`src/observability/langfuse.py`)
   - Provides `trace_llm_call()` helper function
   - Client initializes correctly when configured
   - ❌ **But the helper is NEVER called**

2. **LLM providers don't use Langfuse**
   - `src/llm/providers/openai.py` (and other providers)
   - Create raw LangChain models: `ChatOpenAI(api_key=..., ...)`
   - ❌ **No Langfuse callbacks or tracing**

3. **Agent factory doesn't wrap LLMs**
   - `src/agent/factory.py:276` → `_get_model()` → `get_llm()` → Provider
   - Returns raw LangChain LLM
   - ❌ **No Langfuse wrapping**

### Data Flow:
```
Agent Creation (_get_model)
    ↓
get_llm(provider, model)
    ↓
Provider.create_chat_model()
    ↓
Raw LangChain LLM (ChatOpenAI, ChatAnthropic, etc.)
    ↓
Passed to create_deep_agent(model=...)
    ↓
❌ LLM calls happen WITHOUT Langfuse tracing
```

---

## Secondary Issue: Wrapper API Mismatch

### The Wrapper Bug:

**File:** `src/observability/langfuse.py:108`

```python
# INCORRECT - This doesn't work!
trace = self._client.trace(name=name, metadata=metadata, **kwargs)
```

**Error:**
```
AttributeError: 'Langfuse' object has no attribute 'trace'
```

**Explanation:**
- The wrapper tries to call `.trace()` on the Langfuse SDK client
- But the SDK doesn't have a `.trace()` method
- SDK uses a different API pattern (see below)

---

## Langfuse SDK: Correct API Pattern

### Actual Langfuse SDK API:

The Langfuse Python SDK uses this pattern:

1. **Create trace ID:**
   ```python
   trace_id = langfuse.create_trace_id()
   ```

2. **Create span:**
   ```python
   with langfuse.start_as_current_span(
       name='operation_name',
       trace_context={'trace_id': trace_id},
       metadata={'key': 'value'}
   ):
       # Do work
   ```

3. **Create generation (LLM call):**
   ```python
   with langfuse.start_as_current_observation(
       as_type='generation',
       name='llm_call',
       model='gpt-4o',
       input={'prompt': '...'},
       output={'completion': '...'},
       usage_details={'prompt_tokens': 10, 'completion_tokens': 20}
   ):
       # LLM call happens here
   ```

### Verified Working Code:

```python
from langfuse import Langfuse

lf = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host
)

# Create trace
trace_id = lf.create_trace_id()

# Create span (recommended pattern)
with lf.start_as_current_span(
    name='agent_execution',
    trace_context={'trace_id': trace_id}
):
    # Create generation within span
    with lf.start_as_current_observation(
        as_type='generation',
        name='llm_call',
        model='gpt-4o',
        input={'prompt': 'test'},
        output={'completion': 'response'},
        usage_details={'prompt_tokens': 10, 'completion_tokens': 20}
    ):
        # LLM call would happen here
        pass

lf.flush()
```

---

## Verification: Test Traces Created

### Test Results:

✅ **Authentication:** Successful
✅ **Trace Creation:** Successful
✅ **Generation Tracking:** Successful
✅ **API Endpoint:** https://langfuse.gongchatea.com.au

### Test Traces Created:

1. **Trace ID:** `d0d7012282d3fcdb05c3b62eacb2c982`
   - Type: Span + Generation
   - Status: Created successfully
   - URL: https://langfuse.gongchatea.com.au/trace/d0d7012282d3fcdb05c3b62eacb2c982

2. **Trace ID:** `f1bfdf56cebf3931b0abd319e2924cf7`
   - Type: Generation only
   - Status: Created successfully

---

## Solution: How to Fix Langfuse Integration

### Option 1: LangChain Callbacks (Recommended)

**Easiest and most reliable approach.**

Langfuse provides LangChain callback handlers that automatically trace LLM calls.

**Implementation:**

1. **Install Langfuse LangChain integration:**
   ```bash
   uv add langfuse-langchain
   ```

2. **Update `src/llm/providers/base.py` or individual providers:**
   ```python
   from langfuse.callback import CallbackHandler

   class OpenAIProvider(BaseLLMProvider):
       def create_chat_model(self, model: str, **kwargs):
           # Create base LLM
           llm = ChatOpenAI(api_key=self.api_key, model=model, **kwargs)

           # Add Langfuse callbacks if enabled
           from src.observability.langfuse import is_langfuse_enabled
           if is_langfuse_enabled():
               langfuse_handler = CallbackHandler()
               # Return LLM with callbacks
               return llm

           return llm
   ```

**Pros:**
- ✅ Automatic tracing for all LLM calls
- ✅ Minimal code changes
- ✅ Official Langfuse integration
- ✅ Supports all LangChain LLMs

**Cons:**
- ❌ Requires additional dependency (`langfuse-langchain`)
- ❌ Less control over tracing behavior

---

### Option 2: Manual Tracing with Context Manager

**More control, more work.**

Wrap LLM calls using the `trace_llm_call()` helper.

**Implementation:**

1. **Fix `src/observability/langfuse.py` wrapper:**
   ```python
   @contextmanager
   def trace(self, name: str, ...) -> Generator[Any]:
       if not self._client:
           yield None
           return

       # CORRECT: Create trace ID and span
       trace_id = self._client.create_trace_id()
       with self._client.start_as_current_span(
           name=name,
           trace_context={'trace_id': trace_id},
           metadata=metadata
       ) as span:
           yield span
   ```

2. **Update LLM providers to use tracing:**
   ```python
   class OpenAIProvider(BaseLLMProvider):
       def create_chat_model(self, model: str, **kwargs):
           from src.observability.langfuse import get_langfuse_client
           from langchain_core.language_models.chat_models import BaseChatModel

           # Create wrapped LLM
           class TracedChatOpenAI(ChatOpenAI):
               def _generate(self, messages, **kwargs):
                   client = get_langfuse_client()
                   with client.trace(name=f'llm_call_{model}'):
                       return super()._generate(messages, **kwargs)

           return TracedChatOpenAI(api_key=self.api_key, model=model, **kwargs)
   ```

**Pros:**
- ✅ Full control over tracing
- ✅ No additional dependencies
- ✅ Custom tracing logic

**Cons:**
- ❌ More code changes required
- ❌ Need to subclass each LLM type
- ❌ Maintenance burden

---

### Option 3: Agent-Level Tracing

**Trace at the agent level, not per LLM call.**

**Implementation:**

Update `src/agent/factory.py` to wrap agent execution:

```python
@asynccontextmanager
async def create_ea_agent(...):
    from src.observability.langfuse import get_langfuse_client

    client = get_langfuse_client()
    trace_id = client._client.create_trace_id()

    with client._client.start_as_current_span(
        name='agent_execution',
        trace_context={'trace_id': trace_id},
        metadata={'user_id': user_id, 'agent': agent_name}
    ):
        # Create and yield agent
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            # ... existing code ...
            agent = create_deep_agent(**agent_kwargs)
            yield agent

    client._client.flush()
```

**Pros:**
- ✅ Single trace per agent conversation
- ✅ Minimal code changes
- ✅ High-level observability

**Cons:**
- ❌ No per-LLM-call tracing
- ❌ Less granular insights

---

## Recommendation

**Use Option 1 (LangChain Callbacks)** for the following reasons:

1. **Easiest to implement** - Add callbacks to LLM providers
2. **Official integration** - Supported by Langfuse
3. **Automatic tracing** - No manual wrapping needed
4. **Works with all LLMs** - OpenAI, Anthropic, Google, etc.

---

## Implementation Steps (Option 1)

### Step 1: Install Langfuse LangChain Integration
```bash
uv add langfuse-langchain
```

### Step 2: Update `src/llm/providers/base.py`

Add callback support to the base provider class:

```python
from langfuse.callback import CallbackHandler

class BaseLLMProvider(ABC):
    # ... existing code ...

    def get_langfuse_callbacks(self) -> list:
        """Get Langfuse callbacks if enabled."""
        from src.observability.langfuse import is_langfuse_enabled
        callbacks = []

        if is_langfuse_enabled():
            callbacks.append(CallbackHandler())

        return callbacks
```

### Step 3: Update Individual Providers

Update each provider to pass callbacks:

```python
# src/llm/providers/openai.py
class OpenAIProvider(BaseLLMProvider):
    def create_chat_model(self, model: str, **kwargs) -> ChatOpenAI:
        # ... existing code ...

        return ChatOpenAI(
            api_key=self.api_key,
            model=model,
            callbacks=self.get_langfuse_callbacks(),  # Add this
            **config
        )
```

### Step 4: Verify Integration

```bash
# Run the agent
uv run ea http

# Send a message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'

# Check Langfuse dashboard for traces
# https://langfuse.gongchatea.com.au
```

---

## Files Requiring Changes

| File | Change | Priority |
|------|--------|----------|
| `pyproject.toml` | Add `langfuse-langchain` dependency | High |
| `src/observability/langfuse.py` | Fix `.trace()` API | Medium |
| `src/llm/providers/base.py` | Add `get_langfuse_callbacks()` | High |
| `src/llm/providers/openai.py` | Pass callbacks to ChatOpenAI | High |
| `src/llm/providers/anthropic.py` | Pass callbacks to ChatAnthropic | High |
| `src/llm/providers/google.py` | Pass callbacks to ChatGoogle | High |
| `src/llm/providers/*.py` | Update all 17 providers | Medium |

---

## Testing Checklist

- [ ] Install `langfuse-langchain`
- [ ] Update base provider with callbacks
- [ ] Update OpenAI provider
- [ ] Update Anthropic provider
- [ ] Update remaining providers
- [ ] Run agent with test message
- [ ] Verify traces appear in Langfuse dashboard
- [ ] Check trace contains:
  - [ ] LLM model name
  - [ ] Prompt tokens
  - [ ] Completion tokens
  - [ ] Total cost
  - [ ] Latency
  - [ ] User ID

---

## Summary

**Current State:**
- Langfuse client wrapper exists but isn't used
- LLM providers don't wrap calls with tracing
- No traces appear despite correct configuration

**Required Fix:**
- Add LangChain callbacks to LLM providers
- OR wrap LLM calls with tracing context manager
- OR trace at agent level

**Recommended Approach:**
- Use LangChain callbacks (`langfuse-langchain`)
- Minimal code changes
- Official, supported integration

**Estimated Effort:**
- 2-4 hours to implement
- 1 hour to test and verify
- Total: 3-5 hours

---

## References

- Langfuse Python SDK: https://github.com/langfuse/langfuse-python
- Langchain Integration: https://langfuse.com/docs/sdk/python/langchain
- Test Traces: https://langfuse.gongchatea.com.au
