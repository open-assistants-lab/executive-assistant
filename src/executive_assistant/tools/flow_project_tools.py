"""Flow project workspace helpers."""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool

from executive_assistant.config.settings import settings
from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id


def _sanitize_project_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_-]+", "-", name).strip("-")
    return name[:64] or "flow-project"


@tool
def create_flow_project_workspace(project_name: str) -> str:
    """Create a hidden workspace for flow research/design artifacts. [Files]

    Creates ./data/{user_id}/.{project}/ with starter markdown files.
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "No thread context available."

    user_id = sanitize_thread_id_to_user_id(thread_id)
    safe_name = _sanitize_project_name(project_name)
    base = (settings.USERS_ROOT / user_id / f".{safe_name}").resolve()
    base.mkdir(parents=True, exist_ok=True)

    for fname in ("research.md", "plan.md", "progress.md", "tests.md"):
        fpath = base / fname
        if not fpath.exists():
            fpath.write_text("", encoding="utf-8")

    return f"Flow workspace created: {base}"
