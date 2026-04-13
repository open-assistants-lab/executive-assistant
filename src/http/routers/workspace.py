import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["workspace"])


@router.get("/workspace/read/{path:path}")
async def read_workspace_file(path: str, user_id: str = "default"):
    """Read file - auto-mark as downloaded."""
    from src.tools.file_cache import get_file_cache
    from src.tools.filesystem import files_read

    result = files_read.invoke({"path": path, "user_id": user_id})

    file_cache = get_file_cache(user_id)
    workspace_path = Path(f"data/users/{user_id}/workspace/{path}")
    server_modified = str(workspace_path.stat().st_mtime) if workspace_path.exists() else ""

    file_cache.update_sync(path, server_modified)

    return {"response": str(result), "path": path}


@router.get("/workspace/{path:path}")
async def list_workspace_files(path: str = "", user_id: str = "default"):
    """List files in workspace."""
    from src.tools.filesystem import files_list

    result = files_list.invoke({"path": path, "user_id": user_id})
    return {"response": str(result)}


@router.post("/workspace/{path:path}")
async def write_workspace_file(
    path: str,
    user_id: str = "default",
    request: dict | None = None,
):
    """Write file to workspace."""
    if request is None:
        return {"error": "content is required"}

    content = request.get("content", "")

    from src.tools.filesystem import files_write

    result = files_write.invoke({"path": path, "content": content, "user_id": user_id})
    return {"response": str(result)}


@router.delete("/workspace/{path:path}")
async def delete_workspace_file(path: str, user_id: str = "default"):
    """Delete file from workspace."""
    from src.tools.filesystem import files_delete

    result = files_delete.invoke({"path": path, "user_id": user_id})
    return {"response": str(result)}


@router.get("/sync/status")
async def get_sync_status(user_id: str = "default"):
    """Get sync status for all files."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    return {"status": cache.get_all()}


@router.post("/sync/pin/{path:path}")
async def pin_file(path: str, user_id: str = "default"):
    """Pin a file (keep downloaded)."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_pinned(path)
    return {"status": "pinned", "path": path}


@router.delete("/sync/pin/{path:path}")
async def unpin_file(path: str, user_id: str = "default"):
    """Unpin a file (remove from keep downloaded)."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_cloud_only(path)
    return {"status": "cloud_only", "path": path}


@router.post("/sync/download/{path:path}")
async def mark_downloaded(path: str, user_id: str = "default"):
    """Mark a file as downloaded."""
    from src.tools.file_cache import get_file_cache

    cache = get_file_cache(user_id)
    cache.mark_downloaded(path)
    return {"status": "downloaded", "path": path}


@router.get("/sync/stream")
async def sync_stream(user_id: str = "default"):
    """SSE stream for real-time file change notifications."""

    async def event_generator():
        workspace_path = Path(f"data/users/{user_id}/workspace")

        skills_path = Path(f"data/users/{user_id}/skills")
        subagents_path = Path(f"data/users/{user_id}/subagents")

        last_state = {
            "workspace": {},
            "skills": {},
            "subagents": {},
        }

        while True:
            try:
                current_state = {
                    "workspace": {},
                    "skills": {},
                    "subagents": {},
                }

                if workspace_path.exists():
                    for f in workspace_path.rglob("*"):
                        if f.is_file():
                            rel_path = str(f.relative_to(workspace_path))
                            mtime = str(f.stat().st_mtime)
                            current_state["workspace"][rel_path] = mtime

                if skills_path.exists():
                    for f in skills_path.glob("*/SKILL.md"):
                        skill_name = f.parent.name
                        current_state["skills"][skill_name] = str(f.stat().st_mtime)

                if subagents_path.exists():
                    for f in subagents_path.glob("*/config.yaml"):
                        agent_name = f.parent.name
                        current_state["subagents"][agent_name] = str(f.stat().st_mtime)

                for category in ["workspace", "skills", "subagents"]:
                    new_items = set(current_state[category].keys()) - set(
                        last_state[category].keys()
                    )
                    changed_items = []

                    for path_item, mtime in current_state[category].items():
                        if path_item not in last_state[category]:
                            changed_items.append(path_item)
                        elif last_state[category][path_item] != mtime:
                            changed_items.append(path_item)

                    if changed_items or new_items:
                        all_changed = list(set(changed_items) | set(new_items))
                        for item in all_changed:
                            data = {
                                "type": f"{category}_changed",
                                "category": category,
                                "path": item,
                                "action": "created" if item in new_items else "modified",
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                            yield f"data: {json.dumps(data)}\n\n"

                last_state = current_state
                await asyncio.sleep(3)

            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
