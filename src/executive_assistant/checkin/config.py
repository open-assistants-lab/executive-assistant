"""Check-in configuration and storage.

Manages per-user check-in configuration stored in TDB.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import time
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


def _get_checkin_db_path(thread_id: str | None = None) -> Path:
    """Get the check-in TDB database path."""
    if thread_id is None:
        thread_id = get_thread_id()

    if thread_id is None:
        raise ValueError("No thread_id provided or in context")

    # Store in instincts directory (along with journal, goals)
    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    return instincts_dir / "checkin.db"


def get_checkin_connection(thread_id: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection for check-in config."""
    db_path = _get_checkin_db_path(thread_id)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create check-in config table."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkin_config (
            thread_id TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            every TEXT DEFAULT '30m',
            lookback TEXT DEFAULT '24h',
            active_hours_start TEXT DEFAULT '09:00',
            active_hours_end TEXT DEFAULT '18:00',
            active_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
            last_checkin TEXT,
            updated_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


class CheckinConfig:
    """Check-in configuration for a user."""

    def __init__(
        self,
        thread_id: str,
        enabled: bool = True,  # Enabled by default
        every: str = "30m",
        lookback: str = "24h",
        active_hours_start: str | None = "09:00",
        active_hours_end: str | None = "18:00",
        active_days: str = "Mon,Tue,Wed,Thu,Fri",
        last_checkin: str | None = None,
    ):
        self.thread_id = thread_id
        self.enabled = enabled
        self.every = every
        self.lookback = lookback
        self.active_hours_start = active_hours_start
        self.active_hours_end = active_hours_end
        self.active_days = active_days
        self.last_checkin = last_checkin

    def is_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        from datetime import datetime

        now = datetime.now()
        current_day = now.strftime("%a")
        current_time = now.time()

        # Check if today is an active day
        if current_day not in self.active_days.split(","):
            return False

        # Check if within active hours
        if self.active_hours_start and self.active_hours_end:
            start = time.fromisoformat(self.active_hours_start)
            end = time.fromisoformat(self.active_hours_end)
            if not (start <= current_time <= end):
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "thread_id": self.thread_id,
            "enabled": self.enabled,
            "every": self.every,
            "lookback": self.lookback,
            "active_hours_start": self.active_hours_start,
            "active_hours_end": self.active_hours_end,
            "active_days": self.active_days,
            "last_checkin": self.last_checkin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckinConfig":
        """Create from dictionary."""
        return cls(
            thread_id=data["thread_id"],
            enabled=bool(data["enabled"]),
            every=data["every"],
            lookback=data["lookback"],
            active_hours_start=data.get("active_hours_start"),
            active_hours_end=data.get("active_hours_end"),
            active_days=data["active_days"],
            last_checkin=data.get("last_checkin"),
        )


def get_checkin_config(
    thread_id: str | None = None,
    *,
    persist_default: bool = False,
) -> CheckinConfig:
    """Get check-in config for a user.

    Args:
        thread_id: Thread identifier

    Returns:
        CheckinConfig object (default config if not exists)
    """
    if thread_id is None:
        thread_id = get_thread_id()

    conn = get_checkin_connection(thread_id)
    try:
        row = conn.execute(
            "SELECT * FROM checkin_config WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()

        if not row:
            # Return default config (enabled by default).
            # Optionally persist the default row so background jobs can discover it.
            default_config = CheckinConfig(
                thread_id=thread_id,
                enabled=True,  # Enabled by default
                every="30m",
                lookback="24h",
                active_hours_start="09:00",
                active_hours_end="18:00",
                active_days="Mon,Tue,Wed,Thu,Fri",
            )
            if persist_default:
                save_checkin_config(default_config)
            return default_config

        return CheckinConfig(
            thread_id=row["thread_id"],
            enabled=bool(row["enabled"]),
            every=row["every"],
            lookback=row["lookback"],
            active_hours_start=row["active_hours_start"],
            active_hours_end=row["active_hours_end"],
            active_days=row["active_days"],
            last_checkin=row["last_checkin"],
        )
    finally:
        conn.close()


def save_checkin_config(config: CheckinConfig) -> None:
    """Save check-in config for a user.

    Args:
        config: CheckinConfig object
    """
    from datetime import timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = get_checkin_connection(config.thread_id)
    try:
        conn.execute("""
            INSERT INTO checkin_config (
                thread_id, enabled, every, lookback,
                active_hours_start, active_hours_end, active_days,
                last_checkin, updated_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                enabled = excluded.enabled,
                every = excluded.every,
                lookback = excluded.lookback,
                active_hours_start = excluded.active_hours_start,
                active_hours_end = excluded.active_hours_end,
                active_days = excluded.active_days,
                last_checkin = excluded.last_checkin,
                updated_at = excluded.updated_at
        """, (
            config.thread_id,
            1 if config.enabled else 0,
            config.every,
            config.lookback,
            config.active_hours_start,
            config.active_hours_end,
            config.active_days,
            config.last_checkin,
            now,
            now,
        ))
        conn.commit()
    finally:
        conn.close()


def update_last_checkin(thread_id: str, timestamp: str) -> None:
    """Update the last check-in timestamp.

    Args:
        thread_id: Thread identifier
        timestamp: ISO timestamp of last check-in
    """
    from datetime import timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = get_checkin_connection(thread_id)
    try:
        conn.execute("""
            UPDATE checkin_config
            SET last_checkin = ?, updated_at = ?
            WHERE thread_id = ?
        """, (timestamp, now, thread_id))
        conn.commit()
    finally:
        conn.close()


def get_users_with_checkin_enabled() -> list[str]:
    """Get all thread_ids with check-in enabled.

    This would need to scan all user directories to find enabled check-ins.
    For now, return empty list (can be optimized later with indexing).

    Returns:
        List of thread_ids with check-in enabled
    """
    users: set[str] = set()
    users_root = settings.USERS_ROOT

    if not users_root.exists():
        return []

    # Scan per-user check-in DBs: data/users/{thread_id}/instincts/checkin.db
    for db_path in users_root.glob("*/instincts/checkin.db"):
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT thread_id
                FROM checkin_config
                WHERE enabled = 1
                LIMIT 1
                """
            ).fetchone()
            if row and row["thread_id"]:
                users.add(str(row["thread_id"]))
        except Exception:
            # Ignore malformed or missing DB/schema; continue scanning.
            continue
        finally:
            if conn is not None:
                conn.close()

    return sorted(users)


# Need to import datetime for the functions
from datetime import datetime
