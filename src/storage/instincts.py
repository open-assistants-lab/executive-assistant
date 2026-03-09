"""Instincts storage using SQLite + FTS5 + ChromaDB."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import chromadb
from chromadb.config import Settings

from src.tools.apps.storage import get_embedding


@dataclass
class Instinct:
    """A learned behavioral pattern."""

    id: str
    trigger: str
    action: str
    confidence: float
    domain: str
    source: str
    observations: int
    created_at: datetime
    updated_at: datetime


class InstinctsStore:
    """Manages instincts storage.

    Structure:
        /data/users/{user_id}/instincts/
        ├── instincts.db    # SQLite + FTS5
        └── vectors/       # ChromaDB
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/instincts")
        base_path.mkdir(parents=True, exist_ok=True)

        self.db_path = str((base_path / "instincts.db").resolve())
        self.vector_path = str((base_path / "vectors").resolve())

        self._init_db()
        self._init_vector_store()

    def _init_db(self) -> None:
        """Initialize SQLite with FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS instincts (
                id TEXT PRIMARY KEY,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL DEFAULT 0.3,
                domain TEXT DEFAULT 'preference',
                source TEXT DEFAULT 'auto-learned',
                observations INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS instincts_fts USING fts5(
                trigger,
                action,
                content='instincts',
                content_rowid='rowid'
            )
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS instincts_ai AFTER INSERT ON instincts BEGIN
                INSERT INTO instincts_fts(rowid, trigger, action)
                VALUES (new.rowid, new.trigger, new.action);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS instincts_ad AFTER DELETE ON instincts BEGIN
                INSERT INTO instincts_fts(instincts_fts, rowid, trigger, action)
                VALUES ('delete', old.rowid, old.trigger, old.action);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS instincts_au AFTER UPDATE ON instincts BEGIN
                INSERT INTO instincts_fts(instincts_fts, rowid, trigger, action)
                VALUES ('delete', old.rowid, old.trigger, old.action);
                INSERT INTO instincts_fts(rowid, trigger, action)
                VALUES (new.rowid, new.trigger, new.action);
            END
        """)

        conn.commit()
        conn.close()

    def _init_vector_store(self) -> None:
        """Initialize ChromaDB."""
        self.chroma = chromadb.PersistentClient(
            path=self.vector_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            name="instincts",
            metadata={"user_id": self.user_id},
        )

    def _generate_id(self, trigger: str, action: str) -> str:
        """Generate unique ID from trigger and action."""
        content = f"{trigger}:{action}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def maybe_decay_confidence(self) -> None:
        """Decrease confidence for instincts not observed recently."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        cursor.execute(
            """
            UPDATE instincts
            SET confidence = MAX(0.3, confidence - 0.1),
                updated_at = ?
            WHERE updated_at < ?
        """,
            (datetime.now(UTC).isoformat(), thirty_days_ago.isoformat()),
        )

        conn.commit()
        conn.close()

    def add_instinct(
        self,
        trigger: str,
        action: str,
        confidence: float = 0.3,
        domain: str = "preference",
        source: str = "auto-learned",
    ) -> Instinct:
        """Add or update an instinct."""
        self.maybe_decay_confidence()

        now = datetime.now(UTC).isoformat()
        instinct_id = self._generate_id(trigger, action)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, observations FROM instincts WHERE id = ?", (instinct_id,))
        existing = cursor.fetchone()

        if existing:
            old_id, observations = existing
            cursor.execute(
                """
                UPDATE instincts SET
                    confidence = MIN(0.9, confidence + 0.05),
                    observations = observations + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, instinct_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO instincts (id, trigger, action, confidence, domain, source, observations, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (instinct_id, trigger, action, confidence, domain, source, now, now),
            )

        conn.commit()
        conn.close()

        self._update_vector(instinct_id, trigger, action)

        result = self.get_instinct(instinct_id)
        if result is None:
            raise RuntimeError(f"Failed to create instinct: {instinct_id}")
        return result

    def _update_vector(self, instinct_id: str, trigger: str, action: str) -> None:
        """Update ChromaDB vector."""
        try:
            embedding = get_embedding(f"{trigger}: {action}")
            self.collection.upsert(
                ids=[instinct_id],
                embeddings=[embedding],  # type: ignore[arg-type]
                documents=[f"{trigger}: {action}"],
            )
        except Exception:
            pass

    def get_instinct(self, instinct_id: str) -> Instinct | None:
        """Get an instinct by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM instincts WHERE id = ?", (instinct_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Instinct(
            id=row["id"],
            trigger=row["trigger"],
            action=row["action"],
            confidence=row["confidence"],
            domain=row["domain"],
            source=row["source"],
            observations=row["observations"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_instincts(
        self,
        domain: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Instinct]:
        """List instincts with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM instincts WHERE confidence >= ?"
        params: list[float | str] = [min_confidence]

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        query += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            Instinct(
                id=row["id"],
                trigger=row["trigger"],
                action=row["action"],
                confidence=row["confidence"],
                domain=row["domain"],
                source=row["source"],
                observations=row["observations"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def remove_instinct(self, instinct_id: str) -> bool:
        """Remove an instinct."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM instincts WHERE id = ?", (instinct_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            try:
                self.collection.delete(ids=[instinct_id])
            except Exception:
                pass

        return deleted

    def search_fts(self, query: str, limit: int = 10) -> list[Instinct]:
        """Search instincts using FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT i.* FROM instincts i
            JOIN instincts_fts fts ON i.rowid = fts.rowid
            WHERE instincts_fts MATCH ?
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
            Instinct(
                id=row["id"],
                trigger=row["trigger"],
                action=row["action"],
                confidence=row["confidence"],
                domain=row["domain"],
                source=row["source"],
                observations=row["observations"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def search_semantic(self, query: str, limit: int = 10) -> list[Instinct]:
        """Search instincts using semantic vectors."""
        try:
            embedding = get_embedding(query)
            results = self.collection.query(
                query_embeddings=[embedding],  # type: ignore[arg-type]
                n_results=limit,
            )

            if not results["ids"] or not results["ids"][0]:
                return []

            instinct_ids = results["ids"][0]
            return [i for i in (self.get_instinct(i) for i in instinct_ids) if i is not None]
        except Exception:
            return []

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[Instinct]:
        """Search instincts using hybrid (keyword + semantic)."""
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
            instinct = self.get_instinct(iid)
            if instinct:
                combined.append((score, instinct))

        combined.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in combined[:limit]]


_instincts_store_cache: dict[str, InstinctsStore] = {}


def get_instincts_store(user_id: str) -> InstinctsStore:
    """Get or create instincts store."""
    if user_id not in _instincts_store_cache:
        _instincts_store_cache[user_id] = InstinctsStore(user_id)
    return _instincts_store_cache[user_id]


__all__ = ["InstinctsStore", "Instinct", "get_instincts_store"]
