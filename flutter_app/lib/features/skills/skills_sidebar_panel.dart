import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import '../../theme/app_theme.dart';
import '../../widgets/scope_picker.dart';

class SkillsSidebarPanel extends ConsumerStatefulWidget {
  const SkillsSidebarPanel({super.key});

  @override
  ConsumerState<SkillsSidebarPanel> createState() =>
      _SkillsSidebarPanelState();
}

class _SkillsSidebarPanelState extends ConsumerState<SkillsSidebarPanel> {
  final _searchController = TextEditingController();
  List<Map<String, dynamic>> _skills = [];
  bool _loading = true;
  String? _error;
  int _loadSeq = 0;

  @override
  void initState() {
    super.initState();
    _loadSkills();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadSkills() async {
    if (!mounted) return;
    final seq = ++_loadSeq;
    final ws = ref.read(currentWorkspaceIdProvider);
    setState(() {
      _loading = _skills.isEmpty;
      _error = null;
    });
    try {
      final skills = await ref
          .read(apiClientProvider)
          .listSkills(workspaceId: ws);
      if (!mounted ||
          seq != _loadSeq ||
          ref.read(currentWorkspaceIdProvider) != ws) return;
      setState(() {
        _skills = skills.whereType<Map<String, dynamic>>().toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted || seq != _loadSeq) return;
      setState(() {
        _error = 'Cannot load skills: $e';
        _loading = false;
      });
    }
  }

  Future<void> _setScope(
      String name, String scope, List<String> wids) async {
    final host = ref.read(hostProvider);
    final uri = Uri.parse(
        'http://$host/skills/$name/scope?user_id=default_user');
    await http.Client().patch(uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'scope': scope, 'workspace_ids': wids}));
    await _loadSkills();
  }

  List<Map<String, dynamic>> get _filtered {
    final q = _searchController.text.toLowerCase();
    if (q.isEmpty) return _skills;
    return _skills.where((s) {
      final name = (s['name']?.toString() ?? '').toLowerCase();
      final desc = (s['description']?.toString() ?? '').toLowerCase();
      return name.contains(q) || desc.contains(q);
    }).toList();
  }

  String _scope(Map<String, dynamic> skill) =>
      skill['scope']?.toString() ?? 'all';

  List<String> _wids(Map<String, dynamic> skill) {
    final v = skill['workspace_ids'];
    if (v is List) return v.cast<String>();
    return [];
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(currentWorkspaceIdProvider, (prev, next) {
      if (prev != next) _loadSkills();
    });

    final tokens = context.tokens;
    final filtered = _filtered;

    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(tokens.spacing.md, tokens.spacing.lg,
                tokens.spacing.md, tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Symbols.psychology,
                        size: 18, color: tokens.colors.accent),
                    const SizedBox(width: 8),
                    Text('Skills',
                        style: tokens.typography.textTheme.titleLarge
                            ?.copyWith(color: tokens.colors.textPrimary)),
                    const Spacer(),
                    if (_skills.isNotEmpty)
                      Text('${_skills.length}',
                          style: tokens.typography.textTheme.labelSmall
                              ?.copyWith(color: tokens.colors.textTertiary)),
                  ],
                ),
                SizedBox(height: tokens.spacing.sm),
                TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(
                    hintText: 'Search skills...',
                    prefixIcon: Icon(Symbols.search, size: 18),
                    isDense: true,
                  ),
                  onChanged: (_) => setState(() {}),
                ),
              ],
            ),
          ),
          Expanded(
            child: _loading && _skills.isEmpty
                ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
                : _error != null && _skills.isEmpty
                    ? _buildError(tokens)
                    : filtered.isEmpty
                        ? _buildEmpty(tokens)
                        : ListView.builder(
                            padding:
                                EdgeInsets.symmetric(horizontal: tokens.spacing.md),
                            itemCount: filtered.length,
                            itemBuilder: (_, i) =>
                                _buildRow(filtered[i], tokens),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildError(EaTokens tokens) {
    return Center(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_error!, style: TextStyle(color: tokens.colors.error)),
          SizedBox(height: tokens.spacing.sm),
          OutlinedButton(
              onPressed: _loadSkills, child: const Text('Retry')),
        ]),
      ),
    );
  }

  Widget _buildEmpty(EaTokens tokens) {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Symbols.psychology,
            size: 40, color: tokens.colors.textTertiary),
        const SizedBox(height: 8),
        Text('No skills yet',
            style: tokens.typography.textTheme.bodySmall
                ?.copyWith(color: tokens.colors.textTertiary)),
      ]),
    );
  }

  Widget _buildRow(Map<String, dynamic> skill, EaTokens tokens) {
    final name = skill['name']?.toString() ?? '';
    final desc = skill['description']?.toString() ?? '';
    final isLoaded = skill['is_loaded'] == true;
    final scp = _scope(skill);
    final wids = _wids(skill);
    return Container(
      margin: EdgeInsets.only(bottom: tokens.spacing.sm),
      padding: EdgeInsets.all(tokens.spacing.sm),
      decoration: BoxDecoration(
        color: tokens.colors.bgElevated,
        borderRadius: tokens.radius.smAll,
      ),
      child: Row(
        children: [
          Icon(Symbols.psychology, size: 18, color: tokens.colors.accent),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: tokens.typography.textTheme.bodyMedium
                        ?.copyWith(color: tokens.colors.textPrimary)),
                if (desc.isNotEmpty)
                  Text(desc,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: tokens.typography.textTheme.labelSmall
                          ?.copyWith(color: tokens.colors.textTertiary)),
              ],
            ),
          ),
          if (isLoaded) _badge('loaded', tokens.colors.accent, tokens),
          const SizedBox(width: 8),
          ScopePicker(
            scope: scp == 'selected' && wids.isNotEmpty
                ? ScopeState.selected
                : scp == 'none'
                    ? ScopeState.none
                    : ScopeState.all,
            selectedWorkspaceIds: wids,
            onChanged: (c) => _setScope(name, c.scope.name, c.workspaceIds),
          ),
        ],
      ),
    );
  }

  Widget _badge(String label, Color color, EaTokens tokens) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(label,
          style: tokens.typography.textTheme.bodySmall
              ?.copyWith(fontSize: 10, color: color)),
    );
  }
}
