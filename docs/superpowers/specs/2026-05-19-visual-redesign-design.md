# Visual Redesign — Design Spec

> **Goal:** Full visual redesign with minimalist dark aesthetic, Inter + Fira Code typography, consistent design token system, responsive layout, and polished animations.

**Status:** Approved for Implementation

## Peer Review Resolutions

All blocking findings resolved as follows:

| Finding | Resolution |
|---------|-----------|
| No dark mode foundation | Build `ThemeExtension` subclass (`EaTokens`) with mode-aware colors accessed via `context.tokens.colors.bgSurface`. Deliver dark mode in Phase 1 before any screen retouch. |
| Fonts not bundled | Add Inter + Fira Code via `google_fonts` package in Phase 1 step 0. |
| Motion naming conflict | Keep existing `EaMotion` names (`snappy`/`fluid`/`intuitive`). Component rules reference `EaMotion.buttonPressScale`, `tapPulse`, `staggeredEntry`, `reducedMotion` by name. Curves and numeric durations unchanged from spec. |
| Existing `ea_widgets.dart` unused | Delete old file and rebuild `lib/widgets/` fresh with new token system. No hybrid. Old widgets were never used in production. |
| 400+ token references | Backward-compat static shim (`AppColors.dark`/`light` accessors) during migration. Screens migrate incrementally to `context.tokens`. Shim deprecated with lint annotation, removed in Phase 4. |
| Chat panel duplication | Extract shared `ChatMessageList` widget. Both `ChatScreen` and `_ChatPanel` consume it. Added to file structure. |
| `AnimatedBuilder` | Confirmed correct Flutter API. Not a bug. No action needed. |
| "Fix 37 analyzer issues" | Enumerated below. Fixed in Phase 1: 9 unused imports, 8 RadioListTile deprecations, 20 null-aware warnings. |

**Non-blocking acknowledged:**
- Subagent panel corrected to 1254 lines
- Commented-out sidebar items (`companion`, `memory`, `skills`, `subagents`) out of scope
- Motion naming aligned to existing EaMotion
- Old `ToolCallCard` (62 lines) replaced by new spec

## Design Principles

1. **Tokens over values** — Every color, spacing, radius, and text style is defined as a named token. No raw values in widgets.
2. **Mode-agnostic** — Dark (default), light, and high-contrast modes share one token system. Adding a new mode = adding one map of token overrides.
3. **Motion as intent** — Animations communicate hierarchy (staggered entries), action (press scale), and state (smooth transitions). Not decorative.
4. **8px grid** — All spacing divisible by 4. Layout snaps to rhythm.

---

## 1. Design Tokens

### 1.1 Colors

```
┌─────────────────┬────────────────────────────────────┬────────────────────────────────────┐
│ Token            │ Dark Mode                           │ Light Mode                          │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ Background                                                             │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ bg-canvas        │ #0A0A0F (app shell, sidebar)       │ #F8F8FA                             │
│ bg-surface       │ #12121A (cards, panels, dialogs)   │ #FFFFFF                             │
│ bg-elevated      │ #1A1A26 (hover, active, tooltips)  │ #F0F0F4                             │
│ bg-field         │ #161620 (inputs, search, chips)    │ #EBEBF0                             │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ Content                                                                │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ text-primary     │ #EEEEF0 (body, headings, labels)   │ #12121A                             │
│ text-secondary   │ #8B8BA0 (captions, helpers)        │ #5C5C6E                             │
│ text-tertiary    │ #5C5C6E (disabled, placeholders)   │ #9C9CB0                             │
│ text-inverse     │ #0A0A0F (on accent backgrounds)    │ #FFFFFF                             │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ Accent                                                                 │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ accent           │ #6C5CE7 (primary purple-violet)    │ #5E4ED6 (darker for light BG)       │
│ accent-hover     │ #7C6CF7 (hover / active)           │ #4E3EC6                             │
│ accent-muted     │ #3D3580 (subtle accent BG)         │ #E8E5FF                             │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ Semantic                                                               │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ success          │ #2ED573                             │ #1DB954                             │
│ warning          │ #FFA502                             │ #E89400                             │
│ error            │ #FF4757                             │ #E8404F                             │
│ info             │ #54A0FF                             │ #3B8EFF                             │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ Borders                                                                │
├─────────────────┼────────────────────────────────────┼────────────────────────────────────┤
│ border-subtle    │ #1E1E2E (card edges, dividers)     │ #E4E4EC                             │
│ border-default   │ #2A2A3C (input borders, active)    │ #D0D0DC                             │
│ border-accent    │ #6C5CE780 (focus rings, selected)   │ #5E4ED680                           │
└─────────────────┴────────────────────────────────────┴────────────────────────────────────┘
```

### 1.2 Typography

```
Fonts:
  sans-serif    'Inter'     weights: 400, 500, 600
  mono          'Fira Code' weights: 400, 500

Scale (Inter):
  display-large   32px / 600 / 1.2 / -0.5px   — screen titles, hero text
  heading-large   24px / 600 / 1.3 / -0.3px   — section headers, card titles
  heading-medium  18px / 600 / 1.3 / -0.2px   — dialog titles, panel headers
  body-large      16px / 400 / 1.5 / 0px       — message bubbles, content
  body-medium     14px / 400 / 1.5 / 0px       — descriptions, secondary text
  body-small      13px / 400 / 1.4 / +0.1px    — meta, timestamps
  caption         11px / 500 / 1.3 / +0.2px    — badges, chips, overlines

Scale (Fira Code):
  mono-large      14px / 400 / 1.6 / 0px       — tool results, code blocks
  mono-medium     13px / 400 / 1.5 / 0px       — tool names, metrics, keys
  mono-small      11px / 400 / 1.4 / 0px       — IDs, hashes, compact data
```

### 1.3 Spacing (8px grid)

```
  Space.xs       4px   — icon padding, tight inline gaps
  Space.sm       8px   — inline gaps between chips, icon-to-label
  Space.md      12px   — card content padding
  Space.lg      16px   — component internal spacing
  Space.xl      24px   — screen edge padding, section gaps
  Space.2xl     32px   — between major sections
  Space.3xl     48px   — hero spacing, empty states
```

### 1.4 Radius

```
  Radius.sm      6px   — inputs, chips, badges, small buttons
  Radius.md     10px   — standard buttons, tool cards, inline cards
  Radius.lg     14px   — dialogs, sheet tops, panels
  Radius.xl     20px   — message bubbles, large cards
```

### 1.5 Elevation (mode-dependent)

```
  Dark mode:
    surface-raised    bg-elevated + border-subtle
    surface-floating  bg-surface + border-default + box-shadow(0 4px 24px rgba(0,0,0,0.4))
    surface-modal     bg-surface + border-default + box-shadow(0 8px 48px rgba(0,0,0,0.6)) + backdrop-blur(8px)

  Light mode:
    surface-raised    bg-surface + box-shadow(0 1px 3px rgba(0,0,0,0.08))
    surface-floating  bg-surface + box-shadow(0 4px 16px rgba(0,0,0,0.12))
    surface-modal     bg-surface + box-shadow(0 8px 32px rgba(0,0,0,0.16)) + backdrop-dim
```

### 1.6 Motion

```
  Duration.instant   100ms  — hover feedback, toggle
  Duration.fast      200ms  — press scale, focus ring, tooltip
  Duration.normal    300ms  — page transitions, dialog open/close
  Duration.slow      400ms  — staggered list entry, hero animation
  Duration.graceful  600ms  — empty state, onboarding

  Curve:
    ease-out          cubic-bezier(0.0, 0.0, 0.2, 1.0)    — entering elements
    ease-in           cubic-bezier(0.4, 0.0, 1.0, 1.0)    — exiting elements
    ease-in-out       cubic-bezier(0.4, 0.0, 0.2, 1.0)    — state transitions
    spring            cubic-bezier(0.34, 1.56, 0.64, 1.0) — overshoot for emphasis
```

---

## 2. Component Style Rules

### 2.1 Buttons

**Sizes:**
| Size | Height | Padding H | Font | Radius | Min Width |
|------|--------|-----------|------|--------|-----------|
| sm | 32px | Space.sm (8px) | caption / 11px | Radius.sm | — |
| md | 40px | Space.md (12px) | body-medium / 14px | Radius.md | — |
| lg | 48px | Space.lg (16px) | body-medium / 14px | Radius.md | 120px |

**Variants:**
| Variant | Background | Border | Text | Hover | Pressed |
|---------|------------|--------|------|-------|---------|
| Primary | accent | none | text-inverse | bg → accent-hover | scale(0.97) |
| Secondary | transparent | 1px border-default | text-primary | bg → bg-elevated | scale(0.97) |
| Ghost | transparent | none | text-secondary | text → text-primary, bg → bg-elevated | scale(0.97) |
| Danger | error | none | white | bg → error + 10% lighter | scale(0.97) |

**States:**
| State | Visual |
|-------|--------|
| Default | Variant base |
| Hover | Variant hover (200ms ease-out) |
| Pressed | scale(0.97), 200ms ease-out |
| Focused | 2px border-accent ring outside, 2px gap |
| Disabled | opacity 0.4, no pointer events, no hover |
| Loading | Same size, spinner replaces label, button disabled |

**Icons:**
- Icon before label: 6px gap
- Icon only (square button): same height × same width, icon centered
- Icon after label: not supported (use before only for consistency)

---

### 2.2 Input Fields

**Sizes:**
| Size | Height | Padding H | Padding V | Font | Radius | Gap |
|------|--------|-----------|-----------|------|--------|-----|
| md | 40px | Space.md | 10px | body-medium | Radius.sm | — |
| lg | 48px | Space.lg | 14px | body-large | Radius.sm | — |

**Variants:**
| Variant | Background | Border | Border Width |
|---------|------------|--------|-------------|
| Filled | bg-field | border-default | 1px |
| Outlined | transparent | border-default | 1px |
| Underlined | transparent | border-default (bottom only) | 1px |

**States:**
| State | Visual |
|-------|--------|
| Normal | bg-field, border-default, text-primary |
| Hover | border-default brightens to border-accent 30% |
| Focused | border-accent, 1px glow (box-shadow: 0 0 0 1px accent @ 30% opacity). Label shrinks to caption size, moves up |
| Filled | Same as focused but stays styled (used when value present) |
| Error | border: error, 1px error glow. Helper text: error colored, caption font |
| Disabled | opacity 0.3, bg-canvas (not bg-field), no interactions |

**Decorations:**
- **Label:** Floating label — body-medium when empty/resting → caption when focused/filled. Text-secondary → text-primary on focus
- **Helper text:** Below input, caption font, text-secondary. Becomes error color when in error state
- **Prefix icon:** Left, text-tertiary → text-primary on focus, 16px, Space.sm padding
- **Suffix icon:** Right, same styling. Used for clear (×), visibility toggle, dropdown chevron
- **Character count:** Right-aligned below, caption, text-tertiary, only shown when maxLength set

**Search field variant:**
- Always Filled variant, md size
- Prefix: search icon (16px)
- Suffix: clear (×) icon when text present
- No label (placeholder instead): "Search..."
- Results dropdown: bg-surface, border-default, Radius.md, max-height 240px, scrollable

**Dropdown / Autocomplete variant:**
- Same as md Filled input
- Suffix: chevron-down icon, rotates 180° when open (200ms ease-out)
- Menu: bg-surface, border-default, Radius.md, max-height 280px, scrollable
- Selected item: bg-elevated, text-primary, checkmark suffix
- Hovered item: bg-elevated
- Keyboard navigation: up/down arrows, enter to select, escape to close

---

### 2.3 Cards

**Padding presets:**

| Preset | Padding | Use |
|--------|---------|-----|
| compact | Space.sm (8px) all sides | Tool cards, status chips, dense lists |
| default | Space.md (12px) all sides | Standard cards, message bubbles |
| spacious | Space.lg (16px) all sides | Detail views, forms, settings cards |

**Variants:**

| Variant | Background | Border | Hover |
|---------|------------|--------|-------|
| Static | bg-surface | 1px border-subtle | None |
| Hoverable | bg-surface | 1px border-subtle | bg → bg-elevated, border → border-default, 200ms ease-out |
| Interactive | bg-surface | 1px border-subtle | Same as hoverable + press-scale(0.985) on tap |
| Flat | transparent | none | None (used for grouping, not visual cards) |

**Loading skeleton:**
- Placeholder blocks: bg-elevated, Radius.sm
- Shimmer animation: linear gradient slides left→right, 1.5s duration, repeating
- Preserve card structure (padding, borders) but replace content with skeleton blocks
- Match approximate content layout: title block (60% width), subtitle block (80%), body blocks (100% in 2-3 lines)

**Empty state:**
- Center-aligned within card padding
- Icon: 48px, text-tertiary, accent-muted background circle (56px)
- Title: heading-medium, text-secondary
- Description: body-small, text-tertiary, max-width 280px
- Optional action: Ghost button below description

---

### 2.4 Dialogs and Sheets

**Dialog:**
| Property | Value |
|----------|-------|
| Background | bg-surface |
| Border | 1px border-default |
| Radius | Radius.lg (14px) all corners |
| Padding | Space.xl (24px) |
| Min width | 320px |
| Max width | 480px |
| Backdrop | modal surface (blur 8px dark mode / dim light mode) |

**Dialog structure:**
1. Title: heading-medium, text-primary, Space.md bottom margin (no icon by default)
2. Body: body-medium, text-secondary, scrollable if > 320px height, Space.lg bottom margin
3. Actions: row, right-aligned, Space.sm gap between buttons. Primary action rightmost
4. Close button: × icon button, top-right corner, Ghost variant

**Animations:**
- Open: fade-in backdrop (150ms) + scale(0.92→1.0) dialog, 300ms spring curve
- Close: fade-out (150ms) + scale(1.0→0.92), 200ms ease-in

**Bottom Sheet:**
| Property | Value |
|----------|-------|
| Background | bg-surface |
| Border | 1px border-default |
| Radius | Radius.lg top corners only |
| Padding | Space.xl (24px) |
| Max height | 85vh |
| Handle | 4px × 32px bar, bg: border-default, centered, 8px from top |
| Backdrop | Same as dialog |

**Sheet animations:**
- Open: slide-up from bottom, 300ms ease-out
- Close: slide-down, 200ms ease-in
- Drag handle responds to gesture, velocity > threshold dismisses

---

### 2.5 Message Bubbles

**Assistant bubble:**
| Property | Value |
|----------|-------|
| Background | bg-surface |
| Border | 1px border-subtle |
| Radius | top: Radius.xl (20px), bottom: Radius.sm (6px) |
| Max width | 85% of parent |
| Padding | Space.md (12px) horizontal, Space.sm (8px) vertical |
| Text | body-large, text-primary, Inter |
| Alignment | Left |

**User bubble:**
| Property | Value |
|----------|-------|
| Background | accent-muted (dark) / accent (light) |
| Border | None |
| Radius | top: Radius.xl (20px), bottom: Radius.sm (6px) |
| Max width | 85% of parent |
| Padding | Space.md (12px) horizontal, Space.sm (8px) vertical |
| Text | text-primary (dark) / text-inverse (light), Inter |
| Alignment | Right |

**Streaming bubble:**
Same as Assistant bubble + animated cursor (1.5px wide, accent color, 16px height, blink 1s cycle) at end of text.

**Code blocks within messages:**
- bg-elevated background, border-subtle, Radius.md
- Fira Code mono-medium, Space.md padding
- Copy button: Ghost, top-right corner, icon only
- Scrollable horizontally, max-height 300px

**Timestamps:**
- Below bubble, caption font, text-tertiary
- Right-aligned for user, left-aligned for assistant
- Format: relative ("2m ago") → absolute on tap

---

### 2.6 Tool Calls

**Tool card (inline in chat):**
| Property | Value |
|----------|-------|
| Background | bg-field |
| Border | 1px border-subtle, left 3px status-colored |
| Radius | Radius.md (10px) |
| Padding | Space.sm (8px) |
| Spacing | 4px between rows |

**Tool name row:**
- Icon: 14px (wrench for tools, globe for web, terminal for shell)
- Tool name: mono-medium, text-primary
- Duration: caption, text-tertiary, right-aligned

**Args preview row:**
- 2 lines max, overflow: ellipsis
- mono-small, text-secondary
- Expand chevron on far right: AnimatedRotation 180°

**Expanded args:**
- Full JSON block: mono-small, text-secondary, bg-canvas inset, Radius.sm, scrollable
- Slides open 200ms ease-out

**Status transitions:**
| Status | Left border | Icon | Arg block state |
|--------|-------------|------|-----------------|
| pending | accent | spinner (16px) | collapsed |
| running | accent | spinner (16px) | collapsed |
| completed | success | check (16px) | expandable |
| failed | error | × (16px) | auto-expanded |

**Tool result card:**
| Property | Value |
|----------|-------|
| Background | bg-field |
| Border | 1px border-subtle, left 3px status-colored |
| Radius | Radius.md |
| Padding | Space.sm (8px) |
| Content | body-small, text-secondary, max-height 200px scrollable |
| Header | "Result" caption, text-tertiary, duration right-aligned |

---

### 2.7 Status Chips and Badges

**Status badge (inline):**
| Status | Background | Text | Dot |
|--------|------------|------|-----|
| Success | success @ 12% opacity | success | success (8px) |
| Warning | warning @ 12% opacity | warning | warning (8px) |
| Error | error @ 12% opacity | error | error (8px) |
| Info/Neutral | info @ 12% opacity | info | info (8px) |

**Properties:**
- Height: 22px, Radius: Radius.sm (6px)
- Padding: Space.xs (4px) horizontal
- Font: caption
- Dot: 8px circle, 4px gap before label

**Chip (actionable filter/tag):**
| State | Background | Border | Text |
|-------|------------|--------|------|
| Default | bg-field | 1px border-subtle | text-secondary |
| Selected | accent-muted | 1px accent | text-primary |
| Hover | bg-elevated | 1px border-default | text-primary |

**Properties:**
- Height: 28px, Radius: Radius.md (10px)
- Padding: Space.sm (8px) horizontal
- Font: body-small
- Dismiss (×) icon: 12px, right, only on selected state
- Select animation: 150ms ease-out

---

### 2.8 Sidebar (Desktop)

**Structure:**
- Background: bg-canvas (full height, screen edge to edge)
- Width: 240px fixed at ≥1024px, 64px (rail mode) at 768-1023px
- No right border — uses negative space to separate from content
- User avatar area: top, 48px avatar, heading-medium name, caption email below
- Workspace list: scrolling, ghost-style items
- Bottom section: settings icon, theme toggle, companion status

**Workspace item (240px mode):**
| State | Background | Text | Left border |
|-------|------------|------|-------------|
| Default | transparent | text-secondary | none |
| Hover | bg-elevated | text-primary | none |
| Active | bg-elevated | text-primary | 2px accent (left edge) |

**Properties:**
- Height: 40px, Radius: Radius.md, padding: Space.md horizontal
- Icon: 20px, text-secondary → text-primary on active
- Label: body-medium
- Unread dot: 6px accent circle, right-aligned, only when count > 0
- Context menu: right-click or long-press, positioned at cursor

**Rail mode (64px, 768-1023px):**
- No labels, icons only (24px, centered)
- Active indicator: 2px accent left border + bg-elevated
- Tooltip on hover showing workspace name
- Expand button at bottom to temporarily widen to 240px overlay

---

### 2.9 Bottom Navigation (Mobile, <768px)

| Property | Value |
|----------|-------|
| Background | bg-surface |
| Border | 1px border-subtle (top edge only) |
| Height | 64px + safe area |
| Items | 4 max |

**Item states:**
| State | Icon | Label |
|-------|------|-------|
| Active | accent color, 24px | caption, accent, shown |
| Inactive | text-tertiary, 24px | caption, text-tertiary, shown |

**Badge:** 16px circle, error or accent background, caption font, white text, top-right of icon.

---

## 3. Responsive Layout

### 3.1 Breakpoint System

| Name | Width | Layout | Sidebar |
|------|-------|--------|---------|
| Desktop | ≥ 1024px | 3-column (sidebar + chat + content) | 240px expanded |
| Tablet | 768 — 1023px | 3-column (rail + chat + content) | 64px rail |
| Mobile | < 768px | Single column stack + bottom nav | Hidden (replaced by bottom nav) |

**Breakpoint detection:** Single `LayoutBuilder` in `ResponsiveShell`, no per-screen `MediaQuery` calls. All screens receive a `LayoutMode` enum value (desktop / tablet / mobile) via provider or inherited widget.

**Gap closure:** The previous 768-1023 gap where devices fell through to MobileLayout is replaced with the Tablet rail mode.

---

### 3.2 Desktop Layout (≥ 1024px)

```
┌──────────┬──────────────────────────────────────────────┐
│ Sidebar  │ Chat Panel               │ Content Panel     │
│ 240px    │ min 40%, flex            │ min 320px, flex   │
│          │                           │                   │
│ Avatar   │ ┌─ Tab bar ────────────┐  │ Routed child:     │
│ Search   │ │ ws1 ws2 ws3 + new    │  │ Workspace Panel   │
│          │ └──────────────────────┘  │ Email Screen      │
│ Workspace│                           │ Settings          │
│ list     │ Message list              │                   │
│ (scroll) │ (scrollable)              │                   │
│          │                           │                   │
│ Settings │ Chat input                │                   │
│ Theme    │ (fixed bottom)            │                   │
└──────────┴──────────────────────────────────────────────┘
```

**Split rules:**
- Sidebar: 240px fixed, never resizes. bg-canvas full-height
- Chat panel: `flex` remaining space, min-width 400px. When content panel is hidden (no route), chat takes 100% of remaining
- Content panel: `flex`, min-width 320px, max-width 560px
- Divider between sidebar/chat: 1px border-subtle on sidebar right edge
- Divider between chat/content: 1px border-subtle on content panel left edge
- Panel resizing: User can drag the chat/content divider to resize. Minimum chat 280px, minimum content 200px

**Content panel states:**
| Route Active | Content Panel Behavior |
|-------------|----------------------|
| `/workspace` | Shows workspace panel (files/skills/subagents) |
| `/email` | Shows email list |
| `/tasks` | Placeholder for now |
| `/contacts` | Placeholder for now |
| No route / `/chat` | Hidden — chat panel takes 100% |

---

### 3.3 Tablet Layout (768 — 1023px)

```
┌──────┬──────────────────────────────────────────┐
│ Rail │ Chat Panel              │ Content Panel  │
│ 64px │ min 320px, flex         │ min 280px      │
│      │                         │                │
│ Icons│ Tab bar (compact)       │ Routed child    │
│ only │ Message list            │                 │
│      │                         │                 │
│      │ Chat input              │                 │
└──────┴──────────────────────────────────────────┘
```

**Changes from desktop:**
- Sidebar → Rail: 64px wide, icons only (24px), no labels. Active indicator: 2px accent left border
- Chat panel min-width drops from 400px → 320px
- Content panel min-width drops from 320px → 280px
- Workspace names shown in tooltip on hover (300ms delay)
- Rail expand button at bottom: temporary 240px overlay on long-press
- Tab bar font: body-small (was body-medium on desktop)

---

### 3.4 Mobile Layout (< 768px)

```
┌────────────────────┐
│ App Bar            │  — Workspace name + avatar
├────────────────────┤
│                    │
│ Current screen     │  — Full width, single stack
│ (chat / workspace  │
│  / email / etc.)   │
│                    │
├────────────────────┤
│ Bottom Nav         │  — Home, Email, Tasks, More
└────────────────────┘
```

**Structure:**
- App bar: 56px, bg-canvas, border-subtle bottom border. Workspace name (heading-medium), right: companion pulse + avatar
- Screen body: full remaining height
- Chat input: fixed bottom, above nav bar, collapses to 40px when not focused
- Bottom nav: 4 items, 64px + safe area
- Workspace switcher: bottom sheet triggered from app bar title tap
- Settings: gear icon in app bar → pushes settings screen
- Content panels (files/skills/subagents): bottom sheet overlay, not side panel

**Mobile-specific adaptations:**
| Screen | Behavior |
|--------|----------|
| Chat | Full screen, no side panels. Tool calls collapse by default |
| Workspace panel | Full screen. Tabs (Files/Skills/Subagents) as horizontal scroll or segmented control |
| Email | Full screen. Pull-to-refresh, swipe actions |
| Settings | Full screen pushed onto nav stack |
| Subagent dialogs | Full-width bottom sheets instead of dialogs |
| Message bubbles | 92% width (was 85% on desktop) |

---

### 3.5 Responsive Behavior Summary

| Element | Desktop (≥1024) | Tablet (768-1023) | Mobile (<768) |
|---------|-----------------|-------------------|---------------|
| Sidebar | 240px, full labels | 64px rail, icons only | Hidden |
| Navigation | Sidebar workspace list | Rail + tooltips | Bottom nav bar |
| Chat width | 40-60% of remaining | 50-70% of remaining | 100% |
| Content panel | 320-560px side panel | 280-400px side panel | Bottom sheet or pushed screen |
| Dialogs | Centered modal, 480px max | Centered modal, 400px max | Full-width bottom sheet |
| Cards | 2-3 column grid | 1-2 column grid | Single column |
| Message bubble | 85% width | 88% width | 92% width |
| Font scale | Default | Default | Default (no scaling) |
| Tool cards | Expanded by default | Collapsed, tap to expand | Collapsed, tap to expand |
| Workspace tabs | Inline in content panel | Inline in content panel | Segmented control |
| Subagent panel | Side content panel | Side content panel | Full screen |
| Email list | Side content panel | Side content panel | Full screen |
| Settings | Content panel or dialog | Content panel or dialog | Full screen push |

---

## 4. File Structure

### Theme layer (6 files)

```
lib/theme/
  tokens/
    colors.dart        — Color tokens with dark/light/high-contrast maps
    typography.dart    — Inter + Fira Code scale, TextTheme factory
    spacing.dart       — Spacing constants + EdgeInsets presets
    radius.dart        — Radius constants + BorderRadius presets
    motion.dart        — Duration + Curve constants, transition helpers
  app_theme.dart       — ThemeData factory (builds from tokens), ThemeMode enum,
                          barrel export for tokens/
```

### Component library (8 files)

```
lib/widgets/
  ea_button.dart       — EaPrimaryButton, EaSecondaryButton, EaGhostButton
  ea_input.dart        — EaTextField, EaSearchField, EaDropdownField
  ea_card.dart         — EaCard (static, hoverable, interactive variants)
  ea_dialog.dart       — EaDialog (showEaDialog helper with backdrop)
  ea_sheet.dart        — EaBottomSheet (showEaSheet helper)
  ea_chip.dart         — EaChip, EaStatusChip (color-coded)
  ea_avatar.dart       — EaAvatar (initials, image, status dot)
  ea_divider.dart      — EaDivider (subtle, accent variants)
```

### Screens (refactored, split where needed)

```
lib/features/
  chat/
    chat_screen.dart
    widgets/
      message_bubble.dart
      streaming_bubble.dart
      reasoning_bubble.dart
      tool_call_card.dart
      chat_input.dart
      approval_bar.dart        — (extracted from chat_input.dart)
      connection_banner.dart
      error_bar.dart
  workspace/
    workspace_panel.dart
    widgets/
      files_panel.dart
      skills_panel.dart
      subagents/
        subagents_panel.dart     — main panel (reduced from 1316 lines)
        create_dialog.dart       — extracted
        edit_dialog.dart         — extracted
        start_dialog.dart        — extracted
        detail_sheet.dart        — extracted
        instruct_dialog.dart     — extracted
        job_card.dart            — extracted
  home/
    home_screen.dart
    widgets/
      smart_greeting.dart
      status_cards.dart
      quick_actions.dart
  email/
    email_list_screen.dart
  settings/
    settings_screen.dart
  companion/
    companion_feed.dart
    widget/
      companion_pulse.dart
      companion_toast.dart
```

### Layout (unchanged structure, retouched)

```
lib/core/layout/
  desktop_layout.dart
  mobile_layout.dart
  responsive_shell.dart
```

---

## 5. Migration Plan

### Phase 1: Foundation

1. Add Fira Code as asset (`pubspec.yaml`)
2. Replace `lib/theme/` with new token system
3. Build `lib/widgets/` component library
4. Delete old `ea_widgets.dart`, old theme files
5. Fix all 37 analyzer issues

### Phase 2: Shell and Navigation

1. Retouch `responsive_shell.dart` with new theme
2. Retouch `desktop_layout.dart` (sidebar styling, chat/content panels)
3. Retouch `mobile_layout.dart` (bottom nav)
4. Wire up page transitions (sideways slide, fade-through)

### Phase 3: Screens (most visible first)

1. Chat screen + all chat widgets (message bubbles, tool cards, input)
2. Workspace panel + subagent dialogs (split 1316-line file)
3. Settings screen (migrate from RadioListTile)
4. Email screen
5. Home screen
6. Companion feed

### Phase 4: Polish

1. Staggered list animations everywhere
2. Press-scale micro-interactions on all interactive elements
3. Responsive gap fix (768-1023)
4. Final analyzer pass, remove all TODOs
5. Dark/light mode toggle persistence
