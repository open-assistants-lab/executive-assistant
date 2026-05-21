# Skills & Subagents UX Redesign

Date: 2026-05-21

## Problem

The Skills panel and Subagents panel in the workspace sidebar have inconsistent visual design and poor UX flow:

1. **Different list tile styles** — Skills uses one layout, Subagents uses another. Different badge positioning, icon sets, and action button placement.
2. **Skills buried in subagent editor** — Skills and tools (the most important subagent configuration) are hidden under an "Advanced" expansion tile alongside numeric limits.
3. **No cross-visibility** — Subagent list doesn't show which skills are assigned. Skills list doesn't show which subagents use a skill.
4. **Unmanageable tool list** — 120+ flat checkbox list for tool selection is overwhelming with no search or grouping.

## Design Goals

1. Consistent look and feel across both panels using existing `EaTokens` color/token system
2. Skills surfaced to top level in subagent editor
3. Tools grouped by category prefix
4. Cross-referencing: skill usage count, skill chips on subagent tiles
5. Minimal structural change — keep two-tab layout (Approach B)

## Design

### 1. Shared `EaListTile` Widget

A new shared widget used in both panels for consistent display.

| Token | Usage |
|---|---|
| `bgSurface` | Tile background |
| `borderSubtle` | Tile bottom border |
| `textPrimary` | Name/title |
| `textSecondary` | Description |
| `textTertiary` | Meta info (usage count, tooltips) |
| `accent` | Leading icon color, scope badge text |
| `accentMuted` | Scope badge background, skill chip background |
| `success` / `warning` / `error` | Status badge colors |

Layout (left to right):
```
[icon] | name + description + [skill chips (agents only)] | scope badge + status badge + action icons
```

### 2. Skills Panel Changes

- Each tile shows **usage count**: `"used by N agents"` in `textTertiary`
- Tap tile → open edit dialog (same as current, but with consistent styling)
- Delete: visible on hover (web) or long-press context menu (mobile); or keep trailing delete button but use consistent icon from both panels
- Create: "+" button in header (existing)

### 3. Subagents Panel Changes

- Each tile shows **assigned skill chips** below the description:
  - Background: `accentMuted`, text: `accent`, small rounded pills
  - Max 3 visible, overflow shows "+N"
  - Tap a chip → switch to Skills tab and highlight that skill
- Status badge:
  - `success` for idle
  - `warning` for running / cancelling
  - `error` for failed
- Action buttons: play (idle only), edit, delete (idle only)

### 4. Subagent Editor (Create & Edit) Restructure

Sections in order, no "Advanced" expansion tile:

**Section 1: Basic Info**
- Name (read-only in edit)
- Scope (user / workspace)
- Model (dropdown or text)
- System prompt (multiline, 4 lines)

**Section 2: Skills & Capabilities**
- Sub-section: **Skills** — chip picker with "+" to add
  - Selected skills shown as chips (accentMuted background, accent text)
  - "+" opens a dialog/overlay with searchable skill list
- Sub-section: **Tools** — grouped by category prefix
  - Each category is an ExpansionTile
  - Category header shows tri-state: unchecked (none), partial (some), checked (all)
  - Tool items shown without prefix (category provides context)
  - Search/filter field at top

**Section 3: Limits** (collapsible)
- Max LLM calls (default 50)
- Cost limit USD (default 1.0)
- Timeout seconds (default 300)

### 5. Grouped Tool Selector (Tree View)

Uses a **tree view** widget that shows categories as collapsible parent nodes with items as leaf nodes. This pattern is also reusable for model selection (provider → model) by swapping multi-select checkboxes for single-select radio dots.

Category groups derived from tool name prefix (e.g., `browser_*`, `email_*`, `files_*`, `memory_*`, `contacts_*`, `todos_*`, `mcp_*`, `subagent_*`, `shell_execute` → "shell", `time_get` → "system").

Grouping logic is **client-side** — parse prefix from tool name string. Order groups alphabetically.

Tree view layout (monospace-indented for visual hierarchy):

```
🔍 filter by name or category...
✓ ▾ browser              2/20
      ✓ click
      ✓ close_all
      ☐ eval
      +17 more
☐ ▸ email                0/8
☐ ▸ files                0/7
☐ ▸ contacts             0/6
```

Each group node:
- Tri-state icon: unchecked (☐) / checked (✓) / partial (▣)
- Expand/collapse chevron (▾/▸)
- Selection count (e.g., `2/20`)
- Clicking the row toggles all/none items

Each leaf node:
- Checkbox + tool name (without prefix — context from parent)
- Overflow: groups with 20+ items show "+N more" when collapsed

Search: text field at top filters both group names and item names by substring match. Matching groups expand automatically.

### 6. Color & Widget Consistency

All new/changed widgets use `context.tokens` exclusively — no hardcoded colors. Key token mappings:

| UI Element | Token |
|---|---|
| Skill chip background | `accentMuted` |
| Skill chip text | `accent` |
| Status badge idle | `success` with 18% alpha bg |
| Status badge running | `warning` with 18% alpha bg |
| Status badge failed | `error` with 18% alpha bg |
| Scope badge "ws" | `accentMuted` bg, `accent` text |
| Tool group header | `bgElevated` bg, `textSecondary` text |
| Tool search field | `bgField` bg |
| Section divider | `borderSubtle` |

## File Changes

| File | Change |
|---|---|
| `lib/features/workspace/skills_panel.dart` | Redesign list tiles; add usage count; use shared widget |
| `lib/features/workspace/subagents_panel.dart` | Redesign list tiles with skill chips; restructure editor dialog; use tree view for tools |
| `lib/features/workspace/workspace_panel.dart` | No structural change (tabs stay as-is) |
| (new) `lib/features/workspace/shared_list_tile.dart` | Shared `EaListTile` widget |
| (new) `lib/features/workspace/tree_selector.dart` | Generic `GroupedTreeSelector<T>` widget — reusable for tools (multi-select) and models (single-select) |

## Reusability: Model Selection

The `GroupedTreeSelector<T>` widget supports both modes via a `selectionMode` parameter:

| Mode | Selection | Use case |
|---|---|---|
| `multi` | Checkboxes | Tool selection in subagent editor |
| `single` | Radio dots | Model selection in subagent editor |

Model data is grouped by `provider_id` (e.g., `anthropic`, `openai`, `google/gemini`) with model names as leaf nodes. Same tree view, same search, same expand/collapse behavior.

## Future Considerations (out of scope)

- Skill usage count computed client-side from loaded subagent list
- Cross-tab navigation (tap skill chip → switch to Skills tab) needs a callback mechanism
- Tree selector search is client-side only — no backend endpoint needed
