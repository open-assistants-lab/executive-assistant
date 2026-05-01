"""Tests for ConnectKitBridge."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from connectkit.bridge import ConnectKitBridge


@pytest.fixture
def temp_dir(monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv("CONNECTKIT_SPEC_DIR", str(Path(d) / "connectors"))
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CONNECTKIT_VAULT_KEY", Fernet.generate_key().decode())
    # Use temp dir for vaults too
    from connectkit.bridge import _default_vault_path as _orig

    def _test_vault_path(user_id: str) -> str:
        return str(Path(d) / "vaults" / user_id)

    import connectkit.bridge as bridge_module
    bridge_module._default_vault_path = _test_vault_path
    yield d
    bridge_module._default_vault_path = _orig
    shutil.rmtree(d, ignore_errors=True)


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


def _write_connectors(base: str, specs: list[dict]) -> None:
    spec_dir = Path(base) / "connectors"
    spec_dir.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(specs):
        path = spec_dir / f"{i:02d}_{spec['name']}.yaml"
        path.write_text(yaml.dump(spec))


class TestBridgeLifecycle:
    @pytest.mark.asyncio
    async def test_discover_no_connectors(self, temp_dir):
        _write_connectors(temp_dir, [])
        bridge = ConnectKitBridge("alice")
        await bridge.discover()
        assert bridge.get_tool_definitions() == []

    @pytest.mark.asyncio
    async def test_discover_with_unconnected(self, temp_dir):
        """No tools when nothing is connected."""
        _write_connectors(temp_dir, [_make_cli_spec("github")])
        bridge = ConnectKitBridge("alice")
        await bridge.discover()
        assert bridge.get_tool_definitions() == []

    @pytest.mark.asyncio
    async def test_discover_with_connected(self, temp_dir):
        """Connected services produce tools."""
        _write_connectors(temp_dir, [_make_cli_spec("github")])

        bridge = ConnectKitBridge("alice")
        bridge.vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        with patch("connectkit.backends.cli.CLIAdapter.list_commands",
                   return_value=["repo:list"]):
            await bridge.discover()

        tools = bridge.get_tool_definitions()
        assert len(tools) == 1
        assert tools[0]["name"] == "github__repo_list"

    @pytest.mark.asyncio
    async def test_multiple_connectors(self, temp_dir):
        """Only connected connectors produce tools."""
        _write_connectors(temp_dir, [
            _make_cli_spec("github"),
            _make_cli_spec("slack"),
            _make_cli_spec("linear"),
        ])

        bridge = ConnectKitBridge("alice")
        bridge.vault.store_token("github", "api_key", {"api_key": "ghp_123"})
        bridge.vault.store_token("linear", "api_key", {"api_key": "lin_123"})

        with patch("connectkit.backends.cli.CLIAdapter.list_commands",
                   return_value=["list"]):
            await bridge.discover()

        tools = bridge.get_tool_definitions()
        assert len(tools) == 2  # github + linear, not slack
        names = {t["name"] for t in tools}
        assert "github__list" in names
        assert "linear__list" in names
        assert "slack__list" not in names


class TestListAvailable:
    def test_catalog(self, temp_dir):
        _write_connectors(temp_dir, [
            _make_cli_spec("github"),
            _make_cli_spec("slack"),
        ])

        bridge = ConnectKitBridge("alice")
        bridge.vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        available = bridge.list_available()
        assert len(available) == 2
        github = [a for a in available if a["name"] == "github"][0]
        slack = [a for a in available if a["name"] == "slack"][0]
        assert github["connected"] is True
        assert slack["connected"] is False


class TestConnectedServices:
    def test_lists_connected(self, temp_dir):
        _write_connectors(temp_dir, [
            _make_cli_spec("github"),
            _make_cli_spec("slack"),
        ])

        bridge = ConnectKitBridge("user_conn_svc")
        bridge.vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        connected = bridge.connected_services()
        assert connected == ["github"]

    def test_empty(self, temp_dir):
        _write_connectors(temp_dir, [_make_cli_spec("github")])
        bridge = ConnectKitBridge("newuser")
        assert bridge.connected_services() == []


class TestHealth:
    def test_reports_health(self, temp_dir):
        _write_connectors(temp_dir, [_make_cli_spec("github")])
        bridge = ConnectKitBridge("alice")
        bridge.vault.store_token("github", "api_key", {"api_key": "ghp_123"})

        with patch("connectkit.backends.cli.CLIAdapter.list_commands",
                   return_value=["repo:list"]):
            bridge._runtime._tools = bridge._runtime.get_tools()

        h = bridge.health()
        assert h["vault"]["status"] == "ok"
        assert "connectors" in h
