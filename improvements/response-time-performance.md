# Response Time Performance Improvements

**Status:** Planning
**Created:** 2025-02-09
**Priority:** High

## Overview

This document outlines recommendations for improving the agent's response time. Current response times vary from 10-60 seconds depending on query complexity. The goal is to reduce perceived and actual latency by 50-80% for common queries.

## Performance Improvement Recommendations

### 1. Fast Model Routing (Highest Impact)

**Problem:** All requests use the default model regardless of complexity
**Impact:** 2-5x faster for simple queries
**Effort:** Low

#### Implementation

```python
# src/executive_assistant/agent/model_router.py

FAST_QUERIES = [
    "what is", "list", "show", "get", "check",
    "/mem", "/instincts", "/profile", "/help"
]

def should_use_fast_model(query: str) -> bool:
    """Determine if query should use fast model."""
    q = query.lower().strip()

    # Simple queries under 100 chars
    if len(q) < 100 and any(q.startswith(pattern) for pattern in FAST_QUERIES):
        return True

    # Commands with no arguments
    if q.startswith("/") and " " not in q:
        return True

    return False

async def route_to_appropriate_model(query: str, context: dict):
    """Route query to fast or default model based on complexity."""
    if should_use_fast_model(query):
        return await llm_factory.create("fast")
    return await llm_factory.create("default")
```

**Configuration:**
```yaml
# docker/config.yaml
llm:
  deepseek:
    default_model: deepseek-chat  # Use as default instead of reasoner
    fast_model: deepseek-chat      # Same for now, could be smaller model
```

**Gains:**
- Simple queries: 2-5x faster (15s → 3-7s)
- Reduced API costs for fast model
- Better user experience for common queries

---

### 2. Streaming Improvements

**Problem:** Users see nothing until first token arrives
**Impact:** 30-50% reduction in perceived latency
**Effort:** Medium

#### Implementation

```python
# src/executive_assistant/channels/streaming.py

async def stream_with_priority(response, channel):
    """Stream important information first for better perceived performance."""

    # 1. Send immediate status
    await channel.send({"type": "status", "content": "🤔 Thinking..."})

    # 2. Get first chunk quickly (with timeout)
    try:
        first_chunk = await asyncio.wait_for(
            get_first_chunk(response),
            timeout=2.0
        )
        await channel.send({"type": "content", "content": first_chunk})
    except asyncio.TimeoutError:
        await channel.send({"type": "status", "content": "🔄 Processing..."})

    # 3. Stream remaining content normally
    async for chunk in response:
        await channel.send({"type": "content", "content": chunk})

    # 4. Send completion status
    await channel.send({"type": "status", "content": "✅ Done"})
```

**Gains:**
- Perceived latency reduced by 30-50%
- Better user feedback during processing
- Early error detection

---

### 3. Tool Call Caching

**Problem:** Same tools called repeatedly with identical inputs
**Impact:** 100-500ms saved on repeated operations
**Effort:** Low

#### Implementation

```python
# src/executive_assistant/tools/cached_tools.py

from functools import lru_cache
from hashlib import sha256
import json

def cache_key_for_args(tool_name: str, args: dict) -> str:
    """Generate cache key for tool arguments."""
    # Exclude thread_id from cache key
    cacheable_args = {k: v for k, v in args.items() if k != "thread_id"}
    key_str = f"{tool_name}:{json.dumps(cacheable_args, sort_keys=True)}"
    return sha256(key_str.encode()).hexdigest()[:32]

# In-memory cache for tool results (thread-local)
_tool_result_cache = {}

def get_cached_tool_result(tool_name: str, args: dict, ttl: int = 30):
    """Get cached tool result if available and fresh."""
    key = cache_key_for_args(tool_name, args)

    if key in _tool_result_cache:
        result, timestamp = _tool_result_cache[key]
        if time.time() - timestamp < ttl:
            return result

    return None

def cache_tool_result(tool_name: str, args: dict, result):
    """Cache tool result for future use."""
    key = cache_key_for_args(tool_name, args)
    _tool_result_cache[key] = (result, time.time())
```

**Apply to:**
- `list_memories` (high frequency)
- `get_memory_by_key` (high frequency)
- `list_instincts` (medium frequency)

**Gains:**
- 100-500ms saved on repeated memory lookups
- Reduced database load
- Faster onboarding (profile already cached)

---

### 4. Middleware Optimization

**Problem:** All middleware runs for every message
**Impact:** 50-200ms saved on simple commands
**Effort:** Low

#### Implementation

```python
# src/executive_assistant/agent/middleware_optimizer.py

MIDDLEWARE_SKIP_RULES = {
    "TodoListMiddleware": lambda msg: len(msg) < 50 or msg.startswith("/"),
    "SummarizationMiddleware": lambda msg: len(msg) < 1000,
    "ContextEditingMiddleware": lambda msg: "edit" not in msg.lower(),
}

def should_skip_middleware(middleware_name: str, message: str) -> bool:
    """Check if middleware should be skipped for this message."""
    rule = MIDDLEWARE_SKIP_RULES.get(middleware_name)
    return rule(message) if rule else False

async def run_optimized_middleware(message: str, middlewares: list):
    """Run only necessary middleware for this message."""
    results = []

    for mw in middlewares:
        if not should_skip_middleware(mw.__class__.__name__, message):
            result = await mw.process(message)
            results.append(result)

    return results
```

**Gains:**
- 50-200ms saved on simple commands
- Reduced CPU usage
- Faster processing for high-frequency operations

---

### 5. Concurrent Tool Execution

**Problem:** Tools run sequentially even when independent
**Impact:** 30-50% faster for multi-tool queries
**Effort:** Medium

#### Implementation

```python
# src/executive_assistant/agent/concurrent_tools.py

async def analyze_tool_dependencies(tool_calls: list[ToolCall]) -> dict:
    """Analyze which tools can run concurrently."""
    dependency_graph = {
        "create_memory": [],  # No dependencies
        "create_instinct": ["create_memory"],  # Needs memory first
        "list_memories": [],  # No dependencies
        "list_instincts": [],  # No dependencies
    }

    levels = {}
    for tool in tool_calls:
        levels[tool.name] = dependency_graph.get(tool.name, [])

    return levels

async def run_tools_concurrent(tool_calls: list[ToolCall]) -> list[ToolResult]:
    """Run independent tools concurrently."""
    # Group by dependency level
    levels = await analyze_tool_dependencies(tool_calls)

    # Run level 0 (no dependencies) concurrently
    independent = [t for t in tool_calls if not levels.get(t.name)]
    results = await asyncio.gather(*[t.run() for t in independent])

    # Run dependent tools sequentially
    for tool in [t for t in tool_calls if t not in independent]:
        result = await tool.run()
        results.append(result)

    return results
```

**Example:**
```python
# User: "List my memories and instincts"
# Sequential: list_memories (3s) → list_instincts (2s) = 5s total
# Concurrent: both run together = max(3s, 2s) = 3s total (40% faster)
```

**Gains:**
- 30-50% faster for multi-tool queries
- Better user experience for "overview" commands
- More efficient resource utilization

---

### 6. Database Connection Pooling

**Problem:** New database connection for each query
**Impact:** 50-150ms saved per query
**Effort:** Low

#### Implementation

```yaml
# docker/config.yaml

storage:
  postgres:
    host: localhost
    port: 5432
    user: ken
    db: ken_db
    password: testpassword123

    # Connection pooling (NEW)
    pool_size: 10          # Min connections to maintain
    max_overflow: 20       # Max additional connections
    pool_timeout: 30       # Wait time for connection
    pool_recycle: 3600     # Recycle connections after 1 hour
    pool_pre_ping: true    # Verify connections before use
```

```python
# src/executive_assistant/storage/pooled_postgres.py

from asyncpg import create_pool
from executive_assistant.config import settings

_postgres_pool = None

async def get_postgres_pool():
    """Get or create PostgreSQL connection pool."""
    global _postgres_pool

    if _postgres_pool is None:
        _postgres_pool = await create_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            min_size=settings.POSTGRES_POOL_SIZE,
            max_size=settings.POSTGRES_POOL_SIZE + settings.POSTGRES_MAX_OVERFLOW,
            timeout=settings.POSTGRES_POOL_TIMEOUT,
            command_timeout=60,
        )

    return _postgres_pool
```

**Gains:**
- Eliminates connection overhead (50-150ms per query)
- Better performance under load
- Prevents connection exhaustion

---

### 7. VDB Embedding Cache

**Problem:** Same text embedded repeatedly
**Impact:** 100-300ms saved on VDB searches
**Effort:** Low

#### Implementation

```python
# src/executive_assistant/storage/vdb_cache.py

from functools import lru_cache
import hashlib

@lru_cache(maxsize=256)
def get_embedding_cached(text: str) -> list[float]:
    """Cache embeddings to avoid recomputation."""
    # Normalize text for cache key
    normalized = text.lower().strip()

    # Generate embedding
    return embedding_model.embed(normalized)

def clear_cache_when_full():
    """Clear cache if it grows too large."""
    if get_embedding_cached.cache_info().currsize > 250:
        get_embedding_cached.cache_clear()
```

**Gains:**
- 100-300ms saved on VDB searches
- Reduced CPU usage
- Faster memory retrieval

---

### 8. Reduce System Prompt Size

**Problem:** Full system prompt (5000+ tokens) sent with every request
**Impact:** 500-2000ms saved per LLM call
**Effort:** Medium

#### Implementation

```python
# src/executive_assistant/agent/prompt_optimizer.py

SYSTEM_PROMPT_CORE = """
You are Ken, an AI assistant.
Core behavior: helpful, concise, accurate.
Available tools: [tool list]
"""

SYSTEM_PROMPT_SKILLS = """
Additional skill instructions:
[Skill instructions loaded dynamically]
"""

def build_optimized_system_prompt(
    include_skills: bool = False,
    include_examples: bool = False
) -> str:
    """Build minimal system prompt for the request."""

    prompt = SYSTEM_PROMPT_CORE

    # Only add skill instructions if needed
    if include_skills:
        prompt += "\n" + SYSTEM_PROMPT_SKILLS

    # Only add examples for complex queries
    if include_examples:
        prompt += "\n" + EXAMPLES_SECTION

    return prompt

async def determine_prompt_requirements(query: str) -> dict:
    """Determine what prompt components are needed."""
    return {
        "include_skills": any(
            keyword in query.lower()
            for keyword in ["create", "analyze", "workflow"]
        ),
        "include_examples": len(query) > 200
    }
```

**Gains:**
- 500-2000ms saved per LLM call
- Reduced API costs
- Faster response times

---

## Priority Implementation Order

### Phase 1: Quick Wins (1-2 days)
1. **Fast model routing** - Highest impact, lowest effort
2. **Database connection pooling** - Easy to implement
3. **Tool call caching** - Simple LRU cache

**Expected gains:** 2-5x faster for simple queries

### Phase 2: Medium Complexity (3-5 days)
4. **Middleware optimization** - Skip unnecessary middleware
5. **VDB embedding cache** - Cache embeddings
6. **Streaming improvements** - Better perceived performance

**Expected gains:** Additional 30-50% improvement

### Phase 3: Advanced (1-2 weeks)
7. **Concurrent tool execution** - Requires dependency analysis
8. **Reduce system prompt size** - Requires prompt restructuring

**Expected gains:** Additional 20-40% improvement

---

## Performance Metrics

### Current Performance
- Simple query: 10-20s
- Multi-tool query: 20-40s
- Complex workflow: 40-60s

### Target Performance (After All Optimizations)
- Simple query: 2-5s (4-10x faster)
- Multi-tool query: 5-15s (2-4x faster)
- Complex workflow: 15-30s (2-4x faster)

---

## Testing Strategy

### Performance Benchmarks
```bash
# Create performance test suite
tests/benchmarks/
├── test_simple_queries.py     # Test fast model routing
├── test_concurrent_tools.py   # Test parallel execution
├── test_cache_effectiveness.py # Verify caching works
└── test_end_to_end_latency.py # Full workflow timing
```

### Monitoring
```python
# Add performance tracking
import time

@contextmanager
def track_operation(operation_name: str):
    """Track operation duration."""
    start = time.time()
    yield
    duration = time.time() - start
    logger.info(f"{operation_name} took {duration:.2f}s")

    # Alert if too slow
    if duration > 30.0:
        logger.warning(f"{operation_name} exceeded 30s threshold")
```

---

## Risks and Mitigations

### Risk 1: Fast Model Quality Degradation
**Mitigation:** Only use fast model for read-only queries, preserve default model for complex tasks

### Risk 2: Cache Invalidation
**Mitigation:** Use TTL-based expiration, provide manual cache clear command

### Risk 3: Concurrent Tool Race Conditions
**Mitigation:** Implement proper dependency analysis, maintain sequential execution for dependent tools

### Risk 4: Connection Pool Exhaustion
**Mitigation:** Set reasonable pool limits, implement connection recycling

---

## Next Steps

1. **Review this plan** with the team
2. **Prioritize** based on current bottlenecks
3. **Implement Phase 1** (fast model routing, connection pooling, caching)
4. **Benchmark** and measure improvements
5. **Iterate** based on results

---

## Related Files

- `src/executive_assistant/config/settings.py` - Configuration
- `src/executive_assistant/agent/` - Agent implementation
- `src/executive_assistant/channels/` - Channel implementations
- `docker/config.yaml` - Application configuration
