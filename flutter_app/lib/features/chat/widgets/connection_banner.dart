import 'package:flutter/material.dart';
import '../../../services/backend_service.dart';
import '../../../theme/app_theme.dart';

class ConnectionBanner extends StatelessWidget {
  final bool connected;
  final bool isDisconnected;
  final VoidCallback onReconnect;
  final BackendStatus? backendStatus;

  const ConnectionBanner({
    super.key,
    required this.connected,
    required this.isDisconnected,
    required this.onReconnect,
    this.backendStatus,
  });

  @override
  Widget build(BuildContext context) {
    if (connected) return const SizedBox.shrink();

    final tokens = context.tokens;

    String message;
    Color color;
    bool showSpinner;

    if (backendStatus == BackendStatus.starting ||
        backendStatus == BackendStatus.stopped) {
      message = 'Starting up\u2026';
      color = tokens.colors.warning;
      showSpinner = true;
    } else if (backendStatus == BackendStatus.crashed) {
      message = 'Something went wrong \u2014 tap to restart';
      color = tokens.colors.error;
      showSpinner = false;
    } else if (isDisconnected) {
      message = 'Not connected \u2014 tap to reconnect';
      color = tokens.colors.error;
      showSpinner = false;
    } else {
      message = 'Connecting\u2026';
      color = tokens.colors.warning;
      showSpinner = true;
    }

    return GestureDetector(
      onTap: onReconnect,
      child: Container(
        width: double.infinity,
        padding: EdgeInsets.symmetric(
          vertical: tokens.spacing.sm,
          horizontal: tokens.spacing.lg,
        ),
        color: color.withValues(alpha: 0.08),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (showSpinner)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: color,
                  ),
                ),
              ),
            Text(
              message,
              style: tokens.typography.textTheme.bodySmall?.copyWith(
                color: color,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
