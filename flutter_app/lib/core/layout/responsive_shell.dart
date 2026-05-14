import 'package:flutter/material.dart';
import '../constants/breakpoints.dart';
import 'mobile_layout.dart';
import 'desktop_layout.dart';

class ResponsiveShell extends StatelessWidget {
  final Widget child;

  const ResponsiveShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= Breakpoints.desktop) {
          return DesktopLayout(child: child);
        }
        return MobileLayout(child: child);
      },
    );
  }
}