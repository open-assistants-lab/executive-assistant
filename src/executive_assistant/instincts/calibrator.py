"""Confidence calibration system for instincts.

Tracks prediction accuracy vs reality to adjust confidence scores.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from executive_assistant.storage.instinct_storage import get_instinct_storage


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class ConfidenceCalibrator:
    """Calibrate instinct confidence based on actual outcomes.

    Tracks whether predicted confidence levels match actual success rates.
    """

    def __init__(self) -> None:
        self.storage = get_instinct_storage()
        # History of (predicted_confidence, actual_outcome)
        self.history: list[Dict] = []

        # Calibration data per confidence bin
        # bins: [0.0-0.2), [0.2-0.4), [0.4-0.6), [0.6-0.8), [0.8-1.0]
        self.calibration_data: Dict[str, Dict] = {}

    def record_prediction(
        self,
        predicted_confidence: float,
        actual_outcome: bool,
        instinct_id: str,
        thread_id: str | None = None,
    ) -> None:
        """Record whether confidence prediction was accurate.

        Args:
            predicted_confidence: What we predicted (confidence level)
            actual_outcome: True if user was satisfied, False if frustrated
            instinct_id: Instinct identifier
            thread_id: Thread identifier
        """
        record = {
            "predicted": predicted_confidence,
            "actual": actual_outcome,
            "instinct_id": instinct_id,
            "thread_id": thread_id,
            "ts": _utc_now(),
        }

        self.history.append(record)

        # Update calibration data periodically
        if len(self.history) % 50 == 0:
            self._calibrate()

    def _calibrate(self) -> None:
        """Calculate calibration curve from history.

        Analyzes history to find systematic biases in confidence scores.
        """
        if not self.history:
            return

        # Group by confidence bins
        bins: Dict[str, Dict] = {}
        for record in self.history:
            pred = record["predicted"]
            bin_key = f"{int(pred * 5) / 5:.1f}"  # 0.0, 0.2, 0.4, 0.6, 0.8

            if bin_key not in bins:
                bins[bin_key] = {"correct": 0, "total": 0}

            bins[bin_key]["total"] += 1
            if record["actual"]:
                bins[bin_key]["correct"] += 1

        # Calculate systematic biases
        adjustments: Dict[str, float] = {}

        for bin_key, stats in bins.items():
            if stats["total"] < 5:  # Need minimum data
                continue

            actual_rate = stats["correct"] / stats["total"]
            predicted_rate = float(bin_key)

            # If we're overconfident (actual < predicted)
            if actual_rate < predicted_rate - 0.1:
                adjustments[bin_key] = -0.1  # Reduce
            # If we're underconfident (actual > predicted)
            elif actual_rate > predicted_rate + 0.1:
                adjustments[bin_key] = 0.1   # Increase

        self.calibration_data = {
            "bins": bins,
            "adjustments": adjustments,
            "total_records": len(self.history),
            "ts": _utc_now(),
        }

        # Apply adjustments to instincts
        self._apply_adjustments(adjustments)

    def _apply_adjustments(self, adjustments: Dict[str, float]) -> None:
        """Apply calibration adjustments to all instincts.

        Args:
            adjustments: Map of bin_key to adjustment value
        """
        if not adjustments:
            return

        # Get all threads (this is expensive, so calibration is periodic)
        # For now, we'll adjust on next access

        # Store adjustments for application on load
        self.pending_adjustments = adjustments

    def get_calibrated_confidence(
        self,
        instinct: dict,
    ) -> float:
        """Get confidence score with calibration applied.

        Args:
            instinct: Instinct dictionary

        Returns:
            Calibrated confidence score
        """
        base_confidence = instinct["confidence"]
        bin_key = f"{int(base_confidence * 5) / 5:.1f}"

        if hasattr(self, 'pending_adjustments') and self.pending_adjustments:
            adjustment = self.pending_adjustments.get(bin_key, 0.0)
            return max(0.0, min(1.0, base_confidence + adjustment))

        return base_confidence

    def get_calibration_summary(self) -> dict:
        """Get summary of calibration data.

        Returns:
            Dictionary with calibration statistics
        """
        if not self.calibration_data:
            return {
                "status": "no_data",
                "total_records": len(self.history),
            }

        return {
            "status": "calibrated",
            **self.calibration_data,
        }


# Singleton instance
_calibrator: ConfidenceCalibrator | None = None


def get_confidence_calibrator() -> ConfidenceCalibrator:
    """Get singleton confidence calibrator instance.

    Returns:
        ConfidenceCalibrator instance
    """
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
    return _calibrator
