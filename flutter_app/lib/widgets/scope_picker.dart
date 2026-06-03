import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_symbols_icons/symbols.dart';

/// Three-state scope for a resource (tool, skill, subagent).
enum ScopeState { all, selected, none }

/// Represents a scope change event.
class ScopeChange {
  final ScopeState scope;
  final List<String> workspaceIds;

  const ScopeChange({
    required this.scope,
    this.workspaceIds = const [],
  });
}

/// Inline segmented control: [All ✓] [3 WS] [Off].
///
/// All three options are always visible. Current selection is highlighted.
/// Tapping [All] or [Off] applies immediately. Tapping the middle button
/// (which shows the workspace count when Selected) opens a modal.
class ScopePicker extends StatelessWidget {
  final ScopeState scope;
  final List<String> selectedWorkspaceIds;
  final List<Map<String, dynamic>> allWorkspaces;
  final ValueChanged<ScopeChange> onChanged;

  const ScopePicker({
    super.key,
    required this.scope,
    this.selectedWorkspaceIds = const [],
    this.allWorkspaces = const [],
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final allActive = scope == ScopeState.all;
    final selActive = scope == ScopeState.selected;
    final noneActive = scope == ScopeState.none;

    final selLabel = selActive && selectedWorkspaceIds.isNotEmpty
        ? '${selectedWorkspaceIds.length} WS'
        : 'Select';

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildSegment(
          context: context,
          label: 'All ✓',
          active: allActive,
          onTap: () => onChanged(const ScopeChange(scope: ScopeState.all)),
        ),
        const SizedBox(width: 2),
        _buildSegment(
          context: context,
          label: selLabel,
          active: selActive,
          onTap: () => _showWorkspaceModal(context),
        ),
        const SizedBox(width: 2),
        _buildSegment(
          context: context,
          label: 'Off',
          active: noneActive,
          onTap: () => onChanged(const ScopeChange(scope: ScopeState.none)),
        ),
      ],
    );
  }

  Widget _buildSegment({
    required BuildContext context,
    required String label,
    required bool active,
    required VoidCallback onTap,
  }) {
    final color = active ? Colors.green : Colors.grey;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: BoxDecoration(
          color: active ? color.withAlpha(20) : Colors.transparent,
          border: Border.all(color: color.withAlpha(active ? 150 : 80)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: color,
            fontWeight: active ? FontWeight.w700 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  void _showWorkspaceModal(BuildContext context) {
    showDialog<ScopeChange>(
      context: context,
      builder: (ctx) => _WorkspaceChecklistDialog(
        allWorkspaces: allWorkspaces,
        selectedIds: selectedWorkspaceIds,
        onApply: (ids) {
          onChanged(ScopeChange(
            scope: ids.isEmpty ? ScopeState.none : ScopeState.selected,
            workspaceIds: ids,
          ));
        },
      ),
    );
  }
}

class _WorkspaceChecklistDialog extends StatefulWidget {
  final List<Map<String, dynamic>> allWorkspaces;
  final List<String> selectedIds;
  final ValueChanged<List<String>> onApply;

  const _WorkspaceChecklistDialog({
    required this.allWorkspaces,
    required this.selectedIds,
    required this.onApply,
  });

  @override
  State<_WorkspaceChecklistDialog> createState() =>
      _WorkspaceChecklistDialogState();
}

class _WorkspaceChecklistDialogState extends State<_WorkspaceChecklistDialog> {
  late Set<String> _selected;

  @override
  void initState() {
    super.initState();
    _selected = Set<String>.from(widget.selectedIds);
  }

  bool get _allSelected => _selected.length == widget.allWorkspaces.length;

  void _selectAll() {
    setState(() {
      _selected = widget.allWorkspaces
          .map((w) => w['id'] as String)
          .toSet();
    });
  }

  void _deselectAll() {
    setState(() => _selected.clear());
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Select Workspaces'),
      content: SizedBox(
        width: 320,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton.icon(
                  onPressed: _selectAll,
                  icon: const Icon(Symbols.select_all, size: 14),
                  label: const Text('All', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                  ),
                ),
                TextButton.icon(
                  onPressed: _deselectAll,
                  icon: const Icon(Symbols.deselect, size: 14),
                  label: const Text('None', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (widget.allWorkspaces.isEmpty)
              const Text('No workspaces available.')
            else
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: widget.allWorkspaces
                      .map((ws) {
                        final id = ws['id'] as String;
                        final name = ws['name'] as String? ?? id;
                        return CheckboxListTile(
                          title: Text(name, style: const TextStyle(fontSize: 13)),
                          subtitle: Text(id, style: Theme.of(context).textTheme.bodySmall),
                          value: _selected.contains(id),
                          onChanged: (checked) {
                            setState(() {
                              if (checked == true) {
                                _selected.add(id);
                              } else {
                                _selected.remove(id);
                              }
                            });
                          },
                          dense: true,
                        );
                      })
                      .toList(),
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            widget.onApply(_selected.toList());
            Navigator.of(context).pop();
          },
          child: const Text('Apply'),
        ),
      ],
    );
  }
}
