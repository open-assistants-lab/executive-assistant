"""CLI installation utilities for connector tool sources."""

from __future__ import annotations

import logging
import shutil
import subprocess

from connectkit.spec import CLIToolSource, ConnectorSpec

logger = logging.getLogger("connectkit.utils")


def ensure_cli_installed(spec: ConnectorSpec) -> list[str]:
    """Install missing CLI tools for a connector spec.

    Checks each CLI tool source in the spec. If the command is not found
    on PATH, runs the install command from the spec.

    Returns a list of installed commands (empty if all were already present).
    """
    installed: list[str] = []
    for source in spec.get_tool_sources():
        if not isinstance(source, CLIToolSource):
            continue
        if shutil.which(source.command):
            continue
        if not source.install:
            logger.warning(
                "cli_not_found_no_install",
                {"command": source.command, "spec": spec.name},
            )
            continue
        logger.info(
            "installing_cli",
            {"command": source.command, "install": source.install},
        )
        try:
            subprocess.run(
                source.install,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            installed.append(source.command)
        except Exception as e:
            logger.warning(
                "cli_install_failed",
                {"command": source.command, "error": str(e)},
            )
    return installed