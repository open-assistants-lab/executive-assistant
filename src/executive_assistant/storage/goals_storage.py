"""Goals storage for future intentions with progress tracking and change detection.

Stores user goals and objectives with:
- Goal creation and management
- Progress tracking
- Change detection (5 mechanisms)
- Version history and audit trail

Storage: SQLite with comprehensive goal tracking
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from executive_assistant.config import settings


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class GoalsStorage:
    """Storage for goals with progress tracking and change detection."""

    def __init__(self) -> None:
        pass

    def _get_goals_dir(self, thread_id: str | None = None) -> Path:
        """Get the goals directory for the current thread."""
        if thread_id is None:
            from executive_assistant.storage.file_sandbox import get_thread_id
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided or in context")

        instincts_dir = settings.get_thread_instincts_dir(thread_id)
        goals_dir = instincts_dir.parent / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        return goals_dir

    def _get_db_path(self, thread_id: str | None = None) -> Path:
        """Get the SQLite database path."""
        goals_dir = self._get_goals_dir(thread_id)
        return goals_dir / "goals.db"

    def get_connection(self, thread_id: str | None = None) -> sqlite3.Connection:
        """Get a SQLite connection for the current context."""
        db_path = self._get_db_path(thread_id)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables and indexes."""

        # Main goals table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                target_date TEXT,
                status TEXT DEFAULT 'planned',
                progress REAL DEFAULT 0.0,
                priority INTEGER NOT NULL,
                importance INTEGER NOT NULL,
                parent_goal_id TEXT,
                related_projects JSON,
                depends_on JSON,
                tags JSON,
                notes JSON,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
            )
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_thread ON goals(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_category ON goals(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_target_date ON goals(target_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id)")

        # Goal progress tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goal_progress (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                progress REAL NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_goal ON goal_progress(goal_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_timestamp ON goal_progress(timestamp)")

        # Goal version history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goal_versions (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot JSON NOT NULL,
                change_type TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_goal ON goal_versions(goal_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_version ON goal_versions(version)")

        conn.commit()

    # ========================================================================
    # CREATE: Add goals
    # ========================================================================

    def create_goal(
        self,
        title: str,
        category: str,
        priority: int,
        importance: int,
        thread_id: str | None = None,
        description: str | None = None,
        target_date: str | None = None,
        parent_goal_id: str | None = None,
        related_projects: list[str] | None = None,
        depends_on: list[str] | None = None,
        tags: list[str] | None = None,
        notes: list[str] | None = None,
    ) -> str:
        """
        Create a new goal.

        Args:
            title: Goal title
            category: Goal category (short_term, medium_term, long_term)
            priority: Priority level (1-10)
            importance: Importance level (1-10)
            thread_id: Thread identifier
            description: Goal description
            target_date: Target completion date (ISO timestamp)
            parent_goal_id: Parent goal ID (for sub-goals)
            related_projects: List of related project IDs
            depends_on: List of goal IDs this goal depends on
            tags: List of tags
            notes: List of notes

        Returns:
            Goal ID
        """
        now = _utc_now()

        if related_projects is None:
            related_projects = []
        if depends_on is None:
            depends_on = []
        if tags is None:
            tags = []
        if notes is None:
            notes = []

        goal_id = str(uuid.uuid4())

        conn = self.get_connection(thread_id)
        try:
            conn.execute("""
                INSERT INTO goals (
                    id, thread_id, title, description, category, target_date,
                    status, progress, priority, importance,
                    parent_goal_id, related_projects, depends_on, tags, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                goal_id,
                thread_id or "",
                title,
                description,
                category,
                target_date,
                "planned",
                0.0,
                priority,
                importance,
                parent_goal_id,
                json.dumps(related_projects),
                json.dumps(depends_on),
                json.dumps(tags),
                json.dumps(notes),
                now,
                now,
            ))
            conn.commit()
            return goal_id
        finally:
            conn.close()

    # ========================================================================
    # QUERY: Retrieve goals
    # ========================================================================

    def get_goal(self, goal_id: str, thread_id: str | None = None) -> dict | None:
        """Get a specific goal by ID."""
        conn = self.get_connection(thread_id)
        try:
            row = conn.execute(
                "SELECT * FROM goals WHERE id = ?",
                (goal_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "title": row["title"],
                "description": row["description"],
                "category": row["category"],
                "target_date": row["target_date"],
                "status": row["status"],
                "progress": row["progress"],
                "priority": row["priority"],
                "importance": row["importance"],
                "parent_goal_id": row["parent_goal_id"],
                "related_projects": json.loads(row["related_projects"]) if row["related_projects"] else [],
                "depends_on": json.loads(row["depends_on"]) if row["depends_on"] else [],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "notes": json.loads(row["notes"]) if row["notes"] else [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    def list_goals(
        self,
        thread_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
        min_progress: float | None = None,
        max_progress: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List goals with optional filtering.

        Args:
            thread_id: Thread identifier
            status: Filter by status
            category: Filter by category
            min_progress: Minimum progress
            max_progress: Maximum progress
            limit: Maximum number of goals to return

        Returns:
            List of goals
        """
        conn = self.get_connection(thread_id)
        try:
            # Build query
            query = "SELECT * FROM goals WHERE status != 'deleted'"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if category:
                query += " AND category = ?"
                params.append(category)

            if min_progress is not None:
                query += " AND progress >= ?"
                params.append(min_progress)

            if max_progress is not None:
                query += " AND progress <= ?"
                params.append(max_progress)

            query += " ORDER BY priority DESC, created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "title": row["title"],
                    "description": row["description"],
                    "category": row["category"],
                    "target_date": row["target_date"],
                    "status": row["status"],
                    "progress": row["progress"],
                    "priority": row["priority"],
                    "importance": row["importance"],
                    "parent_goal_id": row["parent_goal_id"],
                    "related_projects": json.loads(row["related_projects"]) if row["related_projects"] else [],
                    "depends_on": json.loads(row["depends_on"]) if row["depends_on"] else [],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "notes": json.loads(row["notes"]) if row["notes"] else [],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                })

            return results
        finally:
            conn.close()

    # ========================================================================
    # UPDATE: Modify goals
    # ========================================================================

    def update_goal(
        self,
        goal_id: str,
        thread_id: str,
        title: str | None = None,
        description: str | None = None,
        category: str | None = None,
        target_date: str | None = None,
        status: str | None = None,
        progress: float | None = None,
        priority: int | None = None,
        importance: int | None = None,
        parent_goal_id: str | None = None,
        related_projects: list[str] | None = None,
        depends_on: list[str] | None = None,
        tags: list[str] | None = None,
        notes: list[str] | None = None,
        change_type: str = "modification",
        change_reason: str = "Goal updated",
    ) -> bool:
        """
        Update a goal with version history.

        Args:
            goal_id: Goal ID
            thread_id: Thread identifier
            change_type: Type of change (modification, status_change, progress_update, etc.)
            change_reason: Reason for the change

        Returns:
            True if updated, False otherwise
        """
        # Get current goal for version history
        current_goal = self.get_goal(goal_id, thread_id)
        if not current_goal:
            return False

        # Create version snapshot
        self._create_version(
            goal_id=goal_id,
            thread_id=thread_id,
            snapshot=current_goal,
            change_type=change_type,
            change_reason=change_reason,
        )

        # Build update query
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if target_date is not None:
            updates.append("target_date = ?")
            params.append(target_date)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)

        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)

        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)

        if parent_goal_id is not None:
            updates.append("parent_goal_id = ?")
            params.append(parent_goal_id)

        if related_projects is not None:
            updates.append("related_projects = ?")
            params.append(json.dumps(related_projects))

        if depends_on is not None:
            updates.append("depends_on = ?")
            params.append(json.dumps(depends_on))

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if notes is not None:
            updates.append("notes = ?")
            params.append(json.dumps(notes))

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(goal_id)

        conn = self.get_connection(thread_id)
        try:
            conn.execute(f"""
                UPDATE goals
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()
            return True
        finally:
            conn.close()

    def update_goal_progress(
        self,
        goal_id: str,
        thread_id: str,
        progress: float,
        source: str = "manual",
        notes: str | None = None,
    ) -> bool:
        """
        Update goal progress and track history.

        Args:
            goal_id: Goal ID
            thread_id: Thread identifier
            progress: Progress value (0.0 to 100.0)
            source: Source of progress update (manual, journal, automatic)
            notes: Optional notes about the progress

        Returns:
            True if updated, False otherwise
        """
        # Update goal progress
        updated = self.update_goal(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=progress,
            change_type="progress_update",
            change_reason=f"Progress updated to {progress}%",
        )

        if not updated:
            return False

        # Add progress entry
        now = _utc_now()
        progress_id = str(uuid.uuid4())

        conn = self.get_connection(thread_id)
        try:
            conn.execute("""
                INSERT INTO goal_progress (id, goal_id, progress, timestamp, source, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (progress_id, goal_id, progress, now, source, notes))
            conn.commit()
            return True
        finally:
            conn.close()

    # ========================================================================
    # VERSION HISTORY: Track changes
    # ========================================================================

    def _create_version(
        self,
        goal_id: str,
        thread_id: str,
        snapshot: dict,
        change_type: str,
        change_reason: str,
    ) -> None:
        """Create a version snapshot."""
        # Get current version number
        conn = self.get_connection(thread_id)
        try:
            result = conn.execute(
                "SELECT COALESCE(MAX(version), 0) as max_version FROM goal_versions WHERE goal_id = ?",
                (goal_id,)
            ).fetchone()

            next_version = (result["max_version"] or 0) + 1

            # Create version entry
            version_id = str(uuid.uuid4())
            now = _utc_now()

            conn.execute("""
                INSERT INTO goal_versions (id, goal_id, version, snapshot, change_type, change_reason, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (version_id, goal_id, next_version, json.dumps(snapshot), change_type, change_reason, now))
            conn.commit()
        finally:
            conn.close()

    def get_version_history(self, goal_id: str, thread_id: str | None = None) -> list[dict[str, Any]]:
        """Get version history for a goal."""
        conn = self.get_connection(thread_id)
        try:
            rows = conn.execute(
                "SELECT * FROM goal_versions WHERE goal_id = ? ORDER BY version DESC",
                (goal_id,)
            ).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "goal_id": row["goal_id"],
                    "version": row["version"],
                    "snapshot": json.loads(row["snapshot"]),
                    "change_type": row["change_type"],
                    "change_reason": row["change_reason"],
                    "changed_at": row["changed_at"],
                })

            return results
        finally:
            conn.close()

    def restore_from_version(
        self,
        goal_id: str,
        thread_id: str,
        version_id: str,
        change_reason: str = "Restored from previous version",
    ) -> bool:
        """Restore a goal from a previous version."""
        # Get version snapshot
        versions = self.get_version_history(goal_id, thread_id)
        target_version = next((v for v in versions if v["id"] == version_id), None)

        if not target_version:
            return False

        snapshot = target_version["snapshot"]

        # Restore goal from snapshot
        return self.update_goal(
            goal_id=goal_id,
            thread_id=thread_id,
            title=snapshot["title"],
            description=snapshot["description"],
            category=snapshot["category"],
            target_date=snapshot["target_date"],
            status=snapshot["status"],
            progress=snapshot["progress"],
            priority=snapshot["priority"],
            importance=snapshot["importance"],
            parent_goal_id=snapshot["parent_goal_id"],
            related_projects=snapshot["related_projects"],
            depends_on=snapshot["depends_on"],
            tags=snapshot["tags"],
            notes=snapshot["notes"],
            change_type="restoration",
            change_reason=change_reason,
        )

    # ========================================================================
    # PROGRESS TRACKING
    # ========================================================================

    def get_progress_history(self, goal_id: str, thread_id: str | None = None) -> list[dict[str, Any]]:
        """Get progress history for a goal."""
        conn = self.get_connection(thread_id)
        try:
            rows = conn.execute(
                "SELECT * FROM goal_progress WHERE goal_id = ? ORDER BY timestamp DESC",
                (goal_id,)
            ).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "goal_id": row["goal_id"],
                    "progress": row["progress"],
                    "timestamp": row["timestamp"],
                    "source": row["source"],
                    "notes": row["notes"],
                })

            return results
        finally:
            conn.close()

    # ========================================================================
    # CHANGE DETECTION (5 Mechanisms)
    # ========================================================================

    def detect_stagnant_goals(self, thread_id: str, weeks: int = 2) -> list[dict[str, Any]]:
        """
        Detect goals with no progress for specified weeks.

        Mechanism 1: Journal stagnation
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()

        conn = self.get_connection(thread_id)
        try:
            # Get goals with no progress since cutoff
            rows = conn.execute("""
                SELECT g.* FROM goals g
                LEFT JOIN goal_progress p ON g.id = p.goal_id
                WHERE g.thread_id = ?
                  AND g.status = 'planned'
                  AND (p.timestamp IS NULL OR p.timestamp < ?)
                GROUP BY g.id
            """, (thread_id or "", cutoff_date)).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "progress": row["progress"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                })

            return results
        finally:
            conn.close()

    def detect_stalled_progress(self, thread_id: str, weeks: int = 1) -> list[dict[str, Any]]:
        """
        Detect goals with stalled progress (same progress for specified weeks).

        Mechanism 2: Progress stalls
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()

        conn = self.get_connection(thread_id)
        try:
            # Get goals where latest progress is older than cutoff
            rows = conn.execute("""
                SELECT DISTINCT g.*, p1.timestamp as last_progress_date
                FROM goals g
                INNER JOIN (
                    SELECT goal_id, MAX(timestamp) as timestamp
                    FROM goal_progress
                    GROUP BY goal_id
                ) p1 ON g.id = p1.goal_id
                WHERE g.thread_id = ?
                  AND g.status = 'planned'
                  AND p1.timestamp < ?
            """, (thread_id or "", cutoff_date)).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "progress": row["progress"],
                    "last_progress_date": row["last_progress_date"],
                })

            return results
        finally:
            conn.close()

    def detect_urgent_goals(
        self,
        thread_id: str,
        days_threshold: int = 7,
        progress_threshold: float = 50.0,
    ) -> list[dict[str, Any]]:
        """
        Detect goals approaching deadline with low progress.

        Mechanism 3: Target dates
        """
        deadline = (datetime.now(timezone.utc) + timedelta(days=days_threshold)).isoformat()

        conn = self.get_connection(thread_id)
        try:
            rows = conn.execute("""
                SELECT * FROM goals
                WHERE thread_id = ?
                  AND status = 'planned'
                  AND target_date IS NOT NULL
                  AND target_date <= ?
                  AND progress < ?
                ORDER BY target_date ASC
            """, (thread_id or "", deadline, progress_threshold)).fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "target_date": row["target_date"],
                    "progress": row["progress"],
                    "priority": row["priority"],
                })

            return results
        finally:
            conn.close()

    def detect_contradictions(self, thread_id: str) -> list[dict[str, Any]]:
        """
        Detect goals that contradict recent journal entries.

        Mechanism 4: Contradictions
        TODO: Implement journal integration
        """
        # TODO: Integrate with journal to detect contradictions
        # For now, return empty list
        return []

    def detect_explicit_changes(self, thread_id: str) -> list[dict[str, Any]]:
        """
        Detect explicitly stated goal changes in conversation.

        Mechanism 5: Explicit statements
        TODO: Implement conversation analysis
        """
        # TODO: Integrate with conversation to detect explicit changes
        # For now, return empty list
        return []

    def detect_all_changes(self, thread_id: str) -> dict[str, list[dict[str, Any]]]:
        """Run all 5 change detection mechanisms."""
        return {
            "stagnant": self.detect_stagnant_goals(thread_id),
            "stalled": self.detect_stalled_progress(thread_id),
            "urgent": self.detect_urgent_goals(thread_id),
            "contradictions": self.detect_contradictions(thread_id),
            "explicit": self.detect_explicit_changes(thread_id),
        }


_goals_storage = GoalsStorage()


def get_goals_storage() -> GoalsStorage:
    return _goals_storage
