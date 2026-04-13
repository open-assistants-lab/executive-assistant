"""Memory storage using SQLite + FTS5 + ChromaDB.

Two-layer memory architecture:
- Working Memory: recent, high-confidence memories → always injected into context
- Long-term Memory: all memories, retrievable on demand

Memory types:
- preference: user wants/prefers X
- fact: factual information about user (name, location, etc)
- workflow: user's working patterns
- correction: user corrections (no, do A not B)

Improvements over v1:
- Per-field vector indexing (trigger, action, structured_data separately)
- Connections graph with relationship semantics
- Smart forgetting (access tracking, confidence boost on retrieval, auto-prune)
- Granular memory shapes per type (structured_data JSON column)
- Project-scoped memories (scope + project_id)
- Insight semantic search via ChromaDB
- WAL mode + batch operations
- Context manager for connections
- Progressive disclosure support (compact/summary/full detail levels)
"""

import hashlib
import json
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from src.app_logging import get_logger
from src.tools.apps.storage import get_embedding

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
    """A connection between two memories with a relationship label."""

    target_id: str
    relationship: str = "relates_to"
    strength: float = 1.0


@dataclass
class Memory:
    """A learned memory about the user."""

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
    """A synthesized insight from grouped memories."""

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
    """Manages memory storage.

    Structure:
        /data/users/{user_id}/memory/
        ├── memory.db    # SQLite + FTS5
        └── vectors/     # ChromaDB (memories + insights collections)
    """

    def __init__(self, user_id: str, base_dir: Path | str | None = None):
        self.user_id = user_id
        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            base_path = Path(f"data/users/{user_id}/memory")
        base_path.mkdir(parents=True, exist_ok=True)

        self.db_path = str((base_path / "memory.db").resolve())
        self.vector_path = str((base_path / "vectors").resolve())
        self._db_lock = threading.Lock()

        self._init_db()
        self._init_vector_store()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for SQLite connections with WAL mode and thread-safe access."""
        with self._db_lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self) -> None:
        """Initialize SQLite with FTS5, new columns, indexes."""
        with self._connect() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL DEFAULT 0.2,
                    domain TEXT DEFAULT 'preference',
                    source TEXT DEFAULT 'learned',
                    memory_type TEXT DEFAULT 'preference',
                    importance REAL DEFAULT 5.0,
                    consolidated INTEGER DEFAULT 0,
                    linked_to TEXT DEFAULT '[]',
                    superseded_by TEXT,
                    is_superseded INTEGER DEFAULT 0,
                    observations INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    structured_data TEXT DEFAULT '{}',
                    scope TEXT DEFAULT 'global',
                    project_id TEXT,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at TEXT
                )
            """)

            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    trigger,
                    action,
                    content='memories',
                    content_rowid='rowid'
                )
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, trigger, action)
                    VALUES (new.rowid, new.trigger, new.action);
                END
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, trigger, action)
                    VALUES ('delete', old.rowid, old.trigger, old.action);
                END
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, trigger, action)
                    VALUES ('delete', old.rowid, old.trigger, old.action);
                    INSERT INTO memories_fts(rowid, trigger, action)
                    VALUES (new.rowid, new.trigger, new.action);
                END
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    domain TEXT DEFAULT 'general',
                    linked_memories TEXT DEFAULT '[]',
                    confidence REAL DEFAULT 0.5,
                    is_superseded INTEGER DEFAULT 0,
                    superseded_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
                    summary,
                    content='insights',
                    content_rowid='rowid'
                )
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS insights_ai AFTER INSERT ON insights BEGIN
                    INSERT INTO insights_fts(rowid, summary)
                    VALUES (new.rowid, new.summary);
                END
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS insights_ad AFTER DELETE ON insights BEGIN
                    INSERT INTO insights_fts(insights_fts, rowid, summary)
                    VALUES ('delete', old.rowid, old.summary);
                END
            """)

            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS insights_au AFTER UPDATE ON insights BEGIN
                    INSERT INTO insights_fts(insights_fts, rowid, summary)
                    VALUES ('delete', old.rowid, old.summary);
                    INSERT INTO insights_fts(rowid, summary)
                    VALUES (new.rowid, new.summary);
                END
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    message_count INTEGER DEFAULT 0,
                    summary TEXT
                )
            """)

            for col_name, col_type, col_default in [
                ("structured_data", "TEXT", "'{}'"),
                ("scope", "TEXT", "'global'"),
                ("project_id", "TEXT", None),
                ("access_count", "INTEGER", "0"),
                ("last_accessed_at", "TEXT", None),
            ]:
                try:
                    cur.execute(
                        f"ALTER TABLE memories ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"
                        if col_default
                        else f"ALTER TABLE memories ADD COLUMN {col_name} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass

            for col_name, col_type, col_default in [
                ("domain", "TEXT", "'general'"),
                ("is_superseded", "INTEGER", "0"),
                ("superseded_by", "TEXT", None),
                ("updated_at", "TEXT", None),
            ]:
                try:
                    cur.execute(
                        f"ALTER TABLE insights ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"
                        if col_default
                        else f"ALTER TABLE insights ADD COLUMN {col_name} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope, project_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type, is_superseded)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain, is_superseded)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at)")

    def _init_vector_store(self) -> None:
        """Initialize ChromaDB with separate collections for memories and insights."""
        self.chroma = chromadb.PersistentClient(
            path=self.vector_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            name="memories",
            metadata={"user_id": self.user_id},
        )
        self.insights_collection = self.chroma.get_or_create_collection(
            name="insights",
            metadata={"user_id": self.user_id},
        )

        self._memories_field_collection = self.chroma.get_or_create_collection(
            name="memories_fields",
            metadata={"user_id": self.user_id, "type": "per_field"},
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
        """Parse linked_to JSON into Connection objects.

        Supports both legacy format (list of strings) and new format
        (list of dicts with target_id, relationship, strength).
        """
        if not linked_to_json or linked_to_json == "[]":
            return []
        raw = json.loads(linked_to_json)
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
        """Serialize Connection objects to JSON for storage."""
        return json.dumps(
            [
                {"target_id": c.target_id, "relationship": c.relationship, "strength": c.strength}
                for c in connections
            ]
        )

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert a database row to a Memory object."""
        linked_to_raw = row["linked_to"] if "linked_to" in row.keys() else "[]"
        connections = self._parse_connections(linked_to_raw)

        structured_raw = row["structured_data"] if "structured_data" in row.keys() else "{}"
        if isinstance(structured_raw, str):
            try:
                structured_data = json.loads(structured_raw)
            except (json.JSONDecodeError, TypeError):
                structured_data = {}
        elif isinstance(structured_raw, dict):
            structured_data = structured_raw
        else:
            structured_data = {}

        scope = row["scope"] if "scope" in row.keys() else SCOPE_GLOBAL
        project_id = row["project_id"] if "project_id" in row.keys() else None
        access_count = row["access_count"] if "access_count" in row.keys() else 0
        last_accessed_at_raw = row["last_accessed_at"] if "last_accessed_at" in row.keys() else None
        last_accessed_at = (
            datetime.fromisoformat(last_accessed_at_raw) if last_accessed_at_raw else None
        )

        return Memory(
            id=row["id"],
            trigger=row["trigger"],
            action=row["action"],
            confidence=row["confidence"],
            domain=row["domain"],
            source=row["source"],
            memory_type=row["memory_type"],
            importance=row["importance"],
            consolidated=bool(row["consolidated"]),
            linked_to=[c.target_id for c in connections],
            connections=connections,
            observations=row["observations"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            superseded_by=row["superseded_by"],
            is_superseded=bool(row["is_superseded"]),
            structured_data=structured_data,
            scope=scope,
            project_id=project_id,
            access_count=access_count,
            last_accessed_at=last_accessed_at,
        )

    def maybe_decay_confidence(self) -> None:
        """Decrease confidence for memories not observed recently. Prune very low confidence."""
        with self._connect() as cur:
            now = datetime.now(UTC).isoformat()
            thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()

            cur.execute(
                "UPDATE memories SET confidence = MAX(0.2, confidence - 0.1), updated_at = ? "
                "WHERE updated_at < ? AND source = 'learned' AND is_superseded = 0",
                (now, thirty_days_ago),
            )

            cur.execute(
                "DELETE FROM memories WHERE confidence < ? AND is_superseded = 0 AND source = 'learned'",
                (MIN_CONFIDENCE_DELETE,),
            )

            deleted_ids = [
                row[0]
                for row in cur.execute(
                    "SELECT id FROM memories WHERE confidence < ? AND is_superseded = 0 AND source = 'learned'",
                    (MIN_CONFIDENCE_DELETE,),
                ).fetchall()
            ]

        for mid in deleted_ids:
            try:
                self.collection.delete(ids=[mid])
                self._memories_field_collection.delete(
                    where={"memory_id": mid}
                    if self._memories_field_collection.count() > 0
                    else None
                )
            except Exception:
                pass

    def _boost_access(self, memory_id: str) -> None:
        """Boost confidence and update access tracking on retrieval."""
        with self._connect() as cur:
            cur.execute(
                "UPDATE memories SET "
                "access_count = access_count + 1, "
                "confidence = MIN(confidence + ?, ?), "
                "last_accessed_at = ?, "
                "updated_at = ? "
                "WHERE id = ? AND is_superseded = 0",
                (
                    CONFIDENCE_BOOST_ON_ACCESS,
                    MAX_CONFIDENCE + MAX_CONFIDENCE_BOOST_FROM_ACCESS,
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    memory_id,
                ),
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
        """Add or update a memory."""
        self.maybe_decay_confidence()

        domain = self._normalize_domain(domain)
        now = datetime.now(UTC).isoformat()
        memory_id = self._generate_id(trigger, action)
        sd_json = json.dumps(structured_data or {})
        conn_json = self._serialize_connections(connections or [])
        effective_id = memory_id

        with self._connect() as cur:
            cur.execute("SELECT id, observations FROM memories WHERE id = ?", (memory_id,))
            existing = cur.fetchone()

            if existing and is_update:
                cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                cur.execute(
                    "UPDATE memories SET action = ?, confidence = MIN(?, confidence + 0.1), "
                    "observations = observations + 1, updated_at = ?, is_superseded = 0, "
                    "superseded_by = NULL, structured_data = ?, scope = ?, project_id = ? "
                    "WHERE id = ?",
                    (action, cap, now, sd_json, scope, project_id, memory_id),
                )
                effective_id = memory_id
            elif existing:
                cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                cur.execute(
                    "UPDATE memories SET confidence = MIN(?, confidence + 0.05), "
                    "observations = observations + 1, updated_at = ?, structured_data = ? "
                    "WHERE id = ?",
                    (cap, now, sd_json, memory_id),
                )
                effective_id = memory_id
            elif is_update:
                cur.execute(
                    "SELECT id, action FROM memories WHERE trigger = ? AND domain = ? AND is_superseded = 0 LIMIT 1",
                    (trigger, domain),
                )
                similar = cur.fetchone()

                if similar:
                    old_id = similar["id"]
                    new_id = self._generate_id(trigger, action + now.split(".")[-1])
                    cur.execute(
                        "UPDATE memories SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
                        (new_id, now, old_id),
                    )
                    initial_confidence = min(
                        confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                    )
                    cur.execute(
                        "INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, "
                        "importance, observations, created_at, updated_at, structured_data, scope, project_id, "
                        "linked_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                        (
                            new_id,
                            trigger,
                            action,
                            initial_confidence,
                            domain,
                            source,
                            memory_type,
                            importance,
                            now,
                            now,
                            sd_json,
                            scope,
                            project_id,
                            conn_json,
                        ),
                    )
                    effective_id = new_id
                else:
                    initial_confidence = min(
                        confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                    )
                    cur.execute(
                        "INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, "
                        "importance, observations, created_at, updated_at, structured_data, scope, project_id, "
                        "linked_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                        (
                            memory_id,
                            trigger,
                            action,
                            initial_confidence,
                            domain,
                            source,
                            memory_type,
                            importance,
                            now,
                            now,
                            sd_json,
                            scope,
                            project_id,
                            conn_json,
                        ),
                    )
                    effective_id = memory_id
            else:
                initial_confidence = min(
                    confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                )
                cur.execute(
                    "INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, "
                    "importance, observations, created_at, updated_at, structured_data, scope, project_id, "
                    "linked_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                    (
                        memory_id,
                        trigger,
                        action,
                        initial_confidence,
                        domain,
                        source,
                        memory_type,
                        importance,
                        now,
                        now,
                        sd_json,
                        scope,
                        project_id,
                        conn_json,
                    ),
                )
                effective_id = memory_id

        self._update_vector(effective_id, trigger, action)

        result = self.get_memory(effective_id)
        if result is None:
            raise RuntimeError(f"Failed to create memory: {effective_id}")
        return result

    def reconcile_vectors(self, limit: int = 100) -> int:
        """Reconcile ChromaDB vectors with SQLite data.

        Finds memories in SQLite that are missing from ChromaDB and adds them.
        Call this periodically or after search anomalies to recover from
        failed ChromaDB writes.

        Returns the number of reconciled memories.
        """
        reconciled = 0
        with self._connect() as cur:
            cur.execute(
                "SELECT id, trigger, action FROM memories WHERE is_superseded = 0 LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()

        for row in rows:
            mid = row["id"]
            try:
                existing = self.collection.get(ids=[mid])
                if not existing["ids"] or mid not in existing["ids"]:
                    self._update_vector(mid, row["trigger"], row["action"])
                    reconciled += 1
            except Exception:
                try:
                    self._update_vector(mid, row["trigger"], row["action"])
                    reconciled += 1
                except Exception:
                    pass

        if reconciled > 0:
            logger.info(
                "memory.reconciled",
                {"reconciled": reconciled},
                user_id=self.user_id,
            )
        return reconciled

    def add_memories_batch(self, memories: list[dict[str, Any]]) -> list[Memory]:
        """Add multiple memories in a single transaction."""
        results = []
        with self._connect() as cur:
            for mem_data in memories:
                trigger = mem_data.get("trigger", "")
                action = mem_data.get("action", "")
                if not trigger or not action:
                    continue
                domain = self._normalize_domain(mem_data.get("domain", "preference"))
                memory_id = self._generate_id(trigger, action)
                confidence = min(
                    mem_data.get("confidence", DEFAULT_CONFIDENCE),
                    MAX_CONFIDENCE
                    if mem_data.get("source", SOURCE_LEARNED) == SOURCE_LEARNED
                    else 1.0,
                )
                source = mem_data.get("source", SOURCE_LEARNED)
                memory_type = mem_data.get("memory_type", MEMORY_TYPE_PREFERENCE)
                importance = mem_data.get("importance", 5.0)
                structured_data = json.dumps(mem_data.get("structured_data", {}))
                scope = mem_data.get("scope", SCOPE_GLOBAL)
                project_id = mem_data.get("project_id")
                now = datetime.now(UTC).isoformat()

                cur.execute("SELECT id FROM memories WHERE id = ?", (memory_id,))
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        "UPDATE memories SET confidence = MIN(?, confidence + 0.05), "
                        "observations = observations + 1, updated_at = ? WHERE id = ?",
                        (confidence, now, memory_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, "
                        "importance, observations, created_at, updated_at, structured_data, scope, project_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)",
                        (
                            memory_id,
                            trigger,
                            action,
                            confidence,
                            domain,
                            source,
                            memory_type,
                            importance,
                            now,
                            now,
                            structured_data,
                            scope,
                            project_id,
                        ),
                    )
                results.append(memory_id)

        for mid in results:
            self._update_vector(mid, "", "")
        loaded: list[Memory] = []
        for mid in results:
            m = self.get_memory(mid)
            if m is not None:
                loaded.append(m)
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
        """Update an existing memory."""
        with self._connect() as cur:
            cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
            if not row:
                return None

            updates = ["updated_at = ?", "observations = observations + 1"]
            params: list[Any] = [datetime.now(UTC).isoformat()]

            if new_trigger:
                updates.append("trigger = ?")
                params.append(new_trigger)
            if new_action:
                updates.append("action = ?")
                params.append(new_action)
            if new_domain:
                updates.append("domain = ?")
                params.append(self._normalize_domain(new_domain))
            if new_structured_data is not None:
                updates.append("structured_data = ?")
                params.append(json.dumps(new_structured_data))

            params.append(memory_id)
            cur.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", params)

        if new_trigger or new_action:
            mem = self.get_memory(memory_id)
            if mem:
                self._update_vector(memory_id, mem.trigger, mem.action)

        return self.get_memory(memory_id)

    def supersede_memory(self, old_id: str, new_id: str) -> None:
        """Mark old memory as superseded by new memory."""
        with self._connect() as cur:
            cur.execute(
                "UPDATE memories SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
                (new_id, datetime.now(UTC).isoformat(), old_id),
            )

    def _update_vector(self, memory_id: str, trigger: str, action: str) -> None:
        """Update ChromaDB with per-field documents for better recall.

        If ChromaDB write fails, the memory still exists in SQLite and can be
        recovered via reconcile_vectors(). Errors are logged but not raised.
        """
        try:
            mem = self.get_memory(memory_id)
            if mem:
                trigger = trigger or mem.trigger
                action = action or mem.action
                doc_text = f"{trigger}: {action}"
                embedding = get_embedding(doc_text)
                self.collection.upsert(
                    ids=[memory_id],
                    embeddings=[embedding],  # type: ignore[arg-type]
                    documents=[doc_text],
                    metadatas=[{"domain": mem.domain, "type": mem.memory_type, "scope": mem.scope}],
                )

                self._memories_field_collection.upsert(
                    ids=[f"{memory_id}_trigger"],
                    embeddings=[get_embedding(trigger)],  # type: ignore[arg-type]
                    documents=[trigger],
                    metadatas=[{"memory_id": memory_id, "field": "trigger", "domain": mem.domain}],
                )
                self._memories_field_collection.upsert(
                    ids=[f"{memory_id}_action"],
                    embeddings=[get_embedding(action)],  # type: ignore[arg-type]
                    documents=[action],
                    metadatas=[{"memory_id": memory_id, "field": "action", "domain": mem.domain}],
                )

                if mem.structured_data:
                    sd_text = " ".join(str(v) for v in mem.structured_data.values() if v)
                    if sd_text.strip():
                        self._memories_field_collection.upsert(
                            ids=[f"{memory_id}_data"],
                            embeddings=[get_embedding(sd_text)],  # type: ignore[arg-type]
                            documents=[sd_text],
                            metadatas=[
                                {
                                    "memory_id": memory_id,
                                    "field": "structured_data",
                                    "domain": mem.domain,
                                }
                            ],
                        )
        except Exception as e:
            logger.warning(
                "memory.vector_update_failed",
                {"memory_id": memory_id, "error": str(e)},
                user_id=self.user_id,
            )

    def get_memory(self, memory_id: str) -> Memory | None:
        """Get a memory by ID."""
        with self._connect() as cur:
            cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()

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
        """List memories with optional filtering."""
        with self._connect() as cur:
            query = "SELECT * FROM memories WHERE confidence >= ?"
            params: list[Any] = [min_confidence]

            if not include_superseded:
                query += " AND is_superseded = 0"
            if domain:
                query += " AND domain = ?"
                params.append(domain)
            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type)
            if source:
                query += " AND source = ?"
                params.append(source)
            if scope:
                query += " AND scope = ?"
                params.append(scope)
            if project_id:
                query += " AND (project_id = ? OR scope = 'global')"
                params.append(project_id)

            query += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._row_to_memory(row) for row in rows]

    def list_working_memories(self, min_confidence: float = 0.3, limit: int = 20) -> list[Memory]:
        """List working memories - high confidence, recently updated."""
        return self.list_memories(min_confidence=min_confidence, limit=limit)

    def list_longterm_memories(self, min_confidence: float = 0.0, limit: int = 100) -> list[Memory]:
        """List all long-term memories - can be retrieved on demand."""
        return self.list_memories(min_confidence=min_confidence, limit=limit)

    def remove_memory(self, memory_id: str) -> bool:
        """Remove a memory."""
        with self._connect() as cur:
            cur.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            deleted = cur.rowcount > 0

        if deleted:
            try:
                self.collection.delete(ids=[memory_id])
            except Exception:
                pass
            try:
                self._memories_field_collection.delete(
                    ids=[f"{memory_id}_trigger", f"{memory_id}_action", f"{memory_id}_data"]
                )
            except Exception:
                pass

        return deleted

    def search_fts(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories using FTS5. Excludes superseded memories."""
        import re

        fts_query = re.sub(r"[^\w\s]", " ", query.strip())
        fts_query = " ".join(fts_query.split())
        if not fts_query:
            return []
        fts_query_or = " OR ".join(fts_query.split())

        with self._connect() as cur:
            try:
                cur.execute(
                    "SELECT m.* FROM memories m "
                    "JOIN memories_fts fts ON m.rowid = fts.rowid "
                    "WHERE memories_fts MATCH ? AND m.is_superseded = 0 "
                    "ORDER BY rank LIMIT ?",
                    (fts_query_or, limit),
                )
                rows = cur.fetchall()
            except Exception:
                cur.execute(
                    "SELECT * FROM memories WHERE content LIKE ? AND is_superseded = 0 "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{fts_query}%", limit),
                )
                rows = cur.fetchall()

        memories = [self._row_to_memory(row) for row in rows]
        for m in memories:
            self._boost_access(m.id)
        return memories

    def search_semantic(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories using semantic vectors. Excludes superseded memories.

        If semantic search returns no results, triggers vector reconciliation
        to recover from possible failed ChromaDB writes.
        """
        try:
            embedding = get_embedding(query)
            results = self.collection.query(
                query_embeddings=[embedding],  # type: ignore[arg-type]
                n_results=limit * 2,
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            memory_ids = results["ids"][0]
            memories = [
                m
                for m in (self.get_memory(i) for i in memory_ids)
                if m is not None and not m.is_superseded
            ]

            for m in memories:
                self._boost_access(m.id)

            # If fewer results than expected for a non-trivial query, reconcile
            if len(memories) < limit and len(memory_ids) < limit:
                self.reconcile_vectors(limit=50)

            return memories[:limit]
        except Exception:
            return []

    def search_field_semantic(
        self, query: str, field: str | None = None, limit: int = 10
    ) -> list[Memory]:
        """Search using per-field vector index for better recall.

        Args:
            query: Search query
            field: Optional field filter ('trigger', 'action', 'structured_data')
            limit: Max results
        """
        try:
            embedding = get_embedding(query)
            where_filter = {"field": field} if field else None
            kwargs: dict[str, Any] = {"query_embeddings": [embedding], "n_results": limit * 2}
            if where_filter:
                kwargs["where"] = where_filter

            results = self._memories_field_collection.query(**kwargs)

            if not results["ids"] or not results["ids"][0]:
                return []

            result_metas_raw = results.get("metadatas")
            result_metas = result_metas_raw[0] if result_metas_raw and result_metas_raw[0] else []

            seen_ids = set()
            unique_memory_ids = []
            for doc_id, meta in zip(results["ids"][0], result_metas):
                mid = str(meta.get("memory_id", ""))
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    unique_memory_ids.append(mid)

            memories = [
                m
                for m in (self.get_memory(i) for i in unique_memory_ids)
                if m is not None and not m.is_superseded
            ]

            for m in memories:
                self._boost_access(m.id)

            return memories[:limit]
        except Exception:
            return []

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[Memory]:
        """Search memories using hybrid (keyword + semantic + field semantic)."""
        fts_results = self.search_fts(query, limit=limit * 2)
        fts_scores: dict[str, float] = {m.id: 1.0 / (idx + 1) for idx, m in enumerate(fts_results)}

        semantic_results = self.search_semantic(query, limit=limit * 2)
        semantic_scores: dict[str, float] = {
            m.id: 1.0 / (idx + 1) for idx, m in enumerate(semantic_results)
        }

        field_results = self.search_field_semantic(query, limit=limit)
        field_scores: dict[str, float] = {
            m.id: 0.7 / (idx + 1) for idx, m in enumerate(field_results)
        }

        all_ids = set(fts_scores.keys()) | set(semantic_scores.keys()) | set(field_scores.keys())
        combined = []
        for mid in all_ids:
            fts_s = fts_scores.get(mid, 0)
            sem_s = semantic_scores.get(mid, 0)
            field_s = field_scores.get(mid, 0)
            score = fts_weight * fts_s + (1 - fts_weight) * 0.7 * sem_s + 0.3 * field_s

            memory = self.get_memory(mid)
            if memory:
                combined.append((score, memory))

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
        """Add a connection between two memories with relationship semantics."""
        with self._connect() as cur:
            cur.execute("SELECT linked_to FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
            if not row:
                return

            connections = self._parse_connections(row["linked_to"])
            existing_targets = {c.target_id for c in connections}
            if target_id not in existing_targets:
                connections.append(
                    Connection(target_id=target_id, relationship=relationship, strength=strength)
                )
                cur.execute(
                    "UPDATE memories SET linked_to = ?, updated_at = ? WHERE id = ?",
                    (
                        self._serialize_connections(connections),
                        datetime.now(UTC).isoformat(),
                        memory_id,
                    ),
                )

    def remove_connection(self, memory_id: str, target_id: str) -> None:
        """Remove a connection from a memory."""
        with self._connect() as cur:
            cur.execute("SELECT linked_to FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
            if not row:
                return

            connections = self._parse_connections(row["linked_to"])
            connections = [c for c in connections if c.target_id != target_id]
            cur.execute(
                "UPDATE memories SET linked_to = ?, updated_at = ? WHERE id = ?",
                (
                    self._serialize_connections(connections),
                    datetime.now(UTC).isoformat(),
                    memory_id,
                ),
            )

    def get_connections(self, memory_id: str) -> list[Connection]:
        """Get all connections for a memory."""
        with self._connect() as cur:
            cur.execute("SELECT linked_to FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
            if not row:
                return []
            return self._parse_connections(row["linked_to"])

    def mark_consolidated(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        with self._connect() as cur:
            placeholders = ",".join("?" * len(memory_ids))
            cur.execute(
                f"UPDATE memories SET consolidated = 1, updated_at = ? WHERE id IN ({placeholders})",
                [datetime.now(UTC).isoformat()] + memory_ids,
            )

    def get_insights(
        self, insight_id: str | None = None, limit: int = 10
    ) -> Insight | None | list[Insight]:
        """Get a single insight by ID, or list insights."""
        if insight_id:
            with self._connect() as cur:
                cur.execute("SELECT * FROM insights WHERE id = ?", (insight_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return Insight(
                    id=row["id"],
                    summary=row["summary"],
                    domain=row["domain"],
                    linked_memories=json.loads(row["linked_memories"]),
                    confidence=row["confidence"],
                    is_superseded=bool(row["is_superseded"]),
                    superseded_by=row["superseded_by"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
        return self.list_insights(limit=limit)

    def add_insight(
        self,
        summary: str,
        linked_memories: list[str],
        confidence: float = 0.5,
        domain: str = "general",
    ) -> Insight:
        """Add a synthesized insight with deduplication."""
        now = datetime.now(UTC).isoformat()
        insight_id = hashlib.sha256(summary.encode()).hexdigest()[:16]

        with self._connect() as cur:
            cur.execute(
                "SELECT id, summary, linked_memories FROM insights WHERE domain = ? AND is_superseded = 0",
                (domain,),
            )
            existing = cur.fetchone()

            if existing:
                existing_id = existing["id"]
                existing_summary = existing["summary"]
                existing_linked = existing["linked_memories"]
                existing_words = set(existing_summary.lower().split())
                new_words = set(summary.lower().split())
                overlap = len(existing_words & new_words) / max(len(existing_words), len(new_words))

                if overlap > 0.6:
                    cur.execute(
                        "UPDATE insights SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
                        (insight_id, now, existing_id),
                    )
                    existing_linked_list = json.loads(existing_linked)
                    linked_memories = list(set(existing_linked_list + linked_memories))

            cur.execute(
                "INSERT OR REPLACE INTO insights "
                "(id, summary, domain, linked_memories, confidence, is_superseded, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (insight_id, summary, domain, json.dumps(linked_memories), confidence, now, now),
            )

        try:
            embedding = get_embedding(summary)
            self.insights_collection.upsert(
                ids=[insight_id],
                embeddings=[embedding],  # type: ignore[arg-type]
                documents=[summary],
                metadatas=[{"domain": domain, "confidence": confidence}],
            )
        except Exception:
            pass

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
        """Search insights using FTS5."""
        import re

        fts_query = re.sub(r"[^\w\s]", " ", query.strip())
        fts_query = " ".join(fts_query.split())
        if not fts_query:
            return []
        fts_query_or = " OR ".join(fts_query.split())

        with self._connect() as cur:
            try:
                cur.execute(
                    "SELECT i.* FROM insights i "
                    "JOIN insights_fts fts ON i.rowid = fts.rowid "
                    "WHERE insights_fts MATCH ? AND i.is_superseded = 0 "
                    "ORDER BY rank LIMIT ?",
                    (fts_query_or, limit),
                )
                rows = cur.fetchall()
            except Exception:
                rows = []

        return [
            Insight(
                id=row["id"],
                summary=row["summary"],
                domain=row["domain"],
                linked_memories=json.loads(row["linked_memories"]),
                confidence=row["confidence"],
                is_superseded=bool(row["is_superseded"]),
                superseded_by=row["superseded_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def search_insights_semantic(self, query: str, limit: int = 5) -> list[Insight]:
        """Search insights using semantic vectors."""
        try:
            embedding = get_embedding(query)
            results = self.insights_collection.query(
                query_embeddings=[embedding],  # type: ignore[arg-type]
                n_results=limit * 2,
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            insight_ids = results["ids"][0]
            insights = []
            with self._connect() as cur:
                placeholders = ",".join("?" * len(insight_ids))
                cur.execute(
                    f"SELECT * FROM insights WHERE id IN ({placeholders}) AND is_superseded = 0",
                    insight_ids,
                )
                rows = cur.fetchall()

            for row in rows:
                insights.append(
                    Insight(
                        id=row["id"],
                        summary=row["summary"],
                        domain=row["domain"],
                        linked_memories=json.loads(row["linked_memories"]),
                        confidence=row["confidence"],
                        is_superseded=bool(row["is_superseded"]),
                        superseded_by=row["superseded_by"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
            return insights[:limit]
        except Exception:
            return []

    def list_insights(
        self, domain: str | None = None, include_superseded: bool = False, limit: int = 20
    ) -> list[Insight]:
        """List insights with optional filtering."""
        with self._connect() as cur:
            query = "SELECT * FROM insights"
            params: list[str] = []

            conditions = []
            if not include_superseded:
                conditions.append("is_superseded = 0")
            if domain:
                conditions.append("domain = ?")
                params.append(domain)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
            params.append(str(limit))

            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            Insight(
                id=row["id"],
                summary=row["summary"],
                domain=row["domain"],
                linked_memories=json.loads(row["linked_memories"]),
                confidence=row["confidence"],
                is_superseded=bool(row["is_superseded"]),
                superseded_by=row["superseded_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def remove_insight(self, insight_id: str) -> bool:
        """Remove an insight."""
        with self._connect() as cur:
            cur.execute("DELETE FROM insights WHERE id = ?", (insight_id,))
            deleted = cur.rowcount > 0
        if deleted:
            try:
                self.insights_collection.delete(ids=[insight_id])
            except Exception:
                pass
        return deleted

    def search_all(
        self,
        query: str,
        memories_limit: int = 5,
        messages_limit: int = 5,
        insights_limit: int = 3,
        user_id: str | None = None,
    ) -> dict[str, list[Any]]:
        """Unified search across memories, messages, and insights."""
        results: dict[str, list[Any]] = {
            "memories": [],
            "messages": [],
            "insights": [],
        }

        memory_results = self.search_hybrid(query, limit=memories_limit)
        results["memories"] = memory_results

        insight_results = self.search_insights(query, limit=insights_limit)
        if not insight_results:
            insight_results = self.search_insights_semantic(query, limit=insights_limit)
        results["insights"] = insight_results

        if user_id:
            try:
                from src.storage.messages import get_conversation_store

                conv_store = get_conversation_store(user_id)
                embedding = get_embedding(query)
                message_results = conv_store.search_hybrid(query, embedding, limit=messages_limit)
                results["messages"] = [
                    {"id": m.id, "content": m.content, "role": m.role, "score": m.score}
                    for m in message_results
                ]
            except Exception:
                pass

        return results

    def get_compact_context(self, max_memories: int = 5) -> str:
        """Build compact memory context for minimal token usage (Layer 1 of progressive disclosure).

        Returns a short summary: domain counts + top triggers only.
        """
        memories = self.list_working_memories(min_confidence=0.3, limit=max_memories * 2)
        if not memories:
            return ""

        by_domain: dict[str, int] = {}
        top_memories: list[str] = []
        for m in sorted(memories, key=lambda x: (-x.confidence, -x.observations))[:max_memories]:
            domain = m.domain
            by_domain[domain] = by_domain.get(domain, 0) + 1
            source_marker = "★" if m.source == SOURCE_EXPLICIT else ""
            top_memories.append(f"{m.trigger}: {m.action}{source_marker}")

        domain_summary = ", ".join(f"{d}:{c}" for d, c in sorted(by_domain.items()))
        return f"## User Profile ({domain_summary})\n" + "\n".join(f"- {m}" for m in top_memories)

    def get_memory_context(self, detail_level: str = MEMORY_DETAIL_SUMMARY) -> str:
        """Build memory context with progressive disclosure levels.

        Args:
            detail_level: 'compact' (domain summary only), 'summary' (working memories),
                          'full' (all working memories with details)
        """
        if detail_level == MEMORY_DETAIL_COMPACT:
            return self.get_compact_context()
        elif detail_level == MEMORY_DETAIL_FULL:
            return self._get_full_context()
        else:
            return self._get_summary_context()

    def _get_summary_context(self) -> str:
        """Build summary memory context (working memories grouped by domain)."""
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
            if days_old < 7:
                recency = ""
            elif days_old > 90:
                recency = " (outdated)"
            else:
                recency = f" ({days_old}d ago)"

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

        remaining_domains = [d for d in sorted(by_domain.keys()) if d not in domain_order]
        for domain in remaining_domains:
            parts.append(f"\n### {domain.capitalize()}")
            parts.extend(by_domain[domain])

        return "\n".join(parts)

    def _get_full_context(self) -> str:
        """Build full detail context (all fields including connections and structured data)."""
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
        """Create a new conversation session for tracking."""
        import uuid

        sid = session_id or str(uuid.uuid4())
        with self._connect() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at, message_count) VALUES (?, ?, 0)",
                (sid, datetime.now(UTC).isoformat()),
            )
        return sid

    def update_session(
        self, session_id: str, message_count: int | None = None, summary: str | None = None
    ) -> None:
        """Update a session's message count and/or summary."""
        with self._connect() as cur:
            updates = []
            params: list[Any] = []

            if message_count is not None:
                updates.append("message_count = ?")
                params.append(message_count)
            if summary is not None:
                updates.append("summary = ?")
                params.append(summary)

            if updates:
                updates.append("ended_at = ?")
                params.append(datetime.now(UTC).isoformat())
                params.append(session_id)
                cur.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session details."""
        with self._connect() as cur:
            cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()

        if not row:
            return None
        return dict(row)

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List sessions ordered by start time."""
        with self._connect() as cur:
            cur.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cur.fetchall()]

    def promote_project_memory(self, memory_id: str) -> Memory | None:
        """Promote a project-scoped memory to global scope.

        Used when a memory is observed across multiple projects.
        """
        mem = self.get_memory(memory_id)
        if not mem or mem.scope == SCOPE_GLOBAL:
            return mem

        with self._connect() as cur:
            cur.execute(
                "UPDATE memories SET scope = ?, project_id = NULL, updated_at = ? WHERE id = ?",
                (SCOPE_GLOBAL, datetime.now(UTC).isoformat(), memory_id),
            )

        return self.get_memory(memory_id)

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        with self._connect() as cur:
            total = cur.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            by_domain = cur.execute(
                "SELECT domain, COUNT(*) as c FROM memories GROUP BY domain ORDER BY c DESC"
            ).fetchall()
            by_type = cur.execute(
                "SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"
            ).fetchall()
            by_source = cur.execute(
                "SELECT source, COUNT(*) as c FROM memories GROUP BY source"
            ).fetchall()
            by_scope = cur.execute(
                "SELECT scope, COUNT(*) as c FROM memories GROUP BY scope"
            ).fetchall()
            consolidated = cur.execute(
                "SELECT COUNT(*) FROM memories WHERE consolidated = 1"
            ).fetchone()[0]
            insights = cur.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            avg_confidence = cur.execute(
                "SELECT AVG(confidence) FROM memories WHERE is_superseded = 0"
            ).fetchone()[0]

        return {
            "total": total,
            "by_domain": dict(by_domain),
            "by_type": dict(by_type),
            "by_source": dict(by_source),
            "by_scope": dict(by_scope),
            "consolidated": consolidated,
            "insights": insights,
            "avg_confidence": round(avg_confidence, 3) if avg_confidence else 0,
        }

    def migrate_normalize_domains(self) -> int:
        """Migrate and normalize domain names."""
        with self._connect() as cur:
            cur.execute(
                "UPDATE memories SET domain = 'preference' WHERE domain IN ('preferences', 'preference')"
            )
            pref_count = cur.rowcount

            cur.execute(
                "UPDATE memories SET domain = 'dislikes' WHERE domain IN ('dislike', 'dislikes')"
            )
            dislike_count = cur.rowcount

        return pref_count + dislike_count


_memory_store_cache: dict[str, MemoryStore] = {}


def get_memory_store(user_id: str) -> MemoryStore:
    """Get or create memory store."""
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
