import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/app_radius.dart';
import '../../theme/app_spacing.dart';
import '../../providers/companion_provider.dart';
import '../../providers/chat_tab_provider.dart';
import '../../widgets/app_input.dart';

class CompanionFeed extends ConsumerStatefulWidget {
  const CompanionFeed({super.key});

  @override
  ConsumerState<CompanionFeed> createState() => _CompanionFeedState();
}

class _CompanionFeedState extends ConsumerState<CompanionFeed> {
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) ref.read(companionNotifierProvider.notifier).fetch();
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final notifications = ref.watch(companionNotifierProvider);
    final paused = ref.watch(companionPausedProvider);

    if (notifications.isEmpty) {
      return _buildEmptyState(paused);
    }

    final grouped = _groupByDate(notifications);

    return Container(
      color: AppColors.background,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: grouped.entries.length,
              itemBuilder: (context, sectionIndex) {
                final entry = grouped.entries.elementAt(sectionIndex);
                return _buildSection(entry.key, entry.value);
              },
            ),
          ),
          const Divider(height: 1),
          _buildFooter(paused),
        ],
      ),
    );
  }

  Widget _buildEmptyState(bool paused) {
    return Container(
      color: AppColors.background,
      child: Column(
        children: [
          _buildHeader(),
          const Divider(height: 1),
          Expanded(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.screenEdge),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (paused) ...[
                      const Icon(Icons.pause_circle, size: 60, color: AppColors.textDim),
                      const SizedBox(height: 16),
                      Text(
                        'Companion is paused',
                        style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'No check-ins until you resume.',
                        style: AppTypography.caption.copyWith(color: AppColors.textDim),
                      ),
                      const SizedBox(height: 24),
                      FilledButton.icon(
                        onPressed: () {
                          ref.read(companionPausedProvider.notifier).state = false;
                          ref.read(companionNotifierProvider.notifier).resume();
                        },
                        icon: const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Resume companion'),
                      ),
                    ] else ...[
                      const Icon(Icons.bubble_chart_outlined, size: 60, color: AppColors.accent),
                      const SizedBox(height: 16),
                      Text(
                        "I'm watching across your workspaces.",
                        style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "I'll let you know if anything needs your attention.",
                        style: AppTypography.caption.copyWith(color: AppColors.textDim),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Until then \u2014 carry on.',
                        style: AppTypography.caption.copyWith(color: AppColors.textDim),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
          const Divider(height: 1),
          _buildFooter(paused),
        ],
      ),
    );
  }

  Widget _buildSection(String label, List<dynamic> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          color: AppColors.surface,
          child: Text(
            label,
            style: AppTypography.caption.copyWith(
              color: AppColors.textDim,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        ...items.map((n) => CompanionEntry(
              notification: n as dynamic,
              onDismiss: () => ref.read(companionNotifierProvider.notifier).dismiss(n.id),
              onSwitchWorkspace: n.workspaceId != null
                  ? () => ref.read(chatTabNotifierProvider.notifier).openWorkspace(
                        n.workspaceId!,
                        n.workspaceId ?? 'Workspace',
                      )
                  : null,
            )),
      ],
    );
  }

  Widget _buildHeader() {
    final status = ref.watch(companionStatusProvider);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          const Icon(Icons.wb_sunny_outlined, size: 20, color: AppColors.accent),
          const SizedBox(width: 8),
          Text('Companion', style: AppTypography.body.copyWith(fontWeight: FontWeight.w600)),
          const Spacer(),
          status.when(
            data: (s) => Text(
              s.lastCheck != null ? _formatTimeAgo(s.lastCheck!) : '',
              style: AppTypography.caption.copyWith(color: AppColors.textDim),
            ),
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(bool paused) {
    final notifier = ref.read(companionNotifierProvider.notifier);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Icon(
            paused ? Icons.circle_outlined : Icons.circle,
            size: 8,
            color: paused ? AppColors.textDim : AppColors.success,
          ),
          const SizedBox(width: 6),
          Text(
            paused ? 'Companion paused' : 'Companion running',
            style: AppTypography.caption.copyWith(color: AppColors.textDim),
          ),
          const Spacer(),
          TextButton(
            onPressed: () {
              if (paused) {
                notifier.resume();
                ref.read(companionPausedProvider.notifier).state = false;
              } else {
                notifier.pause();
                ref.read(companionPausedProvider.notifier).state = true;
              }
            },
            child: Text(
              paused ? 'Resume' : 'Pause companion',
              style: AppTypography.caption.copyWith(color: AppColors.accent),
            ),
          ),
        ],
      ),
    );
  }

  Map<String, List<dynamic>> _groupByDate(List<dynamic> items) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    final groups = <String, List<dynamic>>{};
    for (final item in items) {
      DateTime? dt;
      try {
        dt = DateTime.parse(item.createdAt);
      } catch (_) {
        continue;
      }
      final itemDate = DateTime(dt.year, dt.month, dt.day);
      String label;
      if (itemDate == today) {
        label = 'Today';
      } else if (itemDate == yesterday) {
        label = 'Yesterday';
      } else {
        label = _formatDate(dt);
      }
      groups.putIfAbsent(label, () => []).add(item);
    }
    return groups;
  }

  String _formatDate(DateTime dt) {
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[dt.month - 1]} ${dt.day}';
  }

  String _formatTimeAgo(String iso) {
    try {
      final dt = DateTime.parse(iso);
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 1) return 'just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      return '${diff.inHours}h ago';
    } catch (_) {
      return '';
    }
  }
}

class CompanionEntry extends StatelessWidget {
  final dynamic notification;
  final VoidCallback? onDismiss;
  final VoidCallback? onSwitchWorkspace;

  const CompanionEntry({
    super.key,
    required this.notification,
    this.onDismiss,
    this.onSwitchWorkspace,
  });

  IconData _categoryIcon(String category) {
    switch (category) {
      case 'email':
        return Icons.mail_outline;
      case 'deadline':
        return Icons.calendar_today;
      case 'checkin':
        return Icons.chat_bubble_outline;
      case 'urgent':
        return Icons.warning_amber_rounded;
      default:
        return Icons.notifications_outlined;
    }
  }

  Color _categoryColor(String category) {
    switch (category) {
      case 'email':
        return AppColors.accent;
      case 'deadline':
        return AppColors.warning;
      case 'urgent':
        return AppColors.danger;
      case 'checkin':
        return AppColors.success;
      default:
        return AppColors.textDim;
    }
  }

  @override
  Widget build(BuildContext context) {
    final cat = notification.category?.toString() ?? 'general';
    final msg = notification.message?.toString() ?? '';
    final wsId = notification.workspaceId?.toString();
    final isDimmed = notification.dismissed == true;
    final time = _extractTime(notification.createdAt?.toString());

    return Container(
      decoration: BoxDecoration(
        border: isDimmed
            ? null
            : Border(left: BorderSide(color: _categoryColor(cat), width: 2)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Opacity(
            opacity: isDimmed ? 0.4 : 1.0,
            child: Icon(_categoryIcon(cat), size: 16, color: _categoryColor(cat)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      time,
                      style: AppTypography.caption.copyWith(
                        color: isDimmed ? AppColors.textDim : AppColors.textSecondary,
                        fontSize: 10,
                      ),
                    ),
                    if (wsId != null && wsId.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      GestureDetector(
                        onTap: isDimmed ? null : onSwitchWorkspace,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppColors.accent.withAlpha(20),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            wsId.length > 15 ? '${wsId.substring(0, 15)}\u2026' : wsId,
                            style: AppTypography.caption.copyWith(
                              fontSize: 9,
                              color: AppColors.accent,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  msg,
                  style: AppTypography.body.copyWith(
                    fontSize: 13,
                    color: isDimmed ? AppColors.textDim : AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
          if (onDismiss != null && !isDimmed)
            InkWell(
              onTap: onDismiss,
              child: Padding(
                padding: const EdgeInsets.only(left: 8),
                child: Icon(Icons.close, size: 14, color: AppColors.textDim),
              ),
            ),
        ],
      ),
    );
  }

  String _extractTime(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso);
      final hour = dt.hour > 12 ? dt.hour - 12 : (dt.hour == 0 ? 12 : dt.hour);
      final ampm = dt.hour >= 12 ? 'PM' : 'AM';
      final min = dt.minute.toString().padLeft(2, '0');
      return '$hour:$min $ampm';
    } catch (_) {
      return '';
    }
  }
}
