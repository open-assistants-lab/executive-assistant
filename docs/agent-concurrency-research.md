# Agent Hosting: Concurrency Research

## Problem Statement

We discovered that concurrent requests to the same user cause empty responses (race condition) due to shared state in:
- Cached agent instance (`_agents` dict)
- Conversation store (SQLite connection)
- Checkpointer

## Research Findings

### 1. LangGraph Platform (Official Solution)

**Key Features:**
- **LangGraph Server** - provides concurrency control for multiple incoming user messages
- **Checkpointer** - each user has isolated thread_id
- **Task queues** - horizontally scalable for high volume
- **Streaming runs** - for interactive UX

**Key Insight:** LangGraph's checkpointer uses **thread_id** to isolate state per user. Concurrent requests with different thread_ids are safe. The issue is when **same** thread_id receives concurrent requests.

### 2. Forum Discussion: Postgres Checkpointer Concurrency

From LangChain forum (Feb 2026):
- **PostgresSaver uses internal lock** - can serialize requests if not careful
- **RedisSaver** - no internal lock, better for high concurrency
- **Best practice** - use thread_id per user, connection pooling

### 3. Industry Patterns

**Agent Hosting Platforms:**
- **Task queues** - Background jobs for long-running agents
- **Worker pools** - Multiple workers processing queue
- **Stateless agents** - Each request is independent, state in external DB
- **Autoscaling** - Kubernetes + KEDA for queue-based scaling

## Solutions at Different Scales

### Scale 1: 10-100 Users (Current)

**Problem:** Single VM, occasional concurrency

**Solution: Agent Pool**
```
┌─────────────┐
│   HTTP API  │
├─────────────┤
│  Per-user   │
│ Agent Pool  │  ← 2-3 agents per user max
├─────────────┤
│ Checkpointer│  ← SQLite (local) or Postgres
│ (per user) │
└─────────────┘
```

**Implementation:**
- Per-user lock (asyncio) with timeout
- Agent pool: 2-3 agents per user
- Fallback: return "try again" if pool exhausted

### Scale 2: 100-1000 Users

**Problem:** Need horizontal scaling

**Solution: Queue-Based Architecture**
```
                    ┌──────────────┐
                    │  Load        │
         ┌─────────│  Balancer    │─────────┐
         │         └──────────────┘          │
    ┌────▼────┐                         ┌───▼────┐
    │  API    │                         │  API   │
    │ Server  │                         │ Server  │
    └────┬────┘                         └───┬────┘
         │                                   │
         │         ┌─────────────┐           │
         └────────►│  Task      │◄──────────┘
                   │  Queue     │
                   │ (Redis/    │
                   │  RabbitMQ) │
                   └─────┬───────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │Worker 1│ │Worker 2│ │Worker 3│
         └────────┘ └────────┘ └────────┘
```

**Implementation:**
- FastAPI + Celery/RQ task queue
- Redis for queue + state
- Multiple worker processes
- Postgres checkpointer

### Scale 3: 1000-100k Users

**Problem:** Massive scale, global distribution

**Solution: Distributed LangGraph Platform**
```
┌─────────────────────────────────────────────┐
│           Managed LangGraph Platform         │
│  (or self-hosted LangGraph Server + K8s)    │
├─────────────────────────────────────────────┤
│  • Horizontal scaling (multiple replicas)     │
│  • Task queues with优先级                   │
│  • Redis/Postgres persistence               │
│  • Websocket for real-time                  │
└─────────────────────────────────────────────┘
```

**Options:**
1. **LangGraph Cloud** - Fully managed, handles scaling
2. **Self-hosted LangGraph Platform** - Docker/K8s
3. **Custom** - Build on top of LangGraph primitives

## Recommended Roadmap

### Phase 1: Quick Fix (Now)
- Keep current "fresh agent per request" approach
- Accept slight inefficiency for correctness
- Monitor performance

### Phase 2: Agent Pool (1-3 months)
- Implement per-user agent pool (2-3 agents)
- Add Redis for state if needed
- Support 100+ concurrent users

### Phase 3: Queue-Based (3-6 months)
- Add task queue (Celery/RQ)
- Background workers for heavy tasks
- Redis for queue + cache

### Phase 4: Distributed (6-12 months)
- LangGraph Platform or custom K8s deployment
- Multi-region for global latency
- 10k+ users

## Key Takeaways

1. **thread_id is key** - Each user should have unique thread_id
2. **Same user = serialization** - Don't process concurrent requests for same user
3. **Use connection pooling** - Postgres/Redis connection pools
4. **Queue for scale** - At 100+ users, need task queue
5. **Consider LangGraph Platform** - For managed solution

## References

- LangGraph Platform: https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/
- Postgres Checkpointer: https://docs.langchain.com/oss/python/langgraph/persistence
- Forum Discussion: https://forum.langchain.com/t/does-the-postgres-checkpointer-serialize-concurrent-fastapi-requests/2882
- KEDA: https://keda.sh/ (Kubernetes autoscaling)
