import 'package:executive_assistant/features/workspace/learn_checklist_widget.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('htmlForChecklistItem', () {
    test('returns chat HTML for chat id', () {
      final html = htmlForChecklistItem('chat');
      expect(html, contains('Start a conversation'));
      expect(html, contains('Getting Started'));
      expect(html, contains('explain quantum computing'));
    });

    test('returns email HTML for email id', () {
      final html = htmlForChecklistItem('email');
      expect(html, contains('Connect Google Workspace'));
      expect(html, contains("what's on my calendar today?"));
      expect(html, contains("what's the population of Japan?"));
    });

    test('returns todos HTML for todos id', () {
      final html = htmlForChecklistItem('todos');
      expect(html, contains('Create and manage tasks'));
      expect(html, contains('Tasks'));
      expect(html, contains('add buy groceries'));
    });

    test('returns web HTML for web id', () {
      final html = htmlForChecklistItem('web');
      expect(html, contains('Search the web'));
      expect(html, contains('Web Search'));
      expect(html, contains('latest AI news'));
    });

    test('returns files HTML for files id', () {
      final html = htmlForChecklistItem('files');
      expect(html, contains('Work with files'));
      expect(html, contains('Files'));
      expect(html, contains('notes.txt'));
    });

    test('returns chat HTML for unknown id', () {
      final html = htmlForChecklistItem('unknown');
      expect(html, contains('Start a conversation'));
    });

    test('all HTML includes canvas style', () {
      for (final id in ['chat', 'email', 'todos', 'web', 'files']) {
        final html = htmlForChecklistItem(id);
        expect(html, contains('max-width: 600px'));
        expect(html, contains('class="card"'));
        expect(html, contains('--primary: #3b82f6'));
      }
    });

    test('all HTML has a tag and h2', () {
      for (final id in ['chat', 'email', 'todos', 'web', 'files']) {
        final html = htmlForChecklistItem(id);
        expect(html, contains('class="tag"'));
        expect(html, contains('<h2>'));
      }
    });
  });
}
