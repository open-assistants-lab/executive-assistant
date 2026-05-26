# Autoresearch System Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a system skill for iterative optimization of prompts, skills, and subagent configs using the autoresearch loop pattern (branch → modify → eval → keep/discard).

**Architecture:** A `ResearchLoop` protocol class in `src/sdk/research.py` that implements the generic keep/discard branch+eval loop. Concrete `ResearchTarget` implementations for prompt, skill, and subagent. Tools (`research_start`, `research_results`, `research_abort`) expose the loop to the agent. A seed skill (`src/skills_seed/autoresearch/`) provides agent-facing instructions. The `skill_eval` concept from the skills redesign spec is replaced by this — autoresearch covers iterative skill optimization.

**Tech Stack:** Python 3.11+, git, pytest, subagent system, existing `AgentLoop`

**Depends on:** Plans 1-3 (renaming, user prompt, skill description budget) — independent, but consumes their interfaces.

---

## File Structure

| File | Change |
|------|--------|
| `src/sdk/research.py` | **Create** — `ResearchLoop`, `ResearchTarget` protocol, `PromptTarget`, `SkillTarget`, `SubagentTarget` |
| `src/sdk/tools_core/research.py` | **Create** — `research_start()`, `research_results()`, `research_abort()` tools |
| `src/sdk/native_tools.py` | Wire in new research tools |
| `src/skills_seed/autoresearch/SKILL.md` | **Create** — seed skill with instructions for running research experiments |
| `src/skills_seed/autoresearch/program.md` | **Create** — baseline research program file (like autoresearch's `program.md`) |
| `tests/sdk/test_research.py` | **Create** — tests for ResearchLoop and targets |
| `tests/sdk/test_research_tools.py` | **Create** — tests for research tools |

---

### Task 1: Create ResearchTarget protocol and ResearchLoop

**Files:**
- Create: `src/sdk/research.py`

- [ ] **Step 1: Write failing test for ResearchTarget protocol**

```python
# tests/sdk/test_research.py

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from unittest.mock import AsyncMagicMock

from src.sdk.research import (
    ResearchTarget,
    ResearchLoop,
    ExperimentResult,
    PromptTarget,
    SkillTarget,
    SubagentTarget,
)


class TestExperimentResult:
    def test_creation(self):
        r = ExperimentResult(
            target_name="test",
            metric_value=0.95,
            metric_name="accuracy",
            improved=True,
            commit_hash="abc1234",
            description="Increased temperature to 0.8",
        )
        assert r.improved is True
        assert r.metric_value == 0.95


class TestResearchTarget:
    def test_protocol_has_required_methods(self):
        """Protocol check — any class with get/set/eval/rollback is a ResearchTarget."""
        assert hasattr(ResearchTarget, "get_current")
        assert hasattr(ResearchTarget, "apply_change")
        assert hasattr(ResearchTarget, "evaluate")
        assert hasattr(ResearchTarget, "rollback")

    def test_prompt_target(self):
        """PromptTarget reads/writes from a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "prompt.txt"
            prompt_file.write_text("You are a helpful assistant.")

            target = PromptTarget(prompt_file)
            current = target.get_current()
            assert "helpful assistant" in current

            target.apply_change("You are a pirate.")
            assert prompt_file.read_text() == "You are a pirate."

            target.rollback()
            assert "helpful assistant" in prompt_file.read_text()


class TestResearchLoop:
    @pytest.mark.asyncio
    async def test_run_experiment_keep_on_improvement(self):
        """When evaluate() returns a better metric, the change is kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "prompt.txt"
            prompt_file.write_text("baseline prompt")

            target = AsyncMagicMock(spec=ResearchTarget)
            target.get_current.return_value = "baseline"
            target.evaluate.side_effect = [0.8, 0.9]  # baseline, then improved

            loop = ResearchLoop(target=target, experiment_dir=Path(tmpdir))
            result = await loop.run_experiment("Increase specificity")

            assert result.improved is True
            assert result.metric_value == 0.9
            target.apply_change.assert_called_once()
            # rollback should NOT have been called (improvement was kept)
            target.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_experiment_discard_on_regression(self):
        """When evaluate() returns a worse metric, the change is discarded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = AsyncMagicMock(spec=ResearchTarget)
            target.get_current.return_value = "baseline"
            target.evaluate.side_effect = [0.8, 0.7]  # baseline, then worse

            loop = ResearchLoop(target=target, experiment_dir=Path(tmpdir))
            result = await loop.run_experiment("Made it worse")

            assert result.improved is False
            assert result.metric_value == 0.7
            target.apply_change.assert_called_once()
            target.rollback.assert_called_once()  # reverted

    @pytest.mark.asyncio
    async def test_run_experiment_logs_to_tsv(self):
        """Results are logged to results.tsv in the experiment directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = AsyncMagicMock(spec=ResearchTarget)
            target.get_current.return_value = "baseline"
            target.evaluate.side_effect = [0.8, 0.85]

            loop = ResearchLoop(target=target, experiment_dir=Path(tmpdir))
            await loop.run_experiment("Small improvement")

            tsv_path = Path(tmpdir) / "results.tsv"
            assert tsv_path.exists()
            content = tsv_path.read_text()
            assert "val_metric" in content  # header
            assert "Small improvement" in content  # description
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sdk/test_research.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create research.py**

`src/sdk/research.py`:
```python
"""Autoresearch loop — iterative experiment infrastructure.

Follows the karpathy/autoresearch pattern:
1. Branch or snapshot current state
2. Apply a change
3. Evaluate with a fixed budget
4. If improved → keep; if worse → rollback
5. Log to results TSV
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class ExperimentResult:
    """Result of a single experiment in the research loop."""

    target_name: str
    metric_value: float
    metric_name: str = "val_metric"
    improved: bool = False
    commit_hash: str = ""
    description: str = ""
    memory_gb: float = 0.0
    status: str = "unknown"  # keep, discard, crash


class ResearchTarget(ABC):
    """Abstract interface for something that can be optimized by the research loop.

    Subclasses handle getting current state, applying a change,
    evaluating the result, and rolling back on failure.
    """

    @abstractmethod
    def get_current(self) -> str:
        """Return a representation of the current state (for display/logging)."""
        ...

    @abstractmethod
    def apply_change(self, change_description: str) -> None:
        """Apply a modification. The target decides how to interpret the description."""
        ...

    @abstractmethod
    async def evaluate(self) -> float:
        """Run the evaluation and return the metric (lower is better).

        Must respect a fixed time budget (e.g., 5 minutes for training,
        3 subagent runs for prompt evaluation, etc.).
        """
        ...

    @abstractmethod
    def rollback(self) -> None:
        """Restore the state before the last apply_change()."""
        ...


class PromptTarget(ResearchTarget):
    """Optimize a prompt text file.

    Reads the prompt from a file, applies changes by modifying it,
    evaluates by running a subagent with the prompt, measures success rate.
    """

    def __init__(self, prompt_path: Path, eval_task: str = "",
                 user_id: str = "default_user", workspace_id: str = "personal",
                 tools: list | None = None):
        self.prompt_path = prompt_path
        self.eval_task = eval_task
        self.user_id = user_id
        self.workspace_id = workspace_id
        self._tools = tools or []
        self._backup: str | None = None

    def get_current(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def apply_change(self, change_description: str) -> None:
        self._backup = self.get_current()
        # For prompt targets, the change IS the new text
        self.prompt_path.write_text(change_description, encoding="utf-8")

    async def evaluate(self) -> float:
        """Run a subagent with the current prompt and measure success."""
        try:
            from src.sdk.loop import AgentLoop, RunConfig
            from src.sdk.messages import Message
            from src.sdk.providers.factory import create_model_from_config

            provider = create_model_from_config()
            loop = AgentLoop(
                provider=provider,
                tools=self._tools,
                system_prompt=self.get_current(),
                run_config=RunConfig(max_llm_calls=3, cost_limit_usd=0.05),
                user_id=self.user_id,
                workspace_id=self.workspace_id,
            )
            messages = [Message.user(self.eval_task)]
            result = await loop.run(messages)
            # Metric: 1.0 if assistant responded, 0.0 if error
            last = result[-1] if result else None
            return 0.0 if last is None or last.role != "assistant" else 1.0
        except Exception:
            return 1.0  # failure = high metric (bad)

    def rollback(self) -> None:
        if self._backup is not None:
            self.prompt_path.write_text(self._backup, encoding="utf-8")
            self._backup = None


class SkillTarget(ResearchTarget):
    """Optimize a skill's SKILL.md content (description + instructions).

    ⚠️ STUB — evaluate() always returns 0.5 (neutral). Real trigger-rate
    evaluation is TODO. The class structure is correct but non-functional.
    """

    def __init__(self, skill_name: str, skill_path: Path,
                 eval_queries: list[dict] | None = None,
                 user_id: str = "default_user", workspace_id: str = "personal"):
        self.skill_name = skill_name
        self.skill_path = skill_path
        self.eval_queries = eval_queries or []
        self.user_id = user_id
        self.workspace_id = workspace_id
        self._backup: str | None = None

    def get_current(self) -> str:
        return (self.skill_path / "SKILL.md").read_text(encoding="utf-8")

    def apply_change(self, change_description: str) -> None:
        self._backup = self.get_current()
        (self.skill_path / "SKILL.md").write_text(change_description, encoding="utf-8")

    async def evaluate(self) -> float:
        """Evaluate trigger rate: lower = better (1.0 = no triggers).

        TODO(#future): implement real trigger-rate evaluation by running the
        agent against eval queries and measuring skills_load call frequency.
        Currently returns 0.5 (neutral) for all inputs — skill optimization
        is non-functional until this is implemented.
        """
        return 0.5  # neutral stub

    def rollback(self) -> None:
        if self._backup is not None:
            (self.skill_path / "SKILL.md").write_text(self._backup, encoding="utf-8")
            self._backup = None


class SubagentTarget(ResearchTarget):
    """Optimize a subagent's AgentDef config (prompt, tools, limits, model).

    Evaluates by running the subagent on a benchmark task and measuring
    completion quality, cost, and time.
    """

    def __init__(self, agent_def_path: Path,
                 eval_task: str = "",
                 user_id: str = "default_user", workspace_id: str = "personal"):
        self.agent_def_path = agent_def_path
        self.eval_task = eval_task
        self.user_id = user_id
        self.workspace_id = workspace_id
        self._backup: str | None = None

    def get_current(self) -> str:
        return self.agent_def_path.read_text(encoding="utf-8")

    def apply_change(self, change_description: str) -> None:
        self._backup = self.get_current()
        self.agent_def_path.write_text(change_description, encoding="utf-8")

    async def evaluate(self) -> float:
        """Run the subagent on the eval task and return cost-normalized score."""
        try:
            from src.sdk.coordinator import SubagentCoordinator
            from src.storage.paths import get_paths

            paths = get_paths(self.user_id, workspace_id=self.workspace_id)
            coord = SubagentCoordinator(self.user_id, self.workspace_id)

            result = await coord.delegate(self.agent_def_path.stem, self.eval_task)
            if result.success:
                return 0.0  # perfect
            return 0.8  # ran but failed
        except Exception:
            return 1.0  # crashed

    def rollback(self) -> None:
        if self._backup is not None:
            self.agent_def_path.write_text(self._backup, encoding="utf-8")
            self._backup = None


@dataclass
class ResearchLoop:
    """Generic autoresearch loop: apply change → evaluate → keep or discard.

    All experiment methods are async because evaluate() requires async
    (subagent runs, AgentLoop invocations).

    Usage:
        target = PromptTarget(Path("prompt.txt"), eval_task="...")
        loop = ResearchLoop(target=target)
        result = await loop.run_experiment("Make it more concise")
        print(result.metric_value, result.improved)
    """

    target: ResearchTarget
    experiment_dir: Path = Path(".")
    metric_name: str = "val_metric"
    results_file: str = "results.tsv"
    budget_seconds: int = 300
    _baseline_cache: float | None = None

    def __post_init__(self) -> None:
        self._init_results_file()

    def _init_results_file(self) -> None:
        tsv_path = self.experiment_dir / self.results_file
        if not tsv_path.exists():
            tsv_path.write_text(
                "commit\tdirty\tval_metric\tmemory_gb\tstatus\tdescription\n",
                encoding="utf-8",
            )

    def _is_git_dirty(self) -> bool:
        """Check if git working tree has uncommitted changes."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "diff", "--quiet"],
                capture_output=True, timeout=5,
            )
            return result.returncode != 0
        except Exception:
            return True  # assume dirty if we can't check

    def _get_commit_hash(self) -> str:
        """Get short git commit hash, or 'none' if not in a git repo."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() or "none"
        except Exception:
            return "none"

    def _log_result(self, result: ExperimentResult) -> None:
        tsv_path = self.experiment_dir / self.results_file
        memory_gb = f"{result.memory_gb:.1f}" if result.memory_gb else "0.0"
        val = f"{result.metric_value:.6f}" if result.metric_value else "0.000000"
        dirty = "1" if self._is_git_dirty() else "0"
        # Note: TSV is fragile if descriptions contain tabs. Future: use JSONL.
        line = (
            f"{result.commit_hash}\t{dirty}\t{val}\t{memory_gb}\t"
            f"{result.status}\t{result.description}\n"
        )
        with open(tsv_path, "a", encoding="utf-8") as f:
            f.write(line)

    async def run_experiment(self, change_description: str) -> ExperimentResult:
        """Run one experiment: apply change → eval → keep/discard → log."""
        target_name = getattr(self.target, "skill_name", None) or \
                      getattr(self.target, "prompt_path", "unknown")

        # Baseline evaluation (cached if unchanged)
        if self._baseline_cache is None:
            self._baseline_cache = await self.target.evaluate()
        baseline = self._baseline_cache

        # Apply change
        self.target.apply_change(change_description)

        # Evaluate after change
        try:
            new_metric = await self.target.evaluate()
        except Exception:
            new_metric = 1.0

        improved = new_metric < baseline
        status = "keep" if improved else "discard"

        if not improved:
            self.target.rollback()
        else:
            # Update baseline for next iteration
            self._baseline_cache = new_metric

        result = ExperimentResult(
            target_name=str(target_name),
            metric_value=new_metric,
            metric_name=self.metric_name,
            improved=improved,
            commit_hash=self._get_commit_hash(),
            description=change_description[:200],
            status=status,
        )

        self._log_result(result)
        return result

    async def run_experiments(self, changes: list[str]) -> list[ExperimentResult]:
        """Run multiple experiments sequentially."""
        results = []
        for c in changes:
            results.append(await self.run_experiment(c))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/sdk/test_research.py -v`
Expected: 4 PASS (TestExperimentResult, TestResearchTarget::test_protocol, TestResearchTarget::test_prompt_target, TestResearchLoop tests)

Note: The ResearchLoop tests use `AsyncMagicMock` (from `unittest.mock`) for the async `evaluate()` method. `test_prompt_target` uses real file I/O but only tests sync methods (no async evaluate called). Requires `pytest-asyncio` for `@pytest.mark.asyncio`.

- [ ] **Step 5: Commit**

```bash
git add src/sdk/research.py tests/sdk/test_research.py
git commit -m "feat(autoresearch): add ResearchTarget protocol and ResearchLoop class"
```

---

### Task 2: Create research tools

**Files:**
- Create: `src/sdk/tools_core/research.py`

- [ ] **Step 1: Write failing test**

```python
# tests/sdk/test_research_tools.py

from unittest.mock import patch, MagicMock, PropertyMock
import tempfile
from pathlib import Path

from src.sdk.tools_core.research import research_start, research_results, research_abort


class TestResearchTools:
    @pytest.mark.asyncio
    async def test_research_start_returns_experiment_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("baseline")  # file must exist
            with patch("src.sdk.tools_core.research.ResearchLoop") as MockLoop:
                mock_instance = AsyncMagicMock()
                mock_instance.run_experiment.return_value = MagicMock(
                    metric_value=0.5, improved=True, status="keep",
                    description="test change",
                )
                MockLoop.return_value = mock_instance

                result = await research_start.invoke({
                    "target_type": "prompt",
                    "target_name": str(prompt_path),
                    "change_description": "test change",
                    "user_id": "test_user",
                })
                assert "experiment" in result.lower()
                assert "0.5" in result

    def test_research_results_returns_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tsv = Path(tmpdir) / "results.tsv"
            tsv.write_text(
                "commit\tval_metric\tmemory_gb\tstatus\tdescription\n"
                "abc123\t0.500000\t0.0\tkeep\tfirst change\n"
            )
            result = research_results.invoke({
                "experiment_dir": str(tmpdir),
            })
            assert "0.500000" in result
            assert "first change" in result

    def test_research_abort_returns_not_implemented(self):
        result = research_abort.invoke({
            "experiment_id": "test-exp-001",
        })
        assert "not implemented" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sdk/test_research_tools.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create tools module**

`src/sdk/tools_core/research.py`:
```python
"""Research tools — autonomous experiment loop for optimizing prompts, skills, and subagents.

Follows the karpathy/autoresearch pattern:
- research_start(target_type, target_name, change) → runs one experiment
- research_results(experiment_dir) → reads log
- research_abort(experiment_id) → cancels running experiment
"""

from __future__ import annotations

from pathlib import Path

from src.sdk.tools import ToolAnnotations, tool
from src.app_logging import get_logger

logger = get_logger()


@tool
async def research_start(
    target_type: str,
    target_name: str,
    change_description: str,
    experiment_dir: str = ".",
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Run a single autoresearch experiment on a target.

    Applies a change, evaluates it, keeps or discards, logs to results.tsv.

    Args:
        target_type: Type of target to optimize: 'prompt', 'skill', or 'subagent'
        target_name: For prompt: path to prompt file. For skill: skill name.
                     For subagent: AgentDef name.
        change_description: Description of the change to apply.
        experiment_dir: Directory for results.tsv output.
        user_id: User identifier (injected automatically)
        workspace_id: Workspace identifier

    Returns:
        Experiment result summary
    """
    from src.sdk.research import ResearchLoop, PromptTarget, SkillTarget, SubagentTarget
    from src.storage.paths import get_paths

    target_type = target_type.lower()
    paths = get_paths(user_id, workspace_id=workspace_id)

    if target_type == "prompt":
        prompt_path = Path(target_name)
        # ⚠️ Safety: validate path is within user data directory
        user_data = Path(paths._user_base())
        try:
            prompt_path.relative_to(user_data)
        except ValueError:
            return f"Prompt path must be within user data directory: {user_data}"
        if not prompt_path.exists():
            return f"Prompt file not found: {target_name}"
        eval_task = f"Based on your instructions, respond to: 'Introduce yourself.'"
        target = PromptTarget(
            prompt_path=prompt_path, eval_task=eval_task,
            user_id=user_id, workspace_id=workspace_id,
        )
    elif target_type == "skill":
        from src.skills.registry import get_skill_registry
        registry = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
        skill = registry.get_skill(target_name)
        if not skill:
            return f"Skill '{target_name}' not found."
        skill_path = Path(skill["path"])
        target = SkillTarget(
            skill_name=target_name, skill_path=skill_path,
            user_id=user_id, workspace_id=workspace_id,
        )
    elif target_type == "subagent":
        agent_path = paths.workspace_subagents_dir() / target_name / "config.yaml"
        if not agent_path.exists():
            # Fallback to user-global
            agent_path = paths.global_subagents_dir() / target_name / "config.yaml"
        if not agent_path.exists():
            return f"Subagent '{target_name}' not found."
        target = SubagentTarget(
            agent_def_path=agent_path,
            eval_task=f"Complete the following task: summarize the current workspace.",
            user_id=user_id, workspace_id=workspace_id,
        )
    else:
        return f"Unknown target type: '{target_type}'. Use 'prompt', 'skill', or 'subagent'."

    loop = ResearchLoop(
        target=target,
        experiment_dir=Path(experiment_dir),
    )
    result = await loop.run_experiment(change_description)

    logger.info(
        "research.experiment_complete",
        {
            "target_type": target_type,
            "target_name": target_name,
            "metric": result.metric_value,
            "improved": result.improved,
            "status": result.status,
        },
        user_id=user_id,
    )

    status = "IMPROVED" if result.improved else "no change / worse (discarded)"
    return (
        f"Experiment complete.\n"
        f"  Target: {target_type} '{target_name}'\n"
        f"  Metric ({loop.metric_name}): {result.metric_value:.6f}\n"
        f"  Result: {status}\n"
        f"  Description: {change_description[:100]}\n"
        f"  Log: {Path(experiment_dir) / loop.results_file}"
    )


research_start.annotations = ToolAnnotations(
    title="Start Research Experiment", destructive=True, open_world=True
)


@tool
def research_results(
    experiment_dir: str = ".",
) -> str:
    """Read the experiment results log (results.tsv) from an experiment directory.

    Args:
        experiment_dir: Directory containing results.tsv

    Returns:
        Tabulated experiment results
    """
    tsv_path = Path(experiment_dir) / "results.tsv"
    if not tsv_path.exists():
        return "No results.tsv found in the specified directory."

    lines = tsv_path.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) <= 1:
        return "Results file exists but has no experiment data."

    return f"## Experiment Results\n\n```\n" + "\n".join(lines) + "\n```"


research_results.annotations = ToolAnnotations(
    title="Research Results", read_only=True, idempotent=True
)


@tool
def research_abort(
    experiment_id: str = "",
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Cancel a running research experiment.

    ⚠️ NOT IMPLEMENTED — experiments are synchronous and cannot be aborted
    mid-flight in this version. This tool exists for future use with async
    cancellation via asyncio.Task.

    Args:
        experiment_id: Experiment identifier (reserved for future use)
        user_id: User identifier (injected automatically)
        workspace_id: Workspace identifier

    Returns:
        Explanation that abort is not yet implemented
    """
    logger.info(
        "research.abort",
        {"experiment_id": experiment_id},
        user_id=user_id,
    )
    return (
        f"Abort is not implemented in this version. "
        f"Experiments run synchronously and cannot be cancelled mid-flight. "
        f"Wait for the current experiment to complete."
    )


research_abort.annotations = ToolAnnotations(
    title="Abort Research Experiment", destructive=True
)
```

- [ ] **Step 4: Wire research tools into native_tools.py**

In `src/sdk/native_tools.py`, add the import:
```python
from src.sdk.tools_core.research import research_start, research_results, research_abort
```

Add to the list returned by `get_native_tools()`:
```python
research_start,
research_results,
research_abort,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/sdk/test_research_tools.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/sdk/tools_core/research.py src/sdk/native_tools.py tests/sdk/test_research_tools.py
git commit -m "feat(autoresearch): add research_start, research_results, research_abort tools"
```

---

### Task 3: Create seed skill for autoresearch

**Files:**
- Create: `src/skills_seed/autoresearch/SKILL.md`
- Create: `src/skills_seed/autoresearch/program.md`

- [ ] **Step 1: Write the SKILL.md**

`src/skills_seed/autoresearch/SKILL.md`:
```markdown
---
name: autoresearch
description: >
  Optimize prompts, skills, and subagents through iterative
  experimentation. Use this skill when the user wants to improve an
  agent's behavior, tune a skill's description for better triggering,
  or automatically find optimal configurations through testing.
---

# Autoresearch

Follow the program in `program.md` to run iterative experiments
on a target (prompt, skill, or subagent). The research loop is:

1. Snapshot the current state
2. Apply a change via `research_start(target_type, target_name, change_description)`
3. Evaluate the result (improved metric = keep, worse = discard)
4. Check results with `research_results()`
5. Repeat until the user is satisfied or the metric converges

## Targets

### Prompt optimization
- **What gets modified:** A prompt text file (user prompt, workspace prompt, or subagent system prompt)
- **Evaluation:** The agent runs a standardized test task and measures response quality
- **Command:** `research_start(target_type="prompt", target_name="path/to/prompt.txt", change_description="Your proposed change")`

### Skill optimization
- **What gets modified:** The skill's `SKILL.md` file (description + instructions)
- **Evaluation:** Trigger rate — how often the skill is loaded when relevant queries come in
- **Command:** `research_start(target_type="skill", target_name="skill-name", change_description="Your proposed change")`

### Subagent optimization
- **What gets modified:** The subagent's `config.yaml` (system prompt, model, tools, limits)
- **Evaluation:** Task completion quality on a benchmark task
- **Command:** `research_start(target_type="subagent", target_name="agent-name", change_description="Your proposed change")`

## Workflow

1. **Load this skill:** Run `skills_load("autoresearch")` to get these instructions
2. **Review the program:** Read `program.md` for the detailed experiment protocol
3. **Establish baseline:** Run `research_start()` with a no-op change first to get the baseline metric
4. **Iterate:** Propose a change, run the experiment, check the result
5. **Continue until interrupted:** Do NOT ask "should I continue?" — the loop runs until the user stops you
```

- [ ] **Step 2: Write program.md**

`src/skills_seed/autoresearch/program.md`:
```markdown
# Autoresearch Program

This file defines the research program. Values here influence how the
agent conducts experiments. Edit this file to tune the research strategy.

## Budget
- Default time per evaluation: 300 seconds (5 minutes)
- Default cost limit per eval: $0.05
- Default max LLM calls per eval: 3

## Targets
- prompt: Optimize a prompt text file. Evaluates by running a standardized task.
- skill: Optimize a SKILL.md description. Evaluates by measuring trigger rate.
- subagent: Optimize an AgentDef config. Evaluates by running a benchmark task.

## Protocol
1. Always establish a baseline first (no-op experiment)
2. Make one change per experiment
3. Log all results to results.tsv
4. If the metric is better, keep the change
5. If the metric is worse or equal, roll back
6. NEVER ask the user if you should continue
```

- [ ] **Step 3: Verify the skill registers correctly**

The seed skill is automatically picked up by `SkillRegistry._seed_system_skills()` — it scans `src/skills_seed/` for subdirectories and copies them to the user's skills directory on first run. No additional wiring needed.

```bash
# Quick verification that the skill parses correctly
uv run python -c "
from src.skills.models import parse_skill_file
from pathlib import Path
skill = parse_skill_file(Path('src/skills_seed/autoresearch/SKILL.md'))
print(f'Name: {skill[\"name\"]}')
print(f'Description: {skill[\"description\"][:80]}...')
"
```
Expected: prints "Name: autoresearch" and description

- [ ] **Step 4: Commit**

```bash
git add src/skills_seed/autoresearch/SKILL.md src/skills_seed/autoresearch/program.md
git commit -m "feat(autoresearch): add seed skill with research program"
```

---

### Task 4: Wire research tools into subagents (disallowed_tools update)

**Files:**
- Modify: `src/sdk/subagent_models.py`

The research tools should be added to the default `SAFE_DISALLOWED_TOOLS` for subagents to prevent recursion (a subagent shouldn't run experiments that spawn more subagents).

- [ ] **Step 1: Update SAFE_DISALLOWED_TOOLS**

In `src/sdk/subagent_models.py`, find where `SAFE_DISALLOWED_TOOLS` is defined and add:
```python
"research_start",
"research_abort",
```

- [ ] **Step 2: Run subagent tests**

Run: `pytest tests/sdk/test_subagent_v1.py -v -k "disallowed" 2>&1 | tail -20`
Expected: existing disallowed_tools tests pass (they check `"subagent_start" in d.disallowed_tools`, which still works)

- [ ] **Step 3: Commit**

```bash
git add src/sdk/subagent_models.py
git commit -m "feat(autoresearch): block research tools in subagents to prevent recursion"
```

---

### Task 5: Run all tests

- [ ] **Step 1: Run all research-related tests**

```bash
uv run pytest tests/sdk/test_research.py tests/sdk/test_research_tools.py -v
```
Expected: all pass

- [ ] **Step 2: Run full SDK test suite**

```bash
uv run pytest tests/sdk/ -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 3: Commit any final fixes**

```bash
git commit -m "chore: test fixes after autoresearch implementation"
```

---
