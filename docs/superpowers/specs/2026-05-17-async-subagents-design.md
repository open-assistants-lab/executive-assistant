# Async Configurable Subagents Design

## Summary

Upgrade the current SDK subagent system into a true async worker model. The main agent and user can create, update, delete, list, start, check, instruct, and cancel workspace-scoped subagents. Subagents can be configured with prompt, tools, skills, model, provider options, and runtime limits. A subagent should behave like a main agent inside its workspace, except it cannot create or start further subagents.

Trigger rules for schedules, webhooks, and file changes are intentionally deferred. The design keeps room for them later, but v1 focuses on async subagents only.

---

## Current State

The repo already has a strong subagent foundation:

- `AgentDef` in `src/sdk/subagent_models.py`
- `WorkQueueDB` in `src/sdk/work_queue.py`
- `SubagentCoordinator` in `src/sdk/coordinator.py`
- `ProgressMiddleware` and `InstructionMiddleware`
- SDK tools in `src/sdk/tools_core/subagent.py`
- HTTP routes in `src/http/routers/subagents.py`

Current gaps:

- `subagent_start` uses explicit async wording and returns a job ID.
- No dynamic per-invocation overrides for prompt/tools/skills/model/provider options.
- Skill lookup does not consistently use workspace-aware registry behavior.
- `mcp_config` is persisted but not clearly wired into subagent runtime.
- HTTP routes are incomplete/inconsistent with SDK tools.
- `SubagentCoordinator.delete()` is referenced by tools/tests but may be missing or inconsistent.
- Progress/cancel exists, but runtime lifecycle needs a clearer async job contract.

---

## Scope

### In V1

Build async configurable subagents:

- Workspace-scoped subagent definitions.
- Dynamic prompt, tools, skills, model, provider options, limits.
- True async `subagent_start` returning a job ID immediately.
- `subagent_check`, `subagent_tasks`, `subagent_instruct`, `subagent_cancel`.
- Frozen config snapshot per job.
- Mandatory middleware for visibility/control.
- Mandatory `memory_search` tool.
- Runtime denial of all `subagent_*` tools.

### Not In V1

Do not implement trigger rules yet:

- Schedule triggers.
- Webhook triggers.
- File-change triggers.
- Main-agent triggered wakeups.
- Background chat provenance for trigger runs.

These are future automation-platform work on top of the async job foundation.

---

## Architecture

```text
Main Agent / User
   |
   +--> subagent_create/update/delete/list
   |
   +--> subagent_start  ── returns job_id immediately
   |
   +--> subagent_check / subagent_tasks
   |
   +--> subagent_instruct / subagent_cancel
            |
            v
      WorkQueueDB / AgentJob row
            |
            v
      Background Subagent Runner
            |
            v
      AgentLoop with frozen config snapshot
```

The current `WorkQueueDB` can remain the durable job store for v1. The term `AgentJob` in this design maps to the existing work queue row. A later trigger system can generalize this table or add a compatible `agent_jobs` table.

---

## Subagent Definition

`AgentDef` should represent a reusable workspace-scoped worker.

```text
AgentDef
  name
  description
  workspace_id

  system_prompt
  skills
  tools_allowlist
  tools_denylist

  model
  provider_options

  max_llm_calls
  cost_limit_usd
  timeout_seconds

  output_schema?
  handoff_instructions?
  artifact_policy?

  created_at
  updated_at
```

### Workspace Scope

Subagent definitions belong to one workspace.

```text
subagent_create(name, ..., workspace_id)
  → saves definition under that workspace

subagent_start(name, task, workspace_id)
  → loads definition from that workspace
  → writes job row with same workspace_id
  → subagent files/memory/skills/tools resolve in that workspace
```

Cross-workspace subagents are deferred. V1 avoids permission and mental-model ambiguity by binding each subagent to a workspace.

### Config Snapshot

When a job starts, freeze the full `AgentDef` into the job config snapshot.

```text
subagent_update(...)
  affects future jobs only
  running jobs keep old snapshot
```

---

## Runtime Middleware

All subagents always get the same middleware set. No middleware profiles in v1.

```text
Always enabled:
  ProgressMiddleware
  InstructionMiddleware
  SummarizationMiddleware
  ObservationMiddleware
```

Roles:

| Middleware | Role |
|---|---|
| `ProgressMiddleware` | Updates job progress and detects stuck/doom-loop behavior. |
| `InstructionMiddleware` | Checks cancel/instruction state before model calls. Enables interrupt/course correction. |
| `SummarizationMiddleware` | Keeps long-running subagent conversations within context budget. |
| `ObservationMiddleware` | Records execution observations for audit/debug/workspace awareness. |

`ProgressMiddleware` and `InstructionMiddleware` are required because async workers must remain visible and controllable.

---

## Tool Resolution

Subagents can use tools like the main agent, but with strict recursion prevention.

```text
always denied:
  subagent_*

always included:
  memory_search

tools_allowlist = null:
  all native tools - subagent_* + memory_search

tools_allowlist = [...]:
  tools_allowlist - subagent_* + memory_search

tools_denylist:
  removes denied tools
  but cannot remove memory_search
  and cannot re-enable subagent_*
```

Rules:

- `memory_search` is mandatory and cannot be denied.
- `subagent_*` tools are always denied at runtime, regardless of persisted config.
- Unknown tool names should be rejected on create/update, not silently ignored.
- Denylist wins over allowlist for all tools except mandatory `memory_search`.

---

## Skills

Subagents can be configured with a list of skill names.

Rules:

- Skills resolve workspace-aware.
- Unknown skill names fail validation on create/update.
- Full skill content is injected into the subagent system prompt in v1.
- Progressive skill loading inside subagents can be considered later, but v1 favors predictable explicit injection.

---

## Model And Provider Configuration

Subagents can choose model/provider from already-configured providers only.

```text
model = "provider:model-name"
provider_options = {...}
credentials = never stored in AgentDef
```

Rules:

- No per-subagent API keys in v1.
- Validate model string against the existing model/provider registry where possible.
- Provider options are stored in the frozen job config snapshot.
- If model/provider is unavailable at job start, fail the job early with a clear config error.

---

## Async Runtime Tools

Use new tool names only. Do not keep old invoke/progress aliases because the product has not launched.

### Management Tools

```text
subagent_create
subagent_update
subagent_delete
subagent_list
```

### Runtime Tools

```text
subagent_start
subagent_check
subagent_tasks
subagent_instruct
subagent_cancel
```

### Tool Semantics

`subagent_start(name, task, workspace_id)`:

- Validates definition exists in workspace.
- Inserts job row as `pending`.
- Starts background runner.
- Returns job ID immediately.

`subagent_check(job_id)`:

- Returns status, progress, result, error, timestamps, cost, and LLM calls.

`subagent_tasks(...)`:

- Lists active/recent jobs, filterable by workspace/status/subagent.

`subagent_instruct(job_id, instruction)`:

- Adds course correction for `InstructionMiddleware` to inject.

`subagent_cancel(job_id)`:

- Sets `cancel_requested`.
- Job status moves to `cancelling` if currently running.
- Final state becomes `cancelled` once observed by the runner.

---

## Status Model

```text
pending
running
cancelling
completed
failed
cancelled
```

Future trigger work may add:

```text
skipped
waiting_for_approval
```

V1 does not need `waiting_for_approval` unless subagent HITL is implemented. If a subagent requests destructive approval in v1, the safe behavior is to fail with a clear “approval required but unsupported in subagent job” error, or surface it to the main chat if existing HITL plumbing supports that cleanly.

---

## Background Execution

Current start behavior should use true async background execution.

```text
subagent_start
  → insert job
  → asyncio.create_task(runner(job_id))
  → return job_id
```

Implementation notes:

- Keep an in-process task registry for currently running jobs.
- WorkQueueDB remains source of truth.
- On app startup, mark stale `running`/`cancelling` jobs as `failed: interrupted by restart`.
- Do not attempt recovery in v1.
- Cancellation is cooperative. Long-running tools may not stop until the next model call.

---

## HTTP API

Bring HTTP routes in line with SDK tools.

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

Rules:

- All routes require `user_id` and `workspace_id` context.
- Definitions are workspace-scoped.
- Job routes read/write durable work queue rows.
- Start returns immediately with `job_id`.
- Delete cancels or prevents future jobs as appropriate, but does not mutate running job snapshots.

---

## Validation

Validate on create/update:

- Subagent name format.
- Workspace ID is valid.
- Model exists/configured if specified.
- Tools exist.
- Skills exist and resolve in workspace/user skill registry.
- `subagent_*` tools are rejected if provided.
- `memory_search` cannot be removed.
- Limits are within sane ranges.
- Timeout is positive and bounded.

Validate on start:

- Definition exists in workspace.
- Target config snapshot is valid.
- Provider/model can be created.
- Background runner can enqueue job.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Unknown subagent | Return clear not-found error. |
| Unknown tool/skill | Reject create/update with validation error. |
| Subagent tries to use `subagent_*` | Tool unavailable at runtime. |
| Cancel requested while pending/running | Mark `cancelling`; final `cancelled` when observed. |
| Cancel requested after terminal state | Return current terminal state; no-op. |
| App restarts while job running | Mark stale running jobs failed on startup. |
| Model/provider unavailable | Job fails early with config error. |
| Output too large | Truncate human output, preserve `truncated=true`; future artifacts can store full output. |

---

## Future Trigger Rules

Triggers are explicitly deferred, but the async job model should be compatible.

Future design:

```text
TriggerRule
  id
  name
  enabled
  type: schedule | webhook | workspace_file_change
  target_type: main_agent | subagent
  target_name
  workspace_id
  task_template
  overlap_policy: skip
```

Future behavior:

- Schedule/webhook/file-change triggers can target main agent or subagents.
- File-change triggers watch only workspace files.
- Triggered main-agent output appears as normal chat with trigger provenance.
- Destructive tools require HITL.
- Overlapping trigger runs are skipped.

This should be a separate implementation cycle.

---

## Testing Strategy

### Unit Tests

- `AgentDef` validation for new fields.
- Tool allowlist/denylist resolution.
- Mandatory `memory_search` inclusion.
- Mandatory `subagent_*` exclusion.
- Config snapshot freezing.
- Background start returns before job completion.
- Status transitions.

### Integration Tests

- Create subagent with custom prompt/tools/skills/model.
- Start subagent and poll until completion.
- Instruct running subagent and verify instruction injection.
- Cancel running subagent and verify terminal state.
- Update subagent while job running; verify running snapshot unchanged.
- Restart cleanup marks stale running jobs failed.

### API Tests

- CRUD routes for definitions.
- Start/check/tasks/instruct/cancel job routes.
- Validation failures for unknown tool/skill/model.
- Workspace scoping.

---

## Open Future Questions

- Should subagent HITL approvals be surfaced into main chat in v1 or fail safely?
- Should subagent artifacts be first-class files in v1 or just result text?
- Should MCP config be supported in v1 or deferred until the existing `mcp_config` path is fully wired?
- Should output schemas be validated in v1 or only stored for prompting?

Recommended v1 answers:

- HITL: fail safely unless existing approval flow can be reused cleanly.
- Artifacts: result text now, artifacts later.
- MCP config: validate/storage only unless already easy to wire.
- Output schema: store and prompt only; strict validation later.
