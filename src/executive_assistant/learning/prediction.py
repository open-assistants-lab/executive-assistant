"""Predict → Prepare pattern: Anticipatory assistance.

Ken learns patterns in your behavior and proactively prepares what you'll need
before you even ask.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.journal_storage import JournalStorage


def _get_prediction_db_path(thread_id: str | None = None) -> str:
    """Get the prediction database path."""
    if thread_id is None:
        thread_id = get_thread_id()

    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    return str(instincts_dir / "predictions.db")


def get_prediction_connection(thread_id: str | None = None):
    """Get SQLite connection for prediction data."""
    import sqlite3

    db_path = _get_prediction_db_path(thread_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn) -> None:
    """Create prediction tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            pattern_description TEXT NOT NULL,
            triggers JSON NOT NULL,
            confidence REAL DEFAULT 0.5,
            occurrences INTEGER DEFAULT 1,
            last_observed TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(thread_id, pattern_type, pattern_description)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            prediction_type TEXT NOT NULL,
            prediction_description TEXT NOT NULL,
            preparation JSON,
            status TEXT DEFAULT 'pending',
            offered_at TEXT,
            user_response TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prepared_data (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            data_type TEXT NOT NULL,
            data_content TEXT NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


async def detect_pattern(
    thread_id: str,
    pattern_type: str,
    pattern_description: str,
    triggers: list[dict[str, Any]],
    confidence: float = 0.5,
) -> str:
    """
    Detect and record a pattern from user behavior.

    Args:
        thread_id: Thread identifier
        pattern_type: Type of pattern (time, task, sequence)
        pattern_description: Human-readable description
        triggers: What triggers this pattern
        confidence: How confident we are (0-1)

    Returns:
        Pattern ID
    """
    import uuid

    now = datetime.now(timezone.utc).isoformat()

    conn = get_prediction_connection(thread_id)
    try:
        # Try to insert or update existing pattern
        try:
            pattern_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO patterns (
                    id, thread_id, pattern_type, pattern_description,
                    triggers, confidence, occurrences, last_observed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                pattern_id,
                thread_id,
                pattern_type,
                pattern_description,
                json.dumps(triggers),
                confidence,
                now,
                now,
            ))
        except Exception:
            # Pattern exists, update it
            conn.execute("""
                UPDATE patterns
                SET occurrences = occurrences + 1,
                    confidence = MIN(confidence + 0.1, 1.0),
                    last_observed = ?
                WHERE thread_id = ? AND pattern_type = ? AND pattern_description = ?
            """, (now, thread_id, pattern_type, pattern_description))

            row = conn.execute(
                "SELECT id FROM patterns WHERE thread_id = ? AND pattern_type = ? AND pattern_description = ?",
                (thread_id, pattern_type, pattern_description)
            ).fetchone()
            pattern_id = row["id"]

        conn.commit()
        return pattern_id
    finally:
        conn.close()


async def check_and_offer_preparation(
    thread_id: str,
    current_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Check if any patterns match current context and offer preparation.

    Args:
        thread_id: Thread identifier
        current_context: Current context (time, task, etc.)

    Returns:
        List of predictions to offer
    """
    predictions = []

    conn = get_prediction_connection(thread_id)
    try:
        # Get all patterns with high confidence
        rows = conn.execute("""
            SELECT * FROM patterns
            WHERE thread_id = ? AND confidence >= 0.7
            ORDER BY confidence DESC, last_observed DESC
        """, (thread_id,)).fetchall()

        for row in rows:
            pattern = dict(row)
            triggers = json.loads(pattern["triggers"])

            # Check if triggers match current context
            if matches_context(triggers, current_context):
                predictions.append({
                    "pattern_id": pattern["id"],
                    "pattern_type": pattern["pattern_type"],
                    "description": pattern["pattern_description"],
                    "confidence": pattern["confidence"],
                    "triggers": triggers,
                })

    finally:
        conn.close()

    return predictions


def matches_context(triggers: list[dict[str, Any]], context: dict[str, Any]) -> bool:
    """Check if triggers match current context.

    Args:
        triggers: List of triggers
        context: Current context

    Returns:
        True if any trigger matches
    """
    from datetime import datetime

    now = datetime.now(timezone.utc)

    for trigger in triggers:
        trigger_type = trigger.get("type")

        if trigger_type == "time":
            # Check time-based triggers
            if "hour" in trigger:
                if now.hour == trigger["hour"]:
                    return True
            if "day_of_week" in trigger:
                if now.strftime("%A") == trigger["day_of_week"]:
                    return True

        elif trigger_type == "task":
            # Check task-based triggers
            if "keyword" in trigger:
                if trigger["keyword"].lower() in context.get("message", "").lower():
                    return True

        elif trigger_type == "sequence":
            # Check sequence-based triggers
            if "previous_task" in trigger:
                if context.get("last_task") == trigger["previous_task"]:
                    return True

    return False


async def create_preparation(
    thread_id: str,
    pattern_id: str,
    preparation_type: str,
    preparation_description: str,
    preparation_data: dict[str, Any],
    ttl_minutes: int = 60,
) -> str:
    """
    Create prepared data for a prediction.

    Args:
        thread_id: Thread identifier
        pattern_id: Associated pattern
        preparation_type: Type of preparation
        preparation_description: What was prepared
        preparation_data: The prepared data
        ttl_minutes: Time-to-live in minutes

    Returns:
        Preparation ID
    """
    import uuid

    preparation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()

    conn = get_prediction_connection(thread_id)
    try:
        conn.execute("""
            INSERT INTO prepared_data (
                id, thread_id, data_type, data_content, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            preparation_id,
            thread_id,
            preparation_type,
            json.dumps(preparation_data),
            expires_at,
            now,
        ))
        conn.commit()
    finally:
        conn.close()

    return preparation_id


def get_prepared_data(thread_id: str) -> list[dict[str, Any]]:
    """Get all non-expired prepared data.

    Args:
        thread_id: Thread identifier

    Returns:
        List of prepared data items
    """
    from datetime import datetime, timezone

    conn = get_prediction_connection(thread_id)
    try:
        now = datetime.now(timezone.utc).isoformat()

        rows = conn.execute("""
            SELECT * FROM prepared_data
            WHERE thread_id = ? AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC
        """, (thread_id, now)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_prediction_stats(thread_id: str) -> dict[str, Any]:
    """Get prediction statistics.

    Args:
        thread_id: Thread identifier

    Returns:
        Statistics dictionary
    """
    conn = get_prediction_connection(thread_id)
    try:
        # Total patterns
        total_patterns = conn.execute(
            "SELECT COUNT(*) as count FROM patterns WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        # High confidence patterns
        high_confidence = conn.execute(
            "SELECT COUNT(*) as count FROM patterns WHERE thread_id = ? AND confidence >= 0.7",
            (thread_id,)
        ).fetchone()["count"]

        # Total predictions offered
        total_predictions = conn.execute(
            "SELECT COUNT(*) as count FROM predictions WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        # Accepted predictions
        accepted = conn.execute(
            "SELECT COUNT(*) as count FROM predictions WHERE thread_id = ? AND user_response = 'accepted'",
            (thread_id,)
        ).fetchone()["count"]

        # Active prepared data
        active_data = conn.execute(
            "SELECT COUNT(*) as count FROM prepared_data WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        return {
            "total_patterns": total_patterns,
            "high_confidence_patterns": high_confidence,
            "total_predictions_offered": total_predictions,
            "accepted_predictions": accepted,
            "acceptance_rate": round(accepted / total_predictions * 100, 1) if total_predictions > 0 else 0,
            "active_prepared_data": active_data,
        }
    finally:
        conn.close()


def record_prediction_response(
    prediction_id: str,
    thread_id: str,
    user_response: str,
) -> None:
    """Record user's response to a prediction offer.

    Args:
        prediction_id: Prediction ID
        thread_id: Thread identifier
        user_response: User's response ('accepted', 'rejected', etc.)
    """
    from datetime import datetime

    now = datetime.now(timezone.utc).isoformat()

    conn = get_prediction_connection(thread_id)
    try:
        conn.execute("""
            UPDATE predictions
            SET user_response = ?, updated_at = ?
            WHERE id = ?
        """, (user_response, now, prediction_id))
        conn.commit()
    finally:
        conn.close()
