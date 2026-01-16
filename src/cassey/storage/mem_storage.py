"""Memory storage for embedded user memories and preferences.

Each thread has its own memory database (mem.db) with FTS indexing.
Stores profile information, preferences, facts, tasks, and notes extracted
from conversations or explicitly added via /remember.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from cassey.config import settings
from cassey.storage.file_sandbox import get_thread_id
from cassey.storage.user_registry import sanitize_thread_id


class MemoryStorage:
    """
    Memory storage for thread-scoped user memories.

    Each thread has its own DuckDB database with FTS for searching
    memories by content and key.
    """

    def __init__(self) -> None:
        """Initialize memory storage (no root path needed - uses settings)."""

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """
        Get the memory database path for a thread.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Path to the memory database file.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided and no thread_id in context")

        # Use settings path helper
        mem_path = settings.get_thread_mem_path(thread_id)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        return mem_path

    def get_connection(self, thread_id: str | None = None) -> duckdb.DuckDBPyConnection:
        """
        Get a database connection for the current thread.

        Creates the database file and schema if they don't exist.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Database connection object.
        """
        db_path = self._get_db_path(thread_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(str(db_path))
        self._ensure_schema(conn)
        return conn

    def _ensure_fts_installed(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Ensure FTS extension is installed and loaded."""
        try:
            conn.execute("INSTALL fts")
            conn.execute("LOAD fts")
        except Exception:
            pass  # May already be installed or unavailable

    def _ensure_schema(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create tables and FTS index if they don't exist."""
        # Create memories table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id UUID PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                key TEXT,
                content TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'active',
                source_message_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Install and setup FTS extension
        self._ensure_fts_installed(conn)
        try:
            conn.execute("PRAGMA create_fts_index('memories', 'id', 'content', 'key')")
        except Exception:
            # FTS might already exist or not be available
            pass

    def create_memory(
        self,
        content: str,
        memory_type: str = "note",
        key: str | None = None,
        confidence: float = 1.0,
        owner_type: str = "thread",
        owner_id: str | None = None,
        source_message_id: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """
        Create a new memory entry.

        Args:
            content: The memory content.
            memory_type: Type of memory (profile|preference|fact|task|note).
            key: Optional normalized key for deduplication.
            confidence: Confidence score (0-1).
            owner_type: Either 'thread' or 'user'.
            owner_id: Thread ID or user ID.
            source_message_id: Optional ID of the source message.
            thread_id: Thread identifier (uses context if None).

        Returns:
            The UUID of the created memory.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        if owner_id is None:
            owner_id = thread_id

        memory_id = str(uuid.uuid4())

        conn = self.get_connection(thread_id)
        try:
            conn.execute("""
                INSERT INTO memories (
                    id, owner_type, owner_id, memory_type, key,
                    content, confidence, source_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (memory_id, owner_type, owner_id, memory_type, key, content, confidence, source_message_id))
        finally:
            conn.close()

        return memory_id

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        confidence: float | None = None,
        status: str | None = None,
        thread_id: str | None = None,
    ) -> bool:
        """
        Update an existing memory.

        Args:
            memory_id: UUID of the memory to update.
            content: New content (optional).
            confidence: New confidence score (optional).
            status: New status (optional).
            thread_id: Thread identifier (uses context if None).

        Returns:
            True if updated, False if not found.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # First check if memory exists
            existing = conn.execute(
                "SELECT id FROM memories WHERE id = ? AND status != 'deleted'",
                (memory_id,)
            ).fetchone()

            if not existing:
                return False

            updates = []
            params = []

            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)
            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if not updates:
                return True

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(memory_id)

            conn.execute(f"""
                UPDATE memories
                SET {', '.join(updates)}
                WHERE id = ? AND status != 'deleted'
            """, params)

            return True
        finally:
            conn.close()

    def delete_memory(
        self,
        memory_id: str,
        thread_id: str | None = None,
    ) -> bool:
        """
        Delete (soft delete) a memory by setting status to 'deleted'.

        Args:
            memory_id: UUID of the memory to delete.
            thread_id: Thread identifier (uses context if None).

        Returns:
            True if deleted, False if not found.
        """
        return self.update_memory(memory_id, status="deleted", thread_id=thread_id)

    def deprecate_memory(
        self,
        memory_id: str,
        thread_id: str | None = None,
    ) -> bool:
        """
        Deprecate a memory by setting status to 'deprecated'.

        Used when a newer version of the memory exists.

        Args:
            memory_id: UUID of the memory to deprecate.
            thread_id: Thread identifier (uses context if None).

        Returns:
            True if deprecated, False if not found.
        """
        return self.update_memory(memory_id, status="deprecated", thread_id=thread_id)

    def list_memories(
        self,
        memory_type: str | None = None,
        status: str = "active",
        thread_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List memories for a thread.

        Args:
            memory_type: Filter by memory type (optional).
            status: Filter by status (default 'active').
            thread_id: Thread identifier (uses context if None).

        Returns:
            List of memory dictionaries.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            if memory_type:
                result = conn.execute("""
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE memory_type = ? AND status = ?
                    ORDER BY created_at DESC
                """, (memory_type, status))
            else:
                result = conn.execute("""
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (status,))

            columns = ["id", "memory_type", "key", "content", "confidence", "status", "created_at", "updated_at"]
            return [
                {**dict(zip(columns, row)), "id": str(row[0])}
                for row in result.fetchall()
            ]
        finally:
            conn.close()

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        min_confidence: float = 0.0,
        thread_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search memories by content using FTS.

        Args:
            query: Search query string.
            limit: Maximum number of results.
            min_confidence: Minimum confidence score.
            thread_id: Thread identifier (uses context if None).

        Returns:
            List of matching memory dictionaries.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Try FTS search first
            try:
                self._ensure_fts_installed(conn)
                result = conn.execute("""
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = 'active'
                      AND confidence >= ?
                      AND fts_memories.match_bm25(id, ?) IS NOT NULL
                    ORDER BY fts_memories.match_bm25(id, ?) ASC
                    LIMIT ?
                """, (min_confidence, query, query, limit))
            except Exception:
                # FTS not available or index not set up, fall back to LIKE
                result = conn.execute("""
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = 'active'
                      AND confidence >= ?
                      AND LOWER(content) LIKE LOWER(?)
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (min_confidence, f"%{query}%", limit))

            columns = ["id", "memory_type", "key", "content", "confidence", "status", "created_at", "updated_at"]
            return [
                {**dict(zip(columns, row)), "id": str(row[0])}
                for row in result.fetchall()
            ]
        finally:
            conn.close()

    def get_memory_by_key(
        self,
        key: str,
        thread_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a memory by its key (most recent active).

        Args:
            key: The memory key.
            thread_id: Thread identifier (uses context if None).

        Returns:
            Memory dictionary or None if not found.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            result = conn.execute("""
                SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                FROM memories
                WHERE key = ? AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
            """, (key,))

            row = result.fetchone()
            if row:
                columns = ["id", "memory_type", "key", "content", "confidence", "status", "created_at", "updated_at"]
                return {**dict(zip(columns, row)), "id": str(row[0])}
            return None
        finally:
            conn.close()

    def normalize_or_create(
        self,
        key: str,
        content: str,
        memory_type: str = "preference",
        confidence: float = 1.0,
        thread_id: str | None = None,
    ) -> tuple[str, bool]:
        """
        Normalize a memory by key: deprecate old version, create new one.

        Args:
            key: The memory key.
            content: New content.
            memory_type: Type of memory.
            confidence: Confidence score.
            thread_id: Thread identifier (uses context if None).

        Returns:
            Tuple of (memory_id, is_new).
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Check for existing active memory with this key
            existing = conn.execute("""
                SELECT id FROM memories
                WHERE key = ? AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
            """, (key,)).fetchone()

            if existing:
                # Deprecate old, create new
                old_id = existing[0]
                self.deprecate_memory(old_id, thread_id=thread_id)

            memory_id = self.create_memory(
                content=content,
                memory_type=memory_type,
                key=key,
                confidence=confidence,
                thread_id=thread_id,
            )

            return memory_id, existing is None
        finally:
            conn.close()


# Global storage instance
_mem_storage = MemoryStorage()


def get_mem_storage() -> MemoryStorage:
    """Get the global memory storage instance."""
    return _mem_storage
