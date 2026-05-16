// Shared mocks and test helpers for Flutter tests.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';

import 'package:executive_assistant/models/message.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/services/ws_client.dart';

class MockWsClient extends Mock implements WsClient {}

class MockApiClient extends Mock implements ApiClient {}

class FakeMap extends Fake implements Map<String, dynamic> {}

void registerTestFallbackValues() {
  registerFallbackValue(FakeMap());
}

WsMessage msg(String type, Map<String, dynamic> data) {
  return WsMessage(type: type, data: {'type': type, ...data});
}

Stream<WsMessage> messageStream(List<Map<String, dynamic>> events) async* {
  for (final event in events) {
    final type = event['type']?.toString() ?? '';
    yield WsMessage(type: type, data: event);
  }
}

class InstrumentationSnapshot {
  final List<Map<String, dynamic>> events;

  const InstrumentationSnapshot(this.events);

  List<Map<String, dynamic>> get errors =>
      events.where((event) => event['category'] == 'error').toList();

  List<Map<String, dynamic>> get interactions =>
      events.where((event) => event['category'] == 'interaction').toList();

  List<Map<String, dynamic>> get navigation =>
      events.where((event) => event['category'] == 'navigation').toList();

  bool hasInteraction(String type) =>
      interactions.any((event) => event['type'] == type);

  bool hasError(String exceptionSnippet) => errors.any(
        (event) => (event['exception']?.toString() ?? '').contains(exceptionSnippet),
      );
}

Widget withProviders({
  required Widget child,
  WsClient? wsClient,
  ApiClient? apiClient,
}) {
  return ProviderScope(
    overrides: [
      if (wsClient != null) wsClientProvider.overrideWithValue(wsClient),
      if (apiClient != null) apiClientProvider.overrideWithValue(apiClient),
    ],
    child: child,
  );
}

const Size kMobileSize = Size(390, 844);
const Size kTabletSize = Size(820, 1180);
const Size kDesktopSize = Size(1440, 900);

StreamController<T> streamController<T>() => StreamController<T>.broadcast();
