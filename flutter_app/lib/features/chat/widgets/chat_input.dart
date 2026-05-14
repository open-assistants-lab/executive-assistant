import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../widgets/app_input.dart';
import '../../../providers/agent_provider.dart';
import 'model_switcher.dart';

class ChatInput extends ConsumerWidget {
  const ChatInput({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(agentProvider);
    final isSending = state.status == ChatStatus.streaming ||
        state.status == ChatStatus.awaitingApproval;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AppChatField(
          hint: state.connected ? 'Ask anything...' : 'Connecting...',
          enabled: state.connected,
          sending: isSending,
          onSend: (text) => ref.read(agentProvider.notifier).sendMessage(text),
          onCancel: isSending
              ? () => ref.read(agentProvider.notifier).cancelExecution()
              : null,
          onReconnect: !state.connected
              ? () => ref.read(agentProvider.notifier).connect()
              : null,
        ),
        const ModelSwitcher(),
      ],
    );
  }
}
