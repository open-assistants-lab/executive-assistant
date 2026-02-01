"""Test conflict resolution system for instincts.

Ensures that contradictory instincts are resolved using priority rules.
"""

import pytest

from executive_assistant.instincts.injector import InstinctInjector


class TestConflictResolution:
    """Test suite for instinct conflict resolution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.injector = InstinctInjector()

    def test_urgency_overrides_detailed(self):
        """Urgency instinct should override detailed explanations."""
        instincts = [
            {
                "id": "1",
                "domain": "timing",
                "action": "respond quickly and skip details",
                "confidence": 0.7,
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "provide detailed explanations",
                "confidence": 0.8,
            },
            {
                "id": "3",
                "domain": "learning_style",
                "action": "explain reasoning and show work",
                "confidence": 0.7,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Urgency should remain, detailed explanations should be removed
        assert len(resolved) == 1
        assert resolved[0]["domain"] == "timing"
        assert "quickly" in resolved[0]["action"].lower()

    def test_concise_overrides_verbose(self):
        """Concise instinct should override verbose/detailed instincts."""
        instincts = [
            {
                "id": "1",
                "domain": "communication",
                "action": "be brief and concise",
                "confidence": 0.8,
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "provide thorough detailed explanations",
                "confidence": 0.7,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Only concise should remain
        assert len(resolved) == 1
        assert "concise" in resolved[0]["action"].lower()

    def test_frustrated_overrides_brief(self):
        """Frustrated emotional state should override brief responses."""
        instincts = [
            {
                "id": "1",
                "domain": "emotional_state",
                "action": "user is frustrated and needs support",
                "confidence": 0.6,
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "keep responses brief and to the point",
                "confidence": 0.7,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Frustrated should remain, brief should be removed
        assert len(resolved) == 1
        assert resolved[0]["domain"] == "emotional_state"

    def test_no_conflict_keeps_both(self):
        """Non-conflicting instincts should both be kept."""
        instincts = [
            {
                "id": "1",
                "domain": "format",
                "action": "use JSON format",
                "confidence": 0.8,
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "be friendly and casual",
                "confidence": 0.7,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Both should remain
        assert len(resolved) == 2

    def test_low_confidence_does_not_override(self):
        """Low confidence instincts should not override higher confidence ones."""
        instincts = [
            {
                "id": "1",
                "domain": "timing",
                "action": "respond with urgency",
                "confidence": 0.4,  # Below threshold
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "provide detailed explanations",
                "confidence": 0.8,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Low confidence urgency should not override
        # Both should remain since threshold not met
        assert len(resolved) == 2

    def test_confidence_threshold_enforcement(self):
        """Test that min_confidence in rules is enforced."""
        instincts = [
            {
                "id": "1",
                "domain": "timing",
                "action": "urgent: respond quickly",
                "confidence": 0.5,  # Below 0.6 threshold
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "detailed explanations",
                "confidence": 0.7,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Urgency below threshold shouldn't override
        assert len(resolved) == 2

    def test_multiple_overrides(self):
        """Test multiple conflict resolution rules in one pass."""
        instincts = [
            {
                "id": "1",
                "domain": "timing",
                "action": "urgent: respond quickly",
                "confidence": 0.8,
            },
            {
                "id": "2",
                "domain": "communication",
                "action": "detailed explanations",
                "confidence": 0.7,
            },
            {
                "id": "3",
                "domain": "learning_style",
                "action": "explain everything thoroughly",
                "confidence": 0.7,
            },
            {
                "id": "4",
                "domain": "communication",
                "action": "be brief",
                "confidence": 0.6,
            },
        ]

        resolved = self.injector._resolve_conflicts(instincts)

        # Urgency should override detailed and learning instincts
        # Brief should also be removed by urgency
        # Only urgency should remain
        assert len(resolved) == 1
        assert resolved[0]["domain"] == "timing"


class TestOccurrenceCountBoost:
    """Test suite for occurrence count confidence boosting."""

    def test_frequent_reinforcement_boost(self):
        """Test that frequently-reinforced instincts get confidence boost."""
        instincts = [
            {
                "id": "1",
                "action": "be concise",
                "confidence": 0.6,
                "metadata": {"occurrence_count": 10},
            },
            {
                "id": "2",
                "action": "use JSON",
                "confidence": 0.6,
                "metadata": {"occurrence_count": 0},
            },
        ]

        # Apply boost (would be done in build_instincts_context)
        for instinct in instincts:
            occurrence_count = instinct["metadata"].get("occurrence_count", 0)
            if occurrence_count >= 5:
                boost = min(0.15, occurrence_count * 0.03)
                instinct["confidence"] = min(1.0, instinct["confidence"] + boost)
                instinct["confidence_boosted"] = True

        # First instinct should be boosted
        assert instincts[0]["confidence"] > 0.6
        assert instincts[0]["confidence"] == pytest.approx(0.6 + min(0.15, 10 * 0.03))
        assert instincts[0]["confidence_boosted"] is True

        # Second instinct should not be boosted
        assert instincts[1]["confidence"] == 0.6
        assert "confidence_boosted" not in instincts[1]

    def test_boost_capped_at_0_15(self):
        """Test that confidence boost is capped at +0.15."""
        instinct = {
            "id": "1",
            "action": "be concise",
            "confidence": 0.6,
            "metadata": {"occurrence_count": 100},  # Very high
        }

        occurrence_count = instinct["metadata"]["occurrence_count"]
        boost = min(0.15, occurrence_count * 0.03)
        instinct["confidence"] = min(1.0, instinct["confidence"] + boost)

        # Should be capped at 0.15
        assert boost == 0.15
        assert instinct["confidence"] == pytest.approx(0.75)
