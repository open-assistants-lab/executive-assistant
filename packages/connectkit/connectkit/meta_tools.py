"""Agent Connect meta-tools — framework-agnostic tool specs for connector management.

Each tool is a ToolSpec (Pydantic model) that any agent SDK adapter can convert
into its native tool format (EA ToolDefinition, OpenAI function, etc.).

Five tools:
    connector_list      — List available connectors and connection status
    connector_connect   — Get OAuth URL for a connector
    connector_disconnect — Remove stored credentials for a service
    connector_health    — Report health of all connected connectors
    connector_install_tools — Install missing CLI binaries for a connector
"""

from __future__ import annotations

import logging

from connectkit.sdk_adapter import ToolSpec

logger = logging.getLogger("connectkit.meta_tools")


# ── Tool implementations ──

async def _list(service: str = "", user_id: str = "") -> str:
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


async def _connect(service: str = "", user_id: str = "", gateway_url: str = "") -> str:
    """Connect a SaaS service. gateway_url is injected by the framework adapter."""
    if not user_id:
        return "Error: user_id is required."
    if not service:
        try:
            from connectkit.bridge import ConnectKitBridge

            bridge = ConnectKitBridge(user_id=user_id)
            available = [c["name"] for c in bridge.list_available()]
        except Exception:
            available = []
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
        auth_url = f"{gateway_url}/auth/login?service={service}&user_id={user_id}"
        return (
            f"To connect {spec['display']}, open this URL in your browser:\n"
            f"{auth_url}\n\n"
            f"After authorization, run connector_list to verify the connection."
        )
    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        logger.warning("connector.meta.connect_failed", {"service": service, "error": str(e)})
        return f"Error generating connect URL: {e}"


async def _disconnect(service: str = "", user_id: str = "") -> str:
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
        logger.warning("connector.meta.disconnect_failed", {"service": service, "error": str(e)})
        return f"Error disconnecting: {e}"


async def _health(user_id: str = "") -> str:
    if not user_id:
        return "Error: user_id is required."
    try:
        from connectkit.bridge import ConnectKitBridge

        bridge = ConnectKitBridge(user_id=user_id)
        health = bridge.health()
        lines = ["Connector Health:"]
        lines.append(f"  Vault: {health['vault']['status']}")
        lines.append(f"  Connected services: {health['vault'].get('connected_services', '?')}")
        for name, info in health.get("connectors", {}).items():
            if info["status"] == "not_connected":
                continue
            tool_count = info.get("tools", "?")
            lines.append(f"  - {name}: {info['status']} ({tool_count} tools)")
        return "\n".join(lines)
    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        return f"Error checking health: {e}"


async def _install_tools(service: str = "", user_id: str = "") -> str:
    if not user_id:
        return "Error: user_id is required."
    try:
        from connectkit.bridge import ConnectKitBridge
        from connectkit.utils import ensure_cli_installed

        bridge = ConnectKitBridge(user_id=user_id)
        specs = {s.name: s for s in bridge.list_available_specs()}

        services: list[str] = []
        if service:
            if service not in specs:
                return f"Unknown connector: {service}. Use connector_list to see available services."
            services = [service]
        else:
            services = bridge.vault.list_connected()
            if not services:
                return "No connectors are connected. Use connector_connect first."

        installed: list[str] = []
        for name in services:
            spec = specs.get(name)
            if spec:
                result = ensure_cli_installed(spec)
                installed.extend(result)

        if not installed:
            return "All CLI tools are already installed."
        return "Installed: " + ", ".join(installed)
    except ImportError:
        return "ConnectKit is not installed. pip install connectkit"
    except Exception as e:
        logger.warning("connector.meta.install_tools_failed", {"service": service, "error": str(e)})
        return f"Error installing tools: {e}"


# ── ToolSpec definitions ──

def _list_spec() -> ToolSpec:
    return ToolSpec(
        name="connector_list",
        description=(
            "List all available SaaS connectors and their connection status. "
            "Shows which services are connected (ready to use) and which need authorization."
        ),
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string", "default": "", "title": "Service (optional)"},
                "user_id": {"type": "string", "default": "", "title": "User Id"},
            },
        },
        annotations={"title": "List SaaS Connectors", "read_only": True, "idempotent": True},
        async_function=_list,
    )


def _connect_spec() -> ToolSpec:
    return ToolSpec(
        name="connector_connect",
        description=(
            "Connect a SaaS service. Returns an OAuth URL the user must open in a browser. "
            "After authorization, the service's tools become available. "
            "Use connector_list first to see available services."
        ),
        parameters={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "default": "",
                    "title": "Service",
                    "description": "Connector name (e.g. 'google-workspace')",
                },
                "user_id": {"type": "string", "default": "", "title": "User Id"},
            },
        },
        annotations={"title": "Connect SaaS Service", "read_only": False, "destructive": False},
        async_function=_connect,
    )


def _disconnect_spec() -> ToolSpec:
    return ToolSpec(
        name="connector_disconnect",
        description=(
            "Remove stored credentials for a connected SaaS service. "
            "The service's tools will no longer be available until reconnected."
        ),
        parameters={
            "type": "object",
            "properties": {
                "service": {"type": "string", "default": "", "title": "Service"},
                "user_id": {"type": "string", "default": "", "title": "User Id"},
            },
        },
        annotations={"title": "Disconnect SaaS Service", "read_only": False, "destructive": True},
        async_function=_disconnect,
    )


def _health_spec() -> ToolSpec:
    return ToolSpec(
        name="connector_health",
        description=(
            "Report health of all connected SaaS connectors. Shows which "
            "services are working and how many tools each provides."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "", "title": "User Id"},
            },
        },
        annotations={"title": "SaaS Connector Health", "read_only": True, "idempotent": True},
        async_function=_health,
    )


def _install_tools_spec() -> ToolSpec:
    return ToolSpec(
        name="connector_install_tools",
        description=(
            "Install CLI tools for a connected SaaS connector. "
            "Runs the install command from the connector spec "
            "(e.g. npm install -g @googleworkspace/cli for Google Workspace)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "default": "",
                    "title": "Service",
                    "description": "Connector name (leave empty to check all connected)",
                },
                "user_id": {"type": "string", "default": "", "title": "User Id"},
            },
        },
        annotations={
            "title": "Install Connector CLI Tools",
            "read_only": False,
            "destructive": False,
        },
        async_function=_install_tools,
    )


TOOL_SPECS: list[ToolSpec] = [
    _list_spec(),
    _connect_spec(),
    _disconnect_spec(),
    _health_spec(),
    _install_tools_spec(),
]