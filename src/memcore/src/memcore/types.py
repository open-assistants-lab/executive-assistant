"""Core types for memcore."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Memory:
    """A single memory entry — one message or conversation turn."""
    id: str
    content: str
    role: str = "user"
    ts: datetime | None = None
    session_id: str | None = None
    workspace_id: str | None = None
    score: float = 0.0

    def dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "ts": self.ts.isoformat() if self.ts else None,
            "session_id": self.session_id,
            "score": self.score,
        }


@dataclass
class SearchResult:
    """Result from a memory search."""
    memory: Memory
    score: float = 0.0
    source: str = "semantic"


@dataclass
class SearchQuery:
    """A search query with optional filters."""
    text: str
    limit: int = 10
    wing: str | None = None
    room: str | None = None

    def dict(self) -> dict:
        return {
            "text": self.text,
            "limit": self.limit,
            "wing": self.wing,
            "room": self.room,
        }
