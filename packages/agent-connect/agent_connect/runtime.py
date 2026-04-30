"""ConnectorRuntime — load specs, check connections, discover tools."""

import json
import logging
from pathlib import Path
from typing import Any

from agent_connect.backends.cli import CLIAdapter
from agent_connect.backends.mcp import MCPAdapter
from agent_connect.spec import ConnectorSpec, ToolSourceType
from agent_connect.vault import CredentialVault

logger = logging.getLogger("agent_connect")


class ConnectorRuntime:
    """Orchestrates: YAML specs → auth check → backend → tool dicts.

    Usage:
        runtime = ConnectorRuntime(
            spec_dir="./connectors",
            vault=CredentialVault("./data/users/alice"),
            user_id="alice",
        )
        tools = runtime.get_tools()
        available = runtime.list_available()
        health = runtime.health()
    """

    def __init__(
        self,
        spec_dir: str | Path,
        vault: CredentialVault,
        user_id: str,
    ):
        self.spec_dir = Path(spec_dir)
        self.vault = vault
        self.user_id = user_id
        self._specs: list[ConnectorSpec] = []
        self._load_specs()

    def _load_specs(self) -> None:
        if self.spec_dir.exists():
            self._specs = ConnectorSpec.from_yaml_dir(self.spec_dir)

    def get_specs(self) -> list[ConnectorSpec]:
        return list(self._specs)

    def reload(self) -> None:
        self._load_specs()

    def list_available(self) -> list[dict[str, Any]]:
        connected = set(self.vault.list_connected())
        return [
            {
                "name": s.name,
                "display": s.display,
                "icon": s.icon,
                "category": s.category,
                "description": s.description,
                "connected": s.name in connected,
                "auth_type": s.auth.type.value,
            }
            for s in self._specs
        ]

    def get_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []

        for spec in self._specs:
            if not self.vault.is_connected(spec.name):
                continue

            try:
                adapter_tools = self._load_connector(spec)
                tools.extend(adapter_tools)
            except Exception:
                logger.warning(
                    f"Failed to load connector '{spec.name}'", exc_info=True
                )
                continue

        return tools

    def _load_connector(self, spec: ConnectorSpec) -> list[dict[str, Any]]:
        namespace = spec.name.replace("-", "_")

        if spec.tool_source.type == ToolSourceType.CLI:
            adapter = CLIAdapter(spec, self.vault, self.user_id)
            if not adapter.is_available():
                logger.warning(
                    f"CLI not available for {spec.name}. "
                    f"Install: {spec.tool_source.install}"
                )
                return []
            return adapter.discover_tools(namespace)

        elif spec.tool_source.type == ToolSourceType.MCP:
            adapter = MCPAdapter(spec, self.vault, self.user_id)
            return _mcp_tools_from_adapter(adapter, namespace)

        return []

    def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "ok", "connectors": {}}
        connected_count = 0
        error_count = 0

        for spec in self._specs:
            if not self.vault.is_connected(spec.name):
                result["connectors"][spec.name] = {"status": "not_connected"}
                continue

            connected_count += 1
            try:
                tools = self._load_connector(spec)
                result["connectors"][spec.name] = {
                    "status": "ok",
                    "tools": len(tools),
                }
            except Exception as e:
                error_count += 1
                result["connectors"][spec.name] = {
                    "status": "error",
                    "error": str(e),
                }

        if error_count > 0:
            result["status"] = "broken" if error_count == connected_count else "partial"

        return result


def _mcp_tools_from_adapter(adapter: MCPAdapter, namespace: str) -> list[dict[str, Any]]:
    """Generate a placeholder tool set for an MCP connector.

    The actual tools are discovered by the MCP server at runtime.
    We return a single meta-tool that documents the connector status
    and the command that would be run.

    When EA's MCPToolBridge integrates, it replaces this with real tools.
    """
    config = adapter.get_mcp_config()
    name = f"{namespace}__mcp_status"
    return [
        {
            "name": name,
            "description": (
                f"MCP connector for {adapter.spec.display}. "
                f"Server: {config['command']}. "
                f"Use the MCP bridge to discover available tools."
            ),
            "parameters": {"type": "object", "properties": {}},
            "function": lambda: {
                "content": json.dumps(
                    {"status": "ready", "server": config["command"]}
                ),
                "structured_content": {
                    "status": "ready",
                    "server": config["command"],
                },
                "is_error": False,
            },
            "ainvoke": None,
            "annotations": {
                "read_only": True,
                "destructive": False,
                "idempotent": True,
                "title": name,
            },
            "_is_mcp_placeholder": True,
        }
    ]

