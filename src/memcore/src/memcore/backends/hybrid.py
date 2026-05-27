"""HybridDB backend — SQLite + FTS5 + ChromaDB via hybriddb.

Leverages all three HybridDB layers:
  - SQLite: structured storage, metadata, timestamps
  - FTS5: exact keyword/term matching with BM25-like scoring
  - ChromaDB: semantic similarity via all-MiniLM-L6-v2 embeddings

The fused ranking formula:
  fused_score = semantic_score * (1 + fts_weight * keyword_overlap)
"""

import json
from datetime import datetime

from memcore.backends.base import StoreBackend
from memcore.types import Memory, SearchQuery, SearchResult


class HybridBackend(StoreBackend):
    """HybridDB backend combining semantic + keyword + structured search.

    Ingestion writes to SQLite via HybridDB's journal. The journal
    automatically embeds and indexes into ChromaDB. FTS5 handles
    keyword matching during retrieval. Results are fused via
    semantic * (1 + fts_weight * keyword_overlap).
    """

    def __init__(self, path: str):
        try:
            from hybriddb import HybridDB  # open-source package (production)
        except ImportError:
            try:
                from src.sdk.hybrid_db import HybridDB  # local dev fallback
            except ImportError:
                raise ImportError(
                    "hybriddb is required for HybridBackend. "
                    "Install with: pip install hybriddb"
                )
        self._path = path
        self._db = HybridDB(path=path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        try:
            self._db.create_table(
                "messages",
                {
                    "id": "TEXT PRIMARY KEY",
                    "content": "LONGTEXT",
                    "role": "TEXT",
                    "metadata": "TEXT",
                    "ts": "TEXT",
                },
            )
        except Exception:
            pass

    def ingest(self, memory: Memory) -> str:
        ids = self.ingest_batch([memory])
        return ids[0] if ids else ""

    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        import uuid

        if not memories:
            return []
        rows = []
        ids = []
        for m in memories:
            mid = str(uuid.uuid4())[:12]
            ids.append(mid)
            metadata = {
                "role": m.role,
                "session_id": m.session_id or "",
                "ts": m.ts.isoformat() if m.ts else datetime.now().isoformat(),
            }
            rows.append({
                "id": mid,
                "content": m.content,
                "role": m.role,
                "metadata": json.dumps(metadata),
                "ts": m.ts.isoformat() if m.ts else datetime.now().isoformat(),
            })
        self._db.insert_batch("messages", rows)
        return ids

    def search(self, query: SearchQuery) -> list[SearchResult]:

        try:
            from hybriddb import SearchMode
        except ImportError:
            SearchMode = None

        fetch_limit = query.limit * 3
        fts_weight = 0.5

        kwargs = {
            "table": "messages",
            "column": "content",
            "query": query.text,
            "limit": fetch_limit,
        }
        if SearchMode is not None:
            kwargs["mode"] = SearchMode.HYBRID
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

            meta_dict = {}
            raw_meta = row.get("metadata")
            if raw_meta:
                if isinstance(raw_meta, str):
                    try:
                        meta_dict = json.loads(raw_meta)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(raw_meta, dict):
                    meta_dict = raw_meta

            sid = meta_dict.get("session_id", "")
            ws_id = meta_dict.get("workspace_id", "")
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

            results.append(SearchResult(
                    memory=Memory(
                        id=str(rid),
                        content=content,
                        role=role,
                        ts=ts,
                        session_id=sid or None,
                        workspace_id=ws_id or None,
                        score=score,
                    ),
                score=score,
                source="hybrid",
            ))

            if len(results) >= query.limit:
                break

        return results

    def get_recent(self, limit: int = 10) -> list[Memory]:
        try:
            rows = self._db.search(
                table="messages",
                column="content",
                query="",
                limit=limit,
                order_by="ts DESC",
            )
        except Exception:
            return []
        memories = []
        for row in rows:
            memories.append(Memory(
                id=str(row.get("id", "")),
                content=row.get("content", ""),
                role=row.get("role", "user"),
            ))
        return memories

    def count(self) -> int:
        try:
            result = self._db.count("messages")
            return result if isinstance(result, int) else 0
        except Exception:
            return 0

    def clear(self) -> None:
        try:
            self._db.raw_query("DELETE FROM messages")
        except Exception:
            pass
