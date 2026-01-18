"""DuckDB + Hybrid (FTS + VSS) storage for Vector Store.

Cross-platform vector + fulltext search using DuckDB extensions.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from cassey.config import settings
from cassey.storage.chunking import get_embeddings
from cassey.storage.group_storage import (
    get_workspace_id,
    sanitize_thread_id,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SearchResult:
    """A search result with content, metadata, and score."""

    content: str
    metadata: dict
    score: float


@dataclass
class DuckDBCollection:
    """A DuckDB VS collection."""

    name: str
    workspace_id: str
    conn: Any  # duckdb.DuckDBConnection
    dimension: int = 384
    path: Path = None

    def count(self) -> int:
        """Return total document count."""
        table_name = self._table_name()
        result = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return result[0] if result else 0

    @property
    def documents(self) -> dict[str, str]:
        """Get all documents as {id: content} dict."""
        table_name = self._table_name()
        results = self.conn.execute(f"SELECT id, content FROM {table_name}").fetchall()
        return {r[0]: r[1] for r in results}

    def add_documents(self, documents: list[dict[str, Any]]) -> int:
        """Add documents to the collection.

        Args:
            documents: List of dicts with 'content' and optional 'metadata'.

        Returns:
            Number of documents added.
        """
        from cassey.storage.chunking import prepare_documents_for_vs

        chunks = prepare_documents_for_vs(documents, auto_chunk=True)

        if not chunks:
            return 0

        table_name = self._table_name()
        vector_table = self._vector_table_name()

        # Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = get_embeddings(texts)

        # Insert documents and vectors
        for chunk, emb in zip(chunks, embeddings):
            doc_id = str(uuid.uuid4())
            self.conn.execute(
                f"INSERT INTO {table_name} (id, document_id, content, metadata) VALUES (?, ?, ?, ?)",
                [doc_id, chunk.metadata.get("document_id", ""), chunk.content, json.dumps(chunk.metadata)]
            )
            self.conn.execute(
                f"INSERT INTO {vector_table} (id, embedding) VALUES (?, ?)",
                [doc_id, emb]
            )

        # Refresh FTS index after adding documents
        # DuckDB FTS doesn't auto-update for inserts
        try:
            docs_table_unquoted = self._table_name_unquoted()
            self.conn.execute(f'PRAGMA drop_fts_index(\'{docs_table_unquoted}\')')
            self.conn.execute(f'PRAGMA create_fts_index(\'{docs_table_unquoted}\', \'id\', \'content\')')
        except Exception:
            pass  # FTS may not exist or other error

        return len(chunks)

    def search(
        self,
        query: str,
        limit: int = 5,
        search_type: str = "hybrid"
    ) -> list[SearchResult]:
        """Search the collection.

        Args:
            query: Search query.
            limit: Max results.
            search_type: 'hybrid', 'vector', or 'fulltext'.

        Returns:
            List of SearchResult objects.
        """
        if search_type == "vector":
            return self.search_vector(query, limit)
        elif search_type == "fulltext":
            return self.search_fulltext(query, limit)
        else:  # hybrid
            return self._search_hybrid(query, limit)

    def search_vector(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Vector-only search (semantic).

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of SearchResult objects.
        """
        query_vec = get_embeddings([query])[0]

        table_name = self._table_name()
        vector_table = self._vector_table_name()

        results = self.conn.execute(f"""
            SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[{self.dimension}]) as distance
            FROM {table_name} d
            JOIN {vector_table} v ON d.id = v.id
            ORDER BY distance
            LIMIT ?
        """, [query_vec, limit]).fetchall()

        return [self._format_result(r) for r in results]

    def search_fulltext(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Fulltext-only search with BM25 ranking.

        Uses DuckDB FTS index for fast, relevance-ranked search.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of SearchResult objects.
        """
        table_name = self._table_name()
        fts_table = self._fts_table_name()

        try:
            # Use FTS with BM25 ranking for relevance scoring
            results = self.conn.execute(f"""
                SELECT d.content, d.metadata, {fts_table}.match_bm25(d.id, ?) as score
                FROM {table_name} d
                WHERE {fts_table}.match_bm25(d.id, ?) IS NOT NULL
                ORDER BY score ASC
                LIMIT ?
            """, [query, query, limit]).fetchall()

            return [self._format_result(r) for r in results]
        except Exception:
            # Fallback to LIKE if FTS is not available (e.g., empty collection)
            results = self.conn.execute(f"""
                SELECT content, metadata, -1.0 as score
                FROM {table_name}
                WHERE content LIKE ?
                LIMIT ?
            """, [f"%{query}%", limit]).fetchall()

            return [self._format_result(r) for r in results]

    def _search_hybrid(self, query: str, limit: int) -> list[SearchResult]:
        """Hybrid search: FTS filter + VSS rank.

        Uses FTS index for fast filtering, then ranks results by vector similarity.
        This provides both keyword relevance and semantic matching.
        """
        query_vec = get_embeddings([query])[0]

        table_name = self._table_name()
        fts_table = self._fts_table_name()
        vector_table = self._vector_table_name()

        try:
            # Use FTS for fast filtering, VSS for semantic ranking
            results = self.conn.execute(f"""
                SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[{self.dimension}]) as distance
                FROM {table_name} d
                JOIN {vector_table} v ON d.id = v.id
                WHERE {fts_table}.match_bm25(d.id, ?) IS NOT NULL
                ORDER BY distance
                LIMIT ?
            """, [query_vec, query, limit]).fetchall()

            return [self._format_result(r) for r in results]
        except Exception:
            # Fallback to LIKE if FTS is not available
            results = self.conn.execute(f"""
                SELECT d.content, d.metadata, array_distance(v.embedding, ?::FLOAT[{self.dimension}]) as distance
                FROM {table_name} d
                JOIN {vector_table} v ON d.id = v.id
                WHERE d.content LIKE ?
                ORDER BY distance
                LIMIT ?
            """, [query_vec, f"%{query}%", limit]).fetchall()

            return [self._format_result(r) for r in results]

    def _format_result(self, row: tuple) -> SearchResult:
        """Format a result row as SearchResult."""
        content = row[0]
        try:
            metadata = json.loads(row[1]) if row[1] else {}
        except:
            metadata = {}
        score = row[2] if len(row) > 2 else 0.0
        return SearchResult(content=content, metadata=metadata, score=score)

    def delete(self, ids: list[str]) -> int:
        """Delete documents by ID.

        Args:
            ids: List of document IDs to delete.

        Returns:
            Number of documents deleted.
        """
        if not ids:
            return 0

        table_name = self._table_name()
        vector_table = self._vector_table_name()

        placeholders = ",".join(["?" for _ in ids])

        # Delete from vectors first (foreign key)
        self.conn.execute(f"DELETE FROM {vector_table} WHERE id IN ({placeholders})", ids)
        # Delete from docs
        result = self.conn.execute(f"DELETE FROM {table_name} WHERE id IN ({placeholders})", ids)

        return result.rowcount

    def _table_name(self) -> str:
        """Get the escaped table name for docs."""
        # Sanitize collection name for SQL
        safe_name = self.name.replace("-", "_").replace(" ", "_")
        safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_")
        return f'"{safe_workspace}__{safe_name}_docs"'

    def _table_name_unquoted(self) -> str:
        """Get the unquoted table name for FTS operations."""
        safe_name = self.name.replace("-", "_").replace(" ", "_")
        safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_")
        return f'{safe_workspace}__{safe_name}_docs'

    def _vector_table_name(self) -> str:
        """Get the escaped table name for vectors."""
        safe_name = self.name.replace("-", "_").replace(" ", "_")
        safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_")
        return f'"{safe_workspace}__{safe_name}_vectors"'

    def _fts_table_name(self) -> str:
        """Get the FTS virtual table name.

        DuckDB FTS creates a virtual table with fts_main_ prefix.
        The table name is the docs table name WITHOUT quotes.

        Example: Docs table "ws__collection_docs" -> FTS table fts_main_ws__collection_docs
        """
        safe_name = self.name.replace("-", "_").replace(" ", "_")
        safe_workspace = self.workspace_id.replace("-", "_").replace(":", "_").replace('"', "_")
        # FTS table: fts_main_{group}_{collection}_docs (no quotes in the name)
        base_name = f'{safe_workspace}__{safe_name}_docs'
        return f'fts_main_{base_name}'


# =============================================================================
# Storage Path Management (Group-based routing)
# =============================================================================

def _get_storage_id() -> str:
    """
    Get the storage ID for VS operations.

    Priority:
    1. group_id from context (new, primary)
    2. thread_id from context (legacy, fallback)

    Returns:
        The storage identifier.

    Raises:
        ValueError: If no group_id or thread_id in context.
    """
    # Try group_id first (new group routing)
    group_id = get_workspace_id()
    if group_id:
        return group_id

    # Fall back to thread_id (legacy routing)
    from cassey.storage.file_sandbox import get_thread_id
    thread_id = get_thread_id()
    if thread_id:
        return thread_id

    raise ValueError("No group_id or thread_id in context")


def get_vs_storage_dir(storage_id: str | None = None) -> Path:
    """
    Return the VS directory for a group or thread.

    Storage layout: data/groups/{group_id}/vs/

    Args:
        storage_id: Group or thread identifier (optional, uses context if None).

    Returns:
        Path to the VS directory.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    if not storage_id:
        raise ValueError("No storage_id provided and none in context")

    # Check if this is a group_id (starts with "ws:") or legacy thread_id
    # For group routing: data/groups/{group_id}/vs/
    # For legacy thread routing: data/users/{thread_id}/vs/
    if storage_id.startswith("ws:"):
        # Group-based storage
        root = settings.GROUPS_ROOT
        path = root / sanitize_thread_id(storage_id) / "vs"
    else:
        # Legacy thread-based storage
        path = settings.get_thread_root(storage_id) / "vs"

    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# DuckDB Client Management
# =============================================================================

@lru_cache(maxsize=128)
def _get_duckdb_connection(thread_id: str, path: Path):
    """Get a cached DuckDB connection for a thread.

    Args:
        thread_id: Thread identifier.
        path: Path to the VS directory.

    Returns:
        DuckDB connection object.
    """
    import duckdb

    db_path = path / "vs.db"
    conn = duckdb.connect(str(db_path))

    # Load extensions
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")
    conn.execute("SET hnsw_enable_experimental_persistence=true;")

    conn.execute("INSTALL fts;")
    conn.execute("LOAD fts;")

    return conn


def get_duckdb_connection(storage_id: str | None = None) -> Any:
    """
    Get a DuckDB connection for a group or thread.

    Args:
        storage_id: Group or thread identifier (optional, uses context if None).

    Returns:
        DuckDB connection object.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    path = get_vs_storage_dir(storage_id)
    return _get_duckdb_connection(storage_id, path)


def reset_connection_cache():
    """Reset the connection cache (for testing)."""
    _get_duckdb_connection.cache_clear()


# =============================================================================
# Collection Management
# =============================================================================

def _sanitize_table_name(name: str) -> str:
    """Sanitize a name for use as a SQL table name."""
    # Remove special characters, keep only alphanumeric and underscore
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


def create_duckdb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    embedding_dimension: int = 384,
    documents: list[dict[str, Any]] | None = None,
    # Deprecated alias for backward compatibility
    workspace_id: str | None = None,
) -> DuckDBCollection:
    """Create a new DuckDB VS collection.

    Args:
        storage_id: Workspace or thread identifier (optional, uses context if None).
        collection_name: Name for the collection.
        embedding_dimension: Vector dimension (default 384 for all-MiniLM-L6-v2).
        documents: Optional initial documents.
        workspace_id: Deprecated alias for storage_id.

    Returns:
        DuckDBCollection instance.
    """
    # Backward compatibility: workspace_id → storage_id
    if workspace_id is not None:
        storage_id = workspace_id

    if storage_id is None:
        storage_id = _get_storage_id()

    conn = get_duckdb_connection(storage_id)

    # Create tables
    safe_name = _sanitize_table_name(collection_name)
    safe_storage = _sanitize_table_name(storage_id)

    docs_table = f'"{safe_storage}__{safe_name}_docs"'
    vectors_table = f'"{safe_storage}__{safe_name}_vectors"'

    # Create documents table
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {docs_table} (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR,
            content TEXT,
            metadata JSON DEFAULT '{{}}',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Create vectors table
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {vectors_table} (
            id VARCHAR PRIMARY KEY,
            embedding FLOAT[{embedding_dimension}],
            FOREIGN KEY (id) REFERENCES {docs_table}(id)
        );
    """)

    # Create HNSW index for vectors
    try:
        conn.execute(f'CREATE INDEX IF NOT EXISTS {safe_storage}_{safe_name}_vss_idx ON {vectors_table} USING HNSW (embedding);')
    except Exception:
        pass  # Index may already exist

    collection = DuckDBCollection(
        name=collection_name,
        workspace_id=storage_id,
        conn=conn,
        dimension=embedding_dimension,
        path=get_vs_storage_dir(storage_id)
    )

    # Add initial documents if provided
    if documents:
        collection.add_documents(documents)

    # Create FTS index AFTER documents are added
    # DuckDB FTS doesn't auto-update for inserts after index creation
    # Note: FTS index needs table name WITHOUT quotes
    try:
        docs_table_unquoted = f'{safe_storage}__{safe_name}_docs'
        # Drop existing FTS index if any, then recreate
        try:
            conn.execute(f'PRAGMA drop_fts_index(\'{docs_table_unquoted}\')')
        except Exception:
            pass  # FTS may not exist yet
        conn.execute(f'PRAGMA create_fts_index(\'{docs_table_unquoted}\', \'id\', \'content\')')
    except Exception:
        pass  # FTS may fail silently if table is empty

    return collection


def get_duckdb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    # Deprecated alias for backward compatibility
    workspace_id: str | None = None,
) -> DuckDBCollection:
    """Get an existing DuckDB collection.

    Args:
        storage_id: Workspace or thread identifier (optional, uses context if None).
        collection_name: Collection name.
        workspace_id: Deprecated alias for storage_id.

    Returns:
        DuckDBCollection instance.
    """
    # Backward compatibility: workspace_id → storage_id
    if workspace_id is not None:
        storage_id = workspace_id

    if storage_id is None:
        storage_id = _get_storage_id()

    conn = get_duckdb_connection(storage_id)

    # Verify collection exists
    safe_name = _sanitize_table_name(collection_name)
    safe_storage = _sanitize_table_name(storage_id)
    docs_table = f'"{safe_storage}__{safe_name}_docs"'

    try:
        result = conn.execute(f"SELECT * FROM {docs_table} LIMIT 1").fetchone()
    except Exception:
        raise ValueError(f"Collection '{collection_name}' not found")

    return DuckDBCollection(
        name=collection_name,
        workspace_id=storage_id,
        conn=conn,
        path=get_vs_storage_dir(storage_id)
    )


def list_duckdb_collections(
    storage_id: str | None = None,
    # Deprecated alias for backward compatibility
    workspace_id: str | None = None,
) -> list[str]:
    """List all collection names for a group or thread.

    Args:
        storage_id: Group or thread identifier (optional, uses context if None).
        workspace_id: Deprecated alias for storage_id.

    Returns:
        List of collection names.
    """
    # Backward compatibility: workspace_id → storage_id
    if workspace_id is not None:
        storage_id = workspace_id

    if storage_id is None:
        storage_id = _get_storage_id()

    conn = get_duckdb_connection(storage_id)

    # Get all tables
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()

    # Filter for docs tables (ends with _docs) and belongs to this storage
    safe_storage = _sanitize_table_name(storage_id)
    collection_names = set()

    # Try both with and without quotes for compatibility
    prefixes = [
        f'"{safe_storage}__',
        f'{safe_storage}__',  # Without quotes
    ]

    for (table_name,) in tables:
        if table_name.endswith("_docs"):
            for prefix in prefixes:
                if table_name.startswith(prefix):
                    # Extract collection name: storage__collection_docs -> collection
                    suffix = table_name[len(prefix):-5]
                    if suffix:
                        # Remove trailing quote if present (only one, not all)
                        suffix = suffix[:-1] if suffix.endswith('"') else suffix
                        collection_names.add(suffix)

    return list(collection_names)


def drop_duckdb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    # Deprecated alias for backward compatibility
    workspace_id: str | None = None,
) -> bool:
    """Drop a DuckDB collection.

    Args:
        storage_id: Workspace or thread identifier (optional, uses context if None).
        collection_name: Collection name.
        workspace_id: Deprecated alias for storage_id.

    Returns:
        True if dropped, False if not found.
    """
    # Backward compatibility: workspace_id → storage_id
    if workspace_id is not None:
        storage_id = workspace_id

    if storage_id is None:
        storage_id = _get_storage_id()

    conn = get_duckdb_connection(storage_id)

    safe_name = _sanitize_table_name(collection_name)
    safe_storage = _sanitize_table_name(storage_id)

    docs_table = f'"{safe_storage}__{safe_name}_docs"'
    vectors_table = f'"{safe_storage}__{safe_name}_vectors"'

    # Drop tables
    try:
        conn.execute(f'DROP TABLE IF EXISTS {vectors_table};')
        conn.execute(f'DROP TABLE IF EXISTS {docs_table};')
        return True
    except Exception:
        return False


def drop_all_duckdb_collections(storage_id: str | None = None) -> int:
    """Drop all collections for a group or thread.

    Args:
        storage_id: Group or thread identifier (optional, uses context if None).

    Returns:
        Number of collections dropped.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    collections = list_duckdb_collections(storage_id)
    count = 0

    for name in collections:
        if drop_duckdb_collection(storage_id, name):
            count += 1

    return count
