"""Unified observation-based memory store.

Two-tier pipeline: Observer (perception) → Reflector (processing).
Two tables: observations (what was said), reflections (what it means).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.app_logging import get_logger
from hybriddb import HybridDB

logger = get_logger()


class MemoryStore:
    """Unified observation-based memory.

    observations — Episodic text records from Observer.
    reflections — Synthesized patterns from Reflector.
    """

    def __init__(self, user_id: str, workspace_id: str = "personal",
                 *, base_dir: str | None = None):
        self.user_id = user_id
        self.workspace_id = workspace_id

        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            from src.storage.paths import get_paths
            base_path = get_paths(user_id, workspace_id).user_memory_dir()
        base_path.mkdir(parents=True, exist_ok=True)
        self.db = HybridDB(str(base_path))
        self._init_tables()

    def _init_tables(self) -> None:
        self.db.create_table(
            "observations",
            {
                "id": "TEXT PRIMARY KEY",
                "content": "LONGTEXT",
                "priority": "TEXT",
                "observation_ts": "TEXT",
                "referenced_date": "TEXT",
                "relative_date": "TEXT",
                "source_message_range": "TEXT",
                "created_at": "TEXT",
            },
        )
        self.db.create_table(
            "reflections",
            {
                "id": "TEXT PRIMARY KEY",
                "content": "LONGTEXT",
                "domain": "TEXT",
                "linked_observation_ids": "TEXT",
                "confidence": "REAL DEFAULT 0.6",
                "decay_rate": "REAL DEFAULT 0.05",
                "access_count": "INTEGER DEFAULT 0",
                "created_at": "TEXT",
                "updated_at": "TEXT",
                "last_accessed_at": "TEXT",
            },
        )

    # ── Observations ──────────────────────────────────────

    def insert_observations(self, observations: list[dict[str, Any]]) -> int:
        count = 0
        for obs in observations:
            obs_id = obs.get("id") or f"obs_{uuid.uuid4().hex[:12]}"
            row = {
                "id": obs_id,
                "content": str(obs.get("content", "")),
                "priority": str(obs.get("priority", "🟢")),
                "observation_ts": obs.get("observation_ts")
                    or datetime.now(UTC).isoformat(),
                "referenced_date": obs.get("referenced_date") or "",
                "relative_date": obs.get("relative_date") or "",
                "source_message_range": obs.get("source_message_range") or "",
                "created_at": datetime.now(UTC).isoformat(),
            }
            try:
                self.db.insert("observations", row, sync=False)
                count += 1
            except Exception:
                pass
        self.db.process_journal()
        return count

    def get_recent_observations(self, days: int = 7, limit: int = 50
                                ) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        return self.db.query(
            "observations",
            where="observation_ts > ?",
            params=(cutoff,),
            order_by="observation_ts DESC",
            limit=limit,
        )

    def get_all_observations(self) -> list[dict[str, Any]]:
        return self.db.query("observations", order_by="observation_ts ASC",
                             limit=10000)

    def search_observations(self, query: str, limit: int = 10
                           ) -> list[dict[str, Any]]:
        return self.db.search_all("observations", query, limit=limit)

    # ── Reflections ───────────────────────────────────────

    def insert_reflections(self, reflections: list[dict[str, Any]]) -> int:
        count = 0
        for refl in reflections:
            refl_id = refl.get("id") or f"refl_{uuid.uuid4().hex[:12]}"
            now = datetime.now(UTC).isoformat()
            linked = refl.get("linked_observation_ids", [])
            if isinstance(linked, str):
                linked_str = linked
            else:
                import json
                linked_str = json.dumps(linked)
            row = {
                "id": refl_id,
                "content": str(refl.get("content", "")),
                "domain": str(refl.get("domain", "")),
                "linked_observation_ids": linked_str,
                "confidence": float(refl.get("confidence", 0.6)),
                "decay_rate": float(refl.get("decay_rate", 0.05)),
                "access_count": 0,
                "created_at": now,
                "updated_at": now,
                "last_accessed_at": None,
            }
            try:
                self.db.insert("reflections", row, sync=False)
                count += 1
            except Exception:
                pass
        self.db.process_journal()
        return count

    def search_reflections(self, query: str, method: str = "hybrid",
                           limit: int = 5) -> list[dict[str, Any]]:
        if method == "fts":
            results = self.db.search_all("reflections", query, limit=limit)
        elif method == "semantic":
            try:
                results = self.db.semantic_search("reflections", query,
                                                  limit=limit)
            except Exception:
                results = self.db.search_all("reflections", query, limit=limit)
        else:
            results = self.db.search_all("reflections", query, limit=limit)
            if not results:
                try:
                    results = self.db.semantic_search("reflections", query,
                                                      limit=limit)
                except Exception:
                    pass
        return results

    def boost_reflection(self, reflection_id: str) -> None:
        row = self.db.get("reflections", reflection_id)
        if not row:
            return
        confidence = float(row.get("confidence", 0.6))
        access_count = int(row.get("access_count", 0) or 0)
        new_conf = min(confidence + 0.1 * (1.0 - confidence), 1.0)
        now = datetime.now(UTC).isoformat()
        self.db.update("reflections", reflection_id, {
            "confidence": new_conf,
            "access_count": access_count + 1,
            "last_accessed_at": now,
            "updated_at": now,
        })

    def apply_decay(self) -> int:
        """Apply weekly decay to all reflections. Called by Reflector schedule."""
        now = datetime.now(UTC).isoformat()
        rows = self.db.query("reflections", limit=10000)
        softened = 0
        for row in rows:
            if not row.get("updated_at"):
                continue
            try:
                last = datetime.fromisoformat(str(row["updated_at"]))
            except (ValueError, TypeError):
                continue
            weeks = (datetime.now(UTC) - last).total_seconds() / (7 * 86400)
            if weeks < 1.0:
                continue
            confidence = float(row.get("confidence", 0.6))
            decay_rate = float(row.get("decay_rate", 0.05))
            new_conf = confidence - decay_rate * weeks
            if new_conf <= 0.1:
                continue  # soft-delete: still in DB, filtered from queries
            self.db.update("reflections", row["id"], {
                "confidence": new_conf,
                "updated_at": now,
            })
            softened += 1
        return softened

    def get_reflections(self, limit: int = 20, min_confidence: float = 0.1
                       ) -> list[dict[str, Any]]:
        return self.db.query(
            "reflections",
            where="confidence >= ?",
            params=(min_confidence,),
            order_by="confidence DESC",
            limit=limit,
        )

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass


_memory_store_cache: dict[str, MemoryStore] = {}


def get_memory_store(user_id: str, workspace_id: str = "personal") -> MemoryStore:
    key = f"{user_id}:{workspace_id}"
    if key not in _memory_store_cache:
        _memory_store_cache[key] = MemoryStore(user_id, workspace_id)
    return _memory_store_cache[key]


def clear_memory_store_cache() -> None:
    for store in _memory_store_cache.values():
        try:
            store.close()
        except Exception:
            pass
    _memory_store_cache.clear()
