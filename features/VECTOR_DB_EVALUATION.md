# Memory Database Architecture: SQLite+FTS5 vs Vector DBs

**Current**: SQLite + FTS5
**Alternatives**: LanceDB, ChromaDB, Qdrant, Weaviate

---

## Current Architecture: SQLite + FTS5

### How It Works
```python
# Each user has their own SQLite DB
data/users/http_{user_id}/mem/mem.db

# FTS5 full-text search
SELECT * FROM mem_fts
WHERE mem_fts MATCH 'product manager'
ORDER BY rank
```

### Strengths
- ✅ **Zero dependencies** - Built into Python
- ✅ **Thread-local storage** - Each user has isolated DB
- ✅ **Fast** - FTS5 is optimized for text search
- ✅ **Reliable** - SQLite is battle-tested
- ✅ **Simple** - No external services
- ✅ **Lightweight** - < 1MB per user

### Weaknesses
- ❌ **Keyword-based only** - No semantic understanding
- ❌ **Poor at general queries** - "What do you remember?" finds nothing
- ❌ **No concept similarity** - "sales" doesn't match "revenue"
- ❌ **Requires keyword overlap** - Query must contain memory words

---

## Vector DB Alternative: LanceDB/ChromaDB

### How It Works
```python
# Store embeddings with metadata
memory = {
    "content": "Alice is a product manager",
    "embedding": [0.1, 0.2, ...],  # OpenAI/Cohere/embedding model
    "type": "profile"
}

# Semantic search
results = db.search(
    query="What do you remember?",
    query_type="semantic"  # Finds related concepts
)
```

### Strengths
- ✅ **Semantic search** - Finds related concepts by meaning
- ✅ **Better for general queries** - "What do you remember?" matches profiles
- ✅ **Concept similarity** - "sales" matches "revenue", "customers"
- ✅ **Hybrid search** - Can combine keyword + semantic

### Weaknesses
- ❌ **External dependency** - Another service to manage
- ❌ **Embedding costs** - API calls or local model (memory/CPU)
- ❌ **More complex** - Orchestration, failures, monitoring
- ❌ **Heavier** - 50-200MB vs < 1MB for SQLite
- ❌ **Cloud vs local** - Trade-offs either way

---

## The Real Question: Do We Need Semantic Search?

### Current Memory Types

1. **Profile memories** (name, role, company)
   - Should be **ALWAYS loaded**, not searched
   - Doesn't need semantic search

2. **Facts** (user preferences, constraints)
   - Could benefit from semantic search
   - "I don't like seafood" → "No fish dishes"

3. **Context** (conversation history)
   - Could benefit from semantic search
   - Find related past discussions

### Use Case Analysis

| Memory Type | Current Search | Vector DB | Needed? |
|-------------|---------------|-----------|---------|
| Profile (name, role) | ❌ Fails | ✅ Better | No - Always load |
| Preferences (likes/dislikes) | ⚠️ Limited | ✅ Better | **Maybe** |
| Facts (projects, goals) | ⚠️ Limited | ✅ Better | **Maybe** |
| Context (conversations) | ❌ Poor | ✅ Good | **Yes** |

---

## Recommendation: Hybrid Approach

### Short-term: Fix Current System (No Vector DB)

**Why**: The bug is in HOW we use SQLite, not SQLite itself.

**Solution**:
```python
def _get_relevant_memories(self, thread_id: str, query: str, limit: int = 5):
    storage = get_mem_storage()

    # 1. Always load profile memories (no search)
    profile_memories = storage.list_memories(
        memory_type="profile",
        status="active",
        thread_id=thread_id,
    )

    # 2. For other memories, use smart strategy
    query_lower = query.lower()

    # General questions? List all
    if any(p in query_lower for p in [
        "what do you remember",
        "what do you know",
        "tell me about",
        "who am i"
    ]):
        return profile_memories + storage.list_memories(status="active")

    # Specific queries? Search
    return profile_memories + storage.search_memories(
        query=query,
        limit=limit,
        thread_id=thread_id,
    )
```

**Benefits**:
- ✅ Fixes the bug without new dependencies
- ✅ Profile memories always available
- ✅ Keeps SQLite simplicity
- ✅ Can implement in < 1 hour

---

### Long-term: Add Vector DB for Context Memories

**Why**: Semantic search is valuable for conversation context.

**Architecture**:
```python
# Hybrid storage: SQLite + Vector DB
class HybridMemoryStorage:
    def __init__(self):
        self.sqlite = SQLiteStorage()      # Profile, facts, preferences
        self.vector = LanceDBStorage()     # Context, conversations

    def add_memory(self, content, type):
        if type in ("profile", "fact", "preference"):
            self.sqlite.add_memory(content, type)
        else:
            self.vector.add_memory(content, type)

    def search(self, query):
        # Always get profile
        results = self.sqlite.list_memories(type="profile")

        # Semantic search for context
        results += self.vector.search(query)

        # Keyword search for facts
        results += self.sqlite.search_memories(query)

        return results
```

**Benefits**:
- ✅ Best of both worlds
- ✅ Profile/facts in SQLite (fast, simple)
- ✅ Context in vector DB (semantic search)
- ✅ Gradual migration

**Effort**: 2-3 days (setup, migration, testing)

---

## Vector DB Options

### LanceDB (Recommended for Local)

**Pros**:
- ✅ Embedded (no server)
- ✅ Python-native
- ✅ Works with DuckDB (analytics)
- ✅ Cloud storage support (S3)
- ✅ < 100MB footprint

**Cons**:
- ⚠️ Newer project (less mature)
- ⚠️ Smaller community

**Use Case**: Local-first, simple deployment

```python
import lancedb

db = lancedb.connect("./data/lancedb")
table = db.create_table("memories", data=memories)

# Semantic search
results = table.search("What do you remember?").limit(5).to_df()
```

---

### ChromaDB (Recommended for Cloud)

**Pros**:
- ✅ Mature, widely used
- ✅ Large community
- ✅ Cloud-native
- ✅ Built-in embeddings support

**Cons**:
- ❌ Requires server (Docker/container)
- ❌ More complex setup
- ❌ Heavier footprint

**Use Case**: Cloud deployment, need scaling

```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.get_or_create_collection("memories")

results = collection.query(
    query_texts=["What do you remember?"],
    n_results=5
)
```

---

### Qdrant (Recommended for Production)

**Pros**:
- ✅ Production-ready
- ✅ High performance
- ✅ Hybrid search (keyword + semantic)
- ✅ Good filtering

**Cons**:
- ❌ Requires server
- ❌ More complex setup

**Use Case**: Large-scale production

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
results = client.search(
    collection_name="memories",
    query_vector=embed("What do you remember?"),
    limit=5
)
```

---

## Cost Comparison

### SQLite + FTS5 (Current)
- **Storage**: $0 (embedded)
- **Compute**: $0 (CPU only)
- **Dependencies**: 0
- **Complexity**: Low

### LanceDB (Local Vector DB)
- **Storage**: $0 (embedded)
- **Compute**: $0-50/month (local embeddings) or $10-100/month (OpenAI embeddings)
- **Dependencies**: 1 (lancedb)
- **Complexity**: Medium

### ChromaDB (Cloud Vector DB)
- **Storage**: $10-50/month (hosting)
- **Compute**: $10-100/month (embeddings)
- **Dependencies**: 2 (chromadb + server)
- **Complexity**: High

---

## Recommendation

### Phase 1: Fix Current System (This Week)
- Implement hybrid approach in SQLite
- Profile memories always loaded
- Smart detection of general queries
- **Effort**: 2-4 hours
- **Benefit**: Fixes bug without new deps

### Phase 2: Add LanceDB for Context (Next Sprint)
- Keep SQLite for profile/facts/preferences
- Add LanceDB for conversation context
- Semantic search for "What did we discuss about X?"
- **Effort**: 2-3 days
- **Benefit**: Better context retrieval

### Phase 3: Evaluate & Optimize (Future)
- Measure retrieval quality
- A/B test SQLite vs LanceDB
- User feedback on memory relevance
- Decide if full migration needed

---

## Decision Matrix

| Factor | SQLite Fix | LanceDB | ChromaDB |
|--------|-----------|---------|----------|
| **Time to implement** | 2-4 hours | 2-3 days | 3-5 days |
| **Dependencies** | 0 | 1 | 2 |
| **Complexity** | Low | Medium | High |
| **Semantic search** | ⚠️ Limited | ✅ Yes | ✅ Yes |
| **Local-first** | ✅ Yes | ✅ Yes | ❌ No |
| **Production-ready** | ✅ Yes | ⚠️ New | ✅ Yes |
| **Cost** | Free | Free-$50 | $20-$150 |
| **Migration effort** | None | Low | Medium |

---

## My Recommendation

**Start with SQLite fix** (Phase 1):
- Fixes the immediate bug
- No new dependencies
- Profile memories always loaded
- Can implement today

**Add LanceDB later** (Phase 2):
- When you need semantic context search
- Keep SQLite for structured data
- Gradual migration path

**Skip ChromaDB/Qdrant for now**:
- Overkill for current needs
- More complexity than benefit
- Revisit if scaling issues

---

## Implementation Plan

### Phase 1: Fix SQLite (Today)

```bash
# File: src/executive_assistant/channels/base.py
# Modify: _get_relevant_memories function
```

### Phase 2: Add LanceDB (Next Sprint)

```bash
# Install
pip install lancedb

# File: src/executive_assistant/storage/vector_storage.py (new)
# Implement: HybridMemoryStorage class
```

### Phase 3: Evaluate (Future)

```bash
# Test semantic search quality
# Measure performance
# User feedback
# Decide on full migration
```

---

**Bottom Line**: Fix SQLite first (it's not SQLite's fault), then add LanceDB if you need semantic search for context memories.
