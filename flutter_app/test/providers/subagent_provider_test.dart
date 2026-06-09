import 'package:executive_assistant/providers/subagent_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  group('SubagentProvider', () {
    test('subagentProvider starts with default state', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final state = container.read(subagentProvider);
      expect(state.agents, isEmpty);
      expect(state.activeJobs, isEmpty);
      expect(state.loading, isFalse);
    });
  });
}
