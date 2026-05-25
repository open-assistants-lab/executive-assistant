"""Tests for user prompt HTTP API."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_user_prompt_defaults_empty(client):
    """GET /user/prompt returns empty when no prompt set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.storage.paths import DataPaths
        with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
            r = client.get("/user/prompt", params={"user_id": "test_user"})
            assert r.status_code == 200
            assert r.json()["prompt"] == ""


def test_put_user_prompt_saves_and_get_returns_it(client):
    """PUT /user/prompt saves, GET returns it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.storage.paths import DataPaths
        with patch.object(DataPaths, "user_config_dir", return_value=Path(tmpdir)):
            r = client.put("/user/prompt", json={"prompt": "Be concise."}, params={"user_id": "test_user"})
            assert r.status_code == 200

            r = client.get("/user/prompt", params={"user_id": "test_user"})
            assert r.json()["prompt"] == "Be concise."
