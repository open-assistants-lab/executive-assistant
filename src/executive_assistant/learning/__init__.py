"""Learning patterns: Teach → Verify, Reflect → Improve, Predict → Prepare.

This module implements three learning patterns that make Ken progressively
more intelligent and autonomous:

1. **Teach → Verify**: Two-way learning where Ken confirms understanding
   before saving patterns, preventing bad instincts.

2. **Reflect → Improve**: Self-reflection after tasks to learn from mistakes
   and continuously improve behavior.

3. **Predict → Prepare**: Anticipatory assistance where Ken learns your
   patterns and proactively prepares what you need.

These patterns build on the existing Memory, Instincts, Goals, and Journal
systems to create a comprehensive learning ecosystem.
"""

from executive_assistant.learning.verify import (
    confirm_verification,
    format_verification_prompt,
    get_learning_connection,
    get_pending_verifications,
    get_verification_stats,
    verify_learning,
)
from executive_assistant.learning.reflection import (
    create_improvement_suggestion,
    create_reflection,
    get_pending_improvements,
    get_reflection_connection,
    get_recent_reflections,
    get_reflection_stats,
    mark_improvement_implemented,
)
from executive_assistant.learning.prediction import (
    check_and_offer_preparation,
    create_preparation,
    detect_pattern,
    get_prediction_connection,
    get_prepared_data,
    get_prediction_stats,
    matches_context,
    record_prediction_response,
)

__all__ = [
    # Verify (Teach → Verify)
    "verify_learning",
    "format_verification_prompt",
    "get_pending_verifications",
    "confirm_verification",
    "get_verification_stats",
    # Reflect (Reflect → Improve)
    "create_reflection",
    "get_recent_reflections",
    "get_pending_improvements",
    "mark_improvement_implemented",
    "get_reflection_stats",
    # Predict (Predict → Prepare)
    "detect_pattern",
    "check_and_offer_preparation",
    "create_preparation",
    "get_prepared_data",
    "record_prediction_response",
    "get_prediction_stats",
]
