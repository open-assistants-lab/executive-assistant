"""Observation storage using HybridDB.

Phase 1: Observations + Reflections tables, no ChromaDB (FTS5-only search).
Phase 3: Enable ChromaDB for semantic search over observations.

Design: docs/OBSERVATIONAL_MEMORY_DESIGN.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.app_logging import get_logger
from src.sdk.hybrid_db import HybridDB

logger = get_logger()


class ObservationStore:
    """Storage layer for observations and reflections using HybridDB.

    Observations are dense text entries produced by the Observer agent.
    Reflections are condensed versions produced by the Reflector agent.
    Both are stored in HybridDB with FTS5 keyword search.
    """

    def __init__(self, user_id: str, workspace_id: str = "personal", *, base_dir: str | None = None):
        self.user_id = user_id
        self.workspace_id = workspace_id
        from src.storage.paths import get_paths

        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            base_path = get_paths(user_id, workspace_id).workspace_memory_dir() / "observations"
        base_path.mkdir(parents=True, exist_ok=True)
        self.db = HybridDB(str(base_path), max_chroma_index_gb=0)
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
                "token_count": "INTEGER",
                "context_window": "TEXT",
                "created_at": "TEXT",
            },
        )
        self.db.create_table(
            "reflections",
            {
                "id": "TEXT PRIMARY KEY",
                "content": "LONGTEXT",
                "source_observation_range": "TEXT",
                "observation_count": "INTEGER",
                "token_count": "INTEGER",
                "created_at": "TEXT",
            },
        )
        try:
            self.db.register_entity_node(
                "observations",
                node_type="observation",
                id_column="id",
                label_template="{priority} observation from {observation_ts}",
            )
        except Exception:
            pass

    def insert_observations(self, observations: list[dict[str, Any]]) -> int:
        batch = []
        facts_stored = 0
        for obs in observations:
            obs_id = obs.get("id") or f"obs_{uuid.uuid4().hex[:12]}"
            row = {
                "id": obs_id,
                "content": str(obs.get("content", "")),
                "priority": str(obs.get("priority", "🟢")),
                "observation_ts": obs.get("observation_ts") or datetime.now(UTC).isoformat(),
                "referenced_date": obs.get("referenced_date") or "",
                "relative_date": obs.get("relative_date") or "",
                "source_message_range": obs.get("source_message_range") or "",
                "token_count": int(obs.get("token_count", 0)),
                "context_window": str(obs.get("context_window", "default")),
                "created_at": datetime.now(UTC).isoformat(),
            }
            batch.append(row)

            for fact in obs.get("facts_extracted") or []:
                try:
                    entity = str(fact.get("entity", "user")).strip() or "user"
                    attribute = str(fact.get("attribute", "")).strip()
                    value = str(fact.get("value", "")).strip()
                    if attribute and value:
                        from src.storage.memory import get_memory_store

                        store = get_memory_store(self.user_id, self.workspace_id)
                        store.upsert_fact_memory(entity, attribute, value, confidence=0.6)
                        facts_stored += 1
                except Exception:
                    pass

        count = 0
        for row in batch:
            try:
                self.db.insert("observations", row, sync=False)
                count += 1
            except Exception:
                pass
        self.db.process_journal()
        return count

    def get_recent_observations(self, days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        return self.db.query(
            "observations",
            where="observation_ts > ?",
            params=(cutoff,),
            order_by="observation_ts DESC",
            limit=limit,
        )

    def get_all_observations(self) -> list[dict[str, Any]]:
        return self.db.query("observations", order_by="observation_ts ASC", limit=1000)

    def get_latest_reflection(self) -> dict[str, Any] | None:
        rows = self.db.query("reflections", order_by="created_at DESC", limit=1)
        return rows[0] if rows else None

    def insert_reflection(self, reflection: dict[str, Any]) -> str:
        row_id = reflection.get("id") or f"refl_{uuid.uuid4().hex[:12]}"
        self.db.insert(
            "reflections",
            {
                "id": row_id,
                "content": str(reflection.get("reflection_text", reflection.get("content", ""))),
                "source_observation_range": str(reflection.get("source_observation_range", "")),
                "observation_count": int(reflection.get("observation_count", 0)),
                "token_count": int(reflection.get("token_count", 0)),
                "created_at": datetime.now(UTC).isoformat(),
            },
            sync=True,
        )
        return row_id

    def search_observations(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.db.search_all("observations", query, limit=limit)

    def search_reflections(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.db.search_all("reflections", query, limit=limit)

    def find_facts_for_query(self, query: str, limit: int = 3) -> list[Any]:
        from src.storage.memory import get_memory_store

        store = get_memory_store(self.user_id, self.workspace_id)
        return store.find_facts_for_query(query, limit=limit)

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass


_observation_store_cache: dict[str, ObservationStore] = {}


def get_observation_store(user_id: str, workspace_id: str = "personal") -> ObservationStore:
    key = f"{user_id}:{workspace_id}"
    if key not in _observation_store_cache:
        _observation_store_cache[key] = ObservationStore(user_id, workspace_id)
    return _observation_store_cache[key]
