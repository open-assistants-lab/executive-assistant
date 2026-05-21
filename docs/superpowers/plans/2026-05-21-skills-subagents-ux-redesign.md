# Skills & Subagents UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Skills and Subagents panels with consistent list tiles, grouped tree view for tool/model selection, and restructured subagent editor.

**Architecture:** Two new reusable widgets (`EaListTile`, `GroupedTreeSelector`) created first, then panels refactored to use them. Subagent editor dialog restructured to surface skills and use tree selector for tools.

**Tech Stack:** Flutter, Riverpod, Material Symbols, EaTokens color system

---

### Task 1: Create EaListTile shared widget

**Files:**
- Create: `flutter_app/lib/features/workspace/widgets/ea_list_tile.dart`
- Test: verify it compiles in the analyzer

- [ ] **Step 1: Create directory and widget file**

Create the `widgets` subdirectory and file:

```bash
mkdir -p flutter_app/lib/features/workspace/widgets
```

```dart
// flutter_app/lib/features/workspace/widgets/ea_list_tile.dart
import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class EaListTile extends StatelessWidget {
  final Widget leading;
  final String title;
  final String? subtitle;
  final Widget? subtitleTrailing;
  final List<Widget>? chips;
  final List<Widget>? trailingBadges;
  final List<Widget>? trailingActions;
  final VoidCallback? onTap;

  const EaListTile({
    super.key,
    required this.leading,
    required this.title,
    this.subtitle,
    this.subtitleTrailing,
    this.chips,
    this.trailingBadges,
    this.trailingActions,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: t.colors.borderSubtle)),
        ),
        padding: EdgeInsets.symmetric(
          horizontal: t.spacing.md,
          vertical: t.spacing.sm,
        ),
        child: Row(
          children: [
            leading,
            SizedBox(width: t.spacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          title,
                          style: t.typography.textTheme.bodyMedium?.copyWith(
                            color: t.colors.textPrimary,
                            fontSize: 13,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (subtitleTrailing != null) ...[
                        const SizedBox(width: 4),
                        subtitleTrailing!,
                      ],
                    ],
                  ),
                  if (subtitle != null)
                    Padding(
                      padding: EdgeInsets.only(top: 2),
                      child: Text(
                        subtitle!,
                        style: t.typography.textTheme.bodySmall?.copyWith(
                          color: t.colors.textSecondary,
                          fontSize: 11,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  if (chips != null && chips!.isNotEmpty)
                    Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: Wrap(
                        spacing: 4,
                        runSpacing: 2,
                        children: chips!,
                      ),
                    ),
                ],
              ),
            ),
            if (trailingBadges != null) ...trailingBadges!,
            if (trailingActions != null) ...[
              const SizedBox(width: 4),
              ...trailingActions!,
            ],
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Verify analyzer passes**

Run: `cd flutter_app && dart analyze lib/features/workspace/widgets/ea_list_tile.dart`
Expected: No issues found.

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/workspace/widgets/ea_list_tile.dart
git commit -m "feat: add EaListTile shared widget for consistent panel list items"
```

---

### Task 2: Create GroupedTreeSelector widget

**Files:**
- Create: `flutter_app/lib/features/workspace/widgets/tree_selector.dart`

- [ ] **Step 1: Define the data model and widget**

```dart
// flutter_app/lib/features/workspace/widgets/tree_selector.dart
import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

enum TreeSelectionMode { multi, single }

class TreeSelectorGroup<T> {
  final String label;
  final List<TreeSelectorItem<T>> items;
  const TreeSelectorGroup({required this.label, required this.items});
}

class TreeSelectorItem<T> {
  final String label;
  final T value;
  const TreeSelectorItem({required this.label, required this.value});
}

class GroupedTreeSelector<T> extends StatefulWidget {
  final List<TreeSelectorGroup<T>> groups;
  final Set<T> selected;
  final ValueChanged<Set<T>> onChanged;
  final TreeSelectionMode mode;
  final String searchHint;

  const GroupedTreeSelector({
    super.key,
    required this.groups,
    required this.selected,
    required this.onChanged,
    this.mode = TreeSelectionMode.multi,
    this.searchHint = 'Search...',
  });

  @override
  State<GroupedTreeSelector<T>> createState() => _GroupedTreeSelectorState<T>();
}

class _GroupedTreeSelectorState<T> extends State<GroupedTreeSelector<T>> {
  final _searchCtrl = TextEditingController();
  String _query = '';
  final Set<String> _expandedGroups = {};

  @override
  void initState() {
    super.initState();
    _searchCtrl.addListener(() => setState(() => _query = _searchCtrl.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  List<TreeSelectorGroup<T>> get _filteredGroups {
    if (_query.isEmpty) return widget.groups;
    return widget.groups.where((g) {
      if (g.label.toLowerCase().contains(_query)) return true;
      return g.items.any((i) => i.label.toLowerCase().contains(_query));
    }).map((g) {
      if (_query.isEmpty) return g;
      final filtered = g.items.where((i) => i.label.toLowerCase().contains(_query)).toList();
      return TreeSelectorGroup(label: g.label, items: filtered);
    }).toList();
  }

  int _selectedCount(TreeSelectorGroup<T> group) {
    return group.items.where((i) => widget.selected.contains(i.value)).length;
  }

  bool? _triState(TreeSelectorGroup<T> group) {
    final count = _selectedCount(group);
    if (count == 0) return false;
    if (count == group.items.length) return true;
    return null; // partial
  }

  void _toggleGroup(TreeSelectorGroup<T> group, bool? selectAll) {
    final updated = Set<T>.from(widget.selected);
    if (selectAll == true) {
      for (final item in group.items) {
        updated.add(item.value);
      }
    } else {
      for (final item in group.items) {
        updated.remove(item.value);
      }
    }
    widget.onChanged(updated);
  }

  void _toggleItem(T item) {
    final updated = Set<T>.from(widget.selected);
    if (widget.mode == TreeSelectionMode.single) {
      updated.clear();
      updated.add(item);
    } else {
      if (updated.contains(item)) {
        updated.remove(item);
      } else {
        updated.add(item);
      }
    }
    widget.onChanged(updated);
  }

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final filtered = _filteredGroups;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          height: 32,
          child: TextField(
            controller: _searchCtrl,
            style: t.typography.textTheme.bodySmall?.copyWith(
              color: t.colors.textPrimary,
              fontSize: 12,
            ),
            decoration: InputDecoration(
              hintText: widget.searchHint,
              hintStyle: t.typography.textTheme.bodySmall?.copyWith(
                color: t.colors.textTertiary,
                fontSize: 12,
              ),
              prefixIcon: Icon(Symbols.search, size: 16, color: t.colors.textTertiary),
              contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 8),
              border: OutlineInputBorder(
                borderRadius: t.radius.smAll,
                borderSide: BorderSide(color: t.colors.borderDefault),
              ),
              filled: true,
              fillColor: t.colors.bgField,
              isDense: true,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Flexible(
          child: ListView(
            shrinkWrap: true,
            children: filtered.map((group) => _buildGroup(context, group)).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildGroup(BuildContext context, TreeSelectorGroup<T> group) {
    final t = context.tokens;
    final isExpanded = _expandedGroups.contains(group.label);
    final selectedCount = _selectedCount(group);
    final totalCount = group.items.length;
    final triState = _triState(group);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        InkWell(
          onTap: () {
            setState(() {
              if (isExpanded) {
                _expandedGroups.remove(group.label);
              } else {
                _expandedGroups.add(group.label);
              }
            });
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
            decoration: BoxDecoration(
              color: t.colors.bgElevated,
              borderRadius: t.radius.smAll,
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 24,
                  height: 24,
                  child: Checkbox(
                    value: triState,
                    tristate: true,
                    onChanged: (v) => _toggleGroup(group, v),
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    visualDensity: VisualDensity.compact,
                  ),
                ),
                Icon(
                  isExpanded ? Icons.expand_more : Icons.chevron_right,
                  size: 18,
                  color: t.colors.textTertiary,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    group.label,
                    style: t.typography.textTheme.bodySmall?.copyWith(
                      color: t.colors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ),
                Text(
                  '$selectedCount/$totalCount',
                  style: t.typography.textTheme.bodySmall?.copyWith(
                    color: t.colors.textTertiary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (isExpanded)
          ...group.items.map((item) => _buildItem(context, item)),
      ],
    );
  }

  Widget _buildItem(BuildContext context, TreeSelectorItem<T> item) {
    final t = context.tokens;
    final isSelected = widget.selected.contains(item.value);

    return InkWell(
      onTap: () => _toggleItem(item.value),
      child: Padding(
        padding: const EdgeInsets.only(left: 40, right: 4, top: 2, bottom: 2),
        child: Row(
          children: [
            if (widget.mode == TreeSelectionMode.multi)
              SizedBox(
                width: 20,
                height: 20,
                child: Checkbox(
                  value: isSelected,
                  onChanged: (_) => _toggleItem(item.value),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                ),
              )
            else
              SizedBox(
                width: 20,
                height: 20,
                child: Radio<T>(
                  value: item.value,
                  groupValue: isSelected ? item.value : null,
                  onChanged: (_) => _toggleItem(item.value),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                ),
              ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                item.label,
                style: t.typography.textTheme.bodySmall?.copyWith(
                  color: isSelected ? t.colors.textPrimary : t.colors.textSecondary,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Verify analyzer passes**

Run: `cd flutter_app && dart analyze lib/features/workspace/widgets/tree_selector.dart`
Expected: No issues found.

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/workspace/widgets/tree_selector.dart
git commit -m "feat: add GroupedTreeSelector widget (multi/single mode, search, tri-state)"
```

---

### Task 3: Redesign Skills Panel

**Files:**
- Modify: `flutter_app/lib/features/workspace/skills_panel.dart`

- [ ] **Step 1: Import shared widget and add usage count logic**

Add import at top of `skills_panel.dart`:
```dart
import 'widgets/ea_list_tile.dart';
```

Add a field to the state class to hold loaded subagents for computing usage count:
```dart
List<SubagentAgentDef>? _allAgents;
```

In `_showCreateDialog`, after loading skills, also load subagents for cross-reference:
```dart
try {
  final agentsJson = await ref.read(apiClientProvider).listSubagents(workspaceId: wsId);
  _allAgents = agentsJson.map((j) => SubagentAgentDef.fromJson(j)).toList();
} catch (_) {}
```

Add a helper method to compute usage count:
```dart
int _usageCount(String skillName) {
  if (_allAgents == null) return 0;
  return _allAgents!.where((a) => a.skills?.contains(skillName) == true).length;
}
```

Replace the `_buildBody` ListView to use `EaListTile` instead of `ListTile`:
```dart
// In builder, replace ListTile with:
EaListTile(
  leading: Icon(Symbols.bolt, size: 18, color: context.tokens.colors.accent),
  title: skillName,
  subtitle: usageCount > 0 ? 'used by $usageCount agents' : null,
  trailingBadges: [
    _ScopeBadge(label: scope),
  ],
  trailingActions: [
    IconButton(
      icon: Icon(Symbols.edit, size: 16),
      onPressed: () => _showEditDialog(agent),
    ),
    IconButton(
      icon: Icon(Symbols.delete, size: 16),
      onPressed: () => _confirmDelete(agent),
    ),
  ],
  onTap: () => _showEditDialog(agent),
)
```

Note: Replace the entire `itemBuilder` in the `ListView.builder` section of `_buildBody` (around line 152) to use `EaListTile`.

- [ ] **Step 2: Verify analyzer passes**

Run: `cd flutter_app && dart analyze lib/features/workspace/skills_panel.dart`
Expected: No issues found.

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/workspace/skills_panel.dart
git commit -m "refactor: skills panel uses EaListTile, adds usage count"
```

---

### Task 4: Redesign Subagents Panel List

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart`

- [ ] **Step 1: Import shared widget and create skill chip helper**

Add imports at top:
```dart
import 'widgets/ea_list_tile.dart';
```

Add a helper method to build skill chips:
```dart
List<Widget> _skillChips(List<String>? skills) {
  if (skills == null || skills.isEmpty) return [];
  final chips = skills.take(3).map((s) => _ChipLabel(label: s));
  if (skills.length > 3) {
    return [...chips, _ChipLabel(label: '+${skills.length - 3}')];
  }
  return [...chips];
}
```

- [ ] **Step 2: Replace the list tile in the builder**

In `_buildBody` around line 156, replace the `_SubagentTile` usage with:
```dart
EaListTile(
  leading: Icon(Symbols.smart_toy, size: 18, color: context.tokens.colors.accent),
  title: agent.name,
  subtitle: agent.description.isEmpty ? null : agent.description,
  chips: _skillChips(agent.skills),
  trailingBadges: [
    _ScopeBadge(label: agent.scope),
    _StatusBadge(label: statusLabel),
  ],
  trailingActions: [
    if (!hasRunning)
      IconButton(
        icon: Icon(Symbols.play_arrow, size: 16),
        onPressed: onStart,
      ),
    IconButton(
      icon: Icon(Symbols.edit, size: 16),
      onPressed: onEdit,
    ),
    if (!hasRunning)
      IconButton(
        icon: Icon(Symbols.delete, size: 16),
        onPressed: onDelete,
      ),
  ],
  onTap: onEdit,
)
```

Add a small `_ChipLabel` widget at the bottom of the file:
```dart
class _ChipLabel extends StatelessWidget {
  final String label;
  const _ChipLabel({required this.label});

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: t.colors.accentMuted,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: t.typography.textTheme.bodySmall?.copyWith(
          fontSize: 10,
          color: t.colors.accent,
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Verify analyzer passes**

Run: `cd flutter_app && dart analyze lib/features/workspace/subagents_panel.dart`
Expected: No issues found.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart
git commit -m "refactor: subagents panel uses EaListTile, shows skill chips on tiles"
```

---

### Task 5: Restructure Subagent Create & Edit Dialogs

**Files:**
- Modify: `flutter_app/lib/features/workspace/subagents_panel.dart`

- [ ] **Step 1: Add import for tree selector**

```dart
import 'widgets/tree_selector.dart';
```

- [ ] **Step 2: Add grouping helper function**

Add a utility function to group tools by prefix:
```dart
List<TreeSelectorGroup<String>> _groupTools(List<String> tools) {
  final groups = <String, List<String>>{};
  for (final tool in tools) {
    String prefix;
    if (tool.startsWith('mcp__')) {
      prefix = 'mcp';
    } else if (tool.contains('_')) {
      prefix = tool.split('_').first;
    } else {
      prefix = 'other';
    }
    groups.putIfAbsent(prefix, () => []);
    groups[prefix]!.add(tool);
  }
  final sortedKeys = groups.keys.toList()..sort();
  return sortedKeys.map((key) {
    final items = groups[key]!..sort();
    return TreeSelectorGroup<String>(
      label: key,
      items: items.map((t) {
        final displayName = t.startsWith('$key\_') ? t.substring(key.length + 1) : t;
        return TreeSelectorItem(label: displayName, value: t);
      }).toList(),
    );
  }).toList();
}
```

- [ ] **Step 3: Restructure the create dialog**

In `_showCreateDialog`, replace the entire "Advanced" `ExpansionTile` (lines 273-456) with inline sections:

```dart
// Section 2: Skills & Capabilities (replaces "Advanced")
const SizedBox(height: 14),
Row(
  children: [
    Text('Skills & Capabilities',
      style: t.typography.textTheme.titleSmall?.copyWith(
        color: t.colors.textPrimary,
      )),
  ],
),
const SizedBox(height: 8),

// Skills chips
if (allSkills != null) ...[
  Wrap(
    spacing: 6,
    runSpacing: 4,
    children: [
      ...selectedSkills.map((s) => Chip(
        label: Text(s, style: TextStyle(fontSize: 11, color: t.colors.accent)),
        backgroundColor: t.colors.accentMuted,
        deleteIcon: Icon(Icons.close, size: 14, color: t.colors.accent),
        onDeleted: () => setDialogState(() => selectedSkills.remove(s)),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        visualDensity: VisualDensity.compact,
      )),
      ActionChip(
        label: Text('+ Add skill', style: TextStyle(fontSize: 11, color: t.colors.accent)),
        onPressed: () => setDialogState(() => selectedSkills = allSkills!.toSet()),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        visualDensity: VisualDensity.compact,
      ),
    ],
  ),
  const SizedBox(height: 10),
],

// Grouped tree selector for tools
if (allTools != null) ...[
  Text('Tools',
    style: t.typography.textTheme.bodySmall?.copyWith(
      color: t.colors.textSecondary,
    )),
  const SizedBox(height: 4),
  SizedBox(
    height: 180,
    child: GroupedTreeSelector<String>(
      groups: _groupTools(allTools),
      selected: selectedTools,
      onChanged: (v) => setDialogState(() => selectedTools = v),
      searchHint: 'Filter tools...',
    ),
  ),
  const SizedBox(height: 14),
],

// Section 3: Limits (collapsible)
ExpansionTile(
  title: Text('Limits',
    style: t.typography.textTheme.bodySmall?.copyWith(
      color: t.colors.textSecondary,
    )),
  initiallyExpanded: false,
  children: [
    // Same three number fields as before
    Row(
      children: [
        Expanded(child: _NumberField(label: 'Max LLM calls', value: maxLlmCalls, onChanged: (v) => setDialogState(() => maxLlmCalls = v as int))),
        const SizedBox(width: 8),
        Expanded(child: _NumberField(label: 'Cost limit (\$)', value: costLimitUsd, isDouble: true, onChanged: (v) => setDialogState(() => costLimitUsd = v as double))),
        const SizedBox(width: 8),
        Expanded(child: _NumberField(label: 'Timeout (s)', value: timeoutSeconds, onChanged: (v) => setDialogState(() => timeoutSeconds = v as int))),
      ],
    ),
  ],
),
```

Remove the old `allTools` filter:
```dart
// Remove this line from the create dialog:
//    .where((t) => !t.startsWith('subagent_'))
```

- [ ] **Step 4: Restructure the edit dialog**

Apply the same restructuring in `_showEditDialog` (around lines 704-846):
- Remove the tools/skills sections from their current locations
- Add the same inline "Skills & Capabilities" section and grouped tree selector
- Add the same collapsible "Limits" section

The edit dialog should follow the exact same structure as the create dialog — the only difference is pre-populated values.

- [ ] **Step 5: Verify analyzer passes**

Run: `cd flutter_app && dart analyze lib/features/workspace/subagents_panel.dart`
Expected: No issues found.

- [ ] **Step 6: Run existing tests**

Run: `cd flutter_app && flutter test test/providers/agent_provider_test.dart`
Expected: All 27 tests still pass.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/workspace/subagents_panel.dart
git commit -m "refactor: subagent editor restructured — skills at top, grouped tree selector for tools, limits collapsible"
```
