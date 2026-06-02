import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class JumpToBottomButton extends StatelessWidget {
  final int newCount;
  final VoidCallback onPressed;
  const JumpToBottomButton({
    super.key,
    required this.newCount,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Material(
      color: tokens.colors.bgSurface,
      shape: const CircleBorder(),
      elevation: 2,
      child: InkWell(
        onTap: onPressed,
        customBorder: const CircleBorder(),
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.sm + 2),
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              Icon(
                Symbols.arrow_downward,
                size: 18,
                color: tokens.colors.textPrimary,
              ),
              if (newCount > 0)
                Positioned(
                  right: -8,
                  top: -8,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: tokens.colors.accent,
                      borderRadius: tokens.radius.fullAll,
                    ),
                    child: Text(
                      '$newCount new',
                      style: tokens.typography.textTheme.labelSmall?.copyWith(
                        color: tokens.colors.textInverse,
                        fontWeight: FontWeight.w600,
                        fontSize: 10,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
