import 'package:executive_assistant/features/workspace/learn_checklist_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('LearnChecklistNotifier', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('starts with dismissed=false and empty completed', () {
      final notifier = LearnChecklistNotifier();
      expect(notifier.state.dismissed, isFalse);
      expect(notifier.state.completed, isEmpty);
    });

    test('dismiss() sets dismissed=true', () async {
      final notifier = LearnChecklistNotifier();
      await Future(() {}); // let _load settle
      notifier.dismiss();
      expect(notifier.state.dismissed, isTrue);
    });

    test('complete() adds id to completed set', () async {
      final notifier = LearnChecklistNotifier();
      await Future(() {});
      notifier.complete('chat');
      expect(notifier.state.completed, contains('chat'));
    });

    test('complete() is idempotent', () async {
      final notifier = LearnChecklistNotifier();
      await Future(() {});
      notifier.complete('chat');
      notifier.complete('chat');
      expect(notifier.state.completed.length, 1);
    });

    test('checklistItems has 5 items', () {
      expect(checklistItems.length, 5);
      for (final item in checklistItems) {
        expect(item.id, isNotEmpty);
        expect(item.title, isNotEmpty);
        expect(item.description, isNotEmpty);
      }
    });
  });
}
