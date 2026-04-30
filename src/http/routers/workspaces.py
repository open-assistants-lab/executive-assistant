"""Workspace management API for Flutter client."""
from fastapi import APIRouter
from pydantic import BaseModel

from src.sdk.workspace_models import (
    Workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
    delete_workspace as _delete_ws,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""


@router.get("")
async def get_workspaces(user_id: str = "default_user"):
    workspaces = list_workspaces()
    return {
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "custom_instructions": w.custom_instructions,
            }
            for w in workspaces
        ]
    }


@router.post("")
async def create_workspace(req: CreateWorkspaceRequest):
    ws = Workspace.from_name(req.name)
    ws.description = req.description
    ws.custom_instructions = req.instructions

    from src.storage.paths import DataPaths
    dp = DataPaths(workspace_id=ws.id)
    dp.workspace_files_dir()
    dp.workspace_memory_dir()
    dp.workspace_subagents_dir()

    save_workspace(ws)
    return {"id": ws.id, "name": ws.name}


@router.delete("/{workspace_id}")
async def delete_workspace_endpoint(workspace_id: str):
    ws = load_workspace(workspace_id)
    if ws is None or ws.id == "personal":
        return {"error": "Cannot delete"}, 400
    _delete_ws(ws.id)
    return {"status": "deleted"}
