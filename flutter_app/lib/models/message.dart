class WsMessage {
  final String type;
  final Map<String, dynamic> data;

  const WsMessage({required this.type, required this.data});

  factory WsMessage.fromJson(Map<String, dynamic> json) {
    return WsMessage(type: json['type']?.toString() ?? 'unknown', data: json);
  }

  dynamic operator [](String key) => data[key];

  @override
  String toString() => 'WsMessage(type: $type, data: ${data.keys.toList()})';
}

class ChatMessage {
  final String id;
  final String role;
  final String content;
  final List<ToolCallDisplay> toolCalls;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.toolCalls = const [],
    required this.timestamp,
    this.metadata,
  });

  ChatMessage copyWith({
    String? content,
    List<ToolCallDisplay>? toolCalls,
    Map<String, dynamic>? metadata,
  }) {
    return ChatMessage(
      id: id,
      role: role,
      content: content ?? this.content,
      toolCalls: toolCalls ?? this.toolCalls,
      timestamp: timestamp,
      metadata: metadata ?? this.metadata,
    );
  }
}

class ToolCallDisplay {
  final String callId;
  final String toolName;
  final Map<String, dynamic> args;
  final String? resultPreview;
  final bool isPending;

  const ToolCallDisplay({
    required this.callId,
    required this.toolName,
    required this.args,
    this.resultPreview,
    this.isPending = false,
  });

  ToolCallDisplay copyWith({String? resultPreview, bool? isPending, Map<String, dynamic>? args}) {
    return ToolCallDisplay(
      callId: callId,
      toolName: toolName,
      args: args ?? this.args,
      resultPreview: resultPreview ?? this.resultPreview,
      isPending: isPending ?? this.isPending,
    );
  }
}
