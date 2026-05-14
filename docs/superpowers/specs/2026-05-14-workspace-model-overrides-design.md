# Workspace Model Overrides Design

## Goal

Make model selection predictable and workspace-aware. Settings should define the global default model and provider credentials. Each workspace may optionally override that default. The chat composer should make the active model source clear without crowding the bottom of the window.

## Current Problems

- The model pill appears inside the workspace chat area but currently changes one global model, which implies per-workspace behavior that does not exist.
- Settings and the workspace pill overlap in purpose.
- The workspace pill sits below the composer with weak spacing, so it looks detached and cramped.
- Settings saves raw model IDs in its radio list, while the workspace picker saves `provider:model` values. The backend expects provider-qualified model strings for reliable provider routing.

## Model Resolution

Use a two-level model setting:

1. Global default model: persisted in Flutter `SharedPreferences` as `ea_model`.
2. Workspace override: optional `model_override` field on the workspace config.

Resolution rule:

```text
effective_model = workspace.model_override ?? global_default_model
```

Provider API keys remain global and continue to use `ea_key_<provider_id>`.

## Workspace Data Model

Add an optional field to `Workspace`:

```text
model_override: str | None
```

The field is stored in each workspace's `workspace.yaml`. Missing values mean the workspace inherits the global default.

## Settings UX

Settings owns provider credentials and the global default model.

Changes:

- Rename the model area conceptually to `Default Model`.
- Keep provider API-key editing in Settings.
- Ensure model radio values save `provider:model`, not the raw model ID.
- Continue persisting the default model as `ea_model`.

## Workspace Composer UX

Move the model control into the composer footer row, visually attached to the input, similar to Claude-style controls near the input/send area.

Composer structure:

- Input field remains primary.
- Below the input, add a compact footer row with bottom padding.
- Left side shows the model pill.
- The pill label is source-aware:
  - `Default: <provider/model>` when no workspace override exists.
  - `Override: <provider/model>` when the workspace has an override.
- Tapping the pill opens the model picker.

Picker behavior:

- Shows only providers with saved API keys.
- Selecting a model stores it as the current workspace override.
- If an override exists, show `Use default model` at the top to clear it.
- If no provider key exists, tapping opens Settings.

## Data Flow

On app load:

- Load global `ea_model`.
- Load current workspace metadata.
- Compute effective model from workspace override or global default.
- Set the effective model on `WsClient` and `ApiClient`.

On workspace switch:

- Load that workspace's override.
- Recompute effective model.
- Update `selectedModelProvider` display state and both clients.

On global default change in Settings:

- Save `ea_model`.
- Workspaces without overrides immediately inherit the new default.
- Workspaces with overrides keep their override.

On workspace override change:

- Persist the workspace config.
- Update the clients to the new effective model.

## Testing

Add focused tests for:

- Settings saves provider-qualified model values.
- Workspace with no override uses the global default.
- Workspace override takes precedence over global default.
- Clearing an override returns to the global default.
- Model picker label displays `Default:` or `Override:` correctly.

## Out Of Scope

- Per-workspace provider API keys.
- Multiple simultaneous model selections per open tab beyond one override per workspace.
- Backend-side model preference storage outside existing workspace config files.
