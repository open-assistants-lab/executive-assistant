"""Vector Store tools using LanceDB for high-performance vector search."""

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
from cassey.storage.lancedb_storage import (
    create_lancedb_collection,
    drop_lancedb_collection,
    get_lancedb_collection,
    list_lancedb_collections,
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
def create_vs_collection(collection_name: str, content: str = "", documents: str = "") -> str:
    """
    Create a VS collection for semantic search.

    USE THIS WHEN:
    - You want to store documents for semantic search (find by meaning, not exact words)
    - User asks to "save this for later" and wants to search by topic/concept
    - User wants to build a knowledge base for semantic queries

    NOT for:
    - Saving regular files → use write_file instead
    - Searching file contents by exact text → use grep_files instead
    - Browsing file structure → use list_files instead

    A collection groups related documents for semantic vector search.
    Documents are automatically chunked if they're too large.

    **Two ways to add documents:**

    1. **Single document (recommended for simple use):**
       create_vs_collection("notes", content="Meeting notes from today")

    2. **Multiple documents (bulk import):**
       create_vs_collection("notes", documents='[{"content": "..."}]')

    3. **Empty collection first:** Create structure, then add documents with add_vs_documents
       create_vs_collection("notes")
       add_vs_documents("notes", content="Document 1")

    Args:
        collection_name: Collection name (letters/numbers/underscore/hyphen).
        content: Single document text (leave empty to use documents parameter or create empty).
        documents: JSON array for bulk import: [{"content": "...", "metadata": {...}}]
                    Leave empty to use content parameter or create empty collection.

    Returns:
        Success message with collection info.

    Examples:
        create_vs_collection("notes", content="Today we discussed Q1 goals")
        → "Created VS collection 'notes' with 2 chunks from 1 document(s)"

        create_vs_collection("docs", documents='[{"content": "Doc 1"}, {"content": "Doc 2"}]')
        → "Created VS collection 'docs' with 4 chunks from 2 document(s)"
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
    elif documents and documents.strip():
        # Parse documents JSON
        parsed = _parse_documents(documents)
        if isinstance(parsed, str):
            return parsed
    else:
        # Create empty collection
        parsed = []

    try:
        storage_id = _get_storage_id()

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
    Search VS collections for semantically similar documents (search by meaning, not exact words).

    USE THIS WHEN:
    - User wants to find documents by topic, concept, or meaning
    - User asks "what do we know about X" or "find information about Y"
    - You need to search stored documents by semantic similarity

    NOT for:
    - Searching file contents by exact text match → use grep_files instead
    - Finding files by name/pattern → use glob_files instead
    - Browsing directory structure → use list_files instead

    Vector search finds documents that are semantically similar to your query.
    For best results, use natural language queries describing what you're looking for.

    Examples:
        search_vs("meeting goals", "notes")
        → Finds documents about meetings, objectives, targets, even if those exact words aren't used

        search_vs("database performance")
        → Finds documents about databases, optimization, speed, queries, etc.

    Args:
        query: Search query text (use natural language, describe what you're looking for).
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
            collections = list_lancedb_collections(storage_id=storage_id)
            if collection_name not in collections:
                return f"Error: VS collection '{collection_name}' not found"
            collections = [collection_name]
        else:
            collections = list_lancedb_collections(storage_id=storage_id)

        if not collections:
            return "No VS collections found. Use create_vs_collection to create one first."

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
        collections = list_lancedb_collections(storage_id=storage_id)

        if not collections:
            return "Vector Store is empty. Use create_vs_collection to create a collection."

        lines = ["Vector Store collections:"]
        total_docs = 0

        for name in collections:
            try:
                collection = get_lancedb_collection(storage_id, name)
                count = collection.count()
                total_docs += count
                lines.append(f"- {name}: {count} chunks (LanceDB)")
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

        collection = get_lancedb_collection(storage_id, collection_name)
        count = collection.count()

        drop_lancedb_collection(storage_id, collection_name)
        record_vs_table_removed(storage_id, collection_name)

        return f"Deleted VS collection '{collection_name}' ({count} chunks removed)"

    except Exception as exc:
        return f"Error dropping collection: {exc}"


@tool
def add_vs_documents(collection_name: str, content: str = "", documents: str = "") -> str:
    """
    Add documents to an existing VS collection.

    **Two ways to add documents:**

    1. **Single document (recommended for simple use):**
       add_vs_documents("notes", content="Additional meeting notes")

    2. **Multiple documents (bulk import):**
       add_vs_documents("notes", documents='[{"content": "Doc 1"}, {"content": "Doc 2"}]')

    Documents are automatically chunked if too large.

    Args:
        collection_name: Name of the collection to add to.
        content: Single document text (leave empty to use documents parameter).
        documents: JSON array for bulk import: [{"content": "...", "metadata": {...}}]

    Returns:
        Confirmation message with chunk count.

    Examples:
        add_vs_documents("notes", content="Follow-up from yesterday")
        → "Added 1 chunks to VS collection 'notes' from 1 document(s)"

        add_vs_documents("docs", documents='[{"content": "New doc"}]')
        → "Added 2 chunks to VS collection 'docs' from 1 document(s)"
    """
    validate_identifier(collection_name)

    # Handle content parameter (single document)
    if content and content.strip():
        # Convert single content to document format
        parsed = [{"content": content, "metadata": {}}]
    elif documents and documents.strip():
        # Parse documents JSON
        parsed = _parse_documents(documents)
        if isinstance(parsed, str):
            return parsed
    else:
        return "Error: Either content or documents must be provided"

    try:
        storage_id = _get_storage_id()
        collection = get_lancedb_collection(storage_id, collection_name)

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
        collection = get_lancedb_collection(storage_id, collection_name)

        deleted = collection.delete(id_list)
        record_vs_table_added(storage_id, collection_name)

        return f"Deleted {deleted} chunk(s) from VS collection '{collection_name}'"

    except Exception as exc:
        return f"Error deleting documents: {exc}"


@tool
def add_file_to_vs(collection_name: str, file_path: str) -> str:
    """
    Add/insert a file from the files directory to a VS collection.

    Use this tool when the user wants to:
    - Insert/add a file to VS
    - Save a file for semantic search
    - Index file contents in a collection

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
        collections = list_lancedb_collections(storage_id=storage_id)
        if collection_name not in collections:
            collection = create_lancedb_collection(
                storage_id=storage_id,
                collection_name=collection_name,
                embedding_dimension=384,
            )
            record_vs_table_added(storage_id, collection_name)

        # Add document with filename metadata
        collection = get_lancedb_collection(storage_id, collection_name)
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
