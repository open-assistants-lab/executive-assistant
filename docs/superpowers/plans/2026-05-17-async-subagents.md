# Async Configurable Subagents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current blocking subagent flow into true async, workspace-scoped, configurable subagents with durable job state, safe tool resolution, and aligned SDK/HTTP APIs.

**Architecture:** Keep `WorkQueueDB` as the v1 durable job store, but add claim/heartbeat semantics and async background execution. `AgentDef` becomes the reusable workspace-scoped worker definition; each started job freezes a config snapshot. Runtime tools are renamed to `subagent_start/check/tasks/instruct/cancel`, with no legacy aliases.

**Tech Stack:** Python 3.11+, Pydantic, aiosqlite, FastAPI, custom SDK `AgentLoop`, existing provider/model registry.

---

## File Structure

- `src/sdk/subagent_models.py` — update `AgentDef`, `TaskStatus`, constants, and validation fields.
- `src/sdk/work_queue.py` — add durable claim/heartbeat/cancelling/stale-job behavior.
- `src/sdk/coordinator.py` — split enqueue/start/run logic, add async background runner, tool resolution, prompt building, delete/list/check helpers.
- `src/sdk/tools_core/subagent.py` — replace old runtime tools with `subagent_start`, `subagent_check`, `subagent_tasks`; keep management tools.
- `src/http/routers/subagents.py` — align HTTP API with SDK tools.
- `src/sdk/native_tools.py` — register new subagent tools and remove old names.
- `tests/sdk/test_subagent_v1.py` — update model, queue, coordinator tests.
- `tests/sdk/test_subagent_tools_async.py` — new SDK tool contract tests for new names and async behavior.
- `tests/api/test_subagents.py` — update HTTP contract tests.
- `tests/evaluation/test_subagent_skills.py`, `tests/evaluation/personas.py`, `tests/evaluation/test_25_personas.py` — replace old tool names in evaluation fixtures.

---

### Task 1: Update Models And Validation

**Files:**
- Modify: `src/sdk/subagent_models.py`
- Modify: `tests/sdk/test_subagent_v1.py`

- [ ] **Step 1: Write failing model tests**

Add tests to `tests/sdk/test_subagent_v1.py` under `TestAgentDef` and `TestTaskStatus`:

```python
def test_agent_def_new_fields():
    from src.sdk.subagent_models import AgentDef

    d = AgentDef(
        name="researcher",
        workspace_id="sales",
        provider_options={"anthropic": {"thinking": {"type": "enabled"}}},
        output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        handoff_instructions="Return concise bullets.",
        artifact_policy="write reports under reports/",
    )

    assert d.workspace_id == "sales"
    assert d.provider_options == {"anthropic": {"thinking": {"type": "enabled"}}}
    assert d.output_schema is not None
    assert d.handoff_instructions == "Return concise bullets."
    assert d.artifact_policy == "write reports under reports/"


def test_default_disallowed_tools_use_new_names_only():
    from src.sdk.subagent_models import AgentDef

    d = AgentDef(name="a")
    assert "subagent_start" in d.disallowed_tools
    assert "subagent_tasks" in d.disallowed_tools
    assert "subagent_invoke" not in d.disallowed_tools
    assert "subagent_progress" not in d.disallowed_tools


def test_task_status_has_cancelling():
    from src.sdk.subagent_models import TaskStatus

    assert TaskStatus.CANCELLING == "cancelling"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/sdk/test_subagent_v1.py::TestAgentDef tests/sdk/test_subagent_v1.py::TestTaskStatus -q`

Expected: fails because fields/status/default denylist are not updated.

- [ ] **Step 3: Update `src/sdk/subagent_models.py`**

Apply these changes:

```python
DEFAULT_DISALLOWED_TOOLS = [
    "subagent_create",
    "subagent_update",
    "subagent_delete",
    "subagent_list",
    "subagent_start",
    "subagent_check",
    "subagent_tasks",
    "subagent_instruct",
    "subagent_cancel",
]
```

Add status:

```python
class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

Update `AgentDef` fields:

```python
class AgentDef(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    description: str = ""
    workspace_id: str = "personal"
    model: str | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    tools: list[str] | None = None
    disallowed_tools: list[str] = Field(default_factory=lambda: list(DEFAULT_DISALLOWED_TOOLS))
    skills: list[str] = Field(default_factory=list)
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS
    cost_limit_usd: float = DEFAULT_COST_LIMIT_USD
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    mcp_config: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None

    model_config = {"extra": "ignore"}
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/sdk/test_subagent_v1.py::TestAgentDef tests/sdk/test_subagent_v1.py::TestTaskStatus -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/sdk/subagent_models.py tests/sdk/test_subagent_v1.py
git commit -m "feat: expand subagent definition model"
```

---

### Task 2: Add Durable Claim, Heartbeat, And Cancellable Status To WorkQueueDB

**Files:**
- Modify: `src/sdk/work_queue.py`
- Modify: `tests/sdk/test_subagent_v1.py`

- [ ] **Step 1: Write failing work queue tests**

Add tests under `TestWorkQueueDB`:

```python
@pytest.mark.asyncio
async def test_claim_pending_task_once(self, db, agent_def):
    task_id = await db.insert_task("test_agent", "t", agent_def)

    first = await db.claim_task(task_id, worker_id="worker-a")
    second = await db.claim_task(task_id, worker_id="worker-b")

    assert first is True
    assert second is False
    row = await db.get_task(task_id)
    assert row["status"] == "running"
    assert row["claimed_by"] == "worker-a"
    assert row["claimed_at"]
    assert row["heartbeat_at"]


@pytest.mark.asyncio
async def test_request_cancel_sets_cancelling_for_running_task(self, db, agent_def):
    task_id = await db.insert_task("test_agent", "t", agent_def)
    await db.claim_task(task_id, worker_id="worker-a")

    ok = await db.request_cancel(task_id)

    assert ok
    row = await db.get_task(task_id)
    assert row["cancel_requested"] == 1
    assert row["status"] == "cancelling"


@pytest.mark.asyncio
async def test_heartbeat_updates_timestamp(self, db, agent_def):
    task_id = await db.insert_task("test_agent", "t", agent_def)
    await db.claim_task(task_id, worker_id="worker-a")
    before = (await db.get_task(task_id))["heartbeat_at"]

    ok = await db.heartbeat(task_id, worker_id="worker-a")

    after = (await db.get_task(task_id))["heartbeat_at"]


    assert ok
    assert after >= before


@pytest.mark.asyncio
async def test_mark_stale_running_failed(self, db, agent_def):
    task_id = await db.insert_task("test_agent", "t", agent_def)
    await db.claim_task(task_id, worker_id="worker-a")

    count = await db.mark_stale_running_failed(max_age_seconds=-1)

    assert count >= 1
    row = await db.get_task(task_id)
    assert row["status"] == "failed"
    assert "interrupted by restart" in row["error"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/sdk/test_subagent_v1.py::TestWorkQueueDB -q`

Expected: fails because claim/heartbeat fields and methods do not exist.

- [ ] **Step 3: Update schema and methods**

In `src/sdk/work_queue.py`, extend `_SCHEMA` with additive columns:

```sql
claimed_by TEXT,
claimed_at TEXT,
heartbeat_at TEXT,
started_at TEXT,
completed_at TEXT
```

Because `CREATE TABLE IF NOT EXISTS` does not add columns to existing DBs, after `executescript(_SCHEMA)` add migration logic in `_get_db()`:

```python
await self._ensure_columns()
```

Add method:

```python
async def _ensure_columns(self) -> None:
    db = self._db
    if db is None:
        return
    cursor = await db.execute("PRAGMA table_info(work_queue)")
    rows = await cursor.fetchall()
    existing = {row["name"] for row in rows}
    columns = {
        "claimed_by": "TEXT",
        "claimed_at": "TEXT",
        "heartbeat_at": "TEXT",
        "started_at": "TEXT",
        "completed_at": "TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE work_queue ADD COLUMN {name} {ddl}")
    await db.commit()
```

Add methods:

```python
async def claim_task(self, task_id: str, worker_id: str) -> bool:
    db = await self._get_db()
    now = _now()
    cursor = await db.execute(
        """UPDATE work_queue
        SET status = ?, claimed_by = ?, claimed_at = ?, heartbeat_at = ?, started_at = ?, updated_at = ?
        WHERE id = ? AND status = ?""",
        (TaskStatus.RUNNING.value, worker_id, now, now, now, now, task_id, TaskStatus.PENDING.value),
    )
    await db.commit()
    return cursor.rowcount > 0


async def heartbeat(self, task_id: str, worker_id: str) -> bool:
    db = await self._get_db()
    now = _now()
    cursor = await db.execute(
        "UPDATE work_queue SET heartbeat_at = ?, updated_at = ? WHERE id = ? AND claimed_by = ? AND status IN (?, ?)",
        (now, now, task_id, worker_id, TaskStatus.RUNNING.value, TaskStatus.CANCELLING.value),
    )
    await db.commit()
    return cursor.rowcount > 0


async def mark_stale_running_failed(self, max_age_seconds: int = 300) -> int:
    from datetime import timedelta

    db = await self._get_db()
    cutoff = (datetime.now(UTC) - timedelta(seconds=max_age_seconds)).isoformat()
    now = _now()
    cursor = await db.execute(
        """UPDATE work_queue
        SET status = ?, error = ?, updated_at = ?, completed_at = ?
        WHERE status IN (?, ?) AND (heartbeat_at IS NULL OR heartbeat_at < ?)""",
        (
            TaskStatus.FAILED.value,
            "interrupted by restart",
            now,
            now,
            TaskStatus.RUNNING.value,
            TaskStatus.CANCELLING.value,
            cutoff,
        ),
    )
    await db.commit()
    return cursor.rowcount
```

Update terminal setters to write `completed_at`:

```python
"UPDATE work_queue SET status = ?, result = ?, updated_at = ?, completed_at = ? WHERE id = ?"
```

Update `request_cancel()`:

```python
cursor = await db.execute(
    """UPDATE work_queue
    SET cancel_requested = 1,
        status = CASE WHEN status = ? THEN ? ELSE status END,
        updated_at = ?
    WHERE id = ?""",
    (TaskStatus.RUNNING.value, TaskStatus.CANCELLING.value, now, task_id),
)
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/sdk/test_subagent_v1.py::TestWorkQueueDB -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/sdk/work_queue.py tests/sdk/test_subagent_v1.py
git commit -m "feat: add durable subagent job claiming"
```

---

### Task 3: Implement Safe Tool And Skill Resolution

**Files:**
- Modify: `src/sdk/coordinator.py`
- Modify: `tests/sdk/test_subagent_v1.py`

- [ ] **Step 1: Write failing resolution tests**

Add tests near coordinator tests:

```python
def test_build_tools_removes_subagent_and_extra_memory_tools(agent_def):
    from src.sdk.coordinator import _build_tools_for_subagent
    from src.sdk.subagent_models import AgentDef

    d = AgentDef(name="a", tools=None)
    names = {t.name for t in _build_tools_for_subagent(d)}

    assert "memory_search" in names
    assert not any(n.startswith("subagent_") for n in names)
    assert "memory_search_all" not in names
    assert "memory_search_insights" not in names


def test_build_tools_allowlist_still_includes_memory_search():
    from src.sdk.coordinator import _build_tools_for_subagent
    from src.sdk.subagent_models import AgentDef

    d = AgentDef(name="a", tools=["time_get"], disallowed_tools=["memory_search"])
    names = {t.name for t in _build_tools_for_subagent(d)}

    assert "time_get" in names
    assert "memory_search" in names


def test_build_tools_includes_skills_load_when_skills_configured():
    from src.sdk.coordinator import _build_tools_for_subagent
    from src.sdk.subagent_models import AgentDef

    d = AgentDef(name="a", tools=["time_get"], skills=["skill-creator"])
    names = {t.name for t in _build_tools_for_subagent(d)}

    assert "skills_load" in names


def test_validate_agent_def_rejects_unknown_tool():
    from src.sdk.coordinator import validate_agent_def
    from src.sdk.subagent_models import AgentDef

    errors = validate_agent_def(AgentDef(name="a", tools=["not_a_tool"]))
    assert any("Unknown tool" in e for e in errors)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/sdk/test_subagent_v1.py -q -k "build_tools or validate_agent_def"`

Expected: fails because resolution and validation do not exist.

- [ ] **Step 3: Add constants and validation helpers in `src/sdk/coordinator.py`**

Add near top:

```python
MANDATORY_SUBAGENT_TOOLS = {"memory_search"}
OPTIONAL_SKILL_LOAD_TOOL = "skills_load"
DENIED_SKILL_MANAGEMENT_TOOLS = {"skill_create", "skill_delete", "skill_update"}


def _is_denied_memory_tool(name: str) -> bool:
    return name.startswith("memory_") and name != "memory_search"


def _is_subagent_tool(name: str) -> bool:
    return name.startswith("subagent_")
```

Add validator:

```python
def validate_agent_def(agent_def: AgentDef, user_id: str = "default_user", workspace_id: str = "personal") -> list[str]:
    from src.sdk.native_tools import get_native_tools
    from src.skills.registry import get_skill_registry

    tool_names = {t.name for t in get_native_tools()}
    errors: list[str] = []

    requested = set(agent_def.tools or []) | set(agent_def.disallowed_tools or [])
    for name in requested:
        if name not in tool_names:
            errors.append(f"Unknown tool: {name}")
        if _is_subagent_tool(name):
            errors.append(f"Subagent tool is not allowed in subagents: {name}")
        if _is_denied_memory_tool(name):
            errors.append(f"Only memory_search is allowed from memory tools: {name}")

    registry = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
    for skill_name in agent_def.skills:
        if registry.get_skill(skill_name) is None:
            errors.append(f"Unknown skill: {skill_name}")

    if agent_def.max_llm_calls <= 0:
        errors.append("max_llm_calls must be positive")
    if agent_def.cost_limit_usd <= 0:
        errors.append("cost_limit_usd must be positive")
    if agent_def.timeout_seconds <= 0:
        errors.append("timeout_seconds must be positive")

    return errors
```

Replace `_build_tools_for_subagent()`:

```python
def _build_tools_for_subagent(agent_def: AgentDef) -> list[Any]:
    from src.sdk.native_tools import get_native_tools

    all_native = get_native_tools()
    tool_map = {t.name: t for t in all_native}

    allowed = set(agent_def.tools) if agent_def.tools else set(tool_map.keys())
    final = set(allowed)

    final = {n for n in final if not _is_subagent_tool(n)}
    final = {n for n in final if not _is_denied_memory_tool(n)}
    final -= DENIED_SKILL_MANAGEMENT_TOOLS
    final -= set(agent_def.disallowed_tools)
    final -= {n for n in final if _is_subagent_tool(n)}
    final -= {n for n in final if _is_denied_memory_tool(n)}
    final -= DENIED_SKILL_MANAGEMENT_TOOLS
    final |= MANDATORY_SUBAGENT_TOOLS
    if agent_def.skills:
        final.add(OPTIONAL_SKILL_LOAD_TOOL)

    ordered = sorted(n for n in final if n in tool_map)
    return [tool_map[n] for n in ordered]
```

- [ ] **Step 4: Update system prompt skill section for progressive disclosure**

In `_build_system_prompt()`, change skill loading to use workspace-aware descriptions only:

```python
    skill_registry = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
    selected_skills = []
    for skill_name in agent_def.skills:
        skill = skill_registry.get_skill(skill_name)
        if skill:
            selected_skills.append((skill_name, skill.get("description", "")))
    if selected_skills:
        parts.append("\n## Available Skills")
        parts.append("When the task requires one of these skills, call skills_load(name) before following the skill instructions.")
        for skill_name, description in selected_skills:
            parts.append(f"- **{skill_name}**: {description}")
```

- [ ] **Step 5: Run targeted tests**

Run: `uv run pytest tests/sdk/test_subagent_v1.py -q -k "build_tools or validate_agent_def or Coordinator"`

Expected: pass or reveal existing coordinator tests to update in later tasks.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "feat: enforce safe subagent tool resolution"
```

---

### Task 4: Make Coordinator Start Jobs Asynchronously

**Files:**
- Modify: `src/sdk/coordinator.py`
- Modify: `tests/sdk/test_subagent_v1.py`

- [ ] **Step 1: Write failing async coordinator tests**

Add tests to coordinator section:

```python
@pytest.mark.asyncio
async def test_start_returns_before_runner_finishes(mock_paths, agent_def, monkeypatch):
    from src.sdk.coordinator import SubagentCoordinator

    coordinator = SubagentCoordinator("test_user")
    await coordinator.create(agent_def)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def fake_run_job(task_id: str):
        started.set()
        await finish.wait()

    monkeypatch.setattr(coordinator, "_run_job", fake_run_job)

    task_id = await coordinator.start("test_agent", "do work")

    await asyncio.wait_for(started.wait(), timeout=1)
    row = await (await coordinator._get_db()).get_task(task_id)
    assert row is not None
    assert row["status"] in {"pending", "running"}
    finish.set()


@pytest.mark.asyncio
async def test_start_freezes_config_snapshot(mock_paths, agent_def, monkeypatch):
    from src.sdk.coordinator import SubagentCoordinator

    coordinator = SubagentCoordinator("test_user")
    await coordinator.create(agent_def)

    async def fake_run_job(task_id: str):
        return None

    monkeypatch.setattr(coordinator, "_run_job", fake_run_job)
    task_id = await coordinator.start("test_agent", "do work")
    await coordinator.update("test_agent", model="changed:model")

    row = await (await coordinator._get_db()).get_task(task_id)
    config = json.loads(row["config"])
    assert config["model"] == agent_def.model
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/sdk/test_subagent_v1.py -q -k "start_returns or freezes_config"`

Expected: fails because `start()` does not exist.

- [ ] **Step 3: Add coordinator background runner methods**

In `SubagentCoordinator`, add:

```python
    async def start(
        self,
        agent_name: str,
        task: str,
        parent_id: str | None = None,
    ) -> str:
        agent_def = self.load_def(agent_name)
        if agent_def is None:
            raise ValueError(f"Subagent '{agent_name}' not found. Create it first with subagent_create.")

        errors = validate_agent_def(agent_def, user_id=self.user_id, workspace_id=self.workspace_id)
        if errors:
            raise ValueError("; ".join(errors))

        db = await self._get_db()
        task_id = await db.insert_task(agent_name, task, agent_def, parent_id)
        asyncio.create_task(self._run_job(task_id))
        return task_id

    async def _run_job(self, task_id: str) -> None:
        db = await self._get_db()
        worker_id = f"{self.user_id}:{self.workspace_id}:{id(self)}"
        claimed = await db.claim_task(task_id, worker_id=worker_id)
        if not claimed:
            return

        row = await db.get_task(task_id)
        if row is None:
            return
        agent_def = AgentDef(**json.loads(row.get("config") or "{}"))
        task = row.get("task") or ""

        async def _heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(5)
                await db.heartbeat(task_id, worker_id=worker_id)

        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        try:
            result = await asyncio.wait_for(
                self._run_loop(task_id, agent_def, task, db),
                timeout=agent_def.timeout_seconds,
            )
            await db.set_completed(task_id, result)
        except TaskCancelledError:
            await db.set_cancelled(task_id)
        except TimeoutError:
            await db.set_failed(task_id, f"timeout after {agent_def.timeout_seconds}s")
        except Exception as e:
            await db.set_failed(task_id, f"{type(e).__name__}: {e}")
        finally:
            heartbeat_task.cancel()
```

Keep `invoke()` only temporarily for tests until Task 6 removes old tool references. Change it to await completion by polling only if old tests still require it, or mark old invoke tests for removal in Task 6.

- [ ] **Step 4: Add delete method if missing**

Add to `SubagentCoordinator`:

```python
    async def delete(self, name: str) -> bool:
        import shutil

        agent_def = self.load_def(name)
        if agent_def is None:
            return False
        agent_path = self.base_path / name
        if agent_path.exists():
            shutil.rmtree(agent_path)
        return True
```

- [ ] **Step 5: Include required middleware in `_run_loop()`**

Import and include summarization/observation middleware if available:

```python
        middlewares = [progress_mw, instruction_mw]
        try:
            from src.sdk.middleware_summarization import SummarizationMiddleware
            middlewares.append(SummarizationMiddleware())
        except Exception:
            pass
        try:
            from src.sdk.middleware_observation import ObservationMiddleware
            middlewares.append(ObservationMiddleware(user_id=self.user_id, workspace_id=self.workspace_id))
        except Exception:
            raise
```

If `ObservationMiddleware` constructor differs, adapt to the actual implementation and add tests. Do not silently omit it.

Pass provider options into `RunConfig`:

```python
        run_config = RunConfig(
            max_llm_calls=agent_def.max_llm_calls,
            cost_limit_usd=agent_def.cost_limit_usd,
            provider_options=agent_def.provider_options or None,
        )
```

- [ ] **Step 6: Run targeted tests**

Run: `uv run pytest tests/sdk/test_subagent_v1.py -q -k "Coordinator or start_returns or freezes_config"`

Expected: pass after updating old blocking invoke assertions.

- [ ] **Step 7: Commit**

```bash
git add src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "feat: start subagent jobs asynchronously"
```

---

### Task 5: Rename SDK Subagent Tools And Remove Old Runtime Names

**Files:**
- Modify: `src/sdk/tools_core/subagent.py`
- Modify: `src/sdk/native_tools.py`
- Create: `tests/sdk/test_subagent_tools_async.py`
- Modify: `tests/sdk/test_tool_contracts.py`

- [ ] **Step 1: Write failing tool tests**

Create `tests/sdk/test_subagent_tools_async.py`:

```python
import pytest


def test_new_runtime_tools_registered():
    from src.sdk.native_tools import get_native_tools

    names = {t.name for t in get_native_tools()}
    assert "subagent_start" in names
    assert "subagent_check" in names
    assert "subagent_tasks" in names
    assert "subagent_invoke" not in names
    assert "subagent_progress" not in names


def test_subagent_start_returns_job_id(monkeypatch):
    from src.sdk.tools_core import subagent as mod

    class FakeCoordinator:
        def load_def(self, name):
            return object()
        async def start(self, agent_name, task, parent_id=None):
            return "job123"

    monkeypatch.setattr(mod, "get_coordinator", lambda user_id, workspace_id: FakeCoordinator(), raising=False)
    result = mod.subagent_start.invoke({
        "agent_name": "worker",
        "task": "do work",
        "user_id": "u",
        "workspace_id": "w",
    })
    assert "job123" in result
    assert "subagent_check" in result
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/sdk/test_subagent_tools_async.py -q`

Expected: fails because new tool names do not exist.

- [ ] **Step 3: Rewrite runtime tool names in `src/sdk/tools_core/subagent.py`**

Update module docstring to list 9 tools:

```text
Management: subagent_create, subagent_update, subagent_delete, subagent_list
Runtime: subagent_start, subagent_check, subagent_tasks, subagent_instruct, subagent_cancel
```

Replace `subagent_invoke` with:

```python
@tool
def subagent_start(
    agent_name: str,
    task: str,
    user_id: str,
    workspace_id: str = "personal",
    parent_id: str | None = None,
) -> str:
    """Start a subagent task asynchronously and return a job ID immediately."""
    from src.sdk.coordinator import get_coordinator

    coordinator = get_coordinator(user_id, workspace_id)
    existing = coordinator.load_def(agent_name)
    if existing is None:
        return f"Error: Subagent '{agent_name}' not found. Create it first with subagent_create."

    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            job_id = pool.submit(asyncio.run, coordinator.start(agent_name, task, parent_id=parent_id)).result()
    except RuntimeError:
        job_id = asyncio.run(coordinator.start(agent_name, task, parent_id=parent_id))

    return (
        f"Subagent '{agent_name}' started.\n\n"
        f"**Job ID**: {job_id}\n"
        f"**Task**: {task[:100]}\n\n"
        "Use `subagent_check` with the job ID to check status/results."
    )


subagent_start.annotations = ToolAnnotations(title="Start Subagent", open_world=True)
```

Replace `subagent_progress` with `subagent_check` for one job and add `subagent_tasks` for listing:

```python
@tool
def subagent_check(task_id: str, user_id: str = "default_user", workspace_id: str = "personal") -> str:
    """Check status/progress/result for a subagent job."""
    ...


@tool
def subagent_tasks(
    user_id: str = "default_user",
    workspace_id: str = "personal",
    status: str | None = None,
) -> str:
    """List active/recent subagent jobs."""
    ...
```

Use existing `subagent_progress` body as the source, but remove `parent_id` from `subagent_check`; `subagent_tasks` can support status filters.

- [ ] **Step 4: Update `subagent_create` and `subagent_update` signatures**

Add fields:

```python
provider_options: str | None = None
output_schema: str | None = None
handoff_instructions: str | None = None
artifact_policy: str | None = None
```

Parse JSON strings for `provider_options` and `output_schema`. Pass parsed values into `AgentDef`.

Validate using `validate_agent_def(agent_def, user_id=user_id, workspace_id=workspace_id)` before save. Return `Error: ...` with joined validation errors.

- [ ] **Step 5: Update `src/sdk/native_tools.py` registration**

Remove old names and register new names:

```python
from src.sdk.tools_core.subagent import (
    subagent_cancel,
    subagent_check,
    subagent_create,
    subagent_delete,
    subagent_instruct,
    subagent_list,
    subagent_start,
    subagent_tasks,
    subagent_update,
)
```

Register all nine. Do not register `subagent_invoke` or `subagent_progress`.

- [ ] **Step 6: Run targeted tests**

Run: `uv run pytest tests/sdk/test_subagent_tools_async.py tests/sdk/test_tool_contracts.py -q -k "subagent or ToolRegistry"`

Expected: pass after updating expectations for new names.

- [ ] **Step 7: Commit**

```bash
git add src/sdk/tools_core/subagent.py src/sdk/native_tools.py tests/sdk/test_subagent_tools_async.py tests/sdk/test_tool_contracts.py
git commit -m "feat: rename subagent runtime tools for async jobs"
```

---

### Task 6: Align HTTP Subagent API

**Files:**
- Modify: `src/http/routers/subagents.py`
- Modify: `tests/api/test_subagents.py`

- [ ] **Step 1: Write failing API tests**

Update `tests/api/test_subagents.py` with route expectations:

```python
def test_subagent_start_route(client):
    response = client.post(
        "/subagents/worker/start",
        params={"user_id": "test_user", "workspace_id": "personal"},
        json={"task": "do work"},
    )
    assert response.status_code in {200, 404}


def test_old_invoke_route_removed(client):
    response = client.post("/subagents/invoke", params={"name": "worker", "task": "do work"})
    assert response.status_code == 404


def test_job_instruction_route_exists(client):
    response = client.post(
        "/subagents/jobs/not-real/instructions",
        params={"user_id": "test_user", "workspace_id": "personal"},
        json={"instruction": "focus"},
    )
    assert response.status_code in {200, 404}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/api/test_subagents.py -q`

Expected: fails because routes differ.

- [ ] **Step 3: Update router request models**

In `src/http/routers/subagents.py`, add:

```python
from pydantic import BaseModel, Field


class SubagentCreateRequest(BaseModel):
    name: str
    description: str = ""
    model: str | None = None
    provider_options: dict | None = None
    skills: list[str] = Field(default_factory=list)
    tools: list[str] | None = None
    system_prompt: str | None = None
    max_llm_calls: int = 50
    cost_limit_usd: float = 1.0
    timeout_seconds: int = 300
    output_schema: dict | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None


class SubagentUpdateRequest(BaseModel):
    description: str | None = None
    model: str | None = None
    provider_options: dict | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None
    max_llm_calls: int | None = None
    cost_limit_usd: float | None = None
    timeout_seconds: int | None = None
    output_schema: dict | None = None
    handoff_instructions: str | None = None
    artifact_policy: str | None = None


class SubagentStartRequest(BaseModel):
    task: str
    parent_id: str | None = None


class SubagentInstructionRequest(BaseModel):
    instruction: str
```

- [ ] **Step 4: Replace routes**

Implement:

```text
GET    /subagents
POST   /subagents
PATCH  /subagents/{name}
DELETE /subagents/{name}
POST   /subagents/{name}/start
GET    /subagents/jobs
GET    /subagents/jobs/{job_id}
POST   /subagents/jobs/{job_id}/instructions
POST   /subagents/jobs/{job_id}/cancel
```

For `POST /subagents/{name}/start`:

```python
task_id = await coordinator.start(name, body.task, parent_id=body.parent_id)
return {"job_id": task_id, "status": "pending", "subagent": name}
```

For job detail, return row plus parsed result/progress:

```python
row = await db.get_task(job_id)
if row is None:
    raise HTTPException(status_code=404, detail="Job not found")
return {"job": row}
```

- [ ] **Step 5: Run API tests**

Run: `uv run pytest tests/api/test_subagents.py -q`

Expected: pass after updating tests to new route contract.

- [ ] **Step 6: Commit**

```bash
git add src/http/routers/subagents.py tests/api/test_subagents.py
git commit -m "feat: align subagent HTTP API with async jobs"
```

---

### Task 7: Update References, Tests, And Evaluations For New Names

**Files:**
- Modify: `tests/evaluation/test_subagent_skills.py`
- Modify: `tests/evaluation/personas.py`
- Modify: `tests/evaluation/test_25_personas.py`
- Modify: docs or prompts containing old names

- [ ] **Step 1: Find old names**

Run: `rg "subagent_invoke|subagent_progress" src tests docs AGENTS.md README.md`

Expected: results in tests/docs only after previous tasks.

- [ ] **Step 2: Replace old names**

Rules:

```text
subagent_invoke -> subagent_start
subagent_progress -> subagent_check for one job
subagent_progress listing behavior -> subagent_tasks
```

Update natural language evaluation prompts accordingly:

```text
"invoke subagent" -> "start subagent"
"check progress" -> "check subagent job"
```

- [ ] **Step 3: Run grep verification**

Run: `rg "subagent_invoke|subagent_progress" src tests docs AGENTS.md README.md`

Expected: no results except historical docs explicitly saying old names were removed. If such docs remain, they must say they are removed.

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/evaluation/test_subagent_skills.py tests/evaluation/test_25_personas.py tests/evaluation/test_smoke.py -q`

Expected: pass or skip external-provider tests according to existing test behavior.

- [ ] **Step 5: Commit**

```bash
git add tests/evaluation/test_subagent_skills.py tests/evaluation/personas.py tests/evaluation/test_25_personas.py docs AGENTS.md README.md
git commit -m "chore: update subagent references for async tool names"
```

---

### Task 8: Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run SDK/API tests**

Run: `uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py tests/api/test_subagents.py tests/sdk/test_tool_contracts.py -q`

Expected: all pass.

- [ ] **Step 2: Run lint on touched backend files**

Run: `uv run ruff check src/sdk/subagent_models.py src/sdk/work_queue.py src/sdk/coordinator.py src/sdk/tools_core/subagent.py src/sdk/native_tools.py src/http/routers/subagents.py tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py tests/api/test_subagents.py`

Expected: all checks pass.

- [ ] **Step 3: Run mypy on touched source if practical**

Run: `uv run mypy src/sdk/subagent_models.py src/sdk/work_queue.py src/sdk/coordinator.py src/sdk/tools_core/subagent.py src/http/routers/subagents.py`

Expected: no new errors. If existing project-level mypy config cannot target individual files cleanly, record exact output.

- [ ] **Step 4: Final grep**

Run: `rg "subagent_invoke|subagent_progress" src tests docs AGENTS.md README.md`

Expected: no active references to old tools.

- [ ] **Step 5: Commit final cleanup**

```bash
git add src tests docs AGENTS.md README.md
git commit -m "chore: verify async subagent migration"
```

---

## Deferred Work

Do not implement these in this plan:

- Schedule/webhook/file-change triggers.
- Main-agent wakeups from triggers.
- Trigger provenance in chat.
- Per-subagent credentials.
- Strict output-schema validation.
- First-class artifact storage.
- Full MCP runtime wiring unless it is already trivial from existing code.
