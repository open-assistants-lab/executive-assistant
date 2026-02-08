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
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id

logger = logging.getLogger(__name__)


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

    @staticmethod
    def _resolve_thread_id(thread_id: str | None = None) -> str:
        if thread_id is None:
            thread_id = get_thread_id()
        if thread_id is None:
            raise ValueError("No thread_id provided or in context")
        return thread_id

    @staticmethod
    def _row_to_instinct(row: sqlite3.Row) -> dict[str, Any]:
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

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the SQLite database path for the current thread."""
        thread_id = self._resolve_thread_id(thread_id)

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

        thread_id = self._resolve_thread_id(thread_id)

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
        status: str | None = "enabled",
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
        thread_id = self._resolve_thread_id(thread_id)

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
                instinct = self._row_to_instinct(row)

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
        thread_id = self._resolve_thread_id(thread_id)

        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                "SELECT * FROM instincts WHERE id = ? AND thread_id = ?",
                (instinct_id, thread_id),
            ).fetchone()

            if not row:
                return None

            return self._row_to_instinct(row)
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
        thread_id = self._resolve_thread_id(thread_id)

        conn = self.get_connection(thread_id)
        try:
            # Get current confidence
            row = conn.execute(
                "SELECT confidence FROM instincts WHERE id = ? AND thread_id = ?",
                (instinct_id, thread_id),
            ).fetchone()

            if not row:
                return False

            old_confidence = row["confidence"]
            new_confidence = max(0.0, min(1.0, old_confidence + delta))

            # Update confidence
            conn.execute("""
                UPDATE instincts
                SET confidence = ?, updated_at = ?
                WHERE id = ? AND thread_id = ?
            """, (new_confidence, _utc_now(), instinct_id, thread_id))

            # Auto-disable if confidence too low
            if new_confidence < 0.2:
                conn.execute("""
                    UPDATE instincts
                    SET status = 'disabled', updated_at = ?
                    WHERE id = ? AND thread_id = ?
                """, (_utc_now(), instinct_id, thread_id))

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

        thread_id = self._resolve_thread_id(thread_id)

        conn = self.get_connection(thread_id)
        try:
            cursor = conn.execute("""
                UPDATE instincts
                SET status = ?, updated_at = ?
                WHERE id = ? AND thread_id = ?
            """, (status, _utc_now(), instinct_id, thread_id))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_instinct(self, instinct_id: str, thread_id: str | None = None) -> bool:
        """Delete an instinct by ID."""
        thread_id = self._resolve_thread_id(thread_id)

        conn = self.get_connection(thread_id)
        try:
            cursor = conn.execute(
                "DELETE FROM instincts WHERE id = ? AND thread_id = ?",
                (instinct_id, thread_id),
            )
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
            thread_id = self._resolve_thread_id(thread_id)

            conn = self.get_connection(thread_id)
            try:
                conn.execute("""
                    UPDATE instincts
                    SET confidence = ?, updated_at = ?
                    WHERE id = ? AND thread_id = ?
                """, (new_confidence, _utc_now(), instinct_id, thread_id))
                conn.commit()
            finally:
                conn.close()

        return new_confidence

    def reinforce_instinct(
        self,
        instinct_id: str,
        thread_id: str | None = None,
        confidence_boost: float = 0.05,
    ) -> None:
        """Record that an instinct was triggered and relevant."""
        instinct = self.get_instinct(instinct_id, thread_id)
        if not instinct:
            return

        now = _utc_now()

        thread_id = self._resolve_thread_id(thread_id)
        bounded_boost = max(0.0, min(1.0, confidence_boost))

        conn = self.get_connection(thread_id)
        try:
            # Update metadata
            occurrence_count = instinct["metadata"].get("occurrence_count", 0) + 1

            conn.execute("""
                UPDATE instincts
                SET occurrence_count = ?,
                    last_triggered = ?,
                    confidence = MIN(1.0, confidence + ?),
                    updated_at = ?
                WHERE id = ? AND thread_id = ?
            """, (occurrence_count, now, bounded_boost, now, instinct_id, thread_id))

            conn.commit()
        finally:
            conn.close()

    def _update_snapshot(self, instinct: dict[str, Any], thread_id: str | None = None) -> None:
        """Compatibility upsert used by observer/calibrator flows."""
        thread_id = self._resolve_thread_id(thread_id)
        instinct_id = instinct.get("id")
        if not instinct_id:
            raise ValueError("instinct must include an id")

        metadata = instinct.get("metadata", {})
        now = _utc_now()

        source = instinct.get("source", "session-observation")
        if source not in _ALLOWED_SOURCES:
            source = "session-observation"

        status = instinct.get("status", "enabled")
        if status not in ("enabled", "disabled"):
            status = "enabled"

        confidence = max(0.0, min(1.0, float(instinct.get("confidence", 0.5))))

        conn = self.get_connection(thread_id)
        try:
            conn.execute(
                """
                INSERT INTO instincts (
                    id, thread_id, trigger, action, domain, source, confidence, status,
                    occurrence_count, success_rate, last_triggered, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    trigger=excluded.trigger,
                    action=excluded.action,
                    domain=excluded.domain,
                    source=excluded.source,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    occurrence_count=excluded.occurrence_count,
                    success_rate=excluded.success_rate,
                    last_triggered=excluded.last_triggered,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at
                """,
                (
                    instinct_id,
                    thread_id,
                    instinct.get("trigger", ""),
                    instinct.get("action", ""),
                    instinct.get("domain", "workflow"),
                    source,
                    confidence,
                    status,
                    int(metadata.get("occurrence_count", 0) or 0),
                    float(metadata.get("success_rate", 1.0) or 1.0),
                    metadata.get("last_triggered"),
                    instinct.get("created_at", now),
                    instinct.get("updated_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_applicable_instincts(
        self,
        context: str,
        thread_id: str | None = None,
        max_count: int = 5,
    ) -> list[dict[str, Any]]:
        instincts = self.list_instincts(
            status="enabled",
            min_confidence=0.5,
            thread_id=thread_id,
        )
        context_lower = (context or "").lower()
        if not context_lower:
            return instincts[:max_count]

        applicable: list[dict[str, Any]] = []
        for instinct in instincts:
            trigger_words = instinct["trigger"].lower().split()
            if any(word in context_lower for word in trigger_words if len(word) > 3):
                applicable.append(instinct)

        applicable.sort(key=lambda x: x["confidence"], reverse=True)
        return applicable[:max_count]

    def get_stale_instincts(
        self,
        thread_id: str | None = None,
        days_since_trigger: int = 30,
        min_confidence: float = 0.5,
    ) -> list[dict[str, Any]]:
        instincts = self.list_instincts(
            thread_id=thread_id,
            min_confidence=min_confidence,
            apply_decay=False,
        )
        stale: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for instinct in instincts:
            last_triggered_str = instinct.get("metadata", {}).get("last_triggered")
            if not last_triggered_str:
                enriched = dict(instinct)
                enriched["days_since_trigger"] = 999
                stale.append(enriched)
                continue

            try:
                last_triggered = datetime.fromisoformat(last_triggered_str)
                days = (now - last_triggered).days
                if days >= days_since_trigger:
                    enriched = dict(instinct)
                    enriched["days_since_trigger"] = days
                    stale.append(enriched)
            except Exception:
                enriched = dict(instinct)
                enriched["days_since_trigger"] = 999
                stale.append(enriched)

        return stale

    def cleanup_stale_instincts(
        self,
        thread_id: str | None = None,
        days_since_trigger: int = 60,
        min_confidence: float = 0.4,
    ) -> int:
        stale = self.get_stale_instincts(
            thread_id=thread_id,
            days_since_trigger=days_since_trigger,
            min_confidence=min_confidence,
        )
        removed_count = 0

        for instinct in stale:
            occurrence_count = instinct.get("metadata", {}).get("occurrence_count", 0)
            if occurrence_count < 3 and self.delete_instinct(instinct["id"], thread_id):
                removed_count += 1
                logger.info(
                    "Cleaned stale instinct: %s (occurrence_count=%s, days_since_trigger=%s)",
                    instinct["action"][:50],
                    occurrence_count,
                    instinct.get("days_since_trigger", 0),
                )

        return removed_count

    @staticmethod
    def _calculate_similarity(instinct_a: dict[str, Any], instinct_b: dict[str, Any]) -> float:
        text_a = f"{instinct_a['trigger']} {instinct_a['action']}"
        text_b = f"{instinct_b['trigger']} {instinct_b['action']}"

        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def find_similar_instincts(
        self,
        thread_id: str | None = None,
        similarity_threshold: float = 0.8,
    ) -> list[list[dict[str, Any]]]:
        instincts = self.list_instincts(
            thread_id=thread_id,
            apply_decay=False,
        )
        clusters: list[list[dict[str, Any]]] = []
        used: set[int] = set()

        for i, instinct_a in enumerate(instincts):
            if i in used:
                continue
            cluster = [instinct_a]
            used.add(i)
            for j, instinct_b in enumerate(instincts[i + 1:], start=i + 1):
                if j in used:
                    continue
                sim = self._calculate_similarity(instinct_a, instinct_b)
                if sim >= similarity_threshold:
                    cluster.append(instinct_b)
                    used.add(j)
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    def merge_similar_instincts(
        self,
        thread_id: str | None = None,
        similarity_threshold: float = 0.8,
    ) -> dict[str, int]:
        clusters = self.find_similar_instincts(
            thread_id=thread_id,
            similarity_threshold=similarity_threshold,
        )
        merged_count = 0
        boosted_count = 0

        for cluster in clusters:
            cluster.sort(key=lambda x: x["confidence"], reverse=True)
            keeper = cluster[0]

            for instinct in cluster[1:]:
                boost = instinct["confidence"] * 0.3
                if boost > 0:
                    self.reinforce_instinct(
                        keeper["id"],
                        thread_id=thread_id,
                        confidence_boost=boost,
                    )
                    boosted_count += 1
                if self.delete_instinct(instinct["id"], thread_id=thread_id):
                    merged_count += 1

        return {
            "clusters_found": len(clusters),
            "instincts_merged": merged_count,
            "instincts_boosted": boosted_count,
        }

    def export_instincts(
        self,
        thread_id: str | None = None,
        min_confidence: float = 0.0,
        include_metadata: bool = True,
    ) -> str:
        instincts = self.list_instincts(
            thread_id=thread_id,
            status=None,
            min_confidence=min_confidence,
            apply_decay=False,
        )
        payload: dict[str, Any] = {
            "version": "2.0",
            "storage": "sqlite",
            "exported_at": _utc_now(),
            "thread_id": thread_id,
            "total_instincts": len(instincts),
            "instincts": [],
        }

        for instinct in instincts:
            entry = {
                "id": instinct["id"],
                "trigger": instinct["trigger"],
                "action": instinct["action"],
                "domain": instinct["domain"],
                "source": instinct["source"],
                "confidence": instinct["confidence"],
                "status": instinct["status"],
                "created_at": instinct["created_at"],
                "updated_at": instinct["updated_at"],
            }
            if include_metadata:
                entry["metadata"] = instinct.get("metadata", {})
            payload["instincts"].append(entry)

        return json.dumps(payload, indent=2)

    def import_instincts(
        self,
        json_data: str,
        thread_id: str | None = None,
        merge_strategy: str = "merge",
        confidence_boost: float = 0.0,
    ) -> dict[str, int]:
        if merge_strategy not in {"replace", "merge"}:
            raise ValueError("merge_strategy must be 'replace' or 'merge'")

        data = json.loads(json_data)
        instincts = data.get("instincts")
        if not isinstance(instincts, list):
            raise ValueError("Invalid import format: expected 'instincts' list")

        target_thread = self._resolve_thread_id(thread_id)

        if merge_strategy == "replace":
            conn = self.get_connection(target_thread)
            try:
                conn.execute("DELETE FROM instincts WHERE thread_id = ?", (target_thread,))
                conn.commit()
            finally:
                conn.close()

        existing = self.list_instincts(
            thread_id=target_thread,
            status=None,
            apply_decay=False,
        )
        existing_by_key = {(i["trigger"], i["action"]): i for i in existing}

        imported_count = 0
        skipped_count = 0
        merged_count = 0

        for item in instincts:
            if not isinstance(item, dict):
                skipped_count += 1
                continue

            trigger = item.get("trigger")
            action = item.get("action")
            domain = item.get("domain")
            if not trigger or not action or not domain:
                skipped_count += 1
                continue

            base_confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, base_confidence + confidence_boost))
            key = (trigger, action)

            if merge_strategy == "merge" and key in existing_by_key:
                existing_instinct = existing_by_key[key]
                if confidence > existing_instinct["confidence"]:
                    delta = confidence - existing_instinct["confidence"]
                    self.reinforce_instinct(
                        existing_instinct["id"],
                        thread_id=target_thread,
                        confidence_boost=delta,
                    )
                    merged_count += 1
                else:
                    skipped_count += 1
                continue

            instinct_id = self.create_instinct(
                trigger=trigger,
                action=action,
                domain=domain,
                source=item.get("source", "import"),
                confidence=confidence,
                thread_id=target_thread,
            )
            imported_count += 1

            metadata = item.get("metadata") or {}
            if metadata or item.get("status") or item.get("created_at") or item.get("updated_at"):
                created = self.get_instinct(instinct_id, thread_id=target_thread)
                if created:
                    created["metadata"].update(metadata)
                    if item.get("status"):
                        created["status"] = item["status"]
                    if item.get("created_at"):
                        created["created_at"] = item["created_at"]
                    if item.get("updated_at"):
                        created["updated_at"] = item["updated_at"]
                    self._update_snapshot(created, thread_id=target_thread)

        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "merged": merged_count,
            "total": imported_count + merged_count,
        }


_instinct_storage_sqlite = InstinctStorageSQLite()


def get_instinct_storage_sqlite() -> InstinctStorageSQLite:
    return _instinct_storage_sqlite
