"""Tools API — list tools with metadata, toggle enabled per scope."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.sdk.item_scopes import ItemScopeDB, ScopeKind
from src.sdk.native_tools import get_tool_category
from src.storage.paths import _validate_path_id, get_paths

router = APIRouter(prefix="/tools", tags=["tools"])


def _get_scope_db(user_id: str) -> ItemScopeDB:
    paths = get_paths(user_id)
    return ItemScopeDB(paths.base)


def _get_registry() -> list[Any]:
    """Get the full tool registry from native tools (lazy, cached)."""
    from src.sdk.native_tools import get_native_tools

    return get_native_tools()


def _resolve_scope(
    scope_db: ItemScopeDB,
    user_id: str,
    resource_name: str,
) -> tuple[ScopeKind, list[str]]:
    """Return (scope, workspace_ids) for a tool, falling back to 'all'."""
    row = scope_db.get(user_id, "tool", resource_name)
    if row:
        return row.scope, row.workspace_ids
    return "all", []


def _is_enabled(
    scope: ScopeKind,
    workspace_ids: list[str],
    workspace_id: str,
) -> bool:
    if scope == "all":
        return True
    if scope == "selected":
        return workspace_id in workspace_ids
    return False


@router.get("")
async def list_tools(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
) -> dict[str, Any]:
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    registry = _get_registry()
    scope_db = _get_scope_db(user_id)
    all_scoped = scope_db.get_all_scoped(user_id, "tool")

    tools_list = []
    categories_enabled: dict[str, dict[str, Any]] = {}

    for tool in registry:
        annotations = (
            tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
        )
        category = get_tool_category(tool.name)

        if tool.name in all_scoped:
            item_scope = all_scoped[tool.name]
            scope: ScopeKind = item_scope.scope
            workspace_ids = item_scope.workspace_ids
            enabled = _is_enabled(scope, workspace_ids, workspace_id)
        else:
            # Not configured yet — default to scope=all (available everywhere)
            scope = "all"
            workspace_ids = []
            enabled = True

        tools_list.append(
            {
                "name": tool.name,
                "description": tool.description,
                "category": category,
                "annotations": annotations,
                "parameters": tool.parameters,
                "enabled": enabled,
                "scope": scope,
                "workspace_ids": workspace_ids,
                "source": "native",
            }
        )

        if category not in categories_enabled:
            cat_tools = [t for t in registry if get_tool_category(t.name) == category]
            cat_enabled_count = sum(
                1 for t in cat_tools
                if next(
                    (ti["enabled"] for ti in tools_list if ti["name"] == t.name),
                    True,
                )
            )
            categories_enabled[category] = {
                "count": len(cat_tools),
                "enabled": cat_enabled_count,
            }

    return {"tools": tools_list, "categories": categories_enabled}


def _tool_default(annotations: dict[str, Any]) -> bool:
    """Derive default enabled state from tool annotations."""
    destructive = annotations.get("destructive", False)
    if destructive:
        return False
    return True


@router.get("/{name}")
async def get_tool(
    name: str,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
) -> dict[str, Any]:
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    registry = _get_registry()

    for tool in registry:
        if tool.name == name:
            annotations = (
                tool.annotations.model_dump()
                if hasattr(tool, "annotations")
                else {}
            )
            scope_db = _get_scope_db(user_id)
            scope, wids = _resolve_scope(scope_db, user_id, tool.name)
            enabled = _is_enabled(scope, wids, workspace_id)
            return {
                "name": tool.name,
                "description": tool.description,
                "category": get_tool_category(tool.name),
                "annotations": annotations,
                "parameters": tool.parameters,
                "enabled": enabled,
                "scope": scope,
                "workspace_ids": wids,
                "source": "native",
            }

    raise HTTPException(status_code=404, detail=f"Tool not found: {name}")


@router.patch("/{name}")
async def toggle_tool(
    name: str,
    body: dict[str, Any],
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
) -> dict[str, Any]:
    """Set a tool's scope.

    New body (preferred):
      {"scope": "all"|"selected"|"none", "workspace_ids": ["w1","w2"]}

    Old body (backward compat):
      {"enabled": true/false}
      → enabled=true converts to scope="selected" for current workspace
      → enabled=false converts to scope="selected" + remove current workspace
    """
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    registry = _get_registry()
    if not any(t.name == name for t in registry):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")

    scope_db = _get_scope_db(user_id)

    if "scope" in body:
        new_scope: ScopeKind = body["scope"]
        if new_scope not in ("all", "selected", "none"):
            raise HTTPException(
                status_code=400,
                detail="scope must be 'all', 'selected', or 'none'",
            )
        wids: list[str] = body.get("workspace_ids", [])
        scope_db.set(user_id, "tool", name, new_scope, wids)
        enabled = _is_enabled(new_scope, wids, workspace_id)
        from src.sdk.runner import reset_sdk_loop
        reset_sdk_loop(user_id, workspace_id)
        return {
            "name": name,
            "enabled": enabled,
            "scope": new_scope,
            "workspace_ids": wids,
        }

    if "enabled" in body:
        # Backward compat: old format
        enabled_val = body["enabled"]
        current = scope_db.get(user_id, "tool", name)
        if current and current.scope == "selected":
            wids = list(current.workspace_ids)
        else:
            wids = []
        if enabled_val:
            if workspace_id not in wids:
                wids.append(workspace_id)
        else:
            if workspace_id in wids:
                wids.remove(workspace_id)
        new_scope = "selected" if wids else "none"
        scope_db.set(user_id, "tool", name, new_scope, wids)
        from src.sdk.runner import reset_sdk_loop
        reset_sdk_loop(user_id, workspace_id)
        return {
            "name": name,
            "enabled": enabled_val,
            "scope": new_scope,
            "workspace_ids": wids,
        }

    raise HTTPException(
        status_code=400, detail="Missing 'scope' or 'enabled' field"
    )
