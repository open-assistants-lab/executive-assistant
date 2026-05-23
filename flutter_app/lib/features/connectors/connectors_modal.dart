import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/app_theme.dart';
import 'widgets/llm_providers_tab.dart';
import 'widgets/services_tab.dart';

class ConnectorsModal extends ConsumerStatefulWidget {
  final int initialTab;
  const ConnectorsModal({super.key, this.initialTab = 0});

  @override
  ConsumerState<ConnectorsModal> createState() => _ConnectorsModalState();
}

class _ConnectorsModalState extends ConsumerState<ConnectorsModal>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: 2,
      vsync: this,
      initialIndex: widget.initialTab,
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conectors'),
        leading: IconButton(
          icon: const Icon(Symbols.close, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(
              icon: Icon(Symbols.psychiatry, size: 18),
              text: 'LLM Providers',
            ),
            Tab(
              icon: Icon(Symbols.lan, size: 18),
              text: 'Services',
            ),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          LlmProvidersTab(),
          ServicesTab(),
        ],
      ),
    );
  }
}
