import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../theme/app_theme.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';
import 'skills_panel.dart';
import 'subagents_panel.dart';

typedef WorkspaceFileLoader =
    Future<List<Map<String, dynamic>>> Function(WidgetRef ref);

class WorkspacePanel extends ConsumerStatefulWidget {
  final Duration refreshInterval;
  final WorkspaceFileLoader? fileLoader;

  const WorkspacePanel({
    super.key,
    this.refreshInterval = const Duration(seconds: 3),
    this.fileLoader,
  });

  @override
  ConsumerState<WorkspacePanel> createState() => _WorkspacePanelState();
}

class _WorkspacePanelState extends ConsumerState<WorkspacePanel> {
  List<Map<String, dynamic>> _files = [];
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;
  _WorkspacePanelTab _tab = _WorkspacePanelTab.files;

  @override
  void initState() {
    super.initState();
    _loadFiles();
    _refreshTimer = Timer.periodic(widget.refreshInterval, (_) => _loadFiles());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _fetchFiles() async {
    final host = ref.read(hostProvider);
    final userId = ref.read(userIdProvider);
    final wsId = ref.read(currentWorkspaceIdProvider);
    final url = Uri.parse(
      'http://$host/workspace/json?user_id=$userId&workspace_id=$wsId',
    );
    final response = await http.get(url);
    if (response.statusCode != 200) {
      throw Exception('Failed to load (${response.statusCode})');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return List<Map<String, dynamic>>.from(data['files'] ?? []);
  }

  Future<void> _loadFiles() async {
    if (!mounted) return;
    setState(() {
      _loading = _files.isEmpty;
      _error = null;
    });
    try {
      final files = await (widget.fileLoader?.call(ref) ?? _fetchFiles());
      if (!mounted) return;
      setState(() {
        _files = files;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Cannot connect: $e';
        _loading = false;
      });
    }
  }

  String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(currentWorkspaceIdProvider, (prev, next) {
      if (prev != next) _loadFiles();
    });

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (prev?.status == ChatStatus.streaming &&
          next.status == ChatStatus.idle) {
        _loadFiles();
      }
    });

    return Container(
      color: AppColors.background,
      child: Column(
        children: [
          Expanded(
            child: _tab == _WorkspacePanelTab.files
                ? _buildFilesPanel()
                : _tab == _WorkspacePanelTab.skills
                ? const SkillsPanel()
                : const SubagentsPanel(),
          ),
          _BottomTabs(
            selected: _tab,
            onSelected: (tab) => setState(() => _tab = tab),
          ),
        ],
      ),
    );
  }

  Widget _buildFilesPanel() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          height: 52,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: AppColors.divider)),
          ),
          child: Row(
            children: [
              Icon(Icons.folder, size: 18, color: AppColors.accent),
              const SizedBox(width: 8),
              Text(
                'Files',
                style: AppTypography.sectionTitle.copyWith(fontSize: 15),
              ),
              const Spacer(),
              if (_loading && _files.isNotEmpty)
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              const SizedBox(width: 4),
              Text(
                '${_files.length}',
                style: AppTypography.caption.copyWith(color: AppColors.textDim),
              ),
              const SizedBox(width: 4),
              InkWell(
                onTap: _loadFiles,
                child: Icon(Icons.refresh, size: 16, color: AppColors.textDim),
              ),
            ],
          ),
        ),
        Expanded(child: _buildFilesBody()),
      ],
    );
  }

  Widget _buildFilesBody() {
    if (_loading && _files.isEmpty) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (_error != null && _files.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                style: AppTypography.caption.copyWith(color: AppColors.danger),
              ),
              const SizedBox(height: 8),
              OutlinedButton(onPressed: _loadFiles, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (_files.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.folder_open, size: 40, color: AppColors.textDim),
            const SizedBox(height: 8),
            Text(
              'No files',
              style: AppTypography.caption.copyWith(color: AppColors.textDim),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: EdgeInsets.zero,
      itemCount: _files.length,
      itemBuilder: (_, i) {
        final f = _files[i];
        final name = f['name']?.toString() ?? '';
        final isDir = f['is_dir'] == true;
        final size = f['size'] as int? ?? 0;
        return ListTile(
          dense: true,
          leading: Icon(
            isDir ? Icons.folder : Icons.description,
            size: 18,
            color: isDir ? AppColors.warning : AppColors.textSecondary,
          ),
          title: Text(name, style: AppTypography.body.copyWith(fontSize: 13)),
          subtitle: Text(
            isDir ? 'Folder' : _formatSize(size),
            style: AppTypography.caption.copyWith(fontSize: 11),
          ),
        );
      },
    );
  }
}

enum _WorkspacePanelTab { files, skills, subagents }

class _BottomTabs extends StatelessWidget {
  final _WorkspacePanelTab selected;
  final ValueChanged<_WorkspacePanelTab> onSelected;

  const _BottomTabs({required this.selected, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AppColors.divider)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _BottomTabButton(
            icon: Icons.folder_outlined,
            activeIcon: Icons.folder,
            selected: selected == _WorkspacePanelTab.files,
            tooltip: 'Files',
            onTap: () => onSelected(_WorkspacePanelTab.files),
          ),
          const SizedBox(width: 8),
          _BottomTabButton(
            icon: Icons.bolt_outlined,
            activeIcon: Icons.bolt,
            selected: selected == _WorkspacePanelTab.skills,
            tooltip: 'Skills',
            onTap: () => onSelected(_WorkspacePanelTab.skills),
          ),
          const SizedBox(width: 8),
          _BottomTabButton(
            icon: Icons.smart_toy_outlined,
            activeIcon: Icons.smart_toy,
            selected: selected == _WorkspacePanelTab.subagents,
            tooltip: 'Subagents',
            onTap: () => onSelected(_WorkspacePanelTab.subagents),
          ),
        ],
      ),
    );
  }
}

class _BottomTabButton extends StatelessWidget {
  final IconData icon;
  final IconData activeIcon;
  final bool selected;
  final String tooltip;
  final VoidCallback onTap;

  const _BottomTabButton({
    required this.icon,
    required this.activeIcon,
    required this.selected,
    required this.tooltip,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.chip),
        onTap: onTap,
        child: Container(
          width: 40,
          height: 32,
          decoration: selected
              ? BoxDecoration(
                  color: AppColors.accentLight,
                  borderRadius: BorderRadius.circular(AppRadius.chip),
                )
              : null,
          child: Icon(
            selected ? activeIcon : icon,
            size: 19,
            color: selected ? AppColors.accent : AppColors.textSecondary,
          ),
        ),
      ),
    );
  }
}
