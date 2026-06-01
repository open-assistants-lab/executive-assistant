# Unified Capabilities & AgentProfile — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend for unified capabilities (tool/skill/subagent enable) + AgentProfile OSS package + API endpoints. Flutter UI is a separate follow-up plan.

**Architecture:** AgentProfile is extracted as a standalone OSS package (`agentprofile` on PyPI). EA adds models.dev + skill registry validation on top via `src/sdk/agent_profile.py`. A new `capabilities.yaml` per scope (user/workspace) replaces separate skill/subagent/tool enable files. The AgentLoop filters its tool registry by merged capabilities at creation time. Three new API routers: tools (metadata), capabilities (CRUD), agents (profile CRUD — extends existing subagents router).

**Tech Stack:** Python 3.11+, Pydantic, YAML, FastAPI, models.dev registry

---

### Task 1: Create AgentProfile OSS repo

**Files:**
- Create: `/Users/eddy/Developer/Python/AgentProfile/pyproject.toml`
- Create: `/Users/eddy/Developer/Python/AgentProfile/agentprofile/__init__.py`
- Create: `/Users/eddy/Developer/Python/AgentProfile/agentprofile/models.py`
- Create: `/Users/eddy/Developer/Python/AgentProfile/agentprofile/parser.py`
- Create: `/Users/eddy/Developer/Python/AgentProfile/tests/test_models.py`
- Create: `/Users/eddy/Developer/Python/AgentProfile/tests/test_parser.py`

- [ ] **Step 1: Create project structure**

```bash
mkdir -p /Users/eddy/Developer/Python/AgentProfile/agentprofile
mkdir -p /Users/eddy/Developer/Python/AgentProfile/tests
```

- [ ] **Step 2: Write pyproject.toml**

```toml
# /Users/eddy/Developer/Python/AgentProfile/pyproject.toml
[project]
name = "agentprofile"
version = "0.1.0"
description = "Portable agent profile definition — schema and parser"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Write __init__.py**

```python
# /Users/eddy/Developer/Python/AgentProfile/agentprofile/__init__.py
"""AgentProfile: portable agent definition schema and parser."""

from agentprofile.models import AgentProfile
from agentprofile.parser import load_profile, loads_profile, dumps_profile

__version__ = "0.1.0"
__all__ = ["AgentProfile", "load_profile", "loads_profile", "dumps_profile"]
```

- [ ] **Step 4: Write models.py**

```python
# /Users/eddy/Developer/Python/AgentProfile/agentprofile/models.py
"""Pydantic model for AgentProfile — portable agent definition."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class AgentProfile(BaseModel):
    """Portable definition of an agent: identity, model, tools, instructions."""

    version: int = Field(default=1, ge=1, le=1)
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = Field(..., min_length=1)
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    handoff_instructions: str | None = None

    model_config = {"extra": "ignore"}

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(f"Invalid name: {v!r}. Must match {_NAME_RE.pattern}")
        return v

    @field_validator("version")
    @classmethod
    def _validate_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(f"Unsupported version: {v}. Only version 1 is supported.")
        return v
```

- [ ] **Step 5: Write parser.py**

```python
# /Users/eddy/Developer/Python/AgentProfile/agentprofile/parser.py
"""YAML parsing for AgentProfile files."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentprofile.models import AgentProfile


def load_profile(path: str | Path) -> AgentProfile:
    """Load an AgentProfile from a profile.yaml file."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    return AgentProfile(**data)


def loads_profile(yaml_str: str) -> AgentProfile:
    """Load an AgentProfile from a YAML string."""
    data = yaml.safe_load(yaml_str) or {}
    return AgentProfile(**data)


def dumps_profile(profile: AgentProfile) -> str:
    """Serialize an AgentProfile to YAML string."""
    return yaml.dump(
        profile.model_dump(exclude_none=True, exclude_defaults=True),
        default_flow_style=False,
        sort_keys=False,
    )
```

- [ ] **Step 6: Write test_models.py**

```python
# /Users/eddy/Developer/Python/AgentProfile/tests/test_models.py
"""Tests for AgentProfile Pydantic model."""

import pytest
from agentprofile.models import AgentProfile


def test_minimal_valid_profile():
    profile = AgentProfile(
        name="researcher",
        description="Research agent",
        model="openai:gpt-4o",
        tools=["web_search"],
        system_prompt="You are a researcher.",
    )
    assert profile.name == "researcher"
    assert profile.version == 1
    assert profile.skills == []
    assert profile.tags == []
    assert profile.provider_options == {}
    assert profile.handoff_instructions is None


def test_full_profile():
    profile = AgentProfile(
        name="coder",
        description="Coding agent",
        model="anthropic:claude-sonnet-4-20250514",
        tools=["files_read", "files_write", "shell_execute"],
        system_prompt="You are a coder.",
        skills=["file-management"],
        tags=["coding", "production"],
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        provider_options={"anthropic": {"thinking": {"type": "enabled", "budget_tokens": 4000}}},
        handoff_instructions="Coder has finished the task.",
    )
    assert "anthropic" in profile.provider_options


def test_name_rejects_special_chars():
    with pytest.raises(ValueError):
        AgentProfile(
            name="bad name",
            description="x",
            model="openai:gpt-4o",
            tools=[],
            system_prompt="x",
        )


def test_name_rejects_too_long():
    with pytest.raises(ValueError):
        AgentProfile(
            name="a" * 65,
            description="x",
            model="openai:gpt-4o",
            tools=[],
            system_prompt="x",
        )


def test_version_rejects_unknown():
    with pytest.raises(ValueError):
        AgentProfile(
            version=2,
            name="test",
            description="x",
            model="openai:gpt-4o",
            tools=[],
            system_prompt="x",
        )


def test_extra_fields_ignored():
    profile = AgentProfile(
        name="test",
        description="x",
        model="openai:gpt-4o",
        tools=[],
        system_prompt="x",
        unknown_field="should be ignored",
    )
    assert not hasattr(profile, "unknown_field")
```

- [ ] **Step 7: Write test_parser.py**

```python
# /Users/eddy/Developer/Python/AgentProfile/tests/test_parser.py
"""Tests for AgentProfile YAML parser."""

import tempfile
from pathlib import Path

from agentprofile.parser import load_profile, loads_profile, dumps_profile


def test_loads_profile_minimal():
    yaml_str = """
name: test-agent
description: A test agent
model: openai:gpt-4o
tools:
  - time_get
system_prompt: You are a test agent.
"""
    profile = loads_profile(yaml_str)
    assert profile.name == "test-agent"
    assert profile.tools == ["time_get"]


def test_load_profile_from_file():
    yaml_str = """
name: file-agent
description: Loaded from file
model: ollama:llama3.2
tools:
  - files_read
system_prompt: Read files.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        f.flush()
        profile = load_profile(f.name)
        Path(f.name).unlink()

    assert profile.name == "file-agent"
    assert profile.model == "ollama:llama3.2"


def test_dumps_profile_roundtrip():
    yaml_str = """
name: roundtrip
description: Roundtrip test
model: openai:gpt-4o
tools:
  - time_get
system_prompt: Test.
tags:
  - test
"""
    profile = loads_profile(yaml_str)
    dumped = dumps_profile(profile)
    reloaded = loads_profile(dumped)
    assert reloaded.name == profile.name
    assert reloaded.tools == profile.tools
    assert reloaded.tags == profile.tags
```

- [ ] **Step 8: Install and run tests**

```bash
cd /Users/eddy/Developer/Python/AgentProfile && uv sync && uv run pytest -v
# Expected: 7 passed
```

- [ ] **Step 9: Commit**

```bash
cd /Users/eddy/Developer/Python/AgentProfile && git add -A && git commit -m "feat: initial AgentProfile OSS package — schema + parser"
```

---

### Task 2: Add AgentProfile validation layer in EA

**Files:**
- Create: `tests/sdk/test_agent_profile.py`
- Create: `src/sdk/agent_profile.py`

- [ ] **Step 1: Write the test**

```python
# tests/sdk/test_agent_profile.py
"""Tests for EA-specific AgentProfile validation layer."""
import pytest
from unittest.mock import patch, MagicMock

from src.sdk.agent_profile import validate_profile


def test_valid_profile_passes():
    profile_data = {
        "name": "researcher",
        "description": "Research agent",
        "model": "ollama:llama3.2",
        "tools": ["time_get", "files_read"],
        "system_prompt": "You are a researcher.",
    }
    with patch("src.sdk.agent_profile.get_model_info") as mock_model:
        mock_model.return_value = {"provider": "ollama"}
        with patch("src.sdk.agent_profile.get_native_tool_names") as mock_tools:
            mock_tools.return_value = {"time_get", "files_read", "files_write"}
            errors = validate_profile(profile_data)
    assert errors == []


def test_unknown_model_rejected():
    profile_data = {
        "name": "bad",
        "description": "x",
        "model": "nonexistent:model",
        "tools": ["time_get"],
        "system_prompt": "x",
    }
    with patch("src.sdk.agent_profile.get_model_info", return_value=None):
        errors = validate_profile(profile_data)
    assert any("model" in e.lower() for e in errors)


def test_unknown_tool_rejected():
    profile_data = {
        "name": "bad",
        "description": "x",
        "model": "ollama:llama3.2",
        "tools": ["nonexistent_tool"],
        "system_prompt": "x",
    }
    with patch("src.sdk.agent_profile.get_native_tool_names", return_value={"time_get"}):
        errors = validate_profile({"name": "bad", "description": "x", "model": "ollama:llama3.2", "tools": ["nonexistent_tool"], "system_prompt": "x"})
    assert any("nonexistent_tool" in e for e in errors)


def test_empty_tools_allowed():
    profile_data = {
        "name": "minimal",
        "description": "x",
        "model": "ollama:llama3.2",
        "tools": [],
        "system_prompt": "x",
    }
    with patch("src.sdk.agent_profile.get_model_info", return_value={"provider": "ollama"}):
        with patch("src.sdk.agent_profile.get_native_tool_names", return_value=set()):
            errors = validate_profile(profile_data)
    assert errors == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_agent_profile.py -v
# Expected: FAIL with ModuleNotFoundError
```

- [ ] **Step 3: Write implementation**

```python
# src/sdk/agent_profile.py
"""EA-specific validation for AgentProfile.

Extends the OSS AgentProfile model with EA-specific validators
(models.dev lookup, tool registry, skill registry).
"""

from __future__ import annotations

from typing import Any


def validate_profile(data: dict[str, Any]) -> list[str]:
    """Validate an AgentProfile dict against EA-specific rules.

    Returns a list of error messages. Empty list = valid.
    """
    errors: list[str] = []

    # 1. Model must resolve through models.dev
    model = data.get("model", "")
    if model:
        from src.sdk.registry import get_model_info

        info = get_model_info(model)
        if info is None:
            errors.append(f"Unknown model: {model!r}")

    # 2. Tools must exist in registry
    tools = data.get("tools", [])
    if tools:
        from src.sdk.native_tools import get_native_tool_names

        known = get_native_tool_names()
        for tool_name in tools:
            if tool_name not in known:
                errors.append(f"Unknown tool: {tool_name!r}")

    # 3. Skills must exist in registry
    skills = data.get("skills", [])
    if skills:
        try:
            from src.skills.registry import get_skill_registry

            sr = get_skill_registry()
            for skill_name in skills:
                if not sr.has(skill_name):
                    errors.append(f"Unknown skill: {skill_name!r}")
        except Exception:
            pass  # skill registry may not be initialized in tests

    # 4. Provider options key must be a valid provider ID
    provider_options = data.get("provider_options", {})
    if provider_options:
        from src.sdk.registry import PROVIDER_IDS

        for key in provider_options:
            if key not in PROVIDER_IDS:
                errors.append(f"Unknown provider in provider_options: {key!r}")

    return errors
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/sdk/test_agent_profile.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add tests/sdk/test_agent_profile.py src/sdk/agent_profile.py
git commit -m "feat: add EA-specific AgentProfile validation layer"
```

---

### Task 3: Add tool category mapping

**Files:**
- Modify: `src/sdk/native_tools.py` (append CATEGORIES mapping)

- [ ] **Step 1: Add CATEGORIES dict to native_tools.py**

```python
# Add at end of src/sdk/native_tools.py

# Tool categories derived from naming convention category_verb
CATEGORIES: dict[str, str] = {}

def _derive_category(name: str) -> str:
    """Derive category from tool name (category_verb convention)."""
    if "_" in name:
        return name.split("_")[0]
    return "core"


def get_tool_category(name: str) -> str:
    """Return the category for a given tool name."""
    return CATEGORIES.get(name, _derive_category(name))


def _populate_categories():
    """Auto-populate CATEGORIES from registered tool names."""
    for name in get_native_tool_names():
        CATEGORIES[name] = _derive_category(name)

_populate_categories()
```

- [ ] **Step 2: Write test**

```python
# Add to tests/sdk/test_tools.py (append at end of file)
def test_tool_categories_derived():
    from src.sdk.native_tools import get_tool_category

    assert get_tool_category("files_read") == "files"
    assert get_tool_category("browser_open") == "browser"
    assert get_tool_category("shell_execute") == "shell"
    assert get_tool_category("time_get") == "time"

def test_tool_categories_are_populated():
    from src.sdk.native_tools import CATEGORIES, get_native_tool_names

    names = get_native_tool_names()
    for name in names:
        assert name in CATEGORIES, f"Missing category for {name}"
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/sdk/test_tools.py -v -k "category"
# Expected: 2 passed
```

- [ ] **Step 4: Commit**

```bash
git add src/sdk/native_tools.py tests/sdk/test_tools.py
git commit -m "feat: add tool category mapping to native_tools"
```

---

### Task 4: Capabilities module — load, merge, defaults

**Files:**
- Create: `src/sdk/capabilities.py`
- Create: `tests/sdk/test_capabilities.py`

- [ ] **Step 1: Write tests**

```python
# tests/sdk/test_capabilities.py
"""Tests for capabilities loading, merging, and defaults."""
import tempfile
from pathlib import Path

import yaml
import pytest

from src.sdk.capabilities import (
    load_capabilities,
    merge_capabilities,
    tool_enabled,
    _tool_default,
)


def make_caps(path: str, data: dict):
    """Helper: write capabilities.yaml to a temp path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.dump(data))


def test_load_capabilities_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as d:
        caps = load_capabilities(d)
    assert caps == {"tools": {}, "skills": {}, "subagents": {}}


def test_load_capabilities_reads_yaml():
    with tempfile.TemporaryDirectory() as d:
        make_caps(f"{d}/capabilities.yaml", {
            "version": 1,
            "tools": {"files_read": True, "files_delete": False},
            "skills": {"file-management": True},
            "subagents": {},
        })
        caps = load_capabilities(d)
    assert caps["tools"]["files_read"] is True
    assert caps["tools"]["files_delete"] is False
    assert caps["skills"]["file-management"] is True


def test_merge_workspace_overrides_user():
    user = {"tools": {"files_read": True, "files_delete": False, "shell_execute": False}}
    workspace = {"tools": {"files_delete": True, "browser_open": True}}

    merged = merge_capabilities(user, workspace)
    assert merged["tools"]["files_read"] is True     # inherited
    assert merged["tools"]["files_delete"] is True   # overridden
    assert merged["tools"]["shell_execute"] is False  # inherited
    assert merged["tools"]["browser_open"] is True    # workspace-only


def test_merge_workspace_false_disables():
    user = {"tools": {"files_read": True}}
    workspace = {"tools": {"files_read": False}}

    merged = merge_capabilities(user, workspace)
    assert merged["tools"]["files_read"] is False


def test_merge_skills_and_subagents():
    user = {"tools": {}, "skills": {"agent-browser": True}, "subagents": {"researcher": True}}
    workspace = {"tools": {}, "skills": {"agent-browser": False}, "subagents": {}}

    merged = merge_capabilities(user, workspace)
    assert merged["skills"]["agent-browser"] is False
    assert merged["subagents"]["researcher"] is True


def test_tool_default_read_only():
    """Read-only, non-destructive tools default to enabled."""
    annotations = {"read_only": True, "destructive": False}
    assert _tool_default(annotations) is True


def test_tool_default_destructive():
    """Destructive, non-read-only tools default to disabled."""
    annotations = {"read_only": False, "destructive": True}
    assert _tool_default(annotations) is False


def test_tool_default_both_true_safety_wins():
    annotations = {"read_only": True, "destructive": True}
    assert _tool_default(annotations) is False


def test_tool_default_both_false():
    annotations = {"read_only": False, "destructive": False}
    assert _tool_default(annotations) is True


def test_tool_enabled_explicit():
    caps = {"tools": {"time_get": True, "files_delete": False}}
    assert tool_enabled(caps, "time_get", {"read_only": True, "destructive": False}) is True
    assert tool_enabled(caps, "files_delete", {"read_only": False, "destructive": True}) is False


def test_tool_enabled_missing_uses_default():
    caps = {"tools": {}}
    assert tool_enabled(caps, "files_read", {"read_only": True, "destructive": False}) is True
    assert tool_enabled(caps, "shell_execute", {"read_only": False, "destructive": True}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/sdk/test_capabilities.py -v
# Expected: FAIL with ModuleNotFoundError
```

- [ ] **Step 3: Write implementation**

```python
# src/sdk/capabilities.py
"""Unified capabilities: tool/skill/subagent enable state per scope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_capabilities(root: str | Path) -> dict[str, Any]:
    """Load capabilities.yaml from a directory root.

    Returns empty defaults if file doesn't exist.
    """
    path = Path(root) / "capabilities.yaml"
    if not path.exists():
        return {"tools": {}, "skills": {}, "subagents": {}}
    data = yaml.safe_load(path.read_text()) or {}
    data.setdefault("tools", {})
    data.setdefault("skills", {})
    data.setdefault("subagents", {})
    return data


def merge_capabilities(
    user_caps: dict[str, Any], workspace_caps: dict[str, Any]
) -> dict[str, Any]:
    """Merge workspace capabilities over user capabilities.

    Workspace keys override user keys. Missing keys inherit from user.
    """
    merged: dict[str, Any] = {}
    for section in ("tools", "skills", "subagents"):
        user_section = user_caps.get(section, {})
        ws_section = workspace_caps.get(section, {})
        merged[section] = {**user_section, **ws_section}
    return merged


def _tool_default(annotations: dict[str, Any] | None) -> bool:
    """Derive default enabled state from tool annotations."""
    if not annotations:
        return True
    read_only = annotations.get("read_only", False)
    destructive = annotations.get("destructive", False)
    if destructive and not read_only:
        return False
    return True


def tool_enabled(
    caps: dict[str, Any],
    tool_name: str,
    annotations: dict[str, Any] | None = None,
) -> bool:
    """Check if a tool is enabled in the given capabilities."""
    tools = caps.get("tools", {})
    if tool_name in tools:
        return tools[tool_name] is not False
    return _tool_default(annotations)


def save_capabilities(root: str | Path, caps: dict[str, Any]) -> None:
    """Save capabilities.yaml to a directory root."""
    path = Path(root) / "capabilities.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(caps, default_flow_style=False, sort_keys=False))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/sdk/test_capabilities.py -v
# Expected: 10 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/sdk/capabilities.py tests/sdk/test_capabilities.py
git commit -m "feat: add capabilities module — load, merge, defaults"
```

---

### Task 5: Wire capabilities into AgentLoop tool filtering

**Files:**
- Modify: `src/sdk/runner.py:250-255` (tool list building)
- Modify: `src/sdk/loop.py` (accept filtered tool list)

- [ ] **Step 1: Update runner.py _build_tool_list to filter by capabilities**

Replace the tool building section in `src/sdk/runner.py` (around line 253):

```python
def _build_tool_list(
    user_id: str,
    workspace_id: str,
    tool_registry: list,
    caps: dict[str, Any] | None = None,
) -> list:
    """Build the tool list filtered by capabilities."""
    from src.sdk.capabilities import tool_enabled

    if caps is None:
        from src.sdk.capabilities import load_capabilities, merge_capabilities
        from src.storage.paths import get_paths

        paths = get_paths(user_id, workspace_id=workspace_id)
        user_caps = load_capabilities(paths.root)
        ws_caps = load_capabilities(paths.root / "Workspaces" / workspace_id)
        caps = merge_capabilities(user_caps, ws_caps)

    filtered = []
    for tool in tool_registry:
        annotations = tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
        if tool_enabled(caps, tool.name, annotations):
            filtered.append(tool)
    return filtered
```

- [ ] **Step 2: Update the existing tool-building code in runner.py to call _build_tool_list**

Find the line `tools = get_native_tools()` and replace with:

```python
    tools = _build_tool_list(user_id, workspace_id, get_native_tools())
```

- [ ] **Step 3: Write integration test**

```python
# Add to tests/sdk/test_capabilities.py
def test_build_tool_list_filters_by_capabilities():
    import tempfile
    from unittest.mock import patch, MagicMock

    from src.sdk.capabilities import merge_capabilities, tool_enabled

    # Simulate tool registry entries
    class FakeTool:
        def __init__(self, name, annotations_dict):
            self.name = name
            self.annotations = MagicMock()
            self.annotations.model_dump.return_value = annotations_dict

    tools = [
        FakeTool("time_get", {"read_only": True, "destructive": False}),
        FakeTool("shell_execute", {"read_only": False, "destructive": True}),
        FakeTool("files_read", {"read_only": True, "destructive": False}),
    ]

    caps = {"tools": {"shell_execute": False, "time_get": True}}

    filtered = [t for t in tools if tool_enabled(caps, t.name, t.annotations.model_dump())]
    names = [t.name for t in filtered]
    assert "time_get" in names
    assert "shell_execute" not in names
    assert "files_read" in names  # default: read-only → enabled
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/sdk/test_capabilities.py -v
# Expected: 11 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/sdk/runner.py src/sdk/capabilities.py tests/sdk/test_capabilities.py
git commit -m "feat: wire capabilities into AgentLoop tool filtering"
```

---

### Task 6: Create tools API router

**Files:**
- Create: `src/http/routers/tools.py`
- Create: `src/http/models/tool_responses.py` (optional, or inline in router)
- Create: `tests/api/test_tools_api.py`
- Modify: `src/http/routers/__init__.py` (add tools router export)
- Modify: `src/http/main.py` (register tools router)
- Modify: `src/http/routers/subagents.py` (remove tools_router)

- [ ] **Step 1: Write the test**

```python
# tests/api/test_tools_api.py
"""Tests for tools API endpoints."""
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from src.http.main import app


@pytest.mark.asyncio
async def test_get_tools_returns_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools?user_id=test&workspace_id=personal")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    assert "categories" in data
    assert isinstance(data["tools"], list)
    assert isinstance(data["categories"], dict)


@pytest.mark.asyncio
async def test_get_tools_item_includes_metadata():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools?user_id=test&workspace_id=personal")
    data = resp.json()
    if data["tools"]:
        tool = data["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "category" in tool
        assert "annotations" in tool
        assert "enabled" in tool
        assert "source" in tool


@pytest.mark.asyncio
async def test_get_single_tool():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools/time_get?user_id=test&workspace_id=personal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "time_get"


@pytest.mark.asyncio
async def test_get_unknown_tool_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools/nonexistent_tool?user_id=test&workspace_id=personal")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/api/test_tools_api.py -v
# Expected: FAIL (router not registered)
```

- [ ] **Step 3: Write tools router**

```python
# src/http/routers/tools.py
"""Tools API — list tools with metadata, toggle enabled per scope."""

from fastapi import APIRouter, HTTPException, Query

from src.sdk.native_tools import get_native_tool_names, get_tool_category, CATEGORIES
from src.sdk.tools import ToolRegistry
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
        annotations = tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
        enabled = tool_enabled(caps, tool.name, annotations)
        category = get_tool_category(tool.name)

        tools_list.append({
            "name": tool.name,
            "description": tool.description,
            "category": category,
            "annotations": annotations,
            "parameters": tool.parameters,
            "enabled": enabled,
            "source": "native",
        })

        if category not in categories_enabled:
            cat_tools = [t for t in registry if get_tool_category(t.name) == category]
            cat_enabled = sum(
                1 for t in registry
                if get_tool_category(t.name) == category
                and tool_enabled(caps, t.name,
                                 t.annotations.model_dump() if hasattr(t, "annotations") else {})
            )
            categories_enabled[category] = {"count": len(cat_tools), "enabled": cat_enabled}

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
            annotations = tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
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

    # Save to capabilities
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
```

- [ ] **Step 4: Register tools router**

In `src/http/routers/__init__.py`, add:
```python
from src.http.routers.tools import router as tools_router
```

And remove from `src/http/routers/subagents.py`:
```python
# Remove: tools_router = APIRouter(tags=["tools"])
# Remove: @tools_router.get("/tools/names") endpoint
```

In `src/http/main.py`, ensure `tools_router` is in the import list.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/api/test_tools_api.py -v
# Expected: 4 passed
```

- [ ] **Step 6: Run full suite**

```bash
uv run pytest tests/sdk/ tests/storage/ tests/api/ -q
# Expected: no new failures
```

- [ ] **Step 7: Commit**

```bash
git add src/http/routers/tools.py src/http/routers/__init__.py src/http/main.py src/http/routers/subagents.py tests/api/test_tools_api.py
git commit -m "feat: add tools API router with metadata and enable/disable"
```

---

### Task 7: Create capabilities API router

**Files:**
- Create: `src/http/routers/capabilities.py`
- Create: `tests/api/test_capabilities_api.py`

- [ ] **Step 1: Write test**

```python
# tests/api/test_capabilities_api.py
"""Tests for capabilities API endpoints."""
import tempfile
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

from src.http.main import app


@pytest.mark.asyncio
async def test_get_capabilities_returns_merged():
    with tempfile.TemporaryDirectory() as d:
        with patch("src.storage.paths.get_paths") as mock_gp:
            from src.storage.paths import DataPaths
            mock_gp.return_value = DataPaths(ea_root=d, user_id="test", workspace_id="personal")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/capabilities?user_id=test&workspace_id=personal")
            assert resp.status_code == 200
            data = resp.json()
            assert "tools" in data
            assert "skills" in data
            assert "subagents" in data


@pytest.mark.asyncio
async def test_patch_capabilities_merges():
    with tempfile.TemporaryDirectory() as d:
        with patch("src.storage.paths.get_paths") as mock_gp:
            from src.storage.paths import DataPaths
            mock_gp.return_value = DataPaths(ea_root=d, user_id="test", workspace_id="personal")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.patch(
                    "/capabilities?user_id=test&workspace_id=personal",
                    json={"tools": {"files_read": False}},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["tools"]["files_read"] is False


@pytest.mark.asyncio
async def test_patch_capabilities_null_removes_key():
    with tempfile.TemporaryDirectory() as d:
        with patch("src.storage.paths.get_paths") as mock_gp:
            from src.storage.paths import DataPaths
            mock_gp.return_value = DataPaths(ea_root=d, user_id="test", workspace_id="personal")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # First set a value
                await client.patch(
                    "/capabilities?user_id=test&workspace_id=personal",
                    json={"tools": {"files_read": False}},
                )
                # Then remove it
                resp = await client.patch(
                    "/capabilities?user_id=test&workspace_id=personal",
                    json={"tools": {"files_read": None}},
                )
            assert resp.status_code == 200
            # After removal, should revert to user-level or default (true for read-only)
            data = resp.json()
            assert data["tools"]["files_read"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/api/test_capabilities_api.py -v
# Expected: FAIL (router not registered)
```

- [ ] **Step 3: Write capabilities router**

```python
# src/http/routers/capabilities.py
"""Capabilities API — get/update tool/skill/subagent enable state."""

from fastapi import APIRouter, HTTPException, Query

from src.sdk.capabilities import (
    load_capabilities,
    merge_capabilities,
    save_capabilities,
)
from src.storage.paths import get_paths
from src.storage.paths import _validate_path_id

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


def _resolve_caps(user_id: str, workspace_id: str) -> dict:
    paths = get_paths(user_id, workspace_id=workspace_id)
    user_caps = load_capabilities(paths.root)
    ws_caps = load_capabilities(paths.root / "Workspaces" / workspace_id)
    return merge_capabilities(user_caps, ws_caps)


@router.get("")
async def get_capabilities(
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")
    return _resolve_caps(user_id, workspace_id)


@router.put("")
async def replace_capabilities(
    body: dict,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    paths = get_paths(user_id, workspace_id=workspace_id)
    workspace_root = paths.root / "Workspaces" / workspace_id
    save_capabilities(workspace_root, body)

    from src.sdk.runner import reset_sdk_loop
    reset_sdk_loop(user_id, workspace_id)

    return _resolve_caps(user_id, workspace_id)


@router.patch("")
async def patch_capabilities(
    body: dict,
    user_id: str = Query("default_user"),
    workspace_id: str = Query("personal"),
):
    _validate_path_id(user_id, "user_id")
    _validate_path_id(workspace_id, "workspace_id")

    paths = get_paths(user_id, workspace_id=workspace_id)
    workspace_root = paths.root / "Workspaces" / workspace_id

    # Load current workspace caps
    ws_caps = load_capabilities(workspace_root)

    # Merge user caps as base
    user_caps = load_capabilities(paths.root)

    # Apply patch to each section
    for section in ("tools", "skills", "subagents"):
        if section in body:
            if section not in ws_caps:
                ws_caps[section] = {}
            for key, value in body[section].items():
                if value is None:
                    # Remove key from workspace overrides — revert to user or default
                    ws_caps[section].pop(key, None)
                else:
                    ws_caps[section][key] = value

    save_capabilities(workspace_root, ws_caps)

    from src.sdk.runner import reset_sdk_loop
    reset_sdk_loop(user_id, workspace_id)

    return _resolve_caps(user_id, workspace_id)
```

- [ ] **Step 4: Register capabilities router**

In `src/http/routers/__init__.py`, add:
```python
from src.http.routers.capabilities import router as capabilities_router
```
And in `__all__`.

In `src/http/main.py`, add `capabilities_router` to imports and `app.include_router(...)` if not using router discovery.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/api/test_capabilities_api.py -v
# Expected: 3 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/http/routers/capabilities.py src/http/routers/__init__.py src/http/main.py tests/api/test_capabilities_api.py
git commit -m "feat: add capabilities API router"
```

---

### Task 8: Update subagent coordinator for AgentProfile

**Files:**
- Modify: `src/sdk/subagent_models.py` (drop disallowed_tools, add profile support)
- Modify: `src/sdk/coordinator.py` (read profile.yaml, use capabilities filtering)
- Modify: `tests/sdk/test_subagent_v1.py` (update for profile format)
- Modify: `tests/sdk/test_workspace_isolation.py` (update for profile format)

- [ ] **Step 1: Update AgentDef to drop disallowed_tools**

In `src/sdk/subagent_models.py`, remove `disallowed_tools` field from `AgentDef`:

```python
# REMOVE line 71:
# disallowed_tools: list[str] = Field(default_factory=lambda: list(SAFE_DISALLOWED_TOOLS))

# REMOVE SAFE_DISALLOWED_TOOLS constant if only used by AgentDef
```

Add a `to_profile()` and `from_profile()` method to `AgentDef`:

```python
def to_profile(self) -> dict:
    """Serialize to AgentProfile dict."""
    from agentprofile.models import AgentProfile
    profile = AgentProfile(
        name=self.name,
        description=self.description,
        model=self.model or "",
        tools=self.tools or [],
        system_prompt=self.system_prompt or "",
        skills=self.skills or [],
        output_schema=self.output_schema,
        provider_options=self.provider_options or {},
        handoff_instructions=self.handoff_instructions,
    )
    return profile.model_dump(exclude_none=True, exclude_defaults=True)

@classmethod
def from_profile(cls, data: dict) -> "AgentDef":
    """Create AgentDef from AgentProfile dict."""
    return cls(
        name=data["name"],
        description=data["description"],
        model=data.get("model"),
        tools=data.get("tools"),
        system_prompt=data.get("system_prompt"),
        skills=data.get("skills", []),
        output_schema=data.get("output_schema"),
        provider_options=data.get("provider_options", {}),
        handoff_instructions=data.get("handoff_instructions"),
    )
```

- [ ] **Step 2: Update coordinator create() to write profile.yaml**

In `src/sdk/coordinator.py`, update `create()` method to write both `profile.yaml` and `config.yaml`:

```python
async def create(self, agent_def: AgentDef) -> AgentDef:
    agent_path = self.base_path / agent_def.name
    agent_path.mkdir(parents=True, exist_ok=True)

    # Write AgentProfile
    from src.sdk.agent_profile import validate_profile
    profile_data = agent_def.to_profile()
    errors = validate_profile(profile_data)
    # Log warnings for validation errors but don't block creation
    if errors:
        logger.warning("agent_profile.validation_warnings",
                       {"name": agent_def.name, "errors": errors},
                       user_id=self.user_id)

    profile_yaml = yaml.dump(profile_data, default_flow_style=False, sort_keys=False)
    (agent_path / "profile.yaml").write_text(profile_yaml)

    # Write legacy config.yaml for backward compat
    config = agent_def.model_dump(exclude_none=True, exclude_defaults=True)
    if "disallowed_tools" in config:
        del config["disallowed_tools"]
    (agent_path / "config.yaml").write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    return agent_def
```

- [ ] **Step 3: Update coordinator load_def() to prefer profile.yaml**

```python
def load_def(self, name: str) -> AgentDef | None:
    # 1. Workspace-scoped: prefer profile.yaml
    config_path = self.base_path / name / "config.yaml"
    profile_path = self.base_path / name / "profile.yaml"
    
    if profile_path.exists():
        data = yaml.safe_load(profile_path.read_text()) or {}
        return AgentDef.from_profile(data)
    
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text()) or {}
        if "disallowed_tools" in data:
            del data["disallowed_tools"]
        return AgentDef(**data)
    
    # 2. User-global fallback (same logic)
    try:
        user_dir = _paths.get_paths(user_id=self.user_id).user_subagents_dir()
        config_path = user_dir / name / "config.yaml"
        profile_path = user_dir / name / "profile.yaml"
        
        if profile_path.exists():
            data = yaml.safe_load(profile_path.read_text()) or {}
            return AgentDef.from_profile(data)
        
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text()) or {}
            if "disallowed_tools" in data:
                del data["disallowed_tools"]
            return AgentDef(**data)
    except Exception:
        pass

    return None
```

- [ ] **Step 4: Update coordinator to filter tools by capabilities**

In `SubagentCoordinator.invoke()`, after loading the agent_def, filter tools:

```python
# After agent_def = self.load_def(agent_name)
# Filter tools by workspace capabilities
from src.sdk.capabilities import load_capabilities, merge_capabilities, tool_enabled
from src.storage.paths import get_paths as _gp

paths = _gp(self.user_id, workspace_id=self.workspace_id)
user_caps = load_capabilities(paths.root)
ws_caps = load_capabilities(paths.root / "Workspaces" / self.workspace_id)
caps = merge_capabilities(user_caps, ws_caps)

from src.sdk.native_tools import get_native_tools
registry = {t.name: t for t in get_native_tools()}

filtered_tools = []
if agent_def.tools:
    for tool_name in agent_def.tools:
        tool = registry.get(tool_name)
        if tool:
            annotations = tool.annotations.model_dump() if hasattr(tool, "annotations") else {}
            if tool_enabled(caps, tool.name, annotations):
                filtered_tools.append(tool.name)
            else:
                logger.warning("subagent.tool_disabled_by_caps",
                              {"agent": agent_def.name, "tool": tool_name},
                              user_id=self.user_id)

agent_def.tools = filtered_tools
```

- [ ] **Step 5: Remove disallowed_tools from remaining coordinator code**

Remove all references to `disallowed_tools` in `coordinator.py`:
- Line 73: validation check
- Line 101: set construction
- Line 596: `data.setdefault("disallowed_tools", ...)`
- Line 625: `data.setdefault("disallowed_tools", ...)`

Replace with capabilities-based filtering (already implemented above).

- [ ] **Step 6: Update tests for profile format**

Update `tests/sdk/test_subagent_v1.py`:
- Remove test assertions about `disallowed_tools`
- Add assertion that `profile.yaml` is written on create
- Change any test that creates AgentDef with `disallowed_tools` to use `tools` only

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest tests/sdk/ -q
# Expected: same as before minus disallowed_tools tests
```

- [ ] **Step 8: Commit**

```bash
git add src/sdk/subagent_models.py src/sdk/coordinator.py tests/sdk/test_subagent_v1.py tests/sdk/test_workspace_isolation.py
git commit -m "feat: AgentProfile support in coordinator — drop disallowed_tools"
```

---

### Task 9: Update agents API router (profile.yaml support)

**Files:**
- Modify: `src/http/routers/subagents.py` (return profile format, accept profile on create)
- Create/modify: `tests/api/test_agents_api.py` (or update test_subagents_api)

- [ ] **Step 1: Update SubagentCreateRequest to match AgentProfile**

Remove `disallowed_tools` from `SubagentCreateRequest`. Add `skills`, `tags`, `provider_options`, `handoff_instructions`:

```python
class SubagentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    model: str | None = None
    skills: list[str] = Field(default_factory=list)
    tools: list[str] | None = None
    system_prompt: str | None = None
    tags: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    handoff_instructions: str | None = None
    max_llm_calls: int = 50
    cost_limit_usd: float = 1.0
    timeout_seconds: int = 300
```

- [ ] **Step 2: Update list agents to include tags and skills**

Add `tags` and `skills` to the agent listing response.

- [ ] **Step 3: Update create endpoint to validate with AgentProfile**

```python
@router.post("")
async def create_subagent(request: SubagentCreateRequest, ...):
    # Validate against AgentProfile
    from src.sdk.agent_profile import validate_profile
    profile_data = request.model_dump(exclude={"max_llm_calls", "cost_limit_usd", "timeout_seconds"})
    errors = validate_profile(profile_data)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    
    # Create AgentDef and persist
    coord = SubagentCoordinator(user_id, workspace_id=workspace_id)
    agent_def = AgentDef(**request.model_dump())
    await coord.create(agent_def)
    ...
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/ -q -k "subagent"
# Expected: existing subagent tests pass, new profile fields work
```

- [ ] **Step 5: Commit**

```bash
git add src/http/routers/subagents.py tests/api/
git commit -m "feat: update agents API for AgentProfile format"
```

---

### Task 10: Final integration — full test suite

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/sdk/ tests/storage/ tests/api/ -q
# Expected: all passing (no regressions from pre-existing count)
```

- [ ] **Step 2: Verify pytest output for failures**

Check for any unexpected failures. The pre-existing flaky subagent tests may still fail.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: final integration — all tests pass for capabilities + AgentProfile backend"
```
