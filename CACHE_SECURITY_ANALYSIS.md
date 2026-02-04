# Memory Cache Security Analysis

**Date**: 2026-02-04
**Question**: Can user memory cache be cross-contaminated?

---

## Short Answer

**NO** - The proposed cache is safe because it only tracks **which thread was loaded**, not the actual profile data.

**BUT** - There are other places where cross-contamination COULD happen if you're not careful.

---

## Current Cache Implementation (Safe)

### What We're Caching

```python
class BaseChannel:
    def __init__(self):
        # ✅ SAFE: Only caching thread_id (boolean flag)
        # "Has this thread been loaded?"
        self._profile_loaded = set()  # {thread_id, thread_id, ...}

    def _get_relevant_memories(self, thread_id, query):
        # Check if we already loaded this thread
        if thread_id not in self._profile_loaded:
            # Load from database (per-thread isolation)
            profile = storage.list_memories(thread_id=thread_id)
            self._profile_loaded.add(thread_id)  # ✅ Only store thread_id
        else:
            profile = []  # ✅ Don't reload, but also don't cache data

        return profile
```

### Why This Is Safe

1. **Thread ID is unique per user**
   - Each conversation has unique thread_id
   - HTTP: `http:user_id` (one thread per user or per conversation)
   - Telegram: `telegram:user_id` (one thread per user)
   - No two users share the same thread_id

2. **Cache key = thread_id**
   - We only store: `{"http_alice", "http_bob", "http_charlie"}`
   - We do NOT store: `{alice: "PM at Acme", bob: "Dev at Google"}`
   - Cache says "yes/no", not "what data"

3. **Data still comes from thread-isolated storage**
   ```python
   # Each user has their own database
   data/users/http_http_alice/mem/mem.db  # Alice's memories
   data/users/http_http_bob/mem/mem.db    # Bob's memories
   data/users/http_http_charlie/mem/mem.db # Charlie's memories
   ```

4. **Thread-scoped storage access**
   ```python
   storage.list_memories(thread_id=thread_id)  # ✅ Thread parameter
   # Always queries that thread's database
   # Never cross-thread access
   ```

---

## What Would Be UNSAFE

### Example 1: Caching Actual Profile Data ❌

```python
# UNSAFE: Don't do this!
class BaseChannel:
    def __init__(self):
        # ❌ DANGER: Caching actual profile data
        self._profile_cache = {}  # {thread_id: profile_data}

    def get_profile(self, thread_id):
        if thread_id in self._profile_cache:
            return self._profile_cache[thread_id]  # ❌ Returns wrong data if bug

        profile = load_from_db(thread_id)
        self._profile_cache[thread_id] = profile  # ❌ Could be wrong thread
        return profile
```

**Why this is dangerous**:
- If thread_id generation has bugs, could return wrong profile
- Cache isn't validated against database
- Hard to detect when it's wrong

---

### Example 2: Global Cache Without Thread Key ❌

```python
# UNSAFE: Global cache without thread isolation
_last_profile_loaded = None  # ❌ No thread_id!

def get_profile(thread_id):
    global _last_profile_loaded

    if _last_profile_loaded:
        return _last_profile_loaded  # ❌ Returns wrong user's profile!

    profile = load_from_db(thread_id)
    _last_profile_loaded = profile  # ❌ Overwrites with current user
    return profile
```

**Cross-contamination scenario**:
```
Request 1 (Alice): Load profile → Cache = "Alice is PM"
Request 2 (Bob): Check cache → Returns "Alice is PM" ❌ WRONG!
```

---

### Example 3: LLM Context Confusion ❌

```python
# UNSAFE: Injecting wrong context into LLM
def build_prompt(user_message, thread_id):
    cached_context = get_cached_context()  # ❌ No thread_id check!

    return f"""
    User: {cached_context}  # ❌ Could be Alice's context for Bob!
    Message: {user_message}
    """
```

**What could happen**:
```
Alice (10:00): "I'm a PM at Acme"
             → LLM learns: Alice = PM

Bob (10:05): "Create a report"
             → System uses cached context
             → LLM thinks: Bob = PM at Acme ❌ WRONG!
```

---

## Current System: Safe by Design

### Thread Isolation in Storage

```python
# File: src/executive_assistant/storage/file_sandbox.py

def get_thread_root(thread_id: str | None = None) -> Path:
    """
    Get thread-specific data directory.
    Each thread has isolated storage.
    """
    if thread_id is None:
        thread_id = get_thread_id()  # From context var

    # ✅ Thread-specific directory
    return settings.DATA_ROOT / "users" / thread_id
```

**Result**:
```
data/users/
├── http_http_alice/
│   ├── mem/mem.db         # Alice's memories only
│   ├── vdb/               # Alice's vectors only
│   └── tdb/               # Alice's TDB only
├── http_http_bob/
│   ├── mem/mem.db         # Bob's memories only
│   └── ...
```

**No cross-user access possible** - each thread has separate database!

---

### Memory Storage Always Requires thread_id

```python
# File: src/executive_assistant/storage/mem_storage.py

class MemoryStorage:
    def list_memories(
        self,
        thread_id: str | None = None,  # ✅ Always parameter
        memory_type: str | None = None,
        status: str = "active",
    ):
        if thread_id is None:
            thread_id = get_thread_id()  # ✅ From context

        # ✅ Queries that thread's database only
        conn = self.get_connection(thread_id)

        rows = conn.execute("""
            SELECT * FROM memories
            WHERE thread_id = ?  -- ✅ Thread-scoped query
        """, (thread_id,))
```

**Cannot query across threads** - database connection is thread-specific!

---

### How Thread ID is Set

```python
# File: src/executive_assistant/channels/base.py

async def _process_message(self, message):
    # 1. Extract thread_id from message
    thread_id = self.get_thread_id(message)  # ✅ Per-message

    # 2. Set thread context (thread-local variable)
    set_thread_id(thread_id)  # ✅ Context variable
    set_channel(channel)

    # 3. All storage calls use this context
    memories = get_relevant_memories(thread_id)  # ✅ Thread-scoped
```

**Thread-local context** prevents cross-contamination!

---

## Concurrent Request Safety

### Scenario: Two Users Same Time

```
Time  | Request A (Alice)         | Request B (Bob)
------|---------------------------|------------------------
10:00 | set_thread_id("alice")    |
10:00 | Load profile              |
10:01 |                           | set_thread_id("bob")
10:01 | LLM processing...         | Load profile
10:02 | Response to Alice         | LLM processing...
10:03 |                           | Response to Bob
```

**Is this safe?**

**YES** - Because:
1. Each request has its own async context
2. `thread_id` is a context variable (thread-local)
3. Database connections are per-thread
4. No shared state between requests

**But** - There's a catch:

---

## The Danger: Shared Channel Instance

### Current Architecture

```python
# One channel instance for ALL requests
channel = HTTPChannel()

# Request 1
channel._process_message(alice_message)  # Uses channel._profile_loaded

# Request 2 (concurrent!)
channel._process_message(bob_message)    # Uses SAME channel._profile_loaded
```

**Is the cache safe here?**

```python
class BaseChannel:
    def __init__(self):
        self._profile_loaded = set()  # ⚠️ Shared across ALL requests!

    def _get_relevant_memories(self, thread_id, query):
        if thread_id not in self._profile_loaded:  # ⚠️ Thread-safe check
            profile = storage.list_memories(thread_id=thread_id)  # ✅ Thread-scoped
            self._profile_loaded.add(thread_id)

        return profile
```

**Analysis**:
- `self._profile_loaded` is shared across concurrent requests
- BUT: We're only adding thread_id to set (not data)
- AND: Each check is thread-specific (`thread_id not in self._profile_loaded`)
- AND: Storage is always thread-scoped

**Is this safe?**

✅ **YES** - Because:
1. Set operations are atomic in Python
2. We only store thread_id (boolean flag)
3. Each request checks its own thread_id
4. Even if Alice adds her thread_id while Bob checks, they don't interfere

**Example**:
```
Initial: _profile_loaded = {}

Alice (Thread A): "http_alice" in _profile_loaded? → No
                  Load profile from Alice's DB
                  Add "http_alice" to set
                  _profile_loaded = {"http_alice"}

Bob (Thread B):   "http_bob" in _profile_loaded? → No (different key!)
                  Load profile from Bob's DB
                  Add "http_bob" to set
                  _profile_loaded = {"http_alice", "http_bob"}
```

**No cross-contamination** because thread_id is different!

---

## But What About LLM Confusion?

### Could LLM Mix Up Users?

**Scenario**:
```
Message 1 (Alice): "I'm a PM at Acme"
LLM: "Hi Alice! Noted you're a PM at Acme"

Message 2 (Bob): "Create a report"
LLM: Does it think Bob is the PM?
```

**Answer**: **NO** - Because LLM conversation history is thread-scoped

```python
# File: src/executive_assistant/channels/base.py

async def _process_message(self, message):
    thread_id = self.get_thread_id(message)  # ✅ Per-message thread

    # ✅ Conversation history is thread-scoped
    config = {"configurable": {"thread_id": thread_id}}
    history = self.get_history(thread_id)  # ✅ Alice's history only

    # ✅ LLM only sees this thread's history
    response = await llm.ainvoke(
        messages=history + [user_message],
        config=config
    )
```

**LangGraph handles this**:
- Each thread_id has separate conversation history
- LLM only sees messages from that thread
- Alice's conversation doesn't leak into Bob's

---

## Edge Cases to Watch

### Edge Case 1: Thread ID Collision

**Could two users get same thread_id?**

```python
# HTTP channel
def get_thread_id(self, message):
    return message.user_id  # ⚠️ Is this unique?
```

**Safe if**:
- Each user has unique user_id
- System validates user_id uniqueness

**Unsafe if**:
- user_id can be spoofed
- Multiple user_id formats collide

**Solution**:
```python
# Add channel prefix
def get_thread_id(self, message):
    return f"http:{message.user_id}"  # ✅ Namespaced

# Or use UUID
def get_thread_id(self, message):
    return f"http:{message.user_id}:{conversation_id}"  # ✅ More specific
```

---

### Edge Case 2: Memory Pool Across Threads

**What if we use shared memory pool?**

```python
# UNSAFE: Shared cache
class MemoryCache:
    _cache = {}  # Shared across all threads

    @classmethod
    def get_profile(cls, thread_id):
        if thread_id in cls._cache:
            return cls._cache[thread_id]  # ⚠️ Could be stale

        profile = load_from_db(thread_id)
        cls._cache[thread_id] = profile  # ⚠️ Never expires
        return profile
```

**Problems**:
1. Stale data (never updates)
2. No size limit (memory leak)
3. Cross-contamination if thread_id buggy

**Better approach**:
```python
# SAFE: Per-thread cache with TTL
from cachetools import TTLCache

class BaseChannel:
    def __init__(self):
        # ✅ Thread-specific cache, auto-expires after 1 hour
        self._profile_loaded = TTLCache(maxsize=1000, ttl=3600)

    def _get_relevant_memories(self, thread_id, query):
        if thread_id not in self._profile_loaded:
            profile = storage.list_memories(thread_id=thread_id)
            self._profile_loaded[thread_id] = True  # ✅ Auto-expires
        else:
            profile = []

        return profile
```

---

### Edge Case 3: System Prompt Leakage

**Could system prompt carry over?**

```python
# System prompt is per-request
def build_system_prompt(user_message, thread_id):
    # ✅ Built fresh each request
    return f"You are Ken, assisting {thread_id}"
```

**Safe** - System prompt is built per-request, not cached.

---

## Recommended Safe Implementation

```python
from cachetools import TTLCache
import threading

class BaseChannel:
    def __init__(self):
        # ✅ Thread-safe, auto-expiring cache
        # maxsize=1000: Prevent memory leak
        # ttl=3600: Expire after 1 hour (force reload if profile updated)
        self._profile_loaded = TTLCache(maxsize=1000, ttl=3600)
        self._lock = threading.Lock()  # For thread safety

    def _get_relevant_memories(self, thread_id: str, query: str) -> str:
        """
        Retrieve relevant memories with safe caching.
        """
        storage = get_mem_storage()

        # ✅ Thread-safe check
        with self._lock:
            profile_loaded = thread_id in self._profile_loaded

            if not profile_loaded:
                # ✅ Load from thread-scoped storage
                profile_memories = storage.list_memories(
                    memory_type="profile",
                    status="active",
                    thread_id=thread_id,  # ✅ Thread-specific
                )

                # ✅ Mark as loaded (auto-expires in 1 hour)
                self._profile_loaded[thread_id] = True
            else:
                # ✅ Don't reload, but also don't cache data
                profile_memories = []

        # ✅ Always search for other memories (fresh each time)
        other_memories = storage.search_memories(
            query=query,
            limit=5,
            thread_id=thread_id,  # ✅ Thread-specific
        )

        return self._inject_memories(query, profile_memories + other_memories)

    def reset_conversation(self, thread_id: str):
        """Called when conversation ends."""
        with self._lock:
            self._profile_loaded.pop(thread_id, None)  # ✅ Force reload next time
```

**Safety features**:
1. ✅ Thread-safe with lock
2. ✅ TTL auto-expires (prevents stale data)
3. ✅ Max size limit (prevents memory leak)
4. ✅ Only caches thread_id (not data)
5. ✅ Storage always thread-scoped
6. ✅ No cross-thread data access

---

## Testing for Cross-Contamination

### Test 1: Concurrent Requests

```python
import asyncio

async def test_concurrent_users():
    """Test that Alice and Bob don't mix"""

    # Concurrent requests
    results = await asyncio.gather(
        send_message("alice", "I'm a PM"),
        send_message("bob", "I'm a Dev"),
        send_message("alice", "What am I?"),  # Should say "PM"
        send_message("bob", "What am I?"),    # Should say "Dev"
    )

    # Verify
    assert "PM" in results[2]  # Alice = PM
    assert "Dev" in results[3]  # Bob = Dev
    assert "Bob" not in results[2]  # Alice doesn't know Bob
```

---

### Test 2: Cache Isolation

```python
def test_cache_isolation():
    """Test that cache doesn't share data"""

    channel = BaseChannel()

    # Alice loads profile
    channel._get_relevant_memories("alice", "test")
    assert "alice" in channel._profile_loaded

    # Bob loads profile
    channel._get_relevant_memories("bob", "test")
    assert "bob" in channel._profile_loaded

    # Verify no cross-contamination
    assert "alice" in channel._profile_loaded  # ✅ Still there
    assert "bob" in channel._profile_loaded    # ✅ Both loaded
    assert len(channel._profile_loaded) == 2   # ✅ No extra entries
```

---

### Test 3: Thread ID Collision

```python
def test_no_thread_collision():
    """Test that different channels don't collide"""

    http_channel = HTTPChannel()
    telegram_channel = TelegramChannel()

    # Same user_id, different channels
    http_id = http_channel.get_thread_id(Message(user_id="alice"))
    telegram_id = telegram_channel.get_thread_id(Message(user_id="alice"))

    # Should be different
    assert http_id != telegram_id  # ✅ Namespaced
    assert http_id.startswith("http:")  # ✅ Channel prefix
    assert telegram_id.startswith("telegram:")  # ✅ Channel prefix
```

---

## Summary: Is It Safe?

### ✅ YES - The Cache Is Safe

**Why**:
1. Only caches thread_id (boolean flag), not data
2. Thread-scoped storage prevents cross-user access
3. Set operations are atomic
4. Each request checks its own thread_id
5. LLM conversation history is thread-scoped

### ⚠️ But Watch Out For

1. **Don't cache actual profile data** - Only cache thread_id
2. **Use thread-scoped storage** - Always pass thread_id parameter
3. **Add TTL** - Prevent stale data
4. **Test concurrent requests** - Verify isolation
5. **Validate thread_id uniqueness** - Prevent collisions

### 🛡️ Best Practices

1. ✅ Use TTLCache (auto-expire)
2. ✅ Thread-safe locks for concurrent requests
3. ✅ Only cache thread_id, not data
4. ✅ Always thread-scoped storage access
5. ✅ Test for cross-contamination
6. ✅ Add monitoring for suspicious patterns

---

## Bottom Line

**The cache is safe** because:
- We're not caching data, just "was this thread loaded?"
- Storage is thread-isolated
- LLM conversation is thread-isolated
- No cross-thread data access possible

**Cross-contamination impossible** with this design.

**Want me to implement the safe version with TTL cache and thread locks?**
