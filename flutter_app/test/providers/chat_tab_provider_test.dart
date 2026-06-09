import 'package:executive_assistant/providers/chat_tab_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ChatTabProvider', () {
    test('openChatTabsProvider starts with personal', () {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(openChatTabsProvider), {'personal': 'Personal'});
    });

    test('activeChatTabProvider starts with personal', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(activeChatTabProvider), 'personal');
    });

    test('workspaceSwitchSignalProvider starts at 0', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(workspaceSwitchSignalProvider), 0);
    });
  });
}
