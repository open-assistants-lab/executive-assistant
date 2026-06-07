const _canvasStyle = '''
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  :root {
    --primary: #3b82f6; --bg: #1e1e2e;
    --text: #cdd6f4; --muted: #6c7086;
    --border: #45475a; --card: #313244;
  }
  body {
    margin: 0; padding: 24px;
    font-family: system-ui, -apple-system, sans-serif;
    color: var(--text); background: var(--bg);
    max-width: 600px;
  }
  .card {
    background: var(--card); border-radius: 12px;
    padding: 24px; margin-bottom: 16px;
  }
  .icon { font-size: 48px; margin-bottom: 12px; }
  h2 { margin: 0 0 8px 0; font-size: 20px; font-weight: 600; }
  p { margin: 0 0 16px 0; font-size: 14px; color: var(--muted); line-height: 1.5; }
  .tip {
    background: #1e1e2e; border-left: 3px solid var(--primary);
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    font-size: 13px; font-family: 'SF Mono', 'Fira Code', monospace;
    color: var(--text); margin-bottom: 16px;
  }
  .tag {
    display: inline-block; background: var(--primary); color: white;
    padding: 4px 10px; border-radius: 20px; font-size: 11px;
    font-weight: 500; margin-bottom: 12px;
  }
</style>
''';

String _chatDemoHtml() => '''
$_canvasStyle
<div class="card">
  <div class="icon">&#x1F4AC;</div>
  <div class="tag">Getting Started</div>
  <h2>Start a conversation</h2>
  <p>Just type what you need. No setup required — try any of these right now:</p>
  <div class="tip">"explain quantum computing in simple terms"</div>
  <div class="tip">"write a poem about artificial intelligence"</div>
  <div class="tip">"what are the top 5 tallest mountains in the world?"</div>
</div>
''';

String _emailDemoHtml() => '''
$_canvasStyle
<div class="card">
  <div class="icon">&#x1F4E7;</div>
  <div class="tag">Google Workspace</div>
  <h2>Connect Google Workspace</h2>
  <p>Open <b>Connections</b> in the sidebar, find Google Workspace, and sign in. I'll handle email, calendar, and contacts.</p>
  <div class="tip">"what's on my calendar today?"</div>
  <div class="tip">"email the team about tomorrow's standup"</div>
  <div class="tip">"find Bob's phone number in my contacts"</div>
  <p style="margin-top:16px;font-size:12px;color:var(--muted);">
    &#x1F50D; Don't want to connect? Try a general task:
    <br><span style="font-family:monospace;">"what's the population of Japan?"</span>
  </p>
</div>
''';

String _todosDemoHtml() => '''
$_canvasStyle
<div class="card">
  <div class="icon">&#x1F4CB;</div>
  <div class="tag">Tasks</div>
  <h2>Create and manage tasks</h2>
  <p>Add todos, set priorities, and track what's due. I'll keep your task list organized.</p>
  <div class="tip">"add buy groceries to my todo list"</div>
  <div class="tip">"what tasks are due this week?"</div>
</div>
''';

String _webDemoHtml() => '''
$_canvasStyle
<div class="card">
  <div class="icon">&#x1F310;</div>
  <div class="tag">Web Search</div>
  <h2>Search the web</h2>
  <p>Ask me to find articles, research topics, or pull live information from the web.</p>
  <div class="tip">"search for the latest AI news from this week"</div>
  <div class="tip">"find me a recipe for chocolate chip cookies"</div>
</div>
''';

String _filesDemoHtml() => '''
$_canvasStyle
<div class="card">
  <div class="icon">&#x1F4C1;</div>
  <div class="tag">Files</div>
  <h2>Work with files</h2>
  <p>Read, write, and organize files. You can manage everything through your workspace.</p>
  <div class="tip">"create a new file called notes.txt with today's meeting notes"</div>
  <div class="tip">"show me what files are in my workspace"</div>
</div>
''';

String htmlForChecklistItem(String itemId) {
  return switch (itemId) {
    'chat' => _chatDemoHtml(),
    'email' => _emailDemoHtml(),
    'todos' => _todosDemoHtml(),
    'web' => _webDemoHtml(),
    'files' => _filesDemoHtml(),
    _ => _chatDemoHtml(),
  };
}


