# SeekDB-Only KB Plan

## Objective
Replace the DuckDB-based KB stack with SeekDB as the **sole** KB backend. No fallback or live re-enablement of DuckDB will remain—if we ever roll back, it happens by reverting the commit/configuration history, not toggling at runtime.

**SeekDB Reference:** [oceanbase/pyseekdb](https://github.com/oceanbase/pyseekdb) - AI-native search database from OceanBase (Apache 2.0, released Nov 2025).

---

## Why "Collection" instead of "Table"?

SeekDB uses the term **"collection"** (not "table") for its primary data grouping construct. This aligns with modern vector databases (ChromaDB, Qdrant, Weaviate) and accurately reflects that a collection stores:

1. **Documents** - text content with embeddings
2. **Metadata** - flexible key-value pairs per document
3. **Vector indexes** - HNSW for similarity search
4. **Full-text indexes** - for text search

Unlike SQL tables with fixed schemas, SeekDB collections are schema-flexible and designed specifically for AI/ML workloads (RAG, semantic search).

**Tool naming decision:** Using "collection" in tool names (`create_kb_collection`, not `create_kb_table`) avoids confusion and matches SeekDB's native terminology.

---

## Persistence Model
- SeekDB runs as an embedded engine per thread. Each thread's SeekDB database is stored under `data/users/{thread_id}/kb/` (a directory per thread).
- The `pyseekdb.Client(path=directory, database="kb")` in embedded mode persists to disk automatically; it writes `seekdb.db`, `seekdb.db-wal`, and `seekdb.db-shm` files in the specified directory.
- Metadata (collections, indexes, embeddings) lives inside the SeekDB database file, keeping scope bounded and matching our per-user isolation policy.

**Files created (per thread):**
```
data/users/{thread_id}/kb/
├── seekdb.db          # Main database file
├── seekdb.db-wal      # Write-Ahead Log
└── seekdb.db-shm      # Shared memory (if needed)
```

---

## Implementation Steps

### 1. Clean up DuckDB KB code
- Remove `src/cassey/storage/kb_storage.py` and the DuckDB-specific helper functions.
- Delete `src/cassey/storage/kb_tools.py` entirely—the tool surface will be reimplemented to talk to SeekDB.
- Remove KB-related settings (`KB_ROOT`, `get_thread_kb_path`, `KB_BACKEND`, any `duckdb` dependencies in `pyproject.toml`).
- Remove `rapidfuzz>=3.6.0` from dependencies (no longer needed for fuzzy fallback).
- Drop any DuckDB FTS references from docs (README, prompts, discussions, TODO).

### 2. Add SeekDB storage layer
- Create `src/cassey/storage/seekdb_storage.py`.
- Provide:
  ```python
  from functools import lru_cache
  from pathlib import Path
  import pyseekdb

  def get_thread_seekdb_path(thread_id: str) -> Path:
      """Get the SeekDB directory path for a thread.

      Returns: data/users/{thread_id}/kb/
      """
      sanitized = sanitize_thread_id(thread_id)
      return (settings.SEEKDB_DATA_ROOT / sanitized / "kb").mkdir(parents=True, exist_ok=True)

  @lru_cache(maxsize=128)
  def get_seekdb_client(thread_id: str) -> pyseekdb.Client:
      """Get or create a cached SeekDB client for the thread.

      IMPORTANT: path is a DIRECTORY, not a file. SeekDB creates seekdb.db inside.
      """
      kb_dir = get_thread_seekdb_path(thread_id)
      return pyseekdb.Client(path=str(kb_dir), database="kb")

  def ensure_collection(thread_id: str, collection_name: str, embedding_function=None):
      """Get or create a collection in the thread's KB."""
      client = get_seekdb_client(thread_id)
      return client.get_or_create_collection(name=collection_name, embedding_function=embedding_function)
  ```
- Expose metadata recording (via `meta_registry`) for collection creation/deletion.

### 3. Rebuild KB tools with "collection" terminology
- Create `src/cassey/storage/seekdb_tools.py` that implements the tools using SeekDB's collection concept.
- **Tool names (renamed from DuckDB version):**

  | Old (DuckDB) | New (SeekDB) |
  |--------------|--------------|
  | `create_kb_table` | `create_kb_collection` |
  | `drop_kb_table` | `drop_kb_collection` |
  | `describe_kb` | `describe_kb_collection` |
  | `search_kb` | `search_kb` (unchanged - searches across collections) |
  | `kb_list` | `kb_list` (unchanged - lists collections) |
  | `add_kb_documents` | `add_kb_documents` (unchanged) |
  | `delete_kb_documents` | `delete_kb_documents` (unchanged) |

- **Tool implementation patterns:**

  **create_kb_collection:**
  ```python
  from pyseekdb import DefaultEmbeddingFunction, Configuration, HNSWConfiguration

  client = get_seekdb_client(thread_id)
  ef = DefaultEmbeddingFunction()  # ONNX-based, 384 dimensions, no API key
  config = Configuration(hnsw=HNSWConfiguration(dimension=384, distance='cosine'))

  collection = client.create_collection(
      name=collection_name,
      configuration=config,
      embedding_function=ef
  )

  # Add documents (NOTE: parameters are PLURAL)
  if parsed_docs:
      collection.add(
          ids=[doc["id"] for doc in parsed_docs],
          documents=[doc["content"] for doc in parsed_docs],
          metadatas=[doc.get("metadata", "") for doc in parsed_docs]
      )
  ```

  **search_kb:**
  ```python
  collection = client.get_collection(collection_name)

  # Hybrid search: full-text + vector with RRF rank fusion
  results = collection.hybrid_search(
      query={"where_document": {"$contains": query}, "boost": 0.5},
      knn={"query_texts": [query], "n_results": 10, "boost": 0.8},
      rank={"rrf": {"rank_window_size": 60, "rank_constant": 60}},
      n_results=limit,
  )
  # Returns: {"ids": [...], "distances": [...], "documents": [...], "metadatas": [...]}

  # Fallback to get() if no results
  if not results["ids"]:
      results = collection.get(where_document={"$contains": query}, limit=limit)
  ```

  **kb_list:**
  ```python
  client = get_seekdb_client(thread_id)
  collections = client.list_collections()
  # Format: "Knowledge Base collections:\n- notes: 12 documents (vector + FTS indexed)"
  ```

  **drop_kb_collection:**
  ```python
  client.delete_collection(collection_name)
  ```

- Map output format to be user-friendly (no need to match DuckDB exactly).
- No RapidFuzz dependency (SeekDB handles fuzzy matching via hybrid search).

### 4. Settings + dependencies
- Add SeekDB-specific settings to `src/cassey/config/settings.py`:
  ```python
  # SeekDB KB (embedded mode, per-thread)
  SEEKDB_DATA_ROOT: Path | None = None  # Optional override, defaults to data/users/
  # Embedding mode: "default" (ONNX), "local" (sentence-transformers), "api" (OpenAI/DashScope)
  SEEKDB_EMBEDDING_MODE: Literal["default", "local", "api"] = "default"
  # For "local" mode
  SEEKDB_LOCAL_MODEL: str = "all-MiniLM-L6-v2"
  # For "api" mode - reuse existing keys
  OPENAI_API_KEY: str | None = None
  DASHSCOPE_API_KEY: str | None = None
  ```
- Update `.env.example`:
  ```bash
  # SeekDB Knowledge Base (embedded vector + FTS database)
  SEEKDB_DATA_ROOT=data/users
  SEEKDB_EMBEDDING_MODE=default  # Options: default (ONNX), local (sentence-transformers), api (OpenAI/DashScope)
  SEEKDB_LOCAL_MODEL=all-MiniLM-L6-v2  # For SEEKDB_EMBEDDING_MODE=local
  # For api mode, use OPENAI_API_KEY or DASHSCOPE_API_KEY
  ```
- Update `pyproject.toml`:
  - **Add:** `pyseekdb>=0.1.0` (check actual version on PyPI)
  - **Optional:** `sentence-transformers` (only if `SEEKDB_EMBEDDING_MODE=local`)
  - **Remove:** `duckdb>=1.1.0`, `rapidfuzz>=3.6.0`

### 5. Tool registry + tests
- Point `src/cassey/tools/registry.py` KB section to the new SeekDB tool module:
  ```python
  async def get_kb_tools() -> list[BaseTool]:
      from cassey.storage.seekdb_tools import get_kb_tools as _get
      return await _get()
  ```
- Write unit tests covering SeekDB tool behavior (create/add/search/delete/list).
- Test per-thread client isolation and caching.
- Test hybrid search results format.

### 6. Docs
- Replace DuckDB mentions with SeekDB:
  - README: Update KB section to reference SeekDB and "collections" terminology
  - Prompts: Update TELEGRAM_PROMPT to use "collection" instead of "table":
    - **Old:** "Use KB to store facts... create_kb_table to create a table"
    - **New:** "Use KB to store facts... create_kb_collection to create a collection"
  - Discussions: Archive DuckDB-related plans, add SeekDB migration notes
- Document persistence path: `data/users/{thread_id}/kb/seekdb.db`
- Document rollback approach: "KB uses SeekDB only; rollback requires reverting to commit before this change"
- **IMPORTANT:** Update any prompt text that says "table" to say "collection" for KB operations

### 7. Rollback Strategy
- No runtime toggles - SeekDB is the only supported KB backend.
- Document in README: "To revert to DuckDB KB, git revert to commit before [commit hash]"
- Keep DuckDB code in git history for reference, but remove from runtime.

---

## Quality Gates
- All KB tools use "collection" terminology consistently.
- Tests simulate per-thread behavior (mock `thread_id` context).
- The SeekDB embedded client is cached via `lru_cache` and closed cleanly between operations.
- SeekDB directories are created lazily, following the existing `get_thread_root` pattern.
- Hybrid search tested with both vector and full-text queries.
- Verify `path` is directory (not file) when creating `pyseekdb.Client`.
- Prompts/docs updated to use "collection" instead of "table".

---

## Key API References (from pyseekdb docs)

### Client Creation
```python
import pyseekdb

# Embedded mode - path is a DIRECTORY
client = pyseekdb.Client(
    path="./data/users/mythread/kb",  # Directory where seekdb.db will be created
    database="kb"                       # Database name
)
```

### Collection Creation
```python
from pyseekdb import DefaultEmbeddingFunction, Configuration, HNSWConfiguration

ef = DefaultEmbeddingFunction()  # ONNX-based, 384 dims, no API key
config = Configuration(
    hnsw=HNSWConfiguration(dimension=384, distance='cosine')
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=ef
)
```

### Add Documents (parameters are PLURAL)
```python
collection.add(
    ids=["doc1", "doc2"],           # Required, PLURAL
    documents=["text1", "text2"],   # PLURAL
    metadatas=[{"k": "v"}, ...],   # PLURAL
    # embeddings optional if embedding_function is set
)
```

### Hybrid Search
```python
results = collection.hybrid_search(
    query={"where_document": {"$contains": "machine learning"}, "boost": 0.5},
    knn={"query_texts": ["AI research"], "n_results": 10, "boost": 0.8},
    rank={"rrf": {"rank_window_size": 60, "rank_constant": 60}},
    n_results=5,
)
# Returns: {"ids": [...], "distances": [...], "documents": [...], "metadatas": [...]}
```

### Sources
- [pyseekdb GitHub](https://github.com/oceanbase/pyseekdb)
- [SeekDB Release Announcement](https://www.marktechpost.com/2025/11/26/oceanbase-releases-seekdb-an-open-source-ai-native-hybrid-search-database)
- [pyseekdb API Documentation](https://github.com/oceanbase/pyseekdb/blob/develop/README.md)
- [OceanBase AI Blog - SeekDB Tutorials](https://open.oceanbase.com/blog)

---

Once we get buy-in on this approach, I can start the implementation by drafting the new storage/tool modules and settings. Let me know if you'd like me to proceed or adjust any detail before coding.  
