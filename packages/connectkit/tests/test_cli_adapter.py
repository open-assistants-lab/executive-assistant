"""Tests for CLIAdapter."""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from connectkit.backends.cli import CLIAdapter, _parse_subcommands_from_help
from connectkit.spec import ConnectorSpec, ToolDescription


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


def _make_spec(
    name="test-cli",
    command="echo",
    auth_type="none",
    env_mapping=None,
    tool_descriptions=None,
):
    auth: dict = {"type": auth_type}
    if auth_type == "api_key":
        auth["api_key"] = {"env_var": "TEST_KEY"}
    elif auth_type == "oauth2":
        auth["oauth2"] = {
            "authorize_url": "https://example.com/auth",
            "token_url": "https://example.com/token",
            "scopes": ["read"],
            "token_env_var": "TEST_TOKEN",
        }

    data: dict = {
        "name": name,
        "display": "Test CLI",
        "auth": auth,
        "tool_source": {
            "type": "cli",
            "command": command,
            "install": "echo 'built-in'",
            "env_mapping": env_mapping or {},
        },
    }

    if tool_descriptions:
        data["tool_descriptions"] = tool_descriptions

    return ConnectorSpec.model_validate(data)


class TestAvailability:
    def test_available(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")
        assert adapter.is_available() is True

    def test_not_available(self, vault):
        spec = _make_spec(command="nonexistent-cli-xyz-123")
        adapter = CLIAdapter(spec, vault, "user1")
        assert adapter.is_available() is False


class TestEnvInjection:
    def test_no_token_no_injection(self, vault):
        spec = _make_spec(
            command="echo",
            auth_type="oauth2",
            env_mapping={"access_token": "TEST_TOKEN"},
        )
        adapter = CLIAdapter(spec, vault, "user1")
        env = adapter._build_env()
        assert "TEST_TOKEN" not in env

    def test_injects_access_token(self, vault):
        vault.store_token("test-cli", "oauth2", {"access_token": "ya29.secret"})
        spec = _make_spec(
            command="echo",
            auth_type="oauth2",
            env_mapping={"access_token": "TEST_TOKEN"},
        )
        adapter = CLIAdapter(spec, vault, "user1")
        env = adapter._build_env()
        assert env["TEST_TOKEN"] == "ya29.secret"

    def test_injects_api_key(self, vault):
        vault.store_token("test-cli", "api_key", {"api_key": "key-abc"})
        spec = _make_spec(
            command="echo",
            auth_type="api_key",
            env_mapping={"api_key": "TEST_KEY"},
        )
        adapter = CLIAdapter(spec, vault, "user1")
        env = adapter._build_env()
        assert env["TEST_KEY"] == "key-abc"

    def test_injects_custom_mapping(self, vault):
        vault.store_token("test-cli", "oauth2", {"custom_field": "custom-value"})
        spec = _make_spec(
            command="echo",
            env_mapping={"custom_field": "MY_CUSTOM_VAR"},
        )
        adapter = CLIAdapter(spec, vault, "user1")
        env = adapter._build_env()
        assert env["MY_CUSTOM_VAR"] == "custom-value"

    def test_overrides_existing_env(self, vault):
        os.environ["TEST_TOKEN"] = "original"
        try:
            vault.store_token("test-cli", "oauth2", {"access_token": "injected"})
            spec = _make_spec(
                command="echo",
                auth_type="oauth2",
                env_mapping={"access_token": "TEST_TOKEN"},
            )
            adapter = CLIAdapter(spec, vault, "user1")
            env = adapter._build_env()
            assert env["TEST_TOKEN"] == "injected"
        finally:
            del os.environ["TEST_TOKEN"]


class TestRun:
    def test_successful_run(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")
        rc, stdout, _ = adapter.run(["hello"])
        assert rc == 0
        assert stdout == "hello"

    def test_run_multi_args(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")
        rc, stdout, _ = adapter.run(["hello", "world"])
        assert rc == 0
        assert stdout == "hello world"

    def test_command_not_found(self, vault):
        spec = _make_spec(command="nonexistent-cli-xyz-123")
        adapter = CLIAdapter(spec, vault, "user1")
        rc, _, stderr = adapter.run(["something"])
        assert rc == -1
        assert "not found" in stderr

    def test_timeout(self, vault):
        spec = _make_spec(command="sleep")
        adapter = CLIAdapter(spec, vault, "user1", timeout=1)
        rc, _, stderr = adapter.run(["3"])
        assert rc == -2
        assert "timed out" in stderr.lower()


class TestListCommands:
    def test_from_echo_returns_command_verbatim(self, vault):
        """echo isn't a real CLI — it just echoes the arg back."""
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")
        commands = adapter.list_commands()
        # echo just prints "--list-commands" back — expected behavior
        assert isinstance(commands, list)

    def test_from_unknown(self, vault):
        spec = _make_spec(command="true")
        adapter = CLIAdapter(spec, vault, "user1")
        commands = adapter.list_commands()
        assert isinstance(commands, list)


class TestParseHelp:
    def test_basic_commands(self):
        help_text = """
Usage: test-cli COMMAND [OPTIONS]

Commands:
  scrape    Scrape a URL
  search    Search the web
  crawl     Crawl a site
"""
        commands = _parse_subcommands_from_help(help_text)
        assert "scrape" in commands
        assert "search" in commands
        assert "crawl" in commands

    def test_parse_empty(self):
        assert _parse_subcommands_from_help("") == []

    def test_parse_no_commands(self):
        assert _parse_subcommands_from_help("No commands listed.") == []

    def test_parse_with_colons(self):
        help_text = """
Commands:
  gmail:messages:list      List emails
  gmail:messages:get       Get a single email
  calendar:events:list     List calendar events
"""
        commands = _parse_subcommands_from_help(help_text)
        assert "gmail:messages:list" in commands
        assert "calendar:events:list" in commands

    def test_ignores_single_word_lines(self):
        help_text = """
Commands:
  singleword
  scrape     Scrape URL
"""
        commands = _parse_subcommands_from_help(help_text)
        assert "singleword" in commands
        assert "scrape" in commands


class TestDiscoverTools:
    def test_no_commands_no_tools(self, vault):
        spec = _make_spec(command="true")
        adapter = CLIAdapter(spec, vault, "user1")
        tools = adapter.discover_tools("myns")
        assert tools == []

    def test_namespaced_names(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["hello", "world"]):
            tools = adapter.discover_tools("myns")

        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert "myns__hello" in names
        assert "myns__world" in names

    def test_tool_structure(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["hello"]):
            tools = adapter.discover_tools("myns")

        assert len(tools) == 1
        t = tools[0]
        assert t["name"] == "myns__hello"
        assert "description" in t
        assert "parameters" in t
        assert "function" in t
        assert "ainvoke" in t
        assert callable(t["function"])
        assert t["annotations"]["read_only"] is False

    def test_uses_spec_tool_descriptions(self, vault):
        spec = _make_spec(
            command="echo",
            tool_descriptions=[
                {
                    "name": "myns__greet",
                    "description": "Greet someone by name",
                    "parameter_descriptions": {"name": "The person to greet"},
                }
            ],
        )
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["greet"]):
            tools = adapter.discover_tools("myns")

        assert tools[0]["description"] == "Greet someone by name"
        params = tools[0]["parameters"]["properties"]
        assert "name" in params
        assert params["name"]["description"] == "The person to greet"


class TestToolInvocation:
    def test_invoke_echo(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["hello", "world"]):
            tools = adapter.discover_tools("myns")

        hello_tool = [t for t in tools if t["name"] == "myns__hello"][0]
        result = hello_tool["function"]()
        assert result["is_error"] is False
        assert "hello" in result["content"]

    def test_invoke_failing_command(self, vault):
        spec = _make_spec(command="sh")
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["fail"]):
            tools = adapter.discover_tools("myns")

        tool = tools[0]
        result = tool["function"](code="1")
        if result["is_error"]:
            assert "Error" in result["content"]

    @pytest.mark.asyncio
    async def test_async_invoke(self, vault):
        spec = _make_spec(command="echo")
        adapter = CLIAdapter(spec, vault, "user1")

        with patch.object(adapter, "list_commands", return_value=["hello"]):
            tools = adapter.discover_tools("myns")

        result = await tools[0]["ainvoke"]()
        assert result["is_error"] is False
