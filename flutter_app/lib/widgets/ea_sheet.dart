import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

Future<T?> showEaSheet<T>({
  required BuildContext context,
  required Widget child,
  bool dismissible = true,
}) {
  final t = context.tokens;
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    isDismissible: dismissible,
    barrierColor: Colors.black.withValues(alpha: 0.6),
    backgroundColor: Colors.transparent,
    builder: (_) => Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.85,
      ),
      padding: EdgeInsets.only(
        top: t.spacing.xs,
        left: t.spacing.xl,
        right: t.spacing.xl,
        bottom: t.spacing.xl + MediaQuery.of(context).padding.bottom,
      ),
      decoration: BoxDecoration(
        color: t.colors.bgSurface,
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(t.radius.lg)),
        border: Border.all(color: t.colors.borderDefault),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Center(
            child: Container(
              width: 32,
              height: 4,
              margin: EdgeInsets.only(bottom: t.spacing.md),
              decoration: BoxDecoration(
                color: t.colors.borderDefault,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Flexible(child: SingleChildScrollView(child: child)),
        ],
      ),
    ),
  );
}
