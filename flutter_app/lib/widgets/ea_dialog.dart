import 'dart:ui';

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

Future<T?> showEaDialog<T>({
  required BuildContext context,
  required String title,
  required Widget body,
  List<Widget> actions = const [],
  bool dismissible = true,
}) {
  final t = context.tokens;
  return showDialog<T>(
    context: context,
    barrierDismissible: dismissible,
    barrierColor: Colors.black.withValues(alpha: 0.6),
    builder: (_) => Stack(
      children: [
        BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
          child: Container(color: Colors.transparent),
        ),
        Center(
          child: Container(
            constraints: const BoxConstraints(minWidth: 320, maxWidth: 480),
            padding: EdgeInsets.all(t.spacing.xl),
            decoration: BoxDecoration(
              color: t.colors.bgSurface,
              borderRadius: t.radius.lgAll,
              border: Border.all(color: t.colors.borderDefault),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: t.typography.textTheme.headlineMedium
                            ?.copyWith(color: t.colors.textPrimary),
                      ),
                    ),
                    if (dismissible)
                      GestureDetector(
                        onTap: () => Navigator.of(context).pop(),
                        child: Icon(
                          Symbols.close,
                          size: 18,
                          color: t.colors.textTertiary,
                        ),
                      ),
                  ],
                ),
                SizedBox(height: t.spacing.md),
                Flexible(child: SingleChildScrollView(child: body)),
                if (actions.isNotEmpty) ...[
                  SizedBox(height: t.spacing.lg),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: actions,
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    ),
  );
}
