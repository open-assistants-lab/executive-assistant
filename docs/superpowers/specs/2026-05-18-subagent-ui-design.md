# Subagent UI — Flutter Management Panel

**Date:** 2026-05-18
**Status:** Draft
**Author:** AI-assisted design

## 1. Goal

Add a dedicated subagent management panel to the Flutter app, enabling users to browse, create, start, monitor, instruct, and delete subagents without leaving the app or using chat-based tool calls for management tasks.

V1 provides real-time progress monitoring and full job history (status, result, error, instructions). Per-message transcripts are deferred to a future version.

## 2. Constraints & Non-Goals

- **Progress-only v1.** The backend persists job status, progress (phase, message, steps), result, error, and instructions. Full message-level transcripts are deferred to a future version. For v1, the detail dialog shows the job's progress log, final result/error, and instruction history — no per-message transcript.
- **Skills panel stays as-is.** No refactoring of `skills_panel.dart` to Riverpod. Skills is CRUD-only and works fine with its current `ConsumerStatefulWidget` pattern.
- **Scope support.** Subagents can be user-scoped (visible in all workspaces, stored in the user-level subagents directory) or workspace-scoped (visible only in the current workspace). This matches the existing scope pattern from skills.
- **HITL for destructive actions.** Creating or deleting subagents through chat still requires HITL approval. The panel's REST endpoints bypass HITL because the user is explicitly managing from the panel.

## 3. Architecture

### 3.1 New Files

```
flutter_app/lib/models/subagent.dart
  SubagentAgentDef — name, description, model, tools, skills, scope, etc.
  SubagentJob      — job_id, agent_name, task, status, progress, result, error, instructions, timestamps, workspace_id
  SubagentStatus   — pending | running | cancelling | completed | failed | cancelled

flutter_app/lib/providers/subagent_provider.dart
  SubagentPanelState — agents list, active jobs map, loading/error state
  SubagentNotifier    — StateNotifier<SubagentPanelState>
    loadList(workspaceId)
    createAgent(...)
    deleteAgent(name)
    startJob(agentName, task)
    cancelJob(jobId, workspaceId)
    instructJob(jobId, workspaceId, instruction)
    pollProgress() — Timer-based polling of active job statuses
    dispose() — cancels poll timer

flutter_app/lib/features/workspace/subagents_panel.dart
  SubagentsPanel — ConsumerStatefulWidget, main panel widget
    Header: icon, title, count, refresh, add (+)
    List: SubagentTile per agent
    SubagentTile — name, description, scope badge, status badge, progress, actions
    SubagentDetailDialog — modal with agent info + job history + progress log
    SubagentCreateDialog — form for creating a new subagent
    SubagentEditDialog — form for editing existing subagent
```

### 3.2 Data Flow

```
SubagentNotifier (Riverpod StateNotifier)
  │
  ├── loadList() → GET /subagents → updates state.agents
  │
  ├── createAgent() → POST /subagents → re-run loadList()
  │
  ├── deleteAgent() → DELETE /subagents/{name} → re-run loadList()
  │
  ├── startJob() → POST /subagents/{name}/start → add to state.activeJobs, start poll
  │
  ├── cancelJob() → POST /subagents/jobs/{job_id}/cancel → update job status
  │
  ├── instructJob() → POST /subagents/jobs/{job_id}/instructions → append to instruction log
  │
  └── pollProgress() → GET /subagents/jobs/{job_id}
                        → updates progress + result/error/instructions in state.activeJobs
                        → stops polling when terminal (completed/failed/cancelled)
```

### 3.3 State Model

```dart
class SubagentPanelState {
  List<SubagentAgentDef> agents;
  Map<String, SubagentJob> activeJobs;  // jobId → current job
  bool loading;
  String? error;
  int loadSequence;  // stale-response guard
}
```

### 3.4 Polling

When any subagent has a running or cancelling job, a 2-second Timer polls `GET /subagents/jobs/{job_id}` for each active job. Each `SubagentJob` must store the `workspace_id` from which it was started so polling still targets the original workspace after the user switches workspaces. The poll updates:
- `progress.phase`
- `progress.message`
- `progress.steps_completed`
- `progress.stuck`
- `instructions` array
- `result` and `error`
- `status` (transition to completed/failed/cancelled stops polling)

The timer is created in the notifier and cancelled on `dispose()` or when no active jobs remain.

## 4. Panel Layout

### 4.1 Header

```
[🤖 icon] Subagents    [count] [↻ refresh] [+ add]
```

Same visual density as the skills panel. "Add" button opens `SubagentCreateDialog`.

### 4.2 Subagent Tile

```
┌─────────────────────────────────────────┐
│ 🤖 weather-fetcher                      │
│ Fetches accurate weather data           │
│ ┌──────┐ ┌─────────┐                   │
│ │ user │ │  idle   │ [▶] [ℹ] [🗑]     │
│ └──────┘ └─────────┘                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 🤖 code-reviewer                        │
│ Reviews PRs for style & bugs            │
│ ┌───────┐ ┌─────────┐                  │
│ │ worksp│ │ running │ [⏹] [ℹ] [🗑️]   │
│ └───────┘ └─────────┘                  │
│ Analyzing diff...                       │
└─────────────────────────────────────────┘
```

- **Scope badge** — `_ScopeBadge` ("user" or "ws"), reusing the same component from skills. User scope agents appear in all workspaces. Workspace scope agents appear only in the current workspace.
- **Status badge** — colored pill: idle (gray), running (green), completed (blue), failed (red), cancelled (orange).
- **Progress text** — shows `progress.message`, falling back to `progress.phase` when running. Single line, ellipsis overflow.
- **Action icons** — change based on status:
  - idle: ▶ start | ℹ detail | 🗑 delete
  - running: ⏹ cancel | ℹ detail | 🗑 delete
  - completed: ℹ detail | 🗑 delete
  - failed: ℹ detail | 🗑 delete

### 4.3 States

- **Loading:** Centered `CircularProgressIndicator`
- **Error:** Error message + "Retry" button
- **Empty:** Robot icon + "No subagents yet" + hint text about creating one from the panel or via chat

### 4.4 Workspace Switch Reactivity

On workspace change, `loadList()` re-fetches with the new workspace ID. Active polling jobs are preserved only if each job stores its original `workspace_id`; polling must continue to use that original `workspace_id`, not the newly selected workspace.

## 5. Modal Dialogs

### 5.1 Subagent Detail Dialog

Full-screen modal (not bottom sheet) that shows agent info, job history, progress updates, instructions, and final result/error for the selected job.

```
┌─────────────────────────────────────────────┐
│ ✕                                    [⚙️ edit]│
│ ─────────────────────────────────────────── │
│ 🤖 weather-fetcher                  [user] │
│ Model: deepseek:deepseek-v4-flash          │
│ Tools: web_search, web_fetch               │
│ Created: 2 hours ago                       │
│ ─────────────────────────────────────────── │
│ Jobs                                       │
│ ┌─ task_abc · completed · 3 mins ───────┐  │
│ │ 3 steps, 2 tool calls                 │  │
│ └────────────────────────────────────────┘  │
 │ ┌─ task_def · running · now ─────────────┐  │
 │ │ Phase: researching                     │  │
 │ │ Step 3 of ?: Searching weather data... │  │
 │ │ Instructions: focus on Sydney          │  │
 │ │                                        │  │
 │ │ ✅ Initialized subagent                │  │
 │ │ ✅ Tools configured                    │  │
 │ │ 🔄 Searching weather data...           │  │
 │ └────────────────────────────────────────┘  │
│ ─────────────────────────────────────────── │
│ [▶ Start new task]         [🗑 Delete agent]│
└─────────────────────────────────────────────┘
```

- **Agent info section** — collapsed at top. Shows name, scope, model, tools, created date, limits.
- **Jobs section** — scrollable list of job runs. Latest job first. Load via `GET /subagents/jobs` and filter by `agent_name` client-side.
- **Progress log** — shows a flat, chronologically ordered list of progress updates for the selected job:
  - Status line: `pending`, `running`, `cancelling`, `completed`, `failed`, `cancelled`
  - Progress fields: `progress.phase`, `progress.message`, `progress.steps_completed`
  - Instructions: `instructions[].added_at` and `instructions[].message`
  - Result/error: `result.output`, `result.cost_usd`, `result.llm_calls`, `error`
- **Live updates** — for running jobs, progress and status fields auto-refresh via poll timer every 2s.
- **Actions bar:**
  - Running: **[Cancel]** **[Instruct...]**
  - Idle/Completed: **[▶ Start new task]** **[🗑 Delete agent]**
- **Instruct** — tapping "Instruct..." reveals a text input + send button inline in the actions bar area. User types an instruction (e.g., "focus on Sydney weather"), hits send, the panel calls `POST /subagents/jobs/{job_id}/instructions`. Input collapses back after send. The instruction appears in the progress log as a greyed-out entry with an 📝 icon.

### 5.2 Subagent Create Dialog

```
┌─────────────────────────────────────┐
│ ✕ Create Subagent                   │
│ ─────────────────────────────────── │
│ Name *        [weather-fetcher    ] │
│ Description * [Fetches weather... ] │
│                                     │
│ Scope         ○ User  ● Workspace   │
│                                     │
│ Model         [deepseek:v4-flash ▼] │
│               [                   ] │
│ System prompt [Optional system...  ]│
│                                     │
│ Tools         [☑ web_search        ]│
│               [☑ web_fetch         ]│
│               [☐ files_read        ]│
│                                     │
│ Max LLM calls [50]    Cost [$1.00]  │
│ Timeout (s)   [300]                 │
│ ─────────────────────────────────── │
│              [Cancel] [Create]      │
└─────────────────────────────────────┘
```

- **Name** — required. Alphanumeric + hyphens/underscores.
- **Description** — required. Shown in tile list.
- **Scope** — radio: User (all workspaces) or Workspace (current only). Default: Workspace.
- **Model** — text field (freeform) with a dropdown suggestion list fetched from `GET /models` (the models.dev registry endpoint). Pre-filled with the current workspace's default model. User can type any model string (e.g., `anthropic:claude-sonnet-4-20250514`).
- **System prompt** — optional. Multi-line text area.
- **Tools** — scrollable checkbox list of available tool names. Fetched from `GET /tools/names`. All checked by default.
- **Advanced fields** — Max LLM calls, Cost limit, Timeout. Collapsed under "Advanced" toggle.
- **Create** button sends to `POST /subagents`, closes dialog, refreshes list.

### 5.3 Subagent Edit Dialog

Same form as Create, pre-filled with existing values. Fields editable: description, model, system prompt, tools, limits. Name is NOT editable (immutable after creation).

Send to `PATCH /subagents/{name}`.

## 6. Backend REST Endpoints

Use the existing router `src/http/routers/subagents.py` mounted at `/subagents`. The implementation plan should not create a second router.

```
GET    /subagents?workspace_id=...
       → List agent defs, filtered by workspace. Returns workspace defs plus user-scoped defs.

POST   /subagents
       → Create agent def (admin action, no interrupt).

PATCH  /subagents/{name}
       → Update agent def fields (description, model, prompt, tools, limits).

DELETE /subagents/{name}
       → Delete agent def. Cancels any running tasks first.

POST   /subagents/{name}/start
       → Insert task into work_queue and begin execution. Returns task ID.

GET    /subagents/jobs?status=...
       → List jobs for the current workspace. Flutter filters by agent_name for per-agent history.

GET    /subagents/jobs/{job_id}
       → Get job detail (status, progress, result, error, instructions, timestamps).

POST   /subagents/jobs/{job_id}/cancel
       → Set cancel_requested on the target job.

POST   /subagents/jobs/{job_id}/instructions
       → Inject course-correction into the target job's instruction queue.

GET    /subagents/jobs/{job_id}/events?after_sequence=...
       → Return ordered durable transcript events after the requested sequence.
```

All endpoints accept `workspace_id` as a query parameter and currently default `user_id` to `default_user`. Before production use, align these endpoints with the app's normal user identity/auth pattern instead of trusting arbitrary query-string user IDs.

These endpoints call `SubagentCoordinator` methods directly, bypassing the tool-call/interrupt flow since the user is managing from the panel.

### 6.1 Future: Transcript Persistence

Full message-level transcripts are deferred to a future version. When implemented, they will use a `TranscriptMiddleware` (async, since it writes to aiosqlite via the agent loop's async middleware hooks) that captures assistant messages, tool calls, tool results, and terminal events into a `work_queue_events` table in the work queue database. The Flutter detail dialog will then poll `GET /subagents/jobs/{job_id}/events?after_sequence=...` to stream the live transcript.

Additionally, add a lightweight utility endpoint (or add to the existing skills router):

```
GET    /tools/names
       → List registered native tool names (e.g., ["time_get", "files_list", ...]).
         Used by the create dialog for the tool checkboxes.
```

This can read from `src.sdk.native_tools.get_native_tool_names()`. Keep auth consistent with the rest of the HTTP API even though the data is read-only; tool names reveal local capabilities.

## 7. WebSocket Integration

The existing WS approval flow (interrupt → sheet → approve → retry) remains the primary path for creating subagents through chat. The panel's REST endpoints are a separate, parallel path for direct management.

When a job is started via the panel (`POST /subagents/{name}/start`), the subagent runs in the background work queue. The panel polls for job status and progress. The main chat is not notified about subagent progress; the detail dialog shows the job's status, progress log, and result.

## 8. Scope Filtering

User-scoped agents appear in all workspaces. Workspace-scoped agents appear only in the workspace where they were created.

The backend `SubagentCoordinator.list_defs()` returns both workspace-local definitions and user-level fallback definitions. The backend must include an explicit `scope: "user" | "workspace"` field in `GET /subagents` responses.

Scope is set at creation time via the `scope` field in `POST /subagents` (`"user"` or `"workspace"`). User-scoped agents are stored in the user-level subagents directory; workspace-scoped agents in the workspace subagents directory. Scope cannot be changed after creation.

## 9. Error Handling

- **API errors:** Show inline error banner in the panel (not a toast/snackbar). Retry button.
- **Poll failures:** Log warning, continue polling next cycle. After 3 consecutive failures, show "Connection lost" state on the affected task tile.
- **Missing agents:** If someone deletes an agent externally while the panel is open, the next poll/list will remove it from state silently.
- **Concurrent operations:** If the user starts a job while one is already running for the same agent, the panel shows a confirmation: "This subagent already has a running job. Start another?". If accepted, the UI tracks both jobs by `job_id`.

## 10. Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `flutter_app/lib/models/subagent.dart` | NEW | Data models |
| `flutter_app/lib/providers/subagent_provider.dart` | NEW | StateNotifier + state |
| `flutter_app/lib/features/workspace/subagents_panel.dart` | NEW | Panel widget + dialogs |
| `flutter_app/lib/features/workspace/workspace_panel.dart` | MODIFY | Add subagents tab |
| `flutter_app/lib/services/api_client.dart` | MODIFY | Add subagent REST methods |
| `src/http/routers/subagents.py` | MODIFY | Align REST responses with UI needs (scope field, timestamps); add `/tools/names` utility route or wire elsewhere |
| `src/http/main.py` | VERIFY | Router is already mounted |

## 11. MVP Acceptance Criteria

- `WorkspacePanel` includes a Subagents tab without regressing Files or Skills tabs.
- Flutter lists subagents from `GET /subagents` and shows empty/loading/error states.
- Flutter creates subagents with `POST /subagents`, validates name/description client-side, renders server validation errors inline.
- Flutter starts a job with `POST /subagents/{name}/start` and stores returned `job_id` plus original `workspace_id`.
- Flutter polls `GET /subagents/jobs/{job_id}` every 2 seconds for active jobs and stops on `completed`, `failed`, or `cancelled`.
- Flutter cancels and instructs jobs with `POST /subagents/jobs/{job_id}/cancel` and `POST /subagents/jobs/{job_id}/instructions`.
- Detail dialog shows agent info, job history, progress log, instructions, and final result/error.
- Backend response includes a `scope` field so the Flutter panel can render scope badges.
- Tests cover workspace switching while a job is running, confirming polling continues against the original workspace.
