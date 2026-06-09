from __future__ import annotations

from pathlib import Path

from src.sdk.loop import get_current_agent_loop
from src.sdk.tool_index import (
    compute_source_hashes,
    save_source_hashes,
)
from src.sdk.tools import tool


def _scan_custom_tool_names(tools_dir: Path) -> set[str]:
    names: set[str] = set()
    if not tools_dir.exists():
        return names
    for entry in tools_dir.iterdir():
        if entry.is_dir() and (entry / "TOOL.md").exists():
            names.add(entry.name)
    return names


@tool
def tool_reload() -> str:
    """Reload and re-index all custom tools from disk. Use after creating, editing, or deleting a TOOL.md file.

    This applies to:
      - Custom tools (TOOL.md files in Tools/ directory)
      - MCP tools (.mcp.json changes)
      - Connector tools

    Native tools (built-in) are always available and don't need reloading.

    Returns:
        Summary of tools added, removed, or changed
    """
    loop = get_current_agent_loop()
    if loop is None or not hasattr(loop, "_tool_index") or loop._tool_index is None:
        return "No tool index available."

    from src.storage.paths import get_paths

    paths = get_paths(user_id=loop.user_id or "default_user", workspace_id=loop.workspace_id or "personal")
    user_tools_dir = paths.user_tools_dir()
    workspace_tools_dir = paths.workspace_tools_dir()
    mcp_config = paths.user_mcp_config()
    index_dir = user_tools_dir / ".index"
    hashes_path = index_dir / ".index_hashes.json"

    from src.sdk.tools_custom import get_custom_tools, is_core_tool

    prev_names = set(loop._tool_index.list_all_names())

    loop._tool_index.clear()
    all_custom = get_custom_tools(user_id=loop.user_id or "default_user", workspace_id=loop.workspace_id or "personal")
    for td in all_custom:
        if not is_core_tool(td.name):
            loop._tool_index.index_tool(td, tool_type="custom", namespace="custom", reconstruct={"command": td.description})

    current_hashes = compute_source_hashes(user_tools_dir, workspace_tools_dir, mcp_config)
    save_source_hashes(hashes_path, current_hashes)

    new_names = set(loop._tool_index.list_all_names())
    added = new_names - prev_names
    removed = prev_names - new_names

    if hasattr(loop, "_recently_used") and loop._recently_used:
        for name in removed:
            loop._recently_used.discard(name)
        if added:
            pass

    lines = []
    lines.append(f"Index rebuilt. {len(new_names)} custom tools indexed.")
    if added:
        lines.append(f"  Added: {', '.join(sorted(added))}")
    if removed:
        lines.append(f"  Removed: {', '.join(sorted(removed))}")
    if not added and not removed:
        lines.append("  No changes detected.")

    return "\n".join(lines)
