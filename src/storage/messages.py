"""Conversation storage using HybridDB.

Domain wrapper that adds:
- Conversation compression (summary messages)
- Message/SearchResult dataclasses
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from src.sdk.hybrid_db import HybridDB, SearchMode
from src.storage.paths import get_paths


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
        data/private/conversation/
        ├── app.db    # SQLite + FTS5 + journal (HybridDB)
        └── vectors/ # ChromaDB for semantic search
    """

    def __init__(self, user_id: str, base_dir: Path | str | None = None):
        self.user_id = user_id
        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            base_path = get_paths(user_id).conversation_dir()
        base_path.mkdir(parents=True, exist_ok=True)

        self.db = HybridDB(str(base_path))
        self.db.create_table(
            "messages",
            {
                "ts": "TEXT NOT NULL",
                "role": "TEXT NOT NULL",
                "content": "LONGTEXT",
                "metadata": "JSON",
            },
        )

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> int:
        ts = datetime.now(UTC).isoformat()
        return self.db.insert(
            "messages",
            {
                "ts": ts,
                "role": role,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None,
            },
        )

    def add_message_with_embedding(
        self, role: str, content: str, embedding: list[float], metadata: dict | None = None
    ) -> int:
        return self.add_message(role, content, metadata)

    def search_keyword(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        rows = self.db.search("messages", "content", query, mode=SearchMode.KEYWORD, limit=limit)
        results = []
        for r in rows:
            results.append(
                SearchResult(
                    id=r["id"],
                    content=r["content"],
                    ts=datetime.fromisoformat(r["ts"]),
                    role=r["role"],
                    score=r.get("_score", 0.0),
                )
            )
        return results

    def search_vector(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        rows = self.db.search("messages", "content", query, mode=SearchMode.SEMANTIC, limit=limit)
        results = []
        for r in rows:
            results.append(
                SearchResult(
                    id=r["id"],
                    content=r["content"],
                    ts=datetime.fromisoformat(r["ts"]),
                    role=r["role"],
                    score=r.get("_score", 0.0),
                )
            )
        return results

    def search_hybrid(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.3,
    ) -> list[SearchResult]:
        if not query:
            return []
        rows = self.db.search(
            "messages",
            "content",
            query,
            mode=SearchMode.HYBRID,
            limit=limit,
            fts_weight=fts_weight,
            recency_weight=recency_weight,
            recency_column="ts",
        )
        results = []
        for r in rows:
            results.append(
                SearchResult(
                    id=r["id"],
                    content=r["content"],
                    ts=datetime.fromisoformat(r["ts"]),
                    role=r["role"],
                    score=r.get("_score", 0.0),
                )
            )
        return results

    def get_messages(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        where_parts = []
        params: list[str] = []
        if start_date:
            where_parts.append("ts >= ?")
            params.append(datetime.combine(start_date, datetime.min.time()).isoformat())
        if end_date:
            where_parts.append("ts <= ?")
            params.append(datetime.combine(end_date, datetime.max.time()).isoformat())

        where = " AND ".join(where_parts) if where_parts else ""
        rows = self.db.query(
            "messages", where=where, params=tuple(params), order_by="ts ASC", limit=limit or 10000
        )

        return [
            Message(
                id=r["id"],
                ts=datetime.fromisoformat(r["ts"]),
                role=r["role"],
                content=r["content"],
                metadata=json.loads(r["metadata"]) if r.get("metadata") else None,
            )
            for r in rows
        ]

    def get_recent_messages(self, count: int = 100) -> list[Message]:
        rows = self.db.query("messages", order_by="ts DESC", limit=count)
        messages = [
            Message(
                id=r["id"],
                ts=datetime.fromisoformat(r["ts"]),
                role=r["role"],
                content=r["content"],
                metadata=json.loads(r["metadata"]) if r.get("metadata") else None,
            )
            for r in rows
        ]
        return list(reversed(messages))

    def get_messages_with_summary(self, limit: int = 50) -> list[Message]:
        summary_rows = self.db.query(
            "messages", where="role = 'summary'", order_by="id DESC", limit=1
        )
        if not summary_rows:
            return self.get_recent_messages(limit)

        summary_id = summary_rows[0]["id"]
        rows = self.db.query(
            "messages", where="id >= ?", params=(summary_id,), order_by="id ASC", limit=10000
        )

        return [
            Message(
                id=r["id"],
                ts=datetime.fromisoformat(r["ts"]),
                role=r["role"],
                content=r["content"],
                metadata=json.loads(r["metadata"]) if r.get("metadata") else None,
            )
            for r in rows
        ]

    def add_summary_message(self, content: str) -> int:
        return self.add_message("summary", content)

    def has_summary(self) -> bool:
        rows = self.db.query("messages", where="role = 'summary'", limit=1)
        return len(rows) > 0

    def count_messages(self, start_date: date | None = None, end_date: date | None = None) -> int:
        where_parts = []
        params: list[str] = []
        if start_date:
            where_parts.append("ts >= ?")
            params.append(datetime.combine(start_date, datetime.min.time()).isoformat())
        if end_date:
            where_parts.append("ts <= ?")
            params.append(datetime.combine(end_date, datetime.max.time()).isoformat())

        where = " AND ".join(where_parts) if where_parts else ""
        return self.db.count("messages", where=where, params=tuple(params))

    def clear(self) -> None:
        all_rows = self.db.query("messages", limit=100000)
        for r in all_rows:
            self.db.delete("messages", r["id"])


_stores: dict[str, ConversationStore] = {}


def get_conversation_store(user_id: str = "default") -> ConversationStore:
    if user_id not in _stores:
        _stores[user_id] = ConversationStore(user_id)
    return _stores[user_id]
