# Subagent P2/P3 Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix doom loop false positives, add missing-middleware logging, prune terminal job state, and add Flutter subagent tests + client-side name validation.

**Architecture:** Backend changes touch `middleware_progress.py` (hash tool inputs instead of results) and `coordinator.py` (log ObservationMiddleware import failure). Flutter changes touch `subagent_provider.dart` (cap accumulated terminal jobs) and `subagents_panel.dart` (name regex validation, error display). Tests follow existing patterns in `test_subagent_v1.py` and `workspace_panel_test.dart`.

**Tech Stack:** Python 3.11+, aiosqlite, asyncio. Flutter/Dart with Riverpod, mocktail.

**Test commands:**
- Backend: `uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py -v`
- Flutter: `flutter test test/features/workspace/workspace_panel_test.dart`
- Ruff: `uv run ruff check src/sdk/middleware_progress.py src/sdk/coordinator.py tests/sdk/test_subagent_v1.py`
- Flutter analyze: `flutter analyze lib/features/workspace/subagents_panel.dart lib/providers/subagent_provider.dart`

---

### Task 1: Fix Doom Loop Hash to Use Tool Input Args

**Files:**
- Modify: `src/sdk/middleware_progress.py:25-85` (replace result-based hashing with input-based)
- Test: `tests/sdk/test_subagent_v1.py` (add `TestDoomLoopDetection` class with 3 tests)

**The bug:** `ProgressMiddleware.abefore_model()` hashes the `content` field of the last `tool`-role message (the **result**), not the tool call **arguments**. String-returning tools like `shell_execute` always produce non-JSON results, so `tool_args` falls back to `{}` and every call hashes identically — false positive doom loops.

**The fix:** Walk `state.messages` backwards to find the paired assistant message containing the tool call block, extract `input` from the tool call block, and hash that instead.

- [ ] **Step 1: Write 3 failing tests**

Add class `TestDoomLoopDetection` to `tests/sdk/test_subagent_v1.py`:

```python
class TestDoomLoopDetection:
    """Verify doom loop detection uses tool call args, not result content."""

    @pytest.mark.asyncio
    async def test_doom_loop_detects_same_tool_with_same_args(self):
        from unittest import mock

        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware, DOOM_THRESHOLD
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-1", mock_db)

        state = AgentState()
        # Simulate DOOM_THRESHOLD identical tool calls
        for i in range(DOOM_THRESHOLD):
            state.add_message(Message.assistant(
                [{"type": "tool_call", "name": "files_read", "input": {"path": "/a.txt"}}]
            ))
            state.add_message(Message.tool("file contents", name="files_read"))

        result = await mw.abefore_model(state)
        assert result is not None
        assert result.get("stuck") is True

    @pytest.mark.asyncio
    async def test_doom_loop_distinguishes_same_tool_with_different_args(self):
        from unittest import mock

        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware, DOOM_THRESHOLD
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-2", mock_db)

        state = AgentState()
        # Different paths, same tool — should NOT trigger doom loop
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "files_read", "input": {"path": "/a.txt"}}]
        ))
        state.add_message(Message.tool("content A", name="files_read"))
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "files_read", "input": {"path": "/b.txt"}}]
        ))
        state.add_message(Message.tool("content B", name="files_read"))
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "files_read", "input": {"path": "/c.txt"}}]
        ))
        state.add_message(Message.tool("content C", name="files_read"))

        result = await mw.abefore_model(state)
        assert result is not None
        assert result.get("stuck") is False

    @pytest.mark.asyncio
    async def test_doom_loop_distinguishes_string_returning_tools(self):
        from unittest import mock

        from src.sdk.messages import Message
        from src.sdk.middleware_progress import ProgressMiddleware, DOOM_THRESHOLD
        from src.sdk.state import AgentState

        mock_db = mock.AsyncMock()
        mw = ProgressMiddleware("task-3", mock_db)

        state = AgentState()
        # String results, args differ — should NOT trigger doom loop
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "shell_execute", "input": {"command": "ls"}}]
        ))
        state.add_message(Message.tool("file1\nfile2", name="shell_execute"))
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "shell_execute", "input": {"command": "pwd"}}]
        ))
        state.add_message(Message.tool("/home/user", name="shell_execute"))
        state.add_message(Message.assistant(
            [{"type": "tool_call", "name": "shell_execute", "input": {"command": "date"}}]
        ))
        state.add_message(Message.tool("Mon May 19", name="shell_execute"))

        result = await mw.abefore_model(state)
        assert result is not None
        assert result.get("stuck") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestDoomLoopDetection -v
```

Expected: `test_doom_loop_distinguishes_same_tool_with_different_args` FAILS and `test_doom_loop_distinguishes_string_returning_tools` FAILS — both wrongly detect doom loops. `test_doom_loop_detects_same_tool_with_same_args` passes or fails depending on current behavior.

- [ ] **Step 3: Rewrite the hashing logic in `middleware_progress.py`**

Replace `abefore_model()` entirely:

```python
async def abefore_model(self, state: AgentState) -> dict[str, Any] | None:
    tool_results = [m for m in state.messages if m.role == "tool"]
    if not tool_results:
        return None

    last_result = tool_results[-1]
    tool_name = getattr(last_result, "name", None) or "unknown"
    self._steps_completed += 1

    tool_args = self._extract_tool_call_args(state, tool_name)
    args_json = json.dumps(tool_args, sort_keys=True, ensure_ascii=True)
    call_hash = f"{tool_name}:{hashlib.md5(args_json.encode()).hexdigest()[:8]}"

    self._last_tool_calls.append(call_hash)
    if len(self._last_tool_calls) > DOOM_THRESHOLD:
        self._last_tool_calls = self._last_tool_calls[-DOOM_THRESHOLD:]

    is_stuck = (
        len(self._last_tool_calls) >= DOOM_THRESHOLD
        and len(set(self._last_tool_calls)) == 1
    )

    try:
        await self.db.update_progress(self.task_id, {
            "steps_completed": self._steps_completed,
            "phase": "executing",
            "message": f"Called {tool_name}",
            "stuck": is_stuck,
        })

        if is_stuck:
            await self.db.add_instruction(
                self.task_id,
                "Doom loop detected: same tool called 3x with identical args. "
                "Consider cancelling or redirecting this task.",
            )
    except Exception as e:
        logger.warning(
            "subagent.progress_update_failed",
            {"task_id": self.task_id, "error": str(e)},
        )

    return None

def _extract_tool_call_args(self, state: AgentState, tool_name: str) -> dict[str, Any]:
    """Walk messages backwards to find the tool call block for the last tool result."""
    for msg in reversed(state.messages):
        if msg.role != "assistant":
            continue
        content = msg.content
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_call" and block.get("name") == tool_name:
                return dict(block.get("input") or {})
    return {}
```

Add `import hashlib, json` and remove any result-parsing code. The old `try: parsed = json.loads(...)` block and the `args_json` fallback to `{}` are removed.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestDoomLoopDetection -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run all subagent tests for regressions**

```bash
uv run pytest tests/sdk/test_subagent_v1.py -q
```

Expected: All ~78 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/middleware_progress.py tests/sdk/test_subagent_v1.py
git commit -m "fix: hash tool call args for doom loop detection, not result content"
```

---

### Task 2: Log ObservationMiddleware Import Failure

**Files:**
- Modify: `src/sdk/coordinator.py:372-374` (replace silent try/except with explicit import and logging)
- Test: `tests/sdk/test_subagent_v1.py` (add `TestObservationMiddlewareAwareness` class)

**The problem:** `_run_loop()` does `from src.sdk.middleware_observation import ObservationMiddleware` inside the method body. Currently this import is not wrapped in try/except in `_run_loop()` but it appears the import is unconditional. Looking at the code more carefully, the audit may have been wrong — the import is NOT wrapped. Let me check.

Actually, looking at the coordinator code, the import is bare:
```python
from src.sdk.middleware_observation import ObservationMiddleware
```
No try/except. If the module doesn't exist, the subagent crashes with ImportError, not silently misses. So this finding may be stale. Let me instead add a guard that logs a clear message if the middleware is not available, rather than crashing.

- [ ] **Step 1: Write failing test**

```python
class TestObservationMiddlewareAwareness:
    @pytest.mark.asyncio
    async def test_run_loop_logs_warning_when_observation_middleware_missing(
        self, monkeypatch
    ):
        from unittest import mock

        import src.sdk.coordinator as coordinator_module
        from src.sdk.coordinator import SubagentCoordinator
        from src.sdk.subagent_models import AgentDef
        from src.sdk.work_queue import WorkQueueDB

        # Make the import fail
        def _raise_import_error(*_a, **_kw):
            raise ImportError("no such module")

        monkeypatch.setattr(
            coordinator_module, "ObservationMiddleware",
            _raise_import_error,
        )

        mock_db = mock.MagicMock(spec=WorkQueueDB)
        mock_db.update_progress = mock.AsyncMock()
        mock_db.add_instruction = mock.AsyncMock()

        coordinator = SubagentCoordinator("test_user")
        coordinator.user_id = "test_user"
        coordinator.workspace_id = "personal"

        with mock.patch.object(coordinator_module, "logger") as mock_logger:
            agent_def = AgentDef(name="test", description="test")
            coordinator._run_loop = coordinator_module.SubagentCoordinator._run_loop
            try:
                await coordinator._run_loop(
                    coordinator, "task-1", agent_def, "do thing", mock_db
                )
            except Exception:
                pass

            mock_logger.warning.assert_any_call(
                "subagent.missing_observation_middleware",
                mock.ANY,
                user_id=mock.ANY,
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestObservationMiddlewareAwareness -v
```

Expected: FAIL — no warning logged.

- [ ] **Step 3: Add import guard with logging in `_run_loop()`**

In `src/sdk/coordinator.py`, modify `_run_loop()` around the ObservationMiddleware import (line ~373):

```python
try:
    from src.sdk.middleware_observation import ObservationMiddleware
except ImportError:
    logger.warning(
        "subagent.missing_observation_middleware",
        {"task_id": task_id, "agent": agent_def.name},
        user_id=self.user_id,
    )
    ObservationMiddleware = None

# ... later, when building middlewares:
middlewares = [progress_mw, instruction_mw, summarization_mw]
if ObservationMiddleware is not None:
    try:
        observation_mw = ObservationMiddleware(
            user_id=self.user_id, workspace_id=self.workspace_id
        )
        middlewares.append(observation_mw)
    except Exception as e:
        logger.warning(
            "subagent.observation_middleware_init_failed",
            {"task_id": task_id, "error": str(e)},
            user_id=self.user_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/sdk/test_subagent_v1.py::TestObservationMiddlewareAwareness -v
```

Expected: PASS.

- [ ] **Step 5: Run all subagent tests**

```bash
uv run pytest tests/sdk/test_subagent_v1.py -q
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
git commit -m "fix: log warning when ObservationMiddleware is unavailable"
```

---

### Task 3: Prune Terminal Jobs from Flutter Provider State

**Files:**
- Modify: `flutter_app/lib/providers/subagent_provider.dart` (add `MAX_TERMINAL_JOBS` constant, prune on poll)
- Test: `flutter_app/test/features/workspace/workspace_panel_test.dart` (add `TestTerminalJobPruning`)

**The problem:** `SubagentNotifier.activeJobs` accumulates completed/failed/cancelled jobs forever. In a session where a user starts 20 subagent tasks, 20 entries sit in memory consuming ~20KB — not a crisis, but messy.

**The fix:** Cap terminal jobs at `MAX_TERMINAL_JOBS = 10` and trim oldest.

- [ ] **Step 1: Write failing test**

Add to `workspace_panel_test.dart`:

```dart
testWidgets('prunes terminal jobs after max threshold', (tester) async {
  final api = MockApiClient();
  when(() => api.listSubagents(workspaceId: 'test12345')).thenAnswer(
    (_) async => [],
  );

  final container = ProviderContainer(
    overrides: [apiClientProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  container.read(currentWorkspaceIdProvider.notifier).state = 'test12345';

  // Inject 15 terminal jobs directly into state
  final notifier = container.read(subagentProvider.notifier);
  final jobs = List.generate(
    15,
    (i) => SubagentJob(
      jobId: 'job-$i',
      agentName: 'agent',
      task: 'task',
      status: 'completed',
      workspaceId: 'test12345',
      createdAt: DateTime(2026, 1, i + 1),
    ),
  );

  // Manually populate state by calling _updateJob 15 times,
  // then verify prune caps terminal count
  for (var i = 0; i < 15; i++) {
    notifier._updateJob(SubagentJob(
      jobId: 'job-$i',
      agentName: 'agent',
      task: 'task',
      status: 'completed',
      workspaceId: 'test12345',
      createdAt: DateTime(2026, 1, i + 1),
    ));
  }

  expect(notifier.state.activeJobs.length, 10);
  // Oldest should be dropped (job-0 through job-4 removed)
  expect(notifier.state.activeJobs.containsKey('job-0'), isFalse);
  expect(notifier.state.activeJobs.containsKey('job-14'), isTrue);
});
```

Expected: FAIL — `_pruneTerminalJobs()` doesn't exist, or doesn't prune.

- [ ] **Step 2: Run test to verify it fails**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'prunes terminal jobs after max threshold'
```

Expected: FAIL.

- [ ] **Step 3: Implement pruning**

In `subagent_provider.dart`:

```dart
static const int _maxTerminalJobs = 10;

void _pruneTerminalJobs() {
  final terminal = <String, SubagentJob>{};
  final active = <String, SubagentJob>{};
  for (final entry in state.activeJobs.entries) {
    if (entry.value.isTerminal) {
      terminal[entry.key] = entry.value;
    } else {
      active[entry.key] = entry.value;
    }
  }

  if (terminal.length > _maxTerminalJobs) {
    final sorted = terminal.entries.toList()
      ..sort((a, b) => (a.value.createdAt ?? DateTime(2000))
          .compareTo(b.value.createdAt ?? DateTime(2000)));
    final kept = sorted.skip(sorted.length - _maxTerminalJobs);
    state = state.copyWith(
      activeJobs: {
        ...active,
        for (final e in kept) e.key: e.value,
      },
    );
  }
}
```

Call `_pruneTerminalJobs()` at the end of `_updateJob()` and `_ensurePolling()` tick handler:

```dart
Future<void> _updateJob(SubagentJob job) async {
  state = state.copyWith(
    activeJobs: {...state.activeJobs, job.jobId: job},
  );
  _pruneTerminalJobs();  // add this
}
```

```dart
// In _ensurePolling's Timer callback, after poll:
_pruneTerminalJobs();  // add this
```

- [ ] **Step 4: Run test to verify it passes**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'prunes terminal jobs after max threshold'
```

Expected: PASS.

- [ ] **Step 5: Run all workspace panel tests**

```bash
flutter test test/features/workspace/workspace_panel_test.dart
```

Expected: All pass (10 existing + 1 new = 11).

- [ ] **Step 6: Run Flutter analyzer**

```bash
flutter analyze lib/providers/subagent_provider.dart
```

Expected: Clean.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/providers/subagent_provider.dart flutter_app/test/features/workspace/workspace_panel_test.dart
git commit -m "fix: prune terminal subagent jobs to max 10 in provider state"
```

---

### Task 4: Flutter Client-Side Name Regex Validation

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart` (add validation to create/edit dialog submit)
- Test: `flutter_app/test/features/workspace/workspace_panel_test.dart` (add test for invalid name rejection)

**The problem:** `AgentDef.name` has backend regex `^[a-zA-Z0-9_-]+$`. Flutter sends arbitrary names without client-side validation, producing opaque 422 errors. The error message says `"Invalid user_id..."` which is confusing.

**The fix:** Validate name in the dialog submit handler and show an inline error.

- [ ] **Step 1: Write failing test**

```dart
testWidgets('create dialog rejects invalid name with inline error', (tester) async {
  final api = MockApiClient();
  when(() => api.listSubagents(workspaceId: any(named: 'workspaceId')))
      .thenAnswer((_) async => []);
  when(() => api.listToolNames()).thenAnswer((_) async => ['time_get']);
  when(() => api.createSubagent(
    name: any(named: 'name'),
    description: any(named: 'description'),
    model: any(named: 'model'),
    scope: any(named: 'scope'),
    tools: any(named: 'tools'),
    skills: any(named: 'skills'),
    systemPrompt: any(named: 'systemPrompt'),
    maxLlmCalls: any(named: 'maxLlmCalls'),
    costLimitUsd: any(named: 'costLimitUsd'),
    timeoutSeconds: any(named: 'timeoutSeconds'),
    workspaceId: any(named: 'workspaceId'),
  )).thenAnswer((_) async => {});

  final container = ProviderContainer(
    overrides: [apiClientProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  container.read(currentWorkspaceIdProvider.notifier).state = 'personal';

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: Scaffold(body: SubagentsPanel())),
    ),
  );
  await tester.pump();

  await tester.tap(find.byIcon(Icons.add));
  await tester.pumpAndSettle();

  // Enter invalid name with spaces
  await tester.enterText(find.widgetWithText(TextField, 'Name *'), 'bad name');
  await tester.enterText(
    find.widgetWithText(TextField, 'Description *'),
    'Description',
  );
  await tester.tap(find.text('Create'));
  await tester.pumpAndSettle();

  // Dialog should still be open with error message
  expect(find.text('Name can only contain letters, numbers, hyphens, and underscores'),
      findsOneWidget);
  verifyNever(() => api.createSubagent(
    name: any(named: 'name'),
    description: any(named: 'description'),
    workspaceId: any(named: 'workspaceId'),
    model: any(named: 'model'),
    scope: any(named: 'scope'),
    tools: any(named: 'tools'),
    skills: any(named: 'skills'),
    systemPrompt: any(named: 'systemPrompt'),
    maxLlmCalls: any(named: 'maxLlmCalls'),
    costLimitUsd: any(named: 'costLimitUsd'),
    timeoutSeconds: any(named: 'timeoutSeconds'),
  ));
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog rejects invalid name with inline error'
```

Expected: FAIL — invalid name passes through to API call.

- [ ] **Step 3: Add validation constant and logic**

In `subagents_panel.dart`, add near the top of the file:

```dart
final _nameRegex = RegExp(r'^[a-zA-Z0-9_-]+$');
const _nameValidationMessage =
    'Name can only contain letters, numbers, hyphens, and underscores';
```

In `_showCreateDialog()`, add a `String? nameError` local variable:

```dart
String? nameError;
```

In the submit handler, before the `submitting` block, add validation:

```dart
final name = nameCtrl.text.trim();
final description = descriptionCtrl.text.trim();
if (name.isEmpty || description.isEmpty) return;

if (!_nameRegex.hasMatch(name)) {
  setDialogState(() => nameError = _nameValidationMessage);
  return;
}
setDialogState(() => nameError = null);
```

Add an error display below the name TextField:

```dart
TextField(
  controller: nameCtrl,
  decoration: InputDecoration(
    labelText: 'Name *',
    hintText: 'my-researcher',
    errorText: nameError,
    border: const OutlineInputBorder(),
  ),
  onChanged: (_) =>
      setDialogState(() => nameError = null),
),
```

(Replace the existing name TextField with this. The `onChanged` clears error when user starts typing.)

Also add the same validation in `_showEditDialog()` (same pattern, different controller name).

- [ ] **Step 4: Run test to verify it passes**

```bash
flutter test test/features/workspace/workspace_panel_test.dart --plain-name 'create dialog rejects invalid name with inline error'
```

Expected: PASS.

- [ ] **Step 5: Run all workspace panel tests**

```bash
flutter test test/features/workspace/workspace_panel_test.dart
```

Expected: All pass (11 existing + 1 new = 12).

- [ ] **Step 6: Run Flutter analyzer**

```bash
flutter analyze lib/features/workspace/subagents_panel.dart
```

Expected: Only existing `Radio` deprecation infos.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart flutter_app/test/features/workspace/workspace_panel_test.dart
git commit -m "fix: client-side validation for subagent name regex before API call"
```

---

### Task 5: Final Verification

- [ ] **Step 1: Run all backend subagent tests**

```bash
uv run pytest tests/sdk/test_subagent_v1.py tests/sdk/test_subagent_tools_async.py -v
```

Expected: All pass.

- [ ] **Step 2: Run ruff on all backend changes**

```bash
uv run ruff check src/sdk/middleware_progress.py src/sdk/coordinator.py tests/sdk/test_subagent_v1.py
```

Expected: All checks passed.

- [ ] **Step 3: Run all Flutter workspace panel tests**

```bash
cd flutter_app && flutter test test/features/workspace/workspace_panel_test.dart
```

Expected: All 12 pass.

- [ ] **Step 4: Run Flutter analyzer**

```bash
cd flutter_app && flutter analyze lib/features/workspace/subagents_panel.dart lib/providers/subagent_provider.dart
```

Expected: Only existing `Radio` deprecation infos.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: final verification after subagent P2/P3 fixes"
```
