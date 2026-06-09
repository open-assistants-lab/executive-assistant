"""Message storage using CoreMem.

Thin adapter over MemoryCore, preserving the
Message/SearchResult dataclasses and public API for callers.
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3

from coremem.core import MemoryCore
from coremem.types import Memory as _CoreMem
from coremem.types import SearchResult as _CoreMemResult

from src.storage.paths import get_paths


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

        # Migrate id column BEFORE MemoryCore initializes HybridDB+FTS triggers
        self._migrate_id_column(base_path)

        self._core = MemoryCore(path=str(base_path))

        try:
            with self._core.db._connect() as cur:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)")
        except Exception:
            pass

        try:
            self._core.db.register_duckdb_table("messages")
        except Exception:
            pass

    @staticmethod
    def _migrate_id_column(base_path: Path) -> None:
        """Migrate messages.id from INTEGER PK to TEXT PK if needed.

        The old schema used INTEGER PRIMARY KEY AUTOINCREMENT, but CoreMem
        generates string UUIDs. This mismatch causes HybridDB FTS triggers
        to attempt using a string as an FTS5 rowid, raising:
            IntegrityError: datatype mismatch

        Must run BEFORE MemoryCore is created so HybridDB sees TEXT PK
        and uses new.rowid (not new.id) in FTS triggers.
        """
        db_path = base_path / "app.db"
        if not db_path.exists():
            return
        conn = None
        try:
            conn = sqlite3.connect(str(db_path))
            info = conn.execute("PRAGMA table_info('messages')").fetchone()
            if info and 'INTEGER' in (info[2] or '').upper():
                conn.executescript(f"""
                    DROP TABLE IF EXISTS messages_new;
                    CREATE TABLE messages_new (
                        id TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT,
                        metadata TEXT,
                        session_id TEXT,
                        user_id TEXT,
                        agent_id TEXT
                    );
                    INSERT INTO messages_new(id, ts, role, content, metadata, session_id, user_id, agent_id)
                        SELECT CAST(id AS TEXT), ts, role, content, metadata, session_id, user_id, agent_id
                        FROM messages;
                    DROP TABLE messages;
                    ALTER TABLE messages_new RENAME TO messages;
                    DELETE FROM _schema WHERE table_name = 'messages';
                """)
                # _journal may not exist on fresh DBs
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                if '_journal' in tables:
                    conn.execute("DELETE FROM _journal WHERE app_table = 'messages'")
            conn.close()
        except Exception:
            if conn is not None:
                conn.close()

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
        """Delete all messages for a workspace.

        Uses direct SQLite DELETE because coremem's delete method cannot
        resolve auto-assigned integer ids via DuckDB (id shows as None
        due to the _patch_coremem_for_integer_pk patch that omits id
        from INSERT statements).
        """
        with self._core.db._connect() as cur:
            cur.execute(
                "DELETE FROM messages WHERE json_extract(metadata, '$.workspace_id') = ?",
                [workspace_id],
            )
            count = cur.rowcount
            cur.execute(
                "DELETE FROM _journal WHERE app_table = 'messages'"
                " AND json_extract(metadata, '$.workspace_id') = ?",
                [workspace_id],
            )
        if self._core.db._chroma is not None:
            try:
                memories = self._core.fetch(limit=10000, metadata={"workspace_id": workspace_id})
                ids = [m.id for m in memories if m.id != "None"]
                if ids:
                    self._core.db._chroma.delete(
                        collection_name="messages_content",
                        ids=ids,
                    )
            except Exception:
                pass
        try:
            self._core.db.sync_duckdb_table("messages")
        except Exception:
            pass
        return count

    def clear(self) -> None:
        self._core.clear()


_stores: dict[str, MessageStore] = {}


def get_message_store(user_id: str = "default_user", workspace_id: str = "personal") -> MessageStore:
    key = f"{user_id}:msgstore"
    if key not in _stores:
        _stores[key] = MessageStore(user_id, workspace_id=workspace_id)
    return _stores[key]
