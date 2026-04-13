"""Shell tool for agent - restricted command execution."""

import re
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

# Characters that enable shell injection when used with shell=True
SHELL_METACHARACTERS = re.compile(r"[;|&$`\n\r\\!>{<]")

# Patterns that indicate injection attempts even without metacharacters
SHELL_INJECTION_PATTERNS = re.compile(
    r"(?:"
    r"\$\(|"  # Command substitution
    r"\`|"  # Backtick command substitution
    r"\.\./|"  # Path traversal
    r"~\/|"  # Home directory access
    r"/etc/|"  # System config access
    r"/tmp/"  # Temp directory access
    r")",
    re.IGNORECASE,
)


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
    root = Path(f"data/users/{user_id}/workspace")
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


def _validate_command(command: str) -> str | None:
    """Validate command for shell injection.

    Returns:
        Error message if command is dangerous, None if safe.
    """
    if not command.strip():
        return "Empty command"

    if SHELL_METACHARACTERS.search(command):
        return (
            "Command rejected: contains shell metacharacters. "
            "Only simple commands are allowed (no ; & | $ ` etc.)."
        )

    if SHELL_INJECTION_PATTERNS.search(command):
        return "Command rejected: contains potentially dangerous patterns."

    cmd_parts = command.split()
    if not cmd_parts:
        return "Empty command"

    cmd_base = cmd_parts[0]
    # Ensure the base command is a simple name without path separators
    if "/" in cmd_base or "\\" in cmd_base:
        return f"Command rejected: use command name only, not paths (got '{cmd_base}')."

    return None


@tool
def shell_execute(command: str, user_id: str = "default") -> str:
    """Run a shell command.

    Args:
        command: Command to execute
        user_id: User identifier

    Returns:
        Command output or error message
    """
    try:
        # Validate for shell injection first
        validation_error = _validate_command(command)
        if validation_error:
            return validation_error

        cmd_parts = command.split()
        cmd_base = cmd_parts[0]
        is_allowed_cmd = _is_allowed(cmd_base)

        if not is_allowed_cmd:
            config = _get_shell_config()
            return f"Command not allowed: {cmd_base}. Allowed: {', '.join(sorted(config['allowed_commands']))}"

        root_path = _get_root_path(user_id)
        config = _get_shell_config()

        # Use shell=False with args as a list for safety
        result = subprocess.run(
            cmd_parts,
            shell=False,
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

        logger.info(
            "shell_execute", {"command": command, "return_code": result.returncode}, user_id=user_id
        )
        return output or "(no output)"

    except subprocess.TimeoutExpired:
        config = _get_shell_config()
        return f"Error: Command timed out after {config['timeout_seconds']} seconds"
    except FileNotFoundError:
        return f"Error: Command not found: {cmd_parts[0]}"
    except Exception as e:
        logger.error("shell_execute.error", {"command": command, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"
