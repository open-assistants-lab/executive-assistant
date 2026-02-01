"""Emotional state tracking for user interactions.

Tracks emotional trajectory over conversation to provide context.
Empowers the agent to respond empathetically and appropriately.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import re

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class EmotionalState(Enum):
    """User's current emotional state."""
    NEUTRAL = "neutral"
    ENGAGED = "engaged"           # Active, interested
    CONFUSED = "confused"         # Needs clarification
    FRUSTRATED = "frustrated"     # Negative, needs support
    SATISFIED = "satisfied"       # Positive, successful
    OVERWHELMED = "overwhelmed"   # Too much info
    CURIOUS = "curious"           # Exploring
    URGENT = "urgent"             # Time pressure


class EmotionalTracker:
    """Track user's emotional state across conversation."""

    # Pattern definitions for emotional detection
    PATTERNS = {
        EmotionalState.FRUSTRATED: [
            r"\b(nevermind|forget it|whatever)\b",
            r"^(ok|okay|fine)[!.]*$",
            r"\?+$",
        ],
        EmotionalState.SATISFIED: [
            r"\b(perfect|great|awesome|thanks|exactly)\b",
            r"\b(that's what I needed|just what I wanted)\b",
            r"\b(love it|amazing|brilliant|excellent)\b",
            r"👍|✅|🎉",
        ],
        EmotionalState.CONFUSED: [
            r"\b(don't understand|confused|doesn't make sense)\b",
            r"\b(what do you mean|explain again)\b",
        ],
        EmotionalState.OVERWHELMED: [
            r"\b(too much|overwhelmed|information overload)\b",
            r"\b(step back|simplify|too complicated)\b",
        ],
        EmotionalState.URGENT: [
            r"\b(asap|urgent|emergency|immediately|right now)\b",
            r"\b(hurry|quick|deadline)\b",
        ],
        EmotionalState.CURIOUS: [
            r"\b(just curious|wondering)\b",
            r"\b(what if|try|experiment|explore)\b",
        ],
    }

    # Allowed state transitions (prevent abrupt changes)
    ALLOWED_TRANSITIONS = {
        EmotionalState.NEUTRAL: {
            EmotionalState.ENGAGED,
            EmotionalState.CURIOUS,
            EmotionalState.CONFUSED,
            EmotionalState.FRUSTRATED,
        },
        EmotionalState.ENGAGED: {
            EmotionalState.SATISFIED,
            EmotionalState.CONFUSED,
            EmotionalState.FRUSTRATED,
            EmotionalState.URGENT,
        },
        EmotionalState.CONFUSED: {
            EmotionalState.ENGAGED,
            EmotionalState.OVERWHELMED,
            EmotionalState.FRUSTRATED,
            EmotionalState.NEUTRAL,
        },
        EmotionalState.FRUSTRATED: {
            EmotionalState.SATISFIED,  # Recovery!
            EmotionalState.NEUTRAL,
            EmotionalState.OVERWHELMED,
        },
        EmotionalState.CURIOUS: {
            EmotionalState.ENGAGED,
            EmotionalState.CONFUSED,
            EmotionalState.NEUTRAL,
        },
        EmotionalState.URGENT: {
            EmotionalState.SATISFIED,
            EmotionalState.FRUSTRATED,
            EmotionalState.NEUTRAL,
        },
        EmotionalState.SATISFIED: {
            EmotionalState.ENGAGED,
            EmotionalState.NEUTRAL,
        },
        EmotionalState.OVERWHELMED: {
            EmotionalState.FRUSTRATED,
            EmotionalState.NEUTRAL,
        },
    }

    def __init__(self) -> None:
        # Current state and confidence
        self.current_state = EmotionalState.NEUTRAL
        self.confidence = 0.5

        # History (last 10 states)
        self.history: list[dict] = []

        # Transition patterns we've learned
        self.transitions: dict[tuple[EmotionalState, EmotionalState], int] = {}

    def update_state(
        self,
        user_message: str,
        assistant_message: str | None = None,
        conversation_length: int = 0,
    ) -> EmotionalState:
        """Update emotional state based on latest interaction.

        Args:
            user_message: Latest user message
            assistant_message: Optional assistant response (for context)
            conversation_length: Number of messages in conversation

        Returns:
            Updated emotional state
        """
        # Detect emotional signals from user message
        detected_state = self._detect_emotional_state(user_message)

        # Consider context
        if conversation_length < 2:
            # Early conversation: more likely to be curious/confused
            if detected_state == EmotionalState.NEUTRAL:
                detected_state = EmotionalState.CURIOUS

        # Smooth transitions (don't jump abruptly)
        if self._is_abrupt_transition(self.current_state, detected_state):
            # Reduce confidence, keep current state
            self.confidence *= 0.7
            logger.debug(
                f"Blocked abrupt transition: {self.current_state.value} → {detected_state.value} "
                f"(confidence reduced to {self.confidence:.2f})"
            )
        else:
            # Record transition
            key = (self.current_state, detected_state)
            self.transitions[key] = self.transitions.get(key, 0) + 1

            # Update state with smoothing
            alpha = 0.3  # Smoothing factor
            if self.current_state != detected_state:
                self.confidence = alpha + (self.confidence * (1 - alpha))
            else:
                self.confidence = min(1.0, self.confidence + 0.1)

            self.current_state = detected_state

        # Add to history
        self.history.append({
            "state": self.current_state.value,
            "confidence": self.confidence,
            "timestamp": _utc_now(),
        })

        # Keep only last 10
        if len(self.history) > 10:
            self.history.pop(0)

        return self.current_state

    def _detect_emotional_state(self, message: str) -> EmotionalState:
        """Detect emotional state from user message.

        Args:
            message: User message to analyze

        Returns:
            Detected emotional state
        """
        message_lower = message.lower()

        # Check each state's patterns
        for state, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return state

        return EmotionalState.NEUTRAL

    def _is_abrupt_transition(
        self,
        from_state: EmotionalState,
        to_state: EmotionalState,
    ) -> bool:
        """Check if transition is too abrupt.

        Args:
            from_state: Current emotional state
            to_state: Proposed new state

        Returns:
            True if transition is not allowed
        """
        if from_state == to_state:
            return False

        allowed = self.ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state not in allowed

    def get_state_for_prompt(self) -> str:
        """Get formatted state for system prompt injection.

        Returns:
            Formatted guidance string, or empty if neutral/uncertain
        """
        if self.current_state == EmotionalState.NEUTRAL or self.confidence < 0.6:
            return ""

        guidance = {
            EmotionalState.FRUSTRATED: (
                "The user appears frustrated. "
                "Be extra supportive, offer alternatives, "
                "and break down complex tasks into smaller steps."
            ),
            EmotionalState.CONFUSED: (
                "The user seems confused. "
                "Simplify your explanations, use concrete examples, "
                "and check for understanding before proceeding."
            ),
            EmotionalState.OVERWHELMED: (
                "The user is overwhelmed. "
                "Reduce information density, focus on one thing at a time, "
                "and offer to skip details and just provide the solution."
            ),
            EmotionalState.URGENT: (
                "The user is in a hurry. "
                "Skip explanations, go straight to solutions, "
                "and prioritize speed over completeness."
            ),
            EmotionalState.SATISFIED: (
                "The user is satisfied with current approach. "
                "Continue with this style and level of detail."
            ),
            EmotionalState.CURIOUS: (
                "The user is exploring and curious. "
                "Offer options, explain trade-offs, "
                "and suggest alternative approaches they might find interesting."
            ),
            EmotionalState.ENGAGED: (
                "The user is actively engaged. "
                "Match their energy level and dive into details."
            ),
        }

        return guidance.get(self.current_state, "")

    def get_summary(self) -> dict:
        """Get summary of current emotional state.

        Returns:
            Dictionary with state, confidence, and recent history
        """
        return {
            "current_state": self.current_state.value,
            "confidence": self.confidence,
            "recent_history": self.history[-3:] if self.history else [],
            "total_transitions": sum(self.transitions.values()),
        }


# Singleton instance
_emotional_tracker: Optional[EmotionalTracker] = None


def get_emotional_tracker() -> EmotionalTracker:
    """Get singleton emotional tracker instance.

    Returns:
        EmotionalTracker instance
    """
    global _emotional_tracker
    if _emotional_tracker is None:
        _emotional_tracker = EmotionalTracker()
    return _emotional_tracker


def reset_emotional_tracker() -> EmotionalTracker:
    """Reset emotional tracker (mainly for testing).

    Returns:
        New EmotionalTracker instance
    """
    global _emotional_tracker
    _emotional_tracker = EmotionalTracker()
    return _emotional_tracker
