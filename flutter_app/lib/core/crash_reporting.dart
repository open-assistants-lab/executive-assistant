import 'package:sentry_flutter/sentry_flutter.dart';

const _defaultDsn = String.fromEnvironment('sentry_dsn');
const _defaultEnvironment = String.fromEnvironment('sentry_env', defaultValue: 'production');

Future<void> initCrashReporting({
  String? dsn,
  String environment = _defaultEnvironment,
}) async {
  final resolvedDsn = dsn ?? _defaultDsn;
  if (resolvedDsn.isEmpty) {
    // No DSN configured — crash reporting disabled
    return;
  }

  await SentryFlutter.init(
    (options) {
      options.dsn = resolvedDsn;
      options.environment = environment;
      options.tracesSampleRate = 0.1;
      options.reportPackages = false;
    },
    appRunner: () {},
  );
}

Future<void> reportError(
  dynamic error,
  StackTrace? stack, {
  Map<String, dynamic>? extras,
}) async {
  if (Sentry.isEnabled) {
    Sentry.captureException(
      error,
      stackTrace: stack,
      withScope: (scope) {
        if (extras != null) {
          scope.setContexts('extra', extras);
        }
      },
    );
  }
}
