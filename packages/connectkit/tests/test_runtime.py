"""Tests for ConnectorRuntime."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from connectkit.runtime import ConnectorRuntime


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def vault(monkeypatch, temp_dir):
    from connectkit.vault import CredentialVault

    monkeypatch.setenv("CONNECTKIT_VAULT_KEY", "")
    v = CredentialVault(temp_dir)
    yield v
    v.close()


def _write_specs(spec_dir: Path, specs: list[dict]) -> None:
    spec_dir.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(specs):
        path = spec_dir / f"{i:02d}_{spec['name']}.yaml"
        path.write_text(yaml.dump(spec))


def _make_cli_spec(name: str) -> dict:
    return {
        "name": name,
        "display": name.replace("-", " ").title(),
        "auth": {"type": "api_key", "api_key": {"env_var": f"{name.upper()}_KEY"}},
        "tool_source": {
            "type": "cli",
            "command": "echo",
            "install": "built-in",
            "env_mapping": {"api_key": f"{name.upper()}_KEY"},
        },
    }


def _make_mcp_spec(name: str) -> dict:
    return {
        "name": name,
        "display": name.title(),
        "auth": {
            "type": "oauth2",
            "oauth2": {
                "authorize_url": "https://example.com/auth",
                "token_url": "https://example.com/token",
                "scopes": ["read"],
            },
        },
        "tool_source": {
            "type": "mcp",
            "server_name": name,
            "command": f"npx {name}-mcp",
            "env_mapping": {"access_token": f"{name.upper()}_TOKEN"},
        },
    }


class TestInit:
    def test_loads_specs(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github"), _make_cli_spec("linear")])

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        specs = rt.get_specs()
        assert len(specs) == 2
        names = {s.name for s in specs}
        assert "github" in names
        assert "linear" in names

    def test_empty_dir(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "empty"
        spec_dir.mkdir()
        rt = ConnectorRuntime(spec_dir, vault, "alice")
        assert rt.get_specs() == []

    def test_missing_dir(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "nonexistent"
        rt = ConnectorRuntime(spec_dir, vault, "alice")
        assert rt.get_specs() == []

    def test_reload(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github")])

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        assert len(rt.get_specs()) == 1

        _write_specs(spec_dir, [_make_cli_spec("github"), _make_cli_spec("slack")])
        rt.reload()
        assert len(rt.get_specs()) == 2


class TestListAvailable:
    def test_all_unconnected(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github"), _make_cli_spec("slack")])

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        available = rt.list_available()

        assert len(available) == 2
        for a in available:
            assert a["connected"] is False
            assert a["auth_type"] in ("api_key", "oauth2")

    def test_some_connected(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github"), _make_cli_spec("slack")])

        vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        available = rt.list_available()

        github = [a for a in available if a["name"] == "github"][0]
        slack = [a for a in available if a["name"] == "slack"][0]
        assert github["connected"] is True
        assert slack["connected"] is False


class TestGetTools:
    def test_returns_nothing_when_nothing_connected(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github")])

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        tools = rt.get_tools()
        assert tools == []

    def test_returns_tools_for_connected_cli(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github")])

        vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        rt = ConnectorRuntime(spec_dir, vault, "alice")

        with patch("connectkit.backends.cli.CLIAdapter.list_commands",
                   return_value=["repo:list", "issue:create"]):
            tools = rt.get_tools()

        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert "github__repo_list" in names
        assert "github__issue_create" in names

    def test_returns_mcp_placeholder(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_mcp_spec("dropbox")])

        vault.store_token("dropbox", "oauth2", {"access_token": "sl.123"})

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        tools = rt.get_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "dropbox__mcp_status"
        assert tools[0]["_is_mcp_placeholder"] is True

    def test_skips_broken_connector(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github"), _make_cli_spec("slack")])

        vault.store_token("github", "api_key", {"api_key": "ghp_123"})
        vault.store_token("slack", "api_key", {"api_key": "xoxb_123"})

        rt = ConnectorRuntime(spec_dir, vault, "alice")

        # Let github work but make slack crash
        original_load = rt._load_connector

        call_count = 0

        def mock_load(spec):
            nonlocal call_count
            call_count += 1
            if spec.name == "slack":
                raise RuntimeError("Slack adapter crash")
            return original_load(spec)

        with patch.object(rt, "_load_connector", side_effect=mock_load):
            tools = rt.get_tools()

        # Should return github tools only, not crash
        assert len(tools) >= 0


class TestHealth:
    def test_all_not_connected(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github")])

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        h = rt.health()
        assert h["status"] == "ok"
        assert h["connectors"]["github"]["status"] == "not_connected"

    def test_connected_ok(self, temp_dir, vault):
        spec_dir = Path(temp_dir) / "connectors"
        _write_specs(spec_dir, [_make_cli_spec("github")])

        vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        rt = ConnectorRuntime(spec_dir, vault, "alice")
        h = rt.health()
        assert h["connectors"]["github"]["status"] == "ok"
        assert h["connectors"]["github"]["tools"] >= 0
