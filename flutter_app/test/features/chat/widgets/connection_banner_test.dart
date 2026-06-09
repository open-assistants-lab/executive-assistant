import 'package:executive_assistant/features/chat/widgets/connection_banner.dart';
import 'package:executive_assistant/services/backend_service.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ConnectionBanner', () {
    Widget buildBanner({
      bool connected = false,
      bool isDisconnected = false,
      BackendStatus? backendStatus,
    }) {
      return MaterialApp(
        theme: AppTheme.dark,
        home: Scaffold(
          body: ConnectionBanner(
            connected: connected,
            isDisconnected: isDisconnected,
            onReconnect: () {},
            backendStatus: backendStatus,
          ),
        ),
      );
    }

    testWidgets('hidden when connected', (tester) async {
      await tester.pumpWidget(buildBanner(connected: true));
      expect(find.byType(ConnectionBanner), findsOneWidget);
      expect(find.text('Starting up\u2026'), findsNothing);
      expect(find.text('Not connected'), findsNothing);
    });

    testWidgets('shows starting up when backend starting', (tester) async {
      await tester.pumpWidget(buildBanner(backendStatus: BackendStatus.starting));
      expect(find.text('Starting up\u2026'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows starting up when backend stopped', (tester) async {
      await tester.pumpWidget(buildBanner(backendStatus: BackendStatus.stopped));
      expect(find.text('Starting up\u2026'), findsOneWidget);
    });

    testWidgets('shows crash message when backend crashed', (tester) async {
      await tester.pumpWidget(buildBanner(backendStatus: BackendStatus.crashed));
      expect(find.textContaining('Something went wrong'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('shows not connected when disconnected', (tester) async {
      await tester.pumpWidget(buildBanner(isDisconnected: true));
      expect(find.textContaining('Not connected'), findsOneWidget);
    });

    testWidgets('shows connecting for unknown status', (tester) async {
      await tester.pumpWidget(buildBanner());
      expect(find.text('Connecting\u2026'), findsOneWidget);
    });

    testWidgets('tapping calls onReconnect', (tester) async {
      var tapped = false;
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.dark,
        home: Scaffold(
          body: ConnectionBanner(
            connected: false,
            isDisconnected: true,
            onReconnect: () => tapped = true,
          ),
        ),
      ));
      await tester.tap(find.textContaining('Not connected'));
      expect(tapped, isTrue);
    });
  });
}
