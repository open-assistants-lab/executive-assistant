"""ConnectKit — connect AI agents to SaaS accounts.

One YAML file per service. OAuth, token vault, and tool discovery handled automatically.
"""

__version__ = "0.1.0"

from connectkit.bridge import ConnectKitBridge
from connectkit.meta_tools import TOOL_SPECS
from connectkit.sdk_adapter import ToolSpec
from connectkit.spec import AuthType, ConnectorSpec, RequiredField, ToolSourceType, CLIToolSource
from connectkit.utils import ensure_cli_installed
from connectkit.vault import CredentialVault

__all__ = [
    "ConnectorSpec",
    "AuthType",
    "ToolSourceType",
    "RequiredField",
    "CredentialVault",
    "ConnectKitBridge",
    "ToolSpec",
    "TOOL_SPECS",
    "CLIToolSource",
    "ensure_cli_installed",
]
