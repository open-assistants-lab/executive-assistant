"""Journal + Goals analysis logic for check-in.

Uses LLM to analyze journal entries and goals, surfacing insights
and items needing attention.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from executive_assistant.config import create_model


def format_journal_entries(entries: list[dict[str, Any]]) -> str:
    """Format journal entries for LLM.

    Args:
        entries: List of journal entries

    Returns:
        Formatted string
    """
    if not entries:
        return "No recent journal entries"

    lines = []
    for entry in entries:
        try:
            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            timestamp = entry.get("timestamp", "Unknown")
        lines.append(f"[{timestamp}] {entry['content']}")
    return "\n".join(lines)


def format_goals(goals: list[dict[str, Any]]) -> str:
    """Format goals for LLM.

    Args:
        goals: List of goals

    Returns:
        Formatted string
    """
    if not goals:
        return "No goals"

    lines = []
    for goal in goals:
        # Status emoji
        if goal["progress"] >= 100:
            status = "✓"
        elif goal["progress"] < 50:
            status = "⚠️"
        else:
            status = "→"

        deadline = goal.get("target_date", "No deadline")
        try:
            if deadline != "No deadline":
                deadline_dt = datetime.fromisoformat(deadline)
                deadline = deadline_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

        lines.append(
            f"[{status}] {goal['title']} - {goal['progress']:.0f}% - Due: {deadline}"
        )
    return "\n".join(lines) if lines else "No active goals"


async def analyze_journal_and_goals(
    journal_entries: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    user_id: str,
    concise: bool = False,
) -> str:
    """
    Analyze journal entries and goals together.

    Args:
        journal_entries: Recent journal entries
        goals: User's goals
        user_id: User identifier (for instinct lookup)
        concise: Whether to use concise format

    Returns:
        Analysis result, or "CHECKIN_OK" if nothing important
    """
    # Format data
    journal_text = format_journal_entries(journal_entries)
    goals_text = format_goals(goals)

    # Check for instincts (user preferences)
    # TODO: Load instincts when instinct storage is accessible
    prefers_concise = concise  # For now, use parameter

    # Build prompt
    prompt = f"""You are running a check-in analyzing journal and goals.

JOURNAL ENTRIES (recent activity):
{journal_text}

GOALS STATUS:
{goals_text}

Your task: Identify anything that needs the user's attention.

Look for:
1. **Misalignment**: Working on X but goal Y is stalled
2. **Patterns**: "Always works on X on Mondays", "No goal work this week"
3. **Items needing attention**: "Goal Z due in 2 days with minimal progress"

{"Provide brief bullet points (2-3 max)." if prefers_concise else "Provide detailed analysis with actionable insights."}

If NOTHING important needs attention, return exactly: CHECKIN_OK
"""

    # Get LLM and analyze
    try:
        llm = create_model()
        response = await llm.ainvoke(prompt)
        result = response.strip()

        # Check for empty or unimportant responses
        if not result or result.lower() == "checkin_ok":
            return "CHECKIN_OK"

        return result

    except Exception as e:
        # On error, log and return OK to avoid spamming
        print(f"Check-in analysis error: {e}")
        return "CHECKIN_OK"


def parse_lookback(lookback: str) -> timedelta:
    """Parse lookback string to timedelta.

    Args:
        lookback: String like "24h", "7d", "1w"

    Returns:
        timedelta object
    """
    lookback = lookback.lower().strip()

    if lookback.endswith("h"):
        hours = int(lookback[:-1])
        return timedelta(hours=hours)
    elif lookback.endswith("d"):
        days = int(lookback[:-1])
        return timedelta(days=days)
    elif lookback.endswith("w"):
        weeks = int(lookback[:-1])
        return timedelta(weeks=weeks)
    else:
        # Default to 24 hours
        return timedelta(hours=24)


def get_start_time(lookback: str) -> str:
    """Get start time ISO timestamp for lookback period.

    Args:
        lookback: String like "24h", "7d"

    Returns:
        ISO timestamp string
    """
    delta = parse_lookback(lookback)
    start_time = datetime.now(timezone.utc) - delta
    return start_time.isoformat()
