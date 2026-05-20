# Subagent Resilience & Safety Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the most critical subagent safety, resilience, and UX issues identified in `docs/SUBAGENT_AUDIT_2026-05-18.md`.

**Architecture:** Backend fixes are SDK-internal — add recovery hooks, bridge timeouts, and safer defaults. Flutter fixes wire up the disabled tool picker and add a model dropdown backed by `GET /models`. All changes follow TDD.

**Tech Stack:** Python 3.11+, aiosqlite, asyncio, Pydantic. Flutter/Dart with Riverpod.

**Test commands:**
- Backend: `uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py tests/api/test_subagents.py tests/storage/test_messages_store.py -v`
- Flutter: `flutter test test/features/workspace/workspace_panel_test.dart`
- Ruff: `uv run ruff check src/sdk/ src/http/routers/subagents.py tests/sdk/ tests/api/test_subagents.py`
- Flutter analyze: `flutter analyze lib/features/workspace/subagents_panel.dart lib/providers/subagent_provider.dart lib/models/subagent.dart lib/services/api_client.dart`

---

### Task 1: Stale Job Recovery on Server Restart

**Files:**
- Modify: `src/sdk/coordinator.py` (add `_recover_stale_jobs()` and call it)
- Test: `tests/sdk/test_subagent_v1.py` (add `TestStaleJobRecovery` class)

- [ ] **Step 1: Write failing test**

```python
class TestStaleJobRecovery:
    @pytest.mark.asyncio
    async def test_coordinator_recovers_stale_jobs_on_init(self, tmp_path):
        from datetime import UTC, datetime, timedelta

        db_dir = tmp_path / "subagents"
        db_dir.mkdir()

        # Direct DB: insert a stale RUNNING task
        db = await aiosqlite.connect(str(db_dir / "work_queue.db"))
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS work_queue (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL DEFAULT 'personal',
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress TEXT DEFAULT '{}',
                result TEXT,
                error TEXT,
                instructions TEXT DEFAULT '[]',
                config TEXT DEFAULT '{}',
                cancel_requested INTEGER DEFAULT 0,
                claimed_by TEXT,
                claimed_at TEXT,
                heartbeat_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        stale_time = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
        await db.execute(
            "INSERT INTO work_queue (id, user_id, workspace_id, agent_name, task, status, heartbeat_at, created_at, updated_at) "
            "VALUES ('stale-job', 'test_user', 'test_ws', 'helper', 'do thing', 'running', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (stale_time,)
        )
        await db.commit()
        await db.close()

        # Patch get_paths to use tmp dir
        with mock.patch('src.sdk.work_queue.get_paths', return_value=mock.MagicMock(
            work_queue_db=mock.MagicMock(return_value=db_dir / "work_queue.db")
        )):
            coordinator = SubagentCoordinator("test_user", "test_ws")
            db = await coordinator._get_db()
            task = await db.get_task("stale-job")
            assert task is not None
            assert task["status"] in ("failed", "cancelled")
```

Expected: FAIL — coordinator does not recover stale jobs.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestStaleJobRecovery::test_coordinator_recovers_stale_jobs_on_init -v
```

Expected: FAIL with task still "running".

- [ ] **Step 3: Add recovery call in coordinator `__init__`**

In `src/sdk/coordinator.py`, add to `__init__` and define `_recover_stale_jobs()`:

```python
def __init__(self, user_id: str, workspace_id: str = "personal"):
    self.user_id = user_id
    self.workspace_id = workspace_id
    self.settings = get_settings()
    self.base_path = get_paths(user_id, workspace_id=workspace_id).workspace_subagents_dir()
    self.base_path.mkdir(parents=True, exist_ok=True)
    self._db: WorkQueueDB | None = None
    self._background_tasks: set[asyncio.Task[Any]] = set()
    self._recovery_task: asyncio.Task[Any] | None = None
```

Add `_recover_stale_jobs()`:

```python
async def _recover_stale_jobs(self, max_age_seconds: int = 300) -> int:
    """Mark stale RUNNING/CANCELLING tasks as FAILED. Call on first DB access."""
    db = await self._get_db()
    count = await db.mark_stale_running_failed(max_age_seconds)
    if count > 0:
        logger.warning(
            "subagent.stale_tasks_recovered",
            {"count": count, "user_id": self.user_id, "workspace_id": self.workspace_id},
            user_id="system",
        )
    return count
```

Modify `_get_db()` to call recovery on first access:

```python
async def _get_db(self) -> WorkQueueDB:
    if self._db is None:
        self._db = await get_work_queue(self.user_id, self.workspace_id)
        if self._recovery_task is None:
            self._recovery_task = asyncio.create_task(self._recover_stale_jobs())
    return self._db
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestStaleJobRecovery::test_coordinator_recovers_stale_jobs_on_init -v
```

Expected: PASS.

- [ ] **Step 5: Run all subagent tests to confirm no regressions**

```bash
uv run pytest tests/sdk/test_subagent_v1.py -v
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "fix: recover stale subagent jobs on coordinator init"
```

---

### Task 2: Async Bridge Timeout + Error Recovery

**Files:**
- Modify: `src/sdk/tools_core/subagent.py` (`_run_async()` with timeout, `_get_loop()` with error recovery)
- Test: `tests/sdk/test_subagent_tools_async.py` (add `TestAsyncBridgeRecovery` class)

- [ ] **Step 1: Write failing test**

```python
class TestAsyncBridgeRecovery:
    def test_run_async_respects_timeout(self):
        import src.sdk.tools_core.subagent as subagent_module

        async def slow_coro():
            await asyncio.sleep(60)
            return "done"

        with mock.patch.object(subagent_module, "_TIMEOUT_SECONDS", 0.5):
            with pytest.raises(TimeoutError):
                subagent_module._run_async(slow_coro())

    def test_get_loop_creates_fresh_loop_when_closed(self):
        import src.sdk.tools_core.subagent as subagent_module

        subagent_module._loop = None
        loop1 = subagent_module._get_loop()
        loop1.close()
        loop2 = subagent_module._get_loop()
        assert loop2 is not None
        assert not loop2.is_closed()
        assert loop2 is not loop1
```

Expected: FAIL — no timeout, no closure recovery.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_subagent_tools_async.py::TestAsyncBridgeRecovery -v
```

Expected: FAIL on both tests.

- [ ] **Step 3: Add timeout and error handling to `_run_async()`**

In `src/sdk/tools_core/subagent.py`, replace the bridge:

```python
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()
_TIMEOUT_SECONDS = 300  # max total wait for any subagent tool call
_LOOP_ERROR_COUNT = 0
_MAX_LOOP_ERRORS = 3


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _LOOP_ERROR_COUNT
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(target=_loop.run_forever, daemon=True)
            thread.start()
            _LOOP_ERROR_COUNT = 0
        return _loop


def _run_async(coro: Any) -> Any:
    global _LOOP_ERROR_COUNT

    try:
        loop = _get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=_TIMEOUT_SECONDS)
    except TimeoutError:
        _LOOP_ERROR_COUNT += 1
        raise TimeoutError(
            f"Subagent tool call timed out after {_TIMEOUT_SECONDS}s"
        )
    except Exception as e:
        _LOOP_ERROR_COUNT += 1
        logger.error(
            "subagent.bridge_error",
            {"error": str(e), "error_type": type(e).__name__,
             "error_count": _LOOP_ERROR_COUNT},
            user_id="system",
        )
        if _LOOP_ERROR_COUNT >= _MAX_LOOP_ERRORS:
            with _loop_lock:
                if _loop and not _loop.is_closed():
                    _loop.call_soon_threadsafe(_loop.stop)
            _loop = None
        raise
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/sdk/test_subagent_tools_async.py::TestAsyncBridgeRecovery -v
```

Expected: PASS.

- [ ] **Step 5: Run all subagent tool tests**

```bash
uv run pytest tests/sdk/test_subagent_tools_async.py -v
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/tools_core/subagent.py tests/sdk/test_subagent_tools_async.py
git commit -m "fix: add timeout and error recovery to subagent async bridge"
```

---

### Task 3: Safer Default Tool Restrictions

**Files:**
- Modify: `src/sdk/subagent_models.py` (add `DEFAULT_SAFE_DENIED_TOOLS` constant)
- Modify: `src/sdk/coordinator.py` (use safer default in `load_def()` and `_build_tools_for_subagent()`)
- Test: `tests/sdk/test_subagent_v1.py` (add `TestSafeDefaults` class)
- Test: `tests/sdk/test_subagent_tools_async.py` (add test that create respects defaults)

- [ ] **Step 1: Add safer defaults constant**

In `src/sdk/subagent_models.py`:

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

# Tools denied from subagents by default for safety.
# These are powerful/destructive tools that a subagent should not have
# unless explicitly requested by the user.
DEFAULT_SAFE_DENIED_TOOLS = [
    "shell_execute",
    "email_send",
    "email_connect",
    "email_disconnect",
    "browser_click",
    "browser_input",
    "browser_type",
    "browser_eval",
    "browser_open",
    "browser_keys",
]
```

- [ ] **Step 2: Apply safe defaults in `load_def()`**

In `src/sdk/coordinator.py`, modify `load_def()`:

```python
from src.sdk.subagent_models import (
    DEFAULT_DISALLOWED_TOOLS,
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_SAFE_DENIED_TOOLS,
    AgentDef,
    SubagentResult,
    TaskCancelledError,
    TaskStatus,
)
```

```python
def load_def(self, name: str) -> AgentDef | None:
    # 1. Workspace-scoped
    config_path = self.base_path / name / "config.yaml"
    if config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
            safe_denied = list(DEFAULT_DISALLOWED_TOOLS) + list(DEFAULT_SAFE_DENIED_TOOLS)
            data.setdefault("disallowed_tools", safe_denied)
            return AgentDef(**data)
        except Exception as e:
            logger.warning("subagent.load_failed", {"name": name, "error": str(e)}, user_id=self.user_id)

    # 2. User-global fallback
    try:
        from src.storage.paths import DataPaths
        global_path = DataPaths(user_id=self.user_id).global_subagents_dir() / name / "config.yaml"
        if global_path.exists():
            data = yaml.safe_load(global_path.read_text()) or {}
            safe_denied = list(DEFAULT_DISALLOWED_TOOLS) + list(DEFAULT_SAFE_DENIED_TOOLS)
            data.setdefault("disallowed_tools", safe_denied)
            return AgentDef(**data)
    except Exception as e:
        logger.warning("subagent.load_failed", {"name": name, "error": str(e)}, user_id=self.user_id)

    return None
```

- [ ] **Step 3: Write failing tests**

```python
class TestSafeDefaults:
    def test_load_def_applies_safe_disallowed_tools_by_default(self, tmp_path):
        agent_dir = tmp_path / "subagent" / "agent"
        agent_dir.mkdir(parents=True)
        config = agent_dir / "config.yaml"
        config.write_text(yaml.dump({"name": "agent", "description": "test"}))

        coordinator = mock.MagicMock(spec=SubagentCoordinator)
        coordinator.base_path = tmp_path / "subagent"
        coordinator.user_id = "test_user"

        from src.sdk.coordinator import SubagentCoordinator as SC
        coordinator.load_def = lambda name: SC.load_def(coordinator, name)

        agent_def = coordinator.load_def("agent")
        assert agent_def is not None
        assert "shell_execute" in agent_def.disallowed_tools
        assert "email_send" in agent_def.disallowed_tools
        assert "browser_click" in agent_def.disallowed_tools

    def test_explicit_tools_overrides_safe_defaults(self, tmp_path):
        agent_dir = tmp_path / "subagent" / "agent2"
        agent_dir.mkdir(parents=True)
        config = agent_dir / "config.yaml"
        config.write_text(yaml.dump({
            "name": "agent2",
            "description": "test",
            "tools": ["shell_execute", "memory_search", "files_list"],
            "disallowed_tools": ["subagent_create"]
        }))

        coordinator = mock.MagicMock(spec=SubagentCoordinator)
        coordinator.base_path = tmp_path / "subagent"
        coordinator.user_id = "test_user"

        from src.sdk.coordinator import SubagentCoordinator as SC
        coordinator.load_def = lambda name: SC.load_def(coordinator, name)

        agent_def = coordinator.load_def("agent2")
        assert agent_def is not None
        assert "shell_execute" in agent_def.tools
        assert "shell_execute" not in agent_def.disallowed_tools
```

Expected: FAIL — `shell_execute` not in `disallowed_tools` by default.

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestSafeDefaults -v
```

Expected: FAIL.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestSafeDefaults -v
```

Expected: PASS.

- [ ] **Step 6: Run all subagent tests**

```bash
uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add src/sdk/subagent_models.py src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "fix: deny shell_execute, email_send, browser_* from subagents by default"
```

---

### Task 4: Wire Up Flutter Tool Picker

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart` (wire `onChanged`, track selected tools, pass to `createAgent`)
- Test: `flutter_app/test/features/workspace/workspace_panel_test.dart` (add `TestToolPicker`)

- [ ] **Step 1: Write failing test**

```dart
void main() {
  group('TestToolPicker', () {
    testWidgets('create dialog tool picker shows toggles that work', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: createTestApp(const SubagentsPanel()),
        ),
      );

      // Tap add button
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Verify tool checkboxes exist and are interactive
      final checkboxes = tester.widgetList<CheckboxListTile>(
        find.byType(CheckboxListTile),
      );
      expect(checkboxes.isNotEmpty, true);

      // Verify at least one checkbox has an onChanged that isn't null
      final first = checkboxes.first;
      expect(first.onChanged, isNotNull);
    });
  });
}
```

Expected: FAIL — `onChanged` is `null`.

- [ ] **Step 2: Run test to verify it fails**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog tool picker shows toggles that work'
```

Expected: FAIL.

- [ ] **Step 3: Wire up the tool picker**

In `subagents_panel.dart`, inside the create dialog's `StatefulBuilder`:

Add a `selectedTools` state variable:

```dart
Set<String> selectedTools = allTools != null ? allTools.toSet() : {};
```

Replace the tool list rendering:

```dart
if (allTools != null) ...[
  const SizedBox(height: 10),
  Row(
    children: [
      Text('Tools', style: AppTypography.caption.copyWith(
        color: AppColors.textSecondary,
      )),
      const Spacer(),
      TextButton(
        onPressed: () => setDialogState(() {
          selectedTools = allTools.toSet();
        }),
        child: const Text('Select All', style: TextStyle(fontSize: 11)),
      ),
      TextButton(
        onPressed: () => setDialogState(() => selectedTools = {}),
        child: const Text('Clear All', style: TextStyle(fontSize: 11)),
      ),
    ],
  ),
  const SizedBox(height: 4),
  SizedBox(
    height: 120,
    child: ListView(
      children: allTools
          .where((t) => !t.startsWith('subagent_'))
          .map((t) => CheckboxListTile(
            dense: true,
            value: selectedTools.contains(t),
            title: Text(t, style: AppTypography.caption.copyWith(fontSize: 12)),
            onChanged: (checked) {
              setDialogState(() {
                if (checked == true) {
                  selectedTools.add(t);
                } else {
                  selectedTools.remove(t);
                }
              });
            },
          ))
          .toList(),
    ),
  ),
],
```

Modify `createAgent()` call to pass selected tools:

```dart
await ref.read(subagentProvider.notifier).createAgent(
  name: name,
  description: description,
  model: model,
  tools: selectedTools.isNotEmpty ? selectedTools.toList() : null,
  skills: skills,
  systemPrompt: systemPrompt,
  ...
);
```

Ensure `selectedTools` is captured in the closure properly by moving it into the builder state.

- [ ] **Step 4: Run test to verify it passes**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog tool picker shows toggles that work'
```

Expected: PASS.

- [ ] **Step 5: Run all workspace panel tests**

```bash
flutter test test/features/workspace/workspace_panel_test.dart
```

Expected: All pass.

- [ ] **Step 6: Run Flutter analyzer**

```bash
flutter analyze lib/features/workspace/subagents_panel.dart
```

Expected: Only existing `Radio` deprecation infos.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart flutter_app/test/features/workspace/workspace_panel_test.dart
git commit -m "feat: wire up subagent tool picker with select all/clear"
```

---

### Task 5: Model Dropdown with GET /models

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart` (replace model TextField with autocomplete dropdown)
- Modify: `flutter_app/lib/services/api_client.dart` (add `getModels()` if not present)
- Test: `flutter_app/test/features/workspace/workspace_panel_test.dart` (add model dropdown test)

- [ ] **Step 1: Write failing test**

```dart
group('TestModelDropdown', () {
  testWidgets('create dialog shows model dropdown when models loaded', (tester) async {
    final subagentNotifier = SubagentNotifier(mockApiClient);
    
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          subagentProvider.overrideWith((ref) => subagentNotifier),
        ],
        child: createTestApp(const SubagentsPanel()),
      ),
    );

    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    // Should find an Autocomplete widget, not a plain TextField for model
    expect(find.byType(Autocomplete<String>), findsOneWidget);
  });
});
```

Expected: FAIL — model field is a plain `TextField`.

- [ ] **Step 2: Run test to verify it fails**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog shows model dropdown when models loaded'
```

Expected: FAIL.

- [ ] **Step 3: Add API method if needed**

Check `flutter_app/lib/services/api_client.dart` — if `getModels()` exists, skip this step. If not:

```dart
Future<List<String>> getModels() async {
  final response = await _client.get(Uri.parse('$_baseUrl/models'));
  final data = jsonDecode(response.body) as Map<String, dynamic>;
  final models = data['models'] as List<dynamic>;
  return models.map((m) => m['id'].toString()).toList();
}
```

- [ ] **Step 4: Replace model TextField with Autocomplete**

In `subagents_panel.dart`, add to create dialog state:

```dart
List<String> _modelOptions = [];
bool _modelsLoaded = false;
```

Add a model fetch call before the dialog body:

```dart
if (!_modelsLoaded) {
  try {
    final api = ApiClient();
    _modelOptions = await api.getModels();
  } catch (_) {
    _modelOptions = [];
  }
  _modelsLoaded = true;
}
```

Replace the model `TextField` with:

```dart
Autocomplete<String>(
  optionsBuilder: (textEditingValue) {
    if (textEditingValue.text.isEmpty) return _modelOptions;
    return _modelOptions.where((option) =>
        option.toLowerCase().contains(textEditingValue.text.toLowerCase()));
  },
  initialValue: TextEditingValue(text: modelCtrl.text),
  onSelected: (selection) {
    modelCtrl.text = selection;
  },
  fieldViewBuilder: (context, textEditingController, focusNode, onFieldSubmitted) {
    textEditingController.text = modelCtrl.text;
    return TextField(
      controller: textEditingController,
      focusNode: focusNode,
      decoration: const InputDecoration(
        labelText: 'Model',
        border: OutlineInputBorder(),
        isDense: true,
      ),
      style: const TextStyle(fontSize: 13),
      onChanged: (v) {
        modelCtrl.text = v;
        textEditingController.text = v;
      },
    );
  },
),
```

- [ ] **Step 5: Run test to verify it passes**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog shows model dropdown when models loaded'
```

Expected: PASS.

- [ ] **Step 6: Run Flutter analyzer**

```bash
flutter analyze lib/features/workspace/subagents_panel.dart lib/services/api_client.dart
```

Expected: Only existing `Radio` deprecation infos.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart flutter_app/lib/services/api_client.dart flutter_app/test/features/workspace/workspace_panel_test.dart
git commit -m "feat: replace model text field with autocomplete dropdown"
```

---

### Task 6: `load_def()` Error Distinction

**Files:**
- Modify: `src/sdk/coordinator.py` (`load_def()` returns tuple or raises specific exceptions)
- Test: `tests/sdk/test_subagent_v1.py` (add `TestLoadDefErrors` class)

- [ ] **Step 1: Write failing test**

```python
class TestLoadDefErrors:
    @pytest.mark.asyncio
    async def test_load_def_returns_none_for_missing_agent(self, tmp_path):
        coordinator = SubagentCoordinator("test_user")
        coordinator.base_path = tmp_path / "subagent"
        coordinator.base_path.mkdir(parents=True)

        result = coordinator.load_def("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_def_distinguishes_corrupt_config(self, tmp_path):
        agent_dir = tmp_path / "subagent" / "corrupt"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("{{{ invalid yaml")

        coordinator = SubagentCoordinator("test_user")
        coordinator.base_path = tmp_path / "subagent"
        coordinator.user_id = "test_user"

        result = coordinator.load_def("corrupt")
        # load_def should still return None for corrupt (backward compat)
        # BUT the caller should be able to distinguish via a separate method
        assert result is None
        assert not coordinator.is_valid("corrupt")  # new method
```

Expected: FAIL — `is_valid()` doesn't exist, `load_def()` swallows the YAML error silently with no way to check.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestLoadDefErrors -v
```

Expected: FAIL (AttributeError on `is_valid`).

- [ ] **Step 3: Add `is_valid()` method to coordinator**

In `src/sdk/coordinator.py`:

```python
def is_valid(self, name: str) -> bool:
    """Check if a subagent config exists and is parseable (no exceptions).
    
    Returns False for: missing agent, corrupt YAML, or invalid AgentDef.
    Returns True for: valid, loadable AgentDef.
    """
    config_path = self.base_path / name / "config.yaml"
    if not config_path.exists():
        # check global fallback silently - don't report missing as "invalid"
        try:
            from src.storage.paths import DataPaths
            global_path = DataPaths(user_id=self.user_id).global_subagents_dir() / name / "config.yaml"
            if not global_path.exists():
                return False
        except Exception:
            return False

    try:
        agent_def = self.load_def(name)
        return agent_def is not None
    except Exception:
        return False
```

Also improve `load_def()` logging to differentiate corruption:

```python
def load_def(self, name: str) -> AgentDef | None:
    config_path = self.base_path / name / "config.yaml"
    if config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
            safe_denied = list(DEFAULT_DISALLOWED_TOOLS) + list(DEFAULT_SAFE_DENIED_TOOLS)
            data.setdefault("disallowed_tools", safe_denied)
            return AgentDef(**data)
        except yaml.YAMLError as e:
            logger.error(
                "subagent.corrupt_yaml",
                {"name": name, "path": str(config_path), "error": str(e)},
                user_id=self.user_id,
            )
            return None
        except Exception as e:
            logger.error(
                "subagent.load_failed",
                {"name": name, "error": str(e), "error_type": type(e).__name__},
                user_id=self.user_id,
            )
            return None

    # Global fallback (same improved error handling)
    ...
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestLoadDefErrors -v
```

Expected: PASS.

- [ ] **Step 5: Run all subagent tests**

```bash
uv run pytest tests/sdk/test_subagent_v1.py -v
```

Expected: All 60+ tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "fix: distinguish corrupt/missing subagent config in load_def"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py tests/api/test_subagents.py tests/storage/test_messages_store.py -v
```

Expected: All pass.

- [ ] **Step 2: Run ruff**

```bash
uv run ruff check src/sdk/coordinator.py src/sdk/subagent_models.py src/sdk/tools_core/subagent.py src/http/routers/subagents.py tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py tests/api/test_subagents.py tests/storage/test_messages_store.py
```

Expected: All checks passed.

- [ ] **Step 3: Run all Flutter tests**

```bash
cd flutter_app && flutter test test/features/workspace/workspace_panel_test.dart
```

Expected: All pass.

- [ ] **Step 4: Run Flutter analyzer**

```bash
cd flutter_app && flutter analyze lib/features/workspace/subagents_panel.dart lib/providers/subagent_provider.dart lib/models/subagent.dart lib/services/api_client.dart
```

Expected: Only existing `Radio` deprecation infos.

- [ ] **Step 5: Commit final verification**

```bash
git add -A
git commit -m "chore: final verification after subagent safety fixes"
```
