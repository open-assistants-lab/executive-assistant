"""Pure ChromaDB backend — baseline, zero LLM."""

from memcore.backends.base import StoreBackend
from memcore.types import Memory, SearchResult, SearchQuery


class ChromaBackend(StoreBackend):
    """ChromaDB-only backend for semantic search.

    Stores verbatim text and retrieves via cosine similarity.
    Metadata filtering supports wing/room scoping (optional).
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

    def ingest(self, memory: Memory) -> str:
        ids = self.ingest_batch([memory])
        return ids[0] if ids else ""

    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        import uuid

        if not memories:
            return []

        ids = [m.id or str(uuid.uuid4())[:12] for m in memories]
        documents = [m.content for m in memories]
        metadatas = [
            {
                "role": m.role,
                "session_id": m.session_id or "",
                **({"ts": m.ts.isoformat()} if m.ts else {}),
            }
            for m in memories
        ]
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return ids

    def ingest_batch(self, memories: list[Memory]) -> list[str]:
        import uuid
        if not memories:
            return []
        ids = [m.id or str(uuid.uuid4())[:12] for m in memories]
        documents = [m.content for m in memories]
        metadatas = [
            {
                "role": m.role,
                "session_id": m.session_id or "",
                **({"ts": m.ts.isoformat()} if m.ts else {}),
            }
            for m in memories
        ]
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return ids

    def search(self, query: SearchQuery) -> list[SearchResult]:
        where = {}
        if query.wing:
            where["wing"] = query.wing
        if query.room:
            where["room"] = query.room

        kwargs = {"n_results": query.limit}
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

                memory = Memory(
                    id=mid,
                    content=doc,
                    role=meta.get("role", "user"),
                    session_id=meta.get("session_id"),
                    score=score,
                )
                search_results.append(SearchResult(memory=memory, score=score, source="semantic"))

        return search_results

    def get_recent(self, limit: int = 10) -> list[Memory]:
        results = self._collection.get(
            limit=limit,
            include=["documents", "metadatas"],
        )
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
                ))
        return memories

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._client.delete_collection("mempalace_drawers")
        self._collection = self._client.get_or_create_collection(
            name="mempalace_drawers",
            metadata={"hnsw:space": "cosine"},
        )
