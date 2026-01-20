# DuckDB FTS Index Observations

## Issue: FTS Index Created But Not Used

### Current Implementation in `duckdb_storage.py`

```python
# FTS index IS created (line 381)
conn.execute(f'PRAGMA create_fts_index("{docs_table}", "id", "content")')

# But hybrid search uses LIKE, not the FTS index (lines 171-178)
def _search_hybrid(self, query: str, limit: int) -> list[SearchResult]:
    results = self.conn.execute(f"""
        SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[384]) as distance
        FROM {table_name} d
        JOIN {vector_table} v ON d.id = v.id
        WHERE d.content LIKE ?              # ← NOT using FTS!
        ORDER BY distance
        LIMIT ?
    """, [query_vec, f"%{query}%", limit]).fetchall()
```

**Problem**: The FTS index is created but never used. Hybrid search falls back to `LIKE %%` pattern matching.

---

## Why This Matters

| Aspect | Current (LIKE) | Proper FTS |
|--------|----------------|------------|
| **Performance** | O(n) full table scan | O(log n) index lookup |
| **Ranking** | None | BM25 relevance scoring |
| **Query features** | Wildcard only | Boolean, phrase, proximity |
| **Index overhead** | Wasted storage | Actually utilized |

**Benchmark impact**: On large collections (>10K documents), the FTS index could provide 10-100x faster filtering.

---

## How FTS Should Be Used

### mem_storage.py (Correct Usage)

```python
# Create index
conn.execute("PRAGMA create_fts_index('memories', 'id', 'content', 'key')")

# Search using the index
conn.execute("""
    SELECT ...
    FROM memories
    WHERE fts_memories.match_bm25(id, ?) IS NOT NULL
    ORDER BY fts_memories.match_bm25(id, ?) ASC
""", (query, query))
```

**Key**: Uses `fts_memories.match_bm25()` to actually query the FTS index.

---

## What DuckDB FTS Actually Provides

DuckDB's FTS extension creates a **separate virtual table** for full-text search:

```sql
-- After: PRAGMA create_fts_index("my_docs", "id", "content")
-- A virtual table is created: my_docs_fts

-- Correct usage:
SELECT * FROM my_docs
WHERE my_docs_fts.match_bm25(id, 'search query')
ORDER BY my_docs_fts.match_bm25(id, 'search query');
```

### Available FTS Functions

| Function | Purpose |
|----------|---------|
| `match_bm25(doc_id, query)` | BM25 relevance score (main search function) |
| `match_query(doc_id, query)` | Boolean match (no scoring) |

---

## How to Fix KB Hybrid Search

### Option 1: True Hybrid (FTS filter + VSS rank)

```python
def _search_hybrid(self, query: str, limit: int) -> list[SearchResult]:
    query_vec = get_embeddings([query])[0]

    table_name = self._table_name()
    fts_table = f'"{table_name[1:-1]}_fts"'  # FTS virtual table name
    vector_table = self._vector_table_name()

    results = self.conn.execute(f"""
        SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[384]) as distance
        FROM {table_name} d
        JOIN {vector_table} v ON d.id = v.id
        WHERE {fts_table}.match_bm25(d.id, ?) IS NOT NULL
        ORDER BY distance
        LIMIT ?
    """, [query_vec, query, limit]).fetchall()

    return [self._format_result(r) for r in results]
```

**Pros**:
- Uses FTS for fast filtering
- VSS provides semantic ranking
- Best of both worlds

**Cons**:
- More complex query
- Need to know FTS table name convention

### Option 2: FTS-Only Fast Path

```python
def search(self, query: str, limit: int = 5, search_type: str = "hybrid") -> list[SearchResult]:
    if search_type == "fulltext":
        # Use FTS with BM25 ranking
        fts_table = f'"{self._safe_name(self.workspace_id)}_{self._safe_name(self.name)}_fts"'
        results = self.conn.execute(f"""
            SELECT d.content, d.metadata,
                   {fts_table}.match_bm25(d.id, ?) as score
            FROM {self._table_name()} d
            WHERE {fts_table}.match_bm25(d.id, ?) IS NOT NULL
            ORDER BY score
            LIMIT ?
        """, [query, query, limit]).fetchall()
        return [self._format_result(r) for r in results]
```

### Option 3: Keep Current (Document as Is)

Current implementation works but doesn't leverage the FTS index:
- Index is created but unused
- `LIKE %%` is slower but functional
- For small collections (<1000 docs), performance difference is negligible

---

## FTS Index Name Convention

Based on DuckDB FTS behavior, the index name follows this pattern:

```python
# Docs table: "workspace__collection_docs"
# FTS table:  "workspace__collection_docs_fts"  (auto-created)
```

The `PRAGMA create_fts_index()` creates a virtual table with `_fts` suffix.

---

## Verification

To verify FTS is working:

```sql
-- Check if FTS table exists
SELECT table_name FROM information_schema.tables
WHERE table_name LIKE '%_fts';

-- Test FTS query
SELECT * FROM docs_table
WHERE docs_table_fts.match_bm25(id, 'test query')
LIMIT 10;
```

---

## Recommendations

1. **For KB (duckdb_storage.py)**:
   - Fix `_search_hybrid()` to use actual FTS index
   - Add `search_fulltext()` method using BM25 ranking
   - Keep vector search as-is for semantic queries

2. **For Mem (mem_storage.py)**:
   - Current implementation is correct
   - Uses `match_bm25()` properly
   - No changes needed

3. **Testing**:
   - Add benchmarks comparing LIKE vs FTS performance
   - Test with collections >10K documents to see difference
   - Verify FTS index is actually used (EXPLAIN query plan)

---

## Related Files

| File | Status |
|------|--------|
| `src/executive_assistant/storage/duckdb_storage.py` | ⚠️ FTS created but not used |
| `src/executive_assistant/storage/mem_storage.py` | ✅ FTS used correctly |
| `tests/hybrid_benchmark.py` | ⚠️ Also uses LIKE instead of FTS |
