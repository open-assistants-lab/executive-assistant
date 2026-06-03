"""Tests for ItemScopeDB."""
from __future__ import annotations

import tempfile
from pathlib import Path

from connectkit.item_scopes import ItemScopeDB, ItemScope


def test_set_and_get():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "shell_execute", "selected", ["ws-1", "ws-2"])
    row = db.get("alice", "tool", "shell_execute")
    assert row is not None
    assert row.scope == "selected"
    assert row.workspace_ids == ["ws-1", "ws-2"]


def test_get_missing_returns_none():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    assert db.get("alice", "tool", "nonexistent") is None


def test_set_overwrites():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "shell_execute", "selected", ["ws-1"])
    db.set("alice", "tool", "shell_execute", "all")
    row = db.get("alice", "tool", "shell_execute")
    assert row.scope == "all"
    assert row.workspace_ids == []


def test_delete():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "shell_execute", "all")
    assert db.delete("alice", "tool", "shell_execute")
    assert db.get("alice", "tool", "shell_execute") is None
    assert not db.delete("alice", "tool", "shell_execute")


def test_get_available_names_all():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "all")
    db.set("alice", "tool", "t2", "all")
    names = db.get_available_names("alice", "tool", "any-workspace")
    assert names == {"t1", "t2"}


def test_get_available_names_selected():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "selected", ["ws-a"])
    db.set("alice", "tool", "t2", "selected", ["ws-b"])
    assert "t1" in db.get_available_names("alice", "tool", "ws-a")
    assert "t2" not in db.get_available_names("alice", "tool", "ws-a")


def test_get_available_names_excludes_none():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "none")
    db.set("alice", "tool", "t2", "all")
    names = db.get_available_names("alice", "tool", "ws-a")
    assert "t1" not in names
    assert "t2" in names


def test_get_excluded_names():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "none")
    db.set("alice", "skill", "s1", "none")
    assert db.get_excluded_names("alice", "tool") == {"t1"}
    assert db.get_excluded_names("alice", "skill") == {"s1"}


def test_get_all_scoped():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "all")
    db.set("alice", "tool", "t2", "selected", ["ws-1"])
    scoped = db.get_all_scoped("alice", "tool")
    assert len(scoped) == 2
    assert scoped["t1"].scope == "all"
    assert scoped["t2"].scope == "selected"


def test_list_all_for_type():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "all")
    db.set("alice", "tool", "t2", "none")
    db.set("alice", "skill", "s1", "all")
    tools = db.list_all_for_type("alice", "tool")
    skills = db.list_all_for_type("alice", "skill")
    assert len(tools) == 2
    assert len(skills) == 1


def test_remove_workspace():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "selected", ["ws-1", "ws-2"])
    db.set("alice", "tool", "t2", "selected", ["ws-2"])
    changed = db.remove_workspace("alice", "ws-2")
    assert changed == 2
    row = db.get("alice", "tool", "t1")
    assert row.scope == "selected"
    assert "ws-2" not in row.workspace_ids
    row2 = db.get("alice", "tool", "t2")
    assert row2.scope == "none"


def test_user_isolation():
    d = tempfile.mkdtemp()
    db = ItemScopeDB(d)
    db.set("alice", "tool", "t1", "all")
    db.set("bob", "tool", "t1", "none")
    assert db.get("alice", "tool", "t1").scope == "all"
    assert db.get("bob", "tool", "t1").scope == "none"
