"""MCP-Skill Integration with HITL approval.

This module manages the lifecycle of skills that are auto-detected from MCP servers,
allowing users to view, approve, edit, or reject skills before they're loaded into context.
"""

from pathlib import Path
from typing import Any, Dict, List
import json
from datetime import datetime, timezone

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.config.settings import get_settings


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_pending_skills_dir() -> Path:
    """Get directory for pending skill approvals."""
    thread_id = get_thread_id()
    if not thread_id:
        raise RuntimeError("No thread_id context")

    pending_dir = get_settings().get_thread_root(thread_id) / "mcp" / "pending_skills"
    pending_dir.mkdir(parents=True, exist_ok=True)
    return pending_dir


class MCPSkillProposal:
    """Represents a proposed skill from an MCP server."""

    def __init__(self, skill_name: str, source_server: str, reason: str, content: str = ""):
        self.skill_name = skill_name
        self.source_server = source_server  # Which MCP server needs this
        self.reason = reason  # Why this skill is recommended
        self.content = content  # The skill content (if pre-canned)
        self.created_at = _utc_now()
        self.status = "pending"  # pending, approved, rejected

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "skill_name": self.skill_name,
            "source_server": self.source_server,
            "reason": self.reason,
            "content": self.content,
            "created_at": self.created_at,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MCPSkillProposal":
        """Create from dictionary."""
        obj = cls(
            skill_name=data["skill_name"],
            source_server=data["source_server"],
            reason=data["reason"],
            content=data.get("content", ""),
        )
        obj.created_at = data.get("created_at", _utc_now())
        obj.status = data.get("status", "pending")
        return obj


def save_pending_skill(proposal: MCPSkillProposal) -> None:
    """Save a pending skill proposal to storage."""
    pending_dir = get_pending_skills_dir()

    # Save to file named: {skill_name}.json
    file_path = pending_dir / f"{proposal.skill_name}.json"
    file_path.write_text(json.dumps(proposal.to_dict(), indent=2))


def load_pending_skill(skill_name: str) -> MCPSkillProposal:
    """Load a pending skill proposal."""
    pending_dir = get_pending_skills_dir()
    file_path = pending_dir / f"{skill_name}.json"

    if not file_path.exists():
        return None

    data = json.loads(file_path.read_text())
    return MCPSkillProposal.from_dict(data)


def list_pending_skills() -> List[MCPSkillProposal]:
    """List all pending skill proposals."""
    pending_dir = get_pending_skills_dir()
    proposals = []

    for file_path in pending_dir.glob("*.json"):
        try:
            data = json.loads(file_path.read_text())
            proposal = MCPSkillProposal.from_dict(data)
            if proposal.status == "pending":
                proposals.append(proposal)
        except Exception as e:
            print(f"Warning: Could not load pending skill from {file_path}: {e}")

    # Sort by created_at (newest first)
    proposals.sort(key=lambda p: p.created_at, reverse=True)
    return proposals


def delete_pending_skill(skill_name: str) -> None:
    """Delete a pending skill proposal."""
    pending_dir = get_pending_skills_dir()
    file_path = pending_dir / f"{skill_name}.json"

    if file_path.exists():
        file_path.unlink()


def approve_skill(skill_name: str) -> None:
    """Mark a skill as approved (will be loaded on next reload)."""
    proposal = load_pending_skill(skill_name)
    if not proposal:
        raise ValueError(f"Pending skill '{skill_name}' not found")

    proposal.status = "approved"
    save_pending_skill(proposal)


def reject_skill(skill_name: str) -> None:
    """Mark a skill as rejected."""
    proposal = load_pending_skill(skill_name)
    if not proposal:
        raise ValueError(f"Pending skill '{skill_name}' not found")

    proposal.status = "rejected"
    save_pending_skill(proposal)


def get_approved_skills() -> List[str]:
    """Get list of approved skill names."""
    pending_dir = get_pending_skills_dir()
    approved = []

    for file_path in pending_dir.glob("*.json"):
        try:
            data = json.loads(file_path.read_text())
            if data.get("status") == "approved":
                approved.append(data["skill_name"])
        except Exception:
            pass

    return approved
