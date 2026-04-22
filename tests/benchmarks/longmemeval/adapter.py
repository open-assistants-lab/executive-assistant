"""Adapter to inject LongMemEval sessions into our MessageStore.

This allows our agent's memory system to be tested on the LongMemEval benchmark.
Each question gets its own isolated HybridDB instance to prevent cross-contamination.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from src.storage.messages import MessageStore


def parse_longmemeval_date(date_str: str) -> str:
    """Parse LongMemEval date format like '2023/05/30 (Tue) 21:40'.

    Returns ISO format string for storage.
    """
    from datetime import datetime

    patterns = [
        "%Y/%m/%d (%a) %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(date_str, pattern)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def get_batch_embeddings(texts: list[str]) -> list[list[float]]:
    """Compute embeddings for a list of texts in batch (200x faster than one-by-one)."""
    from src.sdk.tools_core.apps import _get_embedding_model

    model = _get_embedding_model()
    if model is None:
        from src.sdk.tools_core.apps import _hash_embedding
        return [_hash_embedding(t) for t in texts]

    embeddings = model.encode(texts, show_progress_bar=False, batch_size=128)
    return embeddings.tolist()


class LongMemEvalAdapter:
    """Adapter that converts LongMemEval sessions into our MessageStore.

    Each instance creates an isolated MessageStore in a temp directory.
    Messages are tagged with session_id in metadata for retrieval evaluation.
    """

    def __init__(self, user_id: str = "benchmark", base_dir: Path | str | None = None):
        self.user_id = user_id
        if base_dir is not None:
            base_path = Path(base_dir)
        else:
            base_path = Path(f"data/benchmarks/longmemeval/users/{user_id}")
        base_path.mkdir(parents=True, exist_ok=True)
        self.store = MessageStore(user_id=user_id, base_dir=base_path)
        self._base_path = base_path

    def reset(self) -> None:
        """Clear all messages for this user (SQLite + ChromaDB)."""
        self.store.db.raw_query("DELETE FROM messages")
        collection = self.store.db._get_collection("messages_content")
        if collection:
            try:
                existing = collection.get()
                if existing and existing["ids"]:
                    collection.delete(ids=existing["ids"])
            except Exception:
                pass

    def inject_sessions(
        self,
        sessions: list[list[dict[str, str]]],
        session_dates: list[str],
        session_ids: list[str] | None = None,
    ) -> None:
        """Inject LongMemEval sessions using batch embedding (fast).

        Uses batch embedding computation instead of one-by-one, making it
        ~200x faster for large session sets.
        """
        self.reset()

        rows = []
        texts = []
        metas = []
        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            normalized_date = parse_longmemeval_date(session_date)
            sid = session_ids[session_idx] if session_ids else f"session_{session_idx}"
            for turn in session:
                role = turn["role"]
                content = turn["content"]
                metadata = {"session_id": sid, "date": normalized_date}
                rows.append({
                    "ts": normalized_date,
                    "role": role,
                    "content": content,
                    "metadata": json.dumps(metadata),
                })
                texts.append(content)
                metas.append({"role": role, "ts": normalized_date, "session_id": sid})

        embeddings = get_batch_embeddings(texts)

        msg_ids = []
        for row in rows:
            msg_id = self.store.db.insert("messages", row, sync=False)
            msg_ids.append(msg_id)

        self.store.db.process_journal()

        collection = self.store.db._get_collection("messages_content")
        collection.add(
            ids=[str(mid) for mid in msg_ids],
            embeddings=embeddings,
            documents=texts,
            metadatas=metas,
        )

    def search_with_session_ids(
        self,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search and return results with session_id from metadata.

        Returns list of dicts with: session_id, content, score, ts, role.
        """
        results = self.store.search_hybrid(
            query=query,
            limit=limit,
            fts_weight=fts_weight,
            recency_weight=recency_weight,
        )

        enriched = []
        for r in results:
            row = self.store.db.get("messages", r.id)
            sid = None
            if row and row.get("metadata"):
                meta = row["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                sid = meta.get("session_id") if isinstance(meta, dict) else None
            enriched.append({
                "session_id": sid,
                "content": r.content,
                "score": r.score,
                "ts": r.ts.isoformat() if hasattr(r.ts, "isoformat") else str(r.ts),
                "role": r.role,
            })
        return enriched

    def verify_injection(self) -> dict[str, Any]:
        """Verify that sessions were properly injected."""
        messages = self.store.get_recent_messages(count=100000)
        return {
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m.role == "user"),
            "assistant_messages": sum(1 for m in messages if m.role == "assistant"),
            "date_range": (f"{messages[0].ts} to {messages[-1].ts}" if messages else "empty"),
        }

    def cleanup(self) -> None:
        """Remove the benchmark data directory."""
        try:
            shutil.rmtree(self._base_path, ignore_errors=True)
        except Exception:
            pass


def format_sessions_as_context(
    sessions: list[list[dict[str, str]]],
    session_dates: list[str],
    format_type: str = "chatml",
    max_context_chars: int = 100000,
) -> str:
    """Format sessions as a string context (alternative to using MessageStore)."""
    if format_type == "chatml":
        lines = []
        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            lines.append(f"<|session|>{session_date}<|session|>")
            for turn in session:
                role = "user" if turn["role"] == "user" else "assistant"
                lines.append(f"<|{role}|>\n{turn['content']}<|end|>")
        context = "\n".join(lines)
    elif format_type == "natural":
        lines = []
        for session_idx, (session, session_date) in enumerate(zip(sessions, session_dates)):
            lines.append(f"\n--- Conversation on {session_date} ---\n")
            for turn in session:
                role = "User" if turn["role"] == "user" else "Assistant"
                lines.append(f"{role}: {turn['content']}")
        context = "\n".join(lines)
    else:
        raise ValueError(f"Unknown format_type: {format_type}")

    if len(context) > max_context_chars:
        context = "..." + context[-(max_context_chars - 3):]
    return context