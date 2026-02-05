"""User-facing tools for learning patterns.

Tools for Teach → Verify, Reflect → Improve, and Predict → Prepare patterns.
"""

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id

# Import learning functions
from executive_assistant.learning.prediction import (
    check_and_offer_preparation,
    create_preparation,
    get_prediction_stats,
)
from executive_assistant.learning.reflection import (
    create_reflection,
    get_pending_improvements,
    get_reflection_stats,
    get_recent_reflections,
    mark_improvement_implemented,
)
from executive_assistant.learning.verify import (
    confirm_verification,
    format_verification_prompt,
    get_pending_verifications,
    get_verification_stats,
)


# ====================================================================================
# TEACH → VERIFY TOOLS
# ====================================================================================

@tool
def verify_preferences() -> str:
    """Verify and confirm learned preferences.

    Shows pending learning verifications and allows you to confirm
    what Ken has learned from your interactions.

    Returns:
        Verification status and pending items
    """
    thread_id = get_thread_id()

    try:
        pending = get_pending_verifications(thread_id)

        if not pending:
            return """✅ No pending verifications!

All learned patterns have been confirmed."""

        stats = get_verification_stats(thread_id)

        result = f"""📋 Pending Verifications ({len(pending)} items):

"""

        for i, item in enumerate(pending[:5], 1):
            result += f"\n{i}. [{item['learning_type'].upper()}] {item['content'][:80]}"

        if len(pending) > 5:
            result += f"\n... and {len(pending) - 5} more"

        result += f"""

Learning Stats:
• Total: {stats['total']}
• Confirmed: {stats['confirmed']}
• Rejected: {stats['rejected']}
• Acceptance Rate: {stats['acceptance_rate']}%

Review each by number or use: confirm_verification(id, "yes")"""

        return result

    except Exception as e:
        return f"❌ Error loading verifications: {e}"


@tool
def confirm_learning(verification_id: str, response: str) -> str:
    """Confirm a learning verification.

    Args:
        verification_id: ID of verification to confirm
        response: Your response ("yes", "no", or correction)

    Returns:
        Confirmation result
    """
    thread_id = get_thread_id()

    try:
        confirmed = confirm_verification(verification_id, thread_id, response)

        if confirmed:
            return f"""✅ Learning confirmed!

I've saved what I learned. This will help me serve you better in future interactions."""
        else:
            return f"""📝 Noted.

I've recorded your correction and won't save that learning.
This helps me avoid learning incorrect patterns."""

    except Exception as e:
        return f"❌ Error confirming verification: {e}"


# ====================================================================================
# REFLECT → IMPROVE TOOLS
# ====================================================================================

@tool
def show_reflections() -> str:
    """Show recent reflections and improvements.

    Displays what Ken has learned from recent tasks and
    what improvements it has made or suggests.

    Returns:
        Reflections and improvement suggestions
    """
    thread_id = get_thread_id()

    try:
        reflections = get_recent_reflections(thread_id, limit=5)
        improvements = get_pending_improvements(thread_id, limit=10)
        stats = get_reflection_stats(thread_id)

        result = f"""📊 Learning Progress:

Reflections: {stats['total_reflection']}
• With corrections: {stats['with_corrections']}
• Improvement suggestions: {stats['total_suggestions']}
• Implemented: {stats['implemented_suggestions']}
• Implementation rate: {stats['implementation_rate']}%

"""

        if reflections:
            result += "\nRecent Reflections:\n"
            for r in reflections[:3]:
                result += f"\n• {r['task_type']}: {r['task_description'][:60]}\n"

        if improvements:
            result += f"\n\n💡 Suggested Improvements ({len(improvements)}):\n"
            for imp in improvements[:5]:
                result += f"\n• [{imp['suggestion_type']}] {imp['suggestion'][:60]}\n"

        return result.strip()

    except Exception as e:
        return f"❌ Error loading reflections: {e}"


@tool
def create_learning_reflection(
    task_type: str,
    what_went_well: str = "",
    what_could_be_better: str = "",
) -> str:
    """Create a learning reflection after a task.

    Helps Ken learn from completed tasks and improve over time.

    Args:
        task_type: Type of task (analysis, coding, writing, etc.)
        what_went_well: What went well with this task
        what_could_be_better: What could be improved

    Returns:
        Reflection confirmation
    """
    thread_id = get_thread_id()

    try:
        import asyncio

        reflection_id = asyncio.run(create_reflection(
            thread_id=thread_id,
            task_type=task_type,
            task_description=f"Completed {task_type} task",
            what_went_well=what_went_well or None,
            what_could_be_better=what_could_be_better or None,
            user_corrections=None,
        ))

        return f"""✅ Reflection saved!

I've analyzed this {task_type} task and generated improvement suggestions.
Use show_reflections() to see what I've learned.

This helps me continuously improve my performance for {task_type} tasks."""

    except Exception as e:
        return f"❌ Error creating reflection: {e}"


@tool
def implement_improvement(suggestion_id: str) -> str:
    """Mark an improvement suggestion as implemented.

    Args:
        suggestion_id: ID of suggestion to mark as implemented

    Returns:
        Confirmation message
    """
    thread_id = get_thread_id()

    try:
        mark_improvement_implemented(suggestion_id, thread_id)
        return f"""✅ Improvement implemented!

The suggestion has been marked as implemented.
I'll continue using this improved approach going forward."""

    except Exception as e:
        return f"❌ Error implementing improvement: {e}"


# ====================================================================================
# PREDICT → PREPARE TOOLS
# ====================================================================================

@tool
def show_patterns() -> str:
    """Show learned patterns that enable proactive assistance.

    Displays patterns Ken has detected in your behavior that enable
    it to predict and prepare what you'll need.

    Returns:
        Patterns and prediction statistics
    """
    thread_id = get_thread_id()

    try:
        stats = get_prediction_stats(thread_id)

        result = f"""🔮 Learned Patterns:

Pattern Detection Stats:
• Total Patterns: {stats['total_patterns']}
• High Confidence (70%+): {stats['high_confidence_patterns']}
• Predictions Offered: {stats['total_predictions_offered']}
• Acceptance Rate: {stats['acceptance_rate']}%
• Active Prepared Data: {stats['active_prepared_data']}

These patterns help me proactively assist you.
"""

        return result.strip()

    except Exception as e:
        return f"❌ Error loading patterns: {e}"


@tool
def show_prepared_data() -> str:
    """Show what Ken has prepared for you based on patterns.

    Displays data and resources that have been proactively prepared
    based on your behavior patterns.

    Returns:
        Prepared data items
    """
    thread_id = get_thread_id()

    try:
        prepared = get_prepared_data(thread_id)

        if not prepared:
            return """📦 No prepared data currently.

I'll prepare things based on your patterns as I learn them.
Use show_patterns() to see what I'm tracking."""

        result = f"📦 Prepared Data ({len(prepared)} items):\n\n"

        for item in prepared:
            result += f"• [{item['data_type'].upper()}] {item['data_content'][:80]}\n"
            if item.get("expires_at"):
                result += f"  Expires: {item['expires_at']}\n"

        return result.strip()

    except Exception as e:
        return f"❌ Error loading prepared data: {e}"


@tool
def learn_pattern(
    pattern_type: str,
    description: str,
    trigger: str,
    confidence: float = 0.5,
) -> str:
    """Manually teach Ken a pattern for proactive assistance.

    Helps Ken learn your habits so it can proactively assist you.

    Args:
        pattern_type: Type of pattern (time, task, sequence)
        description: Description of the pattern
        trigger: What triggers this pattern (e.g., "Monday 9am")
        confidence: How confident you are this is a pattern (0-1)

    Returns:
        Learning confirmation
    """
    thread_id = get_thread_id()

    try:
        import asyncio

        # Build triggers list
        triggers = [{"type": pattern_type, "description": trigger}]

        pattern_id = asyncio.run(detect_pattern(
            thread_id=thread_id,
            pattern_type=pattern_type,
            pattern_description=description,
            triggers=triggers,
            confidence=confidence,
        ))

        return f"""✅ Pattern learned!

I'll watch for: {description}
Trigger: {trigger}
Confidence: {confidence*100:.0f}%

As this pattern repeats, I'll become more confident and
start offering proactive assistance when I detect it."""

    except Exception as e:
        return f"❌ Error learning pattern: {e}"


# ====================================================================================
# LEARNING STATS OVERVIEW
# ====================================================================================

@tool
def learning_stats() -> str:
    """Show comprehensive learning statistics across all patterns.

    Displays stats for verification, reflection, and prediction systems
    to show how Ken is learning and improving.

    Returns:
        Comprehensive learning statistics
    """
    thread_id = get_thread_id()

    try:
        verify_stats = get_verification_stats(thread_id)
        reflect_stats = get_reflection_stats(thread_id)
        predict_stats = get_prediction_stats(thread_id)

        return f"""📊 Learning Statistics (All Patterns)

TEACH → VERIFY
--------------
Verifications: {verify_stats['total']}
• Confirmed: {verify_stats['confirmed']}
• Rejected: {verify_stats['rejected']}
• Acceptance Rate: {verify_stats['acceptance_rate']}%

REFLECT → IMPROVE
-----------------
Reflections: {reflect_stats['total_reflection']}
• With Corrections: {reflect_stats['with_corrections']}
• Improvement Suggestions: {reflect_stats['total_suggestions']}
• Implemented: {reflect_stats['implemented_suggestions']}
• Implementation Rate: {reflect_stats['implementation_rate']}%

PREDICT → PREPARE
-----------------
Patterns Detected: {predict_stats['total_patterns']}
• High Confidence: {predict_stats['high_confidence_patterns']}
• Predictions Offered: {predict_stats['total_predictions_offered']}
• Acceptance Rate: {predict_stats['acceptance_rate']}%
• Prepared Data: {predict_stats['active_prepared_data']}

💡 These patterns work together to make me progressively more
intelligent and autonomous while keeping you in control."""

    except Exception as e:
        return f"❌ Error loading learning stats: {e}"
