
from pydantic import BaseModel, Field


class SubagentConfig(BaseModel):
    """Subagent configuration."""

    name: str = Field(..., min_length=1, max_length=50)
    model: str | None = None
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    class Config:
        extra = "ignore"
