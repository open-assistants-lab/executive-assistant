import 'package:executive_assistant/providers/workspace_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('WorkspaceProvider', () {
    test('currentWorkspaceIdProvider starts with personal', () {
      final container = ProviderContainer();
      final id = container.read(currentWorkspaceIdProvider);
      expect(id, 'personal');
    });

    test('workspaceListProvider starts empty', () async {
      final container = ProviderContainer();
      final list = await container.read(workspaceListProvider.future);
      expect(list, isEmpty);
    });

  });
}
