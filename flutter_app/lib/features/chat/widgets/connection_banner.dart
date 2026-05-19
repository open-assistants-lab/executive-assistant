import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';

class ConnectionBanner extends StatelessWidget {
  final bool connected;
  final bool isDisconnected;
  final VoidCallback onReconnect;

  const ConnectionBanner({
    super.key,
    required this.connected,
    required this.isDisconnected,
    required this.onReconnect,
  });

  @override
  Widget build(BuildContext context) {
    if (connected) return const SizedBox.shrink();

    final tokens = context.tokens;
    final color = isDisconnected ? tokens.colors.error : tokens.colors.warning;
    final text = isDisconnected
        ? 'Not connected \u2014 tap to reconnect'
        : 'Connecting...';

    return GestureDetector(
      onTap: onReconnect,
      child: Container(
        width: double.infinity,
        padding: EdgeInsets.symmetric(vertical: tokens.spacing.sm, horizontal: tokens.spacing.lg),
        color: color.withValues(alpha: 0.08),
        child: Text(
          text,
          style: tokens.typography.textTheme.bodySmall?.copyWith(color: color),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}