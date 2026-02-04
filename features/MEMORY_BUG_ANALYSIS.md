# Memory Retrieval Bug - Root Cause Analysis

**Date**: 2026-02-04
**Severity**: 🔴 CRITICAL - Affects all models
**Impact**: Users must repeat information every conversation

---

## The Bug

Memory retrieval is failing because the system uses **semantic search** instead of **listing all memories**.

### What's Happening

When a user sends a message, `base.py` automatically retrieves and injects memories:

```python
# Line 305-306 in base.py
memories = self._get_relevant_memories(thread_id, message.content)
enhanced_content = self._inject_memories(message.content, memories)
```

The `_get_relevant_memories` function calls `search_memories()`:

```python
# Line 508 in base.py
memories = storage.search_memories(
    query=query,  # ← User's message is the search query!
    limit=limit,
    min_confidence=settings.MEM_CONFIDENCE_MIN,
)
```

### The Problem

`search_memories()` uses **Full Text Search (FTS)** with the user's message as the query:

```sql
-- Line 609 in mem_storage.py
WHERE m.status = 'active' AND m.confidence >= ? AND mem_fts MATCH ?
--                                                       ^^^^^^^^^^^^^
--                                                       Searches for user's words!
```

**When user asks**: "What do you remember about me?"
- Search query becomes: "What do you remember about me?"
- FTS looks for memories containing: "what", "remember", "about", "me"
- **But the memory says**: "Alice is a product manager at Acme Corp"
- **Result**: NO MATCH! ❌

### What Should Happen

For general questions like "What do you remember?", the system should:
1. Use `list_memories()` to retrieve ALL memories
2. OR always inject all profile memories regardless of query
3. OR detect general questions and use `list_memories` instead

### The Agent Has the Right Tool!

There IS a `list_memories` tool available (mem_tools.py:148):

```python
@tool
def list_memories(
    memory_type: str | None = None,
    status: str = "active",
) -> str:
    """
    List all memories for the current thread.
    ...
    """
```

**But the automatic injection bypasses this tool!**

---

## Why This Affects All Models

The issue is in the **framework** (`base.py`), not in the models:
- Models don't control memory retrieval - it's automatic
- All models go through the same code path
- All models get the same empty memory result

That's why in our tests:
- ✅ claude-sonnet created memories
- ✅ qwen3-next created memories
- ❌ But ALL models failed retrieval (same bug)

---

## Evidence

### Test Results
1. Memories ARE created successfully (verified in SQLite)
2. Memories ARE in database with status='active'
3. But retrieval fails 100% in new conversations

### Database Proof
```bash
$ sqlite3 data/users/http_http_ollama_deepseek_v3.2_cloud/mem/mem.db \
  "SELECT key, content, memory_type FROM memories WHERE memory_type = 'profile';"

user_profile|Alice is a product manager at Acme Corp...|profile
```

The memory exists! But search doesn't find it.

---

## Solutions

### Option 1: Always Inject Profile Memories (Recommended)

Profile memories should ALWAYS be included, not searched:

```python
def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5):
    storage = get_mem_storage()

    # Always include all profile memories
    profile_memories = storage.list_memories(memory_type="profile", status="active")

    # Search for other memory types
    other_memories = storage.search_memories(query=query, limit=limit)

    return profile_memories + other_memories
```

**Pros**: Simple, ensures core context is always available
**Cons**: May inject more memories than needed

---

### Option 2: Detect General Questions

Use `list_memories` for general questions:

```python
def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5):
    storage = get_mem_storage()

    # Detect general memory questions
    general_patterns = [
        "what do you remember",
        "what do you know",
        "tell me about",
        "who am i",
    ]

    query_lower = query.lower()
    if any(pattern in query_lower for pattern in general_patterns):
        # List all memories for general questions
        return storage.list_memories(status="active")

    # Use semantic search for specific queries
    return storage.search_memories(query=query, limit=limit)
```

**Pros**: Smart handling, reduces noise
**Cons**: Pattern matching is fragile

---

### Option 3: Hybrid Approach (Best)

Combine both approaches:

```python
def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5):
    storage = get_mem_storage()

    # Always include profile memories (name, role, etc.)
    profile_memories = storage.list_memories(memory_type="profile", status="active")

    # Search for other relevant memories
    search_results = storage.search_memories(
        query=query,
        limit=limit,
        min_confidence=0.0,
    )

    # If no search results, list all facts/preferences
    if not search_results:
        other_memories = storage.list_memories(
            memory_type=("fact", "preference"),
            status="active",
        )
    else:
        other_memories = search_results

    return profile_memories + other_memories[:limit]
```

**Pros**: Best of both worlds
**Cons**: More complex

---

## Recommended Fix

**Option 3 (Hybrid)** with simplification:

```python
def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve relevant memories for a query.

    Strategy:
    1. Always include all profile memories (name, role, etc.)
    2. Search for other memories using semantic search
    3. If search returns < 3 results, fall back to listing all active memories
    """
    try:
        from executive_assistant.storage.mem_storage import get_mem_storage

        storage = get_mem_storage()

        # 1. Always include profile memories
        profile_memories = storage.list_memories(
            memory_type="profile",
            status="active",
            thread_id=thread_id,
        )

        # 2. Search for other memories
        search_results = storage.search_memories(
            query=query,
            limit=limit,
            min_confidence=0.0,  # Lower threshold for better recall
            thread_id=thread_id,
        )

        # 3. If few results, get more memories
        if len(search_results) < 3:
            all_memories = storage.list_memories(
                status="active",
                thread_id=thread_id,
            )
            # Remove duplicates and profile memories (already included)
            seen = {m["id"] for m in profile_memories}
            for m in all_memories:
                if m["id"] not in seen:
                    search_results.append(m)
                    seen.add(m["id"])

        # Combine: profile first, then others by relevance
        return profile_memories + search_results[:limit]

    except Exception:
        # Don't fail if memory system isn't set up
        return []
```

---

## Testing the Fix

After implementing the fix, test with:

```bash
# Test 1: Create memories
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"hi","user_id":"test_memory_fix","stream":false}'

curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"My name is Alice, I am a product manager","user_id":"test_memory_fix","stream":false}'

# Test 2: Retrieve in new conversation
# (Restart agent first)
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"What do you remember about me?","user_id":"test_memory_fix","stream":false}'

# Should respond: "You're Alice, a product manager"
```

---

## Priority

🔴 **URGENT** - This is a critical production bug affecting all models:
- Users must repeat information every conversation
- Onboarding runs repeatedly
- Poor user experience
- Broken core feature

---

## Related Files

- `src/executive_assistant/channels/base.py:508` - `_get_relevant_memories`
- `src/executive_assistant/storage/mem_storage.py:589` - `search_memories`
- `src/executive_assistant/storage/mem_storage.py:540` - `list_memories`
- `src/executive_assistant/tools/mem_tools.py:148` - `list_memories` tool

---

## Next Steps

1. Implement the hybrid fix in `base.py`
2. Add integration test for memory retrieval
3. Test with all models
4. Verify onboarding flow works correctly
5. Update documentation if needed
