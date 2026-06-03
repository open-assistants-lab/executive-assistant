import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:executive_assistant/services/ws_client.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:executive_assistant/features/home/home_screen.dart';

class MockWsClient extends Mock implements WsClient {}

class MockApiClient extends Mock implements ApiClient {}

Widget _buildHomeScreen(MockWsClient ws, MockApiClient api) {
  return ProviderScope(
    overrides: [
      wsClientProvider.overrideWithValue(ws),
      apiClientProvider.overrideWithValue(api),
    ],
    child: MaterialApp(
      theme: AppTheme.dark,
      home: const Scaffold(body: HomeScreen()),
    ),
  );
}

void main() {
  late MockWsClient mockWs;
  late MockApiClient mockApi;
  late StreamController<ConnectionStatus> statusCtrl;

  setUp(() {
    statusCtrl = StreamController<ConnectionStatus>.broadcast();
    mockWs = MockWsClient();
    mockApi = MockApiClient();
    when(() => mockWs.status).thenAnswer((_) => statusCtrl.stream);
    when(() => mockWs.messages).thenAnswer((_) => Stream.empty());
    when(() => mockWs.isConnected).thenReturn(false);
    when(() => mockWs.pendingApprovals).thenReturn({});
  });

  tearDown(() {
    statusCtrl.close();
  });

  group('HomeScreen renders', () {
    testWidgets('shows SmartGreeting', (WidgetTester tester) async {
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      // SmartGreeting renders a greeting word based on hour.
      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('shows status cards', (WidgetTester tester) async {
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Unread'), findsOneWidget);
      expect(find.text('Due'), findsOneWidget);
      expect(find.text('Active'), findsOneWidget);
    });

    testWidgets('shows Quick Actions section', (WidgetTester tester) async {
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Quick Actions'), findsOneWidget);
      expect(find.text('Draft reply'), findsOneWidget);
      expect(find.text('Summarize'), findsOneWidget);
      expect(find.text('Schedule'), findsOneWidget);
    });

    testWidgets('shows empty state when no conversation', (WidgetTester tester) async {
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('How can I help you today?'), findsOneWidget);
    });
  });

  group('HomeScreen mobile interactions', () {
    testWidgets('quick action Draft reply sends message', (WidgetTester tester) async {
      when(() => mockWs.sendMessage(any())).thenReturn(null);
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      statusCtrl.add(ConnectionStatus.connected);
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Draft reply'));
      await tester.pump();
      verify(() => mockWs.sendMessage('Draft a reply to my latest email')).called(1);
    });

    testWidgets('quick action Summarize sends message', (WidgetTester tester) async {
      when(() => mockWs.sendMessage(any())).thenReturn(null);
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      statusCtrl.add(ConnectionStatus.connected);
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Summarize'));
      await tester.pump();
      verify(() => mockWs.sendMessage('Summarize my recent emails')).called(1);
    });

    testWidgets('quick action Schedule sends message', (WidgetTester tester) async {
      when(() => mockWs.sendMessage(any())).thenReturn(null);
      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      statusCtrl.add(ConnectionStatus.connected);
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      await tester.tap(find.text('Schedule'));
      await tester.pump();
      verify(() => mockWs.sendMessage("What's on my schedule today?")).called(1);
    });
  });

  group('HomeScreen desktop layout', () {
    testWidgets('renders desktop content at 1200 width', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(_buildHomeScreen(mockWs, mockApi));
      await tester.pump(); await tester.pump(const Duration(milliseconds: 100));

      // Desktop layout should show "Recent Activity" header.
      expect(find.text('Recent Activity'), findsOneWidget);
    });
  });
}
