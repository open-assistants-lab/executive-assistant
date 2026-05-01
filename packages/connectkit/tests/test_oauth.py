"""Tests for OAuth router."""

import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from connectkit.oauth import create_oauth_router
from connectkit.spec import ConnectorSpec
from connectkit.vault import CredentialVault

GOOGLE_SPEC = {
    "name": "google-workspace",
    "display": "Google Workspace",
    "icon": "google",
    "category": "productivity",
    "auth": {
        "type": "oauth2",
        "oauth2": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
            "extra_params": {"access_type": "offline", "prompt": "consent"},
            "token_env_var": "GWS_ACCESS_TOKEN",
        },
    },
    "tool_source": {
        "type": "cli",
        "command": "gws",
        "install": "npm install -g @googleworkspace/cli",
        "env_mapping": {"access_token": "GWS_ACCESS_TOKEN"},
    },
}

GITHUB_SPEC = {
    "name": "github",
    "display": "GitHub",
    "icon": "github",
    "category": "dev-tools",
    "auth": {
        "type": "oauth2",
        "oauth2": {
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "read:org"],
        },
    },
    "tool_source": {
        "type": "cli",
        "command": "gh",
        "install": "brew install gh",
    },
}

API_KEY_SPEC = {
    "name": "firecrawl",
    "display": "Firecrawl",
    "category": "web",
    "auth": {
        "type": "api_key",
        "api_key": {
            "env_var": "FIRECRAWL_API_KEY",
        },
    },
    "tool_source": {
        "type": "cli",
        "command": "firecrawl",
        "install": "npm install -g firecrawl@latest",
        "env_mapping": {"api_key": "FIRECRAWL_API_KEY"},
    },
}


def _make_mock_response(status=200, json_data=None, text_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text_data or ""
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    else:
        resp.json = MagicMock(side_effect=ValueError("Not JSON"))
    return resp


@pytest.fixture
def vault_dirs():
    dirs: list[str] = []
    yield dirs
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mock_config():
    return {
        "google-workspace": {"client_id": "google-client-id", "client_secret": "google-secret"},
        "github": {"client_id": "github-client-id", "client_secret": "github-secret"},
    }


@pytest.fixture
def app(monkeypatch, vault_dirs, mock_config):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CONNECTKIT_VAULT_KEY", key)

    _vaults: dict[str, CredentialVault] = {}

    def vault_factory(user_id: str) -> CredentialVault:
        if user_id not in _vaults:
            d = tempfile.mkdtemp(prefix=f"vault_{user_id}_")
            vault_dirs.append(d)
            _vaults[user_id] = CredentialVault(d)
        return _vaults[user_id]

    def config(service: str) -> dict[str, str]:
        return mock_config.get(service, {})

    specs = [
        ConnectorSpec.model_validate(GOOGLE_SPEC),
        ConnectorSpec.model_validate(GITHUB_SPEC),
        ConnectorSpec.model_validate(API_KEY_SPEC),
    ]

    app = FastAPI()
    router = create_oauth_router(
        specs=specs,
        vault_factory=vault_factory,
        config=config,
        base_url="http://localhost:8000",
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestLoginRoute:
    def test_redirects_to_authorize_url(self, client):
        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "accounts.google.com/o/oauth2/v2/auth" in location
        assert "client_id=google-client-id" in location
        assert "response_type=code" in location
        assert "access_type=offline" in location
        assert "prompt=consent" in location
        assert "state=" in location

    def test_includes_scopes_in_url(self, client):
        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        location = resp.headers["location"]
        assert "gmail.readonly" in location
        assert "calendar.readonly" in location

    def test_includes_redirect_uri(self, client):
        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        location = resp.headers["location"]
        assert "redirect_uri=" in location
        assert "auth%2Fcallback" in location

    def test_unknown_service_returns_400(self, client):
        resp = client.get("/auth/login?service=nonexistent&user_id=alice")
        assert resp.status_code == 400

    def test_non_oauth_service_returns_400(self, client):
        resp = client.get("/auth/login?service=firecrawl&user_id=alice")
        assert resp.status_code == 400

    def test_state_is_unique(self, client):
        resp1 = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        resp2 = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)

        import urllib.parse
        loc1 = urllib.parse.urlparse(resp1.headers["location"])
        loc2 = urllib.parse.urlparse(resp2.headers["location"])
        q1 = urllib.parse.parse_qs(loc1.query)
        q2 = urllib.parse.parse_qs(loc2.query)
        assert q1["state"][0] != q2["state"][0]


class TestCallbackRoute:
    def _get_state(self, client):
        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        import urllib.parse
        loc = urllib.parse.urlparse(resp.headers["location"])
        q = urllib.parse.parse_qs(loc.query)
        return q["state"][0]

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_exchanges_code_and_stores_tokens(self, mock_post, client):
        mock_post.return_value = _make_mock_response(json_data={
            "access_token": "ya29.test-token",
            "refresh_token": "ref-token-xyz",
            "expires_in": 3600,
            "token_type": "Bearer",
        })

        state = self._get_state(client)
        resp = client.get(f"/auth/callback?code=auth-code-123&state={state}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["service"] == "google-workspace"
        assert any("gmail.readonly" in s for s in data["scopes"])

        assert mock_post.call_count >= 1

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_stores_token_in_vault(self, mock_post, client):
        mock_post.return_value = _make_mock_response(json_data={
            "access_token": "ya29.test-token",
            "refresh_token": "ref-token-xyz",
        })

        state = self._get_state(client)
        client.get(f"/auth/callback?code=auth-code-123&state={state}")

        resp = client.get("/auth/status?user_id=alice")
        data = resp.json()
        assert len(data["connected"]) == 1
        assert data["connected"][0]["service"] == "google-workspace"

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_multiple_users_dont_leak_tokens(self, mock_post, client):
        mock_post.return_value = _make_mock_response(json_data={"access_token": "tok"})

        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        import urllib.parse
        loc = urllib.parse.urlparse(resp.headers["location"])
        q = urllib.parse.parse_qs(loc.query)
        state_a = q["state"][0]

        resp2 = client.get("/auth/login?service=google-workspace&user_id=bob", follow_redirects=False)
        loc2 = urllib.parse.urlparse(resp2.headers["location"])
        q2 = urllib.parse.parse_qs(loc2.query)
        state_b = q2["state"][0]

        client.get(f"/auth/callback?code=a&state={state_a}")
        client.get(f"/auth/callback?code=b&state={state_b}")

        resp = client.get("/auth/status?user_id=alice")
        assert len(resp.json()["connected"]) == 1

        resp = client.get("/auth/status?user_id=bob")
        assert len(resp.json()["connected"]) == 1

    def test_invalid_state_returns_400(self, client):
        resp = client.get("/auth/callback?code=abc&state=invalid-state")
        assert resp.status_code == 400

    def test_corrupted_state_returns_400(self, client):
        state = self._get_state(client)
        corrupted = state + "x"
        resp = client.get(f"/auth/callback?code=abc&state={corrupted}")
        assert resp.status_code == 400

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_token_exchange_failure_returns_502(self, mock_post, client):
        mock_post.return_value = _make_mock_response(status=401, text_data="invalid_client")

        state = self._get_state(client)
        resp = client.get(f"/auth/callback?code=bad-code&state={state}")
        assert resp.status_code == 502

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_token_response_missing_access_token_returns_502(self, mock_post, client):
        mock_post.return_value = _make_mock_response(json_data={"error": "something"})

        state = self._get_state(client)
        resp = client.get(f"/auth/callback?code=abc&state={state}")
        assert resp.status_code == 502

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_token_response_wrong_type_returns_502(self, mock_post, client):
        mock_post.return_value = _make_mock_response()

        state = self._get_state(client)
        resp = client.get(f"/auth/callback?code=abc&state={state}")
        assert resp.status_code == 502

    def test_callback_with_oauth_error(self, client):
        resp = client.get("/auth/callback?error=access_denied&error_description=User%20declined")
        assert resp.status_code == 400


class TestStatusRoute:
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_connected_services(self, mock_post, client):
        mock_post.return_value = _make_mock_response(json_data={
            "access_token": "tok", "refresh_token": "ref"
        })

        resp = client.get("/auth/login?service=google-workspace&user_id=alice", follow_redirects=False)
        import urllib.parse
        loc = urllib.parse.urlparse(resp.headers["location"])
        q = urllib.parse.parse_qs(loc.query)
        client.get(f"/auth/callback?code=a&state={q['state'][0]}")

        resp2 = client.get("/auth/login?service=github&user_id=alice", follow_redirects=False)
        loc2 = urllib.parse.urlparse(resp2.headers["location"])
        q2 = urllib.parse.parse_qs(loc2.query)
        client.get(f"/auth/callback?code=b&state={q2['state'][0]}")

        resp = client.get("/auth/status?user_id=alice")
        data = resp.json()
        assert len(data["connected"]) == 2
        names = {c["service"] for c in data["connected"]}
        assert "google-workspace" in names
        assert "github" in names

    def test_no_connected_services(self, client):
        resp = client.get("/auth/status?user_id=newuser")
        data = resp.json()
        assert data["connected"] == []
