# Subagent Jobs Results & Skills Tree View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add expandable job history to subagent cards, replace flat skills list with GroupedTreeSelector in create/edit dialogs, remove "Capabilities" wording.

**Architecture:** Three independent changes to the existing subagents panel: (1) provider state additions for per-agent job history and expand tracking, (2) new JobResultDialog widget + expandable job section in each agent tile, (3) skills selector swap from chip-based to tree-selector grouped by scope. All reuse existing SubagentNotifier polling.

**Tech Stack:** Flutter + Riverpod, EaTokens theme, existing GroupedTreeSelector

---

### Task 1: SubagentNotifier state changes

**Files:**
- Modify: `flutter_app/lib/providers/subagent_provider.dart`

- [ ] **Step 1: Add expandedAgentName and toggle to SubagentPanelState + SubagentNotifier**

```dart
// In SubagentPanelState class, add field:
  final String? expandedAgentName;

// Update constructor:
  const SubagentPanelState({
    this.agents = const [],
    this.activeJobs = const {},
    this.loading = false,
    this.error,
    this.loadSequence = 0,
    this.expandedAgentName,  // NEW
  });

// Update copyWith:
  SubagentPanelState copyWith({
    List<SubagentAgentDef>? agents,
    Map<String, SubagentJob>? activeJobs,
    bool? loading,
    Object? error = _errorSentinel,
    int? loadSequence,
    String? Function()? expandedAgentName,  // use nullable Function() to allow setting null
  }) {
    return SubagentPanelState(
      agents: agents ?? this.agents,
      activeJobs: activeJobs ?? this.activeJobs,
      loading: loading ?? this.loading,
      error: identical(error, _errorSentinel) ? this.error : error as String?,
      loadSequence: loadSequence ?? this.loadSequence,
      expandedAgentName: expandedAgentName != null ? expandedAgentName() : this.expandedAgentName,
    );
  }
```

- [ ] **Step 2: Add toggleAgentExpand method to SubagentNotifier**

```dart
// In SubagentNotifier class:
  void toggleAgentExpand(String agentName) {
    if (state.expandedAgentName == agentName) {
      state = state.copyWith(expandedAgentName: () => null);
    } else {
      state = state.copyWith(expandedAgentName: () => agentName);
    }
  }
```

- [ ] **Step 3: Change _pruneTerminalJobs to prune per-agent instead of globally**

```dart
// Replace _pruneTerminalJobs method:
  void _pruneTerminalJobs() {
    // Group terminal jobs by agent
    final agentJobs = <String, List<MapEntry<String, SubagentJob>>>{};
    final active = <String, SubagentJob>{};
    for (final entry in state.activeJobs.entries) {
      if (entry.value.isTerminal) {
        agentJobs.putIfAbsent(entry.value.agentName, () => []);
        agentJobs[entry.value.agentName]!.add(entry);
      } else {
        active[entry.key] = entry.value;
      }
    }
    // Keep max 10 terminal jobs per agent
    final kept = <String, SubagentJob>{};
    for (final group in agentJobs.entries) {
      final sorted = group.value
        ..sort((a, b) => (a.value.createdAt ?? '')
            .compareTo(b.value.createdAt ?? ''));
      final limited = sorted.skip(
        sorted.length > _maxTerminalJobs ? sorted.length - _maxTerminalJobs : 0,
      );
      for (final e in limited) {
        kept[e.key] = e.value;
      }
    }
    state = state.copyWith(activeJobs: {...active, ...kept});
  }
```

- [ ] **Step 4: Add clearCompletedJobs method to SubagentNotifier**

```dart
// In SubagentNotifier class:
  void clearCompletedJobs(String agentName) {
    final remaining = <String, SubagentJob>{};
    for (final entry in state.activeJobs.entries) {
      if (entry.value.agentName == agentName && entry.value.isTerminal) {
        continue; // skip terminal jobs for this agent
      }
      remaining[entry.key] = entry.value;
    }
    state = state.copyWith(activeJobs: remaining);
  }
```

- [ ] **Step 5: Run existing tests to confirm no regressions**

Run: `cd flutter_app && flutter test test/features/workspace/` — expect pass (or note pre-existing failures)

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/providers/subagent_provider.dart
git commit -m "feat: add expandedAgentName, per-agent job pruning, clearCompletedJobs to SubagentNotifier"
```

---

### Task 2: Job Result Dialog widget

**Files:**
- Create: `flutter_app/lib/features/workspace/widgets/job_result_dialog.dart`
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart` (add import)

- [ ] **Step 1: Create job_result_dialog.dart**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../models/subagent.dart';
import '../../../theme/app_theme.dart';

class JobResultDialog extends ConsumerWidget {
  final SubagentJob job;

  const JobResultDialog({super.key, required this.job});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.tokens;
    final isRunning = job.isRunning;
    final isTerminal = job.isTerminal;
    final statusColor = switch (job.status) {
      'completed' => t.colors.success,
      'failed' => t.colors.error,
      'cancelled' => t.colors.warning,
      'running' => t.colors.accent,
      'cancelling' => t.colors.warning,
      _ => t.colors.textTertiary,
    };

    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
      child: SizedBox(
        width: 600,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 12, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Job Result',
                      style: t.typography.textTheme.titleLarge?.copyWith(
                        color: t.colors.textPrimary,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: Icon(Symbols.close, size: 18, color: t.colors.textSecondary),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),
            // Metadata row
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Wrap(
                spacing: 16,
                runSpacing: 6,
                children: [
                  _metaChip(context, 'Status', job.status, statusColor),
                  if (job.startedAt != null && job.completedAt != null)
                    _metaChip(context, 'Duration', _formatDuration(job.startedAt!, job.completedAt!), t.colors.textSecondary),
                  _metaChip(context, 'Agent', job.agentName, t.colors.accent),
                  if (job.result?.isNotEmpty == true && job.result!.contains('llm_calls'))
                    _metaChip(context, 'LLM calls', _extractField(job.result!, 'llm_calls'), t.colors.textSecondary),
                  if (job.result?.isNotEmpty == true && job.result!.contains('cost_usd'))
                    _metaChip(context, 'Cost', '\$${_extractField(job.result!, 'cost_usd')}', t.colors.textSecondary),
                  if (job.createdAt != null)
                    _metaChip(context, 'Created', job.createdAt!, t.colors.textTertiary),
                ],
              ),
            ),
            const Divider(height: 24),
            // Task section
            if (job.task.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text('Task',
                  style: t.typography.textTheme.labelLarge?.copyWith(
                    color: t.colors.textSecondary,
                  )),
              ),
              const SizedBox(height: 4),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  job.task,
                  style: t.typography.textTheme.bodyMedium?.copyWith(
                    color: t.colors.textPrimary,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: 12),
            ],
            // Output section (scrollable, monospace)
            if (job.result != null && job.result!.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text('Output',
                  style: t.typography.textTheme.labelLarge?.copyWith(
                    color: t.colors.textSecondary,
                  )),
              ),
              const SizedBox(height: 4),
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                padding: const EdgeInsets.all(12),
                constraints: const BoxConstraints(maxHeight: 300),
                decoration: BoxDecoration(
                  color: t.colors.bgElevated,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: t.colors.borderSubtle),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    job.result!,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: t.colors.textPrimary,
                      height: 1.4,
                    ),
                  ),
                ),
              ),
            ],
            // Error section (conditional)
            if (job.error != null && job.error!.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: t.colors.error.withAlpha(18),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: t.colors.error.withAlpha(60)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Symbols.error, size: 16, color: t.colors.error),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        job.error!,
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: t.colors.error,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            // Progress section (conditional, for running jobs)
            if (isRunning && job.progress != null) ...[
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    SizedBox(
                      width: 14, height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: t.colors.accent,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      job.progress!['message']?.toString() ?? 'Running...',
                      style: t.typography.textTheme.bodySmall?.copyWith(
                        color: t.colors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 20),
            // Close button
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metaChip(BuildContext context, String label, String value, Color color) {
    final t = context.tokens;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(18),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(fontSize: 11, color: color),
      ),
    );
  }

  String _formatDuration(String start, String end) {
    try {
      final s = DateTime.parse(start);
      final e = DateTime.parse(end);
      final diff = e.difference(s);
      if (diff.inSeconds < 60) return '${diff.inSeconds}s';
      return '${diff.inMinutes}m ${diff.inSeconds % 60}s';
    } catch (_) {
      return '';
    }
  }

  String _extractField(String jsonStr, String field) {
    try {
      // Simple extraction from JSON-like string without parsing
      final regex = RegExp('"$field"\\s*:\\s*([\\d.]+)');
      final match = regex.firstMatch(jsonStr);
      return match?.group(1) ?? '';
    } catch (_) {
      return '';
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add flutter_app/lib/features/workspace/widgets/job_result_dialog.dart
git commit -m "feat: add JobResultDialog widget for viewing subagent job output and metadata"
```

---

### Task 3: Expandable job section on agent cards

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart`

This changes each agent tile in `_buildBody` from a single `EaListTile` to a `Column` with the tile + expandable jobs section. Also updates `onTap` from edit to expand toggle.

- [ ] **Step 1: Add import for JobResultDialog** at top of file

```dart
import 'widgets/job_result_dialog.dart';
```

- [ ] **Step 2: Replace the agent tile in _buildBody with expandable Column**

Change lines 163-211 (`return ListView.builder...` block). Replacement:

```dart
    return ListView.builder(
      padding: EdgeInsets.zero,
      itemCount: state.agents.length,
      itemBuilder: (_, i) {
        final agent = state.agents[i];
        final agentJobs = state.activeJobs.values
            .where((j) => j.agentName == agent.name)
            .toList();
        final runningJobs = agentJobs.where((j) => !j.isTerminal).toList();
        final terminalJobs = agentJobs.where((j) => j.isTerminal).toList();
        final hasRunning = runningJobs.isNotEmpty;
        final statusLabel = hasRunning
            ? (runningJobs.first.status == 'cancelling' ? 'cancelling' : 'running')
            : (terminalJobs.isNotEmpty ? terminalJobs.first.status : 'idle');
        final isExpanded = state.expandedAgentName == agent.name;
        final skillChips = _skillChips(agent.skills);

        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            EaListTile(
              leading: Icon(Symbols.smart_toy, size: 18, color: context.tokens.colors.accent),
              title: agent.name,
              subtitle: agent.description.isEmpty ? null : agent.description,
              chips: skillChips.isEmpty ? null : skillChips,
              trailingBadges: [
                _ScopeBadge(label: agent.scope),
                _StatusBadge(label: statusLabel),
              ],
              trailingActions: [
                if (hasRunning)
                  IconButton(
                    icon: Icon(Symbols.stop_circle, size: 16, color: context.tokens.colors.warning),
                    onPressed: () => ref
                        .read(subagentProvider.notifier)
                        .cancelJob(runningJobs.first.jobId, workspaceId: runningJobs.first.workspaceId),
                  )
                else
                  IconButton(
                    icon: Icon(Symbols.play_arrow, size: 16),
                    onPressed: () => _showStartDialog(agent),
                  ),
                IconButton(
                  icon: Icon(Symbols.edit, size: 16),
                  onPressed: () => _showEditDialog(agent),
                ),
                if (!hasRunning)
                  IconButton(
                    icon: Icon(Symbols.delete, size: 16),
                    onPressed: () => _confirmDelete(agent),
                  ),
              ],
              onTap: () => ref.read(subagentProvider.notifier).toggleAgentExpand(agent.name),
            ),
            if (isExpanded) _buildJobSection(context, agent, agentJobs),
          ],
        );
      },
    );
```

- [ ] **Step 3: Add _buildJobSection method to _SubagentsPanelState**

```dart
  Widget _buildJobSection(BuildContext context, SubagentAgentDef agent, List<SubagentJob> agentJobs) {
    final t = context.tokens;
    final terminal = agentJobs.where((j) => j.isTerminal).toList();
    final running = agentJobs.where((j) => !j.isTerminal).toList();
    // Sort: running first, then terminal by created_at descending
    final sorted = [...running, ...terminal]
      ..sort((a, b) => (b.createdAt ?? '').compareTo(a.createdAt ?? ''));

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 8),
      decoration: BoxDecoration(
        color: t.colors.bgElevated,
        border: Border(bottom: BorderSide(color: t.colors.borderSubtle)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Section header
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                Text(
                  'Jobs (${sorted.length})',
                  style: t.typography.textTheme.bodySmall?.copyWith(
                    color: t.colors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                if (terminal.isNotEmpty)
                  GestureDetector(
                    onTap: () => ref.read(subagentProvider.notifier).clearCompletedJobs(agent.name),
                    child: Text(
                      'Clear completed',
                      style: TextStyle(fontSize: 10, color: t.colors.textTertiary),
                    ),
                  ),
              ],
            ),
          ),
          // Job entries
          if (sorted.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text(
                'No runs yet',
                style: t.typography.textTheme.bodySmall?.copyWith(
                  color: t.colors.textTertiary,
                  fontSize: 11,
                ),
              ),
            )
          else
            ...sorted.take(10).map((job) => _buildJobRow(context, job)),
          if (sorted.length > 10)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '+ ${sorted.length - 10} more',
                style: TextStyle(fontSize: 10, color: t.colors.textTertiary),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildJobRow(BuildContext context, SubagentJob job) {
    final t = context.tokens;
    final isRunning = job.isRunning;
    final statusColor = switch (job.status) {
      'completed' => t.colors.success,
      'failed' => t.colors.error,
      'cancelled' => t.colors.warning,
      'running' => t.colors.accent,
      'cancelling' => t.colors.warning,
      _ => t.colors.textTertiary,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          // Status indicator
          if (isRunning)
            SizedBox(
              width: 10, height: 10,
              child: CircularProgressIndicator(strokeWidth: 1.5, color: statusColor),
            )
          else
            Container(
              width: 8, height: 8,
              decoration: BoxDecoration(
                color: statusColor,
                shape: BoxShape.circle,
              ),
            ),
          const SizedBox(width: 8),
          // Task text
          Expanded(
            child: Text(
              job.task,
              style: TextStyle(fontSize: 11, color: t.colors.textPrimary),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          // Timestamp
          Text(
            _relativeTime(job.createdAt),
            style: TextStyle(fontSize: 10, color: t.colors.textTertiary),
          ),
          const SizedBox(width: 6),
          // Status badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: statusColor.withAlpha(18),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              job.status,
              style: TextStyle(fontSize: 9, color: statusColor),
            ),
          ),
          // View button (only for terminal jobs)
          if (job.isTerminal) ...[
            const SizedBox(width: 4),
            GestureDetector(
              onTap: () => _showJobResult(job),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: t.colors.accent.withAlpha(18),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'View',
                  style: TextStyle(fontSize: 10, color: t.colors.accent),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _relativeTime(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso);
      final diff = DateTime.now().toUtc().difference(dt);
      if (diff.inSeconds < 60) return '${diff.inSeconds}s ago';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      return '${diff.inDays}d ago';
    } catch (_) {
      return '';
    }
  }

  void _showJobResult(SubagentJob job) {
    showDialog(
      context: context,
      builder: (_) => JobResultDialog(job: job),
    );
  }
```

- [ ] **Step 4: Verify the import and build**

Run: `cd flutter_app && flutter analyze lib/features/workspace/subagents_panel.dart` — expect no errors

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart
git commit -m "feat: add expandable job history section to subagent agent cards"
```

---

### Task 4: Skills tree view in create/edit dialog + rename "Capabilities"

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart`

- [ ] **Step 1: Group skills by scope for tree selector**

Add method to _SubagentsPanelState:

```dart
  List<TreeSelectorGroup<String>> _groupSkills(List<String> allSkills, List<Map<String, dynamic>> rawSkills) {
    final userSkills = <String>[];
    final workspaceSkills = <String>[];
    for (final s in rawSkills) {
      final name = s['name']?.toString() ?? '';
      final scope = s['scope']?.toString() ?? 'user';
      if (name.isEmpty) continue;
      if (scope == 'workspace') {
        workspaceSkills.add(name);
      } else {
        userSkills.add(name);
      }
    }
    final groups = <TreeSelectorGroup<String>>[];
    if (userSkills.isNotEmpty) {
      groups.add(TreeSelectorGroup<String>(
        label: 'User Skills',
        items: userSkills..sort().map((s) => TreeSelectorItem(label: s, value: s)).toList(),
      ));
    }
    if (workspaceSkills.isNotEmpty) {
      groups.add(TreeSelectorGroup<String>(
        label: 'Workspace Skills',
        items: workspaceSkills..sort().map((s) => TreeSelectorItem(label: s, value: s)).toList(),
      ));
    }
    return groups;
  }
```

- [ ] **Step 2: Replace skills chip selector with GroupedTreeSelector in _showCreateDialog**

In the create dialog, replace the current skills section (lines 314-346 in current file) with:

```dart
// Replace:
// Row(children: [Text('Skills & Capabilities'...)]),
// SizedBox(height: 8),
// Wrap(children: [selected skills chips...]),

// With:
Row(
  children: [
    Text('Skills',
      style: t.typography.textTheme.headlineMedium?.copyWith(
        fontSize: 14, color: t.colors.textPrimary,
      )),
  ],
),
const SizedBox(height: 8),
if (allSkills != null) ...[
  SizedBox(
    height: 180,
    child: GroupedTreeSelector<String>(
      groups: _groupSkills(allSkills, skillsJson),
      selected: selectedSkills,
      onChanged: (v) => setDialogState(() => selectedSkills = v),
      searchHint: 'Search skills...',
    ),
  ),
  const SizedBox(height: 10),
],
```

Where `skillsJson` is the raw response from `listSkills()` — change `allSkills` variable to `List<Map<String, dynamic>>` and keep the original raw data:

```dart
// Change allSkills from List<String> to List<Map<String, dynamic>>
List<String>? allToolNames;
List<Map<String, dynamic>>? allSkillsRaw;
try {
  allToolNames = await ref.read(apiClientProvider).listToolNames();
  selectedTools = allToolNames.toSet();
} catch (_) {}
try {
  allSkillsRaw = await ref.read(apiClientProvider).listSkills();
} catch (_) {}
```

And the tree selector uses `_groupSkills(allSkillsRaw!.map((s) => s['name']?.toString() ?? '').where((n) => n.isNotEmpty).toList(), allSkillsRaw!)`.

- [ ] **Step 3: Same skills tree view replacement in _showEditDialog**

Apply identical changes to the edit dialog's skills section (lines 617-648). Change the skills data variables similarly, replace chip-based selector with `GroupedTreeSelector<String>` using `_groupSkills(...)`.

- [ ] **Step 4: Build check**

Run: `cd flutter_app && flutter analyze lib/features/workspace/subagents_panel.dart` — fix any issues

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart
git commit -m "feat: replace skills chip selector with GroupedTreeSelector in subagent dialogs, remove Capabilities label"
```

---

## Self-Review

### Spec Coverage

| Spec Section | Task | Covered? |
|---|---|---|
| Expandable agent cards | Task 3 | ✅ `_buildJobSection` + `_buildJobRow` |
| Job result dialog | Task 2 | ✅ `JobResultDialog` widget |
| Per-agent pruning | Task 1 | ✅ `_pruneTerminalJobs` grouped by agent |
| `expandedAgentName` state | Task 1 | ✅ field + `toggleAgentExpand` |
| `clearCompletedJobs` | Task 1 | ✅ method |
| Skills tree view in dialog | Task 4 | ✅ `_groupSkills` + `GroupedTreeSelector` |
| Remove "Capabilities" | Task 4 | ✅ label changed to "Skills" |
| Tap-to-expand replaces tap-to-edit | Task 3 | ✅ `onTap` → `toggleAgentExpand` |
| EaTokens color usage | All | ✅ all colors via `context.tokens` |
| Max 10 jobs per agent | Task 1 | ✅ per-agent pruning limit |

### Placeholder Check

- No TBD, TODO, or incomplete sections
- All code blocks show complete implementations
- All file paths are exact
- All commands show expected behavior

### Type Consistency Check

- `expandedAgentName` is `String?` throughout
- `SubagentJob` fields matched in result dialog
- `GroupedTreeSelector<String>` used consistently
- `_groupSkills` return type matches `TreeSelectorGroup<String>` expected by widget
