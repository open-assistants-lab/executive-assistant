"""Tests for EA-specific AgentProfile validation layer."""
import pytest
from unittest.mock import patch

from src.sdk.agent_profile import validate_profile


def test_valid_profile_passes():
    profile_data = {
        "name": "researcher",
        "description": "Research agent",
        "model": "ollama:llama3.2",
        "tools": ["time_get", "files_read"],
        "system_prompt": "You are a researcher.",
    }
    with patch("src.sdk.registry.get_model_info") as mock_model:
        mock_model.return_value = {"provider": "ollama"}
        with patch("src.sdk.native_tools.get_native_tool_names") as mock_tools:
            mock_tools.return_value = {"time_get", "files_read", "files_write"}
            errors = validate_profile(profile_data)
    assert errors == []


def test_unknown_model_rejected():
    with patch("src.sdk.registry.get_model_info", return_value=None):
        errors = validate_profile({
            "name": "bad",
            "description": "x",
            "model": "nonexistent:model",
            "tools": ["time_get"],
            "system_prompt": "x",
        })
    assert any("model" in e.lower() for e in errors)


def test_unknown_tool_rejected():
    with patch("src.sdk.native_tools.get_native_tool_names", return_value={"time_get"}):
        errors = validate_profile({
            "name": "bad",
            "description": "x",
            "model": "ollama:llama3.2",
            "tools": ["nonexistent_tool"],
            "system_prompt": "x",
        })
    assert any("nonexistent_tool" in e for e in errors)


def test_empty_tools_allowed():
    with patch("src.sdk.registry.get_model_info", return_value={"provider": "ollama"}):
        with patch("src.sdk.native_tools.get_native_tool_names", return_value=set()):
            errors = validate_profile({
                "name": "minimal",
                "description": "x",
                "model": "ollama:llama3.2",
                "tools": [],
                "system_prompt": "x",
            })
    assert errors == []
