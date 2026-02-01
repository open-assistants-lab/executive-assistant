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
    # NEW: User's emotional/mental state
    "emotional_state",
    # NEW: How user prefers to learn
    "learning_style",
    # NEW: Domain expertise tracking
    "expertise",
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
    # Emotional state detection
    "frustration-detected",
    "confusion-detected",
    "satisfaction-detected",
    # Expertise tracking
    "expertise-detected",
    "domain-detected",
    # Contextual patterns
    "urgency-detected",
    "learning-detected",
    "exploration-detected",
}


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class InstinctStorage:
    """Storage for instinct behavioral patterns with confidence scoring."""

    # Temporal decay configuration
    DECAY_CONFIG = {
        "half_life_days": 30,        # Confidence halves every 30 days without reinforcement
        "min_confidence": 0.3,       # Never decay below this
        "reinforcement_reset": True, # Reinforcement resets decay timer
    }

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

    def _set_confidence(
        self,
        instinct_id: str,
        confidence: float,
        thread_id: str | None = None,
    ) -> None:
        """Set the confidence level for an instinct.

        Args:
            instinct_id: Instinct identifier
            confidence: New confidence level (0.0 to 1.0)
            thread_id: Thread identifier
        """
        snapshot = self._load_snapshot(thread_id)

        if instinct_id not in snapshot:
            return

        instinct = snapshot[instinct_id]
        instinct["confidence"] = max(0.0, min(1.0, confidence))
        instinct["updated_at"] = _utc_now()

        self._update_snapshot(instinct, thread_id)

    # ========================================================================
    # QUERY: Retrieve instincts
    # ========================================================================

    def list_instincts(
        self,
        domain: str | None = None,
        status: str = "enabled",
        min_confidence: float = 0.0,
        thread_id: str | None = None,
        apply_decay: bool = True,
    ) -> list[dict[str, Any]]:
        """
        List instincts with optional filtering.

        Args:
            domain: Filter by domain
            status: Filter by status (default: "enabled")
            min_confidence: Minimum confidence score
            thread_id: Thread identifier
            apply_decay: Whether to apply temporal decay (default: True)

        Returns:
            List of instincts with decayed confidence
        """
        snapshot = self._load_snapshot(thread_id)

        results = []
        for instinct in snapshot.values():
            # Apply temporal decay if enabled
            if apply_decay:
                try:
                    adjusted_confidence = self.adjust_confidence_for_decay(
                        instinct["id"], thread_id
                    )
                    instinct["confidence"] = adjusted_confidence
                except Exception:
                    # If decay fails, use original confidence
                    pass

            # Filter by status
            if instinct["status"] != status:
                continue

            # Filter by domain
            if domain and instinct["domain"] != domain:
                continue

            # Filter by confidence (after decay)
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
    # TEMPORAL DECAY: Confidence fades over time without reinforcement
    # ========================================================================

    def adjust_confidence_for_decay(
        self,
        instinct_id: str,
        thread_id: str | None = None,
    ) -> float:
        """Adjust instinct confidence based on age and lack of reinforcement.

        Args:
            instinct_id: Instinct identifier
            thread_id: Thread identifier

        Returns:
            Adjusted confidence score
        """
        instinct = self.get_instinct(instinct_id, thread_id)

        if not instinct:
            raise ValueError(f"Instinct {instinct_id} not found")

        created_at = datetime.fromisoformat(instinct["created_at"])
        days_old = (datetime.now(timezone.utc) - created_at).days

        metadata = instinct.get("metadata", {})
        occurrence_count = metadata.get("occurrence_count", 0)

        # Don't decay heavily reinforced instincts
        if occurrence_count >= 5:
            return instinct["confidence"]

        # Calculate decay
        half_life = self.DECAY_CONFIG["half_life_days"]
        min_conf = self.DECAY_CONFIG["min_confidence"]

        # Exponential decay: confidence * (0.5 ^ (days_old / half_life))
        decay_factor = 0.5 ** (days_old / half_life)
        new_confidence = max(min_conf, instinct["confidence"] * decay_factor)

        # Update if significantly changed
        if abs(new_confidence - instinct["confidence"]) > 0.05:
            self._set_confidence(instinct_id, new_confidence, thread_id)
            # Update in-memory copy for immediate return
            instinct["confidence"] = new_confidence

        return new_confidence

    def reinforce_instinct(
        self,
        instinct_id: str,
        thread_id: str | None = None,
    ) -> None:
        """Record that an instinct was triggered and relevant.

        Resets decay timer by bumping confidence slightly.

        Args:
            instinct_id: Instinct identifier
            thread_id: Thread identifier
        """
        instinct = self.get_instinct(instinct_id, thread_id)
        if not instinct:
            return

        now = _utc_now()

        # Update metadata
        instinct["metadata"]["occurrence_count"] = instinct["metadata"].get("occurrence_count", 0) + 1
        instinct["metadata"]["last_triggered"] = now
        instinct["updated_at"] = now

        # Reset decay by bumping confidence slightly
        instinct["confidence"] = min(1.0, instinct["confidence"] + 0.05)

        # Save to storage
        self._update_snapshot(instinct, thread_id)

        # Record reinforcement event
        event = {
            "event": "reinforce",
            "id": instinct_id,
            "confidence": instinct["confidence"],
            "occurrence_count": instinct["metadata"]["occurrence_count"],
            "ts": now,
        }
        self._append_event(event, thread_id)

    def get_stale_instincts(
        self,
        thread_id: str | None = None,
        days_since_trigger: int = 30,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """Get instincts that haven't been triggered recently.

        Useful for:
        - Identifying outdated patterns
        - Suggesting instinct cleanup
        - Debugging why certain behaviors changed

        Args:
            thread_id: Thread identifier
            days_since_trigger: Days threshold for staleness
            min_confidence: Minimum confidence to check

        Returns:
            List of stale instincts with days_since_trigger added
        """
        instincts = self.list_instincts(
            thread_id=thread_id,
            min_confidence=min_confidence,
            apply_decay=False,  # Don't apply decay when checking staleness
        )

        stale = []
        now = datetime.now(timezone.utc)

        for instinct in instincts:
            metadata = instinct.get("metadata", {})
            last_triggered_str = metadata.get("last_triggered")

            if not last_triggered_str:
                # Never triggered = definitely stale
                instinct["days_since_trigger"] = 999  # Large number
                stale.append(instinct)
                continue

            try:
                last_triggered = datetime.fromisoformat(last_triggered_str)
                days = (now - last_triggered).days

                if days >= days_since_trigger:
                    instinct["days_since_trigger"] = days
                    stale.append(instinct)
            except Exception:
                # Unable to parse date, treat as stale
                instinct["days_since_trigger"] = 999
                stale.append(instinct)

        return stale

    def cleanup_stale_instincts(
        self,
        thread_id: str | None = None,
        days_since_trigger: int = 60,
        min_confidence: float = 0.4,
    ) -> int:
        """Remove instincts that are old and rarely triggered.

        Args:
            thread_id: Thread identifier
            days_since_trigger: Days threshold for staleness
            min_confidence: Maximum confidence to remove

        Returns:
            Count of removed instincts
        """
        stale = self.get_stale_instincts(
            thread_id=thread_id,
            days_since_trigger=days_since_trigger,
            min_confidence=min_confidence,
        )

        removed_count = 0
        for instinct in stale:
            metadata = instinct.get("metadata", {})
            occurrence_count = metadata.get("occurrence_count", 0)

            # Only remove if rarely triggered
            if occurrence_count < 3:
                # Record deletion event
                event = {
                    "event": "delete",
                    "id": instinct["id"],
                    "reason": "cleanup_stale",
                    "occurrence_count": occurrence_count,
                    "days_since_trigger": instinct.get("days_since_trigger", 0),
                    "ts": _utc_now(),
                }
                self._append_event(event, thread_id)

                # Delete from snapshot
                snapshot = self._load_snapshot(thread_id)
                if instinct["id"] in snapshot:
                    del snapshot[instinct["id"]]
                    self._save_snapshot(snapshot, thread_id)
                    removed_count += 1

                    logger.info(
                        f"Cleaned up stale instinct: {instinct['action'][:50]} "
                        f"(occurrence_count: {occurrence_count}, "
                        f"days_since_trigger: {instinct.get('days_since_trigger', 0)})"
                    )

        return removed_count

    # ========================================================================
    # PATTERN RECOGNITION: Find similar instincts
    # ========================================================================

    def find_similar_instincts(
        self,
        thread_id: str | None = None,
        similarity_threshold: float = 0.8,
    ) -> list[list[dict]]:
        """Find instincts that are semantically similar.

        Uses simple word-overlap similarity (can upgrade to embeddings later).

        Args:
            thread_id: Thread identifier
            similarity_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of clusters (lists) of similar instincts
        """
        instincts = self.list_instincts(
            thread_id=thread_id,
            apply_decay=False,  # Use base confidence for similarity
        )

        clusters = []
        used = set()

        for i, instinct_a in enumerate(instincts):
            if i in used:
                continue

            cluster = [instinct_a]
            used.add(i)

            for j, instinct_b in enumerate(instincts[i+1:], start=i+1):
                if j in used:
                    continue

                # Calculate similarity
                sim = self._calculate_similarity(instinct_a, instinct_b)

                if sim >= similarity_threshold:
                    cluster.append(instinct_b)
                    used.add(j)

            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    def _calculate_similarity(self, instinct_a: dict, instinct_b: dict) -> float:
        """Calculate semantic similarity between two instincts.

        Uses word-overlap of trigger and action text.
        Can be upgraded to use embeddings later.

        Args:
            instinct_a: First instinct
            instinct_b: Second instinct

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Combine trigger and action for similarity
        text_a = f"{instinct_a['trigger']} {instinct_a['action']}"
        text_b = f"{instinct_b['trigger']} {instinct_b['action']}"

        # Simple word-overlap similarity
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union)

    def merge_similar_instincts(
        self,
        thread_id: str | None = None,
        similarity_threshold: float = 0.8,
    ) -> dict[str, int]:
        """Merge similar instincts, keeping highest-confidence version.

        Args:
            thread_id: Thread identifier
            similarity_threshold: Minimum similarity to merge
                instincts based on overlap

        Returns:
            Dictionary with merge statistics
        """
        clusters = self.find_similar_instincts(
            thread_id=thread_id,
            similarity_threshold=similarity_threshold,
        )

        merged_count = 0
        boost_count = 0

        for cluster in clusters:
            # Sort by confidence descending
            cluster.sort(key=lambda x: x["confidence"], reverse=True)
            keeper = cluster[0]

            # Merge confidence from others
            for instinct in cluster[1:]:
                # Boost keeper confidence based on merged instinct's confidence
                confidence_boost = instinct["confidence"] * 0.3
                new_confidence = min(1.0, keeper["confidence"] + confidence_boost)

                if new_confidence > keeper["confidence"]:
                    boost_count += 1

                # Merge metadata
                keeper_metadata = keeper.get("metadata", {})
                other_metadata = instinct.get("metadata", {})

                keeper_metadata["occurrence_count"] = (
                    keeper_metadata.get("occurrence_count", 0)
                    + other_metadata.get("occurrence_count", 0)
                )

                # Delete duplicate
                self.delete_instinct(instinct["id"], thread_id)
                merged_count += 1

            # Update keeper confidence
            if boost_count > 0:
                self._set_confidence(keeper["id"], keeper["confidence"], thread_id)

        return {
            "clusters_found": len(clusters),
            "instincts_merged": merged_count,
            "instincts_boosted": boost_count,
        }

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

    def export_instincts(
        self,
        thread_id: str | None = None,
        min_confidence: float = 0.0,
        include_metadata: bool = True,
    ) -> str:
        """Export instincts as JSON string.

        Args:
            thread_id: Thread identifier (None for all threads)
            min_confidence: Minimum confidence threshold
            include_metadata: Whether to include metadata

        Returns:
            JSON string containing exported instincts
        """
        instincts = self.list_instincts(
            thread_id=thread_id,
            min_confidence=min_confidence,
        )

        # Prepare export data
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "thread_id": thread_id,
            "total_instincts": len(instincts),
            "instincts": [],
        }

        for instinct in instincts:
            export_instinct = {
                "id": instinct["id"],
                "trigger": instinct["trigger"],
                "action": instinct["action"],
                "domain": instinct["domain"],
                "confidence": instinct["confidence"],
                "created_at": instinct["created_at"],
            }

            if include_metadata:
                export_instinct["metadata"] = instinct.get("metadata", {})

            export_data["instincts"].append(export_instinct)

        return json.dumps(export_data, indent=2)

    def import_instincts(
        self,
        json_data: str,
        thread_id: str | None = None,
        merge_strategy: "replace" | "merge" = "merge",
        confidence_boost: float = 0.0,
    ) -> dict[str, int]:
        """Import instincts from JSON string.

        Args:
            json_data: JSON string from export_instincts()
            thread_id: Target thread identifier
            merge_strategy: "replace" to overwrite, "merge" to combine
            confidence_boost: Add this to all imported confidences (max 1.0)

        Returns:
            Dictionary with import statistics
        """
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")

        # Validate structure
        if "instincts" not in data:
            raise ValueError("Invalid export format: missing 'instincts'")

        imported_count = 0
        skipped_count = 0
        merged_count = 0

        for export_instinct in data["instincts"]:
            # Apply confidence boost
            confidence = export_instinct["confidence"]
            if confidence_boost > 0:
                confidence = min(1.0, confidence + confidence_boost)

            # Check for duplicates if merging
            if merge_strategy == "merge":
                existing = self.list_instincts(
                    thread_id=thread_id,
                )

                # Check for similar instincts (same trigger+action)
                is_duplicate = False
                for existing_instinct in existing:
                    if (existing_instinct["trigger"] == export_instinct["trigger"] and
                        existing_instinct["action"] == export_instinct["action"]):

                        is_duplicate = True
                        # Merge by keeping higher confidence
                        if confidence > existing_instinct["confidence"]:
                            # Reinforce with higher confidence
                            self.reinforce_instinct(
                                existing_instinct["id"],
                                thread_id,
                                confidence_boost=confidence - existing_instinct["confidence"],
                            )
                            merged_count += 1
                        break

                if is_duplicate:
                    skipped_count += 1
                    continue

            # Create new instinct
            self.create_instinct(
                trigger=export_instinct["trigger"],
                action=export_instinct["action"],
                domain=export_instinct["domain"],
                confidence=confidence,
                thread_id=thread_id,
                metadata=export_instinct.get("metadata", {}),
            )

            imported_count += 1

        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "merged": merged_count,
            "total": imported_count + merged_count,
        }


_instinct_storage = InstinctStorage()


def get_instinct_storage() -> InstinctStorage:
    return _instinct_storage
