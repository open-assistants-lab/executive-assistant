import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _onboardingKey = 'ea_onboarding_complete';

/// Tri-state: null = loading, false = not complete, true = complete.
final onboardingCompleteProvider = StateNotifierProvider<OnboardingNotifier, bool?>((ref) {
  final notifier = OnboardingNotifier();
  notifier.load();
  return notifier;
});

class OnboardingNotifier extends StateNotifier<bool?> {
  OnboardingNotifier() : super(null);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final complete = prefs.getBool(_onboardingKey) ?? false;
    if (!complete) {
      final keys = prefs.getKeys();
      final hasAnyKey = keys.any((k) => k.startsWith('ea_key_'));
      state = hasAnyKey;
      if (hasAnyKey) {
        await prefs.setBool(_onboardingKey, true);
      }
    } else {
      state = true;
    }
  }

  Future<void> complete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_onboardingKey, true);
    state = true;
  }

  Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_onboardingKey);
    state = false;
  }
}
