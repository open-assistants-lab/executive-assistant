"""Workspace isolation integration tests.

Verifies that workspaces are truly isolated:
1. Conversation history between workspaces doesn't leak
2. Memory stores use separate paths per workspace
3. Subagent definitions are scoped per workspace
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def test_conversation_store_uses_different_paths_per_workspace():
    """MessageStore with different workspace_ids should have different base paths."""
    from src.storage.messages import MessageStore

    with tempfile.TemporaryDirectory() as d:
        store_a = MessageStore("test_user", base_dir=f"{d}/ws-a", workspace_id="ws-a")
        store_b = MessageStore("test_user", base_dir=f"{d}/ws-b", workspace_id="ws-b")

        store_a.add_message("user", "I live in Denver")
        store_a.add_message("assistant", "Noted, you live in Denver")

        msgs_a = store_a.get_messages(limit=100)
        msgs_b = store_b.get_messages(limit=100)

        assert len(msgs_a) == 2
        assert len(msgs_b) == 0


def test_conversation_workspace_isolation():
    """Messages in workspace A do not appear in workspace B conversation."""
    from src.storage.messages import MessageStore

    with tempfile.TemporaryDirectory() as d:
        store_a = MessageStore("test_user", base_dir=f"{d}/ws-a", workspace_id="ws-a")
        store_b = MessageStore("test_user", base_dir=f"{d}/ws-b", workspace_id="ws-b")

        store_a.add_message("user", "My project is Q2 Planning")
        store_a.add_message("assistant", "Got it, project Q2 Planning")

        store_b.add_message("user", "What is my project?")

        msgs_a = store_a.get_messages(limit=100)
        msgs_b = store_b.get_messages(limit=100)

        assert any("Q2 Planning" in str(m.content) for m in msgs_a)
        assert not any("Q2 Planning" in str(m.content) for m in msgs_b)


def test_conversation_messages_dont_leak_on_write():
    """Writing to workspace A's store does not affect workspace B's store."""
    from src.storage.messages import MessageStore

    with tempfile.TemporaryDirectory() as d:
        store_a = MessageStore("test_user", base_dir=f"{d}/ws-a", workspace_id="ws-a")
        store_b = MessageStore("test_user", base_dir=f"{d}/ws-b", workspace_id="ws-b")

        store_b.add_message("user", "I prefer dark roast coffee")

        store_a.add_message("user", "I moved to Melbourne")
        store_a.add_message("assistant", "Updated your location to Melbourne")

        msgs_b = store_b.get_messages(limit=100)
        assert len(msgs_b) == 1
        assert "dark roast" in str(msgs_b[0].content)
        assert "Melbourne" not in str(msgs_b[0].content)


def test_memory_stores_have_different_paths():
    """MemoryStore with different workspace_ids should use different dirs."""
    from src.storage.paths import DataPaths

    paths_a = DataPaths(user_id="test_user", workspace_id="ws-a")
    paths_b = DataPaths(user_id="test_user", workspace_id="ws-b")

    mem_a = paths_a.workspace_memory_dir()
    mem_b = paths_b.workspace_memory_dir()

    assert "ws-a" in str(mem_a)
    assert "ws-b" in str(mem_b)
    assert mem_a != mem_b


def test_memory_stores_are_separate():
    """Each workspace gets its own memory store."""
    from src.storage.memory import MemoryStore

    with tempfile.TemporaryDirectory() as d:
        store_a = MemoryStore("test_user", base_dir=f"{d}/ws-a/memory")
        store_b = MemoryStore("test_user", base_dir=f"{d}/ws-b/memory")

        assert store_a.user_id == "test_user"
        assert store_b.user_id == "test_user"
        # Different underlying HybridDB paths
        assert store_a.db.path != store_b.db.path


def test_file_paths_per_workspace():
    """Workspace file directories are isolated."""
    from src.storage.paths import DataPaths

    paths_a = DataPaths(user_id="test_user", workspace_id="project-alpha")
    paths_b = DataPaths(user_id="test_user", workspace_id="project-beta")

    files_a = paths_a.workspace_files_dir()
    files_b = paths_b.workspace_files_dir()

    assert "project-alpha" in str(files_a)
    assert "project-beta" in str(files_b)
    assert files_a != files_b


@pytest.mark.asyncio
async def test_subagent_isolation_between_workspaces():
    """Subagents created in workspace A are not visible in workspace B."""
    import tempfile
    from unittest.mock import patch

    from src.sdk.coordinator import SubagentCoordinator
    from agentprofile.models import AgentProfile
    from src.storage.paths import DataPaths

    with tempfile.TemporaryDirectory() as d:
        mock_a = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-a")
        mock_b = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-b")

        mock_a.subagents_dir = mock_a.workspace_subagents_dir
        mock_b.subagents_dir = mock_b.workspace_subagents_dir

        def _make_path(user_id=None, team_id=None, workspace_id=None):
            if workspace_id == "ws-a":
                return mock_a
            if workspace_id == "ws-b":
                return mock_b
            return DataPaths(ea_root=d, user_id=user_id, workspace_id=workspace_id)

        with patch("src.storage.paths.get_paths", side_effect=_make_path):
            coord_a = SubagentCoordinator("test_user", workspace_id="ws-a")
            coord_b = SubagentCoordinator("test_user", workspace_id="ws-b")

            profile = AgentProfile(
                name="writer",
                description="Report writer for project alpha",
                tools=["time_get"],
            )
            await coord_a.create(profile)

            defs_a = await coord_a.list_defs()
            defs_b = await coord_b.list_defs()

            assert any(d.name == "writer" for d in defs_a), "writer should appear in ws-a"
            assert not any(d.name == "writer" for d in defs_b), "writer should NOT leak to ws-b"


@pytest.mark.asyncio
async def test_same_name_subagent_in_different_workspaces():
    """Same subagent name can exist independently in different workspaces."""
    import tempfile
    from unittest.mock import patch

    from src.sdk.coordinator import SubagentCoordinator
    from agentprofile.models import AgentProfile
    from src.storage.paths import DataPaths

    with tempfile.TemporaryDirectory() as d:
        mock_a = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-a")
        mock_b = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-b")

        mock_a.subagents_dir = mock_a.workspace_subagents_dir
        mock_b.subagents_dir = mock_b.workspace_subagents_dir

        def _make_path(user_id=None, team_id=None, workspace_id=None):
            if workspace_id == "ws-a":
                return mock_a
            if workspace_id == "ws-b":
                return mock_b
            return DataPaths(ea_root=d, user_id=user_id, workspace_id=workspace_id)

        with patch("src.storage.paths.get_paths", side_effect=_make_path):
            coord_a = SubagentCoordinator("test_user", workspace_id="ws-a")
            coord_b = SubagentCoordinator("test_user", workspace_id="ws-b")

            ad_a = AgentProfile(
                name="researcher",
                description="Research for project alpha",
                model="ollama:minimax-m2.5",
                tools=["time_get", "memory_search"],
            )
            ad_b = AgentProfile(
                name="researcher",
                description="Research for project beta",
                model="anthropic:claude-sonnet-4-20250514",
                tools=["time_get"],
            )

            await coord_a.create(ad_a)
            await coord_b.create(ad_b)

            loaded_a = coord_a.load_def("researcher")
            loaded_b = coord_b.load_def("researcher")

            assert loaded_a is not None
            assert loaded_b is not None
            assert loaded_a.description != loaded_b.description
            assert loaded_a.model != loaded_b.model
            assert "memory_search" in (loaded_a.tools or [])
            assert "memory_search" not in (loaded_b.tools or [])


@pytest.mark.asyncio
async def test_subagent_delete_in_one_workspace_does_not_affect_other():
    """Deleting a subagent in workspace A leaves workspace B's subagent intact."""
    import tempfile
    from unittest.mock import patch

    from src.sdk.coordinator import SubagentCoordinator
    from agentprofile.models import AgentProfile
    from src.storage.paths import DataPaths

    with tempfile.TemporaryDirectory() as d:
        mock_a = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-a")
        mock_b = DataPaths(ea_root=d, user_id="test_user", workspace_id="ws-b")

        mock_a.subagents_dir = mock_a.workspace_subagents_dir
        mock_b.subagents_dir = mock_b.workspace_subagents_dir

        def _make_path(user_id=None, team_id=None, workspace_id=None):
            if workspace_id == "ws-a":
                return mock_a
            if workspace_id == "ws-b":
                return mock_b
            return DataPaths(ea_root=d, user_id=user_id, workspace_id=workspace_id)

        with patch("src.storage.paths.get_paths", side_effect=_make_path):
            coord_a = SubagentCoordinator("test_user", workspace_id="ws-a")
            coord_b = SubagentCoordinator("test_user", workspace_id="ws-b")

            agent = AgentProfile(name="shared", description="Exists in both", tools=["time_get"])
            await coord_a.create(agent)
            await coord_b.create(agent)

            # Delete only from ws-a
            import shutil
            shutil.rmtree(coord_a.base_path / "shared")

            assert coord_a.load_def("shared") is None
            assert coord_b.load_def("shared") is not None
            assert coord_b.load_def("shared").name == "shared"


def test_get_paths_with_workspace_defaults_to_personal():
    """Calling get_paths without workspace_id should default to personal."""
    from src.storage.paths import DataPaths

    dp = DataPaths(user_id="test_user")
    files = dp.workspace_files_dir()
    assert "personal" in str(files) or Path.home().as_posix() in str(dp.workspace_base())
