"""Memory store - SQLite + FTS5 + ChromaDB implementation."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from chromadb import PersistentClient
from chromadb.api import ClientAPI
from chromadb.config import Settings

from src.memory.models import (
    Memory,
    MemoryCreate,
    MemorySearchParams,
    MemorySearchResult,
    MemoryTimelineEntry,
    MemoryTimelineParams,
    MemoryType,
    MemoryUpdate,
)


class MemoryStore:
    """Memory storage with SQLite + FTS5 + ChromaDB.

    Architecture:
    - SQLite: Structured storage with FTS5 full-text search
    - ChromaDB: Vector embeddings for semantic search (single collection)
    """

    def __init__(self, user_id: str, data_path: Path) -> None:
        self.user_id = user_id
        self.data_path = data_path
        self.memory_path = data_path / ".memory"
        self.memory_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.memory_path / "memory.db"
        self.chroma_path = self.memory_path / "chroma"

        self._init_sqlite()
        self._init_chroma()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with FTS5."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run database migrations."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subtitle TEXT,
                narrative TEXT,
                type TEXT NOT NULL,
                confidence REAL DEFAULT 0.7,
                source TEXT DEFAULT 'learned',
                facts TEXT,
                concepts TEXT,
                entities TEXT,
                project TEXT,
                occurred_at TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT,
                access_count INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title,
                subtitle,
                narrative,
                facts,
                concepts,
                content='memories',
                content_rowid='rowid'
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_occurred ON memories(occurred_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(archived)
        """)

        self._create_fts_triggers(cursor)

        self.conn.commit()

    def _create_fts_triggers(self, cursor: sqlite3.Cursor) -> None:
        """Create triggers to keep FTS in sync."""
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, subtitle, narrative, facts, concepts)
                VALUES (new.rowid, new.title, new.subtitle, new.narrative, new.facts, new.concepts);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, subtitle, narrative, facts, concepts)
                VALUES('delete', old.rowid, old.title, old.subtitle, old.narrative, old.facts, old.concepts);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, subtitle, narrative, facts, concepts)
                VALUES('delete', old.rowid, old.title, old.subtitle, old.narrative, old.facts, old.concepts);
                INSERT INTO memories_fts(rowid, title, subtitle, narrative, facts, concepts)
                VALUES (new.rowid, new.title, new.subtitle, new.narrative, new.facts, new.concepts);
            END
        """)

    def _init_chroma(self) -> None:
        """Initialize ChromaDB client with single collection."""
        self.chroma_client: ClientAPI = PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="memories",
            metadata={"user_id": self.user_id},
        )

    def add(self, data: MemoryCreate) -> Memory:
        """Add a new memory."""
        memory_id = f"mem-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (
                id, title, subtitle, narrative, type, confidence, source,
                facts, concepts, entities, project, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                data.title,
                data.subtitle,
                data.narrative,
                data.type.value,
                data.confidence,
                data.source.value,
                json.dumps(data.facts) if data.facts else None,
                json.dumps(data.concepts) if data.concepts else None,
                json.dumps(data.entities) if data.entities else None,
                data.project,
                data.occurred_at.isoformat() if data.occurred_at else None,
                now.isoformat(),
            ),
        )
        self.conn.commit()

        doc_text = self._build_document_text(data)
        self.collection.add(
            ids=[memory_id],
            documents=[doc_text],
            metadatas=[
                {
                    "type": data.type.value,
                    "project": data.project or "",
                    "confidence": data.confidence,
                }
            ],
        )

        return self.get(memory_id)

    def get(self, memory_id: str) -> Memory:
        """Get a memory by ID and update access tracking."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE memories SET last_accessed = ?, access_count = access_count + 1
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), memory_id),
        )
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        self.conn.commit()

        if not row:
            raise ValueError(f"Memory not found: {memory_id}")

        return self._row_to_memory(row)

    def update(self, memory_id: str, data: MemoryUpdate) -> Memory:
        """Update an existing memory."""
        updates: list[str] = []
        values: list[Any] = []

        if data.title is not None:
            updates.append("title = ?")
            values.append(data.title)
        if data.subtitle is not None:
            updates.append("subtitle = ?")
            values.append(data.subtitle)
        if data.narrative is not None:
            updates.append("narrative = ?")
            values.append(data.narrative)
        if data.confidence is not None:
            updates.append("confidence = ?")
            values.append(data.confidence)
        if data.facts is not None:
            updates.append("facts = ?")
            values.append(json.dumps(data.facts))
        if data.concepts is not None:
            updates.append("concepts = ?")
            values.append(json.dumps(data.concepts))
        if data.entities is not None:
            updates.append("entities = ?")
            values.append(json.dumps(data.entities))
        if data.project is not None:
            updates.append("project = ?")
            values.append(data.project)
        if data.archived is not None:
            updates.append("archived = ?")
            values.append(1 if data.archived else 0)

        if not updates:
            return self.get(memory_id)

        values.append(memory_id)
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        self.conn.commit()

        return self.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Archive (soft delete) a memory."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE memories SET archived = 1 WHERE id = ?",
            (memory_id,),
        )
        self.conn.commit()

        self.collection.update(
            ids=[memory_id],
            metadatas=[{"archived": True}],
        )

        return cursor.rowcount > 0

    def search(self, params: MemorySearchParams) -> list[MemorySearchResult]:
        """Search memories using hybrid search (FTS5 + semantic in parallel).

        Both FTS5 and semantic search run in parallel, results are merged.
        """
        fts_results: list[MemorySearchResult] = []
        semantic_results: list[MemorySearchResult] = []

        # Run FTS5 search
        try:
            fts_results = self._search_fts(params)
        except Exception:
            pass

        # Run semantic search in parallel
        if params.query:
            try:
                semantic_results = self._search_semantic(params.query, params.limit)
            except Exception:
                pass

        # Merge results from both searches
        combined = fts_results + semantic_results

        # Deduplicate by ID, keeping first occurrence (FTS has higher priority)
        seen: set[str] = set()
        unique_results: list[MemorySearchResult] = []
        for r in combined:
            if r.id not in seen:
                seen.add(r.id)
                unique_results.append(r)

        return unique_results[: params.limit]

    def _search_fts(self, params: MemorySearchParams) -> list[MemorySearchResult]:
        """Full-text search using FTS5."""
        cursor = self.conn.cursor()
        conditions: list[str] = ["archived = 0"]
        args: list[Any] = []

        if params.type:
            conditions.append("type = ?")
            args.append(params.type.value)

        if params.project:
            conditions.append("project = ?")
            args.append(params.project)

        if params.date_start:
            conditions.append("occurred_at >= ?")
            args.append(params.date_start)

        if params.date_end:
            conditions.append("occurred_at <= ?")
            args.append(params.date_end)

        order_clause = "created_at ASC" if params.order_by == "date_asc" else "created_at DESC"
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        if params.query:
            sql = """
                SELECT m.id, m.title, m.type, m.project, m.occurred_at, m.created_at, m.confidence
                FROM memories m
                JOIN memories_fts ON m.rowid = memories_fts.rowid
                WHERE memories_fts MATCH ?
                AND {where_clause}
                ORDER BY bm25(memories_fts)
                LIMIT ? OFFSET ?
            """.format(where_clause=where_clause)

            query_args: list[Any] = [params.query, *args, params.limit, params.offset]
            try:
                cursor.execute(sql, query_args)
            except sqlite3.OperationalError:
                # If user query is invalid FTS syntax, retry as a quoted phrase.
                fallback_query = f'"{params.query.replace("\"", "\"\"")}"'
                cursor.execute(sql, [fallback_query, *args, params.limit, params.offset])
        else:
            sql = f"""
                SELECT id, title, type, project, occurred_at, created_at, confidence
                FROM memories
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """
            cursor.execute(sql, [*args, params.limit, params.offset])
        rows = cursor.fetchall()

        return [
            MemorySearchResult(
                id=row["id"],
                title=row["title"],
                type=row["type"],
                project=row["project"],
                occurred_at=row["occurred_at"],
                created_at=row["created_at"],
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def _search_semantic(self, query: str, limit: int) -> list[MemorySearchResult]:
        """Semantic search using ChromaDB."""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"archived": {"$ne": True}},
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance

                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT title, created_at FROM memories WHERE id = ?",
                    (memory_id,),
                )
                row = cursor.fetchone()

                if row:
                    search_results.append(
                        MemorySearchResult(
                            id=memory_id,
                            title=row["title"],
                            type=metadata.get("type", "unknown"),
                            project=metadata.get("project"),
                            occurred_at=None,
                            created_at=row["created_at"],
                            confidence=metadata.get("confidence", 0.7),
                            score=score,
                        )
                    )

        return search_results

    def _merge_results(
        self,
        fts_results: list[MemorySearchResult],
        semantic_results: list[MemorySearchResult],
    ) -> list[MemorySearchResult]:
        """Merge FTS and semantic search results."""
        seen = set()
        merged = []

        for result in fts_results:
            if result.id not in seen:
                seen.add(result.id)
                merged.append(result)

        for result in semantic_results:
            if result.id not in seen:
                seen.add(result.id)
                result.score = (result.score or 0) * 0.8
                merged.append(result)

        merged.sort(key=lambda x: x.score if x.score else x.confidence, reverse=True)
        return merged

    def timeline(self, params: MemoryTimelineParams) -> dict[str, Any]:
        """Get timeline context around an anchor point (Layer 2)."""
        if params.anchor_id:
            anchor = self.get(params.anchor_id)
        elif params.query:
            search_results = self.search(MemorySearchParams(query=params.query, limit=1))
            if not search_results:
                return {"before": [], "anchor": None, "after": []}
            anchor = self.get(search_results[0].id)
        else:
            raise ValueError("Either anchor_id or query must be provided")

        anchor_time = anchor.occurred_at or anchor.created_at

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT * FROM memories
            WHERE archived = 0
            AND (occurred_at < ? OR (occurred_at IS NULL AND created_at < ?))
            AND (? IS NULL OR project = ?)
            ORDER BY COALESCE(occurred_at, created_at) DESC
            LIMIT ?
            """,
            (
                anchor_time.isoformat(),
                anchor_time.isoformat(),
                params.project,
                params.project,
                params.depth_before,
            ),
        )
        before_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT * FROM memories
            WHERE archived = 0
            AND (occurred_at > ? OR (occurred_at IS NULL AND created_at > ?))
            AND (? IS NULL OR project = ?)
            ORDER BY COALESCE(occurred_at, created_at) ASC
            LIMIT ?
            """,
            (
                anchor_time.isoformat(),
                anchor_time.isoformat(),
                params.project,
                params.project,
                params.depth_after,
            ),
        )
        after_rows = cursor.fetchall()

        return {
            "before": [self._row_to_timeline_entry(r) for r in reversed(before_rows)],
            "anchor": anchor.to_timeline_entry(),
            "after": [self._row_to_timeline_entry(r) for r in after_rows],
        }

    def get_batch(self, ids: list[str]) -> list[Memory]:
        """Get multiple memories by IDs (Layer 3 - full details)."""
        if not ids:
            return []

        placeholders = ",".join("?" * len(ids))
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM memories WHERE id IN ({placeholders}) AND archived = 0",
            ids,
        )
        rows = cursor.fetchall()

        return [self._row_to_memory(row) for row in rows]

    def _build_document_text(self, data: MemoryCreate) -> str:
        """Build document text for embedding."""
        parts = [data.title]
        if data.subtitle:
            parts.append(data.subtitle)
        if data.narrative:
            parts.append(data.narrative)
        if data.facts:
            parts.extend(data.facts)
        if data.concepts:
            parts.extend(data.concepts)
        return " ".join(parts)

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert database row to Memory object."""
        return Memory(
            id=row["id"],
            title=row["title"],
            subtitle=row["subtitle"],
            narrative=row["narrative"],
            type=MemoryType(row["type"]),
            confidence=row["confidence"],
            source=row["source"],
            facts=json.loads(row["facts"]) if row["facts"] else [],
            concepts=json.loads(row["concepts"]) if row["concepts"] else [],
            entities=json.loads(row["entities"]) if row["entities"] else [],
            project=row["project"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]) if row["occurred_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"])
            if row["last_accessed"]
            else None,
            access_count=row["access_count"],
            archived=bool(row["archived"]),
        )

    def _row_to_timeline_entry(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert database row to timeline entry."""
        return {
            "id": row["id"],
            "title": row["title"],
            "subtitle": row["subtitle"],
            "type": row["type"],
            "project": row["project"],
            "occurred_at": row["occurred_at"],
            "facts": json.loads(row["facts"])[:3] if row["facts"] else [],
        }

    def close(self) -> None:
        """Close database connections."""
        self.conn.close()
