from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api.routes.chat import _safe_history_path


def test_safe_history_path_accepts_valid_thread_id(tmp_path: Path) -> None:
    path = _safe_history_path(tmp_path, "api-user-123-clear-20260218120000-abcd1234")
    assert path == (tmp_path / "api-user-123-clear-20260218120000-abcd1234.md").resolve()


@pytest.mark.parametrize("thread_id", ["../escape", "a/b", "a\\b", ""])
def test_safe_history_path_rejects_path_traversal(tmp_path: Path, thread_id: str) -> None:
    with pytest.raises(HTTPException):
        _safe_history_path(tmp_path, thread_id)
