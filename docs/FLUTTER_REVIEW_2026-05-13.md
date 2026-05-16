# Flutter App Review — 2026-05-13

Codebase at `flutter_app/`. Architecture: models → services → providers → features → theme, using Riverpod state management, Go Router for navigation, WebSocket for streaming, HTTP for CRUD.

---

## 1. Race: Duplicate Messages During History Load

**Location:** `lib/providers/agent_provider.dart:463-467` + `lib/providers/agent_provider.dart:154-158`

On WebSocket connect, `_onStatusChange` starts `_loadHistorySafely()`. During the async history load, incoming WS messages are buffered in `_bufferedMessages` (line 262). After loading, buffered messages are flushed (line 154-158).

But history messages get IDs like `hist_0`, `hist_1`, while `done` events create assistant messages with IDs like `ai_1234567890`. These ID prefixes never collide, so the dedup check at lines 129-130 passes. A buffered `done` event that corresponds to a message already loaded from history would be appended as a **duplicate**.

```
connect → loadHistory (async, ~500ms)
         → WS message "done" arrives during load → buffered
         → history loaded (includes this message as hist_42)
         → flush buffer → ai_1234567890 appended again
```

**Fix:** Server should include a stable message ID in `done` events. Client should check content hash rather than id prefix for dedup. Or, the server should return a cursor from `GET /conversation` so the client knows where history ends and streaming begins.

---

## 2. `tool_input_delta` Events Silently Discarded

**Location:** `lib/providers/agent_provider.dart:309-313`

```dart
if (canonical == 'tool_input_delta') {
  // Streaming tool argument deltas from reasoning models;
  // safe to ignore for the Phase 13 chat refactor.
  return;
}
```

Reasoning models (Claude extended thinking, Gemini thinkingConfig) stream tool calls as three block-structured events:

```
tool_input_start {call_id, tool, args: {"to": ...}}   ← partial
tool_input_delta {call_id, args_delta: "more json"}    ← N events
tool_input_delta {call_id, args_delta: "final bit"}
tool_input_end {call_id}
```

The `tool_input_start` event creates the tool card with whatever args arrived in the first chunk. All subsequent deltas carry the remaining argument JSON. Ignoring them means the tool card shows **incomplete or truncated arguments**.

**Impact:** Tool cards in chat show partial JSON like `{"to": "alice@` instead of `{"to": "alice@example.com", "subject": "Q3 report"}`.

**Fix:** Accumulate `args_delta` strings in a `Map<String, StringBuffer>` keyed by `call_id` during streaming, concatenate all deltas, and parse the accumulated JSON at `tool_input_end`. The `_upsertActiveTool` method already supports per-call_id update — it just needs to be called on each delta.

---

## 3. Reasoning Content Discarded

**Location:** `lib/providers/agent_provider.dart:283-288`

```dart
if (canonical == 'reasoning_delta' || type == 'reasoning') {
  // TODO(phase-13): Store reasoning text in state for reasoning_card display
  // For now, silently consume reasoning events.
  return;
}
```

Models with thinking/reasoning capabilities (Anthropic Claude, Gemini, DeepSeek) produce chain-of-thought as `reasoning_start/delta/end` stream events. The app silently consumes them — users never see the model's thinking.

**Impact:** Users can't debug why the model made a decision, can't verify the reasoning is sound, and lose transparency into the agent's thought process.

**Fix:** Add `reasoningText` field to `ChatState`. Append deltas during streaming. Render in a collapsible `ReasoningBubble` (the widget already exists at `lib/features/chat/widgets/reasoning_bubble.dart` but is unused). Clear on `done`.

---

## 4. API Client Has No Timeout

**Location:** `lib/services/api_client.dart:22`

```dart
_httpClient = httpClient ?? http.Client();
```

The `http.Client` is created with no timeout parameter. All HTTP calls (`GET`, `POST`, `PUT`, `DELETE`) to the backend server will block indefinitely if the server hangs.

**Impact:** Frozen UI with no error bar, no retry mechanism, no user feedback.

**Fix:**

```dart
_httpClient = httpClient ?? http.Client()
  ..connectionTimeout = const Duration(seconds: 10);
```

Or wrap calls with `.timeout()`:

```dart
final response = await _get(url).timeout(const Duration(seconds: 30));
```

Timeout should trigger a visible error in the UI via the existing `ErrorBar` widget.

---

## 5. `text_delta` Content Parsing Degrades to Dart `toString()`

**Location:** `lib/providers/agent_provider.dart:241-251`

```dart
String _extractTextContent(dynamic content) {
  if (content is String) return content;
  if (content is List) {
    return content
        .whereType<Map>()
        .where((m) => m['type'] == 'text')
        .map((m) => m['text']?.toString() ?? '')
        .join();
  }
  return content?.toString() ?? '';
}
```

If `content` is neither a `String` nor a `List<Map>`, it falls through to `content?.toString()`. For a `Map` object, Dart's default `toString()` produces `{key1: value1, key2: value2}`, not useful display text. This path should never fire with the current server, but there's no guard clause logging when it happens — the garbage text silently appears in the streaming bubble.

**Fix:** Log a warning and return empty string for unexpected content types:

```dart
if (content is String) return content;
if (content is List) { ... }
debugPrint('[AgentNotifier] Unexpected text_delta content type: ${content.runtimeType}');
return '';
```
