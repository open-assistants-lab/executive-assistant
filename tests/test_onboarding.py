"""Tests for onboarding detection and utilities."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from executive_assistant.utils.onboarding import (
    is_vague_request,
    is_user_data_empty,
    mark_onboarding_started,
    mark_onboarding_complete,
    has_completed_onboarding,
    should_show_onboarding,
)
from executive_assistant.config import settings


class TestVagueRequest:
    """Test vague request detection."""

    def test_greeting_patterns(self):
        """Test that greetings are detected as vague."""
        assert is_vague_request("hi")
        assert is_vague_request("hi!")
        assert is_vague_request("Hi!")
        assert is_vague_request("hello")
        assert is_vague_request("Hello!")
        assert is_vague_request("hey")

    def test_help_request(self):
        """Test that 'help' is detected as vague."""
        assert is_vague_request("help")
        assert is_vague_request("Help!")
        assert is_vague_request("help!")

    def test_capability_question(self):
        """Test that generic capability questions are vague."""
        assert is_vague_request("what can you do")
        assert is_vague_request("What can you do?")

    def test_incomplete_sentences(self):
        """Test that incomplete sentences are detected as vague."""
        assert is_vague_request("i need")
        assert is_vague_request("I want")
        # "I need help with" is NOT vague - has enough content to be actionable

    def test_specific_requests_not_vague(self):
        """Test that specific requests are NOT vague."""
        assert not is_vague_request("create a table named users")
        assert not is_vague_request("what is the weather in Tokyo")
        assert not is_vague_request("help me create a database")
        assert not is_vague_request("I need you to build a sales tracker")

    def test_empty_input(self):
        """Test that empty input is not vague."""
        assert not is_vague_request("")
        assert not is_vague_request(None)


class TestOnboardingDetection:
    """Test onboarding detection based on user data folder."""

    @patch('executive_assistant.utils.onboarding.settings')
    def test_empty_folder_triggers_onboarding(self, mock_settings, tmp_path):
        """Test that empty user data folder triggers onboarding."""
        # Mock user root that exists but is empty
        mock_settings.get_thread_root.return_value = tmp_path

        result = is_user_data_empty("test_thread")
        assert result is True

    @patch('executive_assistant.utils.onboarding.settings')
    def test_nonexistent_folder_triggers_onboarding(self, mock_settings, tmp_path):
        """Test that nonexistent user data folder triggers onboarding."""
        # Mock user root that doesn't exist
        mock_settings.get_thread_root.return_value = tmp_path / "nonexistent"

        result = is_user_data_empty("test_thread")
        assert result is True

    @patch('executive_assistant.utils.onboarding.settings')
    def test_tdb_files_prevent_onboarding(self, mock_settings, tmp_path):
        """Test that TDB database files prevent onboarding."""
        user_root = tmp_path
        tdb_dir = user_root / "tdb"
        tdb_dir.mkdir(parents=True)
        (tdb_dir / "db.sqlite").touch()

        mock_settings.get_thread_root.return_value = user_root

        result = is_user_data_empty("test_thread")
        assert result is False

    @patch('executive_assistant.utils.onboarding.settings')
    def test_vdb_files_prevent_onboarding(self, mock_settings, tmp_path):
        """Test that VDB database files prevent onboarding."""
        user_root = tmp_path
        vdb_dir = user_root / "vdb"
        vdb_dir.mkdir(parents=True)
        (vdb_dir / "some_data").touch()

        mock_settings.get_thread_root.return_value = user_root

        result = is_user_data_empty("test_thread")
        assert result is False

    @patch('executive_assistant.utils.onboarding.settings')
    def test_user_files_prevent_onboarding(self, mock_settings, tmp_path):
        """Test that user files prevent onboarding."""
        user_root = tmp_path
        files_dir = user_root / "files"
        files_dir.mkdir(parents=True)
        (files_dir / "document.txt").touch()

        mock_settings.get_thread_root.return_value = user_root

        result = is_user_data_empty("test_thread")
        assert result is False

    @patch('executive_assistant.utils.onboarding.settings')
    def test_marker_file_prevents_retriggering(self, mock_settings, tmp_path):
        """Test that onboarding marker prevents re-triggering during conversation."""
        user_root = tmp_path
        # Create marker file
        (user_root / ".onboarding_in_progress").touch()

        mock_settings.get_thread_root.return_value = user_root

        result = is_user_data_empty("test_thread")
        assert result is False


class TestOnboardingMarkers:
    """Test onboarding start/complete markers."""

    @patch('executive_assistant.utils.onboarding.settings')
    def test_mark_onboarding_started(self, mock_settings, tmp_path):
        """Test that onboarding start marker is created."""
        mock_settings.get_thread_root.return_value = tmp_path

        mark_onboarding_started("test_thread")

        marker_file = tmp_path / ".onboarding_in_progress"
        assert marker_file.exists()

    @patch('executive_assistant.utils.onboarding.settings')
    def test_mark_onboarding_complete_removes_marker(self, mock_settings, tmp_path):
        """Test that onboarding completion removes marker."""
        user_root = tmp_path
        marker_file = user_root / ".onboarding_in_progress"
        marker_file.touch()

        mock_settings.get_thread_root.return_value = user_root

        mark_onboarding_complete("test_thread")

        assert not marker_file.exists()

    @patch('executive_assistant.utils.onboarding.settings')
    @patch('executive_assistant.tools.mem_tools.create_memory')
    def test_mark_onboarding_complete_creates_memory(self, mock_create_memory, mock_settings, tmp_path):
        """Test that onboarding completion creates a memory."""
        mock_settings.get_thread_root.return_value = tmp_path

        mark_onboarding_complete("test_thread")

        # Verify create_memory was called
        mock_create_memory.assert_called_once()
        call_kwargs = mock_create_memory.call_args[1]
        assert call_kwargs["key"] == "onboarding_complete"
        assert call_kwargs["memory_type"] == "system"
        assert "completed" in call_kwargs["content"].lower()


class TestHasCompletedOnboarding:
    """Test checking if user has completed onboarding."""

    @patch('executive_assistant.utils.onboarding.get_mem_storage')
    def test_no_memories_means_not_completed(self, mock_get_mem_storage):
        """Test that no memories means onboarding not completed."""
        mock_storage = Mock()
        mock_storage.list_memories.return_value = []
        mock_get_mem_storage.return_value = mock_storage

        result = has_completed_onboarding("test_thread")
        assert result is False

    @patch('executive_assistant.utils.onboarding.get_mem_storage')
    def test_completion_marker_detected(self, mock_get_mem_storage):
        """Test that completion marker is detected."""
        mock_storage = Mock()
        mock_storage.list_memories.return_value = [
            {"key": "onboarding_complete", "content": "Onboarding completed"},
            {"key": "role", "content": "Developer"},
        ]
        mock_get_mem_storage.return_value = mock_storage

        result = has_completed_onboarding("test_thread")
        assert result is True

    @patch('executive_assistant.utils.onboarding.get_mem_storage')
    def test_other_memories_no_completion_marker(self, mock_get_mem_storage):
        """Test that other memories without completion marker means not completed."""
        mock_storage = Mock()
        mock_storage.list_memories.return_value = [
            {"key": "role", "content": "Developer"},
            {"key": "name", "content": "John"},
        ]
        mock_get_mem_storage.return_value = mock_storage

        result = has_completed_onboarding("test_thread")
        assert result is False


class TestShouldShowOnboarding:
    """Test should_show_onboarding function."""

    @patch('executive_assistant.utils.onboarding.is_user_data_empty')
    def test_should_show_when_empty(self, mock_is_empty):
        """Test that onboarding should show when data folder is empty."""
        mock_is_empty.return_value = True

        result = should_show_onboarding("test_thread")
        assert result is True

    @patch('executive_assistant.utils.onboarding.is_user_data_empty')
    def test_should_not_show_when_has_data(self, mock_is_empty):
        """Test that onboarding should not show when user has data."""
        mock_is_empty.return_value = False

        result = should_show_onboarding("test_thread")
        assert result is False

    @patch('executive_assistant.utils.onboarding.is_user_data_empty')
    def test_errors_default_to_false(self, mock_is_empty):
        """Test that errors default to not showing onboarding."""
        mock_is_empty.side_effect = Exception("Test error")

        result = should_show_onboarding("test_thread")
        assert result is False
