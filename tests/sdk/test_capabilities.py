"""Tests for capabilities loading, merging, and defaults."""
import tempfile
from pathlib import Path

import yaml

from src.sdk.capabilities import (
    _tool_default,
    load_capabilities,
    merge_capabilities,
    tool_enabled,
)


def make_caps(path: str, data: dict):
    """Helper: write capabilities.yaml to a temp path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.dump(data))


def test_load_capabilities_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as d:
        caps = load_capabilities(d)
    assert caps == {"tools": {}, "skills": {}, "subagents": {}}


def test_load_capabilities_reads_yaml():
    with tempfile.TemporaryDirectory() as d:
        make_caps(f"{d}/capabilities.yaml", {
            "version": 1,
            "tools": {"files_read": True, "files_delete": False},
            "skills": {"file-management": True},
            "subagents": {},
        })
        caps = load_capabilities(d)
    assert caps["tools"]["files_read"] is True
    assert caps["tools"]["files_delete"] is False
    assert caps["skills"]["file-management"] is True


def test_merge_workspace_overrides_user():
    user = {"tools": {"files_read": True, "files_delete": False, "shell_execute": False}}
    workspace = {"tools": {"files_delete": True, "browser_open": True}}

    merged = merge_capabilities(user, workspace)
    assert merged["tools"]["files_read"] is True     # inherited
    assert merged["tools"]["files_delete"] is True   # overridden
    assert merged["tools"]["shell_execute"] is False  # inherited
    assert merged["tools"]["browser_open"] is True    # workspace-only


def test_merge_workspace_false_disables():
    user = {"tools": {"files_read": True}}
    workspace = {"tools": {"files_read": False}}
    merged = merge_capabilities(user, workspace)
    assert merged["tools"]["files_read"] is False


def test_merge_skills_and_subagents():
    user = {"tools": {}, "skills": {"agent-browser": True}, "subagents": {"researcher": True}}
    workspace = {"tools": {}, "skills": {"agent-browser": False}, "subagents": {}}
    merged = merge_capabilities(user, workspace)
    assert merged["skills"]["agent-browser"] is False
    assert merged["subagents"]["researcher"] is True


def test_tool_default_read_only():
    assert _tool_default({"read_only": True, "destructive": False}) is True


def test_tool_default_destructive():
    assert _tool_default({"read_only": False, "destructive": True}) is False


def test_tool_default_both_true_safety_wins():
    assert _tool_default({"read_only": True, "destructive": True}) is False


def test_tool_default_both_false():
    assert _tool_default({"read_only": False, "destructive": False}) is True


def test_tool_enabled_explicit():
    caps = {"tools": {"time_get": True, "files_delete": False}}
    assert tool_enabled(caps, "time_get", {"read_only": True, "destructive": False}) is True
    assert tool_enabled(caps, "files_delete", {"read_only": False, "destructive": True}) is False


def test_tool_enabled_missing_uses_default():
    caps = {"tools": {}}
    assert tool_enabled(caps, "files_read", {"read_only": True, "destructive": False}) is True
    assert tool_enabled(caps, "shell_execute", {"read_only": False, "destructive": True}) is False
