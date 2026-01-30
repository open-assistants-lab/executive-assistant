"""Instinct storage for behavioral pattern learning with confidence scoring.

Instincts are atomic behavioral patterns (trigger → action) learned from user interactions.
They are automatically applied based on confidence scores and can be clustered into skills.

Storage:
- instincts.jsonl: Append-only event log
- instincts.snapshot.json: Compacted current state
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import get_thread_id


# Allowed instinct domains
_ALLOWED_DOMAINS = {
    "communication",
    "format",
    "workflow",
    "tool_selection",
    "verification",
    "timing",
}


# Allowed sources
_ALLOWED_SOURCES = {
    "session-observation",
    "explicit-user",
    "repetition-confirmed",
    "correction-detected",
    "preference-expressed",
    "profile-preset",
    "custom-profile",
    "import",
}


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class InstinctStorage:
    """Storage for instinct behavioral patterns with confidence scoring."""

    def __init__(self) -> None:
        pass

    def _get_instincts_dir(self, thread_id: str | None = None) -> Path:
        """Get the instincts directory for the current thread."""
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided or in context")

        instincts_dir = settings.get_thread_instincts_dir(thread_id)
        instincts_dir.mkdir(parents=True, exist_ok=True)
        return instincts_dir

    def _get_jsonl_path(self, thread_id: str | None = None) -> Path:
        """Get the path to the JSONL event log."""
        return self._get_instincts_dir(thread_id) / "instincts.jsonl"

    def _get_snapshot_path(self, thread_id: str | None = None) -> Path:
        """Get the path to the snapshot file."""
        return self._get_instincts_dir(thread_id) / "instincts.snapshot.json"

    # ========================================================================
    # CREATE: Create new instinct
    # ========================================================================

    def create_instinct(
        self,
        trigger: str,
        action: str,
        domain: str,
        source: str = "session-observation",
        confidence: float = 0.5,
        thread_id: str | None = None,
    ) -> str:
        """
        Create a new instinct entry.

        Args:
            trigger: When this instinct applies (e.g., "user asks quick follow-up questions")
            action: What to do (e.g., "respond briefly, skip detailed explanations")
            domain: Category of instinct
            source: How this instinct was learned
            confidence: Initial confidence score (0.0 to 1.0)
            thread_id: Thread identifier

        Returns:
            Instinct ID
        """
        if domain not in _ALLOWED_DOMAINS:
            raise ValueError(
                f"Invalid domain '{domain}'. Allowed: {', '.join(sorted(_ALLOWED_DOMAINS))}"
            )

        if source not in _ALLOWED_SOURCES:
            raise ValueError(
                f"Invalid source '{source}'. Allowed: {', '.join(sorted(_ALLOWED_SOURCES))}"
            )

        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        instinct_id = str(uuid.uuid4())
        now = _utc_now()

        instinct = {
            "id": instinct_id,
            "trigger": trigger,
            "action": action,
            "domain": domain,
            "source": source,
            "confidence": confidence,
            "evidence": [],
            "metadata": {
                "occurrence_count": 0,
                "success_rate": 1.0,
                "last_triggered": None,
            },
            "status": "enabled",
            "created_at": now,
            "updated_at": now,
        }

        # Record creation event
        event = {
            "event": "create",
            "id": instinct_id,
            "trigger": trigger,
            "action": action,
            "domain": domain,
            "source": source,
            "confidence": confidence,
            "ts": now,
        }

        self._append_event(event, thread_id)
        self._update_snapshot(instinct, thread_id)

        return instinct_id

    # ========================================================================
    # UPDATE: Adjust confidence and status
    # ========================================================================

    def adjust_confidence(
        self,
        instinct_id: str,
        delta: float,
        thread_id: str | None = None,
    ) -> bool:
        """
        Adjust instinct confidence up or down.

        Args:
            instinct_id: Instinct identifier
            delta: Confidence adjustment (-1.0 to 1.0, typically ±0.05 or ±0.1)
            thread_id: Thread identifier

        Returns:
            True if instinct exists, False otherwise
        """
        snapshot = self._load_snapshot(thread_id)

        if instinct_id not in snapshot:
            return False

        instinct = snapshot[instinct_id]
        old_confidence = instinct["confidence"]
        new_confidence = max(0.0, min(1.0, old_confidence + delta))

        instinct["confidence"] = new_confidence
        instinct["updated_at"] = _utc_now()

        # Record confirmation event
        event = {
            "event": "confirm" if delta > 0 else "contradict",
            "id": instinct_id,
            "delta": delta,
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "ts": _utc_now(),
        }

        self._append_event(event, thread_id)

        # Auto-delete if confidence too low
        if new_confidence < 0.2:
            instinct["status"] = "disabled"

        self._update_snapshot(instinct, thread_id)
        return True

    def set_instinct_status(
        self,
        instinct_id: str,
        status: str,
        thread_id: str | None = None,
    ) -> bool:
        """
        Set instinct status (enabled/disabled).

        Args:
            instinct_id: Instinct identifier
            status: Either "enabled" or "disabled"
            thread_id: Thread identifier

        Returns:
            True if instinct exists, False otherwise
        """
        if status not in ("enabled", "disabled"):
            raise ValueError(f"Status must be 'enabled' or 'disabled', got '{status}'")

        snapshot = self._load_snapshot(thread_id)

        if instinct_id not in snapshot:
            return False

        instinct = snapshot[instinct_id]
        instinct["status"] = status
        instinct["updated_at"] = _utc_now()

        self._update_snapshot(instinct, thread_id)
        return True

    # ========================================================================
    # QUERY: Retrieve instincts
    # ========================================================================

    def list_instincts(
        self,
        domain: str | None = None,
        status: str = "enabled",
        min_confidence: float = 0.0,
        thread_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List instincts with optional filtering.

        Args:
            domain: Filter by domain
            status: Filter by status (default: "enabled")
            min_confidence: Minimum confidence score
            thread_id: Thread identifier

        Returns:
            List of instincts
        """
        snapshot = self._load_snapshot(thread_id)

        results = []
        for instinct in snapshot.values():
            # Filter by status
            if instinct["status"] != status:
                continue

            # Filter by domain
            if domain and instinct["domain"] != domain:
                continue

            # Filter by confidence
            if instinct["confidence"] < min_confidence:
                continue

            results.append(instinct)

        # Sort by confidence descending
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results

    def get_instinct(self, instinct_id: str, thread_id: str | None = None) -> dict | None:
        """Get a specific instinct by ID."""
        snapshot = self._load_snapshot(thread_id)
        return snapshot.get(instinct_id)

    def get_applicable_instincts(
        self,
        context: str,
        thread_id: str | None = None,
        max_count: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Get instincts applicable to current context.

        Uses simple keyword matching on the trigger field.
        In production, this would use semantic matching.

        Args:
            context: Current user message/situation
            thread_id: Thread identifier
            max_count: Maximum number of instincts to return

        Returns:
            List of applicable instincts, sorted by confidence
        """
        instincts = self.list_instincts(
            status="enabled",
            min_confidence=0.5,
            thread_id=thread_id,
        )

        # Simple keyword matching (case-insensitive)
        applicable = []
        for instinct in instincts:
            trigger_lower = instinct["trigger"].lower()
            context_lower = context.lower()

            # Check if any trigger word appears in context
            trigger_words = trigger_lower.split()
            if any(word in context_lower for word in trigger_words if len(word) > 3):
                applicable.append(instinct)

        # Sort by confidence and limit
        applicable.sort(key=lambda x: x["confidence"], reverse=True)
        return applicable[:max_count]

    # ========================================================================
    # STORAGE: JSONL + Snapshot
    # ========================================================================

    def _load_snapshot(self, thread_id: str | None = None) -> dict[str, dict]:
        """Load snapshot from disk, rebuilding from JSONL if needed."""
        snapshot_path = self._get_snapshot_path(thread_id)
        jsonl_path = self._get_jsonl_path(thread_id)

        # Try loading snapshot
        if snapshot_path.exists():
            try:
                with open(snapshot_path, "r") as f:
                    snapshot = json.load(f)
                return snapshot
            except (json.JSONDecodeError, IOError):
                pass

        # Rebuild from JSONL
        snapshot = {}
        if jsonl_path.exists():
            with open(jsonl_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)

                        if event["event"] == "create":
                            snapshot[event["id"]] = {
                                "id": event["id"],
                                "trigger": event["trigger"],
                                "action": event["action"],
                                "domain": event["domain"],
                                "source": event["source"],
                                "confidence": event["confidence"],
                                "evidence": [],
                                "metadata": {
                                    "occurrence_count": 0,
                                    "success_rate": 1.0,
                                    "last_triggered": None,
                                },
                                "status": "enabled",
                                "created_at": event["ts"],
                                "updated_at": event["ts"],
                            }

                        elif event["event"] in ("confirm", "contradict"):
                            if event["id"] in snapshot:
                                snapshot[event["id"]]["confidence"] = event.get("new_confidence", 0.5)

                                if snapshot[event["id"]]["confidence"] < 0.2:
                                    snapshot[event["id"]]["status"] = "disabled"

                    except json.JSONDecodeError:
                        continue

        # Save rebuilt snapshot
        if snapshot:
            self._save_snapshot(snapshot, thread_id)

        return snapshot

    def _save_snapshot(self, snapshot: dict, thread_id: str | None = None) -> None:
        """Save snapshot to disk."""
        snapshot_path = self._get_snapshot_path(thread_id)

        with open(snapshot_path, "w") as f:
            json.dump(snapshot, f, indent=2)

    def _append_event(self, event: dict, thread_id: str | None = None) -> None:
        """Append event to JSONL log."""
        jsonl_path = self._get_jsonl_path(thread_id)

        with open(jsonl_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def _update_snapshot(self, instinct: dict, thread_id: str | None = None) -> None:
        """Update a single instinct in snapshot."""
        snapshot = self._load_snapshot(thread_id)
        snapshot[instinct["id"]] = instinct
        self._save_snapshot(snapshot, thread_id)


_instinct_storage = InstinctStorage()


def get_instinct_storage() -> InstinctStorage:
    return _instinct_storage
