"""Journal Check-in feature.

Periodically analyzes the journal and goals to surface patterns
and items needing attention, without the user having to ask.

This is the "Observe → Analyze → Act" pattern in action:
- Observe: Read journal entries and goals
- Analyze: Use LLM to detect patterns and issues
- Act: Message user with findings (only if important)
"""

from executive_assistant.checkin.analyzer import (
    analyze_journal_and_goals,
    format_goals,
    format_journal_entries,
    get_start_time,
    parse_lookback,
)
from executive_assistant.checkin.config import (
    CheckinConfig,
    get_checkin_config,
    get_users_with_checkin_enabled,
    save_checkin_config,
    update_last_checkin,
)
from executive_assistant.checkin.runner import (
    run_checkin,
    run_checkin_and_send,
    send_checkin_message,
    should_run_checkin,
)
from executive_assistant.checkin.tools import (
    checkin_disable,
    checkin_enable,
    checkin_hours,
    checkin_schedule,
    checkin_show,
    checkin_test,
)

__all__ = [
    # Config
    "CheckinConfig",
    "get_checkin_config",
    "save_checkin_config",
    "update_last_checkin",
    "get_users_with_checkin_enabled",
    # Analyzer
    "analyze_journal_and_goals",
    "format_journal_entries",
    "format_goals",
    "get_start_time",
    "parse_lookback",
    # Runner
    "run_checkin",
    "run_checkin_and_send",
    "send_checkin_message",
    "should_run_checkin",
    # Tools
    "checkin_enable",
    "checkin_disable",
    "checkin_show",
    "checkin_schedule",
    "checkin_hours",
    "checkin_test",
]
