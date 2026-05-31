"""Core types for coremem."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Memory:
    """A single memory entry — one message or conversation turn."""
    id: str
    content: str
    role: str = "user"
    ts: datetime | None = None
    session_id: str | None = None
    user_id: str = ""
    agent_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "ts": self.ts.isoformat() if self.ts else None,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    """Result from a memory search."""
    memory: Memory
    score: float = 0.0
    source: str = "semantic"


@dataclass
class SearchQuery:
    """A search query with optional metadata and column filters."""
    text: str
    limit: int = 10
    role: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    ts_after: str | None = None
    ts_before: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
