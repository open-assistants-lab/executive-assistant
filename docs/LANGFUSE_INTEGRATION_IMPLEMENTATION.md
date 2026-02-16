# Langfuse + LangChain Integration Implementation Plan

## Updated Analysis (2026-02-16)

**After reviewing official documentation:** https://langfuse.com/integrations/frameworks/langchain

### Key Finding: No Additional Dependency Needed!

The **`langfuse` package already includes** `langfuse.langchain.CallbackHandler` - no separate `langfuse-langchain` package needed!

---

## Current Setup

### Already Installed:
```bash
langfuse  # Already includes CallbackHandler
langchain  # Already installed
langchain-openai  # Already installed
langgraph  # Already installed (via deepagents)
```

### Configuration (`.env`):
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-***
LANGFUSE_SECRET_KEY=sk-lf-***
LANGFUSE_HOST=https://langfuse.gongchatea.com.au
LANGFUSE_ENABLED=true
```

✅ **Configuration is complete and working!**

---

## Solution: Pass Callbacks to Agent

### The Fix (Single Line Change):

**File:** `src/agent/factory.py`

**Current code (line 432):**
```python
agent = create_deep_agent(**agent_kwargs)
```

**Fixed code:**
```python
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Create Langfuse callback handler
langfuse_handler = CallbackHandler()

# Pass handler via agent_kwargs
agent_kwargs["callbacks"] = [langfuse_handler] if settings.langfuse_enabled else []

agent = create_deep_agent(**agent_kwargs)
```

### Alternative: Pass at Invocation Time

**File:** `src/api/app.py` (or wherever messages are sent)

**When calling the agent:**
```python
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Create handler with user context
langfuse_handler = CallbackHandler()

# Invoke agent with callbacks
response = await agent.ainvoke(
    {"messages": [HumanMessage(content=message)]},
    config={
        "callbacks": [langfuse_handler],
        "metadata": {
            "langfuse_user_id": user_id,
            "langfuse_session_id": session_id,
            "langfuse_tags": ["executive_assistant"]
        }
    }
)
```

---

## Implementation Options

### Option 1: Agent-Level Callbacks (Recommended)

**Pass callbacks when creating the agent.**

**Pros:**
- ✅ Single change in `src/agent/factory.py`
- ✅ All agent invocations automatically traced
- ✅ Minimal code changes

**Cons:**
- ❌ Cannot set dynamic user_id/session_id per request
- ❌ All traces share same metadata

**Implementation:**

```python
# src/agent/factory.py

@asynccontextmanager
async def create_ken_agent(
    settings: Settings | None = None,
    user_id: str = "default",
    skills: list[str] | None = None,
) -> AsyncIterator[CompiledStateGraph]:
    """Create Executive Assistant agent with Langfuse tracing."""
    if settings is None:
        settings = get_settings()

    # ... existing setup code ...

    # Create Langfuse callback handler
    callbacks = []
    if settings.langfuse_enabled:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler

        # Initialize client (singleton)
        _ = get_client()
        callbacks.append(CallbackHandler())

    agent_kwargs = {
        # ... existing kwargs ...
        "callbacks": callbacks,  # Add this line
    }

    agent = create_deep_agent(**agent_kwargs)
    yield agent
```

---

### Option 2: Invocation-Level Callbacks (Most Flexible)

**Pass callbacks when invoking the agent.**

**Pros:**
- ✅ Dynamic user_id/session_id per request
- ✅ Custom tags/metadata per request
- ✅ Most flexible

**Cons:**
- ❌ Requires changes in API endpoints
- ❌ More code changes

**Implementation:**

```python
# src/api/app.py (or similar)

@app.post("/message")
async def send_message(message: str, user_id: str = "default"):
    """Send message to agent with Langfuse tracing."""
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    # Initialize Langfuse client
    _ = get_client()

    # Create handler
    langfuse_handler = CallbackHandler()

    async with create_ken_agent(user_id=user_id) as agent:
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config={
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": f"session-{uuid4()}",
                    "langfuse_tags": ["executive_assistant", "api"]
                }
            }
        )

    return response
```

---

### Option 3: Hybrid Approach (Best of Both)

**Agent-level for general tracing + invocation-level for user context.**

**Pros:**
- ✅ Automatic tracing always enabled
- ✅ Dynamic user context per request
- ✅ Clean separation of concerns

**Cons:**
- ❌ More complex setup
- ❌ Requires understanding both levels

**Implementation:**

```python
# src/agent/factory.py - Enable tracing at agent level
@asynccontextmanager
async def create_ken_agent(...):
    # Always enable Langfuse at agent level
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    _ = get_client()
    callbacks = [CallbackHandler()]

    agent_kwargs["callbacks"] = callbacks
    # ...
```

```python
# src/api/app.py - Add user context at invocation level
@app.post("/message")
async def send_message(message: str, user_id: str = "default"):
    from langfuse import get_client

    langfuse = get_client()

    # Update trace with user context
    with langfuse.start_as_current_observation(
        as_type="span",
        name="api_request",
        metadata={"user_id": user_id, "endpoint": "/message"}
    ):
        langfuse.update_current_trace(
            user_id=user_id,
            session_id=f"session-{uuid4()}"
        )

        async with create_ken_agent(user_id=user_id) as agent:
            response = await agent.ainvoke(
                {"messages": [HumanMessage(content=message)]}
            )

    return response
```

---

## Recommended Implementation: Option 1 (Simplest)

**Why Option 1?**

1. **Minimal code changes** - Single file modification
2. **Automatic tracing** - All invocations traced immediately
3. **Works with existing code** - No API changes needed
4. **Good enough for MVP** - User_id can be added later if needed

**Implementation Steps:**

### Step 1: Update `src/agent/factory.py`

```python
# Add imports at top
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# In create_ken_agent(), before agent_kwargs:
# Create Langfuse callback handler
callbacks = []
if settings.langfuse_enabled:
    # Initialize Langfuse client (singleton)
    _ = get_client()
    callbacks.append(CallbackHandler())

# Add to agent_kwargs
agent_kwargs["callbacks"] = callbacks
```

### Step 2: Test Integration

```bash
# Start the agent
uv run ken serve

# Send a test message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from Langfuse test"}'

# Check Langfuse dashboard
# https://langfuse.gongchatea.com.au
```

### Step 3: Verify Traces

Expected trace structure:
```
TRACE
├── SPAN: agent_execution
│   ├── GENERATION: llm_call (gpt-4o)
│   ├── SPAN: tool_call (web_search)
│   └── SPAN: tool_call (memory_search)
```

---

## Advanced: Dynamic User Context (Optional Enhancement)

If you want per-request user_id/session_id tracking:

**File:** `src/api/app.py`

```python
from langfuse import get_client
import uuid

@app.post("/message")
async def send_message(
    request: Request,
    message: str,
    user_id: str = "default"
):
    """Send message with user-specific Langfuse tracing."""
    langfuse = get_client()

    # Create request-level span
    with langfuse.start_as_current_observation(
        as_type="span",
        name="api_request",
        metadata={
            "user_id": user_id,
            "endpoint": "/message",
            "request_id": str(uuid.uuid4())
        }
    ) as span:
        # Update trace with user context
        span.update_trace(
            user_id=user_id,
            session_id=f"session-{uuid.uuid4()}",
            tags=["executive_assistant", "api"]
        )

        # Invoke agent (already has callbacks from agent factory)
        async with create_ken_agent(user_id=user_id) as agent:
            response = await agent.ainvoke(
                {"messages": [HumanMessage(content=message)]}
            )

        # Update span with response
        span.update(output={"response_length": len(response)})

    return response
```

---

## Testing Checklist

- [ ] Update `src/agent/factory.py` with CallbackHandler
- [ ] Start agent: `uv run ken serve`
- [ ] Send test message via API
- [ ] Verify traces appear in Langfuse dashboard
- [ ] Check trace contains:
  - [ ] LLM model name
  - [ ] Input/output messages
  - [ ] Tool calls
  - [ ] Token usage
  - [ ] Latency
- [ ] (Optional) Add user context at API level

---

## Expected Trace Structure

Based on Langfuse + LangGraph integration, traces should include:

```
TRACE (executive_assistant_conversation)
│
├── SPAN: agent_execution
│   ├── GENERATION: llm_call (openai/gpt-4o)
│   │   ├── Input: messages
│   │   ├── Output: ai_message
│   │   ├── Usage: prompt_tokens, completion_tokens
│   │   └── Metadata: model, temperature
│   │
│   ├── SPAN: tool_call (tavily_search)
│   │   ├── Input: query
│   │   ├── Output: results
│   │   └── Metadata: search_api
│   │
│   └── SPAN: tool_call (memory_search)
│       ├── Input: query
│       ├── Output: memories
│       └── Metadata: memory_type
```

---

## Troubleshooting

### No Traces Appearing

1. **Check environment variables:**
   ```bash
   echo $LANGFUSE_PUBLIC_KEY
   echo $LANGFUSE_SECRET_KEY
   echo $LANGFUSE_HOST
   echo $LANGFUSE_ENABLED
   ```

2. **Verify Langfuse client:**
   ```python
   from langfuse import get_client
   client = get_client()
   print(f"Enabled: {client is not None}")
   ```

3. **Check CallbackHandler:**
   ```python
   from langfuse.langchain import CallbackHandler
   handler = CallbackHandler()
   print(f"Handler: {handler}")
   ```

4. **Test trace creation:**
   ```python
   from langfuse import get_client
   client = get_client()
   trace_id = client.create_trace_id()
   print(f"Test trace: {trace_id}")
   ```

### Missing User Context

If user_id/session_id not appearing:

1. Ensure metadata is passed correctly:
   ```python
   config={
       "callbacks": [handler],
       "metadata": {
           "langfuse_user_id": "user-123",
           "langfuse_session_id": "session-456"
       }
   }
   ```

2. Check for typos in metadata keys (must be exact)

---

## Summary

### What Changed:

**Before (my analysis):**
- Thought we needed `langfuse-langchain` package ❌
- Thought we needed to modify LLM providers ❌
- Thought integration was complex ❌

**After (official docs):**
- `langfuse` already includes `CallbackHandler` ✅
- Just pass handler to agent invocation ✅
- Integration is trivial ✅

### Implementation:

**Single file change:** `src/agent/factory.py`

**Add 5 lines of code:**
```python
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# ... in create_ken_agent() ...
if settings.langfuse_enabled:
    _ = get_client()
    callbacks = [CallbackHandler()]

agent_kwargs["callbacks"] = callbacks
```

**That's it!** 🎉

---

## References

- Official integration: https://langfuse.com/integrations/frameworks/langchain
- LangChain callbacks: https://python.langchain.com/docs/modules/callbacks/
- LangGraph integration: Same as LangChain (pass callbacks)
- Test traces created: https://langfuse.gongchatea.com.au
