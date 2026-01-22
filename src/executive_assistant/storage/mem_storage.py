"""Memory storage for embedded user memories and preferences.

Each user/group has its own SQLite database (mem.db) with FTS5 indexing.
Stores profile information, preferences, facts, constraints, style, and context
extracted from conversations or explicitly added via /remember.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


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
    return datetime.now(timezone.utc).isoformat()


class MemoryStorage:
    """Memory storage for user/group-scoped memories."""

    def __init__(self) -> None:
        pass

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the memory database path for a user/group context."""
        storage_id = None

        # 1. user_id from context (individual mode)
        from executive_assistant.storage.group_storage import get_user_id as get_user_id_from_context
        user_id_val = get_user_id_from_context()
        if user_id_val:
            storage_id = user_id_val
        else:
            # 2. group_id from context (team mode)
            from executive_assistant.storage.group_storage import get_workspace_id
            group_id = get_workspace_id()
            if group_id:
                storage_id = group_id

        # 3. Fall back to thread_id if no user_id or group_id
        if storage_id is None:
            if thread_id is None:
                thread_id = get_thread_id()
            if thread_id is None:
                raise ValueError("No user_id, group_id, or thread_id provided/context")
            from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
            storage_id = sanitize_thread_id_to_user_id(thread_id)

        if storage_id.startswith("group_"):
            mem_path = settings.get_group_mem_path(storage_id)
        else:
            mem_path = settings.get_user_mem_path(storage_id)

        mem_path.parent.mkdir(parents=True, exist_ok=True)
        return mem_path

    def get_connection(self, thread_id: str | None = None) -> sqlite3.Connection:
        """Get a SQLite connection for the current context."""
        db_path = self._get_db_path(thread_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            return conn
        except sqlite3.DatabaseError:
            # Likely a legacy DuckDB file; reset since no migration is required.
            try:
                if db_path.exists():
                    db_path.unlink()
            except OSError:
                pass
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            self._ensure_schema(conn)
            return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables and FTS index if they don't exist."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                key TEXT UNIQUE,
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'active',
                source_message_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_status
            ON memories(status)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_type
            ON memories(memory_type)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_norm_content
            ON memories(normalized_content)
            """
        )

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
                CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memories BEGIN
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
        """Create a new memory entry or update an existing key."""
        self._validate_type(memory_type)

        if thread_id is None:
            thread_id = get_thread_id()
        if owner_id is None:
            owner_id = thread_id

        memory_id = str(uuid.uuid4())
        normalized = _normalize_text(content)
        now = _utc_now()

        conn = self.get_connection(thread_id)
        try:
            if key:
                existing = conn.execute(
                    "SELECT id FROM memories WHERE key = ? ORDER BY updated_at DESC LIMIT 1",
                    (key,),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE memories
                        SET content = ?, normalized_content = ?, confidence = ?, status = 'active', updated_at = ?
                        WHERE key = ?
                        """,
                        (content, normalized, confidence, now, key),
                    )
                    conn.commit()
                    return str(existing["id"])

            conn.execute(
                """
                INSERT INTO memories (
                    id, owner_type, owner_id, memory_type, key,
                    content, normalized_content, confidence, status, source_message_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    memory_id,
                    owner_type,
                    owner_id,
                    memory_type,
                    key,
                    content,
                    normalized,
                    confidence,
                    source_message_id,
                    now,
                    now,
                ),
            )
            conn.commit()
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
        """Update an existing memory."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            existing = conn.execute(
                "SELECT id FROM memories WHERE id = ? AND status != 'deleted'",
                (memory_id,),
            ).fetchone()
            if not existing:
                return False

            updates = []
            params: list[Any] = []

            if content is not None:
                updates.append("content = ?")
                params.append(content)
                updates.append("normalized_content = ?")
                params.append(_normalize_text(content))
            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)
            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if not updates:
                return True

            updates.append("updated_at = ?")
            params.append(_utc_now())
            params.append(memory_id)

            conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_memory(self, memory_id: str, thread_id: str | None = None) -> bool:
        return self.update_memory(memory_id, status="deleted", thread_id=thread_id)

    def deprecate_memory(self, memory_id: str, thread_id: str | None = None) -> bool:
        return self.update_memory(memory_id, status="deprecated", thread_id=thread_id)

    def list_memories(
        self,
        memory_type: str | None = None,
        status: str = "active",
        thread_id: str | None = None,
    ) -> list[dict[str, Any]]:
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
                    ORDER BY created_at DESC
                    """,
                    (memory_type, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, memory_type, key, content, confidence, status, created_at, updated_at
                    FROM memories
                    WHERE status = ?
                    ORDER BY created_at DESC
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
    ) -> list[dict[str, Any]]:
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
                "SELECT id FROM memories WHERE key = ? ORDER BY updated_at DESC LIMIT 1",
                (key,),
            ).fetchone()
            if existing:
                self.update_memory(existing["id"], content=content, confidence=confidence, thread_id=thread_id)
                return str(existing["id"]), False

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
