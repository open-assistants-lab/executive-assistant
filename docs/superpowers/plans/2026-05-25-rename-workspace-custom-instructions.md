# Rename Workspace `custom_instructions` → `prompt` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `custom_instructions` field on the `Workspace` model to `prompt` across the entire codebase.

**Architecture:** Pure refactor — renames a field on a `@dataclass`, its `to_dict()`/`from_dict()` serialization, all call sites in tools, HTTP router, runner, coordinator, and tests. No logic changes, no new features.

**Tech Stack:** Python 3.11+, Pydantic, FastAPI, pytest

**Depends on:** Nothing — independent change.

> ⚠️ **Peer review note:** Line numbers below are snapshots. If files have changed, use function names / `# Before`/`# After` blocks instead.

---

## File Structure

| File | Change |
|------|--------|
| `src/sdk/workspace_models.py` | Rename field + serialization keys |
| `src/sdk/tools_core/workspace.py` | Rename all `ws.custom_instructions` → `ws.prompt` |
| `src/http/routers/workspaces.py` | Rename `custom_instructions` → `prompt` in API response + request |
| `src/sdk/runner.py` | Rename `ws.custom_instructions` in `_get_workspace_context()` |
| `src/sdk/coordinator.py` | Rename `ws.custom_instructions` in `_build_system_prompt()` |
| `tests/sdk/test_workspaces.py` | Update all assertions from `custom_instructions` → `prompt` |

No new files. All modifications are mechanical renames.

---

### Task 1: Rename field in Workspace model

**Files:**
- Modify: `src/sdk/workspace_models.py:24,41,53`

- [ ] **Step 1: Write failing test**

```python
# tests/sdk/test_workspaces.py — in TestWorkspaceModel

def test_prompt_field(self):
    ws = Workspace(
        id="test", name="Test",
        prompt="Respond as a PM. Use AEST.",
    )
    assert ws.prompt == "Respond as a PM. Use AEST."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sdk/test_workspaces.py::TestWorkspaceModel::test_prompt_field -v`
Expected: AttributeError: "Workspace has no attribute 'prompt'"

- [ ] **Step 3: Rename field in dataclass**

In `src/sdk/workspace_models.py:24`:
```python
# Before
custom_instructions: str = ""
# After
prompt: str = ""
```

In `src/sdk/workspace_models.py:41` (`to_dict()`):
```python
# Before
"custom_instructions": self.custom_instructions,
# After
"prompt": self.prompt,
```

In `src/sdk/workspace_models.py:53` (`from_dict()`):
```python
# Before
custom_instructions=d.get("custom_instructions", ""),
# After
prompt=d.get("prompt", d.get("custom_instructions", "")),
#                                    ^^^^^^^^^^^^^^^^^^^^^^^^
#                                    backward compat for existing YAML files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sdk/test_workspaces.py::TestWorkspaceModel -v`
Expected: all tests pass

- [ ] **Step 5: Run existing workspace tests to see failures**

Run: `pytest tests/sdk/test_workspaces.py -v 2>&1 | grep FAILED`
Expected: ~6 failures — all the `custom_instructions` references in tests need updating

- [ ] **Step 6: Commit**

```bash
git add src/sdk/workspace_models.py
git commit -m "refactor(workspace): rename custom_instructions field to prompt"
```

---

### Task 2: Update workspace tools

**Files:**
- Modify: `src/sdk/tools_core/workspace.py`

- [ ] **Step 1: Rename all `custom_instructions` → `prompt` in workspace.py**

Six occurrences at lines 45, 75, 76, 77, 110, 111, 125:

```python
# Line 45
ws.prompt = instructions

# Lines 74-78
inst = (
    ws.prompt[:40] + "..."
    if len(ws.prompt) > 40
    else ws.prompt
)

# Lines 81-83
if inst:
    lines.append(f"    Instructions: {inst}")

# Lines 110-111
if ws.prompt:
    info += f"\nInstructions: {ws.prompt}"

# Line 125
f"Instructions: {ws.prompt or '(none)'}"
```

- [ ] **Step 2: Run workspace tools tests**

Run: `pytest tests/sdk/test_workspaces.py::TestWorkspaceTools -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/sdk/tools_core/workspace.py
git commit -m "refactor(workspace): rename custom_instructions to prompt in tools"
```

---

### Task 3: Update HTTP router

**Files:**
- Modify: `src/http/routers/workspaces.py`

- [ ] **Step 1: Rename in create endpoint**

```python
# Line 42 — get_workspaces response
"prompt": w.prompt,

# Line 54 — create_workspace
ws.prompt = req.instructions

# Line 80 — update_workspace
ws.prompt = req.instructions
```

- [ ] **Step 2: Rename the `instructions` field in request models to `prompt`**

The Pydantic models still call it `instructions` in the request. Rename to `prompt` with backward-compat alias so the Flutter client can migrate incrementally:

```python
# Lines 19-31
from pydantic import Field

class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
    prompt: str = Field("", alias="instructions")
    model_override: str | None = None

class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = Field(None, alias="instructions")
    model_override: str | None = None
```

> **Peer review note:** `Field(alias="instructions")` means old Flutter requests sending `instructions` still work. When Flutter is updated to send `prompt`, remove the alias.

- [ ] **Step 3: Update the references to `instructions` in the endpoint bodies**

```python
# Line 54 — create
ws.prompt = req.prompt

# Line 79-80 — update
if req.prompt is not None:
    ws.prompt = req.prompt
```

- [ ] **Step 4: Commit**

```bash
git add src/http/routers/workspaces.py
git commit -m "refactor(workspace): rename custom_instructions to prompt in HTTP API"
```

---

### Task 4: Update runner and coordinator

**Files:**
- Modify: `src/sdk/runner.py:97-98`
- Modify: `src/sdk/coordinator.py:131-132`

- [ ] **Step 1: Rename in runner.py**

```python
# Lines 97-98
if ws.prompt:
    lines.append(ws.prompt)
```

- [ ] **Step 2: Rename in coordinator.py**

```python
# Lines 131-132
if ws.prompt:
    parts.append(ws.prompt)
```

- [ ] **Step 3: Run full workspace test suite**

Run: `pytest tests/sdk/test_workspaces.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/sdk/runner.py src/sdk/coordinator.py
git commit -m "refactor(workspace): rename custom_instructions to prompt in runner and coordinator"
```

---

### Task 5: Update all workspace tests

**Files:**
- Modify: `tests/sdk/test_workspaces.py`

- [ ] **Step 1: Update every `custom_instructions` → `prompt` in test file**

All occurrences at lines 26, 33, 52, 59, 65, 81, 99.

```python
# Line 26
prompt="Respond as a PM. Use AEST.",
# Line 33
assert ws.prompt == "Respond as a PM. Use AEST."
# Line 52
prompt="ci",
# Line 59
assert d["prompt"] == "ci"
# Line 65
"prompt": "c",
# Line 81
prompt="ci",
# Line 99
prompt="c",
```

- [ ] **Step 2: Run all workspace tests**

Run: `pytest tests/sdk/test_workspaces.py -v`
Expected: all pass (26+ tests)

- [ ] **Step 3: Commit**

```bash
git add tests/sdk/test_workspaces.py
git commit -m "refactor(workspace): update tests for custom_instructions → prompt rename"
```

---

### Task 6: Rename in Workspaces proposal doc and other docs

**Files:**
- Modify: `docs/WORKSPACES_PROPOSAL.md`
- Modify: `docs/COMPANION_PROPOSAL.md`

- [ ] **Step 1: Find and replace in docs**

All occurrences of `custom_instructions` in these docs should become `prompt`.

- [ ] **Step 2: Commit**

```bash
git add docs/WORKSPACES_PROPOSAL.md docs/COMPANION_PROPOSAL.md
git commit -m "docs: update workspace docs for custom_instructions → prompt"
```

---
