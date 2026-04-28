# Executive Assistant — Flutter UI/UX Plan

> Design system, navigation architecture, and screen specifications for the Flutter frontend.
> Inspired by Wise's design philosophy: **Clarity, Context, Conviction.**

---

## Design Philosophy

Three principles adapted from Wise:

| Wise Principle | Our Translation |
|---|---|
| **Fee before you commit** | Show what the agent will do before it acts. Which tools, estimated cost, time. |
| **Trust through transparency** | Every tool call visible in real-time. Show reasoning. Show confidence. Never hide what the agent is doing. |
| **Progressive disclosure** | Simple path first. Chat is the hero. Files, email, todos are one tap deeper. Settings are two taps. |

---

## Color System

### Palette

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#FFFFFF` | Screen background. Wise is 60%+ white. |
| Surface | `#F5F5F7` | Cards, sections, elevated surfaces |
| Primary | `#1A1A2E` | Text, nav active state, headers |
| Accent | `#0D9488` | CTAs, active indicators, links, success highlights |
| Accent hover | `#0F766E` | Pressed/active accent state |
| Success | `#22C55E` | Connected status, confirmed actions |
| Warning | `#F59E0B` | Needs attention, pending approvals |
| Danger | `#EF4444` | Destructive actions, errors, disconnect |
| Text primary | `#111827` | Headlines, body text |
| Text secondary | `#6B7280` | Subtitles, descriptions |
| Text dim | `#9CA3AF` | Timestamps, muted labels |

### Why Teal

- **Purple** (`#7C3AED`) — every AI app uses it (Copilot, Gemini, Notion AI). Invisible branding.
- **Lime** (`#9FE870`) — Wise's signature. Using it looks derivative.
- **Teal** (`#0D9488`) — professional, distinctive, pairs cleanly with navy. Says "trusted assistant" not "trendy AI" or "fintech clone".

### Accent Rules

Accent appears **only** on:
- CTA buttons (Approve, Send, Save)
- Active tab indicator
- Success checkmarks and connection dots
- Links and interactive text

Everywhere else is neutral. This restraint is what makes Wise feel fluid.

---

## Typography

Inter only. One font family, four sizes, two weights. No JetBrains Mono — tool calls use Inter Medium with a chip background instead.

| Role | Size | Weight | Letter Spacing |
|------|------|--------|----------------|
| Screen title | 30px | SemiBold | -2.5% |
| Section title | 22px | SemiBold | -1.5% |
| Body | 14px | Regular | 0% |
| Caption/timestamp | 12px | Regular | +1% |
| Tool call label | 13px | Medium | 0% |
| Key metric | 24px | Bold | -1% |

Negative letter-spacing on titles creates a tight, premium feel (this is what Wise does).

---

## Spacing & Layout

| Token | Value | Usage |
|-------|-------|-------|
| Screen edge | 24px | Mobile left/right padding |
| Between sections | 32px | Major screen section breaks |
| Between cards | 12px | Horizontal gap between cards |
| Card padding | 16px | Internal card padding |
| Component default | 16px | Default spacing between components |
| Text to component | 16px | After a text block, before next component |

---

## Border Radius

Wise's single biggest visual differentiator. Generous curves communicate friendliness.

| Component | Radius (mobile) | Radius (desktop) |
|-----------|-----------------|-------------------|
| Cards | 24px | 32px |
| Buttons | 16px | 16px |
| Chips/pills | 12px | 12px |
| Bottom sheets | 24px (top corners) | 24px |
| Input fields | 12px | 12px |
| Dialogs | 24px | 28px |

---

## Motion

Natural, quick, purposeful — not decorative. This is Wise's motion philosophy.

| Transition | Duration | Curve |
|-----------|----------|-------|
| Tool call expand/collapse | 200ms | easeOut |
| Smart greeting collapse | 300ms | easeOut |
| Screen push (mobile) | 300ms | CupertinoPageRoute |
| Screen replace (desktop) | 200ms | FadeTransition |
| Success celebration | 400ms | easeInOut |

**Reserve animation only for:**
- State transitions (loading → content, empty → populated)
- Success celebrations (task completed, email sent)
- Sheet presentation/dismissal

No bouncing, shimmer on loading, parallax, or decorative micro-interactions. Wise is calm.

---

## Navigation Architecture

### Desktop (>1024px): Three-Panel Layout

```
┌──────────┬──────────────────────────┬─────────────────────┐
│ Sidebar  │     Main Content         │   Chat Panel        │
│ (240px)  │                          │   (360px, resizable)│
│          │                          │                     │
│ ● Home   │  [selected tab content]  │  Smart greeting     │
│ ● Files  │                          │                     │
│ ● Email  │  Depends on active tab:  │  ┌─ You ──────┐    │
│ ● Todos  │  Home → dashboard cards  │  │ Draft reply │    │
│ ● Contacts│ Email → email list      │  └─────────────┘    │
│ ● Skills │  Todos → task groups     │                     │
│ ● Subagents│ Files → file browser  │  ┌─ Assistant ─┐   │
│ ● Memory │  Contacts → list        │  │ I'll find...│    │
│          │  Skills → registry       │  └─────────────┘    │
│ ──────── │  Subagents → status      │                     │
│ ⚙ Settings│ Memory → profile view   │                     │
│          │                          │  [📎] Ask... [➤]   │
└──────────┴──────────────────────────┴─────────────────────┘
```

**Key principles:**
- **Chat panel always visible on right** — never hidden, never a separate tab. Users interact with content (left/center) while directing the agent (right) simultaneously. VS Code + Copilot Chat model.
- **Main content changes per sidebar tab.** Agent tool calls update the active view (e.g., typing "show Sarah's emails" navigates to Email tab with Sarah filter).
- **Sidebar collapses to icon-only (48px) on medium screens.**
- **Settings at bottom of sidebar**, separated by divider.
- **Bidirectional**: Chat drives content panel, clicking content can pre-fill chat context.

### Mobile (<1024px): 4 Bottom Tabs + Sheet-Based Detail

```
┌─────────────────────────────────────┐
│  Home  │  Email  │  Tasks  │  More  │
└─────────────────────────────────────┘
```

| Tab | Content | Why it deserves a tab |
|-----|---------|----------------------|
| **Home** | Dashboard cards + full chat | Primary interface. Executives talk to their assistant. |
| **Email** | Email list → tap for thread | Second most critical on-the-go need. |
| **Tasks** | Tasks grouped by priority/date | Third most critical. Quick "what's due today." |
| **More** | Contacts, Files, Skills, Subagents, Memory, Settings | Everything else. Used <10% on mobile. |

**More tab layout:**

```
┌─────────────────────────────────────┐
│  More                               │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────────────────────┐    │
│  │ 👤 Contacts                 │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 📁 Files         ⟁ Remote  │    │  ← "Remote" badge (self-hosted mode)
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🧠 Skills                  │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🤖 Subagents     ● 2 active│    │  ← Live status badge
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🧬 Memory                  │    │
│  └─────────────────────────────┘    │
│  ─────────────────────────────     │
│  ┌─────────────────────────────┐    │
│  │ ⚙️ Settings                 │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### Mobile Home Tab = Dashboard + Chat Combined

```
┌─────────────────────────────────────┐
│  Good morning, Eddy          [avatar]│
├─────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐        │  ← Status cards (horizontal scroll,
│  │ 📧 3 │ │ ✅ 2 │ │ 🤖 1│        │     24px radius, Wise balance-card pattern)
│  │unread│ │  due │ │active│        │
│  └──────┘ └──────┘ └──────┘        │
│                                     │
│  ── Quick Actions ─────────────     │
│  [Draft reply] [Summarize] [Schedule]
│                                     │
│  ── Today ─────────────────────     │  ← Recent conversation / activity
│  You: Draft a reply to Sarah       │
│  Assistant: I've found 3 emails... │
│  ─────────────────────────────     │
│  You: Schedule lunch with Mike     │
│  Assistant: Done. Friday 12pm.    │
│                                     │
├─────────────────────────────────────┤
│  [📎]  Ask anything...       [➤]   │  ← Chat input always visible
├─────────────────────────────────────┤
│  Home  │  Email  │  Tasks  │  More  │
└─────────────────────────────────────┘
```

When the user starts typing or taps a conversation, it pushes to a **full-screen chat view** with back navigation.

### Cross-Tab Agent Access (Mobile)

On Email and Tasks tabs, a **floating action button** (FAB, bottom-right) provides contextual agent access:

- **Email tab**: `[💬]` → bottom sheet: "Ask about your emails..." Agent can filter/update email list in real-time.
- **Tasks tab**: `[💬]` → bottom sheet: "Add or update tasks..." Agent can create/complete tasks directly.

### Tablet (768–1024px): Hybrid Layout

- Sidebar collapses to icon-only (48px)
- Main content fills center
- Chat panel slides in/out from right (toggle button in app bar)

---

## Screen Specifications

### 1. Chat Flow (Pushed from Home or Standalone)

When user taps a conversation or starts typing on Home, push to full-screen chat:

```
┌──────────────────────────────────────┐
│  ← Back          Executive Assistant │
├──────────────────────────────────────┤
│                                      │
│  You: Draft a reply to Sarah         │
│                                      │
│  Assistant:                          │
│  I'll search your emails...          │
│                                      │
│  ┌─ email_search ────────────────┐  │  ← Collapsible tool card
│  │  query: "Sarah"               │  │     (Wise fee breakdown pattern:
│  │  ✓ Found 3 emails             │  │      tap to expand args/result)
│  └────────────────────────────────┘  │
│                                      │
│  Here's the draft:                   │
│  ┌────────────────────────────────┐  │
│  │ Hi Sarah,                      │  │  ← Editable draft card
│  │ I've reviewed the Q3 numbers.. │  │     (Wise "edit before send")
│  └────────────────────────────────┘  │
│  [Send]  [Edit]  [Discard]          │
│                                      │
├──────────────────────────────────────┤
│  [📎]  Message...            [➤]   │
└──────────────────────────────────────┘
```

### 2. HITL Approval Sheet (Full-Screen Bottom Sheet)

Destructive actions get a dramatic, unmissable confirmation. This is the Wise "Confirm Transfer" pattern.

```
┌──────────────────────────────────────┐
│  ⚠️ Approve Action                   │
├──────────────────────────────────────┤
│                                      │
│  The assistant wants to:              │
│                                      │
│  ┌──────────────────────────────────┐│
│  │ 📧 email_send                   ││  ← Tool icon + name (immediate clarity)
│  │                                  ││
│  │ To: sarah@company.com            ││  ← Key args highlighted
│  │ Subject: Re: Q3 Budget           ││     (Wise shows recipient + amount
│  │                                  ││      prominently)
│  │ [View full args ▾]              ││  ← Progressive disclosure
│  │   body: "Hi Sarah, I've..."      ││
│  │   attachments: []                ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌── Risk Level ──────────────────┐ │
│  │ ⚠️  This will send an email    │ │  ← Destructive = amber warning
│  │    that cannot be undone.       │ │     (Wise shows exchange rate risk)
│  └─────────────────────────────────┘ │
│                                      │
│  ┌─ Edit Before Approving ─────────┐ │
│  │                                  │ │
│  │ To: sarah@company.com            │ │  ← EDITABLE fields
│  │ Subject: [editable]             │ │     (Wise "edit transfer details")
│  │ Body: [editable]                 │ │
│  └──────────────────────────────────┘ │
│                                      │
├──────────────────────────────────────┤
│   [❌ Reject]          [✅ Approve]   │  ← Two clear buttons, Wise pattern
└──────────────────────────────────────┘
```

### 3. Email Screen

```
┌──────────────────────────────────────┐
│  📧 Email              [🔄] [⚙️]    │
├──────────────────────────────────────┤
│  ┌─ Connected Accounts ──────────┐  │
│  │  Gmail • sarah@company.com 🟢 │  │  ← Connection status (Wise's
│  │  Outlook • john@outlook.com 🟢│  │     connected bank accounts)
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ Today ──────────────────────┐   │
│  │  🔴 Sarah Miller              │   │  ← Unread = red dot
│  │     Re: Q3 Budget Review      │   │
│  │     10:32 AM                  │   │
│  │                               │   │
│  │  🔴 David Chen                │   │
│  │     Project X deadline update │   │
│  │     9:15 AM                   │   │
│  │                               │   │
│  │     Mike Johnson               │   │  ← Read = no dot
│  │     Lunch Friday?              │   │
│  │     Yesterday                  │   │
│  └───────────────────────────────┘   │
│                                      │
│  Pull to refresh...                   │
│                           [💬]       │  ← FAB for contextual agent
└──────────────────────────────────────┘
```

Wise translations:
- **Connected accounts** = Wise's "linked bank accounts" (green dot = connected, red = disconnected)
- **Email list** = Wise's transaction list (grouped by date, relevance indicators)
- **Pull to refresh** = Wise's pull-to-refresh on transfer list

### 4. Tasks Screen

```
┌──────────────────────────────────────┐
│  ✅ Tasks                            │
├──────────────────────────────────────┤
│  ┌─ Today ──────────────────────┐  │
│  │  🔴 Review Q3 budget          │  │  ← Priority dots (red=high, amber=med)
│  │  🟡 Call accountant            │  │
│  │  🟢 Book flight to London      │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ This Week ──────────────────┐  │
│  │  🟡 Prepare board deck         │  │
│  │  🟢 Renew passport             │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ Completed ──────────────────┐   │
│  │  ✓ Send contract to David    │   │  ← Strikethrough, muted text
│  │  ✓ Schedule team sync         │   │
│  └────────────────────────────────┘  │
│                                      │
│  [+ Add Task]                        │
│                           [💬]       │  ← FAB for contextual agent
└──────────────────────────────────────┘
```

Wise translation: Scheduled payments screen — grouped by time, clear status indicators. Completed items visible but subdued.

### 5. Profile / Memory Screen

```
┌──────────────────────────────────────┐
│  👤 Your Profile                     │
├──────────────────────────────────────┤
│  ┌─ What I Know About You ──────┐  │
│  │                                │  │
│  │  🏢 Work                       │  │  ← Grouped by domain (Wise's
│  │     Prefers dark mode          │  │     currency accounts)
│  │     Works in PST timezone      │  │
│  │     Uses Notion for notes      │  │
│  │                                │  │
│  │  📧 Communication              │  │
│  │     Prefers short emails       │  │
│  │     Formal tone with clients   │  │
│  │                                │  │
│  │  🔒 Private                    │  │  ← Explicit privacy indicators
│  │     Birthday: Dec 15           │  │     (Wise: fee transparency; we: data
│  │     Home address: [hidden]      │  │      transparency)
│  │                                │  │
│  └────────────────────────────────┘  │
│                                      │
│  [✏️ Edit] [🔍 Search memories]      │
│                                      │
│  ┌─ Confidence ─────────────────┐  │
│  │  ★★★☆☆ Prefers dark mode     │  │  ← Confidence stars (Wise's
│  │  ★★☆☆☆ Birthday Dec 15       │  │     transfer status badges)
│  │  ★★★★★ email: sarah@...      │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ Insights ───────────────────┐   │
│  │  "You tend to prioritize      │   │  ← AI-generated insights
│  │   urgent over important"      │   │     (Wise's market insights)
│  │                                │   │
│  │  [Dismiss] [Keep]             │   │  ← User can accept or reject
│  └────────────────────────────────┘  │
│                                      │
│  ────────────────────────────────    │
│  ⚙️ Settings                         │  ← Settings inside Profile
│  ┌────────────────────────────────┐ │
│  │ Connection: localhost:8080 🟢  │ │
│  │ Model: minimax-m2.5           │ │
│  │ Cost this session: $0.04      │ │
│  │                                │ │
│  │ Privacy                        │ │
│  │  Data stored locally ✓         │ │
│  │  Memory: On [Toggle]           │ │
│  │  Auto-approve: Read-only tools │ │
│  │                                │ │
│  │ Danger Zone                    │ │
│  │  [Clear conversation]          │ │
│  │  [Reset all memory]            │ │
│  │  [Disconnect all accounts]     │ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 6. Files Screen (Desktop Sidebar, Mobile More Tab)

```
┌──────────────────────────────────────┐
│  📁 Files                 ⟁ Remote │  ← Badge indicating server files
├──────────────────────────────────────┤
│  🔍 Search files...                  │
│                                      │
│  ┌─ Project X ──────────────────┐   │
│  │  📄 budget_q3.xlsx             │   │
│  │  📄 notes_meeting.md           │   │
│  │  📁 contracts/                  │   │
│  └────────────────────────────────┘   │
│                                      │
│  ┌─ Personal ──────────────────┐    │
│  │  📄 vacation_plans.txt         │   │
│  │  📄 tax_2025.pdf               │   │
│  └────────────────────────────────┘   │
│                                      │
│  Last synced: 2 min ago              │  ← Connectivity awareness
└──────────────────────────────────────┘
```

### 7. Subagents Screen (Desktop Sidebar, Mobile More Tab)

```
┌──────────────────────────────────────┐
│  🤖 Subagents               ● 2 active
├──────────────────────────────────────┤
│  ┌─ Researcher ──────────────────┐  │
│  │  Status: ● Running             │  │
│  │  Task: "Deep dive on Q3 market" │  │
│  │  Progress: ████████░░ 80%      │  │  ← Progress bar (Wise's transfer progress)
│  │  Cost: $0.02                    │  │
│  │                                │  │
│  │  [Instruct] [Cancel]           │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ Writer ─────────────────────┐  │
│  │  Status: ● Running             │  │
│  │  Task: "Draft board deck slides"│ │
│  │  Progress: ███░░░░░░ 30%      │  │
│  │  Cost: $0.01                    │  │
│  │                                │  │
│  │  [Instruct] [Cancel]           │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌─ Completed ──────────────────┐   │
│  │  ✓ Analyst — finished 1h ago  │   │
│  └────────────────────────────────┘  │
│                                      │
│  [+ New Subagent]                    │
└──────────────────────────────────────┘
```

### 8. Skills Screen (Desktop Sidebar, Mobile More Tab)

```
┌──────────────────────────────────────┐
│  🧠 Skills                           │
├──────────────────────────────────────┤
│  ┌─ Active ─────────────────────┐   │
│  │  🔬 deep-research             │   │  ← Tap to see full description
│  │     Deep research and analysis │   │
│  │     Loaded 2h ago              │   │
│  └────────────────────────────────┘   │
│                                      │
│  ┌─ Available ──────────────────┐   │
│  │  📋 planning-with-files       │   │
│  │     Multi-step task planning   │   │
│  │                                │   │
│  │  🔧 skill-creator              │   │
│  │     Create and improve skills  │   │
│  │                                │   │
│  │  🤖 subagent-manager           │   │
│  │     Create and manage subagents │   │
│  └────────────────────────────────┘   │
│                                      │
│  [🔍 Search skills...]               │
└──────────────────────────────────────┘
```

---

## Component Patterns

| Pattern | Wise Reference | Our Implementation |
|---|---|---|
| **Status indicator** | Green/amber/red dot next to balance | Green/amber/red dot next to connection status |
| **Card with disclosure** | Transfer amount → tap for fee breakdown | Tool call → tap for args/result |
| **Confirmation sheet** | "You're sending £X to Y — Confirm?" | "Send email to X about Y — Approve?" |
| **Progressive disclosure** | "Fee breakdown ▾" | "Show full args ▾" |
| **Grouped list** | Transactions grouped by date | Emails/tasks grouped by date/priority |
| **Action button** | Green "Confirm Transfer" with amount | Accent "Approve" with tool name |
| **Cancel/Destruct** | Gray "Cancel" secondary button | Gray "Reject" secondary button |
| **Pull to refresh** | Transfer list refresh | Email/task list refresh |
| **Error state** | "Transfer failed" with reason | "Action failed" with error + retry |
| **Empty state** | "No transactions yet" with CTA | "No emails — connect an account" with CTA |
| **Remote badge** | N/A | "⟁ Remote" on Files/Subagents (self-hosted) |
| **Sync status** | "Last updated 2m ago" on balances | "Last synced 2m ago" / "Offline — cached 10:32 AM" |

---

## Key UX Decisions

### 1. Chat is the Hero
Wise puts "Send Money" front and center. Our equivalent: the chat input. Always visible, always one tap away. On desktop, it's a permanent right panel. On mobile, it's the Home tab. The executive talks to their assistant — they don't browse it.

### 2. Show the Plan Before Acting
Before a destructive action, the approval sheet shows:
- What tool will be called
- Key arguments (recipient, subject, body)
- Risk level (read-only / destructive / irreversible)
- An "Edit before approving" section

This is the Wise "fee before you commit" principle. The "fee" is what the agent is about to do.

### 3. Tool Calls Are Inline, Not Hidden
Collapsed by default, expandable on tap. Like Wise shows the exchange rate and fee in the transfer flow. The user can always see what the agent is doing.

### 4. Smart Greeting = Wise Balance Summary
First thing on Home: status cards showing what needs attention NOW. Not chat history, not settings. The executive's "balance."

### 5. Editable Drafts = Wise "Edit Transfer Details"
When the agent drafts an email, the draft is EDITABLE. Never auto-send destructive actions.

### 6. Cost Transparency = Wise Transparent Fees
Settings shows "Cost this session: $0.04." Approval sheet shows "Estimated tokens: ~2,000."

### 7. Privacy-First Memory = Wise Data Protection
Memory profile shows what the agent knows, grouped by domain, with confidence indicators. Private info shown as "[hidden]" by default.

### 8. Desktop Side Panel for Chat, Not Separate Tab
On desktop, the agent is always beside you. Like VS Code's Copilot Chat. You don't switch away from your work to talk to the assistant — you talk while looking at your files/emails/tasks.

### 9. Mobile Tabs for Context, FAB for Agent
On mobile, the 4 tabs give context (Home/Dashboard, Email, Tasks, More). The FAB on Email/Tabs tabs provides contextual agent access. On Home, the chat input is always visible at the bottom.

### 10. Self-Hosted Awareness
In self-hosted mode, files and subagents are on a remote device. The UI shows "⟁ Remote" badges on Files, Subagents, and Skills. Lists show "Last synced: X min ago" or "Offline — cached from 10:32 AM." Queued messages send when reconnected (already implemented in WsClient).

---

## What We're NOT Building (Phase 1 Scope)

| Out of Scope | Why |
|---|---|
| Dark mode | Phase 2 — nail light mode first |
| Voice input/output | Phase 2 — complexity |
| Push notifications | Requires APNS/FCM — Phase 2 |
| Multi-language | Phase 2 |
| Tablet-specific layout | Phase 2 — responsive phone first, desktop second |
| Onboarding wizard | Settings inside Profile tab is enough for MVP |
| Illustrations | Phase 2 — icons only for now |
| Dashboard analytics | Phase 2 — status cards first |

---

## Implementation Priority

| Priority | What | Why |
|----------|------|-----|
| **P0** | Design system (`app_theme.dart`) | Everything depends on this |
| **P0** | Responsive layout shell (sidebar + tabs + chat panel) | Core architecture |
| **P0** | Home tab with smart greeting + chat | The 80% screen |
| **P0** | HITL approval sheet (full-screen) | Safety-critical for destructive tools |
| **P1** | GoRouter + 4-tab mobile navigation | Unlocks multi-screen |
| **P1** | Email screen (list + thread) | Second most-used screen |
| **P1** | Tasks screen (grouped by priority/date) | Third most-used screen |
| **P1** | Desktop sidebar navigation | Desktop experience |
| **P1** | Desktop chat panel (persistent RHS) | Desktop experience |
| **P2** | Profile/Memory screen | Lower frequency |
| **P2** | More tab (Contacts, Files, Skills, Subagents, Settings) | Lower frequency |
| **P2** | Editable drafts | High UX value, complex |
| **P3** | Cost tracking display | Nice-to-have |
| **P3** | Dark mode | Phase 2 |
| **P3** | Push notifications | Phase 2 |

---

## Flutter Implementation Notes

### State Management
Current: Riverpod with `StateNotifier<ChatState>`. Keep it.
Add: `AsyncNotifier` for email/tasks/memory (data lives on server, not in WS stream).

### Routing
Use `go_router` with shell route for bottom tab navigation:
```
/         → HomeScreen (dashboard + chat)
/email    → EmailScreen
/tasks    → TasksScreen
/more     → MoreScreen (list items with push navigation)
  /more/contacts   → ContactsScreen
  /more/files      → FilesScreen
  /more/skills     → SkillsScreen
  /more/subagents  → SubagentsScreen
  /more/memory     → MemoryScreen
  /more/settings   → SettingsScreen
/chat/:id  → FullScreenChat (pushed from Home conversation tap)
```

### Desktop Layout
Use `LayoutBuilder` with breakpoints:
- `< 768px`: Mobile layout (bottom tabs)
- `768–1024px`: Tablet layout (collapsed sidebar + slide-in chat)
- `> 1024px`: Desktop layout (sidebar + content + chat panel)

### Responsive Shell
```dart
class ResponsiveShell extends StatelessWidget {
  // If width > 1024: SidebarLayout (sidebar + content + chat panel)
  // If width 768–1024: TabletLayout (icon sidebar + content + slide-in chat)
  // If width < 768: MobileLayout (bottom tabs, chat on Home)
}
```

### WS Event Handling
Current: handles `ai_token`, `tool_start`, `tool_end`, `interrupt`, `reasoning`, `done`, `error`.
Need to add: `text_start`, `text_delta`, `text_end`, `tool_input_start`, `tool_input_delta`, `tool_input_end`, `tool_result`, `reasoning_start`, `reasoning_delta`, `reasoning_end`, `usage`.

### Theme
Create `lib/theme/app_theme.dart` with:
- Color tokens from palette above
- Typography scale from the table above
- Spacing constants from the spacing table above
- Border radius constants from the radius table above
- Component themes (CardTheme, AppBarTheme, BottomSheetTheme, etc.)

### Testing
- Widget tests for each screen
- Integration test: full Chat → Approval flow
- Golden tests for HITL approval sheet layout
- Responsive breakpoint tests (mobile, tablet, desktop widths)

---

## Navigation Summary

| Platform | Pattern | Items |
|----------|---------|-------|
| **Desktop (>1024px)** | Left sidebar (240px, collapsible to 48px icons) | Home, Files, Email, Todos, Contacts, Skills, Subagents, Memory, ──, Settings |
| **Desktop RHS** | Persistent chat panel (360px, resizable) | Always visible |
| **Mobile (<1024px)** | 4 bottom tabs | Home (chat+dashboard), Email, Tasks, More |
| **Mobile More** | List items with push navigation | Contacts, Files (remote), Skills, Subagents, Memory, ──, Settings |
| **Mobile cross-tab** | FAB on Email/Tasks tabs | Contextual agent bottom sheet |
| **Tablet (768–1024px)** | Collapsed sidebar (icons) + content + slide-in chat panel | Hybrid |