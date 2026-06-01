"""Tools API — list tools with metadata, toggle enabled per scope."""

from fastapi import APIRouter, HTTPException, Query

from src.sdk.native_tools import get_native_tool_names, get_tool_category
from src.sdk.capabilities import (
    load_capabilities,
    merge_capabilities,
    tool_enabled,
    save_capabilities,
)
from src.storage.paths import get_paths
from src.storage.paths import _validate_path_id

router = APIRouter(prefix="/tools", tags=["tools"])


def _get_registry() -> list:
    """Get the full tool registry from native tools (lazy, cached)."""
    from src.sdk.native_tools import get_native_tools

    return get_native_tools()


def _resolve_caps(user_id: str, workspace_id: str) -> dict:
    paths = get_paths(user_id, workspace_id=workspace_id)
    user_caps = load_capabilities(paths.root)
    ws_caps = load_capabilities(paths.root / "Workspaces" / workspace_id)
    return merge_capabilities(user_caps, ws_caps)


@router.get("")
async def list_tools(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    registry = _get_registry()
    caps = _resolve_caps(user_id, workspace_id)

    tools_list = []
    categories_enabled: dict[str, dict[str, int]] = {}

    for tool in registry:
        annotations = (
            tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
        )
        enabled = tool_enabled(caps, tool.name, annotations)
        category = get_tool_category(tool.name)

        tools_list.append(
            {
                "name": tool.name,
                "description": tool.description,
                "category": category,
                "annotations": annotations,
                "parameters": tool.parameters,
                "enabled": enabled,
                "source": "native",
            }
        )

        if category not in categories_enabled:
            cat_tools = [t for t in registry if get_tool_category(t.name) == category]
            cat_enabled = sum(
                1
                for t in cat_tools
                if tool_enabled(
                    caps,
                    t.name,
                    t.annotations.model_dump()
                    if hasattr(t, "annotations")
                    else {},
                )
            )
            categories_enabled[category] = {
                "count": len(cat_tools),
                "enabled": cat_enabled,
            }

    return {"tools": tools_list, "categories": categories_enabled}


@router.get("/{name}")
async def get_tool(
    name: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    registry = _get_registry()
    caps = _resolve_caps(user_id, workspace_id)

    for tool in registry:
        if tool.name == name:
            annotations = (
                tool.annotations.model_dump()
                if hasattr(tool, "annotations")
                else {}
            )
            return {
                "name": tool.name,
                "description": tool.description,
                "category": get_tool_category(tool.name),
                "annotations": annotations,
                "parameters": tool.parameters,
                "enabled": tool_enabled(caps, tool.name, annotations),
                "source": "native",
            }

    raise HTTPException(status_code=404, detail=f"Tool not found: {name}")


@router.patch("/{name}")
async def toggle_tool(
    name: str,
    body: dict,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    """Toggle a tool's enabled state for a scope.

    Body: {"enabled": true/false}
    """
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Missing 'enabled' field")

    # Verify tool exists
    registry = _get_registry()
    if not any(t.name == name for t in registry):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")

    # Save to workspace capabilities
    paths = get_paths(user_id, workspace_id=workspace_id)
    workspace_root = paths.root / "Workspaces" / workspace_id
    ws_caps = load_capabilities(workspace_root)

    if "tools" not in ws_caps:
        ws_caps["tools"] = {}
    ws_caps["tools"][name] = enabled

    save_capabilities(workspace_root, ws_caps)

    # Reset cached AgentLoop so next turn picks up changes
    from src.sdk.runner import reset_sdk_loop

    reset_sdk_loop(user_id, workspace_id)

    return {"name": name, "enabled": enabled, "scope": "workspace"}
