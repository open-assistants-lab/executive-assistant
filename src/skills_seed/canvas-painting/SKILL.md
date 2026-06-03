---
name: canvas-painting
description: >-
  Generate HTML for the Canvas tab. Use when asked to create interactive
  visualizations, forms, dashboards, reports, config panels, skill editors,
  subagent editors, or any rendered surface in the Canvas. Always emit full
  HTML via a single fenced code block per surface — the Canvas renders it
  directly.
---

# Canvas Painting

Generate self-contained HTML rendered inside the Canvas tab. Every output
is a single fenced code block using a surface-specific fence tag.

## Output Format

Wrap HTML in a fenced block tagged for the target surface:

    ```html:canvas
    <!DOCTYPE html>
    <html><body>...</body></html>
    ```

    ```html:skill-form
    ...form HTML...
    ```

    ```html:subagent-form
    ...form HTML...
    ```

One block per response. The Canvas extracts the fence and renders in an
isolated, scoped shadow-root environment.

## Surface Types

### `html:canvas` — Free-form interactive pages
No required structure. Use for dashboards, charts, reports, visualizations,
config panels, or any interactive widget.

### `html:skill-form` — Create/edit a skill
Must contain `<form>` fields with these `name` attributes:

| name          | type   | required |
|---------------|--------|----------|
| `name`        | text   | yes      |
| `description` | text   | yes      |
| `content`     | textarea | yes    |

### `html:subagent-form` — Create/edit a subagent
Must contain `<form>` fields with these `name` attributes:

| name             | type   | required |
|------------------|--------|----------|
| `name`           | text   | yes      |
| `description`    | text   | yes      |
| `model`          | select | no       |
| `system_prompt`  | textarea | yes    |

## Theming with CSS Custom Properties

The Canvas host injects these custom properties. Use them instead of
hardcoded colors so surfaces adapt to light/dark mode:

| property         | usage                          |
|------------------|--------------------------------|
| `var(--primary)` | accent color (buttons, links)  |
| `var(--bg)`      | background                     |
| `var(--text)`    | foreground text                |
| `var(--border)`  | borders, dividers              |

```css
body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, sans-serif;
  margin: 0; padding: 16px;
}
button {
  background: var(--primary);
  color: #fff; border: none;
  padding: 8px 16px; border-radius: 6px;
  cursor: pointer;
}
```

## `postMessage` Bridge

To communicate with the host app (save data, request actions, close the
panel), use `window.parent.postMessage`:

```js
window.parent.postMessage({ type: 'canvas:save', payload: {...} }, '*');
window.parent.postMessage({ type: 'canvas:close' }, '*');
```

| message type       | payload     | host action           |
|--------------------|-------------|-----------------------|
| `canvas:save`      | form fields | persist form data     |
| `canvas:close`     | —           | close the canvas tab  |
| `canvas:resize`    | `{height}`  | resize canvas iframe  |

Listen for host → canvas messages to receive context or initial data:

```js
window.addEventListener('message', (e) => {
  if (e.data?.type === 'canvas:init') {
    // e.data.payload contains seed data
  }
});
```

## Constraints

- Output exactly one fenced block per response.
- Do NOT include `<script src="...">` to external origins (CSP blocked).
- Do NOT include `<link href="...">` to external stylesheets.
- Use `input`, `textarea`, `select`, `button` — standard form elements.
- For charts/visuals, either draw with a `<canvas>` element or use inline
  SVG. Small utility libraries are fine if embedded in a `<script>` block.
