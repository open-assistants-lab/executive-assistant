# Workspace Model Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global default model plus optional per-workspace model override, and move the chat model pill into a better-spaced composer footer.

**Architecture:** Keep provider API keys global in Flutter preferences. Store workspace overrides in existing workspace config files via backend workspace APIs, expose the override to Flutter, and compute the effective model client-side on workspace/model changes. Keep the UI minimal by reusing the existing model picker with clearer labels and a `Use default model` action.

**Tech Stack:** Flutter, Riverpod, SharedPreferences, FastAPI, Python dataclasses/YAML, pytest, flutter_test.

---

### Task 1: Backend Workspace Override Field

**Files:**
- Modify: `src/sdk/workspace_models.py`
- Modify: `src/http/routers/workspaces.py`
- Test: `tests/api/test_workspaces.py`

- [ ] **Step 1: Write failing tests**

Add tests that create/update a workspace with `model_override`, fetch it, and verify the field round-trips as `ollama:minimax-m2.7`. Also verify missing override serializes as `null` or absent-safe default.

- [ ] **Step 2: Run tests and verify red**

Run: `uv run pytest tests/api/test_workspaces.py -q`

Expected: failure because `model_override` is not accepted or returned.

- [ ] **Step 3: Implement minimal backend model field**

Add `model_override: str | None = None` to `Workspace`, include it in `to_dict()`, and parse it in `from_dict()`.

If update endpoints use request models, add an optional `model_override` request field and pass it into `save_workspace()`.

- [ ] **Step 4: Run tests and verify green**

Run: `uv run pytest tests/api/test_workspaces.py -q`

Expected: pass.

### Task 2: Flutter Workspace Model State

**Files:**
- Modify: `flutter_app/lib/providers/workspace_provider.dart`
- Modify: `flutter_app/lib/services/api_client.dart`
- Test: `flutter_app/test/providers/workspace_provider_test.dart`

- [ ] **Step 1: Write failing tests**

Test that a workspace with no override resolves to global `ea_model`, and a workspace with `model_override` resolves to that override.

- [ ] **Step 2: Run tests and verify red**

Run: `flutter test test/providers/workspace_provider_test.dart`

Expected: failure because override state/resolution does not exist.

- [ ] **Step 3: Implement minimal client state**

Add workspace model override storage to the workspace state. Add API methods to update/fetch workspace metadata if not already present. Add a helper/provider for effective model resolution.

- [ ] **Step 4: Run tests and verify green**

Run: `flutter test test/providers/workspace_provider_test.dart`

Expected: pass.

### Task 3: Settings Default Model Format

**Files:**
- Modify: `flutter_app/lib/features/settings/settings_screen.dart`
- Test: `flutter_app/test/features/settings/settings_screen_test.dart`

- [ ] **Step 1: Write failing test**

Test that selecting a model from Settings saves `provider:model`, not just `model`, and updates `selectedModelProvider` with the provider-qualified value.

- [ ] **Step 2: Run test and verify red**

Run: `flutter test test/features/settings/settings_screen_test.dart`

Expected: failure because Settings currently uses raw model IDs as radio values.

- [ ] **Step 3: Implement minimal Settings fix**

Use `${pid}:$m` as the radio value, compare against `_selectedModel`, and set `_selectedProvider = pid` when selected. Label the section `Default Model`.

- [ ] **Step 4: Run test and verify green**

Run: `flutter test test/features/settings/settings_screen_test.dart`

Expected: pass.

### Task 4: Workspace Model Picker And Composer Placement

**Files:**
- Modify: `flutter_app/lib/features/chat/widgets/model_switcher.dart`
- Modify: `flutter_app/lib/features/chat/widgets/chat_input.dart`
- Modify: `flutter_app/lib/providers/agent_provider.dart`
- Test: `flutter_app/test/features/chat/model_switcher_test.dart`

- [ ] **Step 1: Write failing tests**

Test labels:
- No override: pill displays `Default:`.
- Override present: pill displays `Override:`.
- Picker includes `Use default model` when override exists.

- [ ] **Step 2: Run tests and verify red**

Run: `flutter test test/features/chat/model_switcher_test.dart`

Expected: failure because labels/override clearing do not exist.

- [ ] **Step 3: Implement minimal UI behavior**

Move the pill into a composer footer inside `ChatInput` with horizontal and bottom padding. Make `ModelSwitcher` source-aware and persist override changes to the active workspace. Keep existing picker logic for authorized providers.

- [ ] **Step 4: Run tests and verify green**

Run: `flutter test test/features/chat/model_switcher_test.dart`

Expected: pass.

### Task 5: End-To-End Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run focused Python tests**

Run: `uv run pytest tests/api/test_workspaces.py tests/api/test_ws_conversation.py -q`

Expected: pass.

- [ ] **Step 2: Run focused Flutter tests**

Run: `flutter test test/providers/workspace_provider_test.dart test/features/settings/settings_screen_test.dart test/features/chat/model_switcher_test.dart`

Expected: pass.

- [ ] **Step 3: Run lint/static checks**

Run: `uv run ruff check src/sdk/workspace_models.py src/http/routers/workspaces.py tests/api/test_workspaces.py`

Expected: pass.

Run: `flutter analyze`

Expected: no new errors; existing warnings may remain.

- [ ] **Step 4: Rebuild and restart app**

Run: `flutter build macos --debug`

Expected: build succeeds.

Open: `build/macos/Build/Products/Debug/flutter_app.app`.

---

## Self-Review

- Spec coverage: backend model field, settings default, workspace override, composer placement, and tests are all covered.
- Placeholder scan: no TBD/TODO/fill-in placeholders.
- Type consistency: field name is consistently `model_override`; persisted model format is consistently `provider:model`.
