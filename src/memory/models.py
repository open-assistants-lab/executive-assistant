"""Memory models for Executive Assistant."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.memory.types import MemoryType


class Memory(BaseModel):
    """A single memory entry."""

    id: Optional[str] = None
    title: str = Field(..., description="Brief title of the memory")
    type: MemoryType = Field(..., description="Type of memory")
    narrative: str = Field(..., description="Main content/narrative of the memory")
    facts: list[str] = Field(default_factory=list, description="Extracted facts")
    concepts: list[str] = Field(default_factory=list, description="Key concepts/topics")
    entities: list[str] = Field(default_factory=list, description="Named entities mentioned")
    source: Optional[str] = Field(
        default=None, description="Source of memory (conversation, tool, etc.)"
    )
    session_id: Optional[str] = Field(default=None, description="Session where created")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    archived: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class MemorySearchResult(BaseModel):
    """Result from memory search."""

    id: str
    title: str
    type: MemoryType
    narrative: str
    score: float = Field(..., description="Relevance score")
    highlights: list[str] = Field(default_factory=list, description="Matching excerpts")


class MemoryTimelineEntry(BaseModel):
    """Timeline entry for memory history."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    title: str
    type: MemoryType
    summary: str = Field(..., description="Brief summary")
    session_id: Optional[str] = None
