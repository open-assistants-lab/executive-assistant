import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'services/instrumented_app.dart';
import 'services/test_instrumentation.dart';
import 'theme/app_theme.dart';

void main() {
  // Capture uncaught async zone errors.
  runZonedGuarded(() {
    runApp(
      InstrumentedApp(
        child: const ProviderScope(child: ExecutiveAssistantApp()),
      ),
    );
  }, (error, stack) {
    TestInstrumentation().onZoneError(error, stack);
  });
}

class ExecutiveAssistantApp extends ConsumerWidget {
  const ExecutiveAssistantApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'Executive Assistant',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: router,
    );
  }
}
