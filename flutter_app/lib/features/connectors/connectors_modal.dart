import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/app_theme.dart';
import 'widgets/services_tab.dart';

class ConnectorsModal extends StatelessWidget {
  const ConnectorsModal({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      color: tokens.colors.bgCanvas,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.all(tokens.spacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Connection',
                        style: tokens.typography.textTheme.titleLarge
                            ?.copyWith(color: tokens.colors.textPrimary)),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Symbols.close, size: 20),
                      onPressed: () {
                        if (Navigator.of(context).canPop()) {
                          Navigator.of(context).pop();
                        } else {
                          GoRouter.of(context).go('/workspace');
                        }
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: tokens.spacing.md),
              child: const ServicesTab(),
            ),
          ),
        ],
      ),
    );
  }
}
