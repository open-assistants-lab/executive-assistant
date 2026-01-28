"""Vector Database tools using LanceDB for high-performance vector search."""

from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from langchain_core.tools import tool

from executive_assistant.config import settings
from executive_assistant.storage.db_storage import validate_identifier
from executive_assistant.storage.file_sandbox import SecurityError
from executive_assistant.storage.thread_storage import get_thread_id
from executive_assistant.storage.meta_registry import (
    record_vdb_table_added,
    record_vdb_table_removed,
)
from executive_assistant.storage.lancedb_storage import (
    create_lancedb_collection,
    drop_lancedb_collection,
    get_lancedb_collection,
    list_lancedb_collections,
)


def _get_storage_id() -> str:
    """
    Get the storage ID for VDB operations.

    Priority:
    1. thread_id from context

    Returns:
        The storage identifier.

    Raises:
        ValueError: If no thread_id context is available.
    """
    # 1. thread_id from context
    thread_id = get_thread_id()
    if thread_id:
        return thread_id
    raise ValueError("No thread_id in context")


def _get_storage_id_with_scope(scope: Literal["context", "shared"] = "context") -> str:
    """
    Get storage ID based on scope.

    Args:
        scope: "context" (default) uses thread_id/thread_id from context,
               "shared" uses organization-wide shared storage.

    Returns:
        Storage identifier for the requested scope.

    Raises:
        ValueError: If scope is invalid or no context available for context-scoped operations.
    """
    if scope == "shared":
        return "shared"  # Fixed ID for shared storage
    elif scope == "context":
        return _get_storage_id()  # Uses thread_id/thread_id from context
    else:
        raise ValueError(f"Invalid scope: {scope}. Must be 'context' or 'shared'.")


def _record_vdb_collection_added(collection_name: str) -> None:
    thread_id = get_thread_id()
    if not thread_id:
        return
    record_vdb_table_added(thread_id, collection_name)


def _record_vdb_collection_removed(collection_name: str) -> None:
    thread_id = get_thread_id()
    if not thread_id:
        return
    record_vdb_table_removed(thread_id, collection_name)


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


def _parse_documents(documents: str | list[dict]) -> list[dict] | str:
    """Parse documents from JSON string or list.

    Returns:
        List of document dicts or error message string.
    """
    if not documents:
        return []
    
    # If already a list, return as-is
    if isinstance(documents, list):
        return documents

    # Parse JSON string
    try:
        parsed = json.loads(documents)
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON data - {exc}"

    if not isinstance(parsed, list):
        return "Error: documents must be a JSON array"

    if not parsed:
        return "Error: documents array is empty"

    return parsed


# =============================================================================
# VDB Tools
# =============================================================================

@tool
def create_vdb_collection(
    collection_name: str,
    content: str = "",
    documents: str | list[dict] = "",
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Create a VDB collection and optionally add documents.

    Examples:
        create_vdb_collection("meetings")  # Empty collection
        create_vdb_collection("meetings", content="Meeting notes about Q1 goals")
        create_vdb_collection("docs", documents=[{"content": "Doc 1"}])
        create_vdb_collection("docs", documents='[{"content": "Doc 1"}]')

    Args:
        collection_name: Name for the collection.
        content: Single document text (plain string, optional).
        documents: List of dicts OR JSON string (e.g., [{"content": "text", "metadata": {}}]).
        scope: "context" (default) or "shared".
    """
    # Validate collection name
    try:
        validate_identifier(collection_name)
    except Exception as e:
        return f"Error: Invalid collection name - {e}"

    # Handle content parameter (single document)
    if content and content.strip():
        # Convert single content to document format
        parsed = [{"content": content, "metadata": {}}]
    elif documents:
        # Handle documents - can be list or JSON string
        if isinstance(documents, list):
            parsed = documents
        elif isinstance(documents, str) and documents.strip():
            parsed = _parse_documents(documents)
            if isinstance(parsed, str):
                return parsed
        else:
            parsed = []
    else:
        # Create empty collection
        parsed = []

    try:
        storage_id = _get_storage_id_with_scope(scope)

        # Check if collection already exists
        existing = list_lancedb_collections(storage_id=storage_id)
        if collection_name in existing:
            drop_lancedb_collection(storage_id, collection_name)

        # Create collection
        collection = create_lancedb_collection(
            storage_id=storage_id,
            collection_name=collection_name,
            embedding_dimension=384,
            documents=parsed if parsed else None
        )

        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_added(collection_name)

        if parsed:
            chunk_count = collection.count()
            return f"Created VDB collection '{collection_name}' with {chunk_count} chunks from {len(parsed)} document(s)"
        return f"Created VDB collection '{collection_name}' (empty, ready for documents)"

    except Exception as exc:
        return f"Error creating collection: {exc}"


@tool
def search_vdb(
    query: str,
    collection_name: str = "",
    limit: int = 5,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Semantic search across VDB collections."""
    if not query or not query.strip():
        return "Error: Search query cannot be empty"

    try:
        storage_id = _get_storage_id_with_scope(scope)

        # Determine which collections to search
        if collection_name:
            validate_identifier(collection_name)
            collections = list_lancedb_collections(storage_id=storage_id)
            if collection_name not in collections:
                return f"Error: VDB collection '{collection_name}' not found"
            collections = [collection_name]
        else:
            collections = list_lancedb_collections(storage_id=storage_id)

        if not collections:
            return "No VDB collections found. Use create_vdb_collection to create one first."

        results: list[str] = []

        for coll_name in collections:
            try:
                collection = get_lancedb_collection(storage_id, coll_name)

                # Use vector search
                search_results = collection.search(query=query, limit=limit, search_type="vector")

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
            return f"No matches found across all VDB collections for query: {query}"

        return f"Search results for '{query}':\n\n" + "\n".join(results)

    except Exception as exc:
        return f"Error searching VDB: {exc}"


@tool
def vdb_list(scope: Literal["context", "shared"] = "context") -> str:
    """List VDB collections and chunk counts."""
    try:
        storage_id = _get_storage_id_with_scope(scope)
        collections = list_lancedb_collections(storage_id=storage_id)

        if not collections:
            return "Vector Database is empty. Use create_vdb_collection to create a collection."

        lines = ["Vector Database collections:"]
        total_docs = 0

        for name in collections:
            try:
                collection = get_lancedb_collection(storage_id, name)
                count = collection.count()
                total_docs += count
                lines.append(f"- {name}: {count} chunks")
            except Exception:
                lines.append(f"- {name}: (error)")

        lines.append(f"\nTotal: {len(collections)} collection(s), {total_docs} chunk(s)")

        return "\n".join(lines)

    except Exception as exc:
        return f"Error listing VDB collections: {exc}"


@tool
def describe_vdb_collection(collection_name: str, scope: Literal["context", "shared"] = "context") -> str:
    """Describe a VDB collection with sample documents."""
    try:
        storage_id = _get_storage_id_with_scope(scope)
        validate_identifier(collection_name)

        collection = get_lancedb_collection(storage_id, collection_name)
        count = collection.count()

        lines = [f"Collection '{collection_name}':"]
        lines.append(f"Total chunks: {count}")
        lines.append(f"Vector dimension: {collection.dimension}")
        lines.append(f"Search type: Vector similarity")

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
def drop_vdb_collection(collection_name: str, scope: Literal["context", "shared"] = "context") -> str:
    """Delete a VDB collection and all its documents."""
    try:
        storage_id = _get_storage_id_with_scope(scope)
        validate_identifier(collection_name)

        collection = get_lancedb_collection(storage_id, collection_name)
        count = collection.count()

        drop_lancedb_collection(storage_id, collection_name)
        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_removed(collection_name)

        return f"Deleted VDB collection '{collection_name}' ({count} chunks removed)"

    except Exception as exc:
        return f"Error dropping collection: {exc}"


@tool
def add_vdb_documents(
    collection_name: str,
    content: str = "",
    documents: str | list[dict] = "",
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Add documents to a VDB collection.

    Examples:
        add_vdb_documents("meetings", content="New meeting notes")
        add_vdb_documents("docs", documents=[{"content": "Doc 1"}])
        add_vdb_documents("docs", documents='[{"content": "Doc 1"}]')

    Args:
        collection_name: Name of the collection.
        content: Single document text (plain string, optional).
        documents: List of dicts OR JSON string (e.g., [{"content": "text"}]).
        scope: "context" (default) or "shared".
    """
    validate_identifier(collection_name)

    # Handle content parameter (single document)
    if content and content.strip():
        # Convert single content to document format
        parsed = [{"content": content, "metadata": {}}]
    elif documents:
        # Handle documents - can be list or JSON string
        if isinstance(documents, list):
            parsed = documents
        elif isinstance(documents, str) and documents.strip():
            parsed = _parse_documents(documents)
            if isinstance(parsed, str):
                return parsed
        else:
            return "Error: Either content or documents must be provided"
    else:
        return "Error: Either content or documents must be provided"

    try:
        storage_id = _get_storage_id_with_scope(scope)
        collection = get_lancedb_collection(storage_id, collection_name)

        added = collection.add_documents(parsed)
        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_added(collection_name)

        return f"Added {added} chunks to VDB collection '{collection_name}' from {len(parsed)} document(s)"

    except Exception as exc:
        return f"Error adding documents: {exc}"


@tool
def delete_vdb_documents(
    collection_name: str,
    ids: str,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Delete chunks by ID from a collection."""
    validate_identifier(collection_name)

    id_list = [item.strip() for item in ids.split(",") if item.strip()]
    if not id_list:
        return "Error: No valid IDs provided"

    try:
        storage_id = _get_storage_id_with_scope(scope)
        collection = get_lancedb_collection(storage_id, collection_name)

        deleted = collection.delete(id_list)
        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_added(collection_name)

        return f"Deleted {deleted} chunk(s) from VDB collection '{collection_name}'"

    except Exception as exc:
        return f"Error deleting documents: {exc}"


@tool
def update_vdb_document(
    collection_name: str,
    document_id: str,
    content: str,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Update a document in a VDB collection by document_id."""
    try:
        validate_identifier(collection_name)
        if not document_id or not document_id.strip():
            return "Error: document_id is required"
        if not content or not content.strip():
            return "Error: content is required"

        storage_id = _get_storage_id_with_scope(scope)
        collection = get_lancedb_collection(storage_id, collection_name)
        added = collection.update_document(document_id=document_id, content=content)

        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_added(collection_name)

        return f"Updated document '{document_id}' in VDB collection '{collection_name}' ({added} chunks)"
    except Exception as exc:
        return f"Error updating VDB document: {exc}"


@tool
def add_file_to_vdb(
    collection_name: str,
    file_path: str,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Index a file into a VDB collection."""
    from executive_assistant.storage.file_sandbox import _get_sandbox_with_scope

    validate_identifier(collection_name)

    try:
        storage_id = _get_storage_id_with_scope(scope)

        # Get the file sandbox based on scope
        sandbox = _get_sandbox_with_scope(scope)

        # Validate and read the file
        try:
            validated_path = sandbox._validate_path(file_path)
            content = validated_path.read_text(encoding="utf-8")
        except SecurityError as e:
            return f"Security error: {e}"
        except FileNotFoundError:
            return f"File not found: {file_path}. Use /file to see available files."

        # Check if collection exists, create if not
        collections = list_lancedb_collections(storage_id=storage_id)
        if collection_name not in collections:
            collection = create_lancedb_collection(
                storage_id=storage_id,
                collection_name=collection_name,
                embedding_dimension=384,
            )
            # Only record metadata for context-scoped VDB
            if scope == "context":
                _record_vdb_collection_added(collection_name)

        # Add document with filename metadata
        collection = get_lancedb_collection(storage_id, collection_name)
        documents = [{"content": content, "metadata": {"filename": file_path}}]
        added = collection.add_documents(documents)
        # Only record metadata for context-scoped VDB
        if scope == "context":
            _record_vdb_collection_added(collection_name)

        return f"Added {added} chunks to VDB collection '{collection_name}' from file '{file_path}'"

    except Exception as exc:
        return f"Error adding file to VDB: {exc}"


async def get_vdb_tools() -> list:
    """Get all Vector Database tools for use in the agent."""
    return [
        create_vdb_collection,
        search_vdb,
        vdb_list,
        describe_vdb_collection,
        drop_vdb_collection,
        add_vdb_documents,
        update_vdb_document,
        delete_vdb_documents,
        add_file_to_vdb,
    ]
