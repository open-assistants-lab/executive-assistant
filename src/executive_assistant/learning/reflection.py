"""Reflect → Improve pattern: Self-reflection and continuous improvement.

After each task, Ken reflects on what went well, what could be better,
and updates its instincts to improve over time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


def _get_reflection_db_path(thread_id: str | None = None) -> str:
    """Get the reflection database path."""
    if thread_id is None:
        thread_id = get_thread_id()

    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    return str(instincts_dir / "reflections.db")


def get_reflection_connection(thread_id: str | None = None):
    """Get SQLite connection for reflection data."""
    import sqlite3

    db_path = _get_reflection_db_path(thread_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn) -> None:
    """Create reflection tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            task_description TEXT,
            what_went_well TEXT,
            what_could_be_better TEXT,
            user_corrections TEXT,
            improvement_actions JSON,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS improvement_suggestions (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            suggestion_type TEXT NOT NULL,
            suggestion TEXT NOT NULL,
            priority REAL DEFAULT 0.5,
            status TEXT DEFAULT 'pending',
            implemented_at TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


async def create_reflection(
    thread_id: str,
    task_type: str,
    task_description: str,
    what_went_well: str | None = None,
    what_could_be_better: str | None = None,
    user_corrections: str | None = None,
) -> str:
    """
    Create a reflection after completing a task.

    Args:
        thread_id: Thread identifier
        task_type: Type of task (e.g., "analysis", "coding", "writing")
        task_description: What the task was
        what_went_well: What went well
        what_could_be_better: What could improve
        user_corrections: Any corrections from user

    Returns:
        Reflection ID
    """
    import uuid

    reflection_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Generate improvement actions
    improvement_actions = generate_improvement_actions(
        task_type,
        what_went_well,
        what_could_be_better,
        user_corrections,
    )

    conn = get_reflection_connection(thread_id)
    try:
        conn.execute("""
            INSERT INTO reflections (
                id, thread_id, task_type, task_description,
                what_went_well, what_could_be_better, user_corrections,
                improvement_actions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reflection_id,
            thread_id,
            task_type,
            task_description,
            what_went_well,
            what_could_be_better,
            user_corrections,
            json.dumps(improvement_actions),
            now,
        ))
        conn.commit()
    finally:
        conn.close()

    # Create improvement suggestions
    for action in improvement_actions:
        await create_improvement_suggestion(
            thread_id,
            action["type"],
            action["suggestion"],
            action["priority"],
        )

    return reflection_id


def generate_improvement_actions(
    task_type: str,
    what_went_well: str | None,
    what_could_be_better: str | None,
    user_corrections: str | None,
) -> list[dict[str, Any]]:
    """
    Generate improvement actions from reflection.

    Args:
        task_type: Type of task
        what_went_well: What went well
        what_could_be_better: What could improve
        user_corrections: User corrections

    Returns:
        List of improvement actions
    """
    actions = []

    # Analyze user corrections
    if user_corrections:
        # User said "too long" → preference for brevity
        if "long" in user_corrections.lower() or "verbose" in user_corrections.lower():
            actions.append({
                "type": "preference",
                "suggestion": "Prefer concise responses for this task type",
                "priority": 0.9,
                "instinct_name": f"prefer_concise_{task_type}",
            })

        # User said "wrong tool" → tool selection issue
        if "wrong tool" in user_corrections.lower() or "better tool" in user_corrections.lower():
            actions.append({
                "type": "tool_selection",
                "suggestion": f"Review tool selection for {task_type} tasks",
                "priority": 0.8,
                "instinct_name": f"improve_tool_selection_{task_type}",
            })

        # User said "format" → formatting preference
        if "format" in user_corrections.lower():
            actions.append({
                "type": "format",
                "suggestion": f"Adjust output format for {task_type}",
                "priority": 0.7,
                "instinct_name": f"prefer_format_{task_type}",
            })

    # Analyze what went well
    if what_went_well:
        # Reinforce successful patterns
        actions.append({
            "type": "success_pattern",
            "suggestion": f"Continue this approach: {what_went_well[:100]}",
            "priority": 0.6,
            "instinct_name": f"success_pattern_{task_type}",
        })

    # Analyze what could be better
    if what_could_be_better:
        actions.append({
            "type": "improvement",
            "suggestion": f"Consider improving: {what_could_be_better[:100]}",
            "priority": 0.5,
            "instinct_name": f"improvement_{task_type}",
        })

    return actions


async def create_improvement_suggestion(
    thread_id: str,
    suggestion_type: str,
    suggestion: str,
    priority: float = 0.5,
) -> str:
    """
    Create an improvement suggestion.

    Args:
        thread_id: Thread identifier
        suggestion_type: Type of suggestion
        suggestion: The suggestion
        priority: Priority (0-1)

    Returns:
        Suggestion ID
    """
    import uuid

    suggestion_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_reflection_connection(thread_id)
    try:
        conn.execute("""
            INSERT INTO improvement_suggestions (
                id, thread_id, suggestion_type, suggestion, priority, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (suggestion_id, thread_id, suggestion_type, suggestion, priority, now))
        conn.commit()
    finally:
        conn.close()

    return suggestion_id


def get_recent_reflections(
    thread_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recent reflections.

    Args:
        thread_id: Thread identifier
        limit: Maximum number to return

    Returns:
        List of reflections
    """
    conn = get_reflection_connection(thread_id)
    try:
        rows = conn.execute("""
            SELECT * FROM reflections
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (thread_id, limit)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_pending_improvements(thread_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get pending improvement suggestions.

    Args:
        thread_id: Thread identifier
        limit: Maximum number to return

    Returns:
        List of improvement suggestions
    """
    conn = get_reflection_connection(thread_id)
    try:
        rows = conn.execute("""
            SELECT * FROM improvement_suggestions
            WHERE thread_id = ? AND status = 'pending'
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
        """, (thread_id, limit)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_improvement_implemented(suggestion_id: str, thread_id: str) -> None:
    """Mark an improvement suggestion as implemented.

    Args:
        suggestion_id: Suggestion ID
        thread_id: Thread identifier
    """
    from datetime import datetime

    now = datetime.now(timezone.utc).isoformat()

    conn = get_reflection_connection(thread_id)
    try:
        conn.execute("""
            UPDATE improvement_suggestions
            SET status = 'implemented',
                implemented_at = ?
            WHERE id = ?
        """, (now, suggestion_id))
        conn.commit()
    finally:
        conn.close()


def get_reflection_stats(thread_id: str) -> dict[str, Any]:
    """Get reflection statistics.

    Args:
        thread_id: Thread identifier

    Returns:
        Statistics dictionary
    """
    conn = get_reflection_connection(thread_id)
    try:
        # Total reflections
        total = conn.execute(
            "SELECT COUNT(*) as count FROM reflections WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        # With user corrections
        with_corrections = conn.execute(
            "SELECT COUNT(*) as count FROM reflections WHERE thread_id = ? AND user_corrections IS NOT NULL",
            (thread_id,)
        ).fetchone()["count"]

        # Improvement suggestions
        total_suggestions = conn.execute(
            "SELECT COUNT(*) as count FROM improvement_suggestions WHERE thread_id = ?",
            (thread_id,)
        ).fetchone()["count"]

        implemented = conn.execute(
            "SELECT COUNT(*) as count FROM improvement_suggestions WHERE thread_id = ? AND status = 'implemented'",
            (thread_id,)
        ).fetchone()["count"]

        return {
            "total_reflections": total,
            "with_corrections": with_corrections,
            "total_suggestions": total_suggestions,
            "implemented_suggestions": implemented,
            "implementation_rate": round(implemented / total_suggestions * 100, 1) if total_suggestions > 0 else 0,
        }
    finally:
        conn.close()
