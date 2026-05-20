import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../theme/app_theme.dart';
import '../../../providers/agent_provider.dart';

class ErrorBar extends ConsumerWidget {
  final String error;

  const ErrorBar({super.key, required this.error});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = context.tokens;
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: tokens.spacing.lg,
        vertical: tokens.spacing.sm,
      ),
      color: tokens.colors.error.withValues(alpha: 0.08),
      child: Row(
        children: [
          Icon(Symbols.error, size: 18, color: tokens.colors.error),
          SizedBox(width: tokens.spacing.sm),
          Expanded(
            child: Text(
              error,
              style: tokens.typography.textTheme.bodySmall?.copyWith(
                color: tokens.colors.error,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          IconButton(
            icon: Icon(Symbols.close, size: 16, color: tokens.colors.error),
            constraints: BoxConstraints(minWidth: 28, minHeight: 28),
            padding: EdgeInsets.zero,
            onPressed: () => ref.read(agentProvider.notifier).clearError(),
          ),
        ],
      ),
    );
  }
}