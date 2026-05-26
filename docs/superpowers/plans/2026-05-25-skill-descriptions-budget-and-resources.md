# Skill: Description Budget + Resource Enumeration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two targeted improvements to the skill system: (1) cap total description characters in the system prompt at 1,536, dropping least-used skills when over budget; (2) when `skills_load()` returns content, enumerate supporting files in the skill directory and inject `SKILL_DIR` so relative paths work.

**Architecture:** The description budget is enforced in `runner.py:_get_skills_context()` by tracking load frequency via `registry._loaded_skills`. Resource enumeration happens in `skills_load()` tool by scanning the skill directory for non-SKILL.md files. `${SKILL_DIR}` is a string substitution performed at load time.

**Tech Stack:** Python 3.11+, pytest, `pathlib`

**Depends on:** Nothing — independent changes.

---

## File Structure

| File | Change |
|------|--------|
| `src/sdk/runner.py` | Cap description chars at 1,536 total in `_get_skills_context()`, drop least-used when over budget |
| `src/sdk/tools_core/skills.py` | Add resource enumeration + `${SKILL_DIR}` substitution in `skills_load()` |
| `src/skills/registry.py` | Add `get_load_count(skill_name)` for tracking usage frequency |
| `tests/sdk/test_skills_descriptions.py` | **Create** — tests for description budget |
| `tests/sdk/test_skill_resources.py` | **Create** — tests for resource enumeration |

---

### Task 1: Add load tracking to SkillRegistry

**Files:**
- Modify: `src/skills/registry.py`

Currently `_loaded_skills` is a `set[str]`. We need a `dict[str, int]` to track how many times each skill was loaded.

- [ ] **Step 1: Write failing test**

```python
# tests/sdk/test_skill_resources.py

from src.skills.registry import SkillRegistry


class TestSkillRegistryLoadTracking:
    def test_load_count_tracks_multiple_loads(self):
        # We'll test the registry directly with temp dirs
        import tempfile
        from pathlib import Path
        from src.skills.models import Skill

        with tempfile.TemporaryDirectory() as skills_dir:
            skill_path = Path(skills_dir) / "test-skill" / "SKILL.md"
            skill_path.parent.mkdir(parents=True)
            skill_path.write_text(
                "---\nname: test-skill\ndescription: A test skill\n---\n\nContent here."
            )

            registry = SkillRegistry(skills_dir=skills_dir)
            registry.mark_skill_loaded("test-skill")
            registry.mark_skill_loaded("test-skill")

            assert registry.get_load_count("test-skill") == 2
            assert registry.get_load_count("never-loaded") == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/sdk/test_skill_resources.py::TestSkillRegistryLoadTracking -v`
Expected: FAIL — "SkillRegistry has no attribute 'get_load_count'"

- [ ] **Step 3: Change `_loaded_skills` from set to dict**

In `src/skills/registry.py`:
```python
# Line 72 — change type
self._loaded_skills: dict[str, int] = {}
```

Update `mark_skill_loaded()`:
```python
def mark_skill_loaded(self, skill_name: str) -> None:
    """Track that a skill has been loaded into context (increment count)."""
    self._loaded_skills[skill_name] = self._loaded_skills.get(skill_name, 0) + 1
```

Update `get_loaded_skills()`:
```python
def get_loaded_skills(self) -> list[str]:
    """Get list of skills loaded in current session."""
    return list(self._loaded_skills.keys())
```

Add new method:
```python
def get_load_count(self, skill_name: str) -> int:
    """Get how many times a skill has been loaded (0 if never loaded)."""
    return self._loaded_skills.get(skill_name, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/sdk/test_skill_resources.py::TestSkillRegistryLoadTracking -v`
Expected: PASS

- [ ] **Step 5: Run existing registry tests**

Run: `pytest tests/sdk/test_registry.py -v`
Expected: all pass (existing tests use `get_loaded_skills()` which still returns `list[str]`)

- [ ] **Step 6: Commit**

```bash
git add src/skills/registry.py
git commit -m "feat(registry): track skill load count for description budget"
```

---

### Task 2: Cap description chars in system prompt

**Files:**
- Modify: `src/sdk/runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/sdk/test_skills_descriptions.py

from unittest.mock import patch, MagicMock
from src.sdk.runner import _get_skills_context


class TestSkillDescriptionBudget:
    SKILL_DESC_BUDGET = 1536

    def test_includes_all_skills_under_budget(self):
        """When total descriptions fit in budget, all are included."""
        skills = [
            {"name": "skill-a", "description": "Short desc A"},
            {"name": "skill-b", "description": "Short desc B"},
        ]
        with patch("src.skills.registry.get_skill_registry") as mock_reg:
            mock_reg.return_value.get_all_skills.return_value = skills
            mock_reg.return_value.get_loaded_skills.return_value = []
            mock_reg.return_value.get_load_count.return_value = 0
            result = _get_skills_context("test_user", "personal")
            assert "skill-a" in result
            assert "skill-b" in result

    def test_drops_least_loaded_when_over_budget(self):
        """When descriptions exceed budget, drop skills with lowest load count first."""
        skills = [
            {"name": "skill-a", "description": "A" * 1000},
            {"name": "skill-b", "description": "B" * 1000},
        ]
        with patch("src.skills.registry.get_skill_registry") as mock_reg:
            mock_reg.return_value.get_all_skills.return_value = skills
            mock_reg.return_value.get_loaded_skills.return_value = ["skill-a"]
            # skill-a has been loaded 5 times, skill-b never loaded
            def load_count(name):
                return 5 if name == "skill-a" else 0
            mock_reg.return_value.get_load_count.side_effect = load_count
            result = _get_skills_context("test_user", "personal")
            assert "skill-a" in result  # loaded more → kept
            assert "skill-b" not in result  # never loaded → dropped

    def test_all_dropped_returns_empty(self):
        """When no skills fit in the budget, return empty string."""
        skills = [
            {"name": "skill-a", "description": "A" * 2000},
            {"name": "skill-b", "description": "B" * 2000},
        ]
        with patch("src.skills.registry.get_skill_registry") as mock_reg:
            mock_reg.return_value.get_all_skills.return_value = skills
            mock_reg.return_value.get_loaded_skills.return_value = []
            mock_reg.return_value.get_load_count.return_value = 0
            result = _get_skills_context("test_user", "personal")
            assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sdk/test_skills_descriptions.py -v`
Expected: FAIL — the tests will pass with current behavior since descriptions aren't capped yet. We need to first update `_get_skills_context` so these tests pass.

Actually wait — the tests will actually fail because the current `_get_skills_context` includes ALL skills regardless of budget. So test 2 and 3 will fail. Good.

- [ ] **Step 3: Update `_get_skills_context()` with budget logic**

Replace the current `_get_skills_context()` in `src/sdk/runner.py`:

```python
SKILL_DESC_BUDGET = 1536


def _get_skills_context(user_id: str, workspace_id: str = "personal") -> str:
    """Build a concise skills reference for the system prompt.

    Description text is capped at SKILL_DESC_BUDGET characters total.
    When over budget, skills with the lowest load count are dropped first.
    """
    try:
        from src.skills.registry import get_skill_registry

        registry = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
        skills = registry.get_all_skills()
        if not skills:
            return ""

        visible_skills = [
            s
            for s in skills
            if str(s.get("metadata", {}).get("disable_model_invocation", "")).lower()
            not in ("true", "1", "yes")
        ]
        if not visible_skills:
            return ""

        # Sort by load count descending (most-used first), then alphabetically as tiebreaker
        def _sort_key(s: dict) -> tuple:
            name = s.get("name", "")
            count = registry.get_load_count(name)
            return (-count, name)

        visible_skills.sort(key=_sort_key)

        # Build entries up to the budget
        # Account for header overhead (~180 chars for section title + instruction line)
        header_overhead = len(
            "\n\n## Available Skills\n"
            "When a task matches a skill description below, call skills_load(name) "
            "first to get detailed instructions before proceeding. "
            "Do NOT call skills_list — descriptions are already here.\n"
        )
        entries: list[tuple[str, str]] = []
        total_chars = header_overhead  # count header towards budget
        for s in visible_skills:
            name = s.get("name", "")
            desc = s.get("description", "")
            entry = f"- **{name}**: {desc}"
            entry_len = len(entry) + 1  # +1 for trailing newline
            if total_chars + entry_len > SKILL_DESC_BUDGET:
                break  # drop this and all remaining skills
            entries.append((name, desc))
            total_chars += entry_len

        if not entries:
            return ""

        lines = ["\n\n## Available Skills"]
        lines.append(
            "When a task matches a skill description below, call skills_load(name) "
            "first to get detailed instructions before proceeding. "
            "Do NOT call skills_list — descriptions are already here."
        )
        lines.append("")
        for name, desc in entries:
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
    except Exception:
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sdk/test_skills_descriptions.py -v`
Expected: 3 PASS

- [ ] **Step 5: Run existing runner tests**

Run: `pytest tests/sdk/test_runner.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/sdk/runner.py tests/sdk/test_skills_descriptions.py
git commit -m "feat(skills): cap description budget at 1536 chars, drop least-used first"
```

---

### Task 3: Add resource enumeration + SKILL_DIR to skills_load()

**Files:**
- Modify: `src/sdk/tools_core/skills.py`

- [ ] **Step 1: Write failing test**

```python
# tests/sdk/test_skill_resources.py

import tempfile
from pathlib import Path
from unittest.mock import patch

from src.sdk.tools_core.skills import skills_load


class TestSkillResourceEnumeration:
    def test_skills_load_includes_resource_listing(self):
        """skills_load() enumerates supporting files in the skill directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: Test\n---\n\nDo the thing."
            )
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "run.sh").write_text("echo hello")
            (skill_dir / "references").mkdir()
            (skill_dir / "references" / "guide.md").write_text("# Guide")
            (skill_dir / "assets").mkdir()
            (skill_dir / "assets" / "template.json").write_text('{"key": "val"}')

            with patch("src.skills.registry.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "my-skill",
                    "content": "Do the thing.",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "my-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert "Do the thing." in result
                assert "Skill directory:" in result
                assert "scripts/run.sh" in result
                assert "references/guide.md" in result
                assert "assets/template.json" in result
                assert "SKILL_DIR" not in result  # raw placeholder removed

    def test_skills_load_substitutes_skill_dir_placeholder(self):
        """${SKILL_DIR} in skill content is replaced with the skill directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "sub-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sub-skill\ndescription: Test\n---\n\nRun ${SKILL_DIR}/scripts/build.sh"
            )
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "build.sh").write_text("echo built")

            with patch("src.skills.registry.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "sub-skill",
                    "content": "Run ${SKILL_DIR}/scripts/build.sh",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "sub-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert str(skill_dir) in result
                assert "${SKILL_DIR}" not in result  # should be substituted

    def test_skills_load_with_empty_skill_dir(self):
        """Skill with no supporting files doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "empty-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: empty-skill\ndescription: Test\n---\n\nJust content."
            )

            with patch("src.skills.registry.get_skill_registry") as mock_reg:
                mock_reg.return_value.get_skill.return_value = {
                    "name": "empty-skill",
                    "content": "Just content.",
                    "path": str(skill_dir),
                    "metadata": {"scope": "user"},
                }
                mock_reg.return_value._loaded_skills = {}
                mock_reg.return_value.mark_skill_loaded = lambda n: None

                result = skills_load.invoke({
                    "skill_name": "empty-skill",
                    "user_id": "test_user",
                    "workspace_id": "personal",
                })

                assert "Just content." in result
                assert "No supporting files" not in result  # section omitted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sdk/test_skill_resources.py::TestSkillResourceEnumeration -v`
Expected: FAIL — current `skills_load()` returns just `f"# {name} ...\n\n{content}"`, no resource listing

- [ ] **Step 3: Update `skills_load()` with resource enumeration**

Replace the body of `skills_load()` in `src/sdk/tools_core/skills.py` from line 168:

```python
    registry.mark_skill_loaded(skill_name)

    # Get skill directory for resource enumeration
    skill_path = skill.get("path")
    content = skill["content"]

    # Substitute ${SKILL_DIR} placeholder with actual path
    # Use regex to avoid matching ${OTHER_VAR} or accidental occurrences
    import re
    if skill_path:
        content = re.sub(r"\$\{SKILL_DIR\}", skill_path, content)

    parts = [f"# {skill['name']} [{_skill_scope(skill)}]\n\n{content}"]

    # Enumerate supporting files
    if skill_path:
        skill_dir = Path(skill_path)
        if skill_dir.is_dir():
            resources = []
            for item in sorted(skill_dir.rglob("*")):
                if item.is_file() and item.name != "SKILL.md":
                    rel = item.relative_to(skill_dir)
                    resources.append(str(rel))

            if resources:
                parts.append("\n---\n")
                parts.append(f"Skill directory: {skill_path}")
                parts.append("Supporting files:")
                for r in resources:
                    parts.append(f"  - {r}")
                parts.append(
                    "\nRelative paths in the content above resolve against the skill directory."
                )

    return "\n".join(parts)
```

Add import at the top of `src/sdk/tools_core/skills.py`:
```python
from pathlib import Path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sdk/test_skill_resources.py::TestSkillResourceEnumeration -v`
Expected: 3 PASS

- [ ] **Step 5: Run existing skills tool tests**

Run: `pytest tests/sdk/test_tools.py -v -k "skill" 2>&1 | tail -20`
Expected: all existing skill tests pass

- [ ] **Step 6: Commit**

```bash
git add src/sdk/tools_core/skills.py tests/sdk/test_skill_resources.py
git commit -m "feat(skills): enumerate supporting files and substitute SKILL_DIR in skills_load()"
```

---

### Task 4: Run full test suite

- [ ] **Step 1: Run all skills-related tests**

```bash
uv run pytest tests/ -k "skill" -v 2>&1 | tail -30
```
Expected: all pass

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/sdk/ -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 3: Commit any cleanup**

```bash
git commit -m "chore: fix test edge cases after skill description budget + resource enumeration"
```

---
