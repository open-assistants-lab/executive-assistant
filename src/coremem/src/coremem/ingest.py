"""Verbatim message ingestion — shared pipeline.

All backends ingest raw text without LLM extraction.
The only processing is deterministic: assign IDs, timestamps,
and attach metadata (role, session_id).

No fact extraction. No summarization. No LLM calls.
"""

from datetime import UTC, datetime
from typing import Any

from coremem.backends.base import StoreBackend
from coremem.types import Memory


def ingest_message(
    backend: StoreBackend, role: str, content: str,
    session_id: str | None = None,
    user_id: str = "",
    agent_id: str = "",
    ts: datetime | None = None,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
) -> str:
    """Store a single message.

    Args:
        backend: The storage backend.
        role: Message role (user, assistant, tool, system).
        content: Raw message text.
        session_id: Optional session/thread identifier.
        user_id: Optional user identifier.
        agent_id: Optional agent identifier.
        ts: Optional timestamp. Defaults to now if not provided.
        metadata: Optional arbitrary key-value pairs for filtering.
        embedding: Optional pre-computed embedding vector.

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
        user_id=user_id,
        agent_id=agent_id,
        metadata=metadata or {},
    )
    return backend.ingest(memory, embedding=embedding)


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
            metadata=msg.get("metadata"),
        )
        if mid:
            ids.append(mid)
    return ids
