import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../theme/app_theme.dart';
import '../../providers/agent_provider.dart';
import '../../providers/workspace_provider.dart';

class WorkspacePanel extends ConsumerStatefulWidget {
  const WorkspacePanel({super.key});

  @override
  ConsumerState<WorkspacePanel> createState() => _WorkspacePanelState();
}

class _WorkspacePanelState extends ConsumerState<WorkspacePanel> {
  List<Map<String, dynamic>> _files = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadFiles();
  }

  Future<void> _loadFiles() async {
    if (!mounted) return;
    setState(() { _loading = _files.isEmpty; _error = null; });
    try {
      final host = ref.read(hostProvider);
      final userId = ref.read(userIdProvider);
      final wsId = ref.read(currentWorkspaceIdProvider);
      final url = Uri.parse('http://$host/workspace/json?user_id=$userId&workspace_id=$wsId');
      final response = await http.get(url);
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        setState(() {
          _files = List<Map<String, dynamic>>.from(data['files'] ?? []);
          _loading = false;
        });
      } else {
        setState(() { _error = 'Failed to load (${response.statusCode})'; _loading = false; });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = 'Cannot connect: $e'; _loading = false; });
    }
  }

  String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(currentWorkspaceIdProvider, (prev, next) {
      if (prev != next) _loadFiles();
    });

    ref.listen<ChatState>(agentProvider, (prev, next) {
      if (prev?.status == ChatStatus.streaming && next.status == ChatStatus.idle) {
        _loadFiles();
      }
    });

    return Container(
      color: AppColors.background,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 52,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.divider))),
            child: Row(children: [
              Icon(Icons.folder, size: 18, color: AppColors.accent),
              const SizedBox(width: 8),
              Text('Files', style: AppTypography.sectionTitle.copyWith(fontSize: 15)),
              const Spacer(),
              if (_loading && _files.isNotEmpty)
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
              const SizedBox(width: 4),
              Text('${_files.length}', style: AppTypography.caption.copyWith(color: AppColors.textDim)),
              const SizedBox(width: 4),
              InkWell(
                onTap: _loadFiles,
                child: Icon(Icons.refresh, size: 16, color: AppColors.textDim),
              ),
            ]),
          ),
          Expanded(
            child: _loading && _files.isEmpty
                ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
                : _error != null && _files.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(mainAxisSize: MainAxisSize.min, children: [
                            Text(_error!, style: AppTypography.caption.copyWith(color: AppColors.danger)),
                            const SizedBox(height: 8),
                            OutlinedButton(onPressed: _loadFiles, child: const Text('Retry')),
                          ]),
                        ),
                      )
                    : _files.isEmpty
                        ? Center(
                            child: Column(mainAxisSize: MainAxisSize.min, children: [
                              Icon(Icons.folder_open, size: 40, color: AppColors.textDim),
                              const SizedBox(height: 8),
                              Text('No files', style: AppTypography.caption.copyWith(color: AppColors.textDim)),
                            ]),
                          )
                        : ListView.builder(
                            padding: EdgeInsets.zero,
                            itemCount: _files.length,
                            itemBuilder: (_, i) {
                              final f = _files[i];
                              final name = f['name']?.toString() ?? '';
                              final isDir = f['is_dir'] == true;
                              final size = f['size'] as int? ?? 0;
                              return ListTile(
                                dense: true,
                                leading: Icon(isDir ? Icons.folder : Icons.description, size: 18, color: isDir ? AppColors.warning : AppColors.textSecondary),
                                title: Text(name, style: AppTypography.body.copyWith(fontSize: 13)),
                                subtitle: Text(isDir ? 'Folder' : _formatSize(size), style: AppTypography.caption.copyWith(fontSize: 11)),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
