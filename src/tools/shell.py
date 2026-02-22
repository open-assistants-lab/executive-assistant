"""Shell tool for agent - restricted command execution."""

import subprocess
from pathlib import Path

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()

DEFAULT_ALLOWED_COMMANDS = {
    "python3",
    "node",
    "echo",
    "date",
    "whoami",
    "pwd",
}


def _get_shell_config():
    """Get shell config from settings."""
    settings = get_settings()
    shell_config = getattr(settings, "shell_tool", None)
    if shell_config:
        return {
            "allowed_commands": set(shell_config.allowed_commands),
            "timeout_seconds": getattr(shell_config, "timeout_seconds", 30),
            "max_output_kb": getattr(shell_config, "max_output_kb", 100),
        }
    return {
        "allowed_commands": DEFAULT_ALLOWED_COMMANDS,
        "timeout_seconds": 30,
        "max_output_kb": 100,
    }


def _get_root_path(user_id: str) -> Path:
    """Get root path for user."""
    settings = get_settings()
    root = Path(settings.filesystem.root_path.format(user_id=user_id))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_allowed(cmd: str) -> bool:
    """Check if command is allowed.

    Returns:
        True if allowed, False otherwise
    """
    config = _get_shell_config()
    allowed = config["allowed_commands"]

    cmd_base = cmd.split()[0] if cmd.split() else ""

    return cmd_base in allowed


@tool
def run_shell(command: str, user_id: str = "default") -> str:
    """Run a shell command.

    Args:
        command: Command to execute
        user_id: User identifier

    Returns:
        Command output or error message
    """
    try:
        cmd_base = command.split()[0] if command.split() else ""
        is_allowed_cmd = _is_allowed(cmd_base)

        if not is_allowed_cmd:
            config = _get_shell_config()
            return f"Command not allowed: {cmd_base}. Allowed: {', '.join(sorted(config['allowed_commands']))}"

        root_path = _get_root_path(user_id)
        config = _get_shell_config()

        result = subprocess.run(
            command,
            shell=True,
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=config["timeout_seconds"],
        )

        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"

        max_output = config["max_output_kb"] * 1024
        if len(output) > max_output:
            output = (
                output[:max_output]
                + f"\n... (truncated, output exceeded {config['max_output_kb']}KB)"
            )

        logger.info("run_shell", {"command": command, "return_code": result.returncode})
        return output or "(no output)"

    except subprocess.TimeoutExpired:
        config = _get_shell_config()
        return f"Error: Command timed out after {config['timeout_seconds']} seconds"
    except Exception as e:
        logger.error("run_shell.error", {"command": command, "error": str(e)})
        return f"Error: {e}"
