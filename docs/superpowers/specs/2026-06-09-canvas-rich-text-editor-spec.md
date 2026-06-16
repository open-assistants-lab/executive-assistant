# Rich Text Editor via Canvas (Novel.sh)

**Date:** 2026-06-09
**Status:** Draft
**Motivation:** The Canvas feature already renders interactive HTML in WebViews with a `postMessage` bridge. By embedding a WYSIWYG rich text editor into a canvas surface, the agent can provide inline file editing — user edits content in the editor, submits via `postMessage`, and the agent writes the file via `files_write`.

---

## 1. Current Canvas Architecture (Already Built)

```
Agent produces ```html:canvas fence block
  → Backend _extract_canvas() parses it
  → WS/SSE/REST delivers CanvasUpdateMessage to Flutter
  → CanvasTab renders HTML in WebViewWidget
  → User interacts via postMessage → canvasBridge → agent as chat message
  → Agent processes and writes file via files_write
```

Existing fence types:
- `html:canvas` — free-form HTML
- `html:skill-form` — skill creation form
- `html:subagent-form` — subagent creation form

---

## 2. New Fence Modifier: `html:editor`

**Schema:** requires `initialContent` (markdown string) and `filePath` (absolute path)

````markdown
```html:editor
filePath: /Users/eddy/some-file.md
---

# Hello World

This is **markdown** content that appears in the editor.
```
````

The fence parser extracts `filePath` from the first line (after `filePath: ` prefix, before the `---` separator). Everything after `---` is the markdown content pre-loaded into the editor.

```python
_EDITOR_FENCE = re.compile(
    r"```html:editor\s*\nfilePath:\s*(.+?)\n---\n(.*?)```",
    re.DOTALL,
)
```

### Schema registration

```python
CANVAS_SCHEMAS: dict[str, list[str]] = {
    "skill-form": ["name", "description", "content"],
    "subagent-form": ["name", "description", "model", "system_prompt"],
    "canvas": [],
    "editor": ["filePath", "content"],
}
```

---

## 3. Editor HTML Wrapper

The backend wraps the editor content with Novel.sh bundled HTML + JS. Since the editor is rendered inside a Flutter WebView, the JS bundle must be loaded inline (no external network in sandboxed mode).

### Bundle strategy

Novel.sh is a React component. The build produces a self-contained IIFE that mounts an editor on a target div. The build process:

1. Create a small entry file that imports + mounts Novel.sh's `Editor` component
2. Bundle with esbuild — React + Novel + theme CSS into a single IIFE
3. Inline the IIFE into `src/http/static/editor.html` (shared path, not per-user)

**Entry file (`build/editor-entry.jsx`):**

```jsx
import { Editor } from 'novel'
import { render } from 'react-dom'

function mountEditor(target, initialMarkdown, filePath) {
  render(
    React.createElement(Editor, {
      defaultValue: initialMarkdown,
      onUpdate: (editor) => {
        window.__editorHtml = editor.getHTML()
        window.__editorMarkdown = editor.storage.markdown.getMarkdown()
      },
      className: 'novel-editor',
    }),
    target
  )
  // Expose save/cancel globally for button onclick handlers
  window.__filePath = filePath
  window.__save = () => {
    const html = window.__editorHtml || target.innerHTML
    const md = window.__editorMarkdown || ''
    const bridge = window.flutterBridge
    if (bridge) bridge.postMessage(JSON.stringify({
      action: 'save',
      editor: 'novel',
      filePath: window.__filePath,
      html,
      markdown: md,
    }))
  }
  window.__cancel = () => {
    const bridge = window.flutterBridge
    if (bridge) bridge.postMessage(JSON.stringify({
      action: 'cancel', editor: 'novel'
    }))
  }
}

window.mountEditor = mountEditor
```

**Build command:**

```bash
mkdir -p build && cd build
npm init -y
npm install react react-dom novel
npx esbuild editor-entry.jsx \
  --bundle --format=iife --minify \
  --external:react --external:react-dom \
  --outfile=editor-bundle.js
# Inline editor-bundle.js into the HTML template
```

The IIFE exposes `window.mountEditor(mountEl, markdown, filePath)` which the template calls on DOMContentLoaded.

### Static file location

The editor HTML lives at `src/http/static/editor.html` — a shared resource, not per-user data.

```python
import os
_EDITOR_TEMPLATE_PATH = Path(__file__).parent.parent / "static" / "editor.html"

def _render_editor_surface(file_path: str, content: str) -> str:
    """Inject file path and initial content into editor HTML template."""
    with open(_EDITOR_TEMPLATE_PATH) as f:
        template = f.read()
    # Use JSON serialization for safe JS string escaping
    import json
    escaped_path = json.dumps(file_path)
    escaped_content = json.dumps(content)
    html = template.replace("__FILE_PATH__", escaped_path)
    html = html.replace("__INITIAL_MARKDOWN__", escaped_content)
    return html
```

`json.dumps()` handles all escaping (quotes, backslashes, newlines, Unicode).

### The wrapper HTML template (`src/http/static/editor.html`)

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    :root { --primary: #6C5CE7; --bg: #1e1e2e; --text: #cdd6f4; --border: #313244; }
    body { background: var(--bg); color: var(--text); font-family: system-ui; margin: 0; }
    .editor-wrapper { display: flex; flex-direction: column; height: 100vh; }
    .editor-content { flex: 1; overflow-y: auto; padding: 16px; }
    .status-bar {
      display: flex; justify-content: space-between; align-items: center;
      padding: 8px 16px; border-top: 1px solid var(--border);
      font-size: 12px; color: #6c7086;
    }
    .status-bar button {
      background: var(--primary); color: #fff; border: none;
      border-radius: 6px; padding: 6px 16px; cursor: pointer;
    }
    .status-bar button.cancel { background: #45475a; }
    .NovelEditor { border: none; min-height: 100%; }
  </style>
</head>
<body>
  <div class="editor-wrapper">
    <div id="novel-mount" class="editor-content"></div>
    <div class="status-bar">
      <span id="chars">0 chars</span>
      <span>
        <button class="cancel" onclick="window.__cancel()">Cancel</button>
        <button onclick="window.__save()">Save</button>
      </span>
    </div>
  </div>
  <script>
    // Novel.sh bundle injected here (see build step)
    __NOVEL_BUNDLE__

    document.addEventListener('DOMContentLoaded', () => {
      const target = document.getElementById('novel-mount');
      window.mountEditor(target, __INITIAL_MARKDOWN__, __FILE_PATH__);
    });
  </script>
</body>
</html>
```

---

## 4. Backend Changes

### `src/http/routers/conversation.py`

- Add `_EDITOR_FENCE` regex alongside `_CANVAS_FENCE`
- Add `_extract_editor(text)` that finds `html:editor` blocks and returns surfaces with `surface_type="editor"`, `surface_id="editor-N"`, `html` = rendered Novel.sh wrapper
- Update `_extract_canvas()` to also call `_extract_editor()` — or create a unified `_extract_surfaces()` that handles all surface types
- The `filePath` is stored as a `data-file-path` attribute or injected via JS init message

```python
_EDITOR_FENCE = re.compile(
    r"```html:editor\s*\nfilePath:\s*(.+?)\n---\n(.*?)```",
    re.DOTALL,
)

def _extract_editor(text: str) -> list[dict]:
    surfaces: list[dict] = []
    for i, match in enumerate(_EDITOR_FENCE.finditer(text)):
        file_path = match.group(1).strip()
        content = match.group(2).strip()
        html = _render_editor_surface(file_path, content)
        surfaces.append({
            "surface_id": f"editor-{i}",
            "action": "create",
            "html": html,
            "surface_type": "editor",
            "file_path": file_path,
        })
    return surfaces
```

### `CanvasUpdateMessage` (`src/http/ws_protocol.py`)

- Add `file_path: str = ""` field to `CanvasUpdateMessage` — optional, populated for editor surfaces. Not strictly needed (Flutter doesn't need filePath), but useful for logging/debugging.

### WebSocket handler (`src/http/routers/ws.py`)

- `_handle_canvas_update()` already broadcasts `CanvasUpdateMessage` for all surfaces. No changes needed — editor surfaces flow through as regular canvas updates.
- `_handle_canvas_update_from_preview()` also works automatically since editor surfaces are just canvas surfaces with `surface_type="editor"`.

### REST handler (`src/http/routers/conversation.py`)

The REST endpoint already includes `canvas_blocks` in verbose data. Editor surfaces appear alongside canvas surfaces.

### SSE handler (`src/http/routers/conversation.py`)

The SSE endpoint already yields canvas blocks as SSE events. Editor surfaces appear alongside canvas surfaces.

---

## 5. Flutter Changes

### `canvas_tab.dart`

- No structural changes needed — the editor renders as a regular canvas surface with `type: "canvas_update"`
- The `postMessage` bridge (`_onCanvasAction()`) already handles `action: 'save'` and `action: 'cancel'` — they flow into the agent as chat messages
- The agent receives the `[Canvas submit] editor: {filePath}` message and calls `files_write` to persist

### Potential UX improvements (optional)

- When receiving an `editor` surface, set it as the active tab automatically (already happens via `WorkspacePanel`'s auto-activation)
- Could add a visual indicator (pencil icon) to distinguish editor surfaces from other canvas surfaces

---

## 6. Agent Skill / Prompt Integration

The `canvas-painting` seed skill (`src/skills_seed/canvas-painting/SKILL.md`) needs an update to document the new fence type:

````
### File Editor

To let the user create or edit a file interactively:

```html:editor
filePath: /path/to/file.md
---

Initial markdown content goes here.
```

The editor will render in the Canvas tab. The user edits the content and clicks Save.
A `[Canvas submit]` message will be sent back containing the file path and the new
markdown content. Use `files_write` to persist the result.
````

---

## 7. Constraints & Edge Cases

| Constraint | Solution |
|------------|----------|
| **Editor bundle size** | Novel.sh core + minimal theme is ~50-100KB gzipped. Acceptable for inline HTML in WS message. Cache in `src/http/static/editor.html`. |
| **No external network** | Flutter WebView has no internet access in sandboxed mode. Bundle must be fully inline. |
| **JS bridge via `postMessage`** | `flutterBridge.postMessage()` is the standard Flutter WebView JS channel. Works with `WebViewController.runJavaScript()` or `JavaScriptChannel`. |
| **Large files** (10K+ chars) | Send as-is in WS message. If >1MB, consider chunked delivery or file reference. Unlikely for typical file editing. |
| **Concurrent editors** | Each editor surface gets a unique `surface_id` (editor-0, editor-1). PostMessage actions include the surface context via agent's message. |
| **Markdown→HTML→markdown round-trip** | Novel.sh parses markdown internally (ProseMirror schema). Output via `editor.storage.markdown.getMarkdown()`. For HTML→markdown, bundle `turndown` alongside in the IIFE. |

---

## 8. Implementation Order

1. **Build editor template** — Create `src/http/static/editor.html` with Novel.sh IIFE + toolbar + status bar + postMessage bridge. Test in standalone browser.
2. **Add `_EDITOR_FENCE` regex** — Parse `html:editor` blocks, extract `filePath` and initial content.
3. **Add `_render_editor_surface()`** — Inject file path and initial content into editor template.
4. **Wire into response pipeline** — Call `_extract_editor()` alongside `_extract_canvas()` in REST, SSE, and WS handlers.
5. **Update canvas-painting skill** — Document the new fence type for the agent.
6. **Test end-to-end** — Manual: agent emits `html:editor` fence, canvas tab shows editor, user edits and saves, agent writes file.

---

## 9. Tests

### Unit tests for `_extract_editor()`

```python
def test_extract_editor_basic():
    text = '```html:editor\nfilePath: /test/file.md\n---\n\n# Hello\n\nWorld\n```'
    result = _extract_editor(text)
    assert len(result) == 1
    assert result[0]["surface_type"] == "editor"
    assert result[0]["file_path"] == "/test/file.md"
    assert "Hello" in result[0]["html"]

def test_extract_editor_multiple():
    text = (
        '```html:editor\nfilePath: /a.md\n---\n\nFile A\n```\n'
        'Some text\n'
        '```html:editor\nfilePath: /b.md\n---\n\nFile B\n```'
    )
    result = _extract_editor(text)
    assert len(result) == 2

def test_extract_editor_no_file_path():
    text = '```html:editor\n---\n\nContent\n```'
    result = _extract_editor(text)
    assert result == []

def test_extract_editor_empty():
    text = 'No fences here'
    result = _extract_editor(text)
    assert result == []

def test_extract_editor_interleaved_with_canvas():
    text = (
        '```html:canvas\n<div>hello</div>\n```\n'
        '```html:editor\nfilePath: /f.md\n---\n\ncontent\n```'
    )
    canvas = _extract_canvas(text)
    editor = _extract_editor(text)
    assert len(canvas) == 1
    assert canvas[0]["surface_type"] == "canvas"
    assert len(editor) == 1
    assert editor[0]["surface_type"] == "editor"

def test_extract_canvas_unified():
    """_extract_surfaces returns both canvas and editor surfaces."""
    text = (
        '```html:canvas\n<div>x</div>\n```\n'
        '```html:editor\nfilePath: /f.md\n---\n\nx\n```'
    )
    result = _extract_surfaces(text)
    assert len(result) == 2
    assert result[0]["surface_type"] == "canvas"
    assert result[1]["surface_type"] == "editor"
```

### Integration test plan

| Scenario | Steps | Expected |
|----------|-------|----------|
| Editor renders in canvas tab | Agent emits `html:editor` fence in response, verify WS delivers `canvas_update` event with `surface_type=editor` | WebView shows editor with initial content |
| Save button sends content back | User clicks Save, verify `[Canvas submit] editor: ...` message sent to agent | Agent receives markdown content and file path |
| Cancel button dismisses | User clicks Cancel, verify `[Canvas] User cancelled the form.` message sent | No file written |
| Multiple editors | Agent emits two `html:editor` fences, verify two surfaces with different `surface_id` values | Both render independently |

---

## 10. Open Questions

1. **Markdown output format** — Novel.sh outputs ProseMirror JSON or HTML via `editor.getHTML()`. For markdown, use `editor.storage.markdown.getMarkdown()` (Novel.sh's built-in markdown extension). Confirm it produces clean markdown on save.
2. **File path validation** — The agent outputs a `filePath` in the fence. Should the editor validate it (existence, extension) before submitting? Or trust the agent? Recommendation: trust agent, validate only on the agent side.
3. **readOnly mode** — Could the editor support a read-only mode for displaying formatted markdown files (preview before editing)?