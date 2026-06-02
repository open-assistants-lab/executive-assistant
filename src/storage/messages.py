"""Message storage using CoreMem.

Thin adapter over MemoryCore + HybridBackend, preserving the
Message/SearchResult dataclasses and public API for callers.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from coremem.backends.hybrid import HybridBackend
from coremem.core import MemoryCore
from coremem.types import Memory as _CoreMem
from coremem.types import SearchResult as _CoreMemResult

from src.storage.paths import get_paths


def _patch_coremem_for_integer_pk() -> None:
    """Patch HybridBackend.ingest_batch to omit non-numeric string ids.

    The OSS coremem library generates uuid-hex string ids (e.g. "a3b4c5d6e7f8")
    and passes them as the `id` column value. Our SQLite schema has
    `id INTEGER PRIMARY KEY AUTOINCREMENT`, and SQLite raises
    `IntegrityError: datatype mismatch` when a non-numeric string is
    inserted into an INTEGER PRIMARY KEY column.

    The fix: omit the `id` field from the row dict and let SQLite assign
    the autoincrement value. `insert_batch` in HybridDB already returns
    the assigned ids via `lastrowid`, so the return contract is preserved.
    """
    if getattr(HybridBackend.ingest_batch, "_ea_patched", False):
        return

    _original = HybridBackend.ingest_batch

    def _patched(self, memories):  # type: ignore[no-untyped-def]
        if not memories:
            return []
        ids: list[str] = []
        rows: list[dict] = []
        for m in memories:
            rows.append(
                {
                    "content": m.content,
                    "role": m.role,
                    "session_id": m.session_id or "",
                    "user_id": m.user_id,
                    "agent_id": m.agent_id,
                    "metadata": json.dumps(m.metadata or {}),
                    "ts": m.ts.isoformat()
                    if m.ts
                    else datetime.now(timezone.utc).isoformat(),
                }
            )
        actual_ids = self._db.insert_batch("messages", rows)
        return [str(i) for i in actual_ids]

    _patched._ea_patched = True  # type: ignore[attr-defined]
    HybridBackend.ingest_batch = _patched  # type: ignore[assignment]


_patch_coremem_for_integer_pk()


@dataclass
class Message:
    """A single message in the conversation."""

    id: str
    ts: datetime
    role: str
    content: str
    metadata: dict | None = None


@dataclass
class SearchResult:
    """Search result with score."""

    id: str
    content: str
    ts: datetime
    role: str
    score: float


class MessageStore:
    """Manages message storage via MemoryCore.

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
            paths = get_paths(user_id)
            base_path = paths.conversation_dir()
        base_path.mkdir(parents=True, exist_ok=True)

        self._core = MemoryCore(backend=HybridBackend(path=str(base_path)))

        try:
            with self._core._backend._db._connect() as cur:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)")
        except Exception:
            pass

        try:
            self._core._backend._db.register_duckdb_table("messages")
        except Exception:
            pass

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> str:
        result = self._core.ingest(role, content or "(empty)", metadata=metadata)
        return result or ""

    def add_message_with_embedding(
        self, role: str, content: str, embedding: list[float], metadata: dict | None = None
    ) -> str:
        result = self._core.ingest(role, content or "(empty)", metadata=metadata, embedding=embedding)
        return result or ""

    @staticmethod
    def _to_msg(m: _CoreMem) -> Message:
        return Message(
            id=m.id,
            ts=m.ts,
            role=m.role,
            content=m.content,
            metadata=m.metadata,
        )

    @staticmethod
    def _to_sr(r: _CoreMemResult) -> SearchResult:
        return SearchResult(
            id=r.memory.id,
            content=r.memory.content,
            ts=r.memory.ts,
            role=r.memory.role,
            score=r.score,
        )

    def search_keyword(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        results = self._core.search(query, limit=limit)
        return [self._to_sr(r) for r in results]

    def search_vector(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query:
            return []
        results = self._core.search(query, limit=limit)
        return [self._to_sr(r) for r in results]

    def search_hybrid(self, query: str, query_embedding: list[float] | None = None,
                      limit: int = 10, **kwargs) -> list[SearchResult]:
        if not query:
            return []
        results = self._core.search_enhanced(query, limit=limit, **kwargs)
        return [self._to_sr(r) for r in results]

    def get_messages(
        self, start_date: date | None = None, end_date: date | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        ts_after = f"{start_date.isoformat()}T00:00:00" if start_date else None
        ts_before = f"{end_date.isoformat()}T23:59:59" if end_date else None
        memories = self._core.fetch(
            limit=limit or 10000,
            ts_after=ts_after,
            ts_before=ts_before,
        )
        return [self._to_msg(m) for m in reversed(memories)]

    def get_messages_by_session_id(self, session_id: str, limit: int = 50) -> list[Message]:
        memories = self._core.fetch(limit=limit, session_id=session_id)
        return [self._to_msg(m) for m in memories]

    def get_recent_messages(self, count: int = 100) -> list[Message]:
        memories = self._core.fetch(limit=count)
        return [self._to_msg(m) for m in reversed(memories)]

    def get_recent_messages_for_workspace(
        self, workspace_id: str = "personal", count: int = 100
    ) -> list[Message]:
        memories = self._core.fetch(limit=count, metadata={"workspace_id": workspace_id})
        return [self._to_msg(m) for m in reversed(memories)]

    def get_messages_with_summary(self, limit: int = 50) -> list[Message]:
        if limit <= 0:
            return []
        summaries = self._core.fetch(limit=1, role="summary")
        if not summaries:
            memories = self._core.fetch(limit=limit)
            return [self._to_msg(m) for m in reversed(memories)]
        non_summaries = self._core.fetch(limit=limit)
        non_summaries = [m for m in non_summaries if m.role != "summary"]
        result: list[Message] = [self._to_msg(summaries[0])]
        result += [self._to_msg(m) for m in non_summaries]
        return result[:limit]

    def add_summary_message(self, content: str) -> int:
        return self.add_message("summary", content)

    def has_summary(self) -> bool:
        return len(self._core.fetch(limit=1, role="summary")) > 0

    def count_messages(self, start_date: date | None = None, end_date: date | None = None) -> int:
        if not start_date and not end_date:
            return self._core.count()
        ts_after = f"{start_date.isoformat()}T00:00:00" if start_date else None
        ts_before = f"{end_date.isoformat()}T23:59:59" if end_date else None
        return len(self._core.fetch_all(ts_after=ts_after, ts_before=ts_before))

    def delete_messages_for_workspace(self, workspace_id: str) -> int:
        return self._core.delete(metadata={"workspace_id": workspace_id})

    def clear(self) -> None:
        self._core.clear()


_stores: dict[str, MessageStore] = {}


def get_message_store(user_id: str = "default_user", workspace_id: str = "personal") -> MessageStore:
    key = f"{user_id}:msgstore"
    if key not in _stores:
        _stores[key] = MessageStore(user_id, workspace_id=workspace_id)
    return _stores[key]
