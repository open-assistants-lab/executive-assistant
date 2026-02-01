"""User-specific MCP (Model Context Protocol) storage.

This module provides storage and validation for user-defined MCP server configurations,
enabling per-thread customization of available tools while maintaining security isolation.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config.settings import get_settings


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class UserMCPStorage:
    """Storage for user-specific MCP configurations.

    Manages two types of MCP server configurations:
    - Local (stdio): Command-line tools run via stdio
    - Remote (HTTP/SSE): Network-accessible MCP servers

    All configurations are stored per-thread for isolation.
    """

    def __init__(self, thread_id: str):
        """Initialize storage for a specific thread.

        Args:
            thread_id: Thread identifier (e.g., "telegram:123456" or "http:conv_id")
        """
        self.thread_id = thread_id
        self.mcp_dir = get_settings().get_thread_mcp_dir(thread_id)
        self.mcp_dir.mkdir(parents=True, exist_ok=True)

    def load_local_config(self) -> dict:
        """Load local MCP configuration (stdio servers).

        Returns:
            Configuration dict with "mcpServers" key.
            Returns empty config if file doesn't exist.
        """
        config_file = self.mcp_dir / "mcp.json"

        if not config_file.exists():
            return {
                "version": "1.0",
                "updated_at": _utc_now(),
                "mcpServers": {},
            }

        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in mcp.json: {e}")

    def load_remote_config(self) -> dict:
        """Load remote MCP configuration (HTTP/SSE servers).

        Returns:
            Configuration dict with "mcpServers" key.
            Returns empty config if file doesn't exist.
        """
        config_file = self.mcp_dir / "mcp_remote.json"

        if not config_file.exists():
            return {
                "version": "1.0",
                "updated_at": _utc_now(),
                "mcpServers": {},
            }

        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in mcp_remote.json: {e}")

    def save_local_config(self, config: dict) -> None:
        """Save local MCP configuration with validation.

        Args:
            config: Configuration dict to save

        Raises:
            ValueError: If config validation fails
        """
        # Validate structure
        self._validate_config_structure(config)

        # Validate each server
        for name, server in config.get("mcpServers", {}).items():
            self._validate_stdio_server(name, server)

        # Create backup
        self._backup_config("mcp.json")

        # Update metadata
        config["version"] = "1.0"
        config["updated_at"] = _utc_now()

        # Write to file
        config_file = self.mcp_dir / "mcp.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

    def save_remote_config(self, config: dict) -> None:
        """Save remote MCP configuration with validation.

        Args:
            config: Configuration dict to save

        Raises:
            ValueError: If config validation fails
        """
        # Validate structure
        self._validate_config_structure(config)

        # Validate each server
        for name, server in config.get("mcpServers", {}).items():
            self._validate_remote_server(name, server)

        # Create backup
        self._backup_config("mcp_remote.json")

        # Update metadata
        config["version"] = "1.0"
        config["updated_at"] = _utc_now()

        # Write to file
        config_file = self.mcp_dir / "mcp_remote.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

    def _validate_config_structure(self, config: dict) -> None:
        """Validate basic configuration structure.

        Args:
            config: Configuration dict to validate

        Raises:
            ValueError: If structure is invalid
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")

        if "mcpServers" not in config:
            raise ValueError("Missing required key: 'mcpServers'")

        if not isinstance(config["mcpServers"], dict):
            raise ValueError("'mcpServers' must be a dictionary")

        # Validate server names
        for name in config["mcpServers"].keys():
            self._validate_server_name(name)

    def _validate_server_name(self, name: str) -> None:
        """Validate MCP server name.

        Args:
            name: Server name to validate

        Raises:
            ValueError: If name is invalid
        """
        if not name:
            raise ValueError("Server name cannot be empty")

        if not isinstance(name, str):
            raise ValueError("Server name must be a string")

        # Only allow alphanumeric, underscore, hyphen
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(
                f"Invalid server name '{name}'. "
                "Use only letters, numbers, underscore, and hyphen."
            )

    def _validate_stdio_server(self, name: str, server: dict) -> None:
        """Validate stdio MCP server configuration.

        Args:
            name: Server name
            server: Server configuration dict

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(server, dict):
            raise ValueError(f"Server '{name}' config must be a dictionary")

        # Required fields
        required = ["command"]
        for field in required:
            if field not in server:
                raise ValueError(f"Server '{name}' missing required field: '{field}'")

        # Validate command
        if not isinstance(server["command"], str):
            raise ValueError(f"Server '{name}' command must be a string")

        # Validate args (optional)
        if "args" in server:
            if not isinstance(server["args"], list):
                raise ValueError(f"Server '{name}' args must be a list")

            for i, arg in enumerate(server["args"]):
                if not isinstance(arg, str):
                    raise ValueError(
                        f"Server '{name}' arg {i} must be a string"
                    )

        # Validate env (optional)
        if "env" in server:
            if not isinstance(server["env"], dict):
                raise ValueError(f"Server '{name}' env must be a dictionary")

            for key, value in server["env"].items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError(
                        f"Server '{name}' env keys and values must be strings"
                    )

        # Validate cwd (optional)
        if "cwd" in server:
            if not isinstance(server["cwd"], str):
                raise ValueError(f"Server '{name}' cwd must be a string")

    def _validate_remote_server(self, name: str, server: dict) -> None:
        """Validate remote MCP server configuration.

        Args:
            name: Server name
            server: Server configuration dict

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(server, dict):
            raise ValueError(f"Server '{name}' config must be a dictionary")

        # Required fields
        required = ["url"]
        for field in required:
            if field not in server:
                raise ValueError(f"Server '{name}' missing required field: '{field}'")

        # Validate URL
        if not isinstance(server["url"], str):
            raise ValueError(f"Server '{name}' url must be a string")

        url = server["url"]

        # Require HTTPS for security (allow localhost for testing)
        if not (
            url.startswith("https://") or
            url.startswith("http://localhost") or
            url.startswith("http://127.0.0.1") or
            url.startswith("http://localhost:") or
            url.startswith("http://127.0.0.1:")
        ):
            raise ValueError(
                f"Server '{name}' must use HTTPS (or http://localhost for testing)"
            )

        # Validate headers (optional)
        if "headers" in server:
            if not isinstance(server["headers"], dict):
                raise ValueError(f"Server '{name}' headers must be a dictionary")

    def _backup_config(self, filename: str) -> None:
        """Create backup of existing config file.

        Args:
            filename: Config filename to backup
        """
        config_file = self.mcp_dir / filename

        if not config_file.exists():
            return

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.backup_{timestamp}"
        backup_file = self.mcp_dir / backup_name

        # Copy to backup
        shutil.copy2(config_file, backup_file)

        # Keep only last 5 backups
        self._cleanup_old_backups(filename)

    def _cleanup_old_backups(self, filename: str, keep: int = 5) -> None:
        """Remove old backup files, keeping only the most recent.

        Args:
            filename: Config filename (without .backup_ prefix)
            keep: Number of backups to keep
        """
        pattern = f"{filename}.backup_*"
        backups = sorted(self.mcp_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

        # Remove old backups
        for old_backup in backups[keep:]:
            old_backup.unlink()

    def list_backups(self, filename: str = "mcp.json") -> list[dict]:
        """List available backup files.

        Args:
            filename: Config filename to list backups for

        Returns:
            List of backup info dicts with 'name', 'timestamp', 'size' keys
        """
        pattern = f"{filename}.backup_*"
        backups = []

        for backup_file in self.mcp_dir.glob(pattern):
            stat = backup_file.stat()
            # Extract timestamp from filename
            timestamp_str = backup_file.stem.split(".backup_")[-1]

            backups.append({
                "name": backup_file.name,
                "timestamp": timestamp_str,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        # Sort by modification time (newest first)
        backups.sort(key=lambda b: b["modified"], reverse=True)
        return backups

    def restore_backup(self, backup_filename: str) -> None:
        """Restore configuration from backup.

        Args:
            backup_filename: Name of backup file to restore

        Raises:
            ValueError: If backup filename is invalid
            FileNotFoundError: If backup doesn't exist
        """
        # Validate filename format first
        if backup_filename.startswith("mcp.json.backup_"):
            target_filename = "mcp.json"
        elif backup_filename.startswith("mcp_remote.json.backup_"):
            target_filename = "mcp_remote.json"
        else:
            raise ValueError(f"Invalid backup filename: {backup_filename}")

        # Check if backup exists
        backup_path = self.mcp_dir / backup_filename
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup '{backup_filename}' not found")

        # Restore backup
        target_path = self.mcp_dir / target_filename
        shutil.copy2(backup_path, target_path)

    def has_local_config(self) -> bool:
        """Check if local MCP config exists.

        Returns:
            True if mcp.json exists
        """
        return (self.mcp_dir / "mcp.json").exists()

    def has_remote_config(self) -> bool:
        """Check if remote MCP config exists.

        Returns:
            True if mcp_remote.json exists
        """
        return (self.mcp_dir / "mcp_remote.json").exists()


# Convenience function
def get_user_mcp_storage(thread_id: str) -> UserMCPStorage:
    """Get UserMCPStorage instance for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        UserMCPStorage instance
    """
    return UserMCPStorage(thread_id)


# Note: There is also a module-level get_thread_mcp_dir() function in settings.py
# that uses context (get_thread_id()). UserMCPStorage uses the instance method
# get_settings().get_thread_mcp_dir(thread_id) instead for explicit thread_id.
