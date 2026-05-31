"""HybridDB backend — SQLite + FTS5 + ChromaDB via hybriddb.

Leverages all three HybridDB layers:
  - SQLite: structured storage, metadata, timestamps
  - FTS5: exact keyword/term matching with BM25-like scoring
  - ChromaDB: semantic similarity via all-MiniLM-L6-v2 embeddings

The fused ranking formula:
  fused_score = semantic_score * (1 + fts_weight * keyword_overlap)
"""

from __future__ import annotations

import json
from datetime import datetime

from coremem.backends.base import StoreBackend
from coremem.types import Memory, SearchQuery, SearchResult


class HybridBackend(StoreBackend):
    """HybridDB backend combining semantic + keyword + structured search.

    Ingestion writes to SQLite via HybridDB's journal. The journal
    automatically embeds and indexes into ChromaDB. FTS5 handles
    keyword matching during retrieval. Results are fused via
    semantic * (1 + fts_weight * keyword_overlap).
    """

    def __init__(self, path: str):
        from hybriddb import HybridDB

        self._path = path
        self._db = HybridDB(path=path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        try:
            self._db.create_table(
                "messages",
                {
                    "id": "TEXT PRIMARY KEY",
                    "ts": "TEXT NOT NULL",
                    "role": "TEXT NOT NULL",
                    "content": "LONGTEXT",
                    "metadata": "TEXT",
                },
            )
        except Exception:
            pass

    def _merge_metadata_for_storage(self, memory: Memory) -> dict:
        meta = {
            "role": memory.role,
            "session_id": memory.session_id or "",
            "ts": memory.ts.isoformat() if memory.ts else datetime.now().isoformat(),
        }
        meta.update(memory.metadata)
        return meta

    def _parse_metadata(self, raw: str | dict | None) -> dict:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def _matches_filters(self, meta: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if meta.get(key) != value:
                return False
        return True

    def _build_where_clause(self, filters: dict) -> tuple[list[str], list[str]]:
        """Build SQL WHERE parts and params from metadata equality filters."""
        parts, params = [], []
        for key, value in filters.items():
            safe_key = key.replace("'", "''")
            parts.append(f"json_extract(metadata, '$.{safe_key}') = ?")
            params.append(str(value))
        return parts, params

    def _delete_with_journal(self, ids: list[str]) -> None:
        """Delete rows, journal entries, ChromaDB vectors, and sync DuckDB."""
        with self._db._connect() as cur:
            placeholders = ",".join("?" for _ in ids)
            cur.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids)
            cur.execute(
                f"DELETE FROM _journal WHERE app_table = 'messages' AND row_id IN ({placeholders})",
                ids,
            )
        if self._db._chroma is not None:
            try:
                self._db._chroma.delete(
                    collection_name="messages_content",
                    ids=[str(i) for i in ids],
                )
            except Exception:
                pass
        self._db.sync_duckdb_table("messages")

    def ingest(self, memory: Memory, embedding: list[float] | None = None) -> str:
        ids = self.ingest_batch([memory])
        if embedding is not None and ids:
            try:
                col = self._db._chroma.get_collection("messages_content")
                col.update(ids=[ids[0]], embeddings=[embedding])
            except Exception:
                pass
        return ids[0] if ids else ""

    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        import uuid

        if not memories:
            return []
        ids = []
        rows = []
        for m in memories:
            mid = m.id or str(uuid.uuid4())[:12]
            ids.append(mid)
            storage_meta = self._merge_metadata_for_storage(m)
            rows.append({
                "id": mid,
                "content": m.content,
                "role": m.role,
                "metadata": json.dumps(storage_meta),
                "ts": m.ts.isoformat() if m.ts else datetime.now().isoformat(),
            })
        self._db.insert_batch("messages", rows)
        return ids

    def search(self, query: SearchQuery) -> list[SearchResult]:
        import sys

        db_module = sys.modules.get(type(self._db).__module__)
        search_mode = getattr(db_module, "SearchMode", None) if db_module else None

        fetch_limit = query.limit * 3
        fts_weight = 0.5

        kwargs: dict = {
            "table": "messages",
            "column": "content",
            "query": query.text,
            "limit": fetch_limit,
        }
        if search_mode is not None:
            kwargs["mode"] = search_mode.HYBRID
            kwargs["fts_weight"] = fts_weight
            kwargs["recency_weight"] = 0.3
            kwargs["recency_column"] = "ts"

        raw_rows = self._db.search(**kwargs)

        seen_sessions: set[str] = set()
        results = []
        for row in raw_rows:
            rid = row.get("id", "")
            content = row.get("content", "")
            score = float(row.get("_score", 0.0))
            ts_str = row.get("ts", "")
            role = row.get("role", "")

            meta_dict = self._parse_metadata(row.get("metadata"))

            if query.metadata and not self._matches_filters(meta_dict, query.metadata):
                continue

            sid = meta_dict.get("session_id", "")
            if sid and sid in seen_sessions:
                continue
            if sid:
                seen_sessions.add(sid)

            ts = None
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    pass

            user_meta = {k: v for k, v in meta_dict.items()
                         if k not in ("role", "session_id", "ts")}

            memory = Memory(
                id=str(rid),
                content=content,
                role=role,
                ts=ts,
                session_id=sid or None,
                score=score,
                metadata=user_meta,
            )
            results.append(SearchResult(memory=memory, score=score, source="hybrid"))

            if len(results) >= query.limit:
                break

        return results

    def list(
        self, metadata: dict | None = None, limit: int | None = None, offset: int = 0,
    ) -> list[Memory]:
        where_parts, params = self._build_where_clause(metadata or {})
        where_clause = " AND ".join(where_parts) if where_parts else ""

        if limit is None:
            sql_limit = 0
        else:
            sql_limit = limit + offset

        rows = self._db.query(
            "messages",
            where=where_clause,
            params=tuple(params),
            order_by="ts DESC",
            limit=sql_limit,
        )

        memories = []
        for row in rows:
            meta_dict = self._parse_metadata(row.get("metadata", ""))
            ts_str = row.get("ts", "")
            ts = None
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    pass

            user_meta = {k: v for k, v in meta_dict.items()
                         if k not in ("role", "session_id", "ts")}

            memories.append(Memory(
                id=str(row.get("id", "")),
                content=row.get("content", ""),
                role=row.get("role", "user"),
                ts=ts,
                session_id=meta_dict.get("session_id"),
                metadata=user_meta,
            ))

        if offset:
            memories = memories[offset:]

        return memories

    def get_recent(self, limit: int = 10) -> list[Memory]:
        return self.list(limit=limit)

    def count(self) -> int:
        try:
            result = self._db.count("messages")
            return result if isinstance(result, int) else 0
        except Exception:
            return 0

    def delete(self, metadata: dict | None = None) -> int:
        parts, params = self._build_where_clause(metadata or {})
        where = " AND ".join(parts) if parts else "1"
        rows = self._db.query("messages", where=where, params=tuple(params))
        ids = [r["id"] for r in rows]
        if not ids:
            return 0
        self._delete_with_journal(ids)
        return len(ids)

    def clear(self) -> None:
        try:
            with self._db._connect() as cur:
                cur.execute("DELETE FROM messages")
                cur.execute("DELETE FROM _journal WHERE app_table = ?", ("messages",))
        except Exception:
            pass
        if self._db._chroma is not None:
            try:
                self._db._chroma.delete_collection("messages_content")
            except Exception:
                pass
        try:
            self._db.sync_duckdb_table("messages")
        except Exception:
            pass
