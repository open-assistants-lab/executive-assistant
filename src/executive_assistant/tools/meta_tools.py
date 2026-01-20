"""Tools for viewing system metadata inventory."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.meta_registry import load_meta, refresh_meta, format_meta


@tool
async def get_meta(format: str = "text", refresh: bool = False) -> str:
    """
    View thread system inventory (files/KB/DB/reminders).

    Args:
        format: "text" (default) or "json".
        refresh: If true, rebuild metadata before returning.

    Returns:
        Inventory summary in the requested format.
    """
    thread_id = get_thread_id()
    if thread_id is None:
        return "Error: No thread_id in context."

    if refresh:
        meta = await refresh_meta(thread_id)
    else:
        meta = load_meta(thread_id)

    if format.lower() == "json":
        return json.dumps(meta, indent=2)

    return format_meta(meta, markdown=False)


def get_meta_tools() -> list:
    """Get meta tools for agent use."""
    return [get_meta]
