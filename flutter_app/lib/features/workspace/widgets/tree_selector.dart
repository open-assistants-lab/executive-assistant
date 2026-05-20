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
    return null;
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

    final listView = ListView(
      shrinkWrap: true,
      children: filtered.map((group) => _buildGroup(context, group)).toList(),
    );

    final listContent = widget.mode == TreeSelectionMode.single
        ? RadioGroup<T>(
            groupValue: widget.selected.isEmpty ? null : widget.selected.first,
            onChanged: (T? value) {
              if (value != null) _toggleItem(value);
            },
            child: listView,
          )
        : listView;

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
        Flexible(child: listContent),
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
                  isExpanded ? Symbols.expand_more : Symbols.chevron_right,
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
