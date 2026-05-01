"""Agent Connect meta-tools — SDK-native tools for connector management.

These are proper SDK ToolDefinition instances (same pattern as mcp_list/reload).
Four tools:
    connector_list      — List available connectors and connection status
    connector_connect   — Get OAuth URL for a connector (user clicks to authorize)
    connector_disconnect — Remove stored credentials for a service
    connector_health    — Report health of all connected connectors
"""

from __future__ import annotations

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, ToolDefinition

logger = get_logger()


async def _connector_list(user_id: str = "") -> str:
    """List all available SaaS connectors and their connection status."""
    if not user_id:
        return "Error: user_id is required."

    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)
        available = bridge.list_available()

        if not available:
            return "No connectors configured. Add YAML specs to the connectors directory."

        lines = ["Available SaaS Connectors:"]
        for conn in available:
            status = "CONNECTED" if conn["connected"] else "not connected"
            lines.append(f"  - {conn['name']} ({conn['display']}): {status}")
        return "\n".join(lines)

    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        logger.warning("connector.meta.list_failed", {"error": str(e)})
        return f"Error listing connectors: {e}"


connector_list = ToolDefinition(
    name="connector_list",
    description=(
        "List all available SaaS connectors and their connection status. "
        "Shows which services are connected (ready to use) and which need authorization."
        "\n\nArgs:\n    user_id: User identifier (REQUIRED)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(
        title="List SaaS Connectors", read_only=True, idempotent=True
    ),
    function=_connector_list,
)


async def _connector_connect(service: str = "", user_id: str = "") -> str:
    """Get the OAuth authorization URL for a SaaS connector.

    Returns a URL the user must open in a browser to authorize the connection.
    After authorization, the connector's tools become available to the agent.

    Args:
        service: Connector name (e.g. 'google-workspace', 'github')
        user_id: User identifier (REQUIRED)
    """
    if not user_id:
        return "Error: user_id is required."
    if not service:
        available = _available_services(user_id)
        if not available:
            return "No connectors configured. Add YAML specs to the connectors directory."
        return (
            "Specify a service to connect. Available services:\n"
            + "\n".join(f"  - {s}" for s in available)
        )

    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)
        available = bridge.list_available()

        spec = next((s for s in available if s["name"] == service), None)
        if not spec:
            return (
                f"Unknown connector: {service}. "
                f"Use connector_list to see available services."
            )

        if spec["connected"]:
            return f"{spec['display']} is already connected."

        # Build the authorization URL
        # In production, this would be the gateway's OAuth endpoint
        gateway = _get_gateway_url()
        auth_url = f"{gateway}/auth/login?service={service}&user_id={user_id}"

        return (
            f"To connect {spec['display']}, open this URL in your browser:\n"
            f"{auth_url}\n\n"
            f"After authorization, run connector_list to verify the connection."
        )

    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        logger.warning(
            "connector.meta.connect_failed", {"service": service, "error": str(e)}
        )
        return f"Error generating connect URL: {e}"


connector_connect = ToolDefinition(
    name="connector_connect",
    description=(
        "Get the authorization URL to connect a SaaS service. "
        "The user must open the URL in a browser to authorize. "
        "After authorization, the service's tools become available. "
        "Use connector_list first to see available services."
        "\n\nArgs:\n"
        "    service: Connector name (e.g. 'google-workspace', 'github'). "
        "Required.\n"
        "    user_id: User identifier (REQUIRED)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "default": "",
                "title": "Service",
                "description": "Connector name from connector_list",
            },
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(
        title="Connect SaaS Service", read_only=False, destructive=False
    ),
    function=_connector_connect,
)


async def _connector_disconnect(service: str = "", user_id: str = "") -> str:
    """Remove stored credentials for a connected SaaS service.

    Args:
        service: Connector name to disconnect
        user_id: User identifier (REQUIRED)
    """
    if not user_id:
        return "Error: user_id is required."
    if not service:
        return "Specify a service to disconnect. Use connector_list to see connected services."

    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)

        if not bridge.vault.is_connected(service):
            return f"{service} is not connected."

        bridge.vault.delete_token(service)
        bridge.reload_specs()
        return f"Disconnected from {service}. Its tools are no longer available."

    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        logger.warning(
            "connector.meta.disconnect_failed", {"service": service, "error": str(e)}
        )
        return f"Error disconnecting: {e}"


connector_disconnect = ToolDefinition(
    name="connector_disconnect",
    description=(
        "Remove stored credentials for a connected SaaS service. "
        "The service's tools will no longer be available until reconnected."
        "\n\nArgs:\n"
        "    service: Connector name to disconnect\n"
        "    user_id: User identifier (REQUIRED)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "default": "",
                "title": "Service",
                "description": "Connector name to disconnect",
            },
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(
        title="Disconnect SaaS Service", read_only=False, destructive=True
    ),
    function=_connector_disconnect,
)


async def _connector_health(user_id: str = "") -> str:
    """Report health of all connected SaaS connectors."""
    if not user_id:
        return "Error: user_id is required."

    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)
        health = bridge.health()

        lines = ["Connector Health:"]
        lines.append(f"  Vault: {health['vault']['status']}")
        lines.append(
            f"  Connected services: {health['vault'].get('connected_services', '?')}"
        )

        connectors = health.get("connectors", {})
        for name, info in connectors.items():
            if info["status"] == "not_connected":
                continue
            tool_count = info.get("tools", "?")
            lines.append(f"  - {name}: {info['status']} ({tool_count} tools)")

        return "\n".join(lines)

    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        return f"Error checking health: {e}"


connector_health = ToolDefinition(
    name="connector_health",
    description=(
        "Report health of all connected SaaS connectors. Shows which "
        "services are working and how many tools each provides."
        "\n\nArgs:\n    user_id: User identifier (REQUIRED)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "default": "", "title": "User Id"},
        },
    },
    annotations=ToolAnnotations(
        title="SaaS Connector Health", read_only=True, idempotent=True
    ),
    function=_connector_health,
)


def _available_services(user_id: str) -> list[str]:
    """Get list of available connector names for a user."""
    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)
        return [c["name"] for c in bridge.list_available()]
    except Exception:
        return []


def _get_gateway_url() -> str:
    """Get the gateway base URL from settings."""
    try:
        from src.config import get_settings

        settings = get_settings()
        return getattr(settings, "gateway_url", "http://localhost:8000")
    except Exception:
        return "http://localhost:8000"
