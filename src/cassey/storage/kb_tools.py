"""Knowledge Base tools using DuckDB Full-Text Search (FTS).

KB tables are per-thread (isolated per conversation) and stored under KB_ROOT.
They differ from workspace DB tables in that KB is designed for persistent
reference data that you want to keep across sessions, while workspace DB is for
temporary working data.

DuckDB FTS Extension Reference:
- INSTALL/LOAD: Auto-loaded on first use
- create_fts_index: Creates BM25 index on text columns
- match_bm25: Search function returning relevance scores
- Schema created: fts_{table_name} with match_bm25(input_id, query, ...) macro

Documentation: https://duckdb.org/docs/stable/core_extensions/full_text_search
"""

from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from cassey.config import settings
from cassey.storage.kb_storage import get_kb_storage
from cassey.storage.db_storage import validate_identifier
from cassey.storage.file_sandbox import get_thread_id
from cassey.storage.user_registry import sanitize_thread_id

_kb_storage = get_kb_storage()


def _get_current_thread_id() -> str:
    """Get the current thread_id from context.

    Raises:
        ValueError: If thread_id is not available (called outside channel context).
    """
    thread_id = get_thread_id()
    if thread_id is None:
        raise ValueError(
            "No thread_id in context. KB tools must be called from within a channel message handler. "
            "If you're calling this tool directly, make sure to set thread_id context first using "
            "set_thread_id() from cassey.storage.file_sandbox."
        )
    return thread_id


def _ensure_fts_installed(conn) -> None:
    """Ensure FTS extension is installed and loaded."""
    try:
        conn.execute("INSTALL fts")
        conn.execute("LOAD fts")
    except Exception:
        pass  # May already be installed


@tool
def create_kb_table(
    table_name: str,
    documents: str = "",
) -> str:
    """
    Create a Knowledge Base table for document storage with full-text search (BM25) indexing.

    The KB is per-thread (isolated to your conversation) and persists across sessions.
    Creates a BM25 FTS index for fast, relevance-ranked search.

    Use this to:
    - Create an empty table first, then add documents in batches
    - Or create with initial documents in one call

    DuckDB FTS automatically:
    - Stems words (e.g., "running" → "run")
    - Removes accents
    - Converts to lowercase
    - Filters English stopwords

    Args:
        table_name: Name for the KB table (creates or replaces existing table).
                    Use descriptive names like 'notes', 'docs', 'product_manual'.
                    Must be a valid SQL identifier (letters, numbers, underscores only).
        documents: Optional JSON array of document objects.
                   Each document has 'content' (required) and optional 'metadata'.
                   Example: '[{"content": "text here", "metadata": "optional tag"}]'
                   If empty, creates an empty table.

    Returns:
        Success message with table name and document count.

    Examples:
        >>> create_kb_table("notes")
        "Created KB table 'notes' (empty, ready for documents)"

        >>> create_kb_table("notes", '[{"content": "Meeting notes: Q1 revenue was $1M", "metadata": "finance"}]')
        "Created KB table 'notes' with 1 documents"

        >>> create_kb_table("docs", '[{"content": "The quick brown fox"}, {"content": "Lorem ipsum"}]')
        "Created KB table 'docs' with 2 documents"
    """
    import json

    # Validate table name
    validate_identifier(table_name)

    # Parse documents if provided
    parsed_docs = []
    if documents:
        try:
            parsed_docs = json.loads(documents)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON data - {str(e)}"

        if not isinstance(parsed_docs, list):
            return "Error: documents must be a JSON array"

    try:
        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            # Drop existing table and FTS index if exists
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            try:
                conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            except Exception:
                pass  # Index may not exist

            # Create main table
            conn.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert documents if provided
            if parsed_docs:
                for i, doc in enumerate(parsed_docs):
                    content = doc.get("content", "")
                    metadata = doc.get("metadata", "")
                    conn.execute(
                        f"INSERT INTO {table_name} (id, content, metadata) VALUES (?, ?, ?)",
                        [i, content, metadata]
                    )

            # Create FTS index on content and metadata
            # Syntax: PRAGMA create_fts_index(table, id_column, text_columns...)
            conn.execute(f"PRAGMA create_fts_index('{table_name}', 'id', 'content', 'metadata')")

            if parsed_docs:
                return f"Created KB table '{table_name}' with {len(parsed_docs)} documents (BM25 FTS indexed)"
            else:
                return f"Created KB table '{table_name}' (empty, ready for documents)"

        finally:
            conn.close()

    except Exception as e:
        return f"Error creating table: {str(e)}"


@tool
def search_kb(
    query: str,
    table_name: str = "",
    limit: int = 5,
) -> str:
    """
    Search the Knowledge Base using BM25 full-text search with relevance ranking.

    Returns documents ranked by relevance (lower score = more relevant).
    Uses DuckDB's FTS extension with stemming, stopwords, and accent removal.

    Search features:
    - BM25 ranking (relevance score)
    - Stemming (e.g., "running" matches "run")
    - Case-insensitive
    - Stopwords filtered automatically
    - Fuzzy matching fallback (via RapidFuzz) when BM25 finds no results

    Args:
        query: Search query - natural language terms work best.
               Examples: "revenue Q1", "meeting notes", "deadline project"
        table_name: KB table to search (optional). If empty, searches all tables.
        limit: Maximum number of results to return (default: 5).

    Returns:
        Search results with relevance scores and document content.

    Examples:
        >>> search_kb("revenue Q1", "notes")
        "Searching KB table 'notes' for 'revenue Q1'\\n\\n--- Results from 'notes' ---\\n[0.5] Meeting notes: Q1 revenue was $1M [finance]"

        >>> search_kb("deadline")
        "Searching all KB tables for 'deadline'..."
    """
    try:
        if table_name:
            validate_identifier(table_name)
        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            # Get tables to search
            if table_name:
                tables = [table_name]
            else:
                tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

            if not tables:
                return "No KB tables found. Use create_kb_table to create one first."

            # Check if requested table exists
            if table_name and table_name not in tables:
                # Provide fuzzy table name suggestions
                from rapidfuzz import process
                suggestions = [
                    (name, score)
                    for name, score, _ in process.extract(
                        query,
                        tables,
                        scorer=None,  # defaults to WRatio
                        limit=3,
                    )
                    if score >= 60
                ]
                if suggestions:
                    suggested = ", ".join(f"{name} ({score:.0f}%)" for name, score in suggestions)
                    return f"Error: KB table '{table_name}' not found. Did you mean: {suggested}? Available: {', '.join(tables)}"
                return f"Error: KB table '{table_name}' not found. Available tables: {', '.join(tables)}"

            results = []
            has_fts_results = False

            for tbl in tables:
                # Try FTS search (match_bm25 is created by create_fts_index)
                # The macro is in fts_{table_name} schema: fts_{tbl}.match_bm25(id, query)
                try:
                    fts_query = f"""
                        SELECT id, content, metadata,
                               fts_{tbl}.match_bm25(id, ?) AS score
                        FROM {tbl}
                        WHERE fts_{tbl}.match_bm25(id, ?) IS NOT NULL
                        ORDER BY score ASC
                        LIMIT {limit}
                    """
                    matches = conn.execute(fts_query, [query, query]).fetchall()

                    if matches:
                        has_fts_results = True
                        results.append(f"--- From '{tbl}' (BM25 ranked) ---")
                        for doc_id, content, metadata, score in matches:
                            meta = f" [metadata: {metadata}]" if metadata else ""
                            results.append(f"[{score:.2f}] {content}{meta}")

                except Exception as fts_error:
                    # FTS not available, fall back to ILIKE
                    matches = conn.execute(f"""
                        SELECT content, metadata
                        FROM {tbl}
                        WHERE content ILIKE ? OR metadata ILIKE ?
                        LIMIT {limit}
                    """, [f"%{query}%", f"%{query}%"]).fetchall()

                    if matches:
                        has_fts_results = True
                        results.append(f"--- From '{tbl}' (substring match) ---")
                        for content, metadata in matches:
                            meta = f" [metadata: {metadata}]" if metadata else ""
                            results.append(f"- {content}{meta}")

            # Fuzzy fallback: no BM25 results, try RapidFuzz
            if not has_fts_results:
                from rapidfuzz import process, fuzz

                for tbl in tables:
                    # Get all documents from this table (with limit to avoid huge scans)
                    all_docs = conn.execute(
                        f"SELECT id, content, metadata FROM {tbl} LIMIT 1000"
                    ).fetchall()

                    if not all_docs:
                        continue

                    # Prepare candidates: content + metadata for scoring
                    candidates = []
                    for doc_id, content, metadata in all_docs:
                        search_text = f"{content} {metadata or ''}".strip()
                        # Limit text for scoring performance
                        candidates.append((doc_id, search_text[:500], content, metadata))

                    # Use RapidFuzz for fuzzy matching
                    matches = process.extract(
                        query,
                        [c[1] for c in candidates],
                        scorer=fuzz.WRatio,
                        limit=limit,
                    )

                    # Filter by score cutoff and format results
                    fuzzy_results = [
                        (candidates[i][2], candidates[i][3], score)
                        for i, (text, score, _) in enumerate(matches)
                        if score >= 70  # Score cutoff for fuzzy matching
                    ]

                    if fuzzy_results:
                        results.append(f"--- From '{tbl}' (fuzzy match) ---")
                        for content, metadata, score in fuzzy_results[:limit]:
                            meta = f" [metadata: {metadata}]" if metadata else ""
                            results.append(f"[{score:.0f}%] {content}{meta}")

            if not results:
                if table_name:
                    return f"No matches found in '{table_name}' for query: {query}"
                else:
                    return f"No matches found across all KB tables for query: {query}"

            return f"Search results for '{query}':\n\n" + "\n".join(results)

        finally:
            conn.close()

    except Exception as e:
        return f"Error searching KB: {str(e)}"


@tool
def kb_list() -> str:
    """
    List all Knowledge Base tables.

    Returns:
        List of KB tables with document counts.

    Examples:
        >>> kb_list()
        "Knowledge Base tables:\\n- notes: 12 documents (FTS indexed)\\n- docs: 5 documents (FTS indexed)"
    """
    try:
        conn = _kb_storage.get_connection()
        try:
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

            if not tables:
                return "Knowledge Base is empty. Use create_kb_table to create a table."

            result = ["Knowledge Base tables:"]
            for tbl in tables:
                # Get document count
                count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                result.append(f"- {tbl}: {count} documents (FTS indexed)")

            return "\n".join(result)

        finally:
            conn.close()

    except Exception as e:
        return f"Error listing KB tables: {str(e)}"


@tool
def describe_kb(table_name: str) -> str:
    """
    Get schema and sample data from a Knowledge Base table.

    Args:
        table_name: Name of the KB table to describe.

    Returns:
        Table schema, document count, and sample documents.

    Examples:
        >>> describe_kb("notes")
        "Table 'notes':\\nSchema: id, content, metadata, created_at\\nTotal documents: 3\\nSample documents:\\n1. Meeting notes..."
    """
    try:
        validate_identifier(table_name)
        conn = _kb_storage.get_connection()
        try:
            # Check if table exists
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                return f"Error: KB table '{table_name}' not found"

            # Get schema
            columns = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            schema = ", ".join([col[1] for col in columns])

            # Get document count
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            # Get sample documents (up to 3)
            samples = conn.execute(f"SELECT content, metadata FROM {table_name} LIMIT 3").fetchall()

            result = [f"Table '{table_name}':"]
            result.append(f"Schema: {schema}")
            result.append(f"Total documents: {count}")
            result.append("Has FTS index: Yes (BM25 ranking)")

            if samples:
                result.append("\nSample documents:")
                for i, (content, metadata) in enumerate(samples, 1):
                    meta_note = f" [metadata: {metadata}]" if metadata else ""
                    result.append(f"{i}. {content}{meta_note}")

            return "\n".join(result)

        finally:
            conn.close()

    except Exception as e:
        return f"Error describing table: {str(e)}"


@tool
def drop_kb_table(table_name: str) -> str:
    """
    Drop a Knowledge Base table and its FTS index.

    Warning: This permanently removes all documents in the table.

    Args:
        table_name: Name of the KB table to drop.

    Returns:
        Success message or error.

    Examples:
        >>> drop_kb_table("old_notes")
        "Dropped KB table 'old_notes' (3 documents removed, FTS index dropped)"
    """
    try:
        validate_identifier(table_name)
        conn = _kb_storage.get_connection()
        try:
            # Check if table exists
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                return f"Error: KB table '{table_name}' not found"

            # Get count before deletion
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            # Drop FTS index
            try:
                conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            except Exception:
                pass  # Index may not exist

            # Drop table
            conn.execute(f"DROP TABLE {table_name}")

            return f"Dropped KB table '{table_name}' ({count} documents removed, FTS index dropped)"

        finally:
            conn.close()

    except Exception as e:
        return f"Error dropping table: {str(e)}"


@tool
def delete_kb_documents(
    table_name: str,
    ids: str,
) -> str:
    """
    Delete specific documents from a Knowledge Base table by ID.

    Args:
        table_name: Name of the KB table.
        ids: Comma-separated document IDs to delete (e.g., "1,3,5" or "1").

    Returns:
        Success message with count of deleted documents.

    Examples:
        >>> delete_kb_documents("notes", "1,3,5")
        "Deleted 3 documents from KB table 'notes' (FTS index rebuilt)"

        >>> delete_kb_documents("notes", "10")
        "Deleted 1 document from KB table 'notes' (FTS index rebuilt)"
    """
    try:
        # Validate table name
        validate_identifier(table_name)

        # Parse IDs
        try:
            id_list = [int(id.strip()) for id in ids.split(",") if id.strip()]
        except ValueError:
            return "Error: IDs must be comma-separated integers (e.g., '1,3,5')"

        if not id_list:
            return "Error: No valid IDs provided"

        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            # Check if table exists
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                return f"Error: KB table '{table_name}' not found"

            # Delete documents
            placeholders = ",".join("?" * len(id_list))
            deleted = conn.execute(
                f"DELETE FROM {table_name} WHERE id IN ({placeholders})",
                id_list
            ).rowcount

            if deleted == 0:
                return f"No documents deleted - IDs {ids} not found in '{table_name}'"

            # Rebuild FTS index
            conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            conn.execute(f"PRAGMA create_fts_index('{table_name}', 'id', 'content', 'metadata')")

            return f"Deleted {deleted} document(s) from KB table '{table_name}' (FTS index rebuilt)"

        finally:
            conn.close()

    except Exception as e:
        return f"Error deleting documents: {str(e)}"


@tool
def add_kb_documents(
    table_name: str,
    documents: str,
) -> str:
    """
    Add documents to an existing KB table (rebuilds FTS index).

    Note: Adding documents requires rebuilding the FTS index, which may be
    slow for large tables. For large additions, consider creating a new table.

    Args:
        table_name: Name of existing KB table.
        documents: JSON array of document objects to add.
                   Example: '[{"content": "new document", "metadata": "tag"}]'

    Returns:
        Success message with count of added documents.

    Examples:
        >>> add_kb_documents("notes", '[{"content": "Additional note"}]')
        "Added 1 documents to KB table 'notes' (FTS index rebuilt)"
    """
    import json

    try:
        validate_identifier(table_name)
    except ValueError as e:
        return f"Error: {str(e)}"

    try:
        parsed_docs = json.loads(documents)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {str(e)}"

    if not isinstance(parsed_docs, list):
        return "Error: documents must be a JSON array"

    if len(parsed_docs) == 0:
        return "Error: documents array is empty"

    try:
        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            # Check if table exists
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                return f"Error: KB table '{table_name}' not found. Use create_kb_table to create it first."

            # Get current max id
            max_id = conn.execute(f"SELECT COALESCE(MAX(id), -1) FROM {table_name}").fetchone()[0]

            # Insert new documents
            for i, doc in enumerate(parsed_docs):
                content = doc.get("content", "")
                metadata = doc.get("metadata", "")
                conn.execute(
                    f"INSERT INTO {table_name} (id, content, metadata) VALUES (?, ?, ?)",
                    [max_id + i + 1, content, metadata]
                )

            # Rebuild FTS index
            conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            conn.execute(f"PRAGMA create_fts_index('{table_name}', 'id', 'content', 'metadata')")

            return f"Added {len(parsed_docs)} documents to KB table '{table_name}' (FTS index rebuilt)"

        finally:
            conn.close()

    except Exception as e:
        return f"Error adding documents: {str(e)}"


# Export list of tools for use in agent
async def get_kb_tools() -> list:
    """Get all Knowledge Base tools for use in the agent."""
    return [
        create_kb_table,
        search_kb,
        kb_list,
        describe_kb,
        drop_kb_table,
        add_kb_documents,
        delete_kb_documents,
    ]
