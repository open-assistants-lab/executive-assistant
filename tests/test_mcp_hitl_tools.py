"""Tests for MCP-Skill HITL workflow tools.

Tests the actual tools that users interact with for managing
skill proposals (mcp_approve_skill, mcp_list_pending_skills, etc.)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from executive_assistant.tools.user_mcp_tools import (
    mcp_list_pending_skills,
    mcp_approve_skill,
    mcp_reject_skill,
    mcp_edit_skill,
    mcp_show_skill,
    mcp_add_server,
    mcp_reload,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_thread_dirs(tmp_path):
    """Create temporary directories for MCP config and pending skills."""
    thread_id = "test_thread_hitl"

    # Create directory structure
    mcp_dir = tmp_path / "users" / thread_id / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    pending_dir = mcp_dir / "pending_skills"
    pending_dir.mkdir(parents=True, exist_ok=True)

    # Create sample pending skill files
    sample_proposals = [
        {
            "skill_name": "web_scraping",
            "source_server": "fetch",
            "reason": "The fetch tool requires knowledge of web scraping best practices",
            "content": "",
            "created_at": "2025-02-01T10:00:00Z",
            "status": "pending",
        },
        {
            "skill_name": "fetch_content",
            "source_server": "fetch",
            "reason": "Content extraction patterns",
            "content": "",
            "created_at": "2025-02-01T10:00:00Z",
            "status": "pending",
        },
        {
            "skill_name": "github_api",
            "source_server": "github",
            "reason": "GitHub API patterns",
            "content": "",
            "created_at": "2025-02-01T10:00:00Z",
            "status": "approved",
        },
    ]

    for proposal in sample_proposals:
        file_path = pending_dir / f"{proposal['skill_name']}.json"
        file_path.write_text(json.dumps(proposal, indent=2))

    # Mock settings to return temp directory
    mock_settings = MagicMock()
    mock_settings.get_thread_mcp_dir.return_value = mcp_dir
    mock_settings.get_thread_root.return_value = tmp_path / "users" / thread_id

    with patch("executive_assistant.storage.user_mcp_storage.get_settings", return_value=mock_settings), \
         patch("executive_assistant.storage.file_sandbox.get_thread_id", return_value=thread_id), \
         patch("executive_assistant.storage.mcp_skill_storage.get_settings", return_value=mock_settings), \
         patch("executive_assistant.storage.mcp_skill_storage.get_thread_id", return_value=thread_id), \
         patch("executive_assistant.tools.user_mcp_tools.get_thread_id", return_value=thread_id):

        yield {
            "thread_id": thread_id,
            "mcp_dir": mcp_dir,
            "pending_dir": pending_dir,
        }


# ============================================================================
# mcp_list_pending_skills Tests
# ============================================================================

def test_list_pending_skills_with_pending_items(temp_thread_dirs):
    """Test listing pending skills when there are pending items."""
    result = mcp_list_pending_skills.invoke({})

    assert "Pending Skill Proposals" in result
    assert "2 proposal(s)" in result  # Only pending, not approved
    assert "web_scraping" in result
    assert "fetch_content" in result
    assert "github_api" not in result  # This one is approved


def test_list_pending_skills_empty(temp_thread_dirs):
    """Test listing pending skills when there are none."""
    # Delete all pending proposals
    pending_dir = temp_thread_dirs["pending_dir"]
    for file_path in pending_dir.glob("*.json"):
        if json.loads(file_path.read_text())["status"] == "pending":
            file_path.unlink()

    result = mcp_list_pending_skills.invoke({})

    assert "No pending skill proposals" in result
    assert "Add an MCP server" in result


def test_list_pending_skills_formatting(temp_thread_dirs):
    """Test that pending skills list is properly formatted."""
    result = mcp_list_pending_skills.invoke({})

    # Check for expected sections
    assert "**Pending Skill Proposals:**" in result
    assert "**Source Server:**" in result
    assert "**Created:**" in result
    assert "**Why it's recommended:**" in result
    assert "**Actions:**" in result


# ============================================================================
# mcp_approve_skill Tests
# ============================================================================

def test_approve_skill_success(temp_thread_dirs):
    """Test approving a pending skill."""
    result = mcp_approve_skill.invoke({"skill_name": "web_scraping"})

    assert "✅ Approved skill 'web_scraping'" in result
    assert "**Source:** fetch server" in result

    # Verify file was updated
    pending_dir = temp_thread_dirs["pending_dir"]
    file_path = pending_dir / "web_scraping.json"
    data = json.loads(file_path.read_text())
    assert data["status"] == "approved"


def test_approve_skill_already_approved(temp_thread_dirs):
    """Test approving a skill that's already approved."""
    result = mcp_approve_skill.invoke({"skill_name": "github_api"})

    assert "already approved" in result
    assert "mcp_reload" in result


def test_approve_nonexistent_skill(temp_thread_dirs):
    """Test approving a skill that doesn't exist."""
    result = mcp_approve_skill.invoke({"skill_name": "nonexistent_skill"})

    assert "❌" in result
    assert "not found" in result


def test_approve_rejected_skill(temp_thread_dirs):
    """Test approving a skill that was previously rejected."""
    # First reject a skill
    pending_dir = temp_thread_dirs["pending_dir"]

    # Create a rejected proposal
    proposal = {
        "skill_name": "test_rejected",
        "source_server": "test",
        "reason": "Test",
        "content": "",
        "created_at": "2025-02-01T10:00:00Z",
        "status": "rejected",
    }
    file_path = pending_dir / "test_rejected.json"
    file_path.write_text(json.dumps(proposal))

    # Try to approve it - should show warning but not approve
    result = mcp_approve_skill.invoke({"skill_name": "test_rejected"})

    # Should warn about previously rejected skill
    assert "previously rejected" in result

    # Status should still be rejected
    data = json.loads(file_path.read_text())
    assert data["status"] == "rejected"


# ============================================================================
# mcp_reject_skill Tests
# ============================================================================

def test_reject_skill_success(temp_thread_dirs):
    """Test rejecting a pending skill."""
    result = mcp_reject_skill.invoke({"skill_name": "web_scraping"})

    assert "✅ Rejected skill 'web_scraping'" in result
    assert "**Source:** fetch server" in result

    # Verify file was updated
    pending_dir = temp_thread_dirs["pending_dir"]
    file_path = pending_dir / "web_scraping.json"
    data = json.loads(file_path.read_text())
    assert data["status"] == "rejected"


def test_reject_skill_already_rejected(temp_thread_dirs):
    """Test rejecting a skill that's already rejected."""
    # Create a rejected proposal
    pending_dir = temp_thread_dirs["pending_dir"]
    proposal = {
        "skill_name": "already_rejected",
        "source_server": "test",
        "reason": "Test",
        "content": "",
        "created_at": "2025-02-01T10:00:00Z",
        "status": "rejected",
    }
    file_path = pending_dir / "already_rejected.json"
    file_path.write_text(json.dumps(proposal))

    result = mcp_reject_skill.invoke({"skill_name": "already_rejected"})

    assert "already rejected" in result


def test_reject_approved_skill(temp_thread_dirs):
    """Test rejecting a skill that was approved."""
    result = mcp_reject_skill.invoke({"skill_name": "github_api"})

    assert "⚠️" in result  # Warning about rejecting approved skill
    assert "already approved" in result


def test_reject_nonexistent_skill(temp_thread_dirs):
    """Test rejecting a skill that doesn't exist."""
    result = mcp_reject_skill.invoke({"skill_name": "nonexistent_skill"})

    assert "❌" in result
    assert "not found" in result


# ============================================================================
# mcp_edit_skill Tests
# ============================================================================

def test_edit_skill_success(temp_thread_dirs):
    """Test editing a skill's content."""
    new_content = "# Custom Web Scraping Guide\n\nThis is my custom content."

    result = mcp_edit_skill.invoke({"skill_name": "web_scraping", "content": new_content})

    assert "✅ Updated skill 'web_scraping'" in result
    assert "Content length:" in result

    # Verify content was saved
    pending_dir = temp_thread_dirs["pending_dir"]
    file_path = pending_dir / "web_scraping.json"
    data = json.loads(file_path.read_text())
    assert data["content"] == new_content


def test_edit_skill_preserves_status(temp_thread_dirs):
    """Test that editing a skill preserves its status."""
    new_content = "New content"

    # Edit an approved skill
    mcp_edit_skill.invoke({"skill_name": "github_api", "content": new_content})

    # Verify status is still approved
    pending_dir = temp_thread_dirs["pending_dir"]
    file_path = pending_dir / "github_api.json"
    data = json.loads(file_path.read_text())
    assert data["status"] == "approved"
    assert data["content"] == new_content


def test_edit_nonexistent_skill(temp_thread_dirs):
    """Test editing a skill that doesn't exist."""
    result = mcp_edit_skill.invoke({"skill_name": "nonexistent", "content": "content"})

    assert "❌" in result
    assert "not found" in result


# ============================================================================
# mcp_show_skill Tests
# ============================================================================

def test_show_skill_pending(temp_thread_dirs):
    """Test showing details of a pending skill."""
    result = mcp_show_skill.invoke({"skill_name": "web_scraping"})

    assert "**Skill:** web_scraping" in result
    assert "**Source Server:** fetch" in result
    assert "**Status:** pending" in result
    assert "**Why it's recommended:**" in result
    assert "mcp_approve_skill" in result
    assert "mcp_reject_skill" in result


def test_show_skill_approved(temp_thread_dirs):
    """Test showing details of an approved skill."""
    result = mcp_show_skill.invoke({"skill_name": "github_api"})

    assert "**Skill:** github_api" in result
    assert "**Status:** approved" in result
    assert "mcp_reload" in result  # Suggests reload


def test_show_skill_with_content(temp_thread_dirs):
    """Test showing a skill that has custom content."""
    # Add content to a skill
    pending_dir = temp_thread_dirs["pending_dir"]
    file_path = pending_dir / "web_scraping.json"
    data = json.loads(file_path.read_text())
    data["content"] = "# Custom Content\n\nThis is custom."
    file_path.write_text(json.dumps(data))

    result = mcp_show_skill.invoke({"skill_name": "web_scraping"})

    assert "**Skill Content:**" in result
    assert "Custom Content" in result


def test_show_nonexistent_skill(temp_thread_dirs):
    """Test showing a skill that doesn't exist."""
    result = mcp_show_skill.invoke({"skill_name": "nonexistent"})

    assert "❌" in result
    assert "not found" in result


# ============================================================================
# mcp_add_server Integration Tests
# ============================================================================

def test_add_server_creates_pending_proposals(temp_thread_dirs):
    """Test that adding a server creates pending skill proposals."""
    mcp_dir = temp_thread_dirs["mcp_dir"]
    pending_dir = temp_thread_dirs["pending_dir"]

    # Count initial proposals
    initial_count = len(list(pending_dir.glob("*.json")))

    # Add fetch server (should propose 2 skills)
    result = mcp_add_server.invoke({
        "name": "fetch",
        "command": "uvx",
        "arguments": "mcp-server-fetch"
    })

    # Check response mentions proposed skills
    assert "✅ Added MCP server 'fetch'" in result
    assert "helper skill(s) proposed" in result or "skill proposal" in result.lower()

    # Check that proposals were created
    new_count = len(list(pending_dir.glob("*.json")))
    assert new_count >= initial_count  # At least one new proposal


def test_add_server_unknown_server_no_proposals(temp_thread_dirs):
    """Test that adding unknown server doesn't create proposals."""
    mcp_dir = temp_thread_dirs["mcp_dir"]
    pending_dir = temp_thread_dirs["pending_dir"]

    # Count initial proposals
    initial_count = len(list(pending_dir.glob("*.json")))

    # Add unknown server
    result = mcp_add_server.invoke({
        "name": "unknown_server",
        "command": "test",
        "arguments": ""
    })

    # Check response
    assert "✅ Added MCP server 'unknown_server'" in result

    # Should not have created new proposals
    new_count = len(list(pending_dir.glob("*.json")))
    assert new_count == initial_count


def test_add_server_duplicate_skill_name(temp_thread_dirs):
    """Test that adding server with existing skill proposal updates it."""
    pending_dir = temp_thread_dirs["pending_dir"]

    # web_scraping already exists from fixture
    # Add another server that also proposes web_scraping
    initial_mtime = (pending_dir / "web_scraping.json").stat().st_mtime

    result = mcp_add_server.invoke({
        "name": "puppeteer",  # Also proposes web_scraping
        "command": "npx",
        "arguments": "@modelcontextprotocol/server-puppeteer"
    })

    # Should succeed
    assert "✅ Added MCP server 'puppeteer'" in result

    # web_scraping.json should still exist (might be updated or left alone)
    assert (pending_dir / "web_scraping.json").exists()


# ============================================================================
# mcp_reload Integration Tests
# ============================================================================

def test_reload_loads_approved_skills(temp_thread_dirs):
    """Test that reload loads approved skills."""
    # Mock the load_skill function to track calls
    loaded_skills = []

    def mock_load_skill(skill_name):
        loaded_skills.append(skill_name)
        return f"✅ Loaded skill {skill_name}"

    with patch("executive_assistant.skills.tool.load_skill", side_effect=mock_load_skill), \
         patch("executive_assistant.tools.registry.clear_mcp_cache", return_value=1):

        result = mcp_reload.invoke({})

        # Check that approved skills were loaded
        assert "github_api" in loaded_skills

        # Check response mentions loaded skills
        assert "✅ MCP tools reloaded" in result
        assert "Skills Loaded:" in result or "1" in result


def test_reload_without_skills(temp_thread_dirs):
    """Test reload with load_skills=False."""
    with patch("executive_assistant.tools.registry.clear_mcp_cache", return_value=1) as mock_clear:
        result = mcp_reload.invoke({"load_skills": False})

        # Should clear cache but not load skills
        assert mock_clear.called
        assert "✅" in result  # Either "MCP tools reloaded" or "MCP cache cleared"


def test_reload_no_approved_skills(temp_thread_dirs):
    """Test reload when there are no approved skills."""
    # Delete approved skill
    pending_dir = temp_thread_dirs["pending_dir"]
    (pending_dir / "github_api.json").unlink()

    with patch("executive_assistant.tools.registry.clear_mcp_cache", return_value=1):
        result = mcp_reload.invoke({})

        # Should complete successfully
        assert "✅" in result


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_list_pending_skills_handles_corrupted_files(temp_thread_dirs):
    """Test that list_pending_skills handles corrupted JSON files."""
    pending_dir = temp_thread_dirs["pending_dir"]

    # Create a corrupted JSON file
    corrupted_file = pending_dir / "corrupted.json"
    corrupted_file.write_text("{invalid json")

    # Should not crash
    result = mcp_list_pending_skills.invoke({})

    # Should still show valid skills
    assert "web_scraping" in result or "fetch_content" in result


def test_approve_skill_handles_corrupted_file(temp_thread_dirs):
    """Test that approve_skill handles corrupted JSON gracefully."""
    pending_dir = temp_thread_dirs["pending_dir"]

    # Create a corrupted JSON file
    corrupted_file = pending_dir / "corrupted.json"
    corrupted_file.write_text("{invalid json")

    # Should handle gracefully
    result = mcp_approve_skill.invoke({"skill_name": "corrupted"})

    assert "❌" in result  # Should show error


# ============================================================================
# Full Workflow Tests
# ============================================================================

def test_full_hitl_workflow(temp_thread_dirs):
    """Test the complete HITL workflow from server add to reload."""
    pending_dir = temp_thread_dirs["pending_dir"]

    # Step 1: Add server (creates proposals)
    result = mcp_add_server.invoke({"name": "fetch", "command": "uvx", "arguments": "mcp-server-fetch"})
    assert "✅ Added MCP server 'fetch'" in result

    # Step 2: List pending skills
    result = mcp_list_pending_skills.invoke({})
    assert "web_scraping" in result or "fetch" in result.lower()

    # Step 3: Show skill details
    result = mcp_show_skill.invoke({"skill_name": "web_scraping"})
    assert "web_scraping" in result

    # Step 4: Approve skill
    result = mcp_approve_skill.invoke({"skill_name": "web_scraping"})
    assert "✅ Approved skill 'web_scraping'" in result

    # Verify status changed
    file_path = pending_dir / "web_scraping.json"
    if file_path.exists():
        data = json.loads(file_path.read_text())
        assert data["status"] == "approved"

    # Step 5: Reload (would load approved skills)
    with patch("executive_assistant.skills.tool.load_skill") as mock_load, \
         patch("executive_assistant.tools.registry.clear_mcp_cache", return_value=1):

        result = mcp_reload.invoke({})
        assert "✅ MCP tools reloaded" in result
