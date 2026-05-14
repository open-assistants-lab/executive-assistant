class Todo {
  final String id;
  final String content;
  final String status;
  final String priority;
  final DateTime createdAt;

  const Todo({
    required this.id,
    required this.content,
    this.status = 'pending',
    this.priority = 'medium',
    required this.createdAt,
  });

  factory Todo.fromJson(Map<String, dynamic> json) {
    return Todo(
      id: json['id']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      status: json['status']?.toString() ?? 'pending',
      priority: json['priority']?.toString() ?? 'medium',
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}
