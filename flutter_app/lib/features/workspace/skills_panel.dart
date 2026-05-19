import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import '../../theme/app_theme.dart';

class SkillsPanel extends ConsumerStatefulWidget {
  const SkillsPanel({super.key});

  @override
  ConsumerState<SkillsPanel> createState() => _SkillsPanelState();
}

class _SkillsPanelState extends ConsumerState<SkillsPanel> {
  List<Map<String, dynamic>> _skills = [];
  bool _loading = true;
  String? _error;
  int _loadSequence = 0;

  @override
  void initState() {
    super.initState();
    _loadSkills();
  }

  Future<void> _loadSkills() async {
    if (!mounted) return;
    final requestId = ++_loadSequence;
    final requestedWorkspaceId = ref.read(currentWorkspaceIdProvider);
    setState(() {
      _loading = _skills.isEmpty;
      _error = null;
    });
    try {
      final skills = await ref
          .read(apiClientProvider)
          .listSkills(workspaceId: requestedWorkspaceId);
      if (!mounted ||
          requestId != _loadSequence ||
          ref.read(currentWorkspaceIdProvider) != requestedWorkspaceId) {
        return;
      }
      setState(() {
        _skills = skills.whereType<Map<String, dynamic>>().toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted ||
          requestId != _loadSequence ||
          ref.read(currentWorkspaceIdProvider) != requestedWorkspaceId) {
        return;
      }
      setState(() {
        _error = 'Cannot load skills: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(currentWorkspaceIdProvider, (prev, next) {
      if (prev != next) _loadSkills();
    });

    return Container(
      color: context.tokens.colors.bgCanvas,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 52,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: context.tokens.colors.borderSubtle)),
            ),
            child: Row(
              children: [
                Icon(Icons.bolt, size: 18, color: context.tokens.colors.accent),
                const SizedBox(width: 8),
                Text(
                  'Skills',
                  style: context.tokens.typography.textTheme.headlineMedium!.copyWith(fontSize: 15),
                ),
                const Spacer(),
                if (_loading && _skills.isNotEmpty)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                const SizedBox(width: 4),
                Text(
                  '${_skills.length}',
                  style: context.tokens.typography.textTheme.bodySmall!.copyWith(
                    color: context.tokens.colors.textTertiary,
                  ),
                ),
                const SizedBox(width: 4),
                InkWell(
                  onTap: _loadSkills,
                  child: Icon(
                    Icons.refresh,
                    size: 16,
                    color: context.tokens.colors.textTertiary,
                  ),
                ),
                const SizedBox(width: 8),
                InkWell(
                  onTap: _showCreateDialog,
                  child: Icon(Icons.add, size: 18, color: context.tokens.colors.textTertiary),
                ),
              ],
            ),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _skills.isEmpty) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (_error != null && _skills.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.error),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: _loadSkills,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    if (_skills.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.bolt_outlined, size: 40, color: context.tokens.colors.textTertiary),
            const SizedBox(height: 8),
            Text(
              'No skills',
              style: context.tokens.typography.textTheme.bodySmall!.copyWith(color: context.tokens.colors.textTertiary),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: EdgeInsets.zero,
      itemCount: _skills.length,
      itemBuilder: (_, i) => _SkillTile(
        skill: _skills[i],
        onView: () => _showDetail(_skills[i]['name']?.toString() ?? ''),
        onDelete: () => _confirmDelete(_skills[i]),
      ),
    );
  }

  Future<void> _showDetail(String name) async {
    if (name.isEmpty) return;
    final workspaceId = ref.read(currentWorkspaceIdProvider);
    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder<Map<String, dynamic>>(
        future: ref
            .read(apiClientProvider)
            .getSkillDetail(name, workspaceId: workspaceId),
        builder: (ctx, snapshot) {
          final content = snapshot.data?['content']?.toString() ?? '';
          return AlertDialog(
            title: Text(name),
            content: SizedBox(
              width: 520,
              child: snapshot.connectionState == ConnectionState.waiting
                  ? const Center(
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : snapshot.hasError
                  ? Text('Cannot load skill: ${snapshot.error}')
                  : SingleChildScrollView(child: SelectableText(content)),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Close'),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _confirmDelete(Map<String, dynamic> skill) async {
    final name = skill['name']?.toString() ?? '';
    if (name.isEmpty) return;
    final scope = _scopeOf(skill);
    final workspaceId = ref.read(currentWorkspaceIdProvider);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete skill?'),
        content: Text(
          'Delete $name from ${scope == 'workspace' ? 'workspace' : 'user'} skills?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    if (confirmed != true) return;
    if (ref.read(currentWorkspaceIdProvider) != workspaceId) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Workspace changed; delete cancelled.')),
      );
      return;
    }
    try {
      await ref
          .read(apiClientProvider)
          .deleteSkill(name, scope: scope, workspaceId: workspaceId);
      await _loadSkills();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Delete failed: $e')));
    }
  }

  Future<void> _showCreateDialog() async {
    final workspaceId = ref.read(currentWorkspaceIdProvider);
    final defaultScope = workspaceId == 'personal' ? 'user' : 'workspace';
    final nameCtrl = TextEditingController();
    final descriptionCtrl = TextEditingController();
    final contentCtrl = TextEditingController();
    var scope = defaultScope;
    var submitting = false;

    final created = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('New Skill'),
          content: SingleChildScrollView(
            child: SizedBox(
              width: 520,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: descriptionCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Description',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: contentCtrl,
                    minLines: 6,
                    maxLines: 10,
                    decoration: const InputDecoration(
                      labelText: 'Content',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    initialValue: scope,
                    decoration: const InputDecoration(
                      labelText: 'Scope',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'user', child: Text('User')),
                      DropdownMenuItem(
                        value: 'workspace',
                        child: Text('Workspace'),
                      ),
                    ],
                    onChanged: submitting
                        ? null
                        : (value) {
                            if (value != null) {
                              setDialogState(() => scope = value);
                            }
                          },
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: submitting ? null : () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: submitting
                  ? null
                  : () async {
                      final name = nameCtrl.text.trim();
                      if (name.isEmpty) return;
                      if (ref.read(currentWorkspaceIdProvider) != workspaceId) {
                        if (!ctx.mounted) return;
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Workspace changed; create cancelled.',
                            ),
                          ),
                        );
                        Navigator.pop(ctx, false);
                        return;
                      }
                      setDialogState(() => submitting = true);
                      try {
                        await ref
                            .read(apiClientProvider)
                            .createSkill(
                              name,
                              descriptionCtrl.text.trim(),
                              contentCtrl.text,
                              scope: scope,
                              workspaceId: workspaceId,
                            );
                        if (ctx.mounted) Navigator.pop(ctx, true);
                      } catch (e) {
                        if (!ctx.mounted) return;
                        setDialogState(() => submitting = false);
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text('Create failed: $e')),
                        );
                      }
                    },
              child: submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Create'),
            ),
          ],
        ),
      ),
    );

    nameCtrl.dispose();
    descriptionCtrl.dispose();
    contentCtrl.dispose();
    if (created == true) await _loadSkills();
  }

  String _scopeOf(Map<String, dynamic> skill) {
    final raw = skill['scope']?.toString() ?? 'user';
    return raw == 'ws' ? 'workspace' : raw;
  }
}

class _SkillTile extends StatelessWidget {
  final Map<String, dynamic> skill;
  final VoidCallback onView;
  final VoidCallback onDelete;

  const _SkillTile({
    required this.skill,
    required this.onView,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final name = skill['name']?.toString() ?? '';
    final description = skill['description']?.toString() ?? '';
    final scope = skill['scope']?.toString() == 'workspace' ? 'ws' : 'user';
    return ListTile(
      dense: true,
      title: Row(
        children: [
          Expanded(
            child: Text(name, style: context.tokens.typography.textTheme.bodyLarge!.copyWith(fontSize: 13)),
          ),
          _ScopeBadge(label: scope),
        ],
      ),
      subtitle: Text(
        description.isEmpty ? 'No description' : description,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: context.tokens.typography.textTheme.bodySmall!.copyWith(fontSize: 11),
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            tooltip: 'View skill',
            icon: const Icon(Icons.visibility_outlined, size: 18),
            onPressed: onView,
          ),
          IconButton(
            tooltip: 'Delete skill',
            icon: const Icon(Icons.delete_outline, size: 18),
            onPressed: onDelete,
          ),
        ],
      ),
    );
  }
}

class _ScopeBadge extends StatelessWidget {
  final String label;

  const _ScopeBadge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(left: 8),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: context.tokens.colors.accent.withAlpha(18),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: context.tokens.typography.textTheme.bodySmall!.copyWith(
          fontSize: 10,
          color: context.tokens.colors.accent,
        ),
      ),
    );
  }
}
