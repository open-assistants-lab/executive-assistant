"""ConnectKit — connect AI agents to SaaS accounts.

One YAML file per service. OAuth, token vault, and tool discovery handled automatically.
"""

__version__ = "0.1.0"

from connectkit.bridge import ConnectKitBridge
from connectkit.spec import AuthType, ConnectorSpec, RequiredField, ToolSourceType
from connectkit.vault import CredentialVault

__all__ = [
    "ConnectorSpec",
    "AuthType",
    "ToolSourceType",
    "RequiredField",
    "CredentialVault",
    "ConnectKitBridge",
]
