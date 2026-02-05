"""Teach → Verify pattern: Two-way learning verification.

When Ken learns something from the user, it reflects back what it learned
and asks for confirmation before saving. This prevents bad patterns and ensures
correct learning.
"""

from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


def _get_learning_db_path(thread_id: str | None = None) -> str:
    """Get the learning database path."""
    if thread_id is None:
        thread_id = get_thread_id()

    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    return str(instincts_dir / "learning.db")


def get_learning_connection(thread_id: str | None = None):
    """Get SQLite connection for learning data."""
    import sqlite3

    db_path = _get_learning_db_path(thread_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn) -> None:
    """Create learning tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verification_requests (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            learning_type TEXT NOT NULL,
            content TEXT NOT NULL,
            proposed_understanding TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            user_response TEXT,
            confirmed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()


async def verify_learning(
    thread_id: str,
    learning_type: str,
    content: str,
    proposed_understanding: str,
) -> str:
    """
    Create a verification request for learning.

    Args:
        thread_id: Thread identifier
        learning_type: Type of learning (memory, instinct, preference)
        content: What was learned
        proposed_understanding: What the agent understood

    Returns:
        Verification request ID
    """
    import uuid
    from datetime import datetime

    verification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_learning_connection(thread_id)
    try:
        conn.execute("""
            INSERT INTO verification_requests (
                id, thread_id, learning_type, content,
                proposed_understanding, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            verification_id,
            thread_id,
            learning_type,
            content,
            proposed_understanding,
            now,
            now,
        ))
        conn.commit()
    finally:
        conn.close()

    return verification_id


def format_verification_prompt(
    learning_type: str,
    content: str,
    proposed_understanding: str,
) -> str:
    """
    Format a user-friendly verification prompt.

    Args:
        learning_type: Type of learning
        content: What was learned
        proposed_understanding: Agent's understanding

    Returns:
        Formatted prompt for user
    """
    if learning_type == "memory":
        return f"""🧠 I learned: {content}

Let me verify I understood:

{proposed_understanding}

Is this correct? Say "yes" to confirm, or correct me.
"""
    elif learning_type == "preference":
        return f"""📝 Preference detected: {content}

My understanding:

{proposed_understanding}

Should I save this? Say "yes" or adjust it.
"""
    elif learning_type == "instinct":
        return f"""🔮 Pattern detected: {content}

My understanding:

{proposed_understanding}

Is this pattern correct? Say "yes" to save, or describe the correction.
"""
    else:
        return f"""📚 Learned: {content}

Understanding:

{proposed_understanding}

Confirm this is correct? (yes/no/correction)
"""


async def get_pending_verifications(thread_id: str) -> list[dict[str, Any]]:
    """Get all pending verification requests for a user.

    Args:
        thread_id: Thread identifier

    Returns:
        List of pending verification requests
    """
    conn = get_learning_connection(thread_id)
    try:
        rows = conn.execute("""
            SELECT * FROM verification_requests
            WHERE thread_id = ? AND status = 'pending'
            ORDER BY created_at DESC
        """, (thread_id,)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def confirm_verification(
    verification_id: str,
    thread_id: str,
    user_response: str,
) -> bool:
    """
    Confirm a verification request (user said "yes" or similar).

    Args:
        verification_id: Verification request ID
        thread_id: Thread identifier
        user_response: User's response

    Returns:
        True if confirmed, False otherwise
    """
    from datetime import datetime

    # Check if user confirmed
    response_lower = user_response.lower().strip()
    confirmations = ["yes", "correct", "right", "confirm", "that's right", "thats right"]

    is_confirmed = any(c in response_lower for c in confirmations)

    if is_confirmed:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_learning_connection(thread_id)
        try:
            conn.execute("""
                UPDATE verification_requests
                SET status = 'confirmed',
                    user_response = ?,
                    confirmed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (user_response, now, now, verification_id))
            conn.commit()
        finally:
            conn.close()

        return True
    else:
        # User rejected or corrected - mark as rejected
        now = datetime.now(timezone.utc).isoformat()
        conn = get_learning_connection(thread_id)
        try:
            conn.execute("""
                UPDATE verification_requests
                SET status = 'rejected',
                    user_response = ?,
                    updated_at = ?
                WHERE id = ?
            """, (user_response, now, verification_id))
            conn.commit()
        finally:
            conn.close()

        return False


def get_verification_stats(thread_id: str) -> dict[str, Any]:
    """Get statistics about learning verifications.

    Args:
        thread_id: Thread identifier

    Returns:
        Statistics dictionary
    """
    conn = get_learning_connection(thread_id)
    try:
        # Total requests
        total = conn.execute(
            "SELECT COUNT(*) as count FROM verification_requests WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        # Confirmed
        confirmed = conn.execute(
            "SELECT COUNT(*) as count FROM verification_requests WHERE thread_id = ? AND status = 'confirmed'",
            (thread_id,)
        ).fetchone()["count"]

        # Rejected
        rejected = conn.execute(
            "SELECT COUNT(*) as count FROM verification_requests WHERE thread_id = ? AND status = 'rejected'",
            (thread_id,)
        ).fetchone()["count"]

        # Pending
        pending = conn.execute(
            "SELECT COUNT(*) as count FROM verification_requests WHERE thread_id = ? AND status = 'pending'",
            (thread_id,)
        ).fetchone()["count"]

        return {
            "total": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "pending": pending,
            "acceptance_rate": round(confirmed / total * 100, 1) if total > 0 else 0,
        }
    finally:
        conn.close()
