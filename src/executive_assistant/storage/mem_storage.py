"""Memory storage for embedded user memories with temporal versioning.

Each user/thread has its own SQLite database (mem.db) with FTS5 indexing.
Stores profile information, preferences, facts, constraints, style, and context
with full history tracking and point-in-time query support.

Versioning: When updating a memory with the same key, the old version is preserved
with valid_to timestamp, and a new version is created with incremented version number.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.user_registry import register_mem_path_best_effort


_ALLOWED_TYPES = {
    "profile",
    "fact",
    "preference",
    "constraint",
    "style",
    "context",
}


def _normalize_text(text: str) -> str:
    """Normalize text for dedupe checks."""
    normalized = text.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    return normalized


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class MemoryStorage:
    """Memory storage for thread-scoped memories with temporal versioning."""

    def __init__(self) -> None:
        pass

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the memory database path for the current thread context."""
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided or in context")

        mem_path = settings.get_thread_mem_path(thread_id)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        return mem_path

    def get_connection(self, thread_id: str | None = None) -> sqlite3.Connection:
        """Get a SQLite connection for the current context."""
        db_path = self._get_db_path(thread_id)
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            return conn
        except sqlite3.DatabaseError:
            # If DB is corrupted, reset it (only for new deployments)
            if db_path.exists():
                db_path.unlink()
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables, indexes, and FTS with temporal support."""
        # Main table with temporal fields
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                key TEXT,

                -- Current state
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'active',

                -- Temporal fields (NEW)
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                history TEXT NOT NULL DEFAULT '[]',

                -- Metadata
                source_message_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Status index
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status)")

        # Type index
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")

        # Normalized content index
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_norm_content ON memories(normalized_content)")

        # Temporal indexes (NEW)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key_valid ON memories(key, valid_from, valid_to)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_valid_from ON memories(valid_from)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_valid_to ON memories(valid_to) WHERE valid_to IS NOT NULL")

        # Full-text search
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts
                USING fts5(content, key, content='memories', content_rowid='rowid')
                """
            )
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO mem_fts(rowid, content, key) VALUES (new.rowid, new.content, new.key);
                END;
                CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO mem_fts(mem_fts, rowid, content, key) VALUES('delete', old.rowid, old.content, old.key);
                END;
                CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE OF content ON memories BEGIN
                    INSERT INTO mem_fts(mem_fts, rowid, content, key) VALUES('delete', old.rowid, old.content, old.key);
                    INSERT INTO mem_fts(rowid, content, key) VALUES (new.rowid, new.content, new.key);
                END;
                """
            )
        except sqlite3.OperationalError:
            # FTS5 not available
            pass

        conn.commit()

    def _validate_type(self, memory_type: str) -> None:
        if memory_type not in _ALLOWED_TYPES:
            raise ValueError(
                f"Invalid memory_type '{memory_type}'. Allowed: {', '.join(sorted(_ALLOWED_TYPES))}"
            )

    # ========================================================================
    # CREATE: Create or update memory with versioning
    # ========================================================================

    def create_memory(
        self,
        content: str,
        memory_type: str = "profile",
        key: str | None = None,
        confidence: float = 1.0,
        owner_type: str = "thread",
        owner_id: str | None = None,
        source_message_id: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """
        Create a new memory entry or version an existing one.

        If key exists:
            - Old version is marked with valid_to = now
            - New version is created with version = old_version + 1
            - History JSON is updated with both versions
        """
        self._validate_type(memory_type)

        if thread_id is None:
            thread_id = get_thread_id()
        if owner_id is None:
            owner_id = thread_id

        now = _utc_now()
        memory_id = str(uuid.uuid4())
        normalized = _normalize_text(content)

        conn = self.get_connection(thread_id)
        try:
            # Check if key already exists
            if key:
                existing = conn.execute(
                    "SELECT id, version, content FROM memories WHERE key = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
                    (key,),
                ).fetchone()

                if existing:
                    existing_id, old_version, old_content = existing

                    # Mark old version as expired
                    old_history = json.loads(conn.execute(
                        "SELECT history FROM memories WHERE id = ?", (existing_id,)
                    ).fetchone()[0] or "[]")

                    # Update old version's history
                    old_history_obj = json.loads(old_history) if old_history else []
                    for entry in old_history_obj:
                        if entry["version"] == old_version:
                            entry["valid_to"] = now
                            entry["changed_at"] = now
                            entry["change_reason"] = "superseded"

                    # Update old memory
                    conn.execute(
                        """
                        UPDATE memories
                        SET
                            valid_to = ?,
                            history = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, json.dumps(old_history_obj), now, existing_id)
                    )

                    # Create new version
                    new_version = old_version + 1

                    # Build new history array
                    new_history = old_history_obj + [{
                        "version": new_version,
                        "content": content,
                        "confidence": confidence,
                        "valid_from": now,
                        "valid_to": None,
                        "changed_at": now,
                        "change_reason": "update"
                    }]

                    conn.execute(
                        """
                        INSERT INTO memories (
                            id, owner_type, owner_id, memory_type, key,
                            content, normalized_content, confidence, status,
                            valid_from, valid_to, version, history,
                            source_message_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            memory_id, owner_type, owner_id, memory_type, key,
                            content, normalized, confidence, 'active',
                            now, None, new_version, json.dumps(new_history),
                            source_message_id, now, now
                        ),
                    )

                    conn.commit()
                    return memory_id

            # No existing key, create new memory
            history_array = [{
                "version": 1,
                "content": content,
                "confidence": confidence,
                "valid_from": now,
                "valid_to": None,
                "changed_at": now,
                "change_reason": "create"
            }]

            conn.execute(
                """
                INSERT INTO memories (
                    id, owner_type, owner_id, memory_type, key,
                    content, normalized_content, confidence, status,
                    valid_from, valid_to, version, history,
                    source_message_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id, owner_type, owner_id, memory_type, key,
                    content, normalized, confidence, 'active',
                    now, None, 1, json.dumps(history_array),
                    source_message_id, now, now
                ),
            )
            conn.commit()
            return memory_id
        finally:
            conn.close()

    # ========================================================================
    # UPDATE: Update memory content (creates new version)
    # ========================================================================

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        confidence: float | None = None,
        status: str | None = None,
        thread_id: str | None = None,
    ) -> bool:
        """Update an existing memory (creates new version if content changes)."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Get current memory
            existing = conn.execute(
                "SELECT * FROM memories WHERE id = ? AND status != 'deleted'",
                (memory_id,),
            ).fetchone()

            if not existing:
                return False

            # If updating content, create new version
            if content is not None:
                return self._create_new_version(
                    conn, memory_id, existing, content, confidence
                )

            # If only updating confidence/status, modify current version
            updates = []
            params = []

            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)

            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if updates:
                updates.append("updated_at = ?")
                params.append(_utc_now())
                params.append(memory_id)

                conn.execute(
                    f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()
                return True

            return True
        finally:
            conn.close()

    def _create_new_version(
        self,
        conn: sqlite3.Connection,
        memory_id: str,
        existing: sqlite3.Row,
        new_content: str,
        new_confidence: float | None,
    ) -> bool:
        """Create a new version of an existing memory."""

        old_version = existing["version"]
        old_content = existing["content"]
        old_confidence = existing["confidence"]
        key = existing["key"]

        now = _utc_now()

        # Mark old version as expired
        old_history = json.loads(existing["history"])
        for entry in old_history:
            if entry["version"] == old_version:
                entry["valid_to"] = now
                entry["changed_at"] = now
                entry["change_reason"] = "superseded"

        conn.execute(
            "UPDATE memories SET valid_to = ?, history = ?, updated_at = ? WHERE id = ?",
            (now, json.dumps(old_history), now, memory_id)
        )

        # Create new version (INSERT new row)
        new_version = old_version + 1
        new_memory_id = str(uuid.uuid4())

        # Build new history array
        if new_confidence is None:
            new_confidence = old_confidence

        new_history = old_history + [{
            "version": new_version,
            "content": new_content,
            "confidence": new_confidence,
            "valid_from": now,
            "valid_to": None,
            "changed_at": now,
            "change_reason": "update"
        }]

        # Get additional fields needed for INSERT
        owner_type = existing["owner_type"] if "owner_type" in existing.keys() else "thread"
        owner_id = existing["owner_id"] if "owner_id" in existing.keys() else ""
        memory_type = existing["memory_type"] if "memory_type" in existing.keys() else "fact"

        conn.execute(
            """
            INSERT INTO memories (
                id, owner_type, owner_id, memory_type, key,
                content, normalized_content, confidence, status,
                valid_from, valid_to, version, history,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_memory_id, owner_type, owner_id, memory_type, key,
                new_content, _normalize_text(new_content), new_confidence, 'active',
                now, None, new_version, json.dumps(new_history),
                now, now
            )
        )

        conn.commit()
        return True

    # ========================================================================
    # TEMPORAL QUERIES: Point-in-time and history
    # ========================================================================

    def get_memory_at_time(
        self,
        key: str,
        query_time: str,
        thread_id: str | None = None
    ) -> dict | None:
        """
        Get memory value as of a specific point in time.

        Args:
            key: Memory key (e.g., "location")
            query_time: ISO timestamp string
            thread_id: Thread identifier

        Returns:
            Memory dict or None if no valid memory found
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                """
                SELECT id, memory_type, key, content, confidence, version, valid_from, valid_to
                FROM memories
                WHERE key = ?
                  AND status = 'active'
                  AND valid_from <= ?
                  AND (valid_to IS NULL OR valid_to > ?)
                ORDER BY version ASC
                LIMIT 1
                """,
                (key, query_time, query_time)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "memory_type": row["memory_type"],
                "key": row["key"],
                "content": row["content"],
                "confidence": row["confidence"],
                "version": row["version"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
            }
        finally:
            conn.close()

    def get_memory_history(
        self,
        key: str,
        thread_id: str | None = None
    ) -> List[dict]:
        """
        Get full version history of a memory.

        Args:
            key: Memory key
            thread_id: Thread identifier

        Returns:
            List of memory versions (oldest first)
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Get current memory (the one with valid_to IS NULL)
            current = conn.execute(
                "SELECT history FROM memories WHERE key = ? AND status = 'active' AND valid_to IS NULL LIMIT 1",
                (key,)
            ).fetchone()

            if not current:
                return []

            history = json.loads(current[0])

            # Return in chronological order
            return sorted(history, key=lambda x: x["version"])
        finally:
            conn.close()

    # ========================================================================
    # EXISTING METHODS (preserved for compatibility)
    # ========================================================================

    def delete_memory(self, memory_id: str, thread_id: str | None = None) -> bool:
        """Soft delete a memory."""
        return self.update_memory(memory_id, status="deleted", thread_id=thread_id)

    def deprecate_memory(self, memory_id: str, thread_id: str | None = None) -> bool:
        """Deprecate a memory."""
        return self.update_memory(memory_id, status="deprecated", thread_id=thread_id)

    def list_memories(
        self,
        memory_type: str | None = None,
        status: str = "active",
        thread_id: str | None = None,
    ) -> List[dict[str, Any]]:
        """List all memories (current versions only)."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            if memory_type:
                rows = conn.execute(
                    """
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE memory_type = ? AND status = ?
                    ORDER BY updated_at DESC
                    """,
                    (memory_type, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    """,
                    (status,),
                ).fetchall()

            return [
                {
                    "id": row["id"],
                    "memory_type": row["memory_type"],
                    "key": row["key"],
                    "content": row["content"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        min_confidence: float = 0.0,
        thread_id: str | None = None,
    ) -> List[dict[str, Any]]:
        """Search memories (searches current versions only)."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            rows = []
            try:
                rows = conn.execute(
                    """
                    SELECT m.id, m.memory_type, m.key, m.content, m.confidence, m.status, m.created_at, m.updated_at
                    FROM mem_fts
                    JOIN memories m ON m.rowid = mem_fts.rowid
                    WHERE m.status = 'active' AND m.confidence >= ? AND mem_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (min_confidence, query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = 'active'
                      AND confidence >= ?
                      AND (LOWER(content) LIKE LOWER(?) OR LOWER(key) LIKE LOWER(?))
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (min_confidence, f"%{query}%", f"%{query}%", limit),
                ).fetchall()

            return [
                {
                    "id": row[0],
                    "memory_type": row[1],
                    "key": row[2],
                    "content": row[3],
                    "confidence": row[4],
                    "status": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_memory_by_content(self, content: str, thread_id: str | None = None) -> dict | None:
        """Get memory by content (current version)."""
        if thread_id is None:
            thread_id = get_thread_id()

        normalized = _normalize_text(content)
        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                """
                SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                FROM memories
                WHERE status = 'active' AND normalized_content = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "memory_type": row["memory_type"],
                "key": row["key"],
                "content": row["content"],
                "confidence": row["confidence"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    def get_memory_by_key(self, key: str, thread_id: str | None = None) -> dict[str, Any] | None:
        """Get memory by key (returns current version)."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                """
                SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                FROM memories
                WHERE key = ? AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (key,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "memory_type": row["memory_type"],
                "key": row["key"],
                "content": row["content"],
                "confidence": row["confidence"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
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
        """Normalize a memory by key: update in place if exists, else create."""
        self._validate_type(memory_type)
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            existing = conn.execute(
                "SELECT id, version, content, confidence, key, history FROM memories WHERE key = ? AND status = 'active' AND valid_to IS NULL LIMIT 1",
                (key,),
            ).fetchone()
            if existing:
                self._create_new_version(
                    conn,
                    existing[0],
                    existing,
                    content,
                    confidence
                )
                return existing[0], False

            memory_id = self.create_memory(
                content=content,
                memory_type=memory_type,
                key=key,
                confidence=confidence,
                thread_id=thread_id,
            )
            return memory_id, True
        finally:
            conn.close()


_mem_storage = MemoryStorage()


def get_mem_storage() -> MemoryStorage:
    return _mem_storage
