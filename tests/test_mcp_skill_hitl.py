"""Tests for MCP-Skill HITL workflow.

Tests the Human-in-the-Loop workflow for managing skill proposals
when MCP servers are added.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from executive_assistant.storage.mcp_skill_storage import (
    MCPSkillProposal,
    save_pending_skill,
    load_pending_skill,
    list_pending_skills,
    approve_skill,
    reject_skill,
    get_approved_skills,
    delete_pending_skill,
    get_pending_skills_dir,
)
from executive_assistant.tools.mcp_skill_mapping import (
    MCP_SERVER_SKILLS,
    get_skills_for_server,
    get_skill_recommendation_reason,
    is_server_auto_load,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_pending_skills_dir(tmp_path):
    """Create a temporary pending skills directory."""
    pending_dir = tmp_path / "pending_skills"
    pending_dir.mkdir(parents=True, exist_ok=True)

    # Patch get_pending_skills_dir to return temp directory
    with patch("executive_assistant.storage.mcp_skill_storage.get_pending_skills_dir", return_value=pending_dir):
        yield pending_dir


@pytest.fixture
def sample_proposal():
    """Create a sample skill proposal."""
    return MCPSkillProposal(
        skill_name="web_scraping",
        source_server="fetch",
        reason="The fetch tool requires knowledge of web scraping best practices",
        content="# Web Scraping Guide\n\nThis is a sample skill.",
    )


# ============================================================================
# MCPSkillProposal Tests
# ============================================================================

def test_proposal_initialization(sample_proposal):
    """Test proposal object initialization."""
    assert sample_proposal.skill_name == "web_scraping"
    assert sample_proposal.source_server == "fetch"
    assert sample_proposal.reason == "The fetch tool requires knowledge of web scraping best practices"
    assert sample_proposal.content == "# Web Scraping Guide\n\nThis is a sample skill."
    assert sample_proposal.status == "pending"
    assert sample_proposal.created_at is not None


def test_proposal_to_dict(sample_proposal):
    """Test converting proposal to dictionary."""
    data = sample_proposal.to_dict()

    assert data["skill_name"] == "web_scraping"
    assert data["source_server"] == "fetch"
    assert data["reason"] == "The fetch tool requires knowledge of web scraping best practices"
    assert data["content"] == "# Web Scraping Guide\n\nThis is a sample skill."
    assert data["status"] == "pending"
    assert "created_at" in data


def test_proposal_from_dict():
    """Test creating proposal from dictionary."""
    data = {
        "skill_name": "github_api",
        "source_server": "github",
        "reason": "GitHub tools require API knowledge",
        "content": "# GitHub API Guide",
        "created_at": "2025-02-01T10:00:00Z",
        "status": "approved",
    }

    proposal = MCPSkillProposal.from_dict(data)

    assert proposal.skill_name == "github_api"
    assert proposal.source_server == "github"
    assert proposal.reason == "GitHub tools require API knowledge"
    assert proposal.content == "# GitHub API Guide"
    assert proposal.created_at == "2025-02-01T10:00:00Z"
    assert proposal.status == "approved"


def test_proposal_from_dict_with_defaults():
    """Test creating proposal from dictionary with missing fields."""
    data = {
        "skill_name": "test_skill",
        "source_server": "test_server",
        "reason": "Test reason",
    }

    proposal = MCPSkillProposal.from_dict(data)

    assert proposal.skill_name == "test_skill"
    assert proposal.content == ""  # Default
    assert proposal.status == "pending"  # Default


# ============================================================================
# Storage Tests
# ============================================================================

def test_save_pending_skill(temp_pending_skills_dir, sample_proposal):
    """Test saving a pending skill proposal."""
    save_pending_skill(sample_proposal)

    # Check file was created
    file_path = temp_pending_skills_dir / "web_scraping.json"
    assert file_path.exists()

    # Check file content
    data = json.loads(file_path.read_text())
    assert data["skill_name"] == "web_scraping"
    assert data["source_server"] == "fetch"
    assert data["status"] == "pending"


def test_load_pending_skill(temp_pending_skills_dir, sample_proposal):
    """Test loading a pending skill proposal."""
    # Save first
    save_pending_skill(sample_proposal)

    # Load it back
    loaded = load_pending_skill("web_scraping")

    assert loaded is not None
    assert loaded.skill_name == "web_scraping"
    assert loaded.source_server == "fetch"
    assert loaded.status == "pending"


def test_load_nonexistent_skill(temp_pending_skills_dir):
    """Test loading a skill that doesn't exist."""
    loaded = load_pending_skill("nonexistent_skill")
    assert loaded is None


def test_list_pending_skills(temp_pending_skills_dir):
    """Test listing all pending skills."""
    # Create multiple proposals
    proposals = [
        MCPSkillProposal("skill1", "server1", "Reason 1"),
        MCPSkillProposal("skill2", "server2", "Reason 2"),
        MCPSkillProposal("skill3", "server3", "Reason 3"),
    ]

    # Save all proposals
    for proposal in proposals:
        save_pending_skill(proposal)

    # List pending skills
    pending = list_pending_skills()

    assert len(pending) == 3
    skill_names = {p.skill_name for p in pending}
    assert skill_names == {"skill1", "skill2", "skill3"}


def test_list_pending_skills_excludes_approved(temp_pending_skills_dir):
    """Test that list_pending_skills excludes approved and rejected skills."""
    # Create proposals with different statuses
    pending_proposal = MCPSkillProposal("pending_skill", "server1", "Reason")
    approved_proposal = MCPSkillProposal("approved_skill", "server2", "Reason")
    rejected_proposal = MCPSkillProposal("rejected_skill", "server3", "Reason")

    # Set statuses
    approved_proposal.status = "approved"
    rejected_proposal.status = "rejected"

    # Save all
    save_pending_skill(pending_proposal)
    save_pending_skill(approved_proposal)
    save_pending_skill(rejected_proposal)

    # List pending skills
    pending = list_pending_skills()

    # Should only return pending skills
    assert len(pending) == 1
    assert pending[0].skill_name == "pending_skill"


def test_approve_skill(temp_pending_skills_dir, sample_proposal):
    """Test approving a skill."""
    # Save pending proposal
    save_pending_skill(sample_proposal)

    # Approve it
    approve_skill("web_scraping")

    # Load and check status
    loaded = load_pending_skill("web_scraping")
    assert loaded.status == "approved"


def test_approve_nonexistent_skill(temp_pending_skills_dir):
    """Test approving a skill that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        approve_skill("nonexistent_skill")


def test_reject_skill(temp_pending_skills_dir, sample_proposal):
    """Test rejecting a skill."""
    # Save pending proposal
    save_pending_skill(sample_proposal)

    # Reject it
    reject_skill("web_scraping")

    # Load and check status
    loaded = load_pending_skill("web_scraping")
    assert loaded.status == "rejected"


def test_reject_nonexistent_skill(temp_pending_skills_dir):
    """Test rejecting a skill that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        reject_skill("nonexistent_skill")


def test_get_approved_skills(temp_pending_skills_dir):
    """Test getting list of approved skills."""
    # Create proposals with different statuses
    proposals = [
        MCPSkillProposal("approved1", "server1", "Reason"),
        MCPSkillProposal("approved2", "server2", "Reason"),
        MCPSkillProposal("pending1", "server3", "Reason"),
        MCPSkillProposal("rejected1", "server4", "Reason"),
    ]

    # Set statuses
    proposals[0].status = "approved"
    proposals[1].status = "approved"
    proposals[2].status = "pending"
    proposals[3].status = "rejected"

    # Save all
    for proposal in proposals:
        save_pending_skill(proposal)

    # Get approved skills
    approved = get_approved_skills()

    assert len(approved) == 2
    assert set(approved) == {"approved1", "approved2"}


def test_delete_pending_skill(temp_pending_skills_dir, sample_proposal):
    """Test deleting a pending skill."""
    # Save proposal
    save_pending_skill(sample_proposal)

    # Verify it exists
    file_path = temp_pending_skills_dir / "web_scraping.json"
    assert file_path.exists()

    # Delete it
    delete_pending_skill("web_scraping")

    # Verify it's gone
    assert not file_path.exists()


def test_list_pending_skills_sorted_by_created_at(temp_pending_skills_dir):
    """Test that pending skills are sorted by creation time (newest first)."""
    # Create proposals with specific timestamps
    proposal1 = MCPSkillProposal("skill1", "server1", "Reason")
    proposal1.created_at = "2025-02-01T10:00:00Z"

    proposal2 = MCPSkillProposal("skill2", "server2", "Reason")
    proposal2.created_at = "2025-02-01T12:00:00Z"

    proposal3 = MCPSkillProposal("skill3", "server3", "Reason")
    proposal3.created_at = "2025-02-01T11:00:00Z"

    # Save in different order
    save_pending_skill(proposal1)
    save_pending_skill(proposal3)
    save_pending_skill(proposal2)

    # List pending skills
    pending = list_pending_skills()

    # Should be sorted newest first
    assert pending[0].skill_name == "skill2"  # 12:00
    assert pending[1].skill_name == "skill3"  # 11:00
    assert pending[2].skill_name == "skill1"  # 10:00


# ============================================================================
# Skill Mapping Tests
# ============================================================================

def test_mcp_server_skills_mapping_exists():
    """Test that MCP_SERVER_SKILLS mapping is defined."""
    assert isinstance(MCP_SERVER_SKILLS, dict)
    assert len(MCP_SERVER_SKILLS) > 0


def test_fetch_server_mapping():
    """Test that fetch server has correct skill mapping."""
    assert "fetch" in MCP_SERVER_SKILLS

    fetch_mapping = MCP_SERVER_SKILLS["fetch"]
    assert fetch_mapping["skills"] == ["web_scraping", "fetch_content"]
    assert "reason" in fetch_mapping
    assert fetch_mapping["auto"] is True


def test_github_server_mapping():
    """Test that github server has correct skill mapping."""
    assert "github" in MCP_SERVER_SKILLS

    github_mapping = MCP_SERVER_SKILLS["github"]
    assert "github_api" in github_mapping["skills"]
    assert "code_search" in github_mapping["skills"]
    assert "git_operations" in github_mapping["skills"]
    assert github_mapping["auto"] is True


def test_clickhouse_server_mapping():
    """Test that clickhouse server has correct skill mapping."""
    assert "clickhouse" in MCP_SERVER_SKILLS

    ch_mapping = MCP_SERVER_SKILLS["clickhouse"]
    assert "clickhouse_sql" in ch_mapping["skills"]
    assert "database_queries" in ch_mapping["skills"]
    assert ch_mapping["auto"] is True


def test_get_skills_for_server_exact_match():
    """Test getting skills for server with exact name match."""
    skills = get_skills_for_server("fetch")
    assert skills == ["web_scraping", "fetch_content"]


def test_get_skills_for_server_command_detection():
    """Test getting skills by detecting from command string."""
    # Test fetch detection
    skills = get_skills_for_server("my-custom-fetch", command="uvx mcp-server-fetch")
    assert skills == ["web_scraping", "fetch_content"]

    # Test github detection
    skills = get_skills_for_server("my-github", command="npx @modelcontextprotocol/server-github")
    assert "github_api" in skills
    assert "code_search" in skills


def test_get_skills_for_server_unknown():
    """Test getting skills for unknown server."""
    skills = get_skills_for_server("unknown-server")
    assert skills == []


def test_get_skill_recommendation_reason():
    """Test getting skill recommendation reason."""
    reason = get_skill_recommendation_reason("fetch")
    assert "web scraping" in reason.lower()
    assert len(reason) > 0


def test_get_skill_recommendation_reason_unknown():
    """Test getting reason for unknown server."""
    reason = get_skill_recommendation_reason("unknown")
    assert "help the agent" in reason.lower()


def test_is_server_auto_load():
    """Test checking if server should auto-load skills."""
    assert is_server_auto_load("fetch") is True
    assert is_server_auto_load("github") is True
    assert is_server_auto_load("clickhouse") is True


def test_is_server_auto_load_filesystem():
    """Test that filesystem server is not auto-load (requires paths)."""
    assert is_server_auto_load("filesystem") is False


def test_is_server_auto_load_unknown():
    """Test that unknown servers are not auto-load."""
    assert is_server_auto_load("unknown") is False


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_workflow(temp_pending_skills_dir):
    """Test the complete HITL workflow."""
    # Step 1: Server added creates pending proposals
    skills = get_skills_for_server("fetch")
    assert len(skills) == 2

    for skill_name in skills:
        proposal = MCPSkillProposal(
            skill_name=skill_name,
            source_server="fetch",
            reason=get_skill_recommendation_reason("fetch"),
        )
        save_pending_skill(proposal)

    # Step 2: List pending skills
    pending = list_pending_skills()
    assert len(pending) == 2

    # Step 3: Approve one skill
    approve_skill("web_scraping")
    loaded = load_pending_skill("web_scraping")
    assert loaded.status == "approved"

    # Step 4: Reject one skill
    reject_skill("fetch_content")
    loaded = load_pending_skill("fetch_content")
    assert loaded.status == "rejected"

    # Step 5: Get approved skills
    approved = get_approved_skills()
    assert approved == ["web_scraping"]

    # Step 6: List pending skills should be empty (none pending)
    pending = list_pending_skills()
    assert len(pending) == 0


def test_multiple_servers_same_skill(temp_pending_skills_dir):
    """Test that same skill from different servers doesn't duplicate."""
    # Add same skill from two different servers
    proposal1 = MCPSkillProposal("web_scraping", "fetch", "Reason from fetch")
    proposal2 = MCPSkillProposal("web_scraping", "puppeteer", "Reason from puppeteer")

    save_pending_skill(proposal1)
    save_pending_skill(proposal2)

    # Second save should overwrite first
    pending = list_pending_skills()
    assert len(pending) == 1

    # Should be the latest one (puppeteer)
    loaded = load_pending_skill("web_scraping")
    assert loaded.source_server == "puppeteer"


def test_edit_approved_skill(temp_pending_skills_dir):
    """Test editing an already-approved skill."""
    # Create and approve skill
    proposal = MCPSkillProposal("test_skill", "test_server", "Reason", "Original content")
    save_pending_skill(proposal)
    approve_skill("test_skill")

    # Load the proposal, edit it, and save (correct workflow)
    loaded_proposal = load_pending_skill("test_skill")
    loaded_proposal.content = "Updated content"
    save_pending_skill(loaded_proposal)

    # Load and verify
    final = load_pending_skill("test_skill")
    assert final.content == "Updated content"
    assert final.status == "approved"  # Status preserved


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_list_pending_skills_handles_invalid_json(temp_pending_skills_dir):
    """Test that list_pending_skills handles invalid JSON files gracefully."""
    # Create a valid proposal
    proposal = MCPSkillProposal("valid_skill", "server", "Reason")
    save_pending_skill(proposal)

    # Create an invalid JSON file
    invalid_file = temp_pending_skills_dir / "invalid_skill.json"
    invalid_file.write_text("{invalid json content")

    # Should skip invalid file and return valid ones
    pending = list_pending_skills()
    assert len(pending) == 1
    assert pending[0].skill_name == "valid_skill"


def test_get_approved_skills_handles_invalid_json(temp_pending_skills_dir):
    """Test that get_approved_skills handles invalid JSON gracefully."""
    # Create an approved skill
    proposal = MCPSkillProposal("approved_skill", "server", "Reason")
    proposal.status = "approved"
    save_pending_skill(proposal)

    # Create an invalid JSON file
    invalid_file = temp_pending_skills_dir / "invalid_skill.json"
    invalid_file.write_text("{invalid json content")

    # Should skip invalid file
    approved = get_approved_skills()
    assert "approved_skill" in approved
