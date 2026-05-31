"""Pure ChromaDB backend — baseline, zero LLM."""

from __future__ import annotations

import uuid

from coremem.backends.base import StoreBackend
from coremem.types import Memory, SearchQuery, SearchResult

_CHROMA_INTERNAL_META_KEYS = frozenset({"role", "session_id", "user_id", "agent_id", "ts"})


class ChromaBackend(StoreBackend):
    """ChromaDB-only backend for semantic search.

    Stores verbatim text and retrieves via cosine similarity.
    Structural fields (role, session_id, user_id, agent_id, ts) are
    stored as ChromaDB metadata keys and stripped on read into the
    Memory model. Remaining keys become Memory.metadata.
    """

    def __init__(self, path: str):
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for ChromaBackend. "
                "Install with: pip install chromadb"
            )
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name="mempalace_drawers",
            metadata={"hnsw:space": "cosine"},
        )

    def _meta_from_memory(self, memory: Memory) -> dict:
        meta: dict = {}
        if memory.role:
            meta["role"] = memory.role
        if memory.session_id:
            meta["session_id"] = memory.session_id
        if memory.user_id:
            meta["user_id"] = memory.user_id
        if memory.agent_id:
            meta["agent_id"] = memory.agent_id
        if memory.ts:
            meta["ts"] = memory.ts.isoformat()
        meta.update(memory.metadata)
        return meta

    def _row_to_memory(self, mid: str, doc: str, meta: dict) -> Memory:
        return Memory(
            id=mid,
            content=doc,
            role=meta.get("role", "user"),
            session_id=meta.get("session_id"),
            user_id=meta.get("user_id", ""),
            agent_id=meta.get("agent_id", ""),
            metadata={k: v for k, v in meta.items() if k not in _CHROMA_INTERNAL_META_KEYS},
        )

    def _build_chroma_where(self, query: SearchQuery | None = None) -> dict | None:
        """Build a ChromaDB where dict from SearchQuery column + metadata filters."""
        if query is None:
            return None

        clauses: dict = {}

        if query.role:
            clauses["role"] = query.role
        if query.session_id:
            clauses["session_id"] = query.session_id
        if query.user_id:
            clauses["user_id"] = query.user_id
        if query.agent_id:
            clauses["agent_id"] = query.agent_id

        ts_filter: dict = {}
        if query.ts_after:
            ts_filter["$gte"] = query.ts_after
        if query.ts_before:
            ts_filter["$lte"] = query.ts_before
        if ts_filter:
            clauses["ts"] = ts_filter

        if query.metadata:
            for k, v in query.metadata.items():
                clauses[k] = v

        return clauses if clauses else None

    def _build_list_where(
        self,
        role: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        ts_after: str | None = None,
        ts_before: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        clauses: dict = {}

        if role is not None:
            clauses["role"] = role
        if session_id is not None:
            clauses["session_id"] = session_id
        if user_id is not None:
            clauses["user_id"] = user_id
        if agent_id is not None:
            clauses["agent_id"] = agent_id

        ts_filter: dict = {}
        if ts_after is not None:
            ts_filter["$gte"] = ts_after
        if ts_before is not None:
            ts_filter["$lte"] = ts_before
        if ts_filter:
            clauses["ts"] = ts_filter

        if metadata:
            for k, v in metadata.items():
                clauses[k] = v

        return clauses if clauses else None

    def ingest(self, memory: Memory, embedding: list[float] | None = None) -> str:
        if embedding is not None:
            meta = self._meta_from_memory(memory)
            mid = memory.id or str(uuid.uuid4())[:12]
            self._collection.add(
                ids=[mid], documents=[memory.content],
                metadatas=[meta], embeddings=[embedding],
            )
            return mid
        ids = self.ingest_batch([memory])
        return ids[0] if ids else ""

    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        if not memories:
            return []
        ids = [m.id or str(uuid.uuid4())[:12] for m in memories]
        documents = [m.content for m in memories]
        metadatas = [self._meta_from_memory(m) for m in memories]
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return ids

    def search(self, query: SearchQuery) -> list[SearchResult]:
        kwargs: dict = {"n_results": query.limit}
        where = self._build_chroma_where(query)
        if where:
            kwargs["where"] = where

        results = self._collection.query(
            query_texts=[query.text],
            include=["documents", "metadatas", "distances"],
            **kwargs,
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, mid in enumerate(results["ids"][0]):
                doc = results["documents"][0][i] if results["documents"] else ""
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 1.0
                score = 1.0 - dist

                memory = self._row_to_memory(mid, doc, meta)
                search_results.append(SearchResult(memory=memory, score=score, source="semantic"))

        return search_results

    def list(
        self,
        role: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        ts_after: str | None = None,
        ts_before: str | None = None,
        metadata: dict | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Memory]:
        kwargs: dict = {"include": ["documents", "metadatas"]}
        where = self._build_list_where(
            role=role, session_id=session_id, user_id=user_id, agent_id=agent_id,
            ts_after=ts_after, ts_before=ts_before, metadata=metadata,
        )
        if where:
            kwargs["where"] = where
        if limit is not None:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset

        results = self._collection.get(**kwargs)
        memories = []
        if results["ids"]:
            for i, mid in enumerate(results["ids"]):
                doc = results["documents"][i] if results["documents"] else ""
                meta = results["metadatas"][i] if results["metadatas"] else {}
                memories.append(self._row_to_memory(mid, doc, meta))
        return memories

    def get_recent(self, limit: int = 10) -> list[Memory]:
        return self.list(limit=limit)

    def count(self) -> int:
        return self._collection.count()

    def delete(
        self,
        role: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        ts_after: str | None = None,
        ts_before: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        where = self._build_list_where(
            role=role, session_id=session_id, user_id=user_id, agent_id=agent_id,
            ts_after=ts_after, ts_before=ts_before, metadata=metadata,
        )
        result = self._collection.get(where=where)
        ids = result["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def clear(self) -> None:
        self._client.delete_collection("mempalace_drawers")
        self._collection = self._client.get_or_create_collection(
            name="mempalace_drawers",
            metadata={"hnsw:space": "cosine"},
        )
