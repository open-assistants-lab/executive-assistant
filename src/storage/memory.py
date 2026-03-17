"""Memory storage using SQLite + FTS5 + ChromaDB.

Two-layer memory architecture:
- Working Memory: recent, high-confidence memories → always injected into context
- Long-term Memory: all memories, retrievable on demand

Memory types:
- preference: user wants/prefers X
- fact: factual information about user (name, location, etc)
- workflow: user's working patterns
- correction: user corrections (no, do A not B)
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from src.tools.apps.storage import get_embedding

# Confidence defaults (fixed from old instincts)
DEFAULT_CONFIDENCE = 0.2
MAX_CONFIDENCE = 0.7  # Cap auto-learned at 0.7

# Memory types
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

# Source types
SOURCE_EXPLICIT = "explicit"  # User explicitly set via profile
SOURCE_LEARNED = "learned"  # Auto-learned from conversation


@dataclass
class Memory:
    """A learned memory about the user."""

    id: str
    trigger: str
    action: str
    confidence: float
    domain: str
    source: str  # explicit or learned
    memory_type: str  # preference, fact, workflow, correction
    observations: int
    created_at: datetime
    updated_at: datetime
    importance: float = 5.0
    consolidated: bool = False
    linked_to: list[str] = field(default_factory=list)
    superseded_by: str | None = None  # ID of memory that corrected this
    is_superseded: bool = False  # Mark as old/corrected


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
        └── vectors/     # ChromaDB
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/memory")
        base_path.mkdir(parents=True, exist_ok=True)

        self.db_path = str((base_path / "memory.db").resolve())
        self.vector_path = str((base_path / "vectors").resolve())

        self._init_db()
        self._init_vector_store()

    def _init_db(self) -> None:
        """Initialize SQLite with FTS5."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")

        conn.execute("""
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
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                trigger,
                action,
                content='memories',
                content_rowid='rowid'
            )
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, trigger, action)
                VALUES (new.rowid, new.trigger, new.action);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, trigger, action)
                VALUES ('delete', old.rowid, old.trigger, old.action);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, trigger, action)
                VALUES ('delete', old.rowid, old.trigger, old.action);
                INSERT INTO memories_fts(rowid, trigger, action)
                VALUES (new.rowid, new.trigger, new.action);
            END
                """)

        # Insights table
        conn.execute("""
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

        # Migration: Add missing columns to existing databases
        try:
            conn.execute("ALTER TABLE insights ADD COLUMN domain TEXT DEFAULT 'general'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE insights ADD COLUMN is_superseded INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE insights ADD COLUMN superseded_by TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE insights ADD COLUMN updated_at TEXT")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    def _init_vector_store(self) -> None:
        """Initialize ChromaDB."""
        self.chroma = chromadb.PersistentClient(
            path=self.vector_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            name="memories",
            metadata={"user_id": self.user_id},
        )

    def _generate_id(self, trigger: str, action: str) -> str:
        """Generate unique ID from trigger and action."""
        content = f"{trigger}:{action}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain to prevent duplicates."""
        domain = domain.lower().strip()
        # Fix common normalization issues
        if domain in ("preferences", "preference"):
            return "preference"
        if domain in ("lesson", "lessons"):
            return "lesson"
        if domain in ("dislike", "dislikes"):
            return "dislikes"
        return domain

    def maybe_decay_confidence(self) -> None:
        """Decrease confidence for memories not observed recently."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        cursor.execute(
            """
            UPDATE memories
            SET confidence = MAX(0.2, confidence - 0.1),
                updated_at = ?
            WHERE updated_at < ? AND source = 'learned'
        """,
            (datetime.now(UTC).isoformat(), thirty_days_ago.isoformat()),
        )

        conn.commit()
        conn.close()

    def add_memory(
        self,
        trigger: str,
        action: str,
        confidence: float = DEFAULT_CONFIDENCE,
        domain: str = "preference",
        source: str = SOURCE_LEARNED,
        memory_type: str = MEMORY_TYPE_PREFERENCE,
        importance: float = 5.0,
        is_update: bool = False,  # Force update of existing
    ) -> Memory:
        """Add or update a memory.

        If is_update=True, will update existing memory with same trigger pattern
        instead of creating a new one.
        """
        self.maybe_decay_confidence()

        domain = self._normalize_domain(domain)

        now = datetime.now(UTC).isoformat()
        memory_id = self._generate_id(trigger, action)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check for existing memory by exact ID match
        cursor.execute("SELECT id, observations FROM memories WHERE id = ?", (memory_id,))
        existing = cursor.fetchone()

        if existing and is_update:
            # Update existing memory
            old_id, observations = existing
            cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
            cursor.execute(
                """
                UPDATE memories SET
                    action = ?,
                    confidence = MIN(?, confidence + 0.1),
                    observations = observations + 1,
                    updated_at = ?,
                    is_superseded = 0,
                    superseded_by = NULL
                WHERE id = ?
                """,
                (action, cap, now, memory_id),
            )
        elif existing:
            # Old behavior: increment observations
            old_id, observations = existing
            cap = MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
            cursor.execute(
                """
                UPDATE memories SET
                    confidence = MIN(?, confidence + 0.05),
                    observations = observations + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (cap, now, memory_id),
            )
        elif is_update:
            # Check for similar memory by trigger pattern and domain, update it
            cursor.execute(
                "SELECT id, action FROM memories WHERE trigger = ? AND domain = ? AND is_superseded = 0 LIMIT 1",
                (trigger, domain),
            )
            similar = cursor.fetchone()

            if similar:
                # Update similar memory instead
                memory_id = similar[0]
                similar[1]
                # Mark old as superseded
                cursor.execute(
                    "UPDATE memories SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
                    (memory_id, now, memory_id),
                )
                # Insert new with updated ID
                initial_confidence = min(
                    confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                )
                cursor.execute(
                    """
                    INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, importance, observations, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
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
                    ),
                )
            else:
                # Create new
                initial_confidence = min(
                    confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
                )
                cursor.execute(
                    """
                    INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, importance, observations, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
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
                    ),
                )
        else:
            # Create new
            initial_confidence = min(
                confidence, MAX_CONFIDENCE if source == SOURCE_LEARNED else 1.0
            )
            cursor.execute(
                """
                INSERT INTO memories (id, trigger, action, confidence, domain, source, memory_type, importance, observations, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
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
                ),
            )

        conn.commit()
        conn.close()

        self._update_vector(memory_id, trigger, action)

        result = self.get_memory(memory_id)
        if result is None:
            raise RuntimeError(f"Failed to create memory: {memory_id}")
        return result

    def find_and_update(
        self,
        trigger_pattern: str,
        new_action: str,
        domain: str | None = None,
        memory_type: str | None = None,
    ) -> Memory | None:
        """Find existing memory by trigger pattern and update it, or create new.

        Uses FTS to find similar triggers and updates if found.
        """
        # Search for existing memory with similar trigger
        existing = self.search_fts(trigger_pattern, limit=5)

        # Filter by domain if specified
        if domain:
            existing = [m for m in existing if m.domain == domain]

        if existing:
            # Update the most confident one
            existing_mem = existing[0]
            return self.update_memory(existing_mem.id, trigger_pattern, new_action)

        # Not found, create new
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
    ) -> Memory | None:
        """Update an existing memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        # Build update query
        updates = ["updated_at = ?", "observations = observations + 1"]
        params = [datetime.now(UTC).isoformat()]

        if new_trigger:
            updates.append("trigger = ?")
            params.append(new_trigger)
        if new_action:
            updates.append("action = ?")
            params.append(new_action)
        if new_domain:
            updates.append("domain = ?")
            params.append(new_domain)

        params.append(memory_id)

        cursor.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        conn.close()

        # Update vector
        if new_trigger or new_action:
            trigger = new_trigger or row["trigger"]
            action = new_action or row["action"]
            self._update_vector(memory_id, trigger, action)

        return self.get_memory(memory_id)

    def supersede_memory(self, old_id: str, new_id: str) -> None:
        """Mark old memory as superseded by new memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE memories SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_id, datetime.now(UTC).isoformat(), old_id),
        )
        conn.commit()
        conn.close()

    def _update_vector(self, memory_id: str, trigger: str, action: str) -> None:
        """Update ChromaDB vector."""
        try:
            embedding = get_embedding(f"{trigger}: {action}")
            self.collection.upsert(
                ids=[memory_id],
                embeddings=[embedding],  # type: ignore[arg-type]
                documents=[f"{trigger}: {action}"],
            )
        except Exception:
            pass

    def get_memory(self, memory_id: str) -> Memory | None:
        """Get a memory by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

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
            linked_to=json.loads(row["linked_to"]),
            observations=row["observations"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            superseded_by=row["superseded_by"],
            is_superseded=bool(row["is_superseded"]),
        )

    def list_memories(
        self,
        domain: str | None = None,
        memory_type: str | None = None,
        source: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
        include_superseded: bool = False,
    ) -> list[Memory]:
        """List memories with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM memories WHERE confidence >= ?"
        params: list[float | str] = [min_confidence]

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

        query += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            Memory(
                id=row["id"],
                trigger=row["trigger"],
                action=row["action"],
                confidence=row["confidence"],
                domain=row["domain"],
                source=row["source"],
                memory_type=row["memory_type"],
                importance=row["importance"],
                consolidated=bool(row["consolidated"]),
                linked_to=json.loads(row["linked_to"]),
                observations=row["observations"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                superseded_by=row["superseded_by"],
                is_superseded=bool(row["is_superseded"]),
            )
            for row in rows
        ]

    def list_working_memories(self, min_confidence: float = 0.3, limit: int = 20) -> list[Memory]:
        """List working memories - high confidence, recently updated."""
        return self.list_memories(
            min_confidence=min_confidence,
            limit=limit,
        )

    def list_longterm_memories(self, min_confidence: float = 0.0, limit: int = 100) -> list[Memory]:
        """List all long-term memories - can be retrieved on demand."""
        return self.list_memories(
            min_confidence=min_confidence,
            limit=limit,
        )

    def remove_memory(self, memory_id: str) -> bool:
        """Remove a memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            try:
                self.collection.delete(ids=[memory_id])
            except Exception:
                pass

        return deleted

    def search_fts(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories using FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT i.* FROM memories i
            JOIN memories_fts fts ON i.rowid = fts.rowid
            WHERE memories_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (query, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        return [
            Memory(
                id=row["id"],
                trigger=row["trigger"],
                action=row["action"],
                confidence=row["confidence"],
                domain=row["domain"],
                source=row["source"],
                memory_type=row["memory_type"],
                importance=row["importance"],
                consolidated=bool(row["consolidated"]),
                linked_to=json.loads(row["linked_to"]),
                observations=row["observations"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def search_semantic(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories using semantic vectors."""
        try:
            embedding = get_embedding(query)
            results = self.collection.query(
                query_embeddings=[embedding],  # type: ignore[arg-type]
                n_results=limit,
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            memory_ids = results["ids"][0]
            return [i for i in (self.get_memory(i) for i in memory_ids) if i is not None]
        except Exception:
            return []

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[Memory]:
        """Search memories using hybrid (keyword + semantic)."""
        fts_results = self.search_fts(query, limit=limit * 2)
        fts_scores: dict[str, float] = {i.id: 1.0 / (idx + 1) for idx, i in enumerate(fts_results)}

        semantic_results = self.search_semantic(query, limit=limit * 2)
        semantic_scores: dict[str, float] = {
            i.id: 1.0 / (idx + 1) for idx, i in enumerate(semantic_results)
        }

        all_ids = set(fts_scores.keys()) | set(semantic_scores.keys())
        combined = []

        for iid in all_ids:
            score = fts_weight * fts_scores.get(iid, 0) + (1 - fts_weight) * semantic_scores.get(
                iid, 0
            )
            memory = self.get_memory(iid)
            if memory:
                combined.append((score, memory))

        combined.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in combined[:limit]]

    def find_similar(self, memory_id: str, limit: int = 5) -> list[Memory]:
        """Find similar memories using vector similarity."""
        memory = self.get_memory(memory_id)
        if not memory:
            return []

        query = f"{memory.trigger}: {memory.action}"
        results = self.search_semantic(query, limit=limit + 1)

        # Filter out self
        return [m for m in results if m.id != memory_id][:limit]

    def add_connection(self, memory_id: str, linked_id: str) -> None:
        """Add a connection between two memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT linked_to FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return

        linked_to = json.loads(row[0])
        if linked_id not in linked_to:
            linked_to.append(linked_id)
            cursor.execute(
                "UPDATE memories SET linked_to = ?, updated_at = ? WHERE id = ?",
                (json.dumps(linked_to), datetime.now(UTC).isoformat(), memory_id),
            )

        conn.commit()
        conn.close()

    def mark_consolidated(self, memory_ids: list[str]) -> None:
        """Mark memories as consolidated."""
        if not memory_ids:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(memory_ids))
        cursor.execute(
            f"UPDATE memories SET consolidated = 1, updated_at = ? WHERE id IN ({placeholders})",
            [datetime.now(UTC).isoformat()] + memory_ids,
        )

        conn.commit()
        conn.close()

    def get_insights(self, limit: int = 10) -> list[Insight]:
        """Get stored insights."""
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

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()

        # Check for existing similar insight
        cursor.execute(
            "SELECT id, summary, linked_memories FROM insights WHERE domain = ? AND is_superseded = 0",
            (domain,),
        )
        existing = cursor.fetchone()

        if existing:
            existing_id, existing_summary, existing_linked = existing
            # Check similarity (simple word overlap)
            existing_words = set(existing_summary.lower().split())
            new_words = set(summary.lower().split())
            overlap = len(existing_words & new_words) / max(len(existing_words), len(new_words))

            if overlap > 0.6:  # >60% word overlap = similar
                # Mark old as superseded
                cursor.execute(
                    "UPDATE insights SET is_superseded = 1, superseded_by = ?, updated_at = ? WHERE id = ?",
                    (insight_id, now, existing_id),
                )
                # Merge linked memories
                existing_linked_list = json.loads(existing_linked)
                merged_linked = list(set(existing_linked_list + linked_memories))
                linked_memories = merged_linked

        # Insert new/updated insight
        cursor.execute(
            """INSERT OR REPLACE INTO insights
               (id, summary, domain, linked_memories, confidence, is_superseded, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (insight_id, summary, domain, json.dumps(linked_memories), confidence, now, now),
        )

        conn.commit()
        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT i.* FROM insights i
            JOIN insights_fts fts ON i.rowid = fts.rowid
            WHERE insights_fts MATCH ? AND i.is_superseded = 0
            ORDER BY rank
            LIMIT ?
        """,
            (query, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

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

    def list_insights(
        self, domain: str | None = None, include_superseded: bool = False, limit: int = 20
    ) -> list[Insight]:
        """List insights with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM insights"
        params: list[str] = []

        if not include_superseded:
            query += " WHERE is_superseded = 0"

        if domain:
            query += " AND domain = ?" if not include_superseded else " WHERE domain = ?"
            params.append(domain)

        query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
        params.append(str(limit))

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

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

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        total = cursor.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_domain = cursor.execute(
            "SELECT domain, COUNT(*) as c FROM memories GROUP BY domain ORDER BY c DESC"
        ).fetchall()
        by_type = cursor.execute(
            "SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"
        ).fetchall()
        by_source = cursor.execute(
            "SELECT source, COUNT(*) as c FROM memories GROUP BY source"
        ).fetchall()
        consolidated = cursor.execute(
            "SELECT COUNT(*) FROM memories WHERE consolidated = 1"
        ).fetchone()[0]
        insights = cursor.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
        conn.close()

        return {
            "total": total,
            "by_domain": dict(by_domain),
            "by_type": dict(by_type),
            "by_source": dict(by_source),
            "consolidated": consolidated,
            "insights": insights,
        }

    def migrate_normalize_domains(self) -> int:
        """Migrate and normalize domain names. Returns count of updated records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Normalize preference/preferences
        cursor.execute(
            "UPDATE memories SET domain = 'preference' WHERE domain IN ('preferences', 'preference')"
        )
        pref_count = cursor.rowcount

        # Normalize dislikes
        cursor.execute(
            "UPDATE memories SET domain = 'dislikes' WHERE domain IN ('dislike', 'dislikes')"
        )
        dislike_count = cursor.rowcount

        conn.commit()
        conn.close()

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
    "MemoryStore",
    "get_memory_store",
    "MEMORY_TYPE_PREFERENCE",
    "MEMORY_TYPE_FACT",
    "MEMORY_TYPE_WORKFLOW",
    "MEMORY_TYPE_CORRECTION",
    "SOURCE_EXPLICIT",
    "SOURCE_LEARNED",
    "DEFAULT_CONFIDENCE",
    "MAX_CONFIDENCE",
]
