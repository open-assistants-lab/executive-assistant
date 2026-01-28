"""LanceDB vector storage implementation.

LanceDB is an embedded, serverless vector database optimized for AI/ML workloads.
This implementation provides the same interface as DuckDB storage for easy comparison.

Multi-tenancy: Each thread gets its own LanceDB database file at:
    data/users/{thread_id}/vdb/.lancedb/
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pyarrow as pa

from executive_assistant.config import settings
from executive_assistant.storage.chunking import get_embeddings
from executive_assistant.storage.thread_storage import get_thread_id, get_thread_path, sanitize_thread_id
from executive_assistant.storage.user_registry import register_vdb_path_best_effort


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
class LanceDBCollection:
    """A LanceDB vector collection."""

    name: str
    thread_id: str
    db: Any  # lancedb.DB
    table: Any  # lancedb.table.Table
    dimension: int = 384
    path: Path = None

    def count(self) -> int:
        """Return total document count."""
        return self.table.count_rows()

    @property
    def documents(self) -> dict[str, str]:
        """Get all documents as {id: content} dict."""
        results = self.table.search().limit(None).to_pandas()
        return {r["id"]: r["content"] for _, r in results.iterrows() if "id" in r and "content" in r}

    def add_documents(self, documents: list[dict[str, Any]]) -> int:
        """Add documents to the collection.

        Args:
            documents: List of dicts with 'content' and optional 'metadata'.

        Returns:
            Number of documents added.
        """
        from executive_assistant.storage.chunking import prepare_documents_for_vdb

        chunks = prepare_documents_for_vdb(documents, auto_chunk=True)

        if not chunks:
            return 0

        # Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = get_embeddings(texts)

        # Prepare data for LanceDB
        data = []
        for chunk, emb in zip(chunks, embeddings):
            data.append({
                "id": str(uuid.uuid4()),
                "document_id": chunk.metadata.get("document_id", ""),
                "content": chunk.content,
                "metadata": json.dumps(chunk.metadata),
                "vector": emb,
            })

        # Add to table
        self.table.add(data)

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

        results = (
            self.table.search(query_vec)
            .limit(limit)
            .to_pandas()
        )

        return [self._format_result(row) for _, row in results.iterrows()]

    def search_fulltext(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Fulltext-only search (LanceDB falls back to vector search).

        LanceDB doesn't have native full-text search with BM25 ranking.
        This falls back to vector search for semantic similarity.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of SearchResult objects.
        """
        # LanceDB doesn't have native FTS, fall back to vector search
        return self.search_vector(query, limit)

    def _search_hybrid(self, query: str, limit: int) -> list[SearchResult]:
        """Hybrid search: vector search with optional filtering.

        LanceDB doesn't have native FTS, so we prioritize vector search.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of SearchResult objects.
        """
        # For LanceDB, hybrid = vector search (since no native FTS)
        # We could add content filtering if needed
        return self.search_vector(query, limit)

    def _format_result(self, row) -> SearchResult:
        """Format a result row as SearchResult."""
        content = row.get("content", "")

        # Handle metadata (might be JSON string or dict)
        metadata_raw = row.get("metadata", {})
        if isinstance(metadata_raw, str):
            try:
                metadata = json.loads(metadata_raw)
            except:
                metadata = {}
        else:
            metadata = metadata_raw if isinstance(metadata_raw, dict) else {}

        # Get score (LanceDB uses _score)
        score = getattr(row, "_score", 0.0)

        return SearchResult(content=content, metadata=metadata, score=score)

    def update_document(self, document_id: str, content: str, metadata: dict | None = None) -> int:
        """Replace all chunks for a document_id with new content.

        Args:
            document_id: Document identifier to replace.
            content: New document content.
            metadata: Optional metadata to attach (merged with document_id).

        Returns:
            Number of chunks added.
        """
        if not document_id:
            raise ValueError("document_id is required")

        # Delete existing chunks for this document_id
        try:
            self.table.delete(f"document_id = {repr(document_id)}")
        except Exception:
            # Best-effort fallback: continue to add new content
            pass

        meta = {"document_id": document_id}
        if metadata:
            meta.update(metadata)

        return self.add_documents([{"content": content, "metadata": meta}])

    def delete(self, ids: list[str]) -> int:
        """Delete documents by ID.

        Args:
            ids: List of document IDs to delete.

        Returns:
            Number of documents deleted.
        """
        if not ids:
            return 0

        # LanceDB doesn't have a direct delete by IDs in older versions
        # We'll filter and delete
        try:
            self.table.delete(f"id IN ({','.join(repr(id) for id in ids)})")
            return len(ids)
        except Exception:
            # Fallback: delete one by one
            count = 0
            for doc_id in ids:
                try:
                    self.table.delete(f"id = {repr(doc_id)}")
                    count += 1
                except Exception:
                    pass
            return count


# =============================================================================
# Storage Path Management (Thread-based routing)
# =============================================================================

def _get_storage_id() -> str:
    """
    Get the storage ID for VDB operations.

    Priority:
    1. thread_id from context

    Returns:
        The storage identifier.

    Raises:
        ValueError: If no thread_id in context.
    """
    from executive_assistant.storage.thread_storage import get_thread_id
    thread_id = get_thread_id()
    if thread_id:
        return thread_id

    raise ValueError("No thread_id in context")



def get_vdb_storage_dir(storage_id: str | None = None) -> Path:
    """
    Return the VDB directory for a thread.

    Storage layout: data/users/{thread_id}/vdb/

    Args:
        storage_id: Thread identifier (optional, uses context if None).

    Returns:
        Path to the VDB directory.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    if not storage_id:
        raise ValueError("No storage_id provided and none in context")

    path = get_thread_path(storage_id) / "vdb"
    path.mkdir(parents=True, exist_ok=True)
    register_vdb_path_best_effort(storage_id, "unknown", str(path))
    return path



# =============================================================================
# LanceDB Client Management
# =============================================================================

@lru_cache(maxsize=128)
def _get_lancedb_connection(storage_id: str, path: Path):
    """Get a cached LanceDB connection for a storage.

    Args:
        storage_id: Storage identifier.
        path: Path to the VDB directory.

    Returns:
        LanceDB database object.
    """
    import lancedb

    db_path = path / ".lancedb"
    db = lancedb.connect(str(db_path))

    return db


def get_lancedb_connection(storage_id: str | None = None) -> Any:
    """
    Get a LanceDB connection for a thread or thread.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).

    Returns:
        LanceDB database object.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    path = get_vdb_storage_dir(storage_id)
    return _get_lancedb_connection(storage_id, path)


def reset_connection_cache():
    """Reset the connection cache (for testing)."""
    _get_lancedb_connection.cache_clear()


# =============================================================================
# Collection Management
# =============================================================================

def _sanitize_table_name(name: str) -> str:
    """Sanitize a name for use as a collection name."""
    import re
    # Remove special characters, keep only alphanumeric and underscore
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


def create_lancedb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    embedding_dimension: int = 384,
    documents: list[dict[str, Any]] | None = None,
    # Deprecated alias for backward compatibility
    thread_id: str | None = None,
) -> LanceDBCollection:
    """Create a new LanceDB vector collection.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).
        collection_name: Name for the collection.
        embedding_dimension: Vector dimension (default 384 for all-MiniLM-L6-v2).
        documents: Optional initial documents.
        thread_id: Deprecated alias for storage_id.

    Returns:
        LanceDBCollection instance.
    """
    # Backward compatibility: thread_id → storage_id
    if thread_id is not None:
        storage_id = thread_id

    if storage_id is None:
        storage_id = _get_storage_id()

    if collection_name == "":
        collection_name = "default"

    db = get_lancedb_connection(storage_id)

    # Sanitize names
    safe_name = _sanitize_table_name(collection_name)

    # Define schema
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("document_id", pa.string()),
        pa.field("content", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), embedding_dimension)),
    ])

    # Create table
    try:
        table = db.create_table(
            safe_name,
            schema=schema,
            mode="overwrite"
        )
    except Exception as e:
        # Table might already exist
        try:
            table = db.open_table(safe_name)
        except Exception:
            raise ValueError(f"Failed to create or open collection '{collection_name}': {e}")

    path = get_vdb_storage_dir(storage_id)
    collection = LanceDBCollection(
        name=collection_name,
        thread_id=storage_id,
        db=db,
        table=table,
        dimension=embedding_dimension,
        path=path
    )

    # Add initial documents if provided
    if documents:
        collection.add_documents(documents)

    # Create vector index for faster search
    try:
        table.create_index(
            "vector",
            index_type="IVF_PQ",
            num_partitions=256,
            num_sub_vectors=embedding_dimension // 4
        )
    except Exception:
        # Index might already exist or creation failed
        pass

    return collection


def get_lancedb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    # Deprecated alias for backward compatibility
    thread_id: str | None = None,
) -> LanceDBCollection:
    """Get an existing LanceDB collection.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).
        collection_name: Collection name.
        thread_id: Deprecated alias for storage_id.

    Returns:
        LanceDBCollection instance.
    """
    # Backward compatibility: thread_id → storage_id
    if thread_id is not None:
        storage_id = thread_id

    if storage_id is None:
        storage_id = _get_storage_id()

    if collection_name == "":
        collection_name = "default"

    db = get_lancedb_connection(storage_id)

    # Sanitize name
    safe_name = _sanitize_table_name(collection_name)

    try:
        table = db.open_table(safe_name)
    except Exception:
        raise ValueError(f"Collection '{collection_name}' not found")

    return LanceDBCollection(
        name=collection_name,
        thread_id=storage_id,
        db=db,
        table=table,
        path=get_vdb_storage_dir(storage_id)
    )


def list_lancedb_collections(
    storage_id: str | None = None,
    # Deprecated alias for backward compatibility
    thread_id: str | None = None,
) -> list[str]:
    """List all collection names for a thread or thread.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).
        thread_id: Deprecated alias for storage_id.

    Returns:
        List of collection names.
    """
    # Backward compatibility: thread_id → storage_id
    if thread_id is not None:
        storage_id = thread_id

    if storage_id is None:
        storage_id = _get_storage_id()

    db = get_lancedb_connection(storage_id)

    tables: list[str] = []
    try:
        result = db.list_tables()
        if hasattr(result, "tables"):
            candidates = result.tables
        else:
            candidates = result

        for item in candidates:
            if isinstance(item, str):
                tables.append(item)
            elif hasattr(item, "name"):
                tables.append(getattr(item, "name"))
            elif isinstance(item, tuple) and item:
                tables.append(item[0])
    except Exception:
        tables = []

    if tables:
        return tables

    # Fallback to on-disk scan when list_tables returns nothing
    try:
        vdb_dir = get_vdb_storage_dir(storage_id)
        lancedb_dir = vdb_dir / ".lancedb"
        if not lancedb_dir.exists():
            return []
        names = []
        for entry in lancedb_dir.iterdir():
            if entry.is_dir() and entry.name.endswith(".lance"):
                names.append(entry.name[:-6])
        return sorted(names)
    except Exception:
        return []


def drop_lancedb_collection(
    storage_id: str | None = None,
    collection_name: str = "",
    # Deprecated alias for backward compatibility
    thread_id: str | None = None,
) -> bool:
    """Drop a LanceDB collection.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).
        collection_name: Collection name.
        thread_id: Deprecated alias for storage_id.

    Returns:
        True if dropped, False if not found.
    """
    # Backward compatibility: thread_id → storage_id
    if thread_id is not None:
        storage_id = thread_id

    if storage_id is None:
        storage_id = _get_storage_id()

    if collection_name == "":
        collection_name = "default"

    db = get_lancedb_connection(storage_id)

    # Sanitize name
    safe_name = _sanitize_table_name(collection_name)

    try:
        db.drop_table(safe_name)
        return True
    except Exception:
        return False


def drop_all_lancedb_collections(storage_id: str | None = None) -> int:
    """Drop all collections for a thread or thread.

    Args:
        storage_id: Thread or thread identifier (optional, uses context if None).

    Returns:
        Number of collections dropped.
    """
    if storage_id is None:
        storage_id = _get_storage_id()

    collections = list_lancedb_collections(storage_id)
    count = 0

    for name in collections:
        if drop_lancedb_collection(storage_id, name):
            count += 1

    return count
