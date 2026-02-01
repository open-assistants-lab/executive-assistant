"""Test temporal decay system for instincts.

Ensures that old instincts fade over time without reinforcement.
"""

import pytest
from datetime import datetime, timezone, timedelta

from executive_assistant.storage.instinct_storage import InstinctStorage


class TestTemporalDecay:
    """Test suite for temporal decay of instinct confidence."""

    def setup_method(self):
        """Set up test fixtures."""
        self.storage = InstinctStorage()

    def test_half_life_decay(self):
        """Test that confidence halves after half_life_days."""
        # Create an instinct
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id="test_thread",
        )

        # Simulate 30 days passing by modifying created_at
        instinct = self.storage.get_instinct(instinct_id, "test_thread")
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        instinct["created_at"] = thirty_days_ago
        self.storage._update_snapshot(instinct, "test_thread")

        # Apply decay
        new_confidence = self.storage.adjust_confidence_for_decay(instinct_id, "test_thread")

        # Should be approximately half (0.4)
        assert new_confidence == pytest.approx(0.4, abs=0.05)

    def test_heavily_reinforced_no_decay(self):
        """Test that heavily reinforced instincts don't decay."""
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id="test_thread",
        )

        # Set high occurrence count
        instinct = self.storage.get_instinct(instinct_id, "test_thread")
        instinct["metadata"]["occurrence_count"] = 10
        instinct["created_at"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self.storage._update_snapshot(instinct, "test_thread")

        # Apply decay
        new_confidence = self.storage.adjust_confidence_for_decay(instinct_id, "test_thread")

        # Should remain at 0.8 (no decay)
        assert new_confidence == 0.8

    def test_decay_never_below_min(self):
        """Test that confidence never decays below minimum."""
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id="test_thread",
        )

        # Simulate 180 days (6 half-lives)
        instinct = self.storage.get_instinct(instinct_id, "test_thread")
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        instinct["created_at"] = six_months_ago
        self.storage._update_snapshot(instinct, "test_thread")

        # Apply decay
        new_confidence = self.storage.adjust_confidence_for_decay(instinct_id, "test_thread")

        # Should not go below 0.3 (DECAY_CONFIG["min_confidence"])
        assert new_confidence >= 0.3

    def test_reinforcement_resets_decay(self):
        """Test that reinforcement resets the decay timer."""
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.6,
            thread_id="test_thread",
        )

        # Simulate 15 days
        instinct = self.storage.get_instinct(instinct_id, "test_thread")
        fifteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        instinct["created_at"] = fifteen_days_ago
        self.storage._update_snapshot(instinct, "test_thread")

        # Apply decay (should reduce confidence slightly)
        confidence_after_decay = self.storage.adjust_confidence_for_decay(
            instinct_id, "test_thread"
        )
        assert confidence_after_decay < 0.6

        # Reinforce the instinct
        self.storage.reinforce_instinct(instinct_id, "test_thread")

        # Check that confidence was boosted
        reinforced_instinct = self.storage.get_instinct(instinct_id, "test_thread")
        assert reinforced_instinct["confidence"] > confidence_after_decay
        assert reinforced_instinct["metadata"]["occurrence_count"] == 1
        assert reinforced_instinct["metadata"]["last_triggered"] is not None

    def test_list_instincts_applies_decay(self):
        """Test that list_instincts can apply temporal decay when enabled."""
        # Create an old instinct
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id="test_thread",
        )

        # Make it old
        instinct = self.storage.get_instinct(instinct_id, "test_thread")
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        instinct["created_at"] = thirty_days_ago
        self.storage._update_snapshot(instinct, "test_thread")

        # List with decay applied - this will call adjust_confidence_for_decay
        # which updates the snapshot, so the decay becomes persistent
        instincts_with_decay = self.storage.list_instincts(
            thread_id="test_thread",
            apply_decay=True,
        )

        # The confidence should now be decayed in the snapshot
        # Verify by loading again without decay
        final_check = self.storage.list_instincts(
            thread_id="test_thread",
            apply_decay=False,
        )

        # Final check should show decayed confidence (< 0.8)
        assert final_check[0]["confidence"] < 0.8

    def test_exponential_decay_curve(self):
        """Test that decay follows exponential curve with minimum floor."""
        instinct_id = self.storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id="test_thread",
        )

        # Test at different time points
        time_points = [0, 30, 60]  # 0, 1, 2 half-lives
        # Account for min_confidence floor of 0.3
        expected_confidences = [0.8, 0.4, 0.3]  # Last one hits floor

        for days, expected in zip(time_points, expected_confidences):
            instinct = self.storage.get_instinct(instinct_id, "test_thread")
            instinct["created_at"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            self.storage._update_snapshot(instinct, "test_thread")

            actual = self.storage.adjust_confidence_for_decay(instinct_id, "test_thread")
            assert actual == pytest.approx(expected, abs=0.1)
