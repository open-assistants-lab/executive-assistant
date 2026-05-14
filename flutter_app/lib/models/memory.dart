class Memory {
  final String id;
  final String content;
  final String domain;
  final String memoryType;
  final double confidence;
  final DateTime createdAt;

  const Memory({
    required this.id,
    required this.content,
    this.domain = '',
    this.memoryType = '',
    this.confidence = 0.0,
    required this.createdAt,
  });

  factory Memory.fromJson(Map<String, dynamic> json) {
    return Memory(
      id: json['id']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      domain: json['domain']?.toString() ?? '',
      memoryType: json['memory_type']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}
