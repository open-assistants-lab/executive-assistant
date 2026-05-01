"""MCPAdapter — vault token injection for MCP tool source connectors.

This adapter wraps a ConnectorSpec whose tool_source.type is "mcp".
It reads the user's OAuth/API token from CredentialVault, injects it
into the MCP server process environment, then returns tool definitions.

For EA integration, the actual MCP server lifecycle is managed by the
existing MCPToolBridge + MCPManager. This adapter just provides the
env dict with per-user tokens.

Usage:
    adapter = MCPAdapter(spec, vault, user_id="alice")
    server_env = adapter.build_server_env()
    # Pass server_env to MCPToolBridge when registering the server
"""

import logging
from typing import Any

from connectkit.spec import ConnectorSpec, MCPToolSource
from connectkit.vault import CredentialVault

logger = logging.getLogger("connectkit")


class MCPAdapter:
    """Wraps an MCP server connector with per-user token injection."""

    def __init__(
        self,
        spec: ConnectorSpec,
        vault: CredentialVault,
        user_id: str,
    ):
        self.spec = spec
        self.vault = vault
        self.user_id = user_id
        self._source: MCPToolSource = spec.tool_source  # type: ignore[assignment]

    @property
    def server_name(self) -> str:
        return self._source.server_name

    @property
    def command(self) -> str:
        return self._source.command

    def build_server_env(self) -> dict[str, str]:
        import os

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

    def get_mcp_config(self) -> dict[str, Any]:
        """Return config dict suitable for registering with MCPManager.

        The caller can pass this to their existing MCP server registry.
        """
        return {
            "command": self._source.command,
            "env": self.build_server_env(),
            "transport": "stdio",
        }

    def health(self) -> dict[str, Any]:
        try:
            token_data = self.vault.get_token(self.spec.name)
            has_token = token_data is not None and "access_token" in token_data
            return {
                "status": "ok" if has_token else "not_connected",
                "service": self.spec.name,
                "server": self._source.server_name,
            }
        except Exception as e:
            return {"status": "error", "service": self.spec.name, "error": str(e)}
