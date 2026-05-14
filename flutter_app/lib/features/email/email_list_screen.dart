import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:executive_assistant/services/api_client.dart';
import 'package:executive_assistant/providers/agent_provider.dart';
import 'package:executive_assistant/core/motion/motion.dart';

class EmailListScreen extends ConsumerStatefulWidget {
  const EmailListScreen({super.key});

  @override
  ConsumerState<EmailListScreen> createState() => _EmailListScreenState();
}

class _EmailListScreenState extends ConsumerState<EmailListScreen> {
  List<dynamic> _emails = [];
  int _unread = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadEmails();
  }

  Future<void> _loadEmails() async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final result = await client.listEmails();
      if (mounted) {
        setState(() {
          _emails = List<dynamic>.from(result['emails'] ?? []);
          _unread = result['unread'] ?? 0;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Email'),
        actions: [
          if (_unread > 0)
            Center(
              child: Container(
                margin: const EdgeInsets.only(right: 16),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$_unread unread',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadEmails,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _emails.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.mail_outline, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text('No emails yet', style: TextStyle(color: Colors.grey)),
                      SizedBox(height: 8),
                      Text(
                        'Connect Gmail in Settings to get started',
                        style: TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadEmails,
                  child: ListView.separated(
                    itemCount: _emails.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final email = _emails[index] as Map<String, dynamic>;
                      final isRead = email['is_read'] == true;
                      return EaMotion.staggeredEntry(
                        index,
                        ListTile(
                        leading: CircleAvatar(
                          backgroundColor: isRead
                              ? Colors.grey.shade200
                              : Theme.of(context).colorScheme.primaryContainer,
                          child: Icon(
                            isRead ? Icons.mail_outline : Icons.mail,
                            size: 20,
                            color: isRead ? Colors.grey : Colors.black87,
                          ),
                        ),
                        title: Text(
                          email['subject'] ?? '(no subject)',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontWeight: isRead ? FontWeight.normal : FontWeight.bold,
                          ),
                        ),
                        subtitle: Row(
                          children: [
                            Expanded(
                              child: Text(
                                email['from'] ?? '',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            Text(
                              _formatDate(email['received_at'] ?? ''),
                              style: const TextStyle(fontSize: 11, color: Colors.grey),
                            ),
                          ],
                        ),
                        dense: true,
                      ),
                      );
                    },
                  ),
                ),
    );
  }

  String _formatDate(String iso) {
    if (iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso);
      final now = DateTime.now();
      if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
        return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      }
      return '${dt.month}/${dt.day}';
    } catch (_) {
      return iso.substring(0, 10);
    }
  }
}
