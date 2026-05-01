"""Tests for MCPAdapter."""

import shutil
import tempfile

import pytest

from connectkit.backends.mcp import MCPAdapter


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


def _make_spec(name="dropbox", env_mapping=None):
    from connectkit.spec import ConnectorSpec

    return ConnectorSpec.model_validate({
        "name": name,
        "display": "Dropbox",
        "auth": {
            "type": "oauth2",
            "oauth2": {
                "authorize_url": "https://dropbox.com/oauth2/authorize",
                "token_url": "https://api.dropbox.com/oauth2/token",
                "scopes": ["files.read"],
                "token_env_var": "DROPBOX_TOKEN",
            },
        },
        "tool_source": {
            "type": "mcp",
            "server_name": "dropbox",
            "command": "npx @anthropic/dropbox-mcp",
            "env_mapping": env_mapping or {"access_token": "DROPBOX_TOKEN"},
        },
    })


class TestProperties:
    def test_server_name(self, vault):
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        assert adapter.server_name == "dropbox"

    def test_command(self, vault):
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        assert adapter.command == "npx @anthropic/dropbox-mcp"


class TestBuildServerEnv:
    def test_no_token_returns_clean_env(self, vault):
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        env = adapter.build_server_env()
        assert "DROPBOX_TOKEN" not in env

    def test_injects_access_token(self, vault):
        vault.store_token("dropbox", "oauth2", {"access_token": "sl.token.123"})
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        env = adapter.build_server_env()
        assert env["DROPBOX_TOKEN"] == "sl.token.123"

    def test_injects_api_key(self, vault):
        from connectkit.spec import ConnectorSpec

        spec = ConnectorSpec.model_validate({
            "name": "stripe",
            "display": "Stripe",
            "auth": {
                "type": "api_key",
                "api_key": {"env_var": "STRIPE_KEY"},
            },
            "tool_source": {
                "type": "mcp",
                "server_name": "stripe",
                "command": "npx stripe-mcp",
                "env_mapping": {"api_key": "STRIPE_KEY"},
            },
        })
        vault.store_token("stripe", "api_key", {"api_key": "sk_test.123"})
        adapter = MCPAdapter(spec, vault, "alice")
        env = adapter.build_server_env()
        assert env["STRIPE_KEY"] == "sk_test.123"

    def test_injects_custom_mapping(self, vault):
        from connectkit.spec import ConnectorSpec

        spec = ConnectorSpec.model_validate({
            "name": "custom-svc",
            "display": "Custom",
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
                "server_name": "custom",
                "command": "custom-mcp",
                "env_mapping": {"custom_field": "CUSTOM_VAR"},
            },
        })
        vault.store_token("custom-svc", "oauth2", {"custom_field": "my-value"})
        adapter = MCPAdapter(spec, vault, "alice")
        env = adapter.build_server_env()
        assert env["CUSTOM_VAR"] == "my-value"


class TestGetMCPConfig:
    def test_returns_dict_with_env(self, vault):
        vault.store_token("dropbox", "oauth2", {"access_token": "tok"})
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        config = adapter.get_mcp_config()
        assert config["command"] == "npx @anthropic/dropbox-mcp"
        assert config["transport"] == "stdio"
        assert "env" in config
        assert config["env"]["DROPBOX_TOKEN"] == "tok"

    def test_no_token_still_returns_config(self, vault):
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        config = adapter.get_mcp_config()
        assert config["command"] == "npx @anthropic/dropbox-mcp"
        assert "env" in config


class TestHealth:
    def test_ok_when_connected(self, vault):
        vault.store_token("dropbox", "oauth2", {"access_token": "tok"})
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        h = adapter.health()
        assert h["status"] == "ok"
        assert h["service"] == "dropbox"

    def test_not_connected_when_no_token(self, vault):
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        h = adapter.health()
        assert h["status"] == "not_connected"

    def test_not_connected_when_token_missing_access(self, vault):
        vault.store_token("dropbox", "oauth2", {"refresh_token": "ref"})
        spec = _make_spec()
        adapter = MCPAdapter(spec, vault, "alice")
        h = adapter.health()
        assert h["status"] == "not_connected"
