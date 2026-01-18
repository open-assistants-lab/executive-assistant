# DuckDB + VSS + Fulltext KB Implementation Plan

## Goal

Replace SeekDB with DuckDB + VSS for cross-platform, faster KB functionality.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KB Tools (kb_tools.py)                   │
│  create_kb_collection, search_kb, add_kb_documents, etc.   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              DuckDB KB Backend (duckdb_kb.py)               │
│  - Collection management                                    │
│  - Document CRUD                                            │
│  - Fulltext + Vector search                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    DuckDB + Extensions                       │
│  ├── fulltext (FTS)                                         │
│  └── vss (Vector Similarity Search)                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Local Embedding Model (optional)                │
│  - sentence-transformers (all-MiniLM-L6-v2)                 │
│  - Cached embeddings                                         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Create `duckdb_kb.py` Module

```python
# src/cassey/storage/duckdb_kb.py

class DuckDBKBCollection:
    """DuckDB-based KB collection with fulltext and vector search."""

    def __init__(self, name: str, storage_path: Path, embedding_mode: str = "none"):
        self.name = name
        self.storage_path = storage_path
        self.embedding_mode = embedding_mode
        self.db_path = storage_path / f"{name}.db"
        self._conn = None
        self._embedding_function = None

    @property
    def conn(self):
        """Lazy connection with extensions loaded."""
        if self._conn is None:
            import duckdb
            self._conn = duckdb.connect(str(self.db_path))
            # Load extensions
            self._conn.execute("INSTALL fulltext;")
            self._conn.execute("LOAD fulltext;")
            if self.embedding_mode != "none":
                self._conn.execute("INSTALL vss;")
                self._conn.execute("LOAD vss;")
                self._init_embeddings()
            self._init_tables()
        return self._conn

    def _init_tables(self):
        """Initialize KB tables."""
        # Main documents table
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.name}_docs (
                id VARCHAR PRIMARY KEY,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Fulltext index
        self.conn.execute(f"""
            CREATE OR REPLACE VIEW {self.name}_fts_view AS
            SELECT id, content FROM {self.name}_docs;
        """)
        self.conn.execute(f"""
            PRAGMA create_fts_index(
                {self.name}_docs, {self.name}_fts, content
            );
        """)

        # Vector table (if enabled)
        if self.embedding_mode != "none":
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.name}_vectors (
                    id VARCHAR PRIMARY KEY REFERENCES {self.name}_docs(id),
                    embedding FLOAT[{self._embedding_function.dimension}]
                );
            """)
            self.conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.name}_vss_idx
                ON {self.name}_vectors USING HNSW (embedding);
            """)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        """Add documents to the collection."""
        # Insert documents
        for doc_id, content, meta in zip(ids, documents, metadatas):
            self.conn.execute(f"""
                INSERT INTO {self.name}_docs (id, content, metadata)
                VALUES (?, ?, ?)
            """, [doc_id, content, json.dumps(meta)])

        # Generate embeddings if enabled
        if self.embedding_mode != "none":
            embeddings = self._embedding_function.embed(documents)
            for doc_id, emb in zip(ids, embeddings):
                self.conn.execute(f"""
                    INSERT INTO {self.name}_vectors (id, embedding)
                    VALUES (?, ?)
                """, [doc_id, str(emb)])

    def search(self, query: str, limit: int = 5):
        """Search using fulltext and/or vector similarity."""
        if self.embedding_mode == "none":
            # Fulltext only
            return self.conn.execute(f"""
                SELECT d.id, d.content, d.metadata,
                       fts.main_index match_rank(d.content, ?) as score
                FROM {self.name}_docs d
                WHERE fts_main_index match_rank(d.content, ?) IS NOT NULL
                ORDER BY score DESC
                LIMIT ?
            """, [query, query, limit]).fetchall()
        else:
            # Hybrid search
            query_vec = self._embedding_function.embed([query])[0]
            return self.conn.execute(f"""
                SELECT d.id, d.content, d.metadata,
                       vss_search(v.embedding, ?::FLOAT[{self._embedding_function.dimension}]) as vector_score,
                       fts_main_index match_rank(d.content, ?) as fts_score
                FROM {self.name}_docs d
                JOIN {self.name}_vectors v ON d.id = v.id
                WHERE fts_main_index match_rank(d.content, ?) IS NOT NULL
                ORDER BY vector_score DESC
                LIMIT ?
            """, [str(query_vec), query, query, limit]).fetchall()

    def count(self) -> int:
        """Return document count."""
        return self.conn.execute(f"SELECT COUNT(*) FROM {self.name}_docs").fetchone()[0]

    def delete(self):
        """Delete the collection."""
        if self._conn:
            self._conn.close()
        self.db_path.unlink(missing_ok=True)
```

### 2. Embedding Function

```python
# src/cassey/storage/embeddings.py

from functools import lru_cache
from sentence_transformers import SentenceTransformer

class LocalEmbeddingFunction:
    """Local sentence-transformers embedding function."""

    MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dims, fast, good quality

    def __init__(self, model_name: str = MODEL_NAME):
        self._model = None
        self.model_name = model_name

    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return 384  # all-MiniLM-L6-v2

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts, with caching."""
        return self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=False
        )

@lru_cache(maxsize=1)
def get_embedding_function():
    """Get cached embedding function."""
    return LocalEmbeddingFunction()
```

### 3. Update KB Tools

Replace seekdb_storage with duckdb_kb in:
- `kb_tools.py` - update all tool functions
- `tools/registry.py` - update imports

### 4. Settings

Add to `.env`:
```bash
# KB Backend (seekdb | duckdb)
KB_BACKEND=duckdb

# DuckDB-specific
DUCKDB_EMBEDDING_MODE=local  # local | none | openai
DUCKDB_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "duckdb>=1.0.0",
    "sentence-transformers>=3.0.0",  # For local embeddings
]
```

## Performance Expectations

| Operation | SeekDB | DuckDB (fulltext) | DuckDB (fulltext+vector) |
|-----------|--------|-------------------|--------------------------|
| Ingest 9MB doc | ~42 min | **~30-60 sec** | **~2-5 min** |
| Search | ~1 sec | **~50-200ms** | **~100-300ms** |
| Cross-platform | ❌ | ✅ | ✅ |

## Migration Strategy

1. Implement `duckdb_kb.py` alongside existing `seekdb_storage.py`
2. Add `KB_BACKEND` setting (default: seekdb for compatibility)
3. Update tools to route based on backend
4. Test with tax document
5. Flip default to duckdb once stable
6. Deprecate SeekDB path

## Next Steps

1. Create `duckdb_kb.py` with basic CRUD
2. Benchmark against SeekDB
3. Add embedding support
4. Update KB tools integration
5. Add tests
