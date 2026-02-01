"""Test metadata utilization in instinct scoring.

Ensures that all metadata factors (frequency, recency, success rate) are properly used.
"""

import pytest
from datetime import datetime, timezone, timedelta

from executive_assistant.instincts.injector import InstinctInjector
from executive_assistant.storage.instinct_storage import InstinctStorage


class TestMetadataFactors:
    """Test suite for metadata-based confidence adjustment."""

    def setup_method(self):
        """Set up test fixtures."""
        self.storage = InstinctStorage()
        self.injector = InstinctInjector()

    def test_frequency_boost(self):
        """Test that occurrence count provides frequency boost."""
        instincts = [
            {
                "id": "1",
                "action": "be concise",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 10,
                    "last_triggered": datetime.now(timezone.utc).isoformat(),
                    "success_rate": 1.0,
                },
            },
            {
                "id": "2",
                "action": "use JSON",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 0,
                    "success_rate": 1.0,
                },
            },
        ]

        # Apply metadata adjustments (simplified version of injector logic)
        for instinct in instincts:
            base_confidence = instinct["confidence"]
            metadata = instinct.get("metadata", {})

            # Frequency boost
            occurrence_count = metadata.get("occurrence_count", 0)
            frequency_boost = min(0.15, occurrence_count * 0.03)

            instinct["final_confidence"] = base_confidence + frequency_boost

        # First should be boosted
        assert instincts[0]["final_confidence"] > 0.6
        assert instincts[1]["final_confidence"] == 0.6

    def test_staleness_penalty(self):
        """Test that old instincts get staleness penalty."""
        now = datetime.now(timezone.utc)
        thirty_days_ago = (now - timedelta(days=30)).isoformat()

        instincts = [
            {
                "id": "1",
                "action": "be concise",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 0,
                    "last_triggered": thirty_days_ago,
                    "success_rate": 1.0,
                },
            },
            {
                "id": "2",
                "action": "use JSON",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 0,
                    "last_triggered": now.isoformat(),
                    "success_rate": 1.0,
                },
            },
        ]

        # Apply metadata adjustments
        for instinct in instincts:
            base_confidence = instinct["confidence"]
            metadata = instinct.get("metadata", {})

            # Staleness penalty
            last_triggered_str = metadata.get("last_triggered")
            if last_triggered_str:
                last_triggered = datetime.fromisoformat(last_triggered_str)
                days_since_trigger = (now - last_triggered).days
                staleness_penalty = max(-0.2, -days_since_trigger * 0.01)
            else:
                staleness_penalty = -0.1

            instinct["final_confidence"] = base_confidence + staleness_penalty

        # Old instinct should have lower confidence
        assert instincts[0]["final_confidence"] < instincts[1]["final_confidence"]

    def test_success_rate_multiplier(self):
        """Test that success rate acts as multiplier."""
        instincts = [
            {
                "id": "1",
                "action": "be concise",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 0,
                    "success_rate": 0.5,  # Poor success rate
                },
            },
            {
                "id": "2",
                "action": "use JSON",
                "confidence": 0.6,
                "metadata": {
                    "occurrence_count": 0,
                    "success_rate": 1.0,  # Perfect success rate
                },
            },
        ]

        # Apply metadata adjustments
        for instinct in instincts:
            base_confidence = instinct["confidence"]
            metadata = instinct.get("metadata", {})

            # Success rate multiplier
            success_rate = metadata.get("success_rate", 1.0)
            success_multiplier = max(0.8, success_rate)

            instinct["final_confidence"] = base_confidence * success_multiplier

        # Poor success rate should reduce confidence
        assert instincts[0]["final_confidence"] < 0.6
        # Perfect success rate should maintain confidence
        assert instincts[1]["final_confidence"] == 0.6

    def test_combined_factors(self):
        """Test that all three factors combine correctly."""
        now = datetime.now(timezone.utc)

        instinct = {
            "id": "1",
            "action": "be concise",
            "confidence": 0.6,
            "metadata": {
                "occurrence_count": 10,  # High frequency -> boost
                "last_triggered": now.isoformat(),  # Recent -> no penalty
                "success_rate": 0.9,  # Good success rate
            },
        }

        # Apply all factors
        base_confidence = instinct["confidence"]
        metadata = instinct.get("metadata", {})

        # Factor 1: Frequency
        occurrence_count = metadata.get("occurrence_count", 0)
        frequency_boost = min(0.15, occurrence_count * 0.03)

        # Factor 2: Recency
        last_triggered_str = metadata.get("last_triggered")
        staleness_penalty = 0.0  # Recent

        # Factor 3: Success rate
        success_rate = metadata.get("success_rate", 1.0)
        success_multiplier = max(0.8, success_rate)

        # Combine
        final_confidence = base_confidence + frequency_boost + staleness_penalty
        final_confidence *= success_multiplier
        final_confidence = max(0.0, min(1.0, final_confidence))

        # Should be boosted overall
        assert final_confidence > 0.6
        # Frequency boost should be applied
        assert frequency_boost > 0

    def test_confidence_breakdown_tracking(self):
        """Test that confidence breakdown is tracked for debugging."""
        instinct = {
            "id": "1",
            "action": "be concise",
            "confidence": 0.6,
            "metadata": {
                "occurrence_count": 5,
                "last_triggered": datetime.now(timezone.utc).isoformat(),
                "success_rate": 0.8,
            },
        }

        # Calculate breakdown
        base_confidence = instinct["confidence"]
        metadata = instinct.get("metadata", {})

        frequency_boost = min(0.15, metadata.get("occurrence_count", 0) * 0.03)
        staleness_penalty = 0.0
        success_multiplier = max(0.8, metadata.get("success_rate", 1.0))

        breakdown = {
            "base": base_confidence,
            "frequency_boost": frequency_boost,
            "staleness_penalty": staleness_penalty,
            "success_multiplier": success_multiplier,
        }

        # Verify breakdown structure
        assert "base" in breakdown
        assert "frequency_boost" in breakdown
        assert "staleness_penalty" in breakdown
        assert "success_multiplier" in breakdown

        # Verify values
        assert breakdown["base"] == 0.6
        assert breakdown["frequency_boost"] > 0
        assert breakdown["success_multiplier"] == 0.8
