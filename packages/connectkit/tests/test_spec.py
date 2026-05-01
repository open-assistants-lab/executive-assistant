"""Tests for connector spec model."""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from connectkit.spec import (
    ConnectorSpec,
    AuthType,
    ToolSourceType,
    OAuth2Config,
    ApiKeyConfig,
    AuthConfig,
    CLIToolSource,
    MCPToolSource,
    ToolDescription,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data))


class TestFromYaml:
    def test_oauth2_connector(self, tmp_path: Path):
        spec_yaml = tmp_path / "google.yaml"
        _write_yaml(spec_yaml, {
            "name": "google-workspace",
            "display": "Google Workspace",
            "icon": "google",
            "category": "productivity",
            "auth": {
                "type": "oauth2",
                "oauth2": {
                    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_url": "https://oauth2.googleapis.com/token",
                    "scopes": ["gmail.readonly", "calendar.readonly"],
                    "token_env_var": "GWS_ACCESS_TOKEN",
                },
            },
            "tool_source": {
                "type": "cli",
                "command": "gws",
                "install": "npm install -g @googleworkspace/cli",
                "env_mapping": {"access_token": "GWS_ACCESS_TOKEN"},
            },
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.name == "google-workspace"
        assert spec.display == "Google Workspace"
        assert spec.icon == "google"
        assert spec.category == "productivity"
        assert spec.auth.type == AuthType.OAUTH2
        assert spec.auth.oauth2 is not None
        assert spec.auth.oauth2.scopes == ["gmail.readonly", "calendar.readonly"]
        assert spec.tool_source.type == "cli"
        assert isinstance(spec.tool_source, CLIToolSource)
        assert spec.tool_source.command == "gws"

    def test_api_key_connector(self, tmp_path: Path):
        spec_yaml = tmp_path / "firecrawl.yaml"
        _write_yaml(spec_yaml, {
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
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.name == "firecrawl"
        assert spec.auth.type == AuthType.API_KEY
        assert spec.auth.api_key is not None
        assert spec.auth.api_key.env_var == "FIRECRAWL_API_KEY"

    def test_none_auth_connector(self, tmp_path: Path):
        spec_yaml = tmp_path / "browser.yaml"
        _write_yaml(spec_yaml, {
            "name": "agent-browser",
            "display": "Browser Automation",
            "category": "web",
            "auth": {"type": "none"},
            "tool_source": {
                "type": "cli",
                "command": "agent-browser",
                "install": "pip install agent-browser",
            },
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.name == "agent-browser"
        assert spec.auth.type == AuthType.NONE

    def test_mcp_source(self, tmp_path: Path):
        spec_yaml = tmp_path / "dropbox.yaml"
        _write_yaml(spec_yaml, {
            "name": "dropbox",
            "display": "Dropbox",
            "category": "storage",
            "auth": {
                "type": "oauth2",
                "oauth2": {
                    "authorize_url": "https://dropbox.com/oauth2/authorize",
                    "token_url": "https://api.dropbox.com/oauth2/token",
                    "scopes": ["files.read"],
                    "token_env_var": "DROPBOX_ACCESS_TOKEN",
                },
            },
            "tool_source": {
                "type": "mcp",
                "server_name": "dropbox",
                "command": "npx @anthropic/dropbox-mcp",
                "env_mapping": {"access_token": "DROPBOX_ACCESS_TOKEN"},
            },
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.tool_source.type == "mcp"
        assert isinstance(spec.tool_source, MCPToolSource)
        assert spec.tool_source.server_name == "dropbox"

    def test_defaults(self, tmp_path: Path):
        spec_yaml = tmp_path / "minimal.yaml"
        _write_yaml(spec_yaml, {
            "name": "minimal",
            "display": "Minimal",
            "auth": {"type": "none"},
            "tool_source": {
                "type": "cli",
                "command": "echo",
                "install": "built-in",
            },
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.icon == "plug"
        assert spec.category == "other"
        assert spec.version == "1.0"
        assert spec.description == ""
        assert spec.tool_descriptions == []

    def test_with_tool_descriptions(self, tmp_path: Path):
        spec_yaml = tmp_path / "with_descs.yaml"
        _write_yaml(spec_yaml, {
            "name": "with-descs",
            "display": "With Descriptions",
            "auth": {"type": "none"},
            "tool_source": {
                "type": "cli",
                "command": "echo",
                "install": "built-in",
            },
            "tool_descriptions": [
                {
                    "name": "with-descs__search",
                    "description": "Search for documents by keyword",
                    "parameter_descriptions": {
                        "query": "The search query string",
                        "limit": "Maximum number of results",
                    },
                },
            ],
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert len(spec.tool_descriptions) == 1
        td = spec.tool_descriptions[0]
        assert td.name == "with-descs__search"
        assert td.description == "Search for documents by keyword"
        assert td.parameter_descriptions["query"] == "The search query string"
        assert td.parameter_descriptions["limit"] == "Maximum number of results"


class TestValidationErrors:
    def test_invalid_name(self, tmp_path: Path):
        spec_yaml = tmp_path / "bad.yaml"
        _write_yaml(spec_yaml, {
            "name": "INVALID NAME",
            "display": "Bad",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        with pytest.raises(ValidationError):
            ConnectorSpec.from_yaml(str(spec_yaml))

    def test_name_with_leading_dash(self, tmp_path: Path):
        spec_yaml = tmp_path / "bad.yaml"
        _write_yaml(spec_yaml, {
            "name": "-bad-name",
            "display": "Bad",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        with pytest.raises(ValidationError):
            ConnectorSpec.from_yaml(str(spec_yaml))

    def test_missing_required(self, tmp_path: Path):
        spec_yaml = tmp_path / "bad.yaml"
        _write_yaml(spec_yaml, {
            "name": "bad",
            "display": "Bad",
            # missing auth
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        with pytest.raises(ValidationError):
            ConnectorSpec.from_yaml(str(spec_yaml))

    def test_missing_tool_source_is_valid(self, tmp_path: Path):
        """tool_source is optional. tool_sources can be used instead."""
        spec_yaml = tmp_path / "minimal.yaml"
        _write_yaml(spec_yaml, {
            "name": "minimal",
            "display": "Minimal",
            "auth": {"type": "none"},
            "tool_sources": [{"type": "cli", "command": "echo", "install": "built-in"}],
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        assert spec.tool_source is None
        assert len(spec.tool_sources) == 1
        assert spec.tool_sources[0].command == "echo"

    def test_tool_source_still_works(self, tmp_path: Path):
        """Backward compat: single tool_source still valid."""
        spec_yaml = tmp_path / "old.yaml"
        _write_yaml(spec_yaml, {
            "name": "old-format",
            "display": "Old Format",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        spec = ConnectorSpec.from_yaml(str(spec_yaml))
        sources = spec.get_tool_sources()
        assert len(sources) == 1
        assert sources[0].command == "echo"

    def test_invalid_tool_source_type(self, tmp_path: Path):
        spec_yaml = tmp_path / "bad.yaml"
        _write_yaml(spec_yaml, {
            "name": "bad",
            "display": "Bad",
            "auth": {"type": "none"},
            "tool_source": {
                "type": "sdk",
                "command": "echo",
                "install": "built-in",
            },
        })

        with pytest.raises(ValidationError):
            ConnectorSpec.from_yaml(str(spec_yaml))


class TestFromYamlDir:
    def test_loads_all_valid(self, tmp_path: Path):
        _write_yaml(tmp_path / "a.yaml", {
            "name": "a-service",
            "display": "A",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })
        _write_yaml(tmp_path / "b.yaml", {
            "name": "b-service",
            "display": "B",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        specs = ConnectorSpec.from_yaml_dir(str(tmp_path))
        assert len(specs) == 2
        names = {s.name for s in specs}
        assert names == {"a-service", "b-service"}

    def test_skips_broken_files(self, tmp_path: Path):
        _write_yaml(tmp_path / "good.yaml", {
            "name": "good",
            "display": "Good",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })
        _write_yaml(tmp_path / "broken.yaml", {
            "name": "BAD NAME",
            "display": "Broken",
            "auth": {"type": "none"},
            "tool_source": {"type": "cli", "command": "echo", "install": "built-in"},
        })

        specs = ConnectorSpec.from_yaml_dir(str(tmp_path))
        assert len(specs) == 1
        assert specs[0].name == "good"

    def test_empty_dir(self, tmp_path: Path):
        specs = ConnectorSpec.from_yaml_dir(str(tmp_path))
        assert specs == []


class TestAuthConfig:
    def test_oauth2_extra_params(self):
        config = OAuth2Config(
            authorize_url="https://example.com/auth",
            token_url="https://example.com/token",
            scopes=["read"],
            extra_params={"access_type": "offline", "prompt": "consent"},
        )
        assert config.extra_params["access_type"] == "offline"
        assert config.pkce is False

    def test_oauth2_pkce(self):
        config = OAuth2Config(
            authorize_url="https://example.com/auth",
            token_url="https://example.com/token",
            scopes=["read"],
            pkce=True,
        )
        assert config.pkce is True

    def test_api_key_defaults(self):
        config = ApiKeyConfig(env_var="MY_KEY")
        assert config.header_name == "Authorization"
        assert config.header_prefix == "Bearer"


class TestCLIToolSource:
    def test_env_mapping_defaults(self):
        source = CLIToolSource(
            type="cli",
            command="test-cli",
            install="pip install test-cli",
        )
        assert source.env_mapping == {}

    def test_env_mapping_custom(self):
        source = CLIToolSource(
            type="cli",
            command="test-cli",
            install="pip install test-cli",
            env_mapping={"access_token": "CLI_TOKEN", "api_key": "CLI_KEY"},
        )
        assert source.env_mapping["access_token"] == "CLI_TOKEN"


class TestToolDescription:
    def test_defaults(self):
        td = ToolDescription(name="my-tool", description="Does a thing")
        assert td.parameter_descriptions == {}

    def test_with_params(self):
        td = ToolDescription(
            name="my-tool",
            description="Does a thing",
            parameter_descriptions={"x": "The X value", "y": "The Y value"},
        )
        assert len(td.parameter_descriptions) == 2
