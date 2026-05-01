"""CLIAdapter — user-aware subprocess wrapper for CLI-based connectors.

Unlike the old CLIToolAdapter singleton in EA's SDK, this:
1.  Reads per-user tokens from CredentialVault
2.  Sets env vars per invocation (no global state)
3.  Discovers tools by parsing CLI --help or a known tool list
4.  Returns namespaced ToolDefinition objects

Usage:
    adapter = CLIAdapter(spec, vault, user_id="alice")
    if not adapter.is_available():
        print(f"CLI not installed: {adapter._source.install}")

    tools = adapter.discover_tools(namespace="google-workspace")
"""

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any

from connectkit.spec import CLIToolSource, ConnectorSpec, ToolDescription
from connectkit.vault import CredentialVault

logger = logging.getLogger("connectkit")


class CLIAdapter:
    """Wraps a CLI tool with per-user token injection.

    Each tool is a closure that spans a subprocess with the user's
    OAuth token in the environment.
    """

    def __init__(
        self,
        spec: ConnectorSpec,
        vault: CredentialVault,
        user_id: str,
        timeout: int = 60,
    ):
        self.spec = spec
        self.vault = vault
        self.user_id = user_id
        self.timeout = timeout
        self._source: CLIToolSource = spec.tool_source  # type: ignore[assignment]
        self._command = self._source.command

    def is_available(self) -> bool:
        return shutil.which(self._command) is not None

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        token_data = self.vault.get_token(self.spec.name)
        if not token_data:
            return env

        for cred_key, env_var in self._source.env_mapping.items():
            if cred_key == "access_token":
                env[env_var] = token_data.get("access_token", "")
            elif cred_key == "api_key":
                env[env_var] = token_data.get("api_key", "")
            elif cred_key in token_data:
                env[env_var] = str(token_data[cred_key])

        return env

    def run(self, args: list[str]) -> tuple[int, str, str]:
        env = self._build_env()
        cmd = [self._command] + args
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -2, "", f"Command timed out after {self.timeout}s: {' '.join(cmd)}"
        except FileNotFoundError:
            return -1, "", f"Command not found: {self._command}. Install: {self._source.install}"
        except Exception as e:
            return -3, "", f"Subprocess error: {e}"

    def list_commands(self) -> list[str]:
        rc, stdout, _ = self.run(["--list-commands"])
        if rc == 0:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return [line.strip() for line in stdout.split("\n") if line.strip()]

        rc, stdout, _ = self.run(["--help"])
        if rc == 0:
            return _parse_subcommands_from_help(stdout)

        return []

    def discover_tools(self, namespace: str) -> list[Any]:
        commands = self.list_commands()
        descriptions_by_name = {
            td.name: td for td in self.spec.tool_descriptions
        }

        tools = []
        for cmd in commands:
            safe_name = cmd.replace(" ", "_").replace("-", "_").replace(":", "_")
            tool_name = f"{namespace}__{safe_name}"

            td = descriptions_by_name.get(tool_name)
            description = (
                td.description if td
                else f"{self.spec.display}: {cmd}"
            )

            parameter_descriptions = td.parameter_descriptions if td else {}

            tool_def = _build_connector_tool(
                name=tool_name,
                description=description,
                adapter=self,
                args=args_from_command(cmd),
                parameter_descriptions=parameter_descriptions,
            )
            tools.append(tool_def)

        return tools


def args_from_command(cmd: str) -> list[str]:
    """Convert a command string like 'gmail:messages:list' to CLI args."""
    return cmd.replace(":", " ").split()


def _parse_subcommands_from_help(help_text: str) -> list[str]:
    commands = []
    for line in help_text.split("\n"):
        if not line.strip():
            continue
        match = re.search(r"\s{2,}([a-z][a-z0-9_:-]+)(?:\s|$)", line)
        if match:
            commands.append(match.group(1))
    return commands


def _build_connector_tool(
    name: str,
    description: str,
    adapter: CLIAdapter,
    args: list[str],
    parameter_descriptions: dict[str, str] | None = None,
) -> Any:
    """Build a ToolDefinition-compatible object for a connector tool.

    Uses a closure that wraps the subprocess call. The closure:
    1.  Formats kwargs as --key value pairs
    2.  Calls adapter.run(args + extra_args)
    3.  Parses stdout as JSON if possible
    4.  Returns a dict with content, structured_content, and error flag
    """

    def _sync_invoke(**kwargs: Any) -> dict:
        extra = []
        for key, val in kwargs.items():
            if val is None:
                continue
            extra.extend([f"--{key.replace('_', '-')}", str(val)])

        rc, stdout, stderr = adapter.run(args + extra)

        result: dict[str, Any] = {
            "content": "",
            "structured_content": None,
            "is_error": False,
        }

        if rc != 0:
            result["content"] = f"Error (code {rc}): {stderr or stdout}"
            result["is_error"] = True
            return result

        try:
            parsed = json.loads(stdout)
            result["content"] = stdout[:4000]
            result["structured_content"] = parsed
            return result
        except (json.JSONDecodeError, ValueError):
            result["content"] = stdout[:4000]
            return result

    async def _async_invoke(**kwargs: Any) -> dict:
        import asyncio
        return await asyncio.to_thread(_sync_invoke, **kwargs)

    params: dict[str, Any] = {
        "type": "object",
        "properties": {
            k: {"type": "string", "description": v}
            for k, v in (parameter_descriptions or {}).items()
        },
    }

    return {
        "name": name,
        "description": description,
        "parameters": params,
        "function": _sync_invoke,
        "ainvoke": _async_invoke,
        "annotations": {
            "read_only": False,
            "destructive": True,
            "idempotent": False,
            "title": name,
        },
    }
