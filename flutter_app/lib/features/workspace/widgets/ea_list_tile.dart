import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class EaListTile extends StatelessWidget {
  final Widget leading;
  final String title;
  final String? subtitle;
  final Widget? subtitleTrailing;
  final List<Widget>? chips;
  final List<Widget>? trailingBadges;
  final List<Widget>? trailingActions;
  final VoidCallback? onTap;

  const EaListTile({
    super.key,
    this.leading = const SizedBox.shrink(),
    required this.title,
    this.subtitle,
    this.subtitleTrailing,
    this.chips,
    this.trailingBadges,
    this.trailingActions,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: t.colors.borderSubtle)),
        ),
        padding: EdgeInsets.symmetric(
          horizontal: t.spacing.md,
          vertical: t.spacing.sm,
        ),
        child: Row(
          children: [
            leading,
            SizedBox(width: t.spacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          title,
                          style: t.typography.textTheme.bodyMedium?.copyWith(
                            color: t.colors.textPrimary,
                            fontSize: 13,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (subtitleTrailing != null) SizedBox(width: t.spacing.xs),
                      ?subtitleTrailing,
                    ],
                  ),
                  if (subtitle != null)
                    Padding(
                      padding: EdgeInsets.only(top: 2), // no token for 2px
                      child: Text(
                        subtitle!,
                        style: t.typography.textTheme.bodySmall?.copyWith(
                          color: t.colors.textSecondary,
                          fontSize: 11,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  if (chips != null && chips!.isNotEmpty)
                    Padding(
                      padding: EdgeInsets.only(top: t.spacing.xs),
                      child: Wrap(
                        spacing: 4,
                        runSpacing: 2,
                        children: chips!,
                      ),
                    ),
                ],
              ),
            ),
            ...?trailingBadges,
            if (trailingActions != null) SizedBox(width: t.spacing.xs),
            ...?trailingActions,
          ],
        ),
      ),
    );
  }
}
