"""Tests for user prompt storage and tools."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.sdk.user_prompt import load_user_prompt, save_user_prompt


class TestUserPromptStorage:
    def test_load_defaults_to_empty_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.storage.paths import DataPaths
            with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
                result = load_user_prompt("test_user")
                assert result == ""

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.storage.paths import DataPaths
            with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
                save_user_prompt("test_user", "Always respond as a pirate.")
                result = load_user_prompt("test_user")
                assert result == "Always respond as a pirate."

    def test_load_nonexistent_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_user_prompt("nonexistent")
            assert result == ""


class TestUserPromptTools:
    """Tools are @tool decorated functions tested via their ToolDefinition."""

    def test_user_prompt_get_defaults_empty(self):
        from src.sdk.tools_core.user_prompt import user_prompt_get
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.storage.paths import DataPaths
            with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
                result = user_prompt_get.invoke({"user_id": "test_user"})
                assert "No custom prompt" in result

    def test_user_prompt_set_and_get_roundtrip(self):
        from src.sdk.tools_core.user_prompt import user_prompt_get, user_prompt_set
        from src.storage.paths import DataPaths
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
                set_result = user_prompt_set.invoke({
                    "prompt": "Be concise and formal.",
                    "user_id": "test_user",
                })
                assert "saved" in set_result.lower()
                get_result = user_prompt_get.invoke({"user_id": "test_user"})
                assert "Be concise and formal" in get_result

    def test_user_prompt_set_empty_clears(self):
        from src.sdk.tools_core.user_prompt import user_prompt_get, user_prompt_set
        from src.storage.paths import DataPaths
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
                user_prompt_set.invoke({"prompt": "Something", "user_id": "u1"})
                user_prompt_set.invoke({"prompt": "", "user_id": "u1"})
                result = user_prompt_get.invoke({"user_id": "u1"})
                assert "No custom prompt" in result
