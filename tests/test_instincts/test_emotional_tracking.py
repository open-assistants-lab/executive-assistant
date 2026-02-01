"""Test emotional state tracking system.

Ensures that user emotions are detected and tracked accurately.
"""

import pytest

from executive_assistant.instincts.emotional_tracker import (
    EmotionalState,
    EmotionalTracker,
    get_emotional_tracker,
    reset_emotional_tracker,
)


class TestEmotionalStateDetection:
    """Test suite for emotional state detection from messages."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EmotionalTracker()

    def test_detect_frustration(self):
        """Test detection of frustrated emotional state."""
        messages = [
            "nevermind, forget it",
            "whatever",
            "ok...",
            "Can you help?????",
        ]

        for message in messages:
            state = self.tracker._detect_emotional_state(message)
            assert state == EmotionalState.FRUSTRATED

    def test_detect_satisfaction(self):
        """Test detection of satisfied emotional state."""
        messages = [
            "perfect, that's exactly what I needed",
            "great! thanks",
            "awesome! 👍",
            "✅ that's brilliant",
        ]

        for message in messages:
            state = self.tracker._detect_emotional_state(message)
            assert state == EmotionalState.SATISFIED

    def test_detect_confusion(self):
        """Test detection of confused emotional state."""
        messages = [
            "I don't understand",
            "this is confusing",
            "what do you mean?",
            "can you explain again?",
        ]

        for message in messages:
            state = self.tracker._detect_emotional_state(message)
            assert state == EmotionalState.CONFUSED

    def test_detect_urgency(self):
        """Test detection of urgent emotional state."""
        messages = [
            "I need this ASAP",
            "urgent! help me now",
            "hurry, deadline approaching",
            "emergency, respond immediately",
        ]

        for message in messages:
            state = self.tracker._detect_emotional_state(message)
            assert state == EmotionalState.URGENT

    def test_detect_neutral(self):
        """Test detection of neutral emotional state."""
        messages = [
            "create a table",
            "what's the weather?",
            "help me with this task",
            "tell me a joke",
        ]

        for message in messages:
            state = self.tracker._detect_emotional_state(message)
            assert state == EmotionalState.NEUTRAL


class TestStateTransitions:
    """Test suite for emotional state transitions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EmotionalTracker()

    def test_allowed_transition(self):
        """Test that allowed transitions succeed."""
        # Start neutral
        assert self.tracker.current_state == EmotionalState.NEUTRAL

        # Transition to engaged (allowed)
        self.tracker.current_state = EmotionalState.NEUTRAL
        self.tracker.update_state("I'm curious about this")
        assert self.tracker.current_state == EmotionalState.CURIOUS

    def test_abrupt_transition_blocked(self):
        """Test that abrupt transitions are blocked."""
        # Start satisfied
        self.tracker.current_state = EmotionalState.SATISFIED
        self.tracker.confidence = 0.9

        # Try to jump to frustrated (abrupt)
        # This should be blocked
        state = self.tracker.update_state("I'm frustrated now")

        # Should not transition to frustrated
        assert state == EmotionalState.SATISFIED
        # Confidence should be reduced
        assert self.tracker.confidence < 0.9

    def test_gradual_transition_to_frustrated(self):
        """Test gradual transition through confused to frustrated."""
        # Start neutral
        self.tracker.current_state = EmotionalState.NEUTRAL

        # Go to confused (allowed)
        self.tracker.update_state("I don't understand")
        assert self.tracker.current_state == EmotionalState.CONFUSED

        # Now go to frustrated (allowed from confused)
        self.tracker.update_state("nevermind, whatever")
        assert self.tracker.current_state == EmotionalState.FRUSTRATED

    def test_recovery_from_frustration(self):
        """Test recovery from frustration to satisfaction."""
        # Start frustrated
        self.tracker.current_state = EmotionalState.FRUSTRATED

        # Recover to satisfied (allowed)
        self.tracker.update_state("perfect! that helps")
        assert self.tracker.current_state == EmotionalState.SATISFIED


class TestConfidenceScoring:
    """Test suite for confidence scoring of emotional states."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EmotionalTracker()

    def test_confidence_increases_on_repetition(self):
        """Test that confidence increases when state repeats."""
        # Start neutral
        assert self.tracker.confidence == 0.5

        # Update to same state multiple times
        for _ in range(5):
            self.tracker.update_state("tell me more")

        # Confidence should have increased
        assert self.tracker.confidence > 0.5

    def test_low_confidence_neutral_state(self):
        """Test that low confidence states are treated as neutral."""
        self.tracker.current_state = EmotionalState.FRUSTRATED
        self.tracker.confidence = 0.4

        # Get state for prompt
        guidance = self.tracker.get_state_for_prompt()

        # Should be empty (below threshold)
        assert guidance == ""

    def test_high_confidence_includes_guidance(self):
        """Test that high confidence states include guidance."""
        self.tracker.current_state = EmotionalState.FRUSTRATED
        self.tracker.confidence = 0.8

        # Get state for prompt
        guidance = self.tracker.get_state_for_prompt()

        # Should not be empty
        assert guidance != ""
        assert "frustrated" in guidance.lower()

    def test_early_conversation_assumes_curious(self):
        """Test that early conversations default to curious if neutral."""
        # Short conversation
        state = self.tracker.update_state("hi there", conversation_length=0)

        # Should be curious
        assert state == EmotionalState.CURIOUS


class TestPromptInjection:
    """Test suite for emotional state injection into prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EmotionalTracker()

    def test_frustrated_guidance(self):
        """Test guidance text for frustrated state."""
        self.tracker.current_state = EmotionalState.FRUSTRATED
        self.tracker.confidence = 0.8

        guidance = self.tracker.get_state_for_prompt()

        assert "frustrated" in guidance.lower()
        assert "supportive" in guidance.lower() or "support" in guidance.lower()

    def test_confused_guidance(self):
        """Test guidance text for confused state."""
        self.tracker.current_state = EmotionalState.CONFUSED
        self.tracker.confidence = 0.8

        guidance = self.tracker.get_state_for_prompt()

        assert "confused" in guidance.lower()
        assert "simplify" in guidance.lower() or "example" in guidance.lower()

    def test_urgent_guidance(self):
        """Test guidance text for urgent state."""
        self.tracker.current_state = EmotionalState.URGENT
        self.tracker.confidence = 0.8

        guidance = self.tracker.get_state_for_prompt()

        assert "urgent" in guidance.lower() or "hurry" in guidance.lower()
        assert "skip" in guidance.lower() or "quickly" in guidance.lower()

    def test_neutral_no_guidance(self):
        """Test that neutral state produces no guidance."""
        self.tracker.current_state = EmotionalState.NEUTRAL
        self.tracker.confidence = 0.8

        guidance = self.tracker.get_state_for_prompt()

        assert guidance == ""

    def test_curious_guidance(self):
        """Test guidance text for curious state."""
        self.tracker.current_state = EmotionalState.CURIOUS
        self.tracker.confidence = 0.8

        guidance = self.tracker.get_state_for_prompt()

        assert "curious" in guidance.lower()
        assert "option" in guidance.lower() or "alternative" in guidance.lower()


class TestHistoryTracking:
    """Test suite for emotional state history tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EmotionalTracker()

    def test_history_limited_to_10(self):
        """Test that history is limited to last 10 states."""
        # Add 15 state changes
        for i in range(15):
            self.tracker.update_state(f"message {i}")

        # Should only have 10 in history
        assert len(self.tracker.history) == 10

    def test_summary_includes_history(self):
        """Test that summary includes recent history."""
        self.tracker.update_state("I'm confused")
        self.tracker.update_state("never mind")

        summary = self.tracker.get_summary()

        assert "recent_history" in summary
        assert len(summary["recent_history"]) >= 2
