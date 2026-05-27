"""Verbatim message ingestion — shared pipeline.

All backends ingest raw text without LLM extraction.
The only processing is deterministic: assign IDs, timestamps,
and attach metadata (role, session_id).

No fact extraction. No summarization. No LLM calls.
"""

from datetime import UTC, datetime

from memcore.backends.base import StoreBackend
from memcore.types import Memory


def ingest_message(
    backend: StoreBackend,
    role: str,
    content: str,
    session_id: str | None = None,
    ts: datetime | None = None,
) -> str:
    """Ingest a single message verbatim.

    Args:
        backend: The storage backend (ChromaBackend or HybridBackend).
        role: Message role (user, assistant, tool, system).
        content: Raw message text — stored as-is, no extraction.
        session_id: Optional session/thread identifier.
        ts: Optional timestamp (defaults to now).

    Returns:
        The storage ID assigned to this memory.
    """
    if not content.strip():
        return ""

    memory = Memory(
        id="",
        content=content,
        role=role,
        ts=ts or datetime.now(UTC),
        session_id=session_id,
    )
    return backend.ingest(memory)


def ingest_batch(
    backend: StoreBackend,
    messages: list[dict],
    session_id: str | None = None,
) -> list[str]:
    """Ingest a batch of messages.

    Args:
        backend: The storage backend.
        messages: List of {"role": str, "content": str} dicts.
        session_id: Optional session/thread identifier.

    Returns:
        List of storage IDs.
    """
    ids = []
    for msg in messages:
        mid = ingest_message(
            backend=backend,
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            session_id=session_id,
        )
        if mid:
            ids.append(mid)
    return ids
