# Memory Tuning Guide for User Customization

## Server Memory Planning

### For 4GB Server (Recommended Settings)

```python
# config.yaml
agent_cache:
  enabled: true
  max_size: 100          # Max concurrent agents to cache
  base_agent_sharing: true  # Clone base agent (optimization)
  per_user_memory_limit_mb: 5  # Max per-user delta
  ttl_seconds: 3600       # Evict after 1 hour of inactivity
```

**Capacity**:
- Active users: 100 (cached)
- Total users: 1000+ (eviction handles overflow)
- Memory usage: ~1GB (well within 4GB limit)

---

## Architecture Options

### Option 1: Full Agent (Simple)

```python
# Current approach: 50MB per user
async def get_or_build_agent(thread_id: str) -> Runnable:
    if thread_id in cache:
        return cache[thread_id]

    # Build complete agent for this user
    agent = create_langchain_agent(
        model=model,
        tools=global_tools + user_mcp_tools,  # All tools baked in
        middleware=middleware,
    )

    cache[thread_id] = agent
    return agent
```

**Memory**: 50MB × 100 users = **5GB** ❌ (too much for 4GB server)

---

### Option 2: Cloned Base Agent (Recommended)

```python
# Optimized approach: Share base, clone per user
_base_agent: Runnable | None = None

async def get_base_agent() -> Runnable:
    """Get or build shared base agent."""
    global _base_agent
    if _base_agent is None:
        _base_agent = create_langchain_agent(
            model=model,
            tools=global_tools,  # Only global tools
            middleware=middleware,
        )
    return _base_agent

async def get_or_build_agent(thread_id: str) -> Runnable:
    """Get base agent + user's MCP tools (optimized)."""
    if thread_id in cache:
        return cache[thread_id]

    # Clone base agent (cheap shallow copy)
    base = await get_base_agent()
    agent = clone_agent(base)

    # Add user's MCP tools only
    user_tools = await load_user_mcp_tools(thread_id)
    agent.tools.extend(user_tools)

    cache[thread_id] = agent
    return agent
```

**Memory**:
- Base agent: 50MB (one-time)
- Per user: 5MB (just MCP tools + references)
- Total: 50MB + (100 × 5MB) = **550MB** ✅

---

### Option 3: Lazy MCP Loading (Advanced)

```python
# Most aggressive: Don't load MCP tools until needed
class LazyAgentProxy:
    """Proxy that loads MCP tools on first use."""

    def __init__(self, base_agent: Runnable, thread_id: str):
        self.base_agent = base_agent
        self.thread_id = thread_id
        self._enhanced_agent: Runnable | None = None

    async def ainvoke(self, input_data):
        if self._enhanced_agent is None:
            # Lazy-load MCP tools on first call
            user_tools = await load_user_mcp_tools(self.thread_id)
            self._enhanced_agent = clone_and_extend(
                self.base_agent,
                user_tools
            )
        return await self._enhanced_agent.ainvoke(input_data)

async def get_or_build_agent(thread_id: str) -> Runnable:
    if thread_id in cache:
        return cache[thread_id]

    base = await get_base_agent()
    proxy = LazyAgentProxy(base, thread_id)

    cache[thread_id] = proxy  # Store proxy (tiny memory footprint)
    return proxy
```

**Memory**:
- Base agent: 50MB
- Per user: ~1KB (proxy object)
- MCP tools: Loaded only when user actually calls them
- Total: 50MB + (100 × 1KB) ≈ **50MB** ✅✅✅

**Tradeoff**: Slight delay on first MCP tool call (50-100ms)

---

## LRU Eviction Strategy

```python
from collections import OrderedDict

class LRUCache:
    """LRU cache with memory limits."""

    def __init__(self, max_size: int, max_memory_mb: int):
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.max_memory = max_memory_mb * 1024 * 1024
        self.current_memory = 0

    def get(self, key: str) -> Runnable | None:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key].agent
        return None

    def put(self, key: str, agent: Runnable, size_mb: int):
        # Evict if at capacity
        while len(self.cache) >= self.max_size or \
              (self.current_memory + size_mb) > self.max_memory:
            self._evict_oldest()

        # Add new entry
        self.cache[key] = CacheEntry(agent, size_mb, time.time())
        self.current_memory += size_mb

    def _evict_oldest(self):
        """Remove least recently used entry."""
        if not self.cache:
            return
        oldest_key, oldest_entry = self.cache.popitem(last=False)
        self.current_memory -= oldest_entry.size_mb
        logger.info(f"Evicted {oldest_key} from cache (LRU)")
```

---

## Monitoring & Alerts

```python
# Health check endpoint
@app.get("/cache-stats")
async def cache_stats():
    return {
        "cached_agents": len(cache),
        "max_size": MAX_CACHE_SIZE,
        "memory_usage_mb": cache.current_memory / (1024*1024),
        "memory_limit_mb": MAX_MEMORY_MB,
        "utilization_percent": (cache.current_memory / MAX_MEMORY_MB) * 100,
        "oldest_entry": cache.oldest_timestamp(),
    }

# Alert if memory high
if cache_stats["utilization_percent"] > 90:
    logger.warning(f"Cache at {cache_stats['utilization_percent']:.1f}% capacity")
    # Send alert, consider increasing MAX_CACHE_SIZE
```

---

## Recommendations for 4GB Server

### Phase 1: Start Simple (Current)
- Max users: 40
- Memory: ~2GB
- Implementation: Full agent per user

### Phase 2: Optimize (Recommended)
- Max users: 200
- Memory: ~1GB
- Implementation: Clone base agent

### Phase 3: Advanced (Future)
- Max users: 500+
- Memory: ~50MB base + lazy loading
- Implementation: Lazy MCP loading

---

## Scaling Beyond 4GB

If you need more users:

| Server RAM | Max Users (Option 1) | Max Users (Option 2) | Max Users (Option 3) |
|------------|---------------------|---------------------|---------------------|
| 4GB        | 40                  | 200                 | 500+                |
| 8GB        | 100                 | 500                 | 1000+               |
| 16GB       | 250                 | 1000+               | 2000+               |

**Note**: Most deployments don't need Option 3. Option 2 (cloned base) is usually sufficient.

---

## Testing Memory Usage

```python
import psutil
import os

def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

async def test_cache_memory():
    """Test actual memory usage with cache."""
    start_mem = get_memory_usage_mb()

    # Add 10 users to cache
    for i in range(10):
        thread_id = f"test:{i}"
        await get_or_build_agent(thread_id)

    end_mem = get_memory_usage_mb()
    per_user = (end_mem - start_mem) / 10

    print(f"Memory per user: {per_user:.1f}MB")
    print(f"Projected 100 users: {per_user * 100:.1f}MB")
    print(f"Max users on 4GB: {int(2500 / per_user)}")
```

Run this test to measure your actual memory usage and tune accordingly!
