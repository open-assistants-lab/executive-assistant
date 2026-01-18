# LLM API Cold Start Optimization Guide (2025)

**Last Updated:** 2025-01-19
**Purpose:** Optimize Cassey's LLM API calls to minimize cold start latency

---

## What is Cold Start vs Warm Start?

### Cold Start
- **Definition:** First request to a model that has been idle
- **Latency:** 14-15 seconds (real-world reports)
- **Cause:** Model needs to load resources, allocate GPU, initialize
- **Impact:** Poor UX for first user interaction

### Warm Start
- **Definition:** Subsequent requests when model is already loaded
- **Latency:** 200ms-2s (10-75× faster)
- **Cause:** Model remains in memory/ready state
- **Impact:** Excellent UX for ongoing interactions

---

## GPT-5.1 "Warmer by Default" - Important Clarification

**⚠️ CRITICAL:** "Warmer by default" applies **only to ChatGPT web interface**, NOT the API!

OpenAI's announcement that "GPT-5.1 Instant is warmer by default" refers specifically to:
- ✅ ChatGPT web users (chatgpt.com)
- ✅ ChatGPT app users
- ✅ Consumer-facing product experience

**It does NOT apply to:**
- ❌ OpenAI API (api.openai.com)
- ❌ Azure OpenAI API
- ❌ API developers building applications

### Evidence:

**OpenAI Community Forum (October 2025):**
> "The time to get a response from the API is very slow, **12 seconds**. If we send a second request with the same data, it's **6s** because it's cached."

**This matches our benchmark results:**
- First request: 12.75s (cold start)
- Subsequent requests: Faster (warm)

### Why the Distinction?

**ChatGPT Web Interface:**
- Massive concurrent traffic (millions of users)
- OpenAI keeps models pre-warmed 24/7
- User experience is critical for consumer product
- "Warmer by default" optimization applies here

**OpenAI API:**
- On-demand resource allocation
- No pre-warming (unless you pay for Provisioned Throughput)
- Developer responsible for optimization
- **Cold starts still occur** (10-15 seconds)

### Bottom Line for API Developers:

**Nothing has changed for API usage.** You still need to implement:
1. Warm-up strategies
2. Connection pooling
3. Request caching
4. Multi-model routing

**Do not rely on "warmer by default" for API applications.**

---

## Optimization Strategies for Cassey

### 1. **Periodic Warm-Up Requests** ⭐ RECOMMENDED

Keep the model warm by sending lightweight requests periodically.

**Implementation:**

```python
import asyncio
from datetime import datetime, timedelta
from openai import AsyncOpenAI

class LLMWarmupService:
    def __init__(self, client: AsyncOpenAI, model: str, warmup_interval: int = 300):
        """
        Args:
            client: OpenAI async client
            model: Model name (e.g., "gpt-5.1-chat-latest")
            warmup_interval: Seconds between warm-up requests (default: 5 minutes)
        """
        self.client = client
        self.model = model
        self.warmup_interval = warmup_interval
        self.last_warmup = None
        self._task = None

    async def warmup_request(self):
        """Send a lightweight warm-up request."""
        try:
            await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1
            )
            self.last_warmup = datetime.now()
            print(f"[{datetime.now()}] Warm-up request sent to {self.model}")
        except Exception as e:
            print(f"[Warm-up] Error: {e}")

    async def start_warmup_loop(self):
        """Start periodic warm-up requests."""
        while True:
            await self.warmup_request()
            await asyncio.sleep(self.warmup_interval)

    async def start(self):
        """Start the warm-up service."""
        if self._task is None:
            self._task = asyncio.create_task(self.start_warmup_loop())
            print("Warm-up service started")

    async def stop(self):
        """Stop the warm-up service."""
        if self._task:
            self._task.cancel()
            self._task = None
            print("Warm-up service stopped")

    def is_warm(self) -> bool:
        """Check if model is likely warm."""
        if self.last_warmup is None:
            return False
        elapsed = (datetime.now() - self.last_warmup).total_seconds()
        return elapsed < self.warmup_interval * 2  # Warm if within 2× interval
```

**Usage in Cassey:**

```python
# In src/cassey/main.py or similar
from src.cassey.llm_service import LLMWarmupService

async def startup():
    """Initialize warm-up service on startup."""
    warmup_service = LLMWarmupService(
        client=openai_client,
        model="gpt-5.1-chat-latest",
        warmup_interval=300  # 5 minutes
    )
    await warmup_service.start()
```

**Pros:**
- ✅ Simple to implement
- ✅ Effective for keeping models warm
- ✅ Low cost (1 token per request)

**Cons:**
- ❌ Adds ongoing API costs (minimal)
- ❌ Requires background task

---

### 2. **Connection Pooling** ⭐ RECOMMENDED

Reuse HTTP connections instead of creating new ones for each request.

**Implementation (using HTTPX):**

```python
import httpx
from openai import AsyncOpenAI, OpenAI

# Configure connection limits
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,      # Max concurrent connections
        max_keepalive_connections=20,  # Max connections to keep alive
        keepalive_expiry=300      # Keep connections alive for 5 minutes
    ),
    timeout=httpx.Timeout(60.0, connect=10.0)
)

# Initialize OpenAI client with connection pooling
client = AsyncOpenAI(
    api_key="your-api-key",
    http_client=http_client
)
```

**For synchronous client:**

```python
import httpx
from openai import OpenAI

http_client = httpx.Client(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=300
    )
)

client = OpenAI(
    api_key="your-api-key",
    http_client=http_client
)
```

**Pros:**
- ✅ Reduces connection overhead
- ✅ Improves performance for multiple concurrent requests
- ✅ Built into HTTP libraries

**Cons:**
- ❌ Requires client configuration

---

### 3. **Authentication Token Caching**

Cache API authentication tokens to avoid re-authentication overhead.

**Implementation:**

```python
from functools import lru_cache
from openai import OpenAI

@lru_cache(maxsize=1)
def get_cached_client(api_key: str) -> OpenAI:
    """Get or create cached OpenAI client."""
    return OpenAI(api_key=api_key)

# Usage
client = get_cached_client("your-api-key")
```

**For environment-based configuration:**

```python
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Get cached client using environment variable."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)
```

**Pros:**
- ✅ Eliminates re-authentication overhead
- ✅ Simple to implement

**Cons:**
- ❌ Only helps if client instantiation is expensive

---

### 4. **Request Queuing and Batching**

Queue requests and send them in batches to reduce cold starts.

**Implementation:**

```python
import asyncio
from collections import deque
from typing import List, Dict, Any

class RequestBatcher:
    def __init__(self, batch_size: int = 5, batch_timeout: float = 2.0):
        """
        Args:
            batch_size: Max requests per batch
            batch_timeout: Max seconds to wait before sending incomplete batch
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.queue: deque = deque()
        self._pending_requests: List[asyncio.Future] = []
        self._lock = asyncio.Lock()
        self._task = None

    async def submit(self, messages: List[Dict], **kwargs) -> str:
        """Submit a request and return response."""
        future = asyncio.Future()
        async with self._lock:
            self._pending_requests.append(future)
            self.queue.append((messages, kwargs))

            if len(self.queue) >= self.batch_size:
                await self._process_batch()

            if self._task is None:
                self._task = asyncio.create_task(self._batch_loop())

        return await future

    async def _batch_loop(self):
        """Process batches periodically."""
        while self.queue:
            await asyncio.sleep(self.batch_timeout)
            async with self._lock:
                if self.queue:
                    await self._process_batch()

        self._task = None

    async def _process_batch(self):
        """Process current batch of requests."""
        if not self.queue:
            return

        batch = []
        futures = []

        while self.queue and len(batch) < self.batch_size:
            messages, kwargs = self.queue.popleft()
            future = self._pending_requests.pop(0)
            batch.append((messages, kwargs))
            futures.append(future)

        # Process batch (example: single LLM call for all requests)
        # This is a simplified example - real batching depends on use case
        for i, (messages, kwargs) in enumerate(batch):
            try:
                # Make actual LLM call here
                response = await call_llm(messages, **kwargs)
                futures[i].set_result(response)
            except Exception as e:
                futures[i].set_exception(e)
```

**Pros:**
- ✅ Reduces number of cold starts
- ✅ Better resource utilization

**Cons:**
- ❌ Adds latency for batched requests
- ❌ Complex implementation

---

### 5. **Prefetch/Common Request Caching**

Cache responses to common requests that don't need real-time generation.

**Implementation:**

```python
from functools import lru_cache
import hashlib

class CachedLLMService:
    def __init__(self, client: OpenAI, cache_size: int = 1000):
        self.client = client
        self.cache_size = cache_size

    def _cache_key(self, messages: List[Dict], model: str, **kwargs) -> str:
        """Generate cache key from request parameters."""
        import json
        key_data = {
            "messages": messages,
            "model": model,
            **kwargs
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    @lru_cache(maxsize=1000)
    def _cached_completion(self, cache_key: str, messages_json: str, model: str, **kwargs):
        """Cached completion wrapper."""
        import json
        messages = json.loads(messages_json)
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )

    def create_completion(self, messages: List[Dict], model: str, **kwargs):
        """Create completion with caching."""
        import json
        cache_key = self._cache_key(messages, model, **kwargs)
        messages_json = json.dumps(messages)
        return self._cached_completion(cache_key, messages_json, model, **kwargs)
```

**Pros:**
- ✅ Eliminates redundant LLM calls
- ✅ Reduces latency for repeated queries
- ✅ Reduces API costs

**Cons:**
- ❌ Not suitable for dynamic/conversational content
- ❌ Requires cache invalidation strategy

---

### 6. **Multi-Model Strategy with Warm Standby**

Keep a smaller/faster model warm for quick initial responses, then use larger model for complex tasks.

**Implementation:**

```python
from enum import Enum
from openai import AsyncOpenAI

class ModelTier(Enum):
    FAST = "gpt-4o-mini"
    BALANCED = "gpt-5.1-chat-latest"
    POWER = "gpt-5.1-thinking"

class SmartModelRouter:
    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.warmup_service = LLMWarmupService(client, ModelTier.FAST.value)
        # Keep fast model always warm
        asyncio.create_task(self.warmup_service.start())

    async def route_request(self, query: str, context: dict = None):
        """Route request to appropriate model based on complexity."""
        complexity = self._estimate_complexity(query, context)

        if complexity == "simple":
            # Use fast model (already warm)
            model = ModelTier.FAST.value
        elif complexity == "medium":
            # Use balanced model
            model = ModelTier.BALANCED.value
        else:
            # Use power model for complex tasks
            model = ModelTier.POWER.value

        return await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}]
        )

    def _estimate_complexity(self, query: str, context: dict = None) -> str:
        """Estimate query complexity."""
        # Simple heuristic
        if len(query) < 50 and not any(word in query.lower() for word in ["explain", "analyze", "compare"]):
            return "simple"
        elif len(query) < 200:
            return "medium"
        else:
            return "complex"
```

**Pros:**
- ✅ Fast responses for simple queries
- ✅ Cost-effective (use cheaper model when possible)
- ✅ Scales to complex tasks

**Cons:**
- ❌ More complex routing logic
- ❌ Need to maintain multiple models warm

---

### 7. **Provisioned Throughput (Azure OpenAI)**

If using Azure OpenAI, use Provisioned Throughput SKU for dedicated resources.

**Benefits:**
- ✅ Eliminates cold starts entirely
- ✅ Consistent performance
- ✅ Dedicated resources

**Trade-offs:**
- ❌ Higher cost (commitment required)
- ❌ Less flexible

---

## Recommended Configuration for Cassey

### Priority 1: Connection Pooling + Warm-Up

```python
# In src/cassey/config/llm_factory.py or similar

import httpx
from openai import AsyncOpenAI
from .llm_warmup import LLMWarmupService

class OptimizedLLMClient:
    def __init__(self):
        # Configure connection pooling
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=300  # 5 minutes
            ),
            timeout=httpx.Timeout(60.0, connect=10.0)
        )

        # Initialize OpenAI client with connection pooling
        self.client = AsyncOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            http_client=self.http_client
        )

        # Initialize warm-up service
        self.warmup = LLMWarmupService(
            client=self.client,
            model="gpt-5.1-chat-latest",
            warmup_interval=300  # 5 minutes
        )

    async def start(self):
        """Start background services."""
        await self.warmup.start()

    async def stop(self):
        """Stop background services."""
        await self.warmup.stop()
        await self.http_client.aclose()

    async def create_completion(self, messages: list, **kwargs):
        """Create LLM completion with optimizations."""
        # Ensure model is warm
        if not self.warmup.is_warm():
            print("Model may be cold, triggering warm-up...")
            await self.warmup.warmup_request()

        return await self.client.chat.completions.create(
            model="gpt-5.1-chat-latest",
            messages=messages,
            **kwargs
        )
```

### Priority 2: Caching for Common Queries

```python
from functools import lru_cache

class CachedLLMClient(OptimizedLLMClient):
    def __init__(self):
        super().__init__()
        self.cache_enabled = True

    @lru_cache(maxsize=1000)
    def _cached_completion(self, cache_key: str, messages_json: str, **kwargs):
        """Cached completion for common queries."""
        import json
        messages = json.loads(messages_json)
        return super().create_completion(messages, **kwargs)

    async def create_completion(self, messages: list, use_cache: bool = True, **kwargs):
        """Create completion with optional caching."""
        if use_cache and self._is_cacheable(messages):
            import json
            cache_key = self._generate_cache_key(messages, **kwargs)
            messages_json = json.dumps(messages)
            return self._cached_completion(cache_key, messages_json, **kwargs)
        else:
            return await super().create_completion(messages, **kwargs)

    def _is_cacheable(self, messages: list) -> bool:
        """Check if request is cacheable."""
        # Only cache simple queries without conversation history
        return len(messages) == 1 and len(messages[0]["content"]) < 100
```

---

## Performance Expectations

### Before Optimization:
- **Cold start:** 14-15 seconds
- **Warm start:** 2-3 seconds
- **User experience:** Poor for first interaction

### After Optimization:
- **Cold start:** 2-5 seconds (warm-up service)
- **Warm start:** 200-500ms (connection pooling)
- **User experience:** Consistent fast responses

---

## Monitoring and Metrics

Track cold start vs warm start performance:

```python
import time
from datetime import datetime, timedelta

class LLMMetrics:
    def __init__(self):
        self.request_times = []
        self.cold_starts = []

    def record_request(self, is_cold: bool, latency: float):
        """Record request metrics."""
        self.request_times.append({
            "timestamp": datetime.now(),
            "is_cold": is_cold,
            "latency": latency
        })

        if is_cold:
            self.cold_starts.append(datetime.now())

    def get_stats(self, window_minutes: int = 60) -> dict:
        """Get statistics for recent time window."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent = [r for r in self.request_times if r["timestamp"] > cutoff]

        if not recent:
            return {}

        cold_count = sum(1 for r in recent if r["is_cold"])
        total_count = len(recent)

        return {
            "total_requests": total_count,
            "cold_starts": cold_count,
            "cold_start_rate": cold_count / total_count if total_count > 0 else 0,
            "avg_latency": sum(r["latency"] for r in recent) / total_count,
            "avg_cold_latency": sum(r["latency"] for r in recent if r["is_cold"]) / cold_count if cold_count > 0 else 0,
            "avg_warm_latency": sum(r["latency"] for r in recent if not r["is_cold"]) / (total_count - cold_count) if total_count > cold_count else 0
        }

# Usage
metrics = LLMMetrics()

async def tracked_completion(client, messages, **kwargs):
    """Track completion metrics."""
    start = time.time()
    is_cold = not client.warmup.is_warm()

    response = await client.create_completion(messages, **kwargs)

    latency = time.time() - start
    metrics.record_request(is_cold, latency)

    return response
```

---

## Cost Analysis

### Warm-Up Service Costs:

**Assumptions:**
- Warm-up interval: 5 minutes (300 seconds)
- Tokens per warm-up: 1 token
- GPT-5.1 Mini pricing: $0.25/1M input tokens

**Cost per day:**
- Requests: (24 × 60 × 60) / 300 = 288 requests/day
- Tokens: 288 tokens/day
- Cost: 288 / 1,000,000 × $0.25 = **$0.000072/day**

**Cost per month:**
- **$0.002/month** (negligible)

### Savings from avoiding cold starts:

**Assumptions:**
- 10 cold starts/day (without warm-up)
- Extra latency cost: 12 seconds per cold start
- User value: $50/hour

**Cost of cold starts:**
- 10 × 12 seconds = 120 seconds/day = 2 minutes/day
- Monthly: 60 minutes = 1 hour/month
- Cost: **$50/month** (in user time)

**ROI:** $50/month value vs $0.002/month cost = **25,000× ROI**

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Connection pooling (5 minutes)
2. ✅ Authentication token caching (5 minutes)

### Phase 2: Warm-Up Service (2-4 hours)
3. ✅ Periodic warm-up requests
4. ✅ Metrics tracking

### Phase 3: Advanced Optimizations (1-2 days)
5. ✅ Request caching for common queries
6. ✅ Multi-model routing strategy
7. ✅ Request batching (if applicable)

---

## Configuration Examples

### For OpenAI (Direct API):

```yaml
llm:
  openai:
    api_key: ${OPENAI_API_KEY}
    default_model: gpt-5.1-chat-latest
    connection_pooling:
      max_connections: 100
      max_keepalive_connections: 20
      keepalive_expiry: 300
    warmup:
      enabled: true
      interval_seconds: 300
      model: gpt-5.1-chat-latest
    cache:
      enabled: true
      max_size: 1000
      ttl_seconds: 3600
```

### For Ollama Cloud:

```yaml
llm:
  ollama:
    api_base: http://localhost:11434
    default_model: minimax-m2:cloud
    connection_pooling:
      max_connections: 50
      max_keepalive_connections: 10
    warmup:
      enabled: true
      interval_seconds: 300
      model: minimax-m2:cloud
```

---

## Troubleshooting

### Issue: Warm-up requests failing

**Solution:** Add exponential backoff and retry logic:

```python
async def warmup_with_retry(self, max_retries: int = 3):
    """Warm-up with retry logic."""
    for attempt in range(max_retries):
        try:
            await self.warmup_request()
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # Exponential backoff
            print(f"Warm-up failed (attempt {attempt + 1}), retrying in {wait}s...")
            await asyncio.sleep(wait)
```

### Issue: Connection pool exhaustion

**Solution:** Increase pool size or add timeout:

```python
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=200,  # Increase from 100
        max_keepalive_connections=50,
        keepalive_expiry=300
    ),
    timeout=httpx.Timeout(30.0, connect=5.0, read=30.0)  # Add explicit timeouts
)
```

---

## Sources:
- [OpenAI GPT-5.1 Announcement - "Warmer by Default"](https://openai.com/index/gpt-5-1/)
- [Azure OpenAI Latency Issues - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2235754/strage-latency-issue-in-azure-openai-models)
- [Connection Pooling for AI APIs](https://smartdev.com/ai-powered-apis-grpc-vs-rest-vs-graphql/)
- [Performance Optimization: Scaling AI to Production](https://medium.com/@omark.k.aly/performance-optimization-scaling-ai-to-production-139502b431c4)
