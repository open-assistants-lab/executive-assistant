import 'package:executive_assistant/providers/companion_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  group('CompanionProvider', () {
    test('companionPausedProvider starts false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(companionPausedProvider), isFalse);
    });

    test('companionActiveToastProvider starts null', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(companionActiveToastProvider), isNull);
    });

    test('companionNotifierProvider starts empty', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(companionNotifierProvider), isEmpty);
    });
  });
}
