"""Journal storage for time-based activity tracking with automatic rollups.

Stores user activities in a time-series format with automatic hierarchical rollups:
- Raw entries: Individual activities
- Hourly rollups: Summarized hourly activities
- Weekly rollups: Summarized weekly activities
- Monthly rollups: Summarized monthly activities
- Yearly rollups: Summarized yearly activities

Storage: SQLite with sqlite-vss for semantic search
"""

from __future__ import annotations

import json
import sqlite3
import struct
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal

from executive_assistant.config import settings

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _get_embedding(text: str) -> list[float] | None:
    """Generate embedding for text using sentence-transformers.

    Returns None if sentence-transformers is not available.
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None

    try:
        # Lazy-load model (singleton pattern)
        if not hasattr(_get_embedding, "_model"):
            _get_embedding._model = SentenceTransformer("all-MiniLM-L6-v2")

        model = _get_embedding._model
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception:
        return None


def _serialize_embedding(embedding: list[float] | None) -> bytes | None:
    """Serialize embedding to bytes for SQLite BLOB storage."""
    if embedding is None:
        return None

    # Pack floats as little-endian bytes
    return struct.pack(f"{len(embedding)}f", *embedding)


def _deserialize_embedding(blob: bytes | None) -> list[float] | None:
    """Deserialize embedding bytes to list of floats."""
    if blob is None:
        return None

    # Unpack bytes to floats
    num_floats = len(blob) // 4  # 4 bytes per float
    return list(struct.unpack(f"{num_floats}f", blob))


EntryType = Literal[
    "raw",
    "hourly_rollup",
    "weekly_rollup",
    "monthly_rollup",
    "yearly_rollup",
]


class JournalStorage:
    """Storage for journal entries with time-based rollups."""

    def __init__(self) -> None:
        pass

    def _get_journal_dir(self, thread_id: str | None = None) -> Path:
        """Get the journal directory for the current thread."""
        if thread_id is None:
            from executive_assistant.storage.file_sandbox import get_thread_id
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided or in context")

        instincts_dir = settings.get_thread_instincts_dir(thread_id)
        journal_dir = instincts_dir.parent / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        return journal_dir

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the SQLite database path."""
        journal_dir = self._get_journal_dir(thread_id)
        return journal_dir / "journal.db"

    def get_connection(self, thread_id: str | None = None) -> sqlite3.Connection:
        """Get a SQLite connection for the current context."""
        db_path = self._get_db_path(thread_id)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables, indexes, and FTS."""
        # Main journal entries table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                content TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                period_start TEXT,
                period_end TEXT,
                metadata JSON,
                embedding BLOB,
                parent_id TEXT,
                rollup_level INTEGER,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES journal_entries(id)
            )
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_thread ON journal_entries(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON journal_entries(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_type ON journal_entries(entry_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_parent ON journal_entries(parent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_rollup ON journal_entries(rollup_level)")

        # Full-text search for keyword search
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
                    content,
                    content='journal_entries',
                    content_rowid='rowid'
                )
            """)

            # Triggers for FTS sync
            conn.executescript("""
                CREATE TRIGGER IF NOT EXISTS journal_ai AFTER INSERT ON journal_entries BEGIN
                    INSERT INTO journal_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS journal_ad AFTER DELETE ON journal_entries BEGIN
                    INSERT INTO journal_fts(journal_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                END;
                CREATE TRIGGER IF NOT EXISTS journal_au AFTER UPDATE OF content ON journal_entries BEGIN
                    INSERT INTO journal_fts(journal_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                    INSERT INTO journal_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
            """)
        except sqlite3.OperationalError:
            # FTS5 not available
            pass

        # Semantic search with sqlite-vss
        try:
            # Load sqlite-vss extension
            conn.enable_load_extension(True)
            conn.load_extension("vss")

            # Create VSS table for semantic search
            # Note: We create a separate table for vectors to avoid issues with rowid
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS journal_vss USING vss0(
                    id TEXT PRIMARY KEY,
                    embedding(384)
                );
            """)

            # Create index for faster VSS queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_vss_id
                ON journal_vss(id);
            """)
        except (sqlite3.OperationalError, AttributeError) as e:
            # sqlite-vss not available or error loading extension
            # Silently continue - semantic search will be disabled
            pass

        conn.commit()

    # ========================================================================
    # CREATE: Add journal entries
    # ========================================================================

    def add_entry(
        self,
        content: str,
        entry_type: EntryType = "raw",
        thread_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
        parent_id: str | None = None,
        rollup_level: int = 0,
    ) -> str:
        """
        Add a journal entry.

        Args:
            content: Entry content
            entry_type: Type of entry (raw, hourly_rollup, etc.)
            thread_id: Thread identifier
            timestamp: ISO timestamp (defaults to now)
            metadata: Additional metadata (JSON)
            parent_id: Parent entry ID (for rollup chains)
            rollup_level: Rollup level (0=raw, 1=hourly, 2=daily, etc.)

        Returns:
            Entry ID
        """
        if timestamp is None:
            timestamp = _utc_now()

        if metadata is None:
            metadata = {}

        entry_id = str(uuid.uuid4())
        now = _utc_now()

        # Generate embedding for semantic search
        embedding = _get_embedding(content)
        embedding_blob = _serialize_embedding(embedding) if embedding else None

        conn = self.get_connection(thread_id)
        try:
            # Insert main entry
            conn.execute("""
                INSERT INTO journal_entries (
                    id, thread_id, content, entry_type, timestamp,
                    period_start, period_end, metadata, parent_id,
                    rollup_level, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id,
                thread_id or "",  # Will be set by get_connection if None
                content,
                entry_type,
                timestamp,
                timestamp,  # period_start defaults to timestamp
                None,  # period_end
                json.dumps(metadata),
                parent_id,
                rollup_level,
                "active",
                now,
                now,
            ))

            # Insert embedding into VSS table if available
            if embedding_blob is not None:
                try:
                    conn.execute("""
                        INSERT INTO journal_vss (id, embedding)
                        VALUES (?, ?)
                    """, (entry_id, embedding_blob))
                except sqlite3.OperationalError:
                    # VSS table doesn't exist or error - skip semantic search
                    pass

            conn.commit()
            return entry_id
        finally:
            conn.close()

    # ========================================================================
    # QUERY: Retrieve journal entries
    # ========================================================================

    def get_entry(self, entry_id: str, thread_id: str | None = None) -> dict | None:
        """Get a specific journal entry by ID."""
        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                "SELECT * FROM journal_entries WHERE id = ?",
                (entry_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "content": row["content"],
                "entry_type": row["entry_type"],
                "timestamp": row["timestamp"],
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "parent_id": row["parent_id"],
                "rollup_level": row["rollup_level"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    def list_entries(
        self,
        thread_id: str | None = None,
        entry_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List journal entries with optional filtering.

        Args:
            thread_id: Thread identifier
            entry_type: Filter by entry type
            start_time: Start of time range (ISO timestamp)
            end_time: End of time range (ISO timestamp)
            limit: Maximum number of entries to return

        Returns:
            List of journal entries
        """
        conn = self.get_connection(thread_id)
        try:
            # Build query
            query = "SELECT * FROM journal_entries WHERE status = 'active'"
            params = []

            if entry_type:
                query += " AND entry_type = ?"
                params.append(entry_type)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "content": row["content"],
                    "entry_type": row["entry_type"],
                    "timestamp": row["timestamp"],
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "parent_id": row["parent_id"],
                    "rollup_level": row["rollup_level"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                })

            return results
        finally:
            conn.close()

    # ========================================================================
    # SEARCH: Keyword and semantic search
    # ========================================================================

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search journal entries using semantic search (sqlite-vss) + keyword search (FTS5).

        Priority order:
        1. Semantic search (sqlite-vss) - meaning-based
        2. Keyword search (FTS5) - keyword matching
        3. LIKE search - fallback

        Args:
            query: Search query
            thread_id: Thread identifier
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum results

        Returns:
            List of matching entries with distance scores (if semantic search)
        """
        conn = self.get_connection(thread_id)
        try:
            # Try semantic search first
            query_embedding = _get_embedding(query)

            if query_embedding is not None:
                try:
                    # Generate embedding blob for query
                    query_blob = _serialize_embedding(query_embedding)

                    # Build semantic search query with VSS
                    sql_query = """
                        SELECT e.*, v.distance
                        FROM journal_entries e
                        INNER JOIN journal_vss v ON e.id = v.id
                        WHERE e.status = 'active'
                        AND v.embedding MATCH ?
                        AND e.id IN (
                            SELECT id FROM journal_vss
                            WHERE embedding MATCH ?
                            ORDER BY distance
                            LIMIT ?
                        )
                    """
                    params = [query_blob, query_blob, limit * 3]  # Get more candidates, filter later

                    if start_time:
                        sql_query += " AND e.timestamp >= ?"
                        params.append(start_time)

                    if end_time:
                        sql_query += " AND e.timestamp <= ?"
                        params.append(end_time)

                    sql_query += " ORDER BY v.distance, e.timestamp DESC LIMIT ?"
                    params.append(limit)

                    rows = conn.execute(sql_query, params).fetchall()

                    # Format results with distance scores
                    results = []
                    for row in rows:
                        results.append({
                            "id": row["id"],
                            "thread_id": row["thread_id"],
                            "content": row["content"],
                            "entry_type": row["entry_type"],
                            "timestamp": row["timestamp"],
                            "period_start": row["period_start"],
                            "period_end": row["period_end"],
                            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                            "parent_id": row["parent_id"],
                            "rollup_level": row["rollup_level"],
                            "status": row["status"],
                            "distance": row.get("distance"),  # Semantic distance (lower = more similar)
                        })

                    return results

                except (sqlite3.OperationalError, AttributeError) as e:
                    # VSS not available or error, fall back to FTS5
                    pass

            # Fall back to FTS5 keyword search
            try:
                sql_query = """
                    SELECT e.* FROM journal_entries e
                    JOIN journal_fts f ON e.rowid = f.rowid
                    WHERE e.status = 'active' AND journal_fts MATCH ?
                """
                params = [query]

                if start_time:
                    sql_query += " AND e.timestamp >= ?"
                    params.append(start_time)

                if end_time:
                    sql_query += " AND e.timestamp <= ?"
                    params.append(end_time)

                sql_query += " ORDER BY e.timestamp DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql_query, params).fetchall()
            except sqlite3.OperationalError:
                # FTS5 not available, fall back to LIKE search
                sql_query = """
                    SELECT * FROM journal_entries
                    WHERE status = 'active' AND content LIKE ?
                """
                params = [f"%{query}%"]

                if start_time:
                    sql_query += " AND timestamp >= ?"
                    params.append(start_time)

                if end_time:
                    sql_query += " AND timestamp <= ?"
                    params.append(end_time)

                sql_query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql_query, params).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "content": row["content"],
                    "entry_type": row["entry_type"],
                    "timestamp": row["timestamp"],
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "parent_id": row["parent_id"],
                    "rollup_level": row["rollup_level"],
                    "status": row["status"],
                })

            return results
        finally:
            conn.close()

    # ========================================================================
    # ROLLUPS: Time-based hierarchical rollups
    # ========================================================================

    def create_rollup(
        self,
        thread_id: str,
        rollup_type: EntryType,
        period_start: str,
        period_end: str,
        parent_ids: list[str] | None = None,
    ) -> str:
        """
        Create a time-based rollup from child entries.

        Args:
            thread_id: Thread identifier
            rollup_type: Type of rollup (hourly_rollup, daily_rollup, etc.)
            period_start: Start of period
            period_end: End of period
            parent_ids: List of child entry IDs to roll up

        Returns:
            Rollup entry ID
        """
        # Get child entries
        child_entries = []
        if parent_ids:
            for pid in parent_ids:
                entry = self.get_entry(pid, thread_id)
                if entry:
                    child_entries.append(entry)

        # Generate rollup content from child entries
        if child_entries:
            contents = [e["content"] for e in child_entries]
            rollup_content = f"Rollup of {len(contents)} activities: " + "; ".join(contents[:3])
            if len(contents) > 3:
                rollup_content += f"... and {len(contents) - 3} more"
        else:
            rollup_content = f"{rollup_type} for {period_start} to {period_end}"

        # Determine rollup level
        rollup_levels = {
            "raw": 0,
            "hourly_rollup": 1,
            "weekly_rollup": 2,
            "monthly_rollup": 3,
            "yearly_rollup": 4,
        }
        rollup_level = rollup_levels.get(rollup_type, 0)

        # Create rollup entry
        rollup_id = self.add_entry(
            content=rollup_content,
            entry_type=rollup_type,
            thread_id=thread_id,
            timestamp=period_end,
            metadata={
                "child_count": len(child_entries),
                "period_start": period_start,
                "period_end": period_end,
            },
            rollup_level=rollup_level,
        )

        # Update parent_id references for child entries
        if parent_ids:
            conn = self.get_connection(thread_id)
            try:
                for pid in parent_ids:
                    conn.execute("""
                        UPDATE journal_entries
                        SET parent_id = ?
                        WHERE id = ?
                    """, (rollup_id, pid))
                conn.commit()
            finally:
                conn.close()

        return rollup_id

    def get_rollup_hierarchy(
        self,
        thread_id: str,
        timestamp: str | None = None,
    ) -> dict[str, list[dict]]:
        """
        Get rollup hierarchy for a given time.

        Returns:
            Dict with keys: raw, hourly, weekly, monthly, yearly
        """
        hierarchy = {
            "raw": [],
            "hourly": [],
            "weekly": [],
            "monthly": [],
            "yearly": [],
        }

        # TODO: Implement full hierarchy retrieval
        # For now, return empty structure
        return hierarchy

    def get_retention_config(self) -> dict[str, int]:
        """
        Get retention configuration from settings.

        Returns:
            Dict with retention periods for each rollup level (in days)
        """
        from executive_assistant.config import settings

        return {
            "hourly": settings.JOURNAL_RETENTION_HOURLY,
            "weekly": settings.JOURNAL_RETENTION_WEEKLY,
            "monthly": settings.JOURNAL_RETENTION_MONTHLY,
            "yearly": settings.JOURNAL_RETENTION_YEARLY,
        }


_journal_storage = JournalStorage()


def get_journal_storage() -> JournalStorage:
    return _journal_storage
