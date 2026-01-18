"""Vector Store tools using DuckDB + Hybrid (FTS + VSS)."""

from __future__ import annotations

import json
from uuid import uuid4

from langchain_core.tools import tool

from cassey.config import settings
from cassey.storage.db_storage import validate_identifier
from cassey.storage.file_sandbox import SecurityError, get_thread_id
from cassey.storage.meta_registry import (
    record_vs_table_added,
    record_vs_table_removed,
)
from cassey.storage.duckdb_storage import (
    create_duckdb_collection,
    drop_duckdb_collection,
    get_duckdb_collection,
    list_duckdb_collections,
)


def _get_storage_id() -> str:
    """
    Get the storage ID for VS operations.

    Uses thread_id for thread-scoped storage (consistent with /mem, /db, /file).

    Returns:
        The storage identifier.

    Raises:
        ValueError: If no thread_id in context.
    """
    thread_id = get_thread_id()
    if thread_id:
        return thread_id

    raise ValueError("No thread_id in context")


def _format_doc_line(doc_id: str, content: str, metadata: dict | None, score: float | None) -> str:
    """Format a document result line."""
    meta_str = ""
    if metadata:
        # Show key metadata fields
        important_keys = ["filename", "page", "chunk_index", "document_id"]
        relevant = {k: v for k, v in metadata.items() if k in important_keys}
        if relevant:
            meta_str = f" [metadata: {relevant}]"

    score_str = f"[{score:.2f}] " if score is not None and score >= 0 else ""
    return f"{score_str}(id: {doc_id}) {content[:200]}{'...' if len(content) > 200 else ''}{meta_str}"


def _parse_documents(documents_str: str) -> list[dict] | str:
    """Parse documents JSON string.

    Returns:
        List of document dicts or error message string.
    """
    if not documents_str:
        return []

    try:
        parsed = json.loads(documents_str)
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON data - {exc}"

    if not isinstance(parsed, list):
        return "Error: documents must be a JSON array"

    if not parsed:
        return "Error: documents array is empty"

    return parsed


# =============================================================================
# VS Tools
# =============================================================================

@tool
def create_vs_collection(collection_name: str, documents: str = "") -> str:
    """
    Create a VS collection in DuckDB.

    A collection groups related documents for semantic + fulltext search.
    Documents are automatically chunked if they're too large.

    Args:
        collection_name: Collection name (letters/numbers/underscore/hyphen).
        documents: JSON array of document objects: [{"content": "...", "metadata": {...}}]

    Returns:
        Success message with collection info.
    """
    # Validate collection name
    try:
        validate_identifier(collection_name)
    except Exception as e:
        return f"Error: Invalid collection name - {e}"

    # Parse documents
    parsed = _parse_documents(documents)
    if isinstance(parsed, str):
        return parsed

    try:
        storage_id = _get_storage_id()

        # Check if collection already exists
        existing = list_duckdb_collections(storage_id=storage_id)
        if collection_name in existing:
            drop_duckdb_collection(storage_id, collection_name)

        # Create collection
        collection = create_duckdb_collection(
            storage_id=storage_id,
            collection_name=collection_name,
            embedding_dimension=384,
            documents=parsed if parsed else None
        )

        record_vs_table_added(storage_id, collection_name)

        if parsed:
            chunk_count = collection.count()
            return f"Created VS collection '{collection_name}' with {chunk_count} chunks from {len(parsed)} document(s)"
        return f"Created VS collection '{collection_name}' (empty, ready for documents)"

    except Exception as exc:
        return f"Error creating collection: {exc}"


@tool
def search_vs(query: str, collection_name: str = "", limit: int = 5) -> str:
    """
    Search VS collections with hybrid search (semantic + fulltext).

    Hybrid search finds documents that:
    - Contain your search terms (fulltext match)
    - Are semantically similar (vector similarity)

    Args:
        query: Search query text.
        collection_name: Specific collection to search, or empty for all collections.
        limit: Maximum results per collection (default: 5).

    Returns:
        Search results with relevance scores.
    """
    if not query or not query.strip():
        return "Error: Search query cannot be empty"

    try:
        storage_id = _get_storage_id()

        # Determine which collections to search
        if collection_name:
            validate_identifier(collection_name)
            collections = list_duckdb_collections(storage_id=storage_id)
            if collection_name not in collections:
                return f"Error: VS collection '{collection_name}' not found"
            collections = [collection_name]
        else:
            collections = list_duckdb_collections(storage_id=storage_id)

        if not collections:
            return "No VS collections found. Use create_vs_collection to create one first."

        results: list[str] = []

        for coll_name in collections:
            try:
                collection = get_duckdb_collection(storage_id, coll_name)

                # Use hybrid search
                search_results = collection.search(query=query, limit=limit, search_type="hybrid")

                if search_results:
                    header = f"--- From '{coll_name}' ---"
                    results.append(header)

                    for result in search_results:
                        doc_id = result.metadata.get("id", result.metadata.get("chunk_id", "unknown"))
                        results.append(_format_doc_line(doc_id, result.content, result.metadata, result.score))

            except Exception as e:
                # Continue to next collection on error
                continue

        if not results:
            if collection_name:
                return f"No matches found in '{collection_name}' for query: {query}"
            return f"No matches found across all VS collections for query: {query}"

        return f"Search results for '{query}':\n\n" + "\n".join(results)

    except Exception as exc:
        return f"Error searching VS: {exc}"


@tool
def vs_list() -> str:
    """
    List all VS collections with document counts.

    Returns:
        List of all collections and their document counts.
    """
    try:
        storage_id = _get_storage_id()
        collections = list_duckdb_collections(storage_id=storage_id)

        if not collections:
            return "Vector Store is empty. Use create_vs_collection to create a collection."

        lines = ["Vector Store collections:"]
        total_docs = 0

        for name in collections:
            try:
                collection = get_duckdb_collection(storage_id, name)
                count = collection.count()
                total_docs += count
                lines.append(f"- {name}: {count} chunks (DuckDB + Hybrid)")
            except Exception:
                lines.append(f"- {name}: (error)")

        lines.append(f"\nTotal: {len(collections)} collection(s), {total_docs} chunk(s)")

        return "\n".join(lines)

    except Exception as exc:
        return f"Error listing VS collections: {exc}"


@tool
def describe_vs_collection(collection_name: str) -> str:
    """
    Describe a VS collection and preview sample documents.

    Args:
        collection_name: Name of the collection to describe.

    Returns:
        Collection details and sample documents.
    """
    try:
        storage_id = _get_storage_id()
        validate_identifier(collection_name)

        collection = get_duckdb_collection(storage_id, collection_name)
        count = collection.count()

        lines = [f"Collection '{collection_name}':"]
        lines.append(f"Total chunks: {count}")
        lines.append(f"Vector dimension: {collection.dimension}")
        lines.append(f"Search type: Hybrid (FTS + VSS)")

        # Show sample documents
        docs = collection.documents
        if docs:
            lines.append("\nSample documents (up to 3):")
            for i, (doc_id, content) in enumerate(list(docs.items())[:3], 1):
                preview = content[:150].replace("\n", " ")
                lines.append(f"  [{i}] (id: {doc_id}) {preview}...")
        else:
            lines.append("\nCollection is empty.")

        return "\n".join(lines)

    except Exception as exc:
        return f"Error describing collection: {exc}"


@tool
def drop_vs_collection(collection_name: str) -> str:
    """
    Drop a VS collection and all its documents.

    Args:
        collection_name: Name of the collection to drop.

    Returns:
        Confirmation message.
    """
    try:
        storage_id = _get_storage_id()
        validate_identifier(collection_name)

        collection = get_duckdb_collection(storage_id, collection_name)
        count = collection.count()

        drop_duckdb_collection(storage_id, collection_name)
        record_vs_table_removed(storage_id, collection_name)

        return f"Deleted VS collection '{collection_name}' ({count} chunks removed)"

    except Exception as exc:
        return f"Error dropping collection: {exc}"


@tool
def add_vs_documents(collection_name: str, documents: str) -> str:
    """
    Add documents to an existing VS collection.

    Documents are automatically chunked if too large.

    Args:
        collection_name: Name of the collection to add to.
        documents: JSON array of document objects: [{"content": "...", "metadata": {...}}]

    Returns:
        Confirmation message with chunk count.
    """
    validate_identifier(collection_name)

    parsed = _parse_documents(documents)
    if isinstance(parsed, str):
        return parsed

    try:
        storage_id = _get_storage_id()
        collection = get_duckdb_collection(storage_id, collection_name)

        added = collection.add_documents(parsed)
        record_vs_table_added(storage_id, collection_name)

        return f"Added {added} chunks to VS collection '{collection_name}' from {len(parsed)} document(s)"

    except Exception as exc:
        return f"Error adding documents: {exc}"


@tool
def delete_vs_documents(collection_name: str, ids: str) -> str:
    """
    Delete chunks by ID from a collection.

    Note: This deletes individual chunks, not whole documents.
    To delete a whole document, use the document_id metadata.

    Args:
        collection_name: Name of the collection.
        ids: Comma-separated list of chunk IDs to delete.

    Returns:
        Confirmation message.
    """
    validate_identifier(collection_name)

    id_list = [item.strip() for item in ids.split(",") if item.strip()]
    if not id_list:
        return "Error: No valid IDs provided"

    try:
        storage_id = _get_storage_id()
        collection = get_duckdb_collection(storage_id, collection_name)

        deleted = collection.delete(id_list)
        record_vs_table_added(storage_id, collection_name)

        return f"Deleted {deleted} chunk(s) from VS collection '{collection_name}'"

    except Exception as exc:
        return f"Error deleting documents: {exc}"


@tool
def add_file_to_vs(collection_name: str, file_path: str) -> str:
    """
    Add a file from the files directory to a VS collection.

    This reads a file and automatically chunks and indexes it for semantic search.

    Args:
        collection_name: Name of the VS collection to add to.
        file_path: Path to the file relative to files directory.

    Returns:
        Confirmation message with chunk count.

    Examples:
        >>> add_file_to_vs("notes", "config.txt")
        "Added 3 chunks to VS collection 'notes' from config.txt"
    """
    from cassey.storage.file_sandbox import get_sandbox

    validate_identifier(collection_name)

    try:
        storage_id = _get_storage_id()

        # Get the file sandbox for this thread/group
        sandbox = get_sandbox()

        # Validate and read the file
        try:
            validated_path = sandbox._validate_path(file_path)
            content = validated_path.read_text(encoding="utf-8")
        except SecurityError as e:
            return f"Security error: {e}"
        except FileNotFoundError:
            return f"File not found: {file_path}. Use /file to see available files."

        # Check if collection exists, create if not
        collections = list_duckdb_collections(storage_id=storage_id)
        if collection_name not in collections:
            collection = create_duckdb_collection(
                storage_id=storage_id,
                collection_name=collection_name,
                embedding_dimension=384,
            )
            record_vs_table_added(storage_id, collection_name)

        # Add document with filename metadata
        collection = get_duckdb_collection(storage_id, collection_name)
        documents = [{"content": content, "metadata": {"filename": file_path}}]
        added = collection.add_documents(documents)
        record_vs_table_added(storage_id, collection_name)

        return f"Added {added} chunks to VS collection '{collection_name}' from file '{file_path}'"

    except Exception as exc:
        return f"Error adding file to VS: {exc}"


async def get_vs_tools() -> list:
    """Get all Vector Store tools for use in the agent."""
    return [
        create_vs_collection,
        search_vs,
        vs_list,
        describe_vs_collection,
        drop_vs_collection,
        add_vs_documents,
        delete_vs_documents,
        add_file_to_vs,
    ]
