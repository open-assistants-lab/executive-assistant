import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

Future<T?> showEaDialog<T>({
  required BuildContext context,
  required String title,
  required Widget content,
  List<Widget> actions = const [],
  bool barrierDismissible = true,
}) {
  return showGeneralDialog<T>(
    context: context,
    barrierDismissible: barrierDismissible,
    barrierLabel: 'dismiss',
    barrierColor: Colors.black.withValues(alpha: 0.6),
    transitionDuration: const Duration(milliseconds: 280),
    pageBuilder: (ctx, anim, _) {
      final tokens = ctx.tokens;
      return Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Material(
            color: tokens.colors.bgElevated,
            borderRadius: tokens.radius.xlAll,
            child: Container(
              decoration: BoxDecoration(
                border: Border.all(color: tokens.colors.borderDefault, width: 1),
                borderRadius: tokens.radius.xlAll,
              ),
              padding: EdgeInsets.all(tokens.spacing.lg + tokens.spacing.xs),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: tokens.typography.textTheme.titleLarge?.copyWith(
                      color: tokens.colors.textPrimary,
                    ),
                  ),
                  SizedBox(height: tokens.spacing.lg),
                  DefaultTextStyle(
                    style: tokens.typography.textTheme.bodyLarge!.copyWith(
                      color: tokens.colors.textSecondary,
                    ),
                    child: content,
                  ),
                  if (actions.isNotEmpty) ...[
                    SizedBox(height: tokens.spacing.lg + tokens.spacing.xs),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        for (var i = 0; i < actions.length; i++) ...[
                          if (i > 0) SizedBox(width: tokens.spacing.sm),
                          actions[i],
                        ],
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    },
    transitionBuilder: (ctx, anim, _, child) {
      final tokens = ctx.tokens;
      final curved = CurvedAnimation(parent: anim, curve: tokens.motion.curveSpring);
      return FadeTransition(
        opacity: anim,
        child: ScaleTransition(
          scale: Tween<double>(begin: 0.96, end: 1.0).animate(curved),
          child: child,
        ),
      );
    },
  );
}
