"""Memory storage using HybridDB.

Two-layer memory architecture:
- Working Memory: recent, high-confidence memories → always injected into context
- Long-term Memory: all memories, retrievable on demand

Domain wrapper over HybridDB that adds:
- Confidence boost on access / confidence decay
- Supersession logic
- Connections graph (linked_to)
- Working/long-term memory tiers
- Progressive disclosure (compact/summary/full)
- Session tracking
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.app_logging import get_logger
from src.sdk.hybrid_db import HybridDB, SearchMode
from src.storage.paths import get_paths

logger = get_logger()

DEFAULT_CONFIDENCE = 0.2
MAX_CONFIDENCE = 0.7
MIN_CONFIDENCE_DELETE = 0.1
CONFIDENCE_BOOST_ON_ACCESS = 0.05
MAX_CONFIDENCE_BOOST_FROM_ACCESS = 0.3

MEMORY_TYPE_PREFERENCE = "preference"
MEMORY_TYPE_FACT = "fact"
MEMORY_TYPE_WORKFLOW = "workflow"
MEMORY_TYPE_CORRECTION = "correction"

MEMORY_TYPES = [
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_WORKFLOW,
    MEMORY_TYPE_CORRECTION,
]

SOURCE_EXPLICIT = "explicit"
SOURCE_LEARNED = "learned"

SCOPE_GLOBAL = "global"
SCOPE_PROJECT = "project"

CONNECTION_RELATIONSHIPS = [
    "relates_to",
    "contradicts",
    "updates",
    "extends",
    "corrects",
    "merged_from",
]

MEMORY_DETAIL_COMPACT = "compact"
MEMORY_DETAIL_SUMMARY = "summary"
MEMORY_DETAIL_FULL = "full"


@dataclass
class Connection:
    target_id: str
    relationship: str = "relates_to"
    strength: float = 1.0


@dataclass
class Memory:
    id: str
    trigger: str
    action: str
    confidence: float
    domain: str
    source: str
    memory_type: str
    observations: int
    created_at: datetime
    updated_at: datetime
    importance: float = 5.0
    consolidated: bool = False
    linked_to: list[str] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    superseded_by: str | None = None
    is_superseded: bool = False
    structured_data: dict[str, Any] = field(default_factory=dict)
    scope: str = SCOPE_GLOBAL
    project_id: str | None = None
    access_count: int = 0
    last_accessed_at: datetime | None = None


@dataclass
class Insight:
    id: str
    summary: str
    domain: str
    linked_memories: list[str]
    confidence: float
    is_superseded: bool
    superseded_by: str | None
    created_at: datetime
    updated_at: datetime


class MemoryStore:
    """Manages memory storage via HybridDB.

    Structure:
        data/private/memory/
        ├── app.db    # SQLite + FTS5 + journal (HybridDB)
        └── vectors/ # ChromaDB (memories + insights collections)
    """

    def __init__(self, user_id: str, base_dir: Path | str | None = None):
        self.user_id = user_id
        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            base_path = get_paths(user_id).memory_dir()
        base_path.mkdir(parents=True, exist_ok=True)

        self.db = HybridDB(str(base_path))
        self._init_tables()

    def _init_tables(self) -> None:
        self.db.create_table(
            "memories",
            {
                "id": "TEXT PRIMARY KEY",
                "trigger": "LONGTEXT",
                "action": "LONGTEXT",
                "confidence": "REAL",
                "domain": "TEXT",
                "source": "TEXT",
                "memory_type": "TEXT",
                "importance": "REAL",
                "consolidated": "BOOLEAN",
                "linked_to": "JSON",
                "superseded_by": "TEXT",
                "is_superseded": "BOOLEAN",
                "observations": "INTEGER",
                "created_at": "TEXT NOT NULL",
                "updated_at": "TEXT NOT NULL",
                "structured_data": "LONGTEXT",
                "scope": "TEXT",
                "project_id": "TEXT",
                "access_count": "INTEGER",
                "last_accessed_at": "TEXT",
            },
        )

        self.db.create_table(
            "insights",
            {
                "id": "TEXT PRIMARY KEY",
                "summary": "LONGTEXT",
                "domain": "TEXT",
                "linked_memories": "JSON",
                "confidence": "REAL",
                "is_superseded": "BOOLEAN",
                "superseded_by": "TEXT",
                "created_at": "TEXT NOT NULL",
                "updated_at": "TEXT NOT NULL",
            },
        )

        self.db.create_table(
            "sessions",
            {
                "id": "TEXT PRIMARY KEY",
                "started_at": "TEXT NOT NULL",
                "ended_at": "TEXT",
                "message_count": "INTEGER",
                "summary": "LONGTEXT",
            },
        )

    def _generate_id(self, trigger: str, action: str) -> str:
        content = f"{trigger}:{action}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _normalize_domain(self, domain: str) -> str:
        domain = domain.lower().strip()
        if domain in ("preferences", "preference"):
            return "preference"
        if domain in ("lesson", "lessons"):
            return "lesson"
        if domain in ("dislike", "dislikes"):
            return "dislikes"
        return domain

    @staticmethod
    def _parse_connections(linked_to_json: str) -> list[Connection]:
        if not linked_to_json or linked_to_json == "[]":
            return []
        raw = json.loads(linked_to_json) if isinstance(linked_to_json, str) else linked_to_json
        connections = []
        for item in raw:
            if isinstance(item, str):
                connections.append(Connection(target_id=item))
            elif isinstance(item, dict):
                connections.append(
                    Connection(
                        target_id=str(item.get("target_id", item.get("id", ""))),
                        relationship=item.get("relationship", "relates_to"),
                        strength=item.get("strength", 1.0),
                    )
                )
        return connections

    @staticmethod
    def _serialize_connections(connections: list[Connection]) -> str:
        return json.dumps(
            [
                {"target_id": c.target_id, "relationship": c.relationship, "strength": c.strength}
                for c in connections
            ]
        )

    def _row_to_memory(self, row: dict) -> Memory:
        connections = self._parse_connections(row.get("linked_to", "[]"))
        structured_raw = row.get("structured_data", "{}")
        if isinstance(structured_raw, str):
            try:
                structured_data = json.loads(structured_raw)
            except (json.JSONDecodeError, TypeError):
                structured_data = {}
        elif isinstance(structured_raw, dict):
            structured_data = structured_raw
        else:
            structured_data = {}

        last_accessed_at = None
        if row.get("last_accessed_at"):
            try:
                last_accessed_at = datetime.fromisoformat(row["last_accessed_at"])
            except (ValueError, TypeError):
                pass

        return Memory(
            id=row["id"],
            trigger=row["trigger"],
            action=row["action"],
            confidence=row["confidence"],
            domain=row["domain"],
            source=row["source"],
            memory_type=row["memory_type"],
            importance=row["importance"],
            consolidated=bool(row.get("consolidated", 0)),
            linked_to=[c.target_id for c in connections],
            connections=connections,
            observations=row["observations"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            superseded_by=row.get("superseded_by"),
            is_superseded=bool(row.get("is_superseded", 0)),
            structured_data=structured_data,
            scope=row.get("scope", SCOPE_GLOBAL),
            project_id=row.get("project_id"),
            access_count=row.get("access_count", 0),
            last_accessed_at=last_accessed_at,
        )

    def _row_to_insight(self, row: dict) -> Insight:
        return Insight(
            id=row["id"],
            summary=row["summary"],
            domain=row["domain"],
            linked_memories=json.loads(row.get("linked_memories", "[]")),
            confidence=row["confidence"],
            is_superseded=bool(row.get("is_superseded", 0)),
            superseded_by=row.get("superseded_by"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ── Domain logic ───────────────────────────────────────

    def maybe_decay_confidence(self) -> None:
        now = datetime.now(UTC).isoformat()
        thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()

        rows = self.db.query(
            "memories",
            where="updated_at < ? AND source = 'learned' AND is_superseded = 0",
            params=(thirty_days_ago,),
            limit=10000,
        )
        for row in rows:
            new_conf = max(0.2, row["confidence"] - 0.1)
            self.db.update("memories", row["id"], {"confidence": new_conf, "updated_at": now})

        delete_rows = self.db.query(
            "memories",
            where="confidence < ? AND is_superseded = 0 AND source = 'learned'",
            params=(MIN_CONFIDENCE_DELETE,),
            limit=10000,
        )
        for row in delete_rows:
            self.db.delete("memories", row["id"])

    def _boost_access(self, memory_id: str) -> None:
        row = self.db.get("memories", memory_id)
        if not row:
            return
        now = datetime.now(UTC).isoformat()
        self.db.update(
            "memories",
            memory_id,
            {
                "access_count": (row.get("access_count", 0) or 0) + 1,
                "confidence": min(
                    row["confidence"] + CONFIDENCE_BOOST_ON_ACCESS,
                    MAX_CONFIDENCE + MAX_CONFIDENCE_BOOST_FROM_ACCESS,
                ),
                "last_accessed_at": now,
                "updated_at": now,
            },
        )

    def add_memory(
        self,
        trigger: str,
        action: str,
        confidence: float = DEFAULT_CONFIDENCE,
        domain: str = "preference",
        source: str = SOURCE_LEARNED,
        memory_type: str = MEMORY_TYPE_PREFERENCE,
        importance: float = 5.0,
        is_update: bool = False,
        structured_data: dict[str, Any] | None = None,
        scope: str = SCOPE_GLOBAL,
        project_id: str | None = None,
        connections: list[Connection] | None = None,
    ) -> Memory:
        self.maybe_decay_confidence()
        domain = self._normalize_domain(domain)
        now = datetime.now(UTC).isoformat()
        memory_id = self._generate_id(trigger, action)
        sd_json = json.dumps(structured_data or {})
        conn_json = self._serialize_connections(connections or [])
        effective_id = memory_id

        base = {
            "trigger": trigger,
            "action": action,
            "domain": domain,
            "source": source,
            "memory_type": memory_type,
            "importance": importance,
            "observations": 1,
            "created_at": now,
            "updated_at": now,
            "structured_data": sd_json,
            "scope": scope,
            "project_id": project_id,
            "linked_to": conn_json,
            "is_superseded": False,
            "superseded_by": None,
            "consolidated": False,
            "access_count": 0,
            "last_accessed_at": None,
        }

        existing = self.db.get("memories", memory_id)

        if existing:
            if is_update:
                cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                self.db.update(
                    "memories",
                    memory_id,
                    {
                        "action": action,
                        "confidence": min(cap, existing["confidence"] + 0.1),
                        "observations": (existing["observations"] or 0) + 1,
                        "updated_at": now,
                        "is_superseded": False,
                        "superseded_by": None,
                        "structured_data": sd_json,
                        "scope": scope,
                        "project_id": project_id,
                    },
                )
                effective_id = memory_id
            else:
                cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                self.db.update(
                    "memories",
                    memory_id,
                    {
                        "confidence": min(cap, existing["confidence"] + 0.05),
                        "observations": (existing["observations"] or 0) + 1,
                        "updated_at": now,
                        "structured_data": sd_json,
                    },
                )
                effective_id = memory_id
        elif is_update:
            similar_rows = self.db.query(
                "memories",
                where="trigger = ? AND domain = ? AND is_superseded = 0",
                params=(trigger, domain),
                limit=1,
            )
            if similar_rows:
                old_id = similar_rows[0]["id"]
                new_id = self._generate_id(trigger, action + now.split(".")[-1])
                self.db.update(
                    "memories",
                    old_id,
                    {
                        "is_superseded": True,
                        "superseded_by": new_id,
                        "updated_at": now,
                    },
                )
                initial_confidence = min(
                    confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                )
                self.db.insert(
                    "memories",
                    {**base, "id": new_id, "confidence": initial_confidence},
                )
                effective_id = new_id
            else:
                initial_confidence = min(
                    confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                )
                self.db.insert(
                    "memories",
                    {**base, "id": memory_id, "confidence": initial_confidence},
                )
                effective_id = memory_id
        else:
            initial_confidence = min(
                confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
            )
            self.db.insert(
                "memories",
                {**base, "id": memory_id, "confidence": initial_confidence},
            )
            effective_id = memory_id

        result = self.get_memory(effective_id)
        if result is None:
            raise RuntimeError(f"Failed to create memory: {effective_id}")
        return result

    def reconcile_vectors(self, limit: int = 100) -> int:
        reconciled = 0
        rows = self.db.query("memories", where="is_superseded = 0", limit=limit)
        for row in rows:
            r = self.db.reconcile("memories")
            reconciled += r.get("missing_added", 0)
            break
        if reconciled > 0:
            logger.info("memory.reconciled", {"reconciled": reconciled}, user_id=self.user_id)
        return reconciled

    def add_memories_batch(self, memories: list[dict[str, Any]]) -> list[Memory]:
        results = []
        for mem_data in memories:
            trigger = mem_data.get("trigger", "")
            action = mem_data.get("action", "")
            if not trigger or not action:
                continue
            domain = self._normalize_domain(mem_data.get("domain", "preference"))
            memory_id = self._generate_id(trigger, action)
            confidence = min(
                mem_data.get("confidence", DEFAULT_CONFIDENCE),
                MAX_CONFIDENCE if mem_data.get("source", SOURCE_LEARNED) == SOURCE_LEARNED else 1.0,
            )
            source = mem_data.get("source", SOURCE_LEARNED)
            memory_type = mem_data.get("memory_type", MEMORY_TYPE_PREFERENCE)
            importance = mem_data.get("importance", 5.0)
            structured_data = json.dumps(mem_data.get("structured_data", {}))
            scope = mem_data.get("scope", SCOPE_GLOBAL)
            project_id = mem_data.get("project_id")
            now = datetime.now(UTC).isoformat()

            existing = self.db.get("memories", memory_id)
            if existing:
                self.db.update(
                    "memories",
                    memory_id,
                    {
                        "confidence": min(confidence, existing["confidence"] + 0.05),
                        "observations": (existing["observations"] or 0) + 1,
                        "updated_at": now,
                    },
                )
            else:
                self.db.insert(
                    "memories",
                    {
                        "id": memory_id,
                        "trigger": trigger,
                        "action": action,
                        "confidence": confidence,
                        "domain": domain,
                        "source": source,
                        "memory_type": memory_type,
                        "importance": importance,
                        "observations": 1,
                        "created_at": now,
                        "updated_at": now,
                        "structured_data": structured_data,
                        "scope": scope,
                        "project_id": project_id,
                        "is_superseded": False,
                        "superseded_by": None,
                        "consolidated": False,
                        "access_count": 0,
                        "last_accessed_at": None,
                    },
                )
            results.append(memory_id)

        loaded = [m for m in (self.get_memory(mid) for mid in results) if m is not None]
        return loaded

    def find_and_update(
        self,
        trigger_pattern: str,
        new_action: str,
        domain: str | None = None,
        memory_type: str | None = None,
    ) -> Memory | None:
        existing = self.search_fts(trigger_pattern, limit=5)
        if domain:
            existing = [m for m in existing if m.domain == domain]
        if existing:
            existing_mem = existing[0]
            return self.update_memory(existing_mem.id, trigger_pattern, new_action)
        return self.add_memory(
            trigger=trigger_pattern,
            action=new_action,
            domain=domain or "preference",
            memory_type=memory_type or MEMORY_TYPE_PREFERENCE,
        )

    def update_memory(
        self,
        memory_id: str,
        new_trigger: str | None = None,
        new_action: str | None = None,
        new_domain: str | None = None,
        new_structured_data: dict[str, Any] | None = None,
    ) -> Memory | None:
        row = self.db.get("memories", memory_id)
        if not row:
            return None

        updates: dict[str, Any] = {
            "updated_at": datetime.now(UTC).isoformat(),
            "observations": (row.get("observations", 0) or 0) + 1,
        }
        if new_trigger:
            updates["trigger"] = new_trigger
        if new_action:
            updates["action"] = new_action
        if new_domain:
            updates["domain"] = self._normalize_domain(new_domain)
        if new_structured_data is not None:
            updates["structured_data"] = json.dumps(new_structured_data)

        self.db.update("memories", memory_id, updates)
        return self.get_memory(memory_id)

    def supersede_memory(self, old_id: str, new_id: str) -> None:
        self.db.update(
            "memories",
            old_id,
            {
                "is_superseded": True,
                "superseded_by": new_id,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    def get_memory(self, memory_id: str) -> Memory | None:
        row = self.db.get("memories", memory_id)
        if not row:
            return None
        return self._row_to_memory(row)

    def list_memories(
        self,
        domain: str | None = None,
        memory_type: str | None = None,
        source: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
        include_superseded: bool = False,
        scope: str | None = None,
        project_id: str | None = None,
    ) -> list[Memory]:
        conditions = ["confidence >= ?"]
        params: list[Any] = [min_confidence]

        if not include_superseded:
            conditions.append("is_superseded = 0")
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if project_id:
            conditions.append("(project_id = ? OR scope = 'global')")
            params.append(project_id)

        where = " AND ".join(conditions)
        rows = self.db.query(
            "memories",
            where=where,
            params=tuple(params),
            order_by="confidence DESC, updated_at DESC",
            limit=limit,
        )
        return [self._row_to_memory(r) for r in rows]

    def list_working_memories(self, min_confidence: float = 0.3, limit: int = 20) -> list[Memory]:
        return self.list_memories(min_confidence=min_confidence, limit=limit)

    def list_longterm_memories(self, min_confidence: float = 0.0, limit: int = 100) -> list[Memory]:
        return self.list_memories(min_confidence=min_confidence, limit=limit)

    def remove_memory(self, memory_id: str) -> bool:
        return self.db.delete("memories", memory_id)

    def search_fts(self, query: str, limit: int = 10) -> list[Memory]:
        if not query.strip():
            return []
        results = self.db.search("memories", "trigger", query, mode=SearchMode.KEYWORD, limit=limit)
        results += self.db.search("memories", "action", query, mode=SearchMode.KEYWORD, limit=limit)
        seen = set()
        unique = []
        for r in results:
            mid = r.get("id")
            if mid and mid not in seen:
                seen.add(mid)
                unique.append(r)
        memories = [self._row_to_memory(r) for r in unique if not r.get("is_superseded")]
        for m in memories:
            self._boost_access(m.id)
        return memories

    def search_semantic(self, query: str, limit: int = 10) -> list[Memory]:
        results = self.db.search_all("memories", query, limit=limit)
        memories = []
        for r in results:
            mem = self.get_memory(r["id"]) if isinstance(r.get("id"), str) else None
            if mem and not mem.is_superseded:
                memories.append(mem)
        for m in memories:
            self._boost_access(m.id)
        if len(memories) < limit:
            self.reconcile_vectors(limit=50)
        return memories[:limit]

    def search_field_semantic(
        self, query: str, field: str | None = None, limit: int = 10
    ) -> list[Memory]:
        if field:
            results = self.db.search(
                "memories", field, query, mode=SearchMode.SEMANTIC, limit=limit
            )
        else:
            results = self.db.search_all("memories", query, limit=limit)

        seen = set()
        memories = []
        for r in results:
            mid = r.get("id")
            if mid and mid not in seen:
                seen.add(mid)
                mem = self.get_memory(mid)
                if mem and not mem.is_superseded:
                    memories.append(mem)
        for m in memories:
            self._boost_access(m.id)
        return memories[:limit]

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[Memory]:
        results = self.db.search_all("memories", query, fts_weight=fts_weight, limit=limit * 2)
        seen = set()
        combined = []
        for r in results:
            mid = r.get("id")
            if mid and mid not in seen:
                seen.add(mid)
                mem = self.get_memory(mid)
                if mem:
                    combined.append((r.get("_score", 0), mem))

        combined.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in combined[:limit]]

    def find_similar(self, memory_id: str, limit: int = 5) -> list[Memory]:
        memory = self.get_memory(memory_id)
        if not memory:
            return []
        query = f"{memory.trigger}: {memory.action}"
        results = self.search_semantic(query, limit=limit + 1)
        return [m for m in results if m.id != memory_id][:limit]

    def add_connection(
        self,
        memory_id: str,
        target_id: str,
        relationship: str = "relates_to",
        strength: float = 1.0,
    ) -> None:
        row = self.db.get("memories", memory_id)
        if not row:
            return
        connections = self._parse_connections(row.get("linked_to", "[]"))
        existing_targets = {c.target_id for c in connections}
        if target_id not in existing_targets:
            connections.append(
                Connection(target_id=target_id, relationship=relationship, strength=strength)
            )
            self.db.update(
                "memories",
                memory_id,
                {
                    "linked_to": self._serialize_connections(connections),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

    def remove_connection(self, memory_id: str, target_id: str) -> None:
        row = self.db.get("memories", memory_id)
        if not row:
            return
        connections = self._parse_connections(row.get("linked_to", "[]"))
        connections = [c for c in connections if c.target_id != target_id]
        self.db.update(
            "memories",
            memory_id,
            {
                "linked_to": self._serialize_connections(connections),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    def get_connections(self, memory_id: str) -> list[Connection]:
        row = self.db.get("memories", memory_id)
        if not row:
            return []
        return self._parse_connections(row.get("linked_to", "[]"))

    def mark_consolidated(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        for mid in memory_ids:
            self.db.update(
                "memories",
                mid,
                {
                    "consolidated": True,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

    def get_insights(
        self, insight_id: str | None = None, limit: int = 10
    ) -> Insight | None | list[Insight]:
        if insight_id:
            row = self.db.get("insights", insight_id)
            if not row:
                return None
            return self._row_to_insight(row)
        return self.list_insights(limit=limit)

    def add_insight(
        self,
        summary: str,
        linked_memories: list[str],
        confidence: float = 0.5,
        domain: str = "general",
    ) -> Insight:
        now = datetime.now(UTC).isoformat()
        insight_id = hashlib.sha256(summary.encode()).hexdigest()[:16]

        existing_rows = self.db.query(
            "insights",
            where="domain = ? AND is_superseded = 0",
            params=(domain,),
            limit=1,
        )
        if existing_rows:
            existing = existing_rows[0]
            existing_words = set(existing["summary"].lower().split())
            new_words = set(summary.lower().split())
            overlap = len(existing_words & new_words) / max(len(existing_words), len(new_words))
            if overlap > 0.6:
                self.db.update(
                    "insights",
                    existing["id"],
                    {
                        "is_superseded": True,
                        "superseded_by": insight_id,
                        "updated_at": now,
                    },
                )
                existing_linked = json.loads(existing.get("linked_memories", "[]"))
                linked_memories = list(set(existing_linked + linked_memories))

        self.db.insert(
            "insights",
            {
                "id": insight_id,
                "summary": summary,
                "domain": domain,
                "linked_memories": json.dumps(linked_memories),
                "confidence": confidence,
                "is_superseded": False,
                "superseded_by": None,
                "created_at": now,
                "updated_at": now,
            },
        )

        return Insight(
            id=insight_id,
            summary=summary,
            domain=domain,
            linked_memories=linked_memories,
            confidence=confidence,
            is_superseded=False,
            superseded_by=None,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def search_insights(self, query: str, limit: int = 5) -> list[Insight]:
        if not query.strip():
            return []
        results = self.db.search("insights", "summary", query, mode=SearchMode.KEYWORD, limit=limit)
        return [self._row_to_insight(r) for r in results if not r.get("is_superseded")]

    def search_insights_semantic(self, query: str, limit: int = 5) -> list[Insight]:
        results = self.db.search(
            "insights", "summary", query, mode=SearchMode.SEMANTIC, limit=limit
        )
        insights = []
        for r in results:
            row = self.db.get("insights", r["id"])
            if row and not row.get("is_superseded"):
                insights.append(self._row_to_insight(row))
        return insights[:limit]

    def list_insights(
        self, domain: str | None = None, include_superseded: bool = False, limit: int = 20
    ) -> list[Insight]:
        conditions = []
        params: list[str] = []
        if not include_superseded:
            conditions.append("is_superseded = 0")
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        where = " AND ".join(conditions) if conditions else ""
        rows = self.db.query(
            "insights",
            where=where,
            params=tuple(params),
            order_by="confidence DESC, created_at DESC",
            limit=limit,
        )
        return [self._row_to_insight(r) for r in rows]

    def remove_insight(self, insight_id: str) -> bool:
        return self.db.delete("insights", insight_id)

    def search_all(
        self,
        query: str,
        memories_limit: int = 5,
        messages_limit: int = 5,
        insights_limit: int = 3,
        user_id: str | None = None,
    ) -> dict[str, list[Any]]:
        results: dict[str, list[Any]] = {
            "memories": [],
            "messages": [],
            "insights": [],
        }
        results["memories"] = self.search_hybrid(query, limit=memories_limit)

        insight_results = self.search_insights(query, limit=insights_limit)
        if not insight_results:
            insight_results = self.search_insights_semantic(query, limit=insights_limit)
        results["insights"] = insight_results

        if user_id:
            try:
                from src.storage.messages import get_conversation_store

                conv_store = get_conversation_store(user_id)
                message_results = conv_store.search_hybrid(query, limit=messages_limit)
                results["messages"] = [
                    {"id": m.id, "content": m.content, "role": m.role, "score": m.score}
                    for m in message_results
                ]
            except Exception:
                pass

        return results

    def get_compact_context(self, max_memories: int = 5) -> str:
        memories = self.list_working_memories(min_confidence=0.3, limit=max_memories * 2)
        if not memories:
            return ""
        by_domain: dict[str, int] = {}
        top_memories: list[str] = []
        for m in sorted(memories, key=lambda x: (-x.confidence, -x.observations))[:max_memories]:
            by_domain[m.domain] = by_domain.get(m.domain, 0) + 1
            source_marker = "★" if m.source == SOURCE_EXPLICIT else ""
            top_memories.append(f"{m.trigger}: {m.action}{source_marker}")
        domain_summary = ", ".join(f"{d}:{c}" for d, c in sorted(by_domain.items()))
        return f"## User Profile ({domain_summary})\n" + "\n".join(f"- {m}" for m in top_memories)

    def get_memory_context(self, detail_level: str = MEMORY_DETAIL_SUMMARY) -> str:
        if detail_level == MEMORY_DETAIL_COMPACT:
            return self.get_compact_context()
        elif detail_level == MEMORY_DETAIL_FULL:
            return self._get_full_context()
        return self._get_summary_context()

    def _get_summary_context(self) -> str:
        memories = self.list_working_memories(min_confidence=0.3, limit=20)
        if not memories:
            return ""
        now = datetime.now(UTC)
        by_domain: dict[str, list[str]] = {}
        for memory in memories:
            domain = memory.domain
            if domain not in by_domain:
                by_domain[domain] = []
            days_old = (now - memory.updated_at).days
            recency = (
                "" if days_old < 7 else f" ({days_old}d ago)" if days_old <= 90 else " (outdated)"
            )
            source_marker = "★" if memory.source == SOURCE_EXPLICIT else ""
            by_domain[domain].append(
                f"  - {memory.trigger}: {memory.action}{recency}{source_marker}"
            )

        domain_order = [
            "personal",
            "work",
            "location",
            "interests",
            "skills",
            "goals",
            "constraints",
            "communication",
            "tools",
            "languages",
            "correction",
            "workflow",
            "lesson",
            "dislikes",
        ]
        parts = ["## User Profile & Preferences"]
        for domain in domain_order:
            if domain in by_domain:
                parts.append(f"\n### {domain.capitalize()}")
                parts.extend(by_domain[domain])
        remaining = [d for d in sorted(by_domain.keys()) if d not in domain_order]
        for domain in remaining:
            parts.append(f"\n### {domain.capitalize()}")
            parts.extend(by_domain[domain])
        return "\n".join(parts)

    def _get_full_context(self) -> str:
        memories = self.list_working_memories(min_confidence=0.3, limit=50)
        if not memories:
            return ""
        parts = ["## User Profile & Preferences (Full)"]
        for memory in sorted(memories, key=lambda m: (-m.confidence, m.domain)):
            source_marker = "★" if memory.source == SOURCE_EXPLICIT else ""
            parts.append(
                f"\n### [{memory.domain}] {memory.trigger}: {memory.action}{source_marker}"
            )
            parts.append(
                f"  - Type: {memory.memory_type} | Confidence: {min(memory.confidence, 1.0):.0%} | Observed: {memory.observations}x"
            )
            if memory.structured_data:
                for key, value in memory.structured_data.items():
                    parts.append(f"  - {key}: {value}")
            if memory.connections:
                parts.append(
                    f"  - Connections: {', '.join(f'{c.target_id[:8]}({c.relationship})' for c in memory.connections)}"
                )
            if memory.scope == SCOPE_PROJECT and memory.project_id:
                parts.append(f"  - Scope: {memory.scope} ({memory.project_id})")
        return "\n".join(parts)

    def create_session(self, session_id: str | None = None) -> str:
        import uuid

        sid = session_id or str(uuid.uuid4())
        self.db.insert(
            "sessions",
            {
                "id": sid,
                "started_at": datetime.now(UTC).isoformat(),
                "message_count": 0,
            },
        )
        return sid

    def update_session(
        self, session_id: str, message_count: int | None = None, summary: str | None = None
    ) -> None:
        updates: dict[str, Any] = {"ended_at": datetime.now(UTC).isoformat()}
        if message_count is not None:
            updates["message_count"] = message_count
        if summary is not None:
            updates["summary"] = summary
        self.db.update("sessions", session_id, updates)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.db.get("sessions", session_id)

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.query("sessions", order_by="started_at DESC", limit=limit)

    def promote_project_memory(self, memory_id: str) -> Memory | None:
        mem = self.get_memory(memory_id)
        if not mem or mem.scope == SCOPE_GLOBAL:
            return mem
        self.db.update(
            "memories",
            memory_id,
            {
                "scope": SCOPE_GLOBAL,
                "project_id": None,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        return self.get_memory(memory_id)

    def get_stats(self) -> dict[str, Any]:
        total = self.db.count("memories")
        rows_by_domain = self.db.query("memories", limit=10000)
        by_domain: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        consolidated = 0
        confidences = []
        for r in rows_by_domain:
            d = r.get("domain", "unknown")
            by_domain[d] = by_domain.get(d, 0) + 1
            t = r.get("memory_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            s = r.get("source", "unknown")
            by_source[s] = by_source.get(s, 0) + 1
            sc = r.get("scope", "global")
            by_scope[sc] = by_scope.get(sc, 0) + 1
            if r.get("consolidated"):
                consolidated += 1
            if not r.get("is_superseded"):
                confidences.append(r.get("confidence", 0))

        insights_count = self.db.count("insights")
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "total": total,
            "by_domain": by_domain,
            "by_type": by_type,
            "by_source": by_source,
            "by_scope": by_scope,
            "consolidated": consolidated,
            "insights": insights_count,
            "avg_confidence": round(avg_conf, 3),
        }

    def migrate_normalize_domains(self) -> int:
        count = 0
        rows = self.db.query(
            "memories", where="domain IN ('preferences', 'preference')", limit=10000
        )
        for r in rows:
            self.db.update("memories", r["id"], {"domain": "preference"})
            count += 1
        rows = self.db.query("memories", where="domain IN ('dislike', 'dislikes')", limit=10000)
        for r in rows:
            self.db.update("memories", r["id"], {"domain": "dislikes"})
            count += 1
        return count


_memory_store_cache: dict[str, MemoryStore] = {}


def get_memory_store(user_id: str) -> MemoryStore:
    if user_id not in _memory_store_cache:
        _memory_store_cache[user_id] = MemoryStore(user_id)
    return _memory_store_cache[user_id]


__all__ = [
    "Memory",
    "Insight",
    "Connection",
    "MemoryStore",
    "get_memory_store",
    "MEMORY_TYPE_PREFERENCE",
    "MEMORY_TYPE_FACT",
    "MEMORY_TYPE_WORKFLOW",
    "MEMORY_TYPE_CORRECTION",
    "SOURCE_EXPLICIT",
    "SOURCE_LEARNED",
    "SCOPE_GLOBAL",
    "SCOPE_PROJECT",
    "CONNECTION_RELATIONSHIPS",
    "DEFAULT_CONFIDENCE",
    "MAX_CONFIDENCE",
    "MIN_CONFIDENCE_DELETE",
    "MEMORY_DETAIL_COMPACT",
    "MEMORY_DETAIL_SUMMARY",
    "MEMORY_DETAIL_FULL",
]
