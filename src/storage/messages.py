"""Conversation storage using SQLite + FTS5 + ChromaDB."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import chromadb

from src.tools.apps.storage import get_embedding


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
        /data/users/{user_id}/messages/
        ├── messages.db  # SQLite + FTS5
        └── vectors/    # ChromaDB for semantic search
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/messages")
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

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
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
        """Add a message to the conversation with auto-generated embedding."""
        ts = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(self.messages_db_path)
        cursor = conn.execute(
            "INSERT INTO messages (ts, role, content, metadata) VALUES (?, ?, ?, ?)",
            [ts, role, content, json.dumps(metadata) if metadata else None],
        )
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Auto-generate embedding and add to ChromaDB
        embedding = get_embedding(content)
        self.collection.add(
            ids=[str(msg_id)],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"role": role, "ts": ts}],
        )
        return msg_id

    def add_message_with_embedding(
        self, role: str, content: str, embedding: list[float], metadata: dict | None = None
    ) -> int:
        """Add a message with vector embedding."""
        ts = datetime.now(UTC).isoformat()
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

        import re

        fts_query = query.strip()
        # Remove characters that FTS5 cannot handle in MATCH queries
        # Keep letters, digits, spaces, and hyphens between words
        fts_query = re.sub(r"[^\w\s]", " ", fts_query)
        # Collapse multiple spaces
        fts_query = " ".join(fts_query.split())

        if not fts_query:
            return []

        # Use OR operator so each word is matched independently
        # This handles natural language queries like "what degree did I graduate with"
        fts_query_or = " OR ".join(fts_query.split())

        conn = sqlite3.connect(self.messages_db_path)
        try:
            cursor = conn.execute(
                "SELECT m.id, m.content, m.ts, m.role, bm25(messages_fts) as score "
                "FROM messages_fts f JOIN messages m ON m.id = f.rowid "
                "WHERE messages_fts MATCH ? ORDER BY score LIMIT ?",
                [fts_query_or, limit],
            )
            results = [
                SearchResult(
                    id=row[0],
                    content=row[1],
                    ts=datetime.fromisoformat(row[2]),
                    role=row[3],
                    score=row[4],
                )
                for row in cursor.fetchall()
            ]
        except Exception:
            # Fallback: if OR query fails, try simple phrase match
            try:
                cursor = conn.execute(
                    "SELECT m.id, m.content, m.ts, m.role, 0.0 as score "
                    "FROM messages m WHERE m.content LIKE ? ORDER BY m.ts DESC LIMIT ?",
                    [f"%{fts_query}%", limit],
                )
                results = [
                    SearchResult(
                        id=row[0],
                        content=row[1],
                        ts=datetime.fromisoformat(row[2]),
                        role=row[3],
                        score=row[4],
                    )
                    for row in cursor.fetchall()
                ]
            except Exception:
                results = []
        finally:
            conn.close()

        return results

    def search_vector(self, query_embedding: list[float], limit: int = 10) -> list[SearchResult]:
        """Vector search using ChromaDB. Returns results with similarity scores."""
        if not query_embedding:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=limit,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        # Batch fetch message info from SQLite instead of N+1 queries
        msg_ids = [int(mid) for mid in results["ids"][0]]
        conn = sqlite3.connect(self.messages_db_path)
        placeholders = ",".join("?" * len(msg_ids))
        rows = conn.execute(
            f"SELECT id, ts, role FROM messages WHERE id IN ({placeholders})",
            msg_ids,
        ).fetchall()
        conn.close()
        id_to_row = {row[0]: row for row in rows}

        search_results = []
        for i, msg_id in enumerate(results["ids"][0]):
            if int(msg_id) not in id_to_row:
                continue
            row = id_to_row[int(msg_id)]
            content = results["documents"][0][i]
            distance = results["distances"][0][i] if "distances" in results else 0
            # Cosine distance to similarity: 1-dist for cosine, clip to [0,1]
            similarity = max(0.0, 1.0 - distance)

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
        now = datetime.now(UTC)

        fts_results_raw = self.search_keyword(query, limit * 2)
        vec_results_raw = self.search_vector(query_embedding, limit * 2)

        # Normalize FTS scores (BM25 is negative, best=closer to 0)
        # Convert to [0, 1]: rank-based normalization
        fts_results: dict[int, tuple[SearchResult, float]] = {}
        if fts_results_raw:
            # BM25 scores are negative; closer to 0 = better
            # Normalize: best result gets 1.0, others proportional
            best_fts = max(r.score for r in fts_results_raw)
            worst_fts = min(r.score for r in fts_results_raw)
            fts_range = best_fts - worst_fts if best_fts != worst_fts else 1.0
            for rank, r in enumerate(fts_results_raw):
                # Use rank-based score: 1/(rank+1) for robustness
                # plus a quality bonus based on BM25 score
                normalized = 1.0 / (rank + 1)
                fts_results[r.id] = (r, normalized)

        # Normalize vector scores (distance → similarity, then rank-based)
        vec_results: dict[int, tuple[SearchResult, float]] = {}
        if vec_results_raw:
            for rank, r in enumerate(vec_results_raw):
                normalized = 1.0 / (rank + 1)
                vec_results[r.id] = (r, normalized)

        all_ids = set(fts_results.keys()) | set(vec_results.keys())
        combined = []
        for msg_id in all_ids:
            fts_score = fts_results.get(msg_id, (None, 0))[1]
            vec_score = vec_results.get(msg_id, (None, 0))[1]

            # Relevance score: weighted combination of normalized scores
            relevance = fts_weight * fts_score + (1 - fts_weight) * vec_score

            # Get timestamp for recency
            fts_result = fts_results.get(msg_id, (None, 0))[0]
            vec_result = vec_results.get(msg_id, (None, 0))[0]
            result = fts_result or vec_result
            if result:
                days_ago = max((now - result.ts).days, 0)
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

    def get_messages_with_summary(self, limit: int = 50) -> list[Message]:
        """Get messages, handling summarization.

        If a summary exists (role='summary'), load:
        - The summary message
        - All messages after the summary

        Otherwise, load last N messages (standard behavior).
        """
        conn = sqlite3.connect(self.messages_db_path)

        # Check if summary exists
        summary_row = conn.execute(
            "SELECT id FROM messages WHERE role = 'summary' ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if not summary_row:
            # No summary - use old behavior
            conn.close()
            return self.get_recent_messages(limit)

        summary_id = summary_row[0]

        # Load summary + all messages after it
        result = conn.execute(
            """SELECT id, ts, role, content, metadata FROM messages
               WHERE id >= ? ORDER BY id ASC""",
            [summary_id],
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
        return messages

    def add_summary_message(self, content: str) -> int:
        """Add a summary message to the conversation.

        Args:
            content: The summary content

        Returns:
            The ID of the inserted summary message
        """
        conn = sqlite3.connect(self.messages_db_path)
        cursor = conn.execute(
            """INSERT INTO messages (ts, role, content, metadata)
               VALUES (?, 'summary', ?, NULL)""",
            [datetime.now(UTC).isoformat(), content],
        )
        conn.commit()
        summary_id = cursor.lastrowid
        conn.close()
        return summary_id

    def has_summary(self) -> bool:
        """Check if a summary message exists."""
        conn = sqlite3.connect(self.messages_db_path)
        result = conn.execute("SELECT 1 FROM messages WHERE role = 'summary' LIMIT 1").fetchone()
        conn.close()
        return result is not None

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

    def clear(self) -> None:
        """Clear all messages from conversation store."""
        conn = sqlite3.connect(self.messages_db_path)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()


_stores: dict[str, ConversationStore] = {}


def get_conversation_store(user_id: str = "default") -> ConversationStore:
    """Get conversation store for a user."""
    if user_id not in _stores:
        _stores[user_id] = ConversationStore(user_id)
    return _stores[user_id]
