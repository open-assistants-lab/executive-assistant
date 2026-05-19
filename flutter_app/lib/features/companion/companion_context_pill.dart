import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../providers/companion_provider.dart';

class CompanionContextPill extends ConsumerWidget {
  final String activeWorkspaceId;

  const CompanionContextPill({super.key, required this.activeWorkspaceId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifications = ref.watch(companionNotifierProvider);
    final relevant = notifications
        .where((n) =>
            !n.dismissed &&
            (n.workspaceId == null || n.workspaceId == activeWorkspaceId))
        .toList();

    if (relevant.isEmpty) return const SizedBox.shrink();

    final notif = relevant.first;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.accent.withAlpha(15),
          border: const Border(left: BorderSide(color: AppColors.accent, width: 2)),
          borderRadius: BorderRadius.circular(8),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Icon(Icons.lightbulb_outline, size: 14, color: AppColors.accent),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                notif.message,
                style: AppTypography.caption.copyWith(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () => ref.read(companionNotifierProvider.notifier).dismiss(notif.id),
              child: Text('Dismiss', style: AppTypography.caption.copyWith(color: AppColors.accent, fontSize: 11)),
            ),
          ],
        ),
      ),
    );
  }
}
