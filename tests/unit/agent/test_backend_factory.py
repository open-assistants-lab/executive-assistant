from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from deepagents.backends import FilesystemBackend, StateBackend

from src.agent.factory import _make_user_backend_factory

if TYPE_CHECKING:
    from pathlib import Path


def test_conversation_history_route_persists_to_filesystem(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    runtime = SimpleNamespace(state={"files": {}})

    backend_factory = _make_user_backend_factory(user_id="user-123", data_path=data_path)
    backend = backend_factory(runtime)

    assert "/conversation_history/" in backend.routes
    assert isinstance(backend.routes["/conversation_history/"], FilesystemBackend)

    backend.write("/conversation_history/thread-1.md", "summary content")

    history_file = data_path / "users" / "user-123" / ".conversation_history" / "thread-1.md"
    assert history_file.exists()
    assert history_file.read_text() == "summary content"
    assert runtime.state["files"] == {}


def test_unrouted_paths_still_use_state_backend(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    runtime = SimpleNamespace(state={"files": {}})

    backend_factory = _make_user_backend_factory(user_id="user-123", data_path=data_path)
    backend = backend_factory(runtime)

    assert isinstance(backend.default, StateBackend)

    backend.write("/scratch.md", "temporary")

    assert "/scratch.md" in runtime.state["files"]
