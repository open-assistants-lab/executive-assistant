import 'package:executive_assistant/providers/draft_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DraftNotifier', () {
    late ProviderContainer container;
    late DraftNotifier notifier;

    setUp(() {
      container = ProviderContainer();
      notifier = container.read(draftProvider.notifier);
    });

    tearDown(() => container.dispose());

    test('save and load round-trip', () {
      notifier.save('ws1', 'hello world');
      expect(notifier.load('ws1'), 'hello world');
    });

    test('load returns null for unknown workspace', () {
      expect(notifier.load('nope'), isNull);
    });

    test('clear removes the draft', () {
      notifier.save('ws1', 'draft');
      notifier.clear('ws1');
      expect(notifier.load('ws1'), isNull);
    });

    test('drafts are isolated per workspace', () {
      notifier.save('ws1', 'a');
      notifier.save('ws2', 'b');
      expect(notifier.load('ws1'), 'a');
      expect(notifier.load('ws2'), 'b');
    });
  });
}
