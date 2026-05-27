class Memory {
  final String id;
  final String content;
  final String priority;
  final String domain;
  final double confidence;
  final DateTime observationTs;

  const Memory({
    required this.id,
    required this.content,
    this.priority = '',
    this.domain = '',
    this.confidence = 0.0,
    required this.observationTs,
  });

  factory Memory.fromJson(Map<String, dynamic> json) {
    return Memory(
      id: json['id']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      priority: json['priority']?.toString() ?? '',
      domain: json['domain']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      observationTs:
          DateTime.tryParse(json['observation_ts']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}
