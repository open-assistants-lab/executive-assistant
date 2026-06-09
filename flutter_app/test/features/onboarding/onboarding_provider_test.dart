import 'package:executive_assistant/features/onboarding/onboarding_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('OnboardingNotifier', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('starts with null (loading)', () {
      final notifier = OnboardingNotifier();
      expect(notifier.state, isNull);
    });

    test('load() sets false when no keys exist', () async {
      final notifier = OnboardingNotifier();
      await notifier.load();
      expect(notifier.state, isFalse);
    });

    test('load() sets true when ea_key_ pref exists', () async {
      SharedPreferences.setMockInitialValues({'ea_key_openai': 'sk-xxx'});
      final notifier = OnboardingNotifier();
      await notifier.load();
      expect(notifier.state, isTrue);
    });

    test('load() sets true when onboarding already complete', () async {
      SharedPreferences.setMockInitialValues({'ea_onboarding_complete': true});
      final notifier = OnboardingNotifier();
      await notifier.load();
      expect(notifier.state, isTrue);
    });

    test('complete() sets state to true and persists', () async {
      final notifier = OnboardingNotifier();
      await notifier.complete();
      expect(notifier.state, isTrue);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('ea_onboarding_complete'), isTrue);
    });

    test('reset() sets state to false', () async {
      SharedPreferences.setMockInitialValues({'ea_onboarding_complete': true});
      final notifier = OnboardingNotifier();
      await notifier.load();
      expect(notifier.state, isTrue);
      await notifier.reset();
      expect(notifier.state, isFalse);
    });
  });
}
