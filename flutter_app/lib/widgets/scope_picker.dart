import 'package:flutter/material.dart';
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

/// Tappable scope badge + popup menu + workspace modal.
///
/// Displays one of:
///   [All ✓]  — green, enabled everywhere
///   [3 WS ✓] — green, enabled for N workspaces
///   [Off]    — grey, disabled
///
/// Tapping opens a popup menu. Choosing "Selected" opens a modal
/// with a workspace checklist.
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
    final (label, color) = switch (scope) {
      ScopeState.all => ('All ✓', Colors.green),
      ScopeState.selected => ('${selectedWorkspaceIds.length} WS ✓', Colors.green),
      ScopeState.none => ('Off', Colors.grey),
    };
    return GestureDetector(
      onTap: () => _showPopup(context),
      child: Tooltip(
        message: scope == ScopeState.selected && selectedWorkspaceIds.isNotEmpty
            ? _workspaceNames()
            : '',
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            border: Border.all(color: color.withAlpha(100)),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            label,
            style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }

  String _workspaceNames() {
    return selectedWorkspaceIds
        .map((id) {
          final ws = allWorkspaces.cast<Map<String, dynamic>?>().firstWhere(
                (w) => w?['id'] == id,
                orElse: () => null,
              );
          return ws?['name'] as String? ?? id;
        })
        .join(', ');
  }

  void _showPopup(BuildContext context) {
    final renderBox = context.findRenderObject() as RenderBox;
    final offset = renderBox.localToGlobal(Offset.zero);
    final size = renderBox.size;
    showMenu<String>(
      context: context,
      position: RelativeRect.fromLTRB(
        offset.dx,
        offset.dy + size.height + 4,
        offset.dx + size.width,
        offset.dy + size.height + 4,
      ),
      items: [
        PopupMenuItem<String>(
          value: 'all',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(scope == ScopeState.all ? Symbols.radio_button_checked : Symbols.radio_button_unchecked, size: 18),
              const SizedBox(width: 8),
              const Flexible(child: Text('Enable for all workspaces')),
            ],
          ),
        ),
        PopupMenuItem<String>(
          value: 'selected',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(scope == ScopeState.selected ? Symbols.radio_button_checked : Symbols.radio_button_unchecked, size: 18),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  scope == ScopeState.selected && selectedWorkspaceIds.isNotEmpty
                      ? 'Enable for selected workspaces (${selectedWorkspaceIds.length})…'
                      : 'Enable for selected workspaces…',
                ),
              ),
            ],
          ),
        ),
        PopupMenuItem<String>(
          value: 'none',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(scope == ScopeState.none ? Symbols.radio_button_checked : Symbols.radio_button_unchecked, size: 18),
              const SizedBox(width: 8),
              const Flexible(child: Text('Disable')),
            ],
          ),
        ),
      ],
    ).then((value) {
      if (value == null) return;
      if (value == 'selected') {
        _showWorkspaceModal(context);
      } else {
        onChanged(ScopeChange(
          scope: value == 'all' ? ScopeState.all : ScopeState.none,
        ));
      }
    });
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

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Select Workspaces'),
      content: SizedBox(
        width: 300,
        child: widget.allWorkspaces.isEmpty
            ? const Text('No workspaces available.')
            : ListView(
                shrinkWrap: true,
                children: widget.allWorkspaces
                    .map((ws) {
                      final id = ws['id'] as String;
                      final name = ws['name'] as String? ?? id;
                      return CheckboxListTile(
                        title: Text(name),
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
