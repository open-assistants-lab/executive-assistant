"""CLI tool adapter — base class for wrapping CLI commands as SDK tools.

Provides a unified pattern for invoking external CLIs (firecrawl, browser-use, etc.)
with:
  - Automatic CLI discovery (is it on PATH?)
  - JSON output parsing (--json flag)
  - Timeout and error handling
  - Graceful error messages when CLI is missing

Subclasses define:
  - cli_name: the command name (e.g., "firecrawl", "browser-use")
  - install_hint: how to install the CLI
  - Tool functions that call self._run(...)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from src.app_logging import get_logger

logger = get_logger()


class CLIToolAdapter:
    """Base class for CLI-backed SDK tools.

    Usage:
        class FirecrawlCLI(CLIToolAdapter):
            cli_name = "firecrawl"
            install_hint = "npm install -g firecrawl-cli"

        fc = FirecrawlCLI()
        result = fc.run(["scrape", "https://example.com", "--json"])
    """

    cli_name: str = ""
    install_hint: str = ""
    _detected: bool | None = None

    def is_available(self) -> bool:
        """Check if the CLI is on PATH."""
        if self._detected is not None:
            return self._detected
        self._detected = shutil.which(self.cli_name) is not None
        return self._detected

    def run(
        self,
        args: list[str],
        timeout: int = 120,
        json_output: bool = False,
    ) -> tuple[int, str]:
        """Run a CLI command and return (exit_code, output).

        Args:
            args: CLI arguments (e.g., ["scrape", "https://example.com", "--json"])
            timeout: Timeout in seconds
            json_output: Whether to expect JSON and add --json flag

        Returns:
            Tuple of (exit_code, stdout+stderr combined)
        """
        if not self.is_available():
            return (
                -1,
                f"Error: {self.cli_name} CLI is not installed. Install with: {self.install_hint}",
            )

        cmd = [self.cli_name, *args]
        if json_output and "--json" not in args and "-j" not in args:
            cmd.append("--json")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n{result.stderr}" if output else result.stderr

            if result.returncode != 0:
                logger.warning(
                    "cli_tool.error",
                    {"cli": self.cli_name, "args": args[:3], "rc": result.returncode},
                )

            return result.returncode, output

        except subprocess.TimeoutExpired:
            return -2, f"Error: {self.cli_name} command timed out after {timeout}s"
        except FileNotFoundError:
            self._detected = False
            return (
                -1,
                f"Error: {self.cli_name} CLI is not installed. Install with: {self.install_hint}",
            )
        except Exception as e:
            return -3, f"Error running {self.cli_name}: {e}"

    def run_json(
        self,
        args: list[str],
        timeout: int = 120,
    ) -> dict[str, Any] | list | None:
        """Run a CLI command expecting JSON output.

        Returns parsed JSON dict/list or None on failure.
        """
        rc, output = self.run(args, timeout=timeout, json_output=True)

        if rc != 0:
            return None

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # Some CLIs output text before JSON (e.g., progress bars)
            # Try to find JSON start
            for start_char in ("{", "["):
                idx = output.find(start_char)
                if idx >= 0:
                    try:
                        return json.loads(output[idx:])
                    except json.JSONDecodeError:
                        continue
            return None

    def require(self) -> str | None:
        """Return error message if CLI not available, None if available."""
        if not self.is_available():
            return f"{self.cli_name} CLI is not installed. Install with: {self.install_hint}"
        return None
