"""Skills API endpoints — user-level only, scoped via item_scopes."""

import shutil
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from connectkit.item_scopes import ItemScopeDB, ScopeKind
from src.storage.paths import get_paths
from src.skills.models import _is_valid_skill_name, parse_skill_file
from src.skills.registry import get_skill_registry
from src.storage.paths import DEFAULT_USER_ID, _validate_path_id

router = APIRouter(prefix="/skills", tags=["skills"])

SkillScope = str  # "all" | "selected" | "none" (from item_scopes)


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    content: str
    scope: str = "user"  # deprecated, always stored at user level


class SkillUpdateRequest(BaseModel):
    description: str | None = None
    content: str | None = None
    scope: str = "user"  # deprecated


class SkillSummary(BaseModel):
    name: str
    description: str
    scope: str = "all"
    workspace_id: str | None = None
    workspace_ids: list[str] = Field(default_factory=list)
    is_loaded: bool = False
    disable_model_invocation: bool = False


class SkillListResponse(BaseModel):
    skills: list[SkillSummary]


class SkillDetail(SkillSummary):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: str | None = None
    frontmatter: dict[str, Any] = Field(default_factory=dict)


def _validate_skill_name(name: str) -> None:
    if not _is_valid_skill_name(name):
        raise HTTPException(status_code=400, detail=f"Invalid skill name: {name!r}")


def _validate_workspace_id(workspace_id: str) -> None:
    try:
        _validate_path_id(workspace_id or "personal", "workspace_id")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _validate_user_id(user_id: str) -> None:
    try:
        _validate_path_id(user_id or DEFAULT_USER_ID, "user_id")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _reset_user_loops(user_id: str) -> None:
    from src.sdk.runner import reset_user_sdk_loops
    reset_user_sdk_loops(user_id)


def _skill_dir(user_id: str) -> Path:
    paths = get_paths(user_id)
    return paths.user_skills_dir()


def _skill_file_path(user_id: str, skill_name: str) -> Path:
    root = _skill_dir(user_id)
    skill_file = root / skill_name / "SKILL.md"
    root_r = root.resolve()
    file_r = skill_file.resolve()
    if not file_r.is_relative_to(root_r):
        raise HTTPException(status_code=400, detail=f"Invalid skill name: {skill_name!r}")
    return skill_file


def _format_skill_file(frontmatter: dict[str, Any], content: str) -> str:
    body = content.strip()
    yaml_frontmatter = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{yaml_frontmatter}\n---\n\n{body}\n"


def _new_frontmatter(name: str, description: str) -> dict[str, Any]:
    return {"name": name, "description": description}


def _parse_skill_document(skill_file: Path) -> tuple[dict[str, Any], str]:
    content = skill_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise HTTPException(status_code=400, detail="Skill file has invalid frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Skill file has invalid frontmatter")
    try:
        frontmatter = yaml.safe_load(parts[1].strip()) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail="Skill file has invalid frontmatter") from e
    if not isinstance(frontmatter, dict):
        raise HTTPException(status_code=400, detail="Skill file has invalid frontmatter")
    return frontmatter, parts[2].strip()


def _get_registry(user_id: str, workspace_id: str):
    try:
        return get_skill_registry(user_id=user_id, workspace_id=workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _to_summary(skill: dict[str, Any], loaded_names: set[str]) -> SkillSummary:
    metadata = skill.get("metadata", {})
    return SkillSummary(
        name=skill["name"],
        description=skill.get("description", ""),
        scope="all",
        is_loaded=skill["name"] in loaded_names,
        disable_model_invocation=metadata.get("disable_model_invocation", False) is True,
    )


def _to_detail(skill: dict[str, Any], loaded_names: set[str]) -> SkillDetail:
    summary = _to_summary(skill, loaded_names)
    frontmatter = {
        "name": skill["name"],
        "description": skill.get("description", ""),
        "metadata": skill.get("metadata", {}),
    }
    for field in ("license", "compatibility", "allowed_tools"):
        if field in skill:
            frontmatter[field] = skill[field]
    return SkillDetail(
        **summary.model_dump(),
        content=skill.get("content", ""),
        metadata=skill.get("metadata", {}),
        license=skill.get("license"),
        compatibility=skill.get("compatibility"),
        allowed_tools=skill.get("allowed_tools"),
        frontmatter=frontmatter,
    )


@router.get("", response_model=SkillListResponse)
async def list_skills(user_id: str = "default_user", workspace_id: str = "personal"):
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    registry = _get_registry(user_id, workspace_id)
    loaded_names = set(registry.get_loaded_skills())
    paths = get_paths(user_id)
    scope_db = ItemScopeDB(paths.base)
    all_scoped = scope_db.get_all_scoped(user_id, "skill")

    summaries = []
    for skill in registry.get_all_skills():
        name = skill["name"]
        summary = _to_summary(skill, loaded_names)
        if name in all_scoped:
            item = all_scoped[name]
            summary.scope = item.scope
            summary.workspace_ids = item.workspace_ids
        summaries.append(summary)

    return SkillListResponse(skills=summaries)


@router.get("/{skill_name}", response_model=SkillDetail)
async def get_skill(
    skill_name: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(skill_name)
    registry = _get_registry(user_id, workspace_id)
    skill = registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _to_detail(skill, set(registry.get_loaded_skills()))


@router.post("", response_model=SkillDetail)
async def create_skill(
    request: SkillCreateRequest,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(request.name)
    description = request.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description must not be empty")

    skill_file = _skill_file_path(user_id, request.name)
    if skill_file.exists():
        raise HTTPException(status_code=409, detail="Skill already exists")

    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        _format_skill_file(_new_frontmatter(request.name, description), request.content),
        encoding="utf-8",
    )
    _get_registry(user_id, workspace_id).reload()
    _reset_user_loops(user_id)

    skill = parse_skill_file(skill_file)
    if not skill:
        raise HTTPException(status_code=500, detail="Skill could not be loaded")
    return _to_detail(skill, set(_get_registry(user_id, workspace_id).get_loaded_skills()))


@router.put("/{skill_name}", response_model=SkillDetail)
async def update_skill(
    skill_name: str,
    request: SkillUpdateRequest,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(skill_name)

    skill_file = _skill_file_path(user_id, skill_name)
    if not skill_file.exists():
        raise HTTPException(status_code=404, detail="Skill not found")

    frontmatter, current_content = _parse_skill_document(skill_file)
    frontmatter["name"] = skill_name
    if request.description is not None:
        d = request.description.strip()
        if not d:
            raise HTTPException(status_code=400, detail="Description must not be empty")
        frontmatter["description"] = d
    content = request.content if request.content is not None else current_content
    skill_file.write_text(_format_skill_file(frontmatter, content), encoding="utf-8")
    _get_registry(user_id, workspace_id).reload()
    _reset_user_loops(user_id)

    skill = parse_skill_file(skill_file)
    if not skill:
        raise HTTPException(status_code=500, detail="Skill could not be loaded")
    return _to_detail(skill, set(_get_registry(user_id, workspace_id).get_loaded_skills()))


@router.delete("/{skill_name}")
async def delete_skill(
    skill_name: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(skill_name)

    skill_file = _skill_file_path(user_id, skill_name)
    skill_dir = skill_file.parent
    if not skill_file.exists() or not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    shutil.rmtree(skill_dir)
    _get_registry(user_id, workspace_id).reload()
    _reset_user_loops(user_id)
    return {"status": "deleted", "name": skill_name}


@router.patch("/{skill_name}/scope")
async def set_skill_scope(
    skill_name: str,
    body: dict,
    user_id: str = "default_user",
):
    _validate_user_id(user_id)
    _validate_skill_name(skill_name)
    scope: ScopeKind = body.get("scope", "all")
    if scope not in ("all", "selected", "none"):
        raise HTTPException(status_code=400, detail="scope must be all, selected, or none")
    wids = body.get("workspace_ids", [])
    paths = get_paths(user_id)
    scope_db = ItemScopeDB(paths.base)
    scope_db.set(user_id, "skill", skill_name, scope, wids)
    return {"name": skill_name, "scope": scope, "workspace_ids": wids}
