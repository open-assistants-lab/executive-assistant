"""Agent Connect — connect AI agents to SaaS accounts.

One YAML file per service. OAuth, token vault, and tool discovery handled automatically.
"""

__version__ = "0.1.0"

from agent_connect.bridge import AgentConnectBridge
from agent_connect.spec import AuthType, ConnectorSpec, ToolSourceType
from agent_connect.vault import CredentialVault

__all__ = [
    "ConnectorSpec",
    "AuthType",
    "ToolSourceType",
    "CredentialVault",
    "AgentConnectBridge",
]
