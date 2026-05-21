# Subagent Jobs Results & Skills Tree View

Date: 2026-05-21
**Status:** Needs Revision Before Implementation

## Peer Review Verdict

**Verdict:** The core idea (expandable job history, result dialog, structured skill selector) is sound and the changes are narrowly scoped. However, the spec contains three factual errors against the current codebase that must be corrected before implementation:

### Blocking Findings

- **`GroupedTreeSelector<String>` widget does not exist.** The spec claims "Already exists at `widgets/tree_selector.dart`" but no such file or class exists in the Flutter codebase. Grep for `GroupedTreeSelector`, `treeSelector`, `TreeSelector`, and glob for `tree_selector.dart` all returned zero results. This widget must be **created**, not referenced as existing. The spec should either add the widget to the file changes table or remove the claim.
- **"Capabilities" wording does not exist anywhere.** The spec says to rename "Skills & Capabilities" → "Skills" in create/edit dialogs, but grep for `capabilities` / `Capabilities` across the entire Flutter codebase returned zero matches. The current skill selector is already labeled "Skills" at lines 389 and 781 of `subagents_panel.dart`. No renaming work is needed.
- **The skills selector is already interactive.** The spec describes the old disabled tool picker pattern but the skills picker (`CheckboxListTile` list at lines 425-444 and 817-839) uses real state via `selectedSkills` with working `onChanged` callbacks. It is not the same as the tool picker (which is `value: true, onChanged: null`). The upgrade to a `GroupedTreeSelector` is about UX polish (grouping/search), not fixing a broken widget.

### Non-Blocking Observations

- **Result dialog data model.** `SubagentJob.result` is typed `String?` (`subagent.dart:68`), populated from `json['result']?.toString()`. The backend `_serialize_job` returns parsed JSON via `_parse_json_field` (`subagents.py:82`), which returns a dict for JSON result objects. `?.toString()` on a dict produces `"Instance of '...'"`, which is a pre-existing bug. The result dialog will need to handle this correctly (either parse the JSON string on the Flutter side or read the raw backend response before `.toString()` mangles it).
- **Per-agent pruning scope change** is well-identified. Currently `_pruneTerminalJobs` at line 173 keeps `_maxTerminalJobs = 10` globally. Changing to per-agent is the right design.
- **`_pruneTerminalJobs` already clears terminal jobs during polling** (called at lines 126, 170, 238). The "Clear completed" action should also call this with an agent-specific filter.
- **No new REST endpoints** are needed. The spec correctly relies on existing polling and endpoints.
- **Token system exists and is used.** `context.tokens.colors.bgCanvas` is used at line 54 of `subagents_panel.dart`. The spec's requirement for `context.tokens`-exclusive access is consistent.

### Recommended Correction

Replace the `GroupedTreeSelector` + "Capabilities" fixes with concrete widget creation work. The central changes are:
1. Create a `GroupedTreeSelector<String>` widget (new file in `lib/widgets/tree_selector.dart` or populate `lib/features/workspace/widgets/`).
2. Implement expandable job sections and result dialog as designed.
3. Change `_pruneTerminalJobs` from global to per-agent (adding `expandedAgentName` to state).
4. Fix `SubagentJob.result` handling from backend response.

## Problem

1. **No job history UI** — Subagents panel shows agent definitions with inline status (running/idle), but once a job completes, the card reverts to "idle" with no way to see the result. Users can't review past runs, compare outcomes, or inspect errors.

2. **Flat skills list in dialog** — The subagent create/edit dialog shows skills as a flat checkbox list. With many skills available (user + workspace scoped), this becomes unmanageable — no grouping, no search.

3. **"Capabilities" terminology** — The dialog labels the section "Skills & Capabilities", but "Capabilities" is redundant (skills and capabilities are the same concept). This adds confusion.

## Design Goals

1. Surface job results inline on each subagent card via expandable section
2. Replace flat skill checkboxes with the existing `GroupedTreeSelector` widget in the create/edit dialog
3. Rename "Skills & Capabilities" → "Skills" and remove "Capabilities" wording
4. Minimal state/store changes — reuse existing `SubagentNotifier` polling architecture

## Design

### 1. Expandable Agent Cards for Job History

Each subagent tile gains tap-to-expand behavior revealing recent jobs for that agent.

**Default (collapsed) state** — identical to current tile:
```
[icon] | name + description + skill chips | scope badge + status badge + [play] [edit] [delete]
```

**Expanded state** — slides in below the agent info row:
```
[icon] | name + description + skill chips | scope badge + status badge + [play] [edit] [delete]
─────────────────────────────────────────────────────────────────
  Jobs (3)                                         Clear completed
  ● Research Chatime stores   2m ago   ✓ Completed  [View]
  ● Update system prompt     15m ago  ✗ Failed     [View]
  ● Test email tool          1h ago   ✓ Completed  [View]
  ───────────────────────────────────────────────────────────────
  No more jobs
```

Each job entry row:
- Leading: status dot (running=blue, completed=green, failed=red, cancelled=gray, pending=yellow)
- Title: task text (truncated to 1 line, ellipsis overflow)
- Subtitle: relative timestamp  ("2m ago", "1h ago", "3d ago")
- Center: status badge pill (`completed`, `failed`, `cancelled`, `running`)
- Trailing: "View" button → opens result dialog

Section header: "Jobs (N)" with "Clear completed" action (removes terminal jobs for that agent only).

**Interaction rules:**
- Only one agent card expanded at a time (tapping another agent auto-collapses the current one)
- Tapping the same agent card again collapses it
- Tapping the agent tile body toggles expand (replaces the old "tap to edit" behavior — editing is now always via the edit trailing button)
- Jobs that are `running` or `cancelling` show a live-updating progress message (existing polling)
- Max 10 recent jobs shown per agent (already pruned by `SubagentNotifier._pruneTerminalJobs`)

### 2. Job Result Dialog

Opened by tapping "View" on a job entry. Full-screen dialog (or bottom sheet on narrow screens):

```
┌──────────────────────────────────────────────────┐
│  Job Result                                      │
│  ─────────────────────────────────────────────── │
│                                                   │
│  Status: ✓ Completed           Duration: 12.4s   │
│  Agent:  chatime-researcher    LLM calls: 11      │
│  Cost:   $0.000                Cost limit: $0.50  │
│                                                   │
│  Task                                              │
│  ─────────────────────────────────────────────── │
│  Research Chatime Australia store count and       │
│  business info...                                  │
│                                                   │
│  Output (scrollable, monospace)                    │
│  ─────────────────────────────────────────────── │
│  Here's a comprehensive summary of Chatime in     │
│  Australia...                                      │
│                                                   │
│  [Close]                                           │
└──────────────────────────────────────────────────┘
```

Sections:
- **Header**: Title "Job Result", close button (X)
- **Metadata row**: Status badge, duration (started→completed), agent name, LLM calls, cost
- **Task**: original task text (read-only, scrollable)
- **Output**: full result output in monospace font (scrollable, selectable)
- **Error section** (conditional): shown only if job failed — error message and details in red section
- **Close button**: bottom-right

### 3. Skills Tree View in Subagent Dialog

Replace the flat `CheckboxListTile` list in the create/edit dialog's skill selector with the existing `GroupedTreeSelector<String>` widget.

**Data grouping:**
- **User Skills** — skills in user scope (global)
- **Workspace Skills** — skills in this workspace

Each group shows `selected/N` count. Search filters both groups and items. Tri-state header checkbox for each group.

**Widget:** `GroupedTreeSelector<String>` (already exists at `widgets/tree_selector.dart`)
- Props: `groups`, `selected`, `onChanged`, `mode: TreeSelectionMode.multi`, `searchHint: "Search skills..."`
- Same height as tool selector (~180px)

### 4. Remove "Capabilities" Wording

| Location | Before | After |
|---|---|---|
| Create dialog section | "Skills & Capabilities" | "Skills" |
| Edit dialog section | "Skills & Capabilities" | "Skills" |
| Any other references | "Capabilities" | (removed) |

### 5. Color & Token Usage

All new/changed widgets use `context.tokens` exclusively:

| UI Element | Token |
|---|---|
| Job entry status dot | `success` / `warning` / `error` / `textTertiary` |
| Job section background | `bgElevated` |
| Job section divider | `borderSubtle` |
| Result dialog output text | `textPrimary`, monospace |
| Result dialog metadata labels | `textSecondary` |
| Result dialog error section | `error` bg at 10% alpha, `error` text |
| "No more jobs" text | `textTertiary` |

## State Changes

### `SubagentPanelState` (Riverpod)

```
Current:
  SubagentPanelState {
    agents: List<SubagentAgentDef>,
    activeJobs: Map<String, SubagentJob>,
    loading: bool,
    error: String?,
    loadSequence: int,
  }

Add:
    expandedAgentName: String?,  // which agent card is expanded (null = none)
```

Jobs are already polled every 2s and stored in `activeJobs`. No new polling needed. The expandable section filters `activeJobs` by agent name.

**Pruning change:** Currently `_pruneTerminalJobs` keeps max 10 terminal jobs globally. Change to keep max 10 terminal jobs **per agent** — each agent card shows up to 10 recent jobs independently.

### `SubagentNotifier`

Add methods:
- `toggleAgentExpand(String agentName)` — sets `expandedAgentName`
- `clearCompletedJobs(String agentName)` — removes terminal jobs for agent from local state + prunes from work_queue

No change to existing `startJob`, `pollJob`, `cancelJob` methods.

## File Changes

| File | Change |
|---|---|
| `lib/features/workspace/subagents_panel.dart` | Add expandable job section to each agent card; add result dialog; restructure skills selector in create/edit dialog; rename "Capabilities" → "" |
| `lib/providers/subagent_provider.dart` | Add `expandedAgentName` field; add `toggleAgentExpand` / `clearCompletedJobs` methods |
| `lib/features/workspace/skills_panel.dart` | No change (only the dialog uses tree view) |
| `lib/features/workspace/widgets/tree_selector.dart` | No change (already supports multi-select mode) |
| `lib/features/workspace/widgets/ea_list_tile.dart` | No change |

## Future Considerations (out of scope)

- Job logs/streaming in real-time (currently poll-based; WS push would be a separate project)
- Export job results to file
- Job filtering / search across all agents
- Batch operations (re-run, delete multiple jobs)
- Job metrics dashboard (avg duration, success rate, cost tracking)
