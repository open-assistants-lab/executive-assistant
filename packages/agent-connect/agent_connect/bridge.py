"""AgentConnectBridge — EA integration point.

Mirrors the MCPToolBridge pattern:
    bridge = AgentConnectBridge(user_id="alice")
    await bridge.discover()
    tools = bridge.get_tool_definitions()

EA's runner.py injects this between native_tools and AgentLoop creation.
Each tool dict contains: name, description, parameters, function, ainvoke,
annotations, and optional _is_mcp_placeholder.
"""

import logging
from pathlib import Path
from typing import Any

from agent_connect.runtime import ConnectorRuntime
from agent_connect.vault import CredentialVault

logger = logging.getLogger("agent_connect")


def _default_vault_path(user_id: str) -> str:
    return str(Path("data") / "users" / user_id / "agent_connect")


def _default_spec_dir() -> str:
    import os

    env = os.environ.get("AGENT_CONNECT_SPEC_DIR")
    if env:
        return env

    try:
        import importlib.resources

        return str(importlib.resources.files("agent_connect") / "connectors")
    except Exception:
        return str(Path(__file__).parent.parent / "connectors")


def get_vault(user_id: str, vault_path: str | None = None) -> CredentialVault:
    """Get or create a CredentialVault for a user."""
    path = vault_path or _default_vault_path(user_id)
    return CredentialVault(path)


class AgentConnectBridge:
    """Bridge between Agent Connect and an agent loop.

    Mirrors the MCPToolBridge pattern exactly:
        - discover() → loads connector specs, checks vault, discovers tools
        - get_tool_definitions() → returns list[dict]
        - health() → reports connector health
        - list_available() → catalog of known connectors
    """

    def __init__(
        self,
        user_id: str,
        spec_dir: str | None = None,
        vault_path: str | None = None,
    ):
        self.user_id = user_id
        self._spec_dir = spec_dir or _default_spec_dir()
        self._vault = get_vault(user_id, vault_path)
        self._runtime = ConnectorRuntime(self._spec_dir, self._vault, user_id)
        self._tools: list[dict[str, Any]] = []

    @property
    def spec_dir(self) -> str:
        return self._spec_dir

    @property
    def runtime(self) -> ConnectorRuntime:
        return self._runtime

    @property
    def vault(self) -> CredentialVault:
        return self._vault

    async def discover(self) -> None:
        self._tools = self._runtime.get_tools()
        logger.info(
            f"agent_connect.discover user={self.user_id} tools={len(self._tools)}"
        )

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return self._tools

    def list_available(self) -> list[dict[str, Any]]:
        return self._runtime.list_available()

    def health(self) -> dict[str, Any]:
        vault_health = self._vault.health()
        connector_health = self._runtime.health()
        return {
            "vault": vault_health,
            "connectors": connector_health,
            "total_tools": len(self._tools),
        }

    def connected_services(self) -> list[str]:
        return self._vault.list_connected()

    def reload_specs(self) -> None:
        self._runtime.reload()
