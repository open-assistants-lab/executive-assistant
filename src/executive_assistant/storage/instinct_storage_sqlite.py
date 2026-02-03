"""SQLite-based instincts storage with migration support.

This module provides the SQLite implementation of instincts storage,
migrating from the JSON-based system.

Migration Path:
- OLD: instincts.jsonl + instincts.snapshot.json
- NEW: instincts.db (SQLite)

Benefits:
- Consistent with other pillars (memory, journal, goals)
- SQL queries for better filtering/sorting
- Single file per user
- Better performance for large datasets
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


# Allowed instinct domains (same as JSON version)
_ALLOWED_DOMAINS = {
    "communication",
    "format",
    "workflow",
    "tool_selection",
    "verification",
    "timing",
    "emotional_state",
    "learning_style",
    "expertise",
}

# Allowed sources (same as JSON version)
_ALLOWED_SOURCES = {
    "session-observation",
    "explicit-user",
    "repetition-confirmed",
    "correction-detected",
    "preference-expressed",
    "profile-preset",
    "custom-profile",
    "import",
    "frustration-detected",
    "confusion-detected",
    "satisfaction-detected",
    "expertise-detected",
    "domain-detected",
    "urgency-detected",
    "learning-detected",
    "exploration-detected",
}


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class InstinctStorageSQLite:
    """SQLite-based storage for instinct behavioral patterns."""

    # Temporal decay configuration (same as JSON version)
    DECAY_CONFIG = {
        "half_life_days": 30,
        "min_confidence": 0.3,
        "reinforcement_reset": True,
    }

    def __init__(self) -> None:
        pass

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the SQLite database path for the current thread."""
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided or in context")

        instincts_dir = settings.get_thread_instincts_dir(thread_id)
        instincts_dir.mkdir(parents=True, exist_ok=True)
        return instincts_dir / "instincts.db"

    def get_connection(self, thread_id: str | None = None) -> sqlite3.Connection:
        """Get a SQLite connection for the current context."""
        db_path = self._get_db_path(thread_id)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables, indexes, and FTS."""
        # Main instincts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instincts (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                domain TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'enabled',

                occurrence_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                last_triggered TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instincts_thread ON instincts(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instincts_domain ON instincts(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instincts_status ON instincts(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instincts_confidence ON instincts(confidence)")

        # Full-text search for pattern matching
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS instincts_fts USING fts5(
                    trigger,
                    action,
                    content='instincts',
                    content_rowid='rowid'
                )
            """)

            # Triggers for FTS sync
            conn.executescript("""
                CREATE TRIGGER IF NOT EXISTS instincts_ai AFTER INSERT ON instincts BEGIN
                    INSERT INTO instincts_fts(rowid, trigger, action) VALUES (new.rowid, new.trigger, new.action);
                END;
                CREATE TRIGGER IF NOT EXISTS instincts_ad AFTER DELETE ON instincts BEGIN
                    INSERT INTO instincts_fts(instincts_fts, rowid, trigger, action) VALUES('delete', old.rowid, old.trigger, old.action);
                END;
                CREATE TRIGGER IF NOT EXISTS instincts_au AFTER UPDATE OF trigger, action ON instincts BEGIN
                    INSERT INTO instincts_fts(instincts_fts, rowid, trigger, action) VALUES('delete', old.rowid, old.trigger, old.action);
                    INSERT INTO instincts_fts(rowid, trigger, action) VALUES (new.rowid, new.trigger, new.action);
                END;
            """)
        except sqlite3.OperationalError:
            # FTS5 not available
            pass

        conn.commit()

    def _validate_domain(self, domain: str) -> None:
        if domain not in _ALLOWED_DOMAINS:
            raise ValueError(
                f"Invalid domain '{domain}'. Allowed: {', '.join(sorted(_ALLOWED_DOMAINS))}"
            )

    def _validate_source(self, source: str) -> None:
        if source not in _ALLOWED_SOURCES:
            raise ValueError(
                f"Invalid source '{source}'. Allowed: {', '.join(sorted(_ALLOWED_SOURCES))}"
            )

    # ========================================================================
    # CREATE: Create new instinct
    # ========================================================================

    def create_instinct(
        self,
        trigger: str,
        action: str,
        domain: str,
        source: str = "session-observation",
        confidence: float = 0.5,
        thread_id: str | None = None,
    ) -> str:
        """
        Create a new instinct entry.

        Args:
            trigger: When this instinct applies
            action: What to do
            domain: Category of instinct
            source: How this instinct was learned
            confidence: Initial confidence score (0.0 to 1.0)
            thread_id: Thread identifier

        Returns:
            Instinct ID
        """
        self._validate_domain(domain)
        self._validate_source(source)

        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        instinct_id = str(uuid.uuid4())
        now = _utc_now()

        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            conn.execute("""
                INSERT INTO instincts (
                    id, thread_id, trigger, action, domain, source,
                    confidence, status, occurrence_count, success_rate,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instinct_id, thread_id, trigger, action, domain, source,
                confidence, 'enabled', 0, 1.0, now, now
            ))
            conn.commit()
            return instinct_id
        finally:
            conn.close()

    # ========================================================================
    # QUERY: Retrieve instincts
    # ========================================================================

    def list_instincts(
        self,
        domain: str | None = None,
        status: str = "enabled",
        min_confidence: float = 0.0,
        thread_id: str | None = None,
        apply_decay: bool = True,
    ) -> list[dict[str, Any]]:
        """
        List instincts with optional filtering.

        Args:
            domain: Filter by domain
            status: Filter by status (default: "enabled")
            min_confidence: Minimum confidence score
            thread_id: Thread identifier
            apply_decay: Whether to apply temporal decay (default: True)

        Returns:
            List of instincts
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Build query
            query = "SELECT * FROM instincts WHERE thread_id = ?"
            params = [thread_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            if domain:
                query += " AND domain = ?"
                params.append(domain)

            query += " AND confidence >= ?"
            params.append(min_confidence)

            query += " ORDER BY confidence DESC"

            rows = conn.execute(query, params).fetchall()

            results = []
            for row in rows:
                instinct = {
                    "id": row["id"],
                    "trigger": row["trigger"],
                    "action": row["action"],
                    "domain": row["domain"],
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                    "metadata": {
                        "occurrence_count": row["occurrence_count"],
                        "success_rate": row["success_rate"],
                        "last_triggered": row["last_triggered"],
                    },
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }

                # Apply temporal decay if enabled
                if apply_decay:
                    try:
                        adjusted_confidence = self.adjust_confidence_for_decay(
                            instinct["id"], thread_id
                        )
                        instinct["confidence"] = adjusted_confidence
                    except Exception:
                        # If decay fails, use original confidence
                        pass

                results.append(instinct)

            return results
        finally:
            conn.close()

    def get_instinct(self, instinct_id: str, thread_id: str | None = None) -> dict | None:
        """Get a specific instinct by ID."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                "SELECT * FROM instincts WHERE id = ?",
                (instinct_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "trigger": row["trigger"],
                "action": row["action"],
                "domain": row["domain"],
                "source": row["source"],
                "confidence": row["confidence"],
                "status": row["status"],
                "metadata": {
                    "occurrence_count": row["occurrence_count"],
                    "success_rate": row["success_rate"],
                    "last_triggered": row["last_triggered"],
                },
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    # ========================================================================
    # UPDATE: Adjust confidence and status
    # ========================================================================

    def adjust_confidence(
        self,
        instinct_id: str,
        delta: float,
        thread_id: str | None = None,
    ) -> bool:
        """
        Adjust instinct confidence up or down.

        Args:
            instinct_id: Instinct identifier
            delta: Confidence adjustment
            thread_id: Thread identifier

        Returns:
            True if instinct exists, False otherwise
        """
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Get current confidence
            row = conn.execute(
                "SELECT confidence FROM instincts WHERE id = ?",
                (instinct_id,)
            ).fetchone()

            if not row:
                return False

            old_confidence = row["confidence"]
            new_confidence = max(0.0, min(1.0, old_confidence + delta))

            # Update confidence
            conn.execute("""
                UPDATE instincts
                SET confidence = ?, updated_at = ?
                WHERE id = ?
            """, (new_confidence, _utc_now(), instinct_id))

            # Auto-disable if confidence too low
            if new_confidence < 0.2:
                conn.execute("""
                    UPDATE instincts
                    SET status = 'disabled', updated_at = ?
                    WHERE id = ?
                """, (_utc_now(), instinct_id))

            conn.commit()
            return True
        finally:
            conn.close()

    def set_instinct_status(
        self,
        instinct_id: str,
        status: str,
        thread_id: str | None = None,
    ) -> bool:
        """Set instinct status (enabled/disabled)."""
        if status not in ("enabled", "disabled"):
            raise ValueError(f"Status must be 'enabled' or 'disabled', got '{status}'")

        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            cursor = conn.execute("""
                UPDATE instincts
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, _utc_now(), instinct_id))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_instinct(self, instinct_id: str, thread_id: str | None = None) -> bool:
        """Delete an instinct by ID."""
        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            cursor = conn.execute("DELETE FROM instincts WHERE id = ?", (instinct_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========================================================================
    # TEMPORAL DECAY: Confidence fades over time without reinforcement
    # ========================================================================

    def adjust_confidence_for_decay(
        self,
        instinct_id: str,
        thread_id: str | None = None,
    ) -> float:
        """Adjust instinct confidence based on age and lack of reinforcement."""
        instinct = self.get_instinct(instinct_id, thread_id)

        if not instinct:
            raise ValueError(f"Instinct {instinct_id} not found")

        created_at = datetime.fromisoformat(instinct["created_at"])
        days_old = (datetime.now(timezone.utc) - created_at).days

        metadata = instinct.get("metadata", {})
        occurrence_count = metadata.get("occurrence_count", 0)

        # Don't decay heavily reinforced instincts
        if occurrence_count >= 5:
            return instinct["confidence"]

        # Calculate decay
        half_life = self.DECAY_CONFIG["half_life_days"]
        min_conf = self.DECAY_CONFIG["min_confidence"]

        # Exponential decay
        decay_factor = 0.5 ** (days_old / half_life)
        new_confidence = max(min_conf, instinct["confidence"] * decay_factor)

        # Update if significantly changed
        if abs(new_confidence - instinct["confidence"]) > 0.05:
            if thread_id is None:
                thread_id = get_thread_id()

            conn = self.get_connection(thread_id)
            try:
                conn.execute("""
                    UPDATE instincts
                    SET confidence = ?, updated_at = ?
                    WHERE id = ?
                """, (new_confidence, _utc_now(), instinct_id))
                conn.commit()
            finally:
                conn.close()

        return new_confidence

    def reinforce_instinct(
        self,
        instinct_id: str,
        thread_id: str | None = None,
    ) -> None:
        """Record that an instinct was triggered and relevant."""
        instinct = self.get_instinct(instinct_id, thread_id)
        if not instinct:
            return

        now = _utc_now()

        if thread_id is None:
            thread_id = get_thread_id()

        conn = self.get_connection(thread_id)
        try:
            # Update metadata
            occurrence_count = instinct["metadata"].get("occurrence_count", 0) + 1

            conn.execute("""
                UPDATE instincts
                SET occurrence_count = ?,
                    last_triggered = ?,
                    confidence = MIN(1.0, confidence + 0.05),
                    updated_at = ?
                WHERE id = ?
            """, (occurrence_count, now, now, instinct_id))

            conn.commit()
        finally:
            conn.close()


_instinct_storage_sqlite = InstinctStorageSQLite()


def get_instinct_storage_sqlite() -> InstinctStorageSQLite:
    return _instinct_storage_sqlite
