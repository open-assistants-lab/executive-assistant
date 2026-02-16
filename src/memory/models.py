"""Memory models for the Executive Assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Types of memories for an executive assistant."""

    PROFILE = "profile"
    CONTACT = "contact"
    PREFERENCE = "preference"
    SCHEDULE = "schedule"
    TASK = "task"
    DECISION = "decision"
    INSIGHT = "insight"
    CONTEXT = "context"
    GOAL = "goal"
    CHAT = "chat"
    FEEDBACK = "feedback"
    PERSONAL = "personal"


class MemorySource(str, Enum):
    """Source of a memory."""

    EXPLICIT = "explicit"
    LEARNED = "learned"
    INFERRED = "inferred"


class Memory(BaseModel):
    """A single memory entry."""

    id: str = Field(..., description="Unique memory identifier")
    title: str = Field(..., description="Short summary (~10 words)")
    subtitle: str | None = Field(None, description="Context (~30 words)")
    narrative: str | None = Field(None, description="Full description (~200 words)")

    type: MemoryType = Field(..., description="Memory type classification")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Confidence score")
    source: MemorySource = Field(MemorySource.LEARNED, description="How memory was acquired")

    facts: list[str] = Field(default_factory=list, description="Key facts extracted")
    concepts: list[str] = Field(default_factory=list, description="Tags/concepts")
    entities: list[str] = Field(default_factory=list, description="Named entities")

    project: str | None = Field(None, description="Associated project")
    occurred_at: datetime | None = Field(None, description="When the event happened")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When memory was created",
    )

    last_accessed: datetime | None = Field(None, description="Last access time")
    access_count: int = Field(0, ge=0, description="Number of times accessed")
    archived: bool = Field(False, description="Soft delete flag")

    def to_search_result(self) -> dict[str, Any]:
        """Convert to lightweight search result (Layer 1)."""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "project": self.project,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "created_at": self.created_at.isoformat(),
            "confidence": self.confidence,
        }

    def to_timeline_entry(self) -> dict[str, Any]:
        """Convert to timeline entry (Layer 2)."""
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "type": self.type.value,
            "project": self.project,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "facts": self.facts[:3],
        }

    def to_full_details(self) -> dict[str, Any]:
        """Convert to full details (Layer 3)."""
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "narrative": self.narrative,
            "type": self.type.value,
            "confidence": self.confidence,
            "source": self.source.value,
            "facts": self.facts,
            "concepts": self.concepts,
            "entities": self.entities,
            "project": self.project,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
        }


class MemoryCreate(BaseModel):
    """Data for creating a new memory."""

    title: str = Field(..., min_length=3, max_length=200)
    subtitle: str | None = Field(None, max_length=500)
    narrative: str | None = Field(None, max_length=2000)

    type: MemoryType = Field(..., description="Memory type")
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    source: MemorySource = Field(MemorySource.LEARNED)

    facts: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)

    project: str | None = None
    occurred_at: datetime | None = None


class MemoryUpdate(BaseModel):
    """Data for updating an existing memory."""

    title: str | None = Field(None, min_length=3, max_length=200)
    subtitle: str | None = Field(None, max_length=500)
    narrative: str | None = Field(None, max_length=2000)

    confidence: float | None = Field(None, ge=0.0, le=1.0)

    facts: list[str] | None = None
    concepts: list[str] | None = None
    entities: list[str] | None = None

    project: str | None = None
    archived: bool | None = None


class MemorySearchResult(BaseModel):
    """Search result with index information."""

    id: str
    title: str
    type: str
    project: str | None
    occurred_at: str | None
    created_at: str
    confidence: float
    score: float | None = None


class MemoryTimelineEntry(BaseModel):
    """Timeline entry with context."""

    id: str
    title: str
    subtitle: str | None
    type: str
    project: str | None
    occurred_at: str | None
    facts: list[str]


class MemorySearchParams(BaseModel):
    """Parameters for memory search."""

    query: str | None = None
    type: MemoryType | None = None
    project: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    order_by: str = Field("date_desc", pattern="^(date_desc|date_asc|relevance)$")


class MemoryTimelineParams(BaseModel):
    """Parameters for timeline retrieval."""

    anchor_id: str | None = None
    query: str | None = None
    depth_before: int = Field(3, ge=0, le=20)
    depth_after: int = Field(3, ge=0, le=20)
    project: str | None = None
