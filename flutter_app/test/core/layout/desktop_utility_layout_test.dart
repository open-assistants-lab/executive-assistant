import 'package:executive_assistant/core/layout/desktop_utility_layout.dart';
import 'package:executive_assistant/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders sidebar and child in two columns', (tester) async {
    final sidebarKey = GlobalKey();
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.light,
          home: DesktopUtilityLayout(
            sidebar: SizedBox(key: sidebarKey, width: 240, child: const Text('SB')),
            child: const Text('PANEL'),
          ),
        ),
      ),
    );
    expect(find.text('SB'), findsOneWidget);
    expect(find.text('PANEL'), findsOneWidget);
    // Sidebar is fixed-width, panel takes the rest
    final sidebarBox = tester.getRect(find.byKey(sidebarKey));
    final panelFinder = find.text('PANEL');
    final panelBox = tester.getRect(panelFinder);
    expect(sidebarBox.width, 240);
    expect(panelBox.left, greaterThan(sidebarBox.right));
  });
}
