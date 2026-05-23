import 'package:flutter/material.dart';
import '../../theme/app_theme.dart';
import 'widgets/services_tab.dart';

class ConnectorsModal extends StatelessWidget {
  const ConnectorsModal({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Connection'),
        leading: IconButton(
          icon: const Icon(Symbols.close, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: const ServicesTab(),
    );
  }
}
