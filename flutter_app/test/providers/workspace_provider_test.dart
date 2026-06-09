import 'package:executive_assistant/providers/workspace_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('WorkspaceProvider', () {
    test('currentWorkspaceIdProvider starts with personal', () {
      final container = ProviderContainer();
      final id = container.read(currentWorkspaceIdProvider);
      expect(id, 'personal');
    });

    test('workspaceListProvider starts empty', () {
      final container = ProviderContainer();
      final list = container.read(workspaceListProvider);
      expect(list, isEmpty);
    });

    test('scrollPositionsProvider starts empty', () {
      final container = ProviderContainer();
      final positions = container.read(scrollPositionsProvider);
      expect(positions, isEmpty);
    });

    test('loadScrollPositionsFromPrefs loads saved positions', () async {
      SharedPreferences.setMockInitialValues({
        'scroll_personal': '150',
        'scroll_work': '300',
      });
      await loadScrollPositionsFromPrefs();
      final container = ProviderContainer();
      final positions = container.read(scrollPositionsProvider);
      expect(positions['personal'], 150.0);
      expect(positions['work'], 300.0);
    });
  });
}
