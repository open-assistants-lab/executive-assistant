"""MCP Manager - Stateful MCP server management with lazy start and idle timeout."""

import asyncio
import hashlib
import os
import time
from typing import Any

from src.app_logging import get_logger
from src.config import get_settings
from src.tools.mcp.config import (
    MCPServerConfig,
    get_config_mtime,
    load_mcp_config,
)

logger = get_logger()

_MCP_MANAGERS: dict[str, "MCPManager"] = {}


class MCPManager:
    """Manages MCP servers for a user with lazy start and idle timeout."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._clients: dict[str, Any] = {}
        self._tools: dict[str, list[Any]] = {}
        self._config_mtime: float = 0.0
        self._config_hash: str = ""
        self._lock = asyncio.Lock()
        self._last_used: float = time.time()
        self._idle_task: asyncio.Task | None = None

    def _get_idle_timeout(self) -> int:
        """Get idle timeout from config (in seconds)."""
        try:
            settings = get_settings()
            return settings.mcp.idle_timeout_minutes * 60
        except Exception:
            return 30 * 60  # Default 30 minutes

    def _is_enabled(self) -> bool:
        """Check if MCP is enabled in config."""
        try:
            settings = get_settings()
            return settings.mcp.enabled
        except Exception:
            return True  # Default enabled

    async def _start_idle_monitor(self) -> None:
        """Start background task to monitor idle timeout."""
        if self._idle_task is not None:
            return

        async def _monitor():
            while True:
                await asyncio.sleep(60)  # Check every minute
                if not self._clients:
                    continue

                idle_time = time.time() - self._last_used
                timeout = self._get_idle_timeout()

                if idle_time > timeout:
                    logger.info(
                        "mcp.idle_timeout",
                        {
                            "user_id": self.user_id,
                            "idle_seconds": int(idle_time),
                            "timeout": timeout,
                        },
                    )
                    await self._stop_all()

        self._idle_task = asyncio.create_task(_monitor())

    async def _ensure_started(self) -> None:
        """Ensure MCP servers are started (lazy start)."""
        if not self._is_enabled():
            return

        if self._clients:
            return  # Already started

        config = load_mcp_config(self.user_id)
        if not config:
            logger.info("mcp.no_config", {"user_id": self.user_id})
            return

        self._config_mtime = get_config_mtime(self.user_id)
        self._config_hash = self._compute_config_hash(config)

        for server_name, server_config in config.mcpServers.items():
            await self._start_server(server_name, server_config)

        await self._start_idle_monitor()

    def _compute_config_hash(self, config) -> str:
        """Compute hash of config for change detection."""
        data = config.model_dump_json()
        return hashlib.md5(data.encode()).hexdigest()

    async def _start_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """Start an MCP server and get its tools."""
        try:
            logger.info(
                "mcp.starting_server",
                {"server": server_name, "command": server_config.command},
            )
            client = await self._create_client(server_name, server_config)
            self._clients[server_name] = client

            tools = await client.get_tools()
            self._tools[server_name] = tools

            logger.info("mcp.server_started", {"server": server_name, "tools": len(tools)})
        except Exception as e:
            logger.error(
                "mcp.server_error",
                {"server": server_name, "error": str(e), "error_type": type(e).__name__},
            )

    async def _create_client(self, server_name: str, server_config: MCPServerConfig):
        """Create MCP client for a server."""
        from langchain_mcp_adapters.client import MultiServerMCPClient

        if server_config.transport == "http" or server_config.url:
            client_config = {
                server_name: {
                    "transport": "http",
                    "url": server_config.url or "http://localhost:8000/mcp",
                }
            }
        else:
            env = dict(os.environ)
            env.update(server_config.env)

            client_config = {
                server_name: {
                    "transport": "stdio",
                    "command": server_config.command,
                    "args": server_config.args,
                    "env": env,
                }
            }

        return MultiServerMCPClient(client_config)

    def _config_changed(self) -> bool:
        """Check if config file has changed."""
        current_mtime = get_config_mtime(self.user_id)
        if current_mtime != self._config_mtime:
            return True

        config = load_mcp_config(self.user_id)
        if config and self._compute_config_hash(config) != self._config_hash:
            return True

        return False

    async def get_tools(self, server_name: str | None = None) -> list[Any]:
        """Get tools from MCP servers (lazy start on first call)."""
        if not self._is_enabled():
            return []

        async with self._lock:
            # Lazy start if not already started
            await self._ensure_started()

            # Check config changes and restart if needed
            if self._config_changed():
                await self._restart_all()

            # Update last used time
            self._last_used = time.time()

            if not self._clients:
                return []

            if server_name:
                return self._tools.get(server_name, [])

            all_tools = []
            for tools in self._tools.values():
                all_tools.extend(tools)
            return all_tools

    async def list_servers(self) -> dict[str, Any]:
        """List configured MCP servers and their status."""
        config = load_mcp_config(self.user_id)
        servers = {}

        if config:
            for name, cfg in config.mcpServers.items():
                servers[name] = {
                    "command": cfg.command,
                    "args": cfg.args,
                    "transport": cfg.transport,
                    "running": name in self._clients,
                    "tool_count": len(self._tools.get(name, [])),
                }

        return servers

    async def reload(self) -> str:
        """Reload all MCP servers."""
        await self._restart_all()
        return "MCP servers reloaded"

    async def _restart_all(self) -> None:
        """Stop all servers and restart from config."""
        logger.info("mcp.reloading", {"user_id": self.user_id})

        await self._stop_all()

        config = load_mcp_config(self.user_id)
        if config:
            self._config_mtime = get_config_mtime(self.user_id)
            self._config_hash = self._compute_config_hash(config)

            for server_name, server_config in config.mcpServers.items():
                await self._start_server(server_name, server_config)

    async def _stop_all(self) -> None:
        """Stop all MCP servers."""
        for server_name in list(self._clients.keys()):
            await self._stop_server(server_name)

    async def _stop_server(self, server_name: str) -> None:
        """Stop a specific MCP server."""
        if server_name in self._clients:
            try:
                client = self._clients[server_name]
                await client.aclose()
            except Exception:
                pass
            del self._clients[server_name]

        if server_name in self._tools:
            del self._tools[server_name]

        logger.info("mcp.server_stopped", {"server": server_name})

    async def cleanup(self) -> None:
        """Clean up all MCP resources."""
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None
        await self._stop_all()


def get_mcp_manager(user_id: str) -> MCPManager:
    """Get or create MCP manager for a user."""
    if user_id not in _MCP_MANAGERS:
        _MCP_MANAGERS[user_id] = MCPManager(user_id)
    return _MCP_MANAGERS[user_id]
