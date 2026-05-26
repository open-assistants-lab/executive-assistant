"""Skills API endpoints."""

import shutil
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.skills.models import _is_valid_skill_name, parse_skill_file
from src.skills.registry import get_skill_registry
from src.storage.paths import DEFAULT_USER_ID, _validate_path_id, get_paths

router = APIRouter(prefix="/skills", tags=["skills"])

SkillScope = Literal["user", "workspace"]


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    content: str
    scope: str = "user"


class SkillUpdateRequest(BaseModel):
    description: str | None = None
    content: str | None = None
    scope: str = "user"


class SkillSummary(BaseModel):
    name: str
    description: str
    scope: SkillScope
    workspace_id: str | None = None
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


def _reset_sdk_loop(user_id: str, workspace_id: str) -> None:
    from src.sdk.runner import reset_sdk_loop

    reset_sdk_loop(user_id, workspace_id)


def _reset_sdk_loops_for_scope(user_id: str, workspace_id: str, scope: SkillScope) -> None:
    if scope == "user":
        from src.sdk.runner import reset_user_sdk_loops

        reset_user_sdk_loops(user_id)
    else:
        _reset_sdk_loop(user_id, workspace_id)


def _validate_scope(scope: str) -> SkillScope:
    if scope not in ("user", "workspace"):
        raise HTTPException(status_code=400, detail="Invalid scope")
    return scope  # type: ignore[return-value]


def _validate_description(description: str) -> str:
    stripped = description.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="Description must not be empty")
    return stripped


def _disable_model_invocation(metadata: dict[str, Any]) -> bool:
    value = metadata.get("disable_model_invocation", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def _skill_scope(skill: dict[str, Any]) -> SkillScope:
    return _validate_scope(skill.get("metadata", {}).get("scope", "user"))


def _skill_workspace_id(skill: dict[str, Any]) -> str | None:
    workspace_id = skill.get("metadata", {}).get("workspace_id")
    return workspace_id or None


def _to_summary(skill: dict[str, Any], loaded_names: set[str]) -> SkillSummary:
    metadata = skill.get("metadata", {})
    return SkillSummary(
        name=skill["name"],
        description=skill.get("description", ""),
        scope=_skill_scope(skill),
        workspace_id=_skill_workspace_id(skill),
        is_loaded=skill["name"] in loaded_names,
        disable_model_invocation=_disable_model_invocation(metadata),
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


def _get_registry(user_id: str, workspace_id: str):
    try:
        return get_skill_registry(user_id=user_id, workspace_id=workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _target_root(user_id: str, workspace_id: str, scope: SkillScope) -> Path:
    try:
        paths = get_paths(user_id, workspace_id=workspace_id)
        return paths.workspace_skills_dir() if scope == "workspace" else paths.skills_dir()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _skill_file(user_id: str, workspace_id: str, scope: SkillScope, skill_name: str) -> Path:
    root = _target_root(user_id, workspace_id, scope)
    skill_dir = root / skill_name
    skill_file = skill_dir / "SKILL.md"

    root_resolved = root.resolve()
    file_resolved = skill_file.resolve()
    if not file_resolved.is_relative_to(root_resolved):
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


def _load_scoped_skill(skill_file: Path, scope: SkillScope, workspace_id: str) -> dict[str, Any]:
    skill = parse_skill_file(skill_file)
    if not skill:
        raise HTTPException(status_code=500, detail="Skill could not be loaded")
    metadata = skill.setdefault("metadata", {})
    metadata["scope"] = scope
    metadata["workspace_id"] = workspace_id if scope == "workspace" else ""
    return skill


@router.get("", response_model=SkillListResponse)
async def list_skills(user_id: str = "default_user", workspace_id: str = "personal"):
    """List merged user and workspace skills."""
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    registry = _get_registry(user_id, workspace_id)
    loaded_names = set(registry.get_loaded_skills())
    return SkillListResponse(
        skills=[_to_summary(skill, loaded_names) for skill in registry.get_all_skills()]
    )


@router.get("/{skill_name}", response_model=SkillDetail)
async def get_skill(
    skill_name: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Return full skill detail."""
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
    """Create a skill in user or workspace scope."""
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(request.name)
    description = _validate_description(request.description)
    scope = _validate_scope(request.scope)
    registry = _get_registry(user_id, workspace_id)
    skill_file = _skill_file(user_id, workspace_id, scope, request.name)
    if skill_file.exists():
        raise HTTPException(status_code=409, detail="Skill already exists")

    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        _format_skill_file(_new_frontmatter(request.name, description), request.content),
        encoding="utf-8",
    )
    registry.reload()
    _reset_sdk_loops_for_scope(user_id, workspace_id, scope)

    skill = _load_scoped_skill(skill_file, scope, workspace_id)
    return _to_detail(skill, set(registry.get_loaded_skills()))


@router.put("/{skill_name}", response_model=SkillDetail)
async def update_skill(
    skill_name: str,
    request: SkillUpdateRequest,
    user_id: str = "default_user",
    workspace_id: str = "personal",
):
    """Update a skill by replacing its generated SKILL.md content."""
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(skill_name)
    description = (
        _validate_description(request.description)
        if request.description is not None
        else None
    )
    scope = _validate_scope(request.scope)
    registry = _get_registry(user_id, workspace_id)
    skill_file = _skill_file(user_id, workspace_id, scope, skill_name)
    if not skill_file.exists():
        raise HTTPException(status_code=404, detail="Skill not found")

    frontmatter, current_content = _parse_skill_document(skill_file)
    frontmatter["name"] = skill_name
    if description is not None:
        frontmatter["description"] = description
    content = request.content if request.content is not None else current_content
    skill_file.write_text(_format_skill_file(frontmatter, content), encoding="utf-8")
    registry.reload()
    _reset_sdk_loops_for_scope(user_id, workspace_id, scope)

    updated = _load_scoped_skill(skill_file, scope, workspace_id)
    return _to_detail(updated, set(registry.get_loaded_skills()))


@router.delete("/{skill_name}")
async def delete_skill(
    skill_name: str,
    user_id: str = "default_user",
    workspace_id: str = "personal",
    scope: str = Query(default="user"),
):
    """Delete a skill from the requested scope."""
    _validate_user_id(user_id)
    _validate_workspace_id(workspace_id)
    _validate_skill_name(skill_name)
    valid_scope = _validate_scope(scope)
    registry = _get_registry(user_id, workspace_id)
    skill_file = _skill_file(user_id, workspace_id, valid_scope, skill_name)
    skill_dir = skill_file.parent
    if not skill_file.exists() or not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    shutil.rmtree(skill_dir)
    registry.reload()
    _reset_sdk_loops_for_scope(user_id, workspace_id, valid_scope)
    return {"status": "deleted", "name": skill_name, "scope": valid_scope}
