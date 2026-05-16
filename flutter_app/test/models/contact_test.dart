import 'package:flutter_test/flutter_test.dart';
import 'package:executive_assistant/models/models.dart';

void main() {
  group('Todo.fromJson', () {
    test('parses valid todo', () {
      final json = {
        'id': '1',
        'content': 'Buy milk',
        'status': 'pending',
        'priority': 'high',
        'created_at': '2024-01-15T10:30:00Z',
      };
      final todo = Todo.fromJson(json);
      expect(todo.id, '1');
      expect(todo.content, 'Buy milk');
      expect(todo.status, 'pending');
      expect(todo.priority, 'high');
      expect(todo.createdAt.year, 2024);
    });

    test('uses defaults for missing optional fields', () {
      final json = {
        'id': '2',
        'content': 'Task',
        'created_at': '2024-01-15T10:30:00Z',
      };
      final todo = Todo.fromJson(json);
      expect(todo.status, 'pending');
      expect(todo.priority, 'medium');
    });

    test('uses DateTime.now fallback for invalid date', () {
      final json = {
        'id': '3',
        'content': 'Task',
        'created_at': 'invalid',
      };
      final todo = Todo.fromJson(json);
      expect(todo.createdAt.difference(DateTime.now()).inSeconds.abs(), lessThan(5));
    });

    test('handles null fields gracefully', () {
      final todo = Todo.fromJson({});
      expect(todo.id, '');
      expect(todo.content, '');
      expect(todo.status, 'pending');
    });
  });

  group('Contact.fromJson', () {
    test('parses full contact', () {
      final json = {
        'id': '1',
        'name': 'Alice',
        'email': 'alice@example.com',
        'phone': '+123',
        'company': 'Acme',
      };
      final c = Contact.fromJson(json);
      expect(c.name, 'Alice');
      expect(c.email, 'alice@example.com');
      expect(c.phone, '+123');
      expect(c.company, 'Acme');
    });

    test('allows null optional fields', () {
      final json = {'id': '1', 'name': 'Bob', 'email': 'bob@example.com'};
      final c = Contact.fromJson(json);
      expect(c.phone, isNull);
      expect(c.company, isNull);
    });

    test('handles null map gracefully', () {
      final c = Contact.fromJson({});
      expect(c.id, '');
      expect(c.name, '');
    });
  });

  group('Memory.fromJson', () {
    test('parses full memory', () {
      final json = {
        'id': '1',
        'content': 'User likes dark mode',
        'domain': 'preferences',
        'memory_type': 'explicit',
        'confidence': 0.95,
        'created_at': '2024-01-15T10:30:00Z',
      };
      final m = Memory.fromJson(json);
      expect(m.content, 'User likes dark mode');
      expect(m.domain, 'preferences');
      expect(m.memoryType, 'explicit');
      expect(m.confidence, 0.95);
    });

    test('defaults confidence to 0.0', () {
      final m = Memory.fromJson({'id': '1', 'content': 'test', 'created_at': '2024-01-15T10:30:00Z'});
      expect(m.confidence, 0.0);
    });

    test('defaults domain and memoryType to empty strings', () {
      final m = Memory.fromJson({'id': '1', 'content': 'test', 'created_at': '2024-01-15T10:30:00Z'});
      expect(m.domain, '');
      expect(m.memoryType, '');
    });
  });
}
