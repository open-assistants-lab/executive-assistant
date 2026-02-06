"""Development entry point (HTTP-first)."""

from __future__ import annotations

import os

from executive_assistant.main import run_main


def main() -> None:
    """Run the assistant with HTTP channel enabled by default."""
    os.environ.setdefault("EXECUTIVE_ASSISTANT_CHANNELS", "http")
    run_main()


if __name__ == "__main__":
    main()
