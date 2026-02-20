"""Conversation storage using SQLite + FTS5 + ChromaDB."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import chromadb
import chromadb.config

from src.config import get_settings


@dataclass
class Message:
    """A single message in the conversation."""

    id: int
    ts: datetime
    role: str
    content: str
    metadata: dict | None = None


@dataclass
class SearchResult:
    """Search result with score."""

    id: int
    content: str
    ts: datetime
    role: str
    score: float


class ConversationStore:
    """Manages conversation storage (messages only).

    Structure:
        /data/users/{user_id}/.conversation/
        ├── messages.db  # SQLite + FTS5
        └── vectors/    # ChromaDB for semantic search
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        settings = get_settings()
        config = settings.memory

        base_path = Path(config.messages.path.format(user_id=user_id)).parent
        base_path.mkdir(parents=True, exist_ok=True)

        self.messages_db_path = str((base_path / "messages.db").resolve())
        self.vector_path = str((base_path / "vectors").resolve())

        self._init_messages_db()
        self._init_vector_store()

    def _init_messages_db(self) -> None:
        """Initialize messages SQLite with FTS5."""
        conn = sqlite3.connect(self.messages_db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSON
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)")

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='id'
            )
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        conn.commit()
        conn.close()

    def _init_vector_store(self):
        """Initialize ChromaDB for vector search."""
        Path(self.vector_path).mkdir(parents=True, exist_ok=True)
        self.chroma = chromadb.PersistentClient(
            path=self.vector_path,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            f"messages_{self.user_id}",
            metadata={"user_id": self.user_id},
        )

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> int:
        """Add a message to the conversation."""
        ts = datetime.now().isoformat()
        conn = sqlite3.connect(self.messages_db_path)
        cursor = conn.execute(
            "INSERT INTO messages (ts, role, content, metadata) VALUES (?, ?, ?, ?)",
            [ts, role, content, json.dumps(metadata) if metadata else None],
        )
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return msg_id

    def add_message_with_embedding(
        self, role: str, content: str, embedding: list[float], metadata: dict | None = None
    ) -> int:
        """Add a message with vector embedding."""
        ts = datetime.now().isoformat()
        conn = sqlite3.connect(self.messages_db_path)
        cursor = conn.execute(
            "INSERT INTO messages (ts, role, content, metadata) VALUES (?, ?, ?, ?)",
            [ts, role, content, json.dumps(metadata) if metadata else None],
        )
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.collection.add(
            ids=[str(msg_id)],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"role": role, "ts": ts}],
        )
        return msg_id

    def search_keyword(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Keyword search using FTS5."""
        if not query:
            return []

        fts_query = query.replace("'", "''")
        conn = sqlite3.connect(self.messages_db_path)
        cursor = conn.execute(
            "SELECT m.id, m.content, m.ts, m.role, bm25(messages_fts) as score FROM messages_fts f JOIN messages m ON m.id = f.rowid WHERE messages_fts MATCH ? ORDER BY score LIMIT ?",
            [fts_query, limit],
        )
        results = []
        for row in cursor.fetchall():
            results.append(
                SearchResult(
                    id=row[0],
                    content=row[1],
                    ts=datetime.fromisoformat(row[2]),
                    role=row[3],
                    score=row[4],
                )
            )
        conn.close()
        return results

    def search_vector(self, query_embedding: list[float], limit: int = 10) -> list[SearchResult]:
        """Vector search using ChromaDB."""
        if not query_embedding:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        search_results = []
        for i, msg_id in enumerate(results["ids"][0]):
            content = results["documents"][0][i]
            distance = results["distances"][0][i] if "distances" in results else 0
            similarity = 1.0 - distance

            conn = sqlite3.connect(self.messages_db_path)
            cursor = conn.execute("SELECT id, ts, role FROM messages WHERE id = ?", [int(msg_id)])
            row = cursor.fetchone()
            conn.close()

            if row:
                search_results.append(
                    SearchResult(
                        id=row[0],
                        content=content,
                        ts=datetime.fromisoformat(row[1]),
                        role=row[2],
                        score=similarity,
                    )
                )

        return search_results

    def search_hybrid(
        self,
        query: str,
        query_embedding: list[float],
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.3,
    ) -> list[SearchResult]:
        """Combined keyword + vector + recency search."""
        now = datetime.now()

        fts_results = {
            r.id: (r, 1.0 / (abs(r.score) + 1)) for r in self.search_keyword(query, limit * 2)
        }
        vec_results = {r.id: (r, r.score) for r in self.search_vector(query_embedding, limit * 2)}

        all_ids = set(fts_results.keys()) | set(vec_results.keys())
        combined = []
        for msg_id in all_ids:
            fts_score = fts_results.get(msg_id, (None, 0))[1]
            vec_score = vec_results.get(msg_id, (None, 0))[1]

            # Relevance score (keyword + vector)
            relevance = fts_weight * fts_score + (1 - fts_weight) * vec_score

            # Get timestamp for recency
            result = fts_results.get(msg_id, vec_results.get(msg_id, (None, 0)))[0]
            if result:
                days_ago = (now - result.ts).days
                recency = 1.0 / (1 + days_ago / 30)  # Decay over months
            else:
                recency = 0

            # Combined score: relevance + recency
            combined_score = (relevance * (1 - recency_weight)) + (recency * recency_weight)

            if result:
                combined.append(
                    SearchResult(
                        id=result.id,
                        content=result.content,
                        ts=result.ts,
                        role=result.role,
                        score=combined_score,
                    )
                )

        combined.sort(key=lambda x: x.score, reverse=True)
        return combined[:limit]

    def get_messages(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages within a date range."""
        conn = sqlite3.connect(self.messages_db_path)

        query = "SELECT id, ts, role, content, metadata FROM messages"
        params = []

        if start_date or end_date:
            query += " WHERE "
            conditions = []
            if start_date:
                conditions.append("ts >= ?")
                params.append(datetime.combine(start_date, datetime.min.time()).isoformat())
            if end_date:
                conditions.append("ts <= ?")
                params.append(datetime.combine(end_date, datetime.max.time()).isoformat())
            query += " AND ".join(conditions)

        query += " ORDER BY ts ASC"

        if limit:
            query += f" LIMIT {limit}"

        result = conn.execute(query, params).fetchall()
        conn.close()

        return [
            Message(
                id=row[0],
                ts=datetime.fromisoformat(row[1]),
                role=row[2],
                content=row[3],
                metadata=json.loads(row[4]) if row[4] else None,
            )
            for row in result
        ]

    def get_recent_messages(self, count: int = 100) -> list[Message]:
        """Get N most recent messages."""
        conn = sqlite3.connect(self.messages_db_path)
        result = conn.execute(
            "SELECT id, ts, role, content, metadata FROM messages ORDER BY ts DESC LIMIT ?",
            [count],
        ).fetchall()
        conn.close()

        messages = [
            Message(
                id=row[0],
                ts=datetime.fromisoformat(row[1]),
                role=row[2],
                content=row[3],
                metadata=json.loads(row[4]) if row[4] else None,
            )
            for row in result
        ]
        return list(reversed(messages))

    def count_messages(self, start_date: date | None = None, end_date: date | None = None) -> int:
        """Count messages in a date range."""
        conn = sqlite3.connect(self.messages_db_path)

        query = "SELECT COUNT(*) FROM messages"
        params = []

        if start_date or end_date:
            query += " WHERE "
            conditions = []
            if start_date:
                conditions.append("ts >= ?")
                params.append(datetime.combine(start_date, datetime.min.time()).isoformat())
            if end_date:
                conditions.append("ts <= ?")
                params.append(datetime.combine(end_date, datetime.max.time()).isoformat())
            query += " AND ".join(conditions)

        result = conn.execute(query, params).fetchone()
        conn.close()
        return result[0] if result else 0


_stores: dict[str, ConversationStore] = {}


def get_conversation_store(user_id: str = "default") -> ConversationStore:
    """Get conversation store for a user."""
    if user_id not in _stores:
        _stores[user_id] = ConversationStore(user_id)
    return _stores[user_id]
