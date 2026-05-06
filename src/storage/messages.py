"""Message storage using HybridDB.

Domain wrapper that adds:
- DuckDB columnar analytics on message history
- Conversation compression (summary messages)
- Message/SearchResult dataclasses
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.hybrid_db import HybridDB, SearchMode
from src.storage.paths import get_paths

logger = get_logger()


def _date_filter_bounds(
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[str, tuple[str, ...]]:
    where_parts = []
    params: list[str] = []
    if start_date:
        where_parts.append("ts >= ?")
        params.append(datetime.combine(start_date, datetime.min.time(), tzinfo=UTC).isoformat())
    if end_date:
        where_parts.append("ts <= ?")
        params.append(datetime.combine(end_date, datetime.max.time(), tzinfo=UTC).isoformat())
    return " AND ".join(where_parts) if where_parts else "", tuple(params)


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


class MessageStore:
    """Manages message storage.

    Structure:
        data/private/conversation/
        ├── app.db    # SQLite + FTS5 + journal (HybridDB)
        └── vectors/ # ChromaDB for semantic search
    """

    def __init__(self, user_id: str, base_dir: Path | str | None = None, workspace_id: str = "personal"):
        self.user_id = user_id
        self.workspace_id = workspace_id
        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            paths = get_paths(user_id, workspace_id=workspace_id)
            base_path = paths.workspace_conversation_path().parent
        base_path.mkdir(parents=True, exist_ok=True)

        settings = get_settings()
        self.db = HybridDB(
            str(base_path),
            max_chroma_index_gb=settings.memory.messages.max_chroma_index_gb,
        )
        self.db.create_table(
            "messages",
            {
                "ts": "TEXT NOT NULL",
                "role": "TEXT NOT NULL",
                "content": "LONGTEXT",
                "metadata": "JSON",
            },
        )
        with self.db._connect() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)")
        self.db.register_duckdb_table("messages")

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
        ts = datetime.now(UTC).isoformat()
        row_id = self.db.insert(
            "messages",
            {
                "ts": ts,
                "role": role,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None,
            },
            sync=False,
            skip_journal_columns={"content"},
        )
        row = self.db.get("messages", row_id)
        if row:
            self.db.vector_upsert(
                "messages_content",
                row_id,
                content,
                embedding,
                self.db.row_to_metadata("messages", row),
            )
        self.db.process_journal()
        return int(row_id)

    @staticmethod
    def _rows_to_search_results(rows: list[dict]) -> list[SearchResult]:
        return [
            SearchResult(
                id=r["id"],
                content=r["content"],
                ts=datetime.fromisoformat(r["ts"]),
                role=r["role"],
                score=r.get("_score", 0.0),
            )
            for r in rows
        ]

    @staticmethod
    def _rows_to_messages(rows: list[dict]) -> list[Message]:
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

    def search_keyword(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        rows = self.db.search("messages", "content", query, mode=SearchMode.KEYWORD, limit=limit)
        return self._rows_to_search_results(rows)

    def search_vector(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        rows = self.db.search("messages", "content", query, mode=SearchMode.SEMANTIC, limit=limit)
        return self._rows_to_search_results(rows)

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
            query_embedding=query_embedding,
        )
        return self._rows_to_search_results(rows)

    def get_messages(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        where, params = _date_filter_bounds(start_date, end_date)
        rows = self.db.query(
            "messages", where=where, params=params, order_by="ts ASC", limit=limit or 10000
        )

        return self._rows_to_messages(rows)

    def get_recent_messages(self, count: int = 100) -> list[Message]:
        rows = self.db.query("messages", order_by="ts DESC", limit=count)
        messages = self._rows_to_messages(rows)
        return list(reversed(messages))

    def get_messages_with_summary(self, limit: int = 50) -> list[Message]:
        summary_rows = self.db.query(
            "messages", where="role = 'summary'", order_by="id DESC", limit=1
        )
        if not summary_rows:
            return self.get_recent_messages(limit)

        if limit <= 0:
            return []

        summary_id = summary_rows[0]["id"]
        if limit == 1:
            rows = summary_rows
        else:
            after_summary = self.db.query(
                "messages",
                where="id > ?",
                params=(summary_id,),
                order_by="id DESC",
                limit=limit - 1,
            )
            rows = [summary_rows[0], *reversed(after_summary)]

        return self._rows_to_messages(rows)

    def add_summary_message(self, content: str) -> int:
        return self.add_message("summary", content)

    def has_summary(self) -> bool:
        return self.db.count("messages", where="role = 'summary'") > 0

    def count_messages(self, start_date: date | None = None, end_date: date | None = None) -> int:
        where, params = _date_filter_bounds(start_date, end_date)
        return self.db.count("messages", where=where, params=params)

    def clear(self) -> None:
        with self.db._connect() as cur:
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM _journal WHERE app_table = ?", ("messages",))
        if self.db._chroma is not None:
            try:
                self.db._chroma.delete_collection("messages_content")
            except Exception:
                pass
        self.db.sync_duckdb_table("messages")


_stores: dict[str, MessageStore] = {}


def get_message_store(user_id: str = "default_user", workspace_id: str = "personal") -> MessageStore:
    key = f"{user_id}:{workspace_id}"
    if key not in _stores:
        _stores[key] = MessageStore(user_id, workspace_id=workspace_id)
    return _stores[key]
