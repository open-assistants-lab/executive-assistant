"""Pure ChromaDB backend — baseline, zero LLM."""

from __future__ import annotations

import uuid

from coremem.backends.base import StoreBackend
from coremem.types import Memory, SearchQuery, SearchResult

_CHROMA_INTERNAL_META_KEYS = frozenset({"role", "session_id", "ts"})


class ChromaBackend(StoreBackend):
    """ChromaDB-only backend for semantic search.

    Stores verbatim text and retrieves via cosine similarity.
    User metadata is flattened into top-level ChromaDB metadatas keys.
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

    def ingest(self, memory: Memory, embedding: list[float] | None = None) -> str:
        if embedding is not None:
            meta = {
                "role": memory.role,
                "session_id": memory.session_id or "",
            }
            if memory.ts:
                meta["ts"] = memory.ts.isoformat()
            meta.update(memory.metadata)
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
        metadatas = []
        for m in memories:
            meta = {
                "role": m.role,
                "session_id": m.session_id or "",
            }
            if m.ts:
                meta["ts"] = m.ts.isoformat()
            meta.update(m.metadata)
            metadatas.append(meta)

        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return ids

    def search(self, query: SearchQuery) -> list[SearchResult]:
        kwargs: dict = {"n_results": query.limit}
        if query.filters:
            kwargs["where"] = query.filters

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

                memory = Memory(
                    id=mid,
                    content=doc,
                    role=meta.get("role", "user"),
                    session_id=meta.get("session_id"),
                    score=score,
                    metadata={k: v for k, v in meta.items() if k not in _CHROMA_INTERNAL_META_KEYS},
                )
                search_results.append(SearchResult(memory=memory, score=score, source="semantic"))

        return search_results

    def list(
        self, filters: dict | None = None, limit: int | None = None, offset: int = 0,
    ) -> list[Memory]:
        kwargs: dict = {"include": ["documents", "metadatas"]}
        if filters:
            kwargs["where"] = filters
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
                memories.append(Memory(
                    id=mid,
                    content=doc,
                    role=meta.get("role", "user"),
                    session_id=meta.get("session_id"),
                    metadata={k: v for k, v in meta.items() if k not in _CHROMA_INTERNAL_META_KEYS},
                ))
        return memories

    def get_recent(self, limit: int = 10) -> list[Memory]:
        return self.list(limit=limit)

    def count(self) -> int:
        return self._collection.count()

    def delete(self, filters: dict | None = None) -> int:
        result = self._collection.get(where=filters)
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
