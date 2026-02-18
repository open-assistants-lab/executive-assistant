# Pagination + External History Architecture

## Overview

Instead of relying on CheckpointCleanupMiddleware to manage checkpoint size, use a pagination-based architecture that:
1. Switches threads periodically
2. Stores full history externally
3. Loads context from external storage when needed

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Session                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ Thread Jan   │ →  │ Thread Feb  │ →  │ Thread Mar  │  ...  │
│  │ 500 msgs    │    │ 500 msgs    │    │ 300 msgs    │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         ↓                  ↓                  ↓                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              External History Store                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │   │
│  │  │ Jan Summary  │ │ Feb Summary  │ │ Mar Summary  │  │   │
│  │  │ Full History │ │ Full History │ │ Full History │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### 1. Thread Manager

```python
class ThreadManager:
    """Manages thread switching based on thresholds."""
    
    MESSAGES_PER_THREAD = 500  # Switch after this many messages
    
    def __init__(self, user_id: str, db: YourDatabase):
        self.user_id = user_id
        self.db = db
    
    def get_current_thread(self) -> str:
        """Get current thread ID, creating new if needed."""
        metadata = self.db.get_thread_metadata(self.user_id)
        
        if metadata is None:
            # First thread
            thread_id = self._create_new_thread()
        elif metadata["message_count"] >= self.MESSAGES_PER_THREAD:
            # Threshold reached, create new thread
            thread_id = self._create_new_thread()
        else:
            thread_id = metadata["thread_id"]
        
        return thread_id
    
    def _create_new_thread(self) -> str:
        """Create new thread with initial summary from previous."""
        previous_thread = self.db.get_current_thread(self.user_id)
        
        # Get summary from previous thread for context
        if previous_thread:
            previous_summary = self._generate_thread_summary(previous_thread)
        else:
            previous_summary = None
        
        # Create new thread
        thread_id = f"{self.user_id}-{uuid.uuid4().hex[:8]}"
        
        self.db.create_thread(
            user_id=self.user_id,
            thread_id=thread_id,
            previous_summary=previous_summary,
        )
        
        return thread_id
    
    def _generate_thread_summary(self, thread_id: str) -> str:
        """Generate summary for thread context."""
        messages = self.db.get_messages(thread_id)
        # Use LLM to summarize
        return summarize_messages(messages)
```

### 2. Context Loader

```python
class ContextLoader:
    """Loads context from external history when resuming."""
    
    def __init__(self, db: YourDatabase):
        self.db = db
    
    def load_context(self, user_id: str) -> list[dict]:
        """Load summaries from all previous threads."""
        threads = self.db.get_all_threads(user_id)
        
        context = []
        for thread in threads:
            summary = thread["summary"]
            previous_summary = thread.get("previous_summary")
            
            if previous_summary:
                context.append({
                    "type": "context",
                    "content": f"Previous conversation: {previous_summary}"
                })
            
            context.append({
                "type": "summary",
                "content": summary
            })
        
        return context
    
    def inject_into_agent(self, agent, user_id: str) -> None:
        """Inject context into agent system prompt."""
        context = self.load_context(user_id)
        
        context_block = "\n\n".join([
            f"{c['type'].upper()}: {c['content']}"
            for c in context
        ])
        
        # Inject as system message or memory
        agent.system_prompt = f"""
{agent.system_prompt}

## Previous Conversations Context
{context_block}
"""
```

### 3. Integration with Agent Factory

```python
# In agent/factory.py
def create_agent_for_user(user_id: str):
    thread_manager = ThreadManager(user_id, db)
    thread_id = thread_manager.get_current_thread()
    
    # Load context from previous threads
    context_loader = ContextLoader(db)
    previous_context = context_loader.load_context(user_id)
    
    # Create agent with context
    agent = create_deep_agent(
        name=f"ea-{user_id}",
        model=model,
        # Inject context into system prompt or memory
    )
    
    # Track message count for thread switching
    agent._thread_manager = thread_manager
    
    return agent
```

### 4. Thread Switching Trigger

```python
# Middleware or tool to check after each turn
class ThreadSwitchMiddleware:
    """Checks if thread should be switched after each turn."""
    
    def after_agent(self, state, runtime):
        message_count = len(state.get("messages", []))
        
        if message_count >= ThreadManager.MESSAGES_PER_THREAD:
            # Trigger thread switch for next turn
            runtime.store.set(
                f"thread_switch_pending_{runtime.config['configurable']['user_id']}",
                "true"
            )
```

---

## Configuration

### Recommended Settings

```yaml
# config.yaml
middleware:
  summarization:
    threshold_tokens: 8000  # DeepAgents handles LLM context

# Application config
threads:
  messages_per_thread: 500
  switch_strategy: "message_count"  # or "time", "manual"
  time_period: "monthly"  # if using time strategy
```

---

## Benefits

| Aspect | Benefit |
|--------|---------|
| **Checkpoint size** | Each thread has max 500 messages |
| **Resume time** | Fast - only replay recent thread |
| **History access** | Full history in external DB |
| **Reliability** | Simple, no deepagents coupling |
| **Maintenance** | Low - standard architecture |

---

## Trade-offs

| Aspect | Consideration |
|--------|---------------|
| **Context loss** | Need to load previous summaries manually |
| **Complexity** | More components to maintain |
| **Storage** | External DB required for history |

---

## Migration Path

1. **Phase 1**: Disable CheckpointCleanupMiddleware
2. **Phase 2**: Implement ThreadManager
3. **Phase 3**: Implement ContextLoader
4. **Phase 4**: Wire into agent factory
5. **Phase 5**: Monitor and tune threshold

---

## References

- LangGraph checkpointing: Official documentation
- DeepAgents SummarizationMiddleware: `deepagents/middleware/summarization.py`
- Related: `verdict-checkpoint-cleanup-middleware.md`
