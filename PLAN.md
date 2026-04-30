# Executive Assistant — Project Plan

> Custom agent SDK replacing LangChain/LangGraph. Test-driven. Incremental. Zero regression.

---

## Status Summary

| Phase | Description | Status |
|-------|------------|--------|
| **0** | Test Harness & Baseline | ✅ Done |
| **0.5** | API Contracts + WS Protocol | ✅ Done |
| **1** | Core SDK (Messages, Tools, State) | ✅ Done |
| **2** | LLM Provider Abstraction | ✅ Done |
| **3** | Agent Loop | ✅ Done |
| **4** | Middleware + SDK HTTP Wiring | ✅ Done |
| **5** | Structured Streaming + Tool Annotations | ✅ Done |
| **6** | Guardrails, Handoffs, Tracing | ✅ Done |
| **models.dev** | Dynamic Model Registry (4172+ models) | ✅ Done |
| **7** | Tool Migration (LangChain → SDK-native) | ✅ Done |
| **7.5** | LangChain Removal | ✅ Done |
| **7.6** | Browser Tool Replacement (Agent-Browser CLI) | ✅ Done |
| **10.1** | Critical Bug Fixes | ✅ Done |
| **10.2** | MCP Tool Bridge | ✅ Done |
| **10.3** | Discovery-Based Skills | ✅ Done |
| **10.4** | Parallel Tool Execution | ✅ Done |
| **10.5** | Architecture Improvements (ToolResult, hooks, usage, provider_options) | ✅ Done |
| **11** | Subagent V1 (work_queue, coordinator, middlewares, 8 tools) | ✅ Done |
| **12** | API Auth + Connection Modes | 🔲 Next |
| **13** | Flutter 0 — Design System + Responsive Shell + Chat + HITL | 🔲 Next |
| **14** | Flutter 1 — Settings + Connection + Local Persistence | 🔲 Future |
| **15** | Flutter 2 — Home Tab (when backend data exists) | 🔲 Future |
| **16** | Flutter 3 — Email + Tasks + Desktop Sidebar + Chat Panel (when skills re-enabled) | 🔲 Future |
| **17** | Flutter 4 — More Tab + Profile/Memory + Files + Subagents + Skills | 🔲 Future |
| **8** | Data Architecture + Team Layer + Folder Cleanup | 🔲 Future |
| **18** | Event-Driven Triggers, Smart Routing & Self-Evolution | 🔲 Future |
| **9** | Extract & Open Source SDK | 🔲 Planned |
| **19** | Parallel Subagent Execution | 🔲 Planned |
| **20** | Dynamic Subagent Creation (inline spawn) | 🔲 Planned |
| **21** | Agent Teams (multi-agent coordination) | 🔲 Planned |
| **22** | Computer Use (screen control + app automation) | 🔲 Planned |
| **23** | Workspaces (multi-project isolation) | 🔲 Planned |

**470+ SDK tests passing. Agent runs end-to-end on CLI and HTTP (REST + SSE + WebSocket). All LangChain removed.**

### Phase Dependency Graph

```
Phase 12 (Auth) ──────────────┐
                                ├──► Phase 13 (Flutter 0) ──► Phase 14 (Flutter 1)
Phase 8 (Data Architecture) ──┘                         │
                                                        ├──► Phase 15 (Flutter 2)
Phase 11 (Subagent V1) ──┬── Phase 19 (Parallel)       │
                         ├── Phase 20 (Dynamic Spawn)   │
                         ├── Phase 21 (Agent Teams) ────┤
                          └── Phase 22 (Computer Use)    │
                                                         │
Phase 23 (Workspaces) ─── standalone (affects all layers)
                                                         │
    gws/m365 skills ──► Email/Todos backend ──────────► Phase 16 (Flutter 3)
                                                         └──► Phase 17 (Flutter 4)
```

---

## Completed Work

### Pre-Phase 13 Bug Fixes (Flutter Client)

Bug fixes applied to existing Flutter code before Phase 13 implementation begins, plus an audit of **additional bugs introduced and fixed** during the Pre-Phase 13 session.

#### Phase 13 Code Already Implemented (Before Bug Fixes)

The Flutter app was already significantly implemented when this session began. This is NOT a from-scratch codebase:

| Module | Files | State |
|--------|-------|-------|
| **Theme System** (`lib/theme/`) | `app_colors.dart`, `app_typography.dart`, `app_spacing.dart`, `app_radius.dart`, `app_theme.dart` | **Complete** — All 5 design tokens + full `ThemeData` with card, appbar, bottom nav, FAB, input, sheet, divider, chip themes |
| **Responsive Layout** (`lib/core/layout/`) | `responsive_shell.dart`, `mobile_layout.dart`, `desktop_layout.dart` | **Complete** — LayoutBuilder + Breakpoints + GoRouter shell route. Mobile: BottomNavigationBar with 4 tabs. Desktop: 240px sidebar + content + 360px RHS chat panel |
| **Router** (`lib/core/router/`) | `app_router.dart` | **Complete** — GoRouter with ShellRoute, 9 named routes (`/`, `/files`, `/email`, `/tasks`, `/contacts`, `/skills`, `/subagents`, `/settings`, `/more`), `/chat` pushed route |
| **Home Screen** (`lib/features/home/`) | `home_screen.dart`, `smart_greeting.dart`, `status_cards.dart`, `quick_actions.dart` | **Complete** — SmartGreeting, StatusCards (dummy data), QuickActions, Conversation section, EmptyState. Desktop vs mobile layouts |
| **Chat Screen** (`lib/features/chat/`) | `chat_screen.dart`, `message_bubble.dart`, `streaming_bubble.dart`, `tool_call_card.dart`, `approval_sheet.dart`, `chat_input.dart`, `error_bar.dart`, `connection_banner.dart` | **Complete** — Refactored from old monolithic `chat_screen.dart` into proper feature directory. HITL bottom sheet, message list, tool cards |
| **Models** (`lib/models/`) | `message.dart`, `todo.dart`, `contact.dart`, `memory.dart`, `models.dart` | **Complete** — Plain Dart classes with `fromJson`/`toJson` |
| **Providers** (`lib/providers/`) | `agent_provider.dart` | **Complete** — `AgentNotifier` with streaming, tool calls, HITL, block-structured events, canonical type mapping |
| **Services** (`lib/services/`) | `ws_client.dart`, `api_client.dart` | **Complete** — WS with reconnect, REST with error handling |

**The app runs.** Analyzing it before this session showed: `No issues found! (ran in 1.6s)`.

---

#### 🔴 Bugs Introduced During This Session (ALL FIXED)

| # | File | Bug Introduced | How Fixed |
|---|------|----------------|-----------|
| **1** | `lib/main.dart` | **Destroyed the entire app.** Replaced existing `MaterialApp.router(...)` + `GoRouter` with a dummy `MaterialApp(home: _PlaceholderHome(...))` showing "Phase 13: Chat refactor starts here." All existing UI (responsive shell, sidebar, routing, HomeScreen, ChatScreen, theme) was **completely inaccessible**. | Restored full `MaterialApp.router` with `appRouterProvider`, `AppTheme.light`, and `ProviderScope`. |
| **2** | `lib/main.dart` | **Duplicate `main()` function.** Two `main()` entries — one created by my edit, one existing from original file. | The file was rewritten cleanly — only one `main()` remains. The `runZonedGuarded` wrapper is preserved for zone error capture. |
| **3** | `lib/main.dart` | **Wrong import for `ChatScreen`/`screens/` path.** Original Phase 13 code uses `features/chat/chat_screen.dart`, not `screens/chat_screen.dart` (which no longer exists). | Removed the bad import. The app now uses GoRouter to navigate to `HomeScreen()` as the initial route. |
| **4** | `lib/core/router/app_router.dart` | **Import placed after declarations.** `import 'instrumented_app.dart'` was inserted after `final _rootNavigatorKey = ...`, which Dart rejects. | Moved import to the top of the file, before any declarations. Also added `observers: [EaRouteObserver()]` to `GoRouter` constructor for route tracking. |
| **5** | `lib/main.dart` | **Attempted `navigatorObservers` on `MaterialApp.router`.** `MaterialApp.router` does not have a `navigatorObservers` parameter — that's only on `MaterialApp`. | Removed the invalid parameter. `EaRouteObserver` is now passed to `GoRouter(observers: [...])` instead, which is the correct location. |
| **6** | `lib/services/ws_client.dart` | **Duplicate `connect()` method.** During a failed edit, two `connect()` methods existed simultaneously with overlapping `_connecting` flag logic. | Rewrote the entire `connect()` method cleanly. Removed `_connecting` flag (it was not in the original design). Single `connect()` with `_wsScheme`, `_cleanHost`, and proper error handling. |
| **7** | `lib/services/ws_client.dart` | **Missing `_scheduleReconnect()` method.** It was accidentally deleted during the `connect()` cleanup. | Restored `_scheduleReconnect()` with exponential backoff and `_maxReconnectAttempts` check. |
| **8** | `lib/services/ws_client.dart` | **Missing `_safeArgs()` helper.** Original Phase 13 code added this helper for type-safe access to `msg['args']`. | Restored `_safeArgs()` method for handling typed tool call arguments from WebSocket messages. |

---

#### ✅ Bugs Fixed in Pre-Existing Code

| # | File | Issue | Fix |
|---|------|-------|-----|
| A | `lib/services/api_client.dart` | `jsonDecode(body)['memories']` throws when server returns non-Map (e.g., HTML error page). Same pattern for every list endpoint. | Wrapped all `jsonDecode` results with `if (decoded is Map)` guard, returning `[]` on failure. |
| B | `lib/services/api_client.dart` | `user_id` missing from POST bodies. Backend requires `user_id` for contacts, todos, memories/search. | Added `'user_id': _userId` to all POST/PUT request bodies. |
| C | `lib/services/api_client.dart` | `listMemories`, `listContacts`, `listTodos` called `jsonDecode` before `_handleResponse`, causing 500 errors to skip status check and hit raw decode. | Reordered: `_handleResponse` (status check) → `jsonDecode` on successful response. |
| D | `lib/services/api_client.dart` | Missing `sendMessage` REST method. Code had private helpers but no public method. | Added `Future<Map> sendMessage(content)` for non-streaming chat via REST. |
| E | `lib/services/ws_client.dart` | Hardcoded `ws://` scheme. Connecting to `https://host:443` or WSS servers fails silently. | Added `_wsScheme` getter (returns `wss` for `https://` or `:443`, `ws` otherwise) + `_cleanHost` getter to strip http(s):// prefixes. |
| F | `lib/services/ws_client.dart` | `connect()` swallowed actual errors via `catch(_)` — real exception hidden from user. | Changed to `catch(e, stackTrace)`. Still schedules reconnect, but error propagates to listeners. |
| G | `lib/providers/agent_provider.dart` | `switch(msg.type)` with `break` after each case means `break` never reached in switch (Dart uses `return` or fall-through). | Replaced `switch` with `if/else if` chain using `return`. Added `_canonicalType()` helper mapping backward-compat aliases (`ai_token` → `text_delta`, etc.). |
| H | `lib/providers/agent_provider.dart` | Block-structured events (`text_delta`, `tool_input_start`, `reasoning_delta`, etc.) not handled. Server emits these, Flutter ignores them. | Added `if/else if` chain for all 17 event types + canonical forms. Forward-compat: unknown types silently ignored. |
| I | `lib/providers/agent_provider.dart` | Only 1 `_statusSubscription` exists but also `_messageSubscription` field declared but never set, causing constructor to subscribe in `initState`. | Verified code: `_messageSubscription` is set in constructor (line 66). `_disposed` flag added for safe lifecycle. |

#### 🆕 Test Instrumentation Added

| File | Lines | Purpose |
|------|-------|---------|
| `lib/services/test_instrumentation.dart` | 232 | Core tracker: errors (framework, zone, platform), interactions (tap, drag, scroll, pointer, keyboard), navigation, lifecycle |
| `lib/services/instrumented_app.dart` | 105 | `InstrumentedApp` widget wrapper + `EaRouteObserver` that logs all GoRouter navigation push/pop/replace |
| `lib/main.dart` | Updated | Wires instrumentation around app + `runZonedGuarded` for async error capture |

**Instrumentation is zero-overhead when disabled.** Set `TestInstrumentation().enabled = false` at runtime to stop all logging. No rebuild required.

#### ✅ Flutter ↔ Backend Contract Fixes Applied

| # | Area | Fix |
|---|------|-----|
| 1 | REST host/scheme handling | `ApiClient` now preserves explicit `http://` / `https://`, infers `https` for `:443`, and strips trailing slashes. This aligns REST with WebSocket scheme handling. |
| 2 | REST testability | `ApiClient` now uses the injected `http.Client` for every request instead of static `http.get/post/put`, allowing deterministic unit tests without live network calls. |
| 3 | REST error handling | List endpoints now call the shared response handler before decoding and return `[]` only for successful responses where the expected list key is absent. Non-2xx responses raise `ApiException`. |
| 4 | WebSocket host handling | `WsClient` uses the public `cleanHost` getter consistently. Analyzer breakage from the `_cleanHost` rename is fixed. |
| 5 | WebSocket HITL protocol | Backend `/ws/conversation` now handles `reject` and `edit_and_approve` messages explicitly instead of silently ignoring them. It returns deterministic `DoneMessage` or `NO_PENDING_INTERRUPT` errors. |
| 6 | Cancel behavior | Removed duplicate/unreachable cancel branch in `ws.py`; cancel now sends `DoneMessage(response="Cancelled")` before closing. |
| 7 | Tests | Added deterministic ApiClient and WsClient unit tests for scheme detection, user_id/query propagation, response handling, and error handling. Targeted suite passes. |

**Verification:**

- `flutter analyze` → **No issues found**
- `flutter test test/models/ test/services/api_client_test.dart test/services/ws_client_test.dart` → **41 passed**
- `uv run pytest tests/api/test_agent_loop.py -q` → **10 passed**

**Remaining contract gaps:**

- Email, contacts, and todos routers remain disabled backend-side, so Flutter should keep these screens/placeholders non-live until gws/m365 skills are implemented.
- Full HITL resume semantics are not solved yet. `approve`, `reject`, and `edit_and_approve` now produce deterministic backend responses, but approve/edit do not yet resume the interrupted tool execution. That requires deeper AgentLoop interrupt continuation support.
- Memory JSON shape still differs: backend returns `trigger`/`action`/`updated_at`, Flutter `Memory` expects `content`/`created_at`. Either map `content = action` client-side or add a backend compatibility field.
- The generated broad widget test suite still needs cleanup; several tests are harness issues (missing GoRouter/ProviderScope/Material context) rather than app bugs. The targeted contract/unit suite is stable.

### Phase 7: Tool Migration — ✅ DONE

All tools migrated from LangChain `@tool` to SDK `@tool` in `src/sdk/tools_core/`:

| Module | Tools | Count |
|--------|-------|-------|
| `time.py` | `time_get` | 1 |
| `shell.py` | `shell_execute` | 1 |
| `filesystem.py` | `files_list`, `files_read`, `files_write`, `files_edit`, `files_delete`, `files_mkdir`, `files_rename` | 7 |
| `file_search.py` | `files_glob_search`, `files_grep_search` | 2 |
| `file_versioning.py` | `files_versions_list`, `files_versions_restore`, `files_versions_delete`, `files_versions_clean` | 4 |
| `memory.py` | `memory_connect`, `memory_get_history`, `memory_search`, `memory_search_all`, `memory_search_insights` | 5 |
| `firecrawl.py` | `scrape_url`, `search_web`, `map_url`, `crawl_url`, `get_crawl_status`, `cancel_crawl`, `firecrawl_status`, `firecrawl_agent` | 8 |
| `browser.py` | `browser_open`, `browser_snapshot`, `browser_click`, `browser_fill`, `browser_type`, `browser_press`, `browser_scroll`, `browser_hover`, `browser_screenshot`, `browser_eval`, `browser_get_title`, `browser_get_text`, `browser_get_html`, `browser_get_url`, `browser_tab_new`, `browser_tab_close`, `browser_back`, `browser_forward`, `browser_wait_text`, `browser_sessions`, `browser_close_all`, `browser_status` | 22 |
| `apps.py` | `app_create`, `app_list`, `app_schema`, `app_delete`, `app_insert`, `app_update`, `app_delete_row`, `app_column_add`, `app_column_delete`, `app_column_rename`, `app_query`, `app_search_fts`, `app_search_semantic`, `app_search_hybrid` | 14 |
| `mcp.py` | `mcp_list`, `mcp_reload`, `mcp_tools` | 3 |
| `skills.py` | `skills_list`, `skills_search`, `skills_load`, `skill_create`, `sql_write_query` | 5 |

**Note:** Email (8), contacts (6), todos (5) tools are disabled pending redesign (see "Disabled Tools" section).

### Phase 7.5: LangChain Removal — ✅ DONE

- `langchain_adapter.py` — deleted
- `messages.py` — removed `to_langchain()` / `from_langchain()` bridge methods
- `middleware_memory.py` — replaced LangChain imports with SDK provider
- `middleware_summarization.py` — removed LangChain fallback
- `cli/main.py` — rewritten to use SDK runner
- `http/main.py` — lifespan no longer depends on LangChain agent pool
- MCP manager — rewritten to use native `mcp` SDK
- `pyproject.toml` — 7 LangChain deps removed from core; Telegram extra removed (bot being discontinued)
- `tests/sdk/test_conformance.py` — deleted (LangChain parity tests)
- `tests/sdk/test_messages.py` — removed LangChain interop tests

### Phase 7.6: Browser Tool Replacement — ✅ DONE

- `src/sdk/tools_core/browser.py` — new, using Agent-Browser CLI (Rust, ref-based)
- `src/sdk/tools_core/browser_use.py` — deleted (was Browser-Use CLI, Python-based)
- `native_tools.py` — imports updated, tool names updated

---

## Phase 12: API Auth + Connection Modes — 🔲 NEXT

> Prerequisite for any remote Flutter client (LAN, Tailscale, cloud). Currently the HTTP server and WebSocket have zero auth — any connection is trusted. This must be fixed before Phase 13.

### Why Auth Now

1. **The Flutter app connects remotely.** Solo mode (localhost) needs no auth, but LAN, Tailscale, and cloud deployments expose the API to the network. Without auth, anyone on the same network can send messages, approve tool calls, and read conversation history.

2. **The WS protocol passes `user_id` as a plain string.** Any client can impersonate any user by setting `user_id: "alice"`. The server trusts it blindly.

3. **Solo mode should remain zero-config.** Auth must not add friction for localhost users. The solution: auth is required on all connections unless the request comes from localhost (127.0.0.1/::1).

### Design: API Key Auth (Not JWT)

| Aspect | Decision | Why |
|--------|----------|-----|
| **Method** | Bearer token (API key) | Simplest auth that works for all connection modes. No token refresh, no OIDC flow, no session management. |
| **Why not JWT** | JWT adds issuance, rotation, expiry, revocation infrastructure. EA is per-user (one container = one user). A static API key per container is sufficient — JWT solves multi-user single-process auth which we don't have. |
| **Why not OAuth** | OAuth requires an authorization server, redirect flows, and scope management. Overkill for a single-user agent API. |
| **Storage** | `EA_API_KEY` env var or `api_key` in `config.yaml`. Hashed with SHA-256 for comparison. | Same pattern as DEPLOYMENT.md team mode (`EA_AUTH_JWT_SECRET`). |
| **Solo bypass** | Requests from 127.0.0.1 or ::1 skip auth. | Zero-config for localhost. No API key needed for `ea http` on your own machine. |
| **Flutter client** | API key stored in `flutter_secure_storage`. Sent as `Authorization: Bearer <key>` header (REST) and `{"type": "auth", "api_key": "<key>"}` first WS message. | Matches DEPLOYMENT.md connection modes. |

### Implementation

| # | Task | Details |
|---|------|---------|
| 1 | Add `AuthConfig` to `src/config/settings.py` | `api_key: str = ""` (empty = auth disabled for solo), `solo_bypass: bool = True` (skip auth for localhost) |
| 2 | Create `src/http/auth.py` | `verify_api_key(key: str) -> bool` — SHA-256 compare against configured key. `get_api_key_hash() -> str` — hash for storage. `is_localhost(request: Request) -> bool` — check client IP. |
| 3 | Create `src/http/middleware.py` | FastAPI `Depends` dependency. If `auth_config.api_key` is empty → allow all. If `auth_config.solo_bypass` and `is_localhost(request)` → allow. Otherwise → validate `Authorization: Bearer <key>` header. Returns 401 on failure. |
| 4 | Add auth dependency to all REST routers | `conversation_router`, `memories_router`, `workspace_router`, `skills_router`, `subagents_router` — all get `Depends(auth_middleware)`. Health endpoints remain unauthenticated. |
| 5 | Add auth to WebSocket handshake | On `ws/conversation` connect, client must send `{"type": "auth", "api_key": "<key>"}` as first message. Server validates and responds with `{"type": "auth_ok"}` or `{"type": "error", "code": "AUTH_FAILED"}` and closes. If `EA_API_KEY` is empty and client connects from localhost → skip auth. |
| 6 | Add auth message type to `ws_protocol.py` | `AuthMessage(api_key: str)` → client-to-server. `AuthOkMessage()` → server-to-client. |
| 7 | Update `WsClient` in Flutter | Add `apiKey` field. On connect, send `AuthMessage` as first message if key is non-empty. Handle `auth_ok` and `auth_failed` responses. |
| 8 | Update `ApiClient` in Flutter | Add `Authorization: Bearer <key>` header to all requests if key is non-empty. |
| 9 | Add connection mode detection to Flutter | `ConnectionMode` enum: `localhost` (no auth needed), `lan` (need API key), `tailscale` (need API key), `cloud` (need API key). Auto-detect: if host is 127.0.0.1 or localhost → `localhost`. Otherwise → `lan` (require key). |
| 10 | Update Flutter settings | Replace `_SettingsSheet` bottom sheet with proper settings screen. Add connection mode indicator (green/amber/red dot), API key field (masked), model display. Store API key in `flutter_secure_storage`. |
| 11 | Add REST endpoint `GET /auth/verify` | Returns `{"valid": true}` if API key is correct. Flutter calls this on connect to validate the stored key. Unauthenticated if auth is disabled (solo mode). |

### Solo vs Remote Auth Flow

```
Solo (localhost):
  Client connects → no EA_API_KEY → no auth required → proceeds
  Client connects → EA_API_KEY set → localhost bypass → proceeds

Remote (LAN/Tailscale/Cloud):
  Client connects → EA_API_KEY is set → auth required
  REST: Authorization: Bearer <key> → middleware validates → 401 or proceed
  WS: {"type": "auth", "api_key": "<key>"} → server validates → auth_ok or close
  Client connects → EA_API_KEY empty → 401/forbidden (remote without key = unsafe)
```

---

## Phase 13: Flutter 0 — Design System + Responsive Shell + Chat + HITL — 🔲 NEXT

> The first usable Flutter app. Depends on Phase 12 for auth (remote connections).

Full design doc: [docs/FLUTTER_UX_PLAN.md](./docs/FLUTTER_UX_PLAN.md)

### 13.1 Design System (`lib/theme/`)

Create the foundational theme files that everything else depends on.

| # | Task | Details |
|---|------|---------|
| 1 | Create `lib/theme/app_colors.dart` | Color tokens: Background `#FFFFFF`, Surface `#F5F5F7`, Primary `#1A1A2E`, Accent `#0D9488`, Accent hover `#0F766E`, Success `#22C55E`, Warning `#F59E0B`, Danger `#EF4444`, Text primary/secondary/dim |
| 2 | Create `lib/theme/app_typography.dart` | Inter-only type scale: Screen title 30px/SemiBold/-2.5%, Section title 22px/SemiBold/-1.5%, Body 14px/Regular, Caption 12px/Regular/+1%, Tool 13px/Medium, Metric 24px/Bold/-1% |
| 3 | Create `lib/theme/app_spacing.dart` | Spacing tokens: screenEdge 24px, betweenSections 32px, betweenCards 12px, cardPadding 16px, componentDefault 16px, textToComponent 16px |
| 4 | Create `lib/theme/app_radius.dart` | Radius tokens: card 24px/32px (mobile/desktop), button 16px, chip 12px, sheet 24px, input 12px, dialog 24px/28px |
| 5 | Create `lib/theme/app_theme.dart` | Material 3 `ThemeData` combining all tokens. Light mode only (dark = Phase 3). Export `AppTheme` class. |
| 6 | Update `main.dart` to use `AppTheme` | Replace `ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo))` |

### 13.2 Responsive Layout Shell

Build the three-breakpoint adaptive shell that switches between mobile tabs, tablet hybrid, and desktop three-panel.

| # | Task | Details |
|---|------|---------|
| 7 | Create `lib/core/router/app_router.dart` | GoRouter config with shell route for bottom tabs. Routes: `/` (Home), `/email`, `/tasks`, `/more`, `/more/contacts`, `/more/files`, `/more/skills`, `/more/subagents`, `/more/memory`, `/more/settings`, `/chat/:id` (pushed from Home). |
| 8 | Create `lib/core/constants/breakpoints.dart` | `class Breakpoints { mobile: 768, tablet: 1024 }` |
| 9 | Create `lib/core/layout/responsive_shell.dart` | `ResponsiveShell` widget: uses `LayoutBuilder` + breakpoints. If >1024: `DesktopLayout` (sidebar + content + chat). If 768-1024: `TabletLayout` (icon sidebar + content + slide-in chat). If <768: `MobileLayout` (bottom tabs). |
| 10 | Create `lib/core/layout/desktop_layout.dart` | Three-panel: `Sidebar` (240px, collapsible to 48px icons) + `MainContent` (flexible) + `ChatPanel` (360px, resizable via drag). Sidebar items: Home, Files, Email, Todos, Contacts, Skills, Subagents, Memory, divider, Settings. |
| 11 | Create `lib/core/layout/tablet_layout.dart` | Collapsed icon sidebar (48px) + main content + `SlidingChatPanel` (opens from right via toggle button in app bar). |
| 12 | Create `lib/core/layout/mobile_layout.dart` | `BottomNavigationBar` with 4 tabs: Home, Email, Tasks, More. `GoRouter` shell route manages navigation. No chat panel — chat integrated in Home tab. |
| 13 | Create `lib/core/layout/sidebar.dart` | Desktop sidebar widget with icon + label items. Collapsible. Active state uses accent color. Settings at bottom, separated by divider. |
| 14 | Create `lib/core/widgets/status_badge.dart` | Reusable `StatusBadge` widget: green/amber/red dot + label. Used for connection status, sync status, subagent status. |
| 15 | Create `lib/core/widgets/sync_indicator.dart` | `SyncIndicator`: shows "Last synced: X min ago" or "Offline — cached from HH:MM". For remote (self-hosted) mode awareness. |
| 16 | Update `main.dart` to use `ResponsiveShell` + `AppRouter` | Replace `home: const ChatScreen()` with `MaterialApp.router(routerConfig: appRouter, theme: AppTheme.light)` |

### 13.3 Home Screen (Chat-Only Placeholder)

The primary screen for Phase 13 is chat-only — the full dashboard with status cards and recent activity moves to Phase 15 when backend data exists. For now, the Home screen is just the ChatScreen from Phase 13.4 embedded in the mobile layout and desktop chat panel.

| # | Task | Details |
|---|------|---------|
| 17 | Create `lib/features/home/home_screen.dart` | Placeholder: embeds `ChatScreen` for mobile, delegates to dashboard layout for desktop. Full dashboard cards (status, activity, quick actions) move to Phase 15. |

### 13.4 Chat (Refactored)

Refactor existing `chat_screen.dart` into proper feature structure and add block-structured streaming support.

| # | Task | Details |
|---|------|---------|
| 23 | Create `lib/features/chat/chat_screen.dart` | Mobile: used when pushing from Home conversation tap (`/chat/:id`). Full-screen chat with back button. Desktop: already visible as RHS panel, this widget fills it. |
| 24 | Create `lib/features/chat/widgets/message_bubble.dart` | Extract from `_MessageBubble`. User right-aligned (accent bg), assistant left-aligned (surface bg). 24px radius (top corners only for user, bottom corners for assistant — chat bubble shape). |
| 25 | Create `lib/features/chat/widgets/streaming_bubble.dart` | Extract from `_StreamingBubble`. Shows partial text with spinner. Uses accent color for the typing indicator dot. |
| 26 | Create `lib/features/chat/widgets/tool_call_card.dart` | Replace `_ToolCallBubble` + `_ToolCallChip`. Collapsible card: shows `toolName` + status (spinning ✓ or failed ✗). Tap expands to show args + result. Uses Inter Medium 13px, chip bg = surface color, 12px radius. |
| 27 | Create `lib/features/chat/widgets/editable_draft_card.dart` | New. When assistant produces a draft (email, etc.), shows it in an editable card with `[Send] [Edit] [Discard]` buttons. Wise "edit before send" pattern. |
| 28 | Create `lib/features/chat/widgets/chat_input.dart` | Extract from `_InputStream`. Always-visible input bar: `TextField` (24px radius, surface bg) + `[📎]` attachment + `[➤]` send (accent color). Send swaps to stop icon when streaming. |
| 29 | Create `lib/features/chat/providers/chat_provider.dart` | Refactor `AgentNotifier` + `ChatState` from `agent_provider.dart`. Add support for block-structured streaming events: `text_start`, `text_delta`, `text_end`, `tool_input_start`, `tool_input_delta`, `tool_input_end`, `tool_result`, `reasoning_start`, `reasoning_delta`, `reasoning_end`, `usage`. Keep backward-compat aliases for existing events. |
| 30 | Create `lib/features/chat/widgets/reasoning_card.dart` | Collapsible card for reasoning/thinking content. Default collapsed, tap to expand. Shows "Thinking..." with a brain icon. Dimmed text, surface bg. |

### 13.5 HITL Approval Sheet

Full-screen bottom sheet for destructive tool approvals. Wise "Confirm Transfer" pattern.

| # | Task | Details |
|---|------|---------|
| 31 | Create `lib/features/chat/widgets/approval_sheet.dart` | `showModalBottomSheet(isScrollControlled: true, ...)` — full-height sheet. Contains: tool icon + name, key arguments highlighted, risk level badge (amber for destructive, red for irreversible), "View full args ▾" progressive disclosure, editable fields section, `[Reject]` (gray) + `[Approve]` (accent) buttons. 24px top corner radius. |
| 32 | Create `lib/features/chat/widgets/risk_badge.dart` | `RiskBadge` widget: amber "⚡ Destructive" or red "⚠️ Irreversible". Based on `ToolAnnotations.destructive` + `readOnly`. |
| 33 | Create `lib/features/chat/widgets/editable_fields.dart` | `EditableFields` widget: renders tool args as editable `TextField`s. Only arguments marked as editable by tool annotations. Pre-filled with current values. |
| 34 | Wire approval sheet into `chat_provider.dart` | Replace inline `_ApprovalBar` with `ApprovalSheet`. On `interrupt` event, show `ApprovalSheet`. On approve: send `approveToolCall`. On reject: send `rejectToolCall`. |

### 13.6 Connection Status + Settings Refactor

Move settings from bottom sheet to proper screen inside Profile/More tab. Keep connection status as a persistent indicator.

| # | Task | Details |
|---|------|---------|
| 35 | Create `lib/features/settings/settings_screen.dart` | Connection section (host, user ID, model, cost this session), Privacy section (memory toggle, auto-approve read-only), Danger Zone section (clear conversation, reset memory, disconnect accounts). Wise-inspired card layout. |
| 36 | Create `lib/features/settings/widgets/connection_card.dart` | Shows server host, user ID, connected status (green/red/amber dot), model name, session cost. Tap to edit. |
| 37 | Create `lib/features/settings/widgets/privacy_card.dart` | Memory on/off toggle, auto-approve read-only toggle, data stored locally indicator. |
| 38 | Create `lib/features/settings/widgets/danger_zone_card.dart` | Red-accented card with destructive actions: clear conversation, reset memory, disconnect. Each with confirmation dialog. |
| 39 | Refactor `agent_provider.dart` → `connection_provider.dart` + `chat_provider.dart` | Split connection state (host, userId, connected) into `ConnectionNotifier`. Chat state stays in `ChatNotifier`. Settings provider for preferences. |

### 13.7 Services Layer

Update and expand the services to support the new screens.

| # | Task | Details |
|---|------|---------|
| 40 | Update `lib/services/ws_client.dart` | Add handlers for block-structured events: `text_start/delta/end`, `tool_input_start/delta/end`, `tool_result`, `reasoning_start/delta/end`, `usage`. Map backward-compat aliases (`ai_token` → `text_delta`, `tool_start` → `tool_input_start`, etc.). |
| 41 | Update `lib/services/api_client.dart` | Add methods for new endpoints: `getEmails`, `getTodos`, `getContacts`, `getSubagents`, `getMemories`, `getSkills`. All take `user_id` param. |
| 42 | Create `lib/services/sync_service.dart` | `SyncService` tracks last-sync timestamps per data type. Shows "Last synced X min ago" or "Offline — cached from HH:MM". For self-hosted mode awareness. |
| 43 | Create `lib/models/` barrel file updates | Use plain Dart classes with `copyWith` (skip `freezed` for now — thin client doesn't need the build step overhead). Add `fromJson`/`toJson` manually where needed for WS/REST serialization. |

> **Note on `freezed`:** The original plan called for freezed + json_serializable on all models. After review, this adds significant build_step complexity (`dart run build_runner build`) for a thin WebSocket client. Plain Dart classes with `copyWith` (as the current app already uses) are sufficient. Add freezed later only if model immutability becomes painful.

---

## Phase 14: Flutter 1 — Settings + Connection + Local Persistence — 🔲 FUTURE

> Depends on Phase 13 for the design system and basic UI structure.

### 14.1 Settings Screen + Auth Integration

| # | Task | Details |
|---|------|---------|
| 1 | Implement Phase 12 auth in Flutter | If `EA_API_KEY` is set on server and host is not localhost, show API key field in settings. Send `AuthMessage` as first WS message. Add `Authorization` header to REST calls. |
| 2 | Create settings screen (task 35 from Phase 13) | Connection section with mode indicator (localhost/lan/cloud), host field, API key field (masked), user ID, model name, session cost. Privacy section. Danger zone section. |
| 3 | Create connection card widget (task 36) | Shows host, user ID, connected status dot, model name, session cost. Tap to edit. |
| 4 | Create privacy card widget (task 37) | Memory toggle, auto-approve read-only toggle, data stored locally indicator. |
| 5 | Create danger zone card widget (task 38) | Clear conversation, reset memory, disconnect. Each with confirmation dialog. |
| 6 | Add `ConnectionMode` detection | Auto-detect: localhost → no auth, LAN → need API key, Tailscale → need API key, Cloud → need API key. |

### 14.2 Provider Refactor + Local Persistence

| # | Task | Details |
|---|------|---------|
| 7 | Refactor `agent_provider.dart` → `connection_provider.dart` + `chat_provider.dart` | Split: `ConnectionNotifier` owns host/userId/connected/status. `ChatNotifier` owns messages/streaming/toolCalls/approvals. |
| 8 | Add `shared_preferences` dependency | Key-value storage for: host, user_id, api_key (move to flutter_secure_storage later), auto_approve_readonly, memory_enabled. |
| 9 | Add `flutter_secure_storage` dependency | Store API key securely. Never store in shared_preferences. |
| 10 | Create `lib/services/storage_service.dart` | Wrapper over shared_preferences + flutter_secure_storage. Load/save connection config, user preferences. Survives app restart. |
| 11 | Cache conversation metadata locally | Store conversation IDs + last message preview in shared_preferences. Enables Home tab's "Recent activity" without a network call. |

---

## Phase 15: Flutter 2 — Home Tab — 🔲 FUTURE

> Depends on Phase 14 for settings/persistence, and backend data existing (conversation history API, subagent status API).

### 15.1 Home Tab

| # | Task | Details |
|---|------|---------|
| 1 | Create `lib/features/home/home_screen.dart` | Mobile: `Column(SmartGreeting, StatusCards, RecentActivity, ChatInput)`. Desktop: delegates to dashboard content area. |
| 2 | Create `lib/features/home/widgets/smart_greeting.dart` | "Good morning, Eddy" + date. Dynamic greeting based on time of day. |
| 3 | Create `lib/features/home/widgets/status_cards.dart` | Horizontal scrolling cards. Unread emails, due tasks, active subagents. Each card shows count + icon + accent color. Tap navigates to tab. 24px radius. |
| 4 | Create `lib/features/home/widgets/quick_actions.dart` | Action chips: "Draft reply", "Summarize", "Schedule". Tap pre-fills chat input. |
| 5 | Create `lib/features/home/widgets/recent_activity.dart` | Recent conversation summaries grouped by date. Tap pushes to `/chat/:id`. |
| 6 | Create `lib/features/home/providers/home_provider.dart` | Riverpod `AsyncNotifier` fetching: unread counts, due tasks, active subagents, recent conversations. |

> **Note:** Status cards for email and tasks will show "Connect account" or "0" until the gws/m365 skills are implemented and the email/todos endpoints are re-enabled. The subagent card can show real data immediately (subagent endpoints are active).

---

## Phase 16: Flutter 3 — Email + Tasks + Desktop Sidebar + Chat Panel — 🔲 FUTURE

> Depends on email/todos skills being re-enabled (gws/m365). Build these screens when backend data exists.

### 16.1 Email Screen

| # | Task | Details |
|---|------|---------|
| 1 | Create `lib/features/email/email_screen.dart` | Pull-to-refresh list. Connected accounts card at top. Emails grouped by date ("Today", "Yesterday", "This week"). Unread = red dot. Tap → thread view (push). |
| 2 | Create `lib/features/email/widgets/connected_accounts_card.dart` | Shows connected email accounts with status dots (green = connected, red = disconnected). Tap to reconnect. 24px radius card. |
| 3 | Create `lib/features/email/widgets/email_list_tile.dart` | Leading: avatar or initials. Title: sender name. Subtitle: subject. Trailing: timestamp + unread dot. Tap pushes to email detail. |
| 4 | Create `lib/features/email/widgets/email_detail_screen.dart` | Full email thread view. From/To/Subject header. Body content. Action bar: Reply, Forward, Archive. |
| 5 | Create `lib/features/email/providers/email_provider.dart` | Riverpod `AsyncNotifier` fetching emails from `ApiClient`. Supports: pull-to-refresh, search, filter by account. |
| 6 | Add FAB for contextual agent on email screen | `[💬]` FAB → bottom sheet with "Ask about your emails..." input. Agent response can update email list filter. |

### 16.2 Tasks Screen

| # | Task | Details |
|---|------|---------|
| 7 | Create `lib/features/tasks/tasks_screen.dart` | Tasks grouped by urgency: Today (red/amber/green priority dots), This Week, Completed (strikethrough, gray). Pull-to-refresh. FAB to add task. |
| 8 | Create `lib/features/tasks/widgets/task_group.dart` | Section with header ("Today", "This Week", "Completed") + list of `TaskTile` items. 32px between sections. |
| 9 | Create `lib/features/tasks/widgets/task_tile.dart` | Leading: priority dot (red/amber/green). Title: task content. Trailing: due date. Tap → task detail sheet. Checkbox to complete. |
| 10 | Create `lib/features/tasks/widgets/add_task_sheet.dart` | Bottom sheet with text field. Auto-extract from `todos_extract` or manual entry. Accent "Add" button. |
| 11 | Create `lib/features/tasks/providers/tasks_provider.dart` | Riverpod `AsyncNotifier` fetching todos from `ApiClient`. Supports: add, complete, delete, refresh. |
| 12 | Add FAB for contextual agent on tasks screen | `[💬]` FAB → bottom sheet with "Add or update tasks..." input. |

### 16.3 Desktop Sidebar + Chat Panel

| # | Task | Details |
|---|------|---------|
| 13 | Implement desktop `Sidebar` widget | 240px wide, collapsible to 48px icons. Items: Home, Files, Email, Todos, Contacts, Skills, Subagents, Memory. Divider. Settings at bottom. Active item uses accent color. |
| 14 | Implement desktop `ChatPanel` widget | 360px wide, resizable via drag handle. Contains: chat messages + input bar. Always visible. Can be minimized to icon button. |
| 15 | Wire bidirectional navigation | Chat can drive content panel: "show me Sarah's emails" navigates sidebar to Email tab with Sarah filter. Sidebar tab changes update content panel. |
| 16 | Tablet: implement `SlidingChatPanel` | Animation slide-in from right. Toggle button in app bar. 360px width when open. |

---

## Phase 17: Flutter 4 — More Tab + Profile/Memory + Files + Subagents + Skills — 🔲 FUTURE

### 17.1 More Tab (Mobile)

| # | Task | Details |
|---|------|---------|
| 1 | Create `lib/features/more/more_screen.dart` | List of section items: Contacts, Files (⟁ Remote badge), Skills, Subagents (● N active badge), Memory. Divider. Settings at bottom. Each item pushes to its screen. 24px radius list items with icons. |
| 2 | Create `lib/features/more/widgets/more_list_tile.dart` | Leading icon, title, optional trailing badge or subtitle. Tap pushes to detail screen. |

### 17.2 Profile / Memory Screen

| # | Task | Details |
|---|------|---------|
| 3 | Create `lib/features/memory/memory_screen.dart` | "What I Know About You" grouped by domain (Work, Communication, Private). Each memory shows content + confidence stars. Tap to reveal private items. Editable. AI-generated insights section with Keep/Dismiss. |
| 4 | Create `lib/features/memory/widgets/memory_domain_group.dart` | Card per domain (Work, Communication, Private). Expansion tile with memory items. Each item: content text + confidence star rating. |
| 5 | Create `lib/features/memory/widgets/insight_card.dart` | AI-generated text with `[Keep]` / `[Dismiss]` buttons. Surface bg, 24px radius. |
| 6 | Create `lib/features/memory/providers/memory_provider.dart` | Riverpod `AsyncNotifier` fetching memories from `ApiClient`. Supports: search, edit, delete, create insight. |

### 17.3 Contacts Screen

| # | Task | Details |
|---|------|---------|
| 7 | Create `lib/features/contacts/contacts_screen.dart` | Search bar at top. Contact list: avatar + name + company + email. Tap → contact detail. Alphabetical sections. |
| 8 | Create `lib/features/contacts/widgets/contact_tile.dart` | Leading: initials avatar. Title: name. Subtitle: company. Trailing: email icon. |
| 9 | Create `lib/features/contacts/providers/contacts_provider.dart` | Riverpod `AsyncNotifier` fetching contacts from `ApiClient`. Search, add, update. |

### 17.4 Files Screen

| # | Task | Details |
|---|------|---------|
| 10 | Create `lib/features/files/files_screen.dart` | Search bar. "⟁ Remote" badge in app bar (self-hosted mode). File tree grouped by folder. "Last synced: X min ago" indicator. Tap file → preview/download. |
| 11 | Create `lib/features/files/widgets/file_tile.dart` | Leading: file type icon (doc/image/code). Title: filename. Subtitle: size + modified date. Trailing: download icon. |
| 12 | Create `lib/features/files/providers/files_provider.dart` | Riverpod `AsyncNotifier` calling `files_list` via `ApiClient`. Supports: navigate folders, search, download. |

### 17.5 Subagents Screen

| # | Task | Details |
|---|------|---------|
| 13 | Create `lib/features/subagents/subagents_screen.dart` | Two sections: Active (with status, progress bar, cost) and Completed. Tap → subagent detail. "New Subagent" FAB. |
| 14 | Create `lib/features/subagents/widgets/subagent_card.dart` | Card with: name, status dot (running/complete/failed), task description, progress bar, cost, `[Instruct]` `[Cancel]` buttons. 24px radius. |
| 15 | Create `lib/features/subagents/providers/subagents_provider.dart` | Riverpod `AsyncNotifier` fetching subagents from `ApiClient`. Supports: create, invoke, progress, cancel, instruct. |

### 17.6 Skills Screen

| # | Task | Details |
|---|------|---------|
| 16 | Create `lib/features/skills/skills_screen.dart` | Two sections: Active skills (currently loaded) and Available skills (can be loaded). Tap → skill description + load button. Search bar. |
| 17 | Create `lib/features/skills/widgets/skill_tile.dart` | Icon + name + short description + "Loaded X ago" or "Tap to load". |
| 18 | Create `lib/features/skills/providers/skills_provider.dart` | Riverpod `AsyncNotifier` fetching skills from `ApiClient`. Load, search. |

---

## Phase 8: Data Architecture + App Sharing + Folder Cleanup — 🔲 FUTURE

See [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md) for the full data architecture design.

### 8.1 DataPaths Class + Config

Add deployment-aware data path resolution:

```python
class DataPaths:
    deployment: str          # "solo" | "multi-user"
    base: Path              # data/

    def private(self) -> Path: ...       # data/private/
    def shared(self) -> Path: ...        # data/shared/
    def templates(self) -> Path: ...     # data/templates/
    def personal_apps(self) -> Path: ... # data/private/apps/
    def shared_apps(self) -> Path: ...   # data/shared/apps/
```

- Add `deployment` and `data_path` to `src/config/settings.py`
- Solo: `data/shared/` may not exist (no one to share with)
- Multi-user: `data/shared/` is a mounted volume visible to all containers

**Why `private/` + `shared/` instead of `users/{user_id}/`**: Each deployment serves exactly one user. The container IS the isolation boundary. A `users/` directory adds path complexity for no benefit.

### 8.2 Migrate Storage Classes to DataPaths

Update all storage classes to use `DataPaths` instead of hardcoded `data/users/{user_id}/`:

| Class | Current Path | New Path |
|-------|-------------|----------|
| `AppStorage` | `data/users/{user_id}/apps/` | `DataPaths.personal_apps()` |
| `ConversationStorage` | `data/users/{user_id}/conversation/` | `DataPaths.private()/conversation/` |
| `EmailDB` | `data/users/{user_id}/email/` | `DataPaths.private()/email/` |
| `ContactsDB` | `data/users/{user_id}/contacts/` | `DataPaths.private()/contacts/` |
| `TodosDB` | `data/users/{user_id}/todos/` | `DataPaths.private()/todos/` |
| `MemoryDB` | `data/users/{user_id}/memory/` | `DataPaths.private()/memory/` |

Auto-migration: if `data/private/` doesn't exist but `data/users/` does, move contents.

### 8.3 App Sharing — Schema + Access Control

Add `_app_shares` table to shared apps for role-based access:

```sql
CREATE TABLE _app_shares (
    share_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL,  -- 'viewer' | 'editor' | 'admin'
    created_at  INTEGER NOT NULL
);
```

New tools:

| Tool | Role | Description |
|------|------|-------------|
| `app_share` | admin | Grant a user access (viewer/editor/admin) |
| `app_unshare` | admin | Revoke a user's access |
| `app_shares_list` | admin | List who has access |
| `app_export` | admin | Export app as `.ea-app` tarball |
| `app_import` | any | Import `.ea-app` tarball (creates fork) |
| `app_template` | admin | Export schema-only template |
| `app_create_from_template` | any | Create app from a template |

### 8.4 Folder Cleanup — Delete Dead Code

Current dead code (LangChain tool wrappers and infrastructure):

| Directory | Status | Action |
|-----------|--------|--------|
| `src/tools/core/` | Dead (LangChain tool wrappers) | Delete entirely |
| `src/tools/apps/tools.py` | Dead | Delete (SDK version in `tools_core/apps.py`) |
| `src/tools/contacts/tools.py` | Dead | Delete |
| `src/tools/email/account.py`, `read.py`, `send.py` | Dead | Delete |
| `src/tools/filesystem/search.py`, `versioning.py` | Dead | Delete |
| `src/tools/mcp/tools.py` | Dead | Delete |
| `src/tools/memory/` | Dead | Delete entirely |
| `src/tools/vault/` | Dead | Delete entirely (no external consumers) |
| `src/storage/checkpoint.py` | Quasi-dead | Delete (LangGraph checkpoints disabled) |
| `src/storage/database.py` | Legacy | Delete (self-documented as unused) |

Still-active files that need relocation before their parent dirs can be deleted:

| File | Consumer | Relocate to |
|------|----------|-------------|
| `src/tools/apps/storage.py` | `sdk/tools_core/apps.py` | `src/sdk/tools_core/apps_storage.py` |
| `src/tools/contacts/storage.py` | `sdk/tools_core/contacts.py` | `src/sdk/tools_core/contacts_storage.py` |
| `src/tools/email/db.py`, `sync.py` | `sdk/tools_core/email.py`, HTTP routers | `src/sdk/tools_core/email_db.py`, `src/sdk/tools_core/email_sync.py` |
| `src/tools/filesystem/cache.py` | HTTP workspace router | `src/http/workspace_cache.py` |
| `src/tools/filesystem/tools.py` | HTTP workspace router | `src/http/workspace_tools.py` |
| `src/tools/mcp/manager.py` | `sdk/tools_core/mcp.py` | `src/sdk/tools_core/mcp_manager.py` |

After relocating active files, delete:

| Directory | What's Left After Relocation | Action |
|-----------|------------------------------|--------|
| `src/tools/` | Nothing — delete entirely | Delete |
| `src/agents/` | LangChain-based agent pool | Delete after confirming no remaining consumers |
| `src/llm/` | LangChain LLM providers | Delete after confirming no remaining consumers |
| `src/middleware/` | LangChain middleware | Delete after confirming no remaining consumers |

**Note**: The Telegram bot (`src/telegram/main.py`) was the last consumer of `src/agents/manager.py` and `src/llm/providers.py`. Since the Telegram channel is being removed, these three directories are no longer blocked and can be deleted once we confirm no remaining imports.

### 8.5 Implementation Order

| Step | Task | Depends on |
|------|------|-----------|
| 1 | Create `DataPaths` class in `src/storage/paths.py` | — |
| 2 | Add `deployment` + `data_path` to `Settings` | Step 1 |
| 3 | Migrate `AppStorage` to use `DataPaths` | Step 2 |
| 4 | Migrate other storage classes to `DataPaths` | Step 2 |
| 5 | Add auto-migration (`data/users/` → `data/private/`) | Steps 3-4 |
| 6 | Relocate active files from `src/tools/` to `src/sdk/tools_core/` or `src/http/` | — |
| 7 | Delete dead code (`src/tools/core/`, `memory/`, `vault/`, etc.) | Step 6 |
| 8 | Add `_app_shares` table to `AppStorage` | Step 3 |
| 9 | Implement `app_share`, `app_unshare`, `app_shares_list` tools | Step 8 |
| 10 | Implement `app_export`, `app_import`, `app_template` tools | Step 8 |
| 11 | Update `AppStorage` operations to check `_app_shares` for shared apps | Steps 8-9 |
| 12 | Delete `src/storage/checkpoint.py` and `database.py` | — |

Steps 6-7 can proceed now. Steps 1-5 are data architecture. Steps 8-11 are app sharing.

---

## External Tool Upgrades & Integrations

### ripgrep — Replace Pure Python `files_grep_search`

**Decision: Add as core tool (CLI adapter, like firecrawl/browser)**

Our agent is general-purpose — fast code search is table stakes. The current `files_grep_search` in `src/sdk/tools_core/file_search.py` is pure Python (reads every file, slow). ripgrep is 5-13x faster and the industry standard for agent code search.

**Implementation:** Replace the pure Python grep with `rg` CLI calls via `CLIToolAdapter` (same pattern as firecrawl/browser-use). Fallback to pure Python if `rg` not found.

| Aspect | Current | After |
|--------|---------|-------|
| Tool name | `files_grep_search` | `files_grep_search` (same) |
| Backend | Pure Python `re` | `rg` CLI (fallback: pure Python) |
| Speed | ~1x | 5-13x faster |
| Dependency | None (built-in) | `ripgrep` binary (brew/pkg install) |
| Pattern | N/A | `CLIToolAdapter` (like `firecrawl.py`) |

**Reference:** https://github.com/BurntSushi/ripgrep

### Pandoc — Document Format Conversion (Skill, Not Core)

**Decision: Include as a skill, not a core tool**

Pandoc converts between 50+ document formats (Markdown↔HTML↔PDF↔DOCX↔LaTeX↔EPUB...). It's powerful but niche — most users don't need it on every session. Making it a skill means:
- Loaded on demand (`skills_load pandoc`) — zero startup cost
- Doesn't bloat the core tool registry
- Users who need it get full pandoc power

**Implementation:** Create `src/skills/pandoc/` skill that wraps the `pandoc` CLI. Skill instructs the agent how to invoke `pandoc` via `shell_execute` — no new tool needed.

| Aspect | Detail |
|--------|--------|
| Install | `brew install pandoc` / `apt install pandoc` |
| Skill name | `pandoc` |
| Activation | `skills_load pandoc` |
| Tools used | Existing `shell_execute` (no new tool) |
| MCP alternative | `vivekVells/mcp-pandoc` (MCP server wrapping pandoc) |

**References:**
- https://github.com/jgm/pandoc
- https://github.com/vivekVells/mcp-pandoc (MCP server)

### Google Workspace CLI (`gws`) — Full Google Workspace Access

**Decision: Adopt as skill (on-demand), covers Gmail, Drive, Calendar, Sheets, Docs, Chat, Admin, Tasks, and more**

The Google Workspace CLI (`gws`) is a Rust-based CLI that dynamically generates commands from Google's Discovery Service — meaning it covers **every** Google Workspace API, not just email.

**Implementation:** Create `src/skills/google-workspace/` skill. The skill instructs the agent how to invoke `gws` CLI commands via `shell_execute`. No new tools needed. The CLI's built-in SKILL.md files (100+) provide curated recipes like `gmail +send`, `calendar +agenda`, `drive +upload`, `workflow +standup-report`.

| Aspect | Detail |
|--------|--------|
| Repo | https://github.com/googleworkspace/cli |
| Install | `brew install googleworkspace-cli` (macOS/Linux), npm, cargo, or binary |
| Stars | 24.7k |
| Auth | OAuth2 desktop flow, headless/CI credentials, service accounts, gcloud tokens |
| Key helper commands | `gmail +send`, `calendar +agenda`, `drive +upload`, `drive +download`, `sheets +read`, `docs +create` |
| Skill name | `google-workspace` |
| Activation | `skills_load google-workspace` |
| Tools used | Existing `shell_execute` (no new tool) |

### CLI for Microsoft 365 (`m365`) — Full Microsoft 365 Access

**Decision: Adopt as skill (on-demand), covers Outlook, Teams, SharePoint, OneDrive, Planner, To Do, Power Platform, Entra ID, and more**

CLI for Microsoft 365 (`m365`) is the Microsoft equivalent of `gws` — a TypeScript-based CLI covering the full Microsoft 365 suite. Admin/tenant-focused (SharePoint, Teams, Entra ID) as well as personal Outlook email.

**Implementation:** Create `src/skills/microsoft-365/` skill. The skill instructs the agent how to invoke `m365` CLI commands via `shell_execute`. Especially useful for users with Microsoft 365 work/tenant accounts.

| Aspect | Detail |
|--------|--------|
| Repo | https://github.com/pnp/cli-microsoft365 |
| Docs | https://pnp.github.io/cli-microsoft365/ |
| Install | `npm install -g @pnp/cli-microsoft365` |
| Stars | 1.3k |
| Contributors | 139 |
| Auth | Device code (simplest), certificate, client secret, username+password, managed identity |
| Outlook mail commands | `m365 outlook mail send/list/get`, `m365 outlook message list/get` |
| Key commands | `m365 teams *`, `m365 spo *` (SharePoint), `m365 aad *` (Entra ID), `m365 outlook *`, `m365 planner *`, `m365 todo *` |
| Skill name | `microsoft-365` |
| Activation | `skills_load microsoft-365` |
| Tools used | Existing `shell_execute` (no new tool) |

### Workspace Strategy Summary

| User Scenario | Recommended Tool(s) |
|---------------|---------------------|
| **Gmail only** | `gws` skill (Gmail + Drive + Calendar + more) |
| **Microsoft 365 work account** | `m365` skill (full tenant) |
| **Gmail + Microsoft 365** | `gws` skill + `m365` skill |
| **Generic IMAP/SMTP** | Built-in `email_*` SDK tools |
| **Document conversion** | `pandoc` skill |

**Two layers:**
1. **Core tools** — Built-in `email_*` (local IMAP/SMTP, always available)
2. **Skills** — `gws`, `m365`, `pandoc` (loaded on-demand, cover entire workspace suites)

---

## Phase 9: Extract & Open Source SDK — 🔲 FUTURE

**Goal**: Publish the SDK as a standalone Python package.

### Why Open Source

- **No provider-agnostic, Python-first agent SDK exists.** Vercel AI SDK is TypeScript. OpenAI Agents SDK is OpenAI-first. Google ADK is Gemini-first.
- **MCP convergence.** A Python SDK with native MCP client + tool annotations becomes a universal tool consumer.
- **Differentiation.** Tool annotations from MCP, structured + text results, block streaming, reasoning in messages.

### Prerequisites

1. No LangChain imports (Phase 7.5 ✅ — `langchain_adapter.py` deleted)
2. Stable streaming protocol (Phase 5 ✅)
3. Integration tests against at least OpenAI + Anthropic
4. Docs: README, quickstart, provider guide, 3-5 examples
5. Tool annotations on all built-in tools ✅

### Package Structure

```
agent-sdk/
├── pyproject.toml            # pip install agent-sdk
├── src/agent_sdk/
│   ├── __init__.py
│   ├── messages.py
│   ├── tools.py
│   ├── state.py
│   ├── loop.py
│   ├── middleware.py
│   ├── guardrails.py
│   ├── handoffs.py
│   ├── tracing.py
│   ├── validation.py
│   ├── registry.py
│   └── providers/
│       ├── base.py
│       ├── openai.py
│       ├── anthropic.py
│       ├── gemini.py
│       ├── ollama.py
│       └── factory.py
└── tests/
```

### Dependencies

```toml
dependencies = ["pydantic>=2.0", "httpx>=0.27", "tiktoken>=0.7"]
[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = []          # httpx only
gemini = []             # httpx only
mcp = ["mcp>=0.9"]
```

Zero heavy dependencies by default. Providers lazy-imported.

---

## Parallel Tool Calls (Multi-Turn + In-Turn Parallel)

**Two dimensions must work together:**

1. **Multi-turn** (already works): The agent loop iterates — LLM calls tools, gets results, decides to call more tools, gets results, until it responds with text only. This is the ReAct loop already in `AgentLoop`.

2. **In-turn parallel** (missing): When the LLM returns **multiple `tool_calls`** in a single response, they should execute concurrently where safe, then all results are collected and sent back together before the next LLM call. This is the pattern from [Ollama's tool calling docs](https://docs.ollama.com/capabilities/tool-calling) — parallel tool calling + multi-turn agent loop.

**Current state:** The AgentLoop executes tools **sequentially** within a turn (`for tc in response.tool_calls: execute(tc)` at loop.py:336). Multi-turn works — the loop repeats until no tool_calls. But when the LLM returns N tools, they run one at a time.

**Provider support:** All major providers return multiple tool_calls in a single response, and our SDK providers already parse them correctly (using `dict[int, dict]` index-based accumulation across streaming chunks):

| Provider | Multi tool_calls | SDK parsing |
|----------|:---:|---|
| **OpenAI** | ✅ `parallel_tool_calls` param (default true) | `openai.py:142` — index-based `current_tool_calls` |
| **Anthropic** | ✅ Multiple `tool_use` content blocks | `anthropic.py:222` — index-based `current_tool_calls` |
| **Gemini** | ✅ Multiple `functionCall` in parts array | `gemini.py:228` — index-based `current_tool_calls` |
| **Ollama Local** | ✅ OpenAI-compatible `/v1/chat/completions` | `ollama.py:296` — index-based `current_tool_calls` |
| **Ollama Cloud** | ✅ Native `/api/chat` tool_calls array | `ollama.py:88` — index-based `current_tool_calls` |

The **only change needed** is in `AgentLoop`: after collecting tool_calls, group by safety and run independent calls via `asyncio.gather()` instead of `for tc in tool_calls: execute(tc)`. No provider code changes.

**Target state:** When the LLM returns multiple tool_calls in one turn:
1. Classify each call: safe-to-parallel (read-only, non-destructive) vs. must-serialize (destructive, write-side-effects)
2. Execute all safe-to-parallel calls concurrently via `asyncio.gather()`
3. Execute any destructive/sequential calls one at a time after
4. Collect all results, add as tool_result messages, send back to LLM as one batch
5. Continue the multi-turn loop

**Impact on middleware and hooks:**

- **Middleware** runs per-tool (already designed for single invocation). No structural change. In the parallel case, each tool still gets its own `mw.wrap_tool_call()`. Middleware doesn't need to know about parallelism.
- **PreToolUse hooks** need to handle a batch: given N tool calls, return N decisions (allow/deny/modify). Parallel execution only starts after all pre-hooks approve. If any hook denies a call, that call is skipped; other parallel calls proceed.
- **PostToolUse hooks** receive individual results — no change needed.
- **Interrupt handling** changes: when multiple tools are called and one needs HITL approval, we have two options:
  - **A) Eager**: Execute all safe calls in parallel, but queue any interrupts. After all parallel calls complete, yield interrupts one at a time for user resolution, then execute approved calls.
  - **B) Conservative**: If any call would interrupt, skip all parallel execution for that batch and ask the user first. Simpler but slower.
  - **Recommend: Option A** — don't block independent work on a single approval decision.
- **Guardrails** already run per-tool — no structural change.

**Impact on streaming protocol:**
- Block-structured events already support multiple concurrent tool calls (each `tool_input_start` / `tool_result` has its own `tool_call_id`)
- For parallel execution, we emit `tool_input_start` for all parallel calls, then emit their `tool_result` events as they complete (order may differ from start order)
- No protocol change needed

---

## Middleware vs Hooks

These are **complementary systems serving different audiences**:

| | Middleware | Hooks |
|--|-----------|-------|
| **What** | Python code running in-process | Shell commands running out-of-process |
| **Who writes it** | Developers (us) | Users (anyone with a shell script) |
| **When it runs** | Agent lifecycle events: `before_agent`, `before_model`, `after_model` | Tool lifecycle events: `PreToolUse`, `PostToolUse` |
| **Can modify** | State, messages, tool arguments, tool results | Tool input, tool output, permission override |
| **Can abort** | Yes (raise exception) | Yes (deny + cancel) |
| **Example** | `SkillMiddleware` injects skill descriptions; `SummarizationMiddleware` compresses history | A bash script that auto-approves `files_read` but blocks `shell_execute` for specific paths |
| **Extensibility** | Requires code change + deployment | User creates `.ea/hooks/pre-tool-use.sh` and it works |

**Why both:** Middleware handles structural transformations (memory injection, summarization, skill discovery) that require deep SDK access. Hooks handle per-tool policy decisions (approve/deny/modify) that users should customize without touching code. They coexist — middleware runs at agent lifecycle boundaries, hooks run at tool execution boundaries.

---

## Skills: Discovery-Based (Removing SkillMiddleware)

**Current:** `SkillMiddleware` injects skill names+descriptions into the **system prompt on every request**. This costs tokens even when the LLM never needs a skill. Three separate `SkillRegistry` instances (middleware, SDK tools, legacy tools) are not synchronized.

**Target:** Kill `SkillMiddleware`. Move skill discovery into the tool description of `skills_list`. The tool's `description` field dynamically includes available skill names. The LLM sees skills as part of the tools list — zero system prompt waste.

Pattern (adopted from Claw Code and OpenCode):

```
Tool: skills_list
Description: |
  List and discover available skills. Current skills:
  - deep-research: Deep research and web content analysis
  - planning-with-files: Multi-step task planning
  - skill-creator: Create and improve skills
  - subagent-manager: Create and manage subagents
  
  Use skills_load(name) to get full instructions for any skill.
```

**Progressive disclosure stays the same:** LLM sees names+descriptions → calls `skills_load("deep-research")` → gets full SKILL.md body → optionally reads bundled scripts/references via `files_read`.

**Benefits:**
- Zero system prompt tokens for skills (was ~100 words per skill per request)
- Single SkillRegistry instance (shared between `skills_list` tool and `skills_load` tool)
- Skills appear naturally as a tool the LLM can call, not injected text
- LLM decides when to explore skills based on relevance, not because they're always in context

---

## Phase 10: Agent Loop Modernization

### 10.1 Critical Bug Fixes

| # | Task | Priority |
|---|------|----------|
| 1 | Delete dead `src/skills/tools.py` (legacy LangChain 153 lines) | High |
| 2 | Fix `UserSkillStorage` stale path (`data/users/` → `DataPaths.skills_dir()`) | High |
| 3 | Unify SkillRegistry instances (one per user, shared between middleware + tools) | High |
| 4 | Fix streaming interrupt inconsistency: both `run()` and `run_stream()` should yield interrupt chunks, never raise `Interrupt` as exception | High |
| 5 | Remove `interrupt_on` parameter from AgentLoop — rely solely on `ToolAnnotations.destructive` | High |
| 6 | Delete CLI (`src/cli/`, `src/__main__.py` CLI entry) — HTTP API is primary interface | High |

### 10.2 MCP Tool Bridge

| # | Task | Priority |
|---|------|----------|
| 7 | Build `MCPToolBridge`: convert MCP `mcp` SDK tool objects → SDK `ToolDefinition` | High |
| 8 | Add `AgentLoop.register_tool()` / `unregister_tool()` for dynamic tool registration | High |
| 9 | Inject discovered MCP tools into main loop as `mcp__{server}__{tool}` | High |
| 10 | Support degraded-mode: partial MCP server failures don't crash the agent | Medium |
| 11 | Replace `MCPManager._run_async()` thread hack with proper async integration | Medium |

### 10.3 Discovery-Based Skills

| # | Task | Priority |
|---|------|----------|
| 12 | Kill `SkillMiddleware` — remove from runner.py middleware stack | High |
| 13 | Move skill descriptions into `skills_list` tool description (dynamically generated) | High |
| 14 | Consolidate SkillRegistry to single per-user instance (shared by all tools) | High |
| 15 | Remove `src/sdk/middleware_skill.py` | High |

### 10.4 Parallel Tool Execution

| # | Task | Priority |
|---|------|----------|
| 16 | Modify `AgentLoop` to identify independent tool calls (non-destructive, no shared state) | High |
| 17 | Execute independent tool calls concurrently via `asyncio.gather()` | High |
| 18 | Execute destructive/dependent calls sequentially after concurrent batch | High |
| 19 | Update PreToolUse hooks to support batch mode (list of tool calls → list of decisions) | Medium |
| 20 | Update streaming to emit parallel `tool_input_start`/`tool_result` events correctly | Medium |

### 10.5 Architecture Improvements

| # | Task | Priority |
|---|------|----------|
| 21 | Implement `ToolResult` properly in `_execute_tool()`: return structured content + human content + audience + is_error | High |
| 22 | Add shell hooks at `PreToolUse` / `PostToolUse` (user-extensible, out-of-process) | High |
| 23 | Add plugin system: `plugin.json` manifest + subprocess execution like Claw Code | Medium |
| 24 | Plumb actual token counts from provider responses into `CostTracker` | Medium |
| 25 | Accept `provider_options` from `RunConfig` or per-request kwargs (currently hardcoded `None`) | Medium |

### 10.6 Advanced (Phase 18+)

| # | Task | Priority | Status |
|---|------|----------|--------|
| 26 | HITL middleware: adopt interrupt/approve/reject flow — when a destructive tool is called, yield interrupt chunk, wait for user resolution, then continue or skip | High | 🔲 Future |
| 27 | Skill-activated tools: skills can declare tool dependencies that get registered on load | Medium | 🔲 Future |
| 28 | Git-based undo/redo for file changes (like OpenCode snapshots) | Low | 🔲 Future |
| 29 | ~~Subagent system rewrite (LangChain → SDK)~~ | ~~High~~ | ✅ Done (Phase 11) |
| 30 | Worker state machine (Spawning → Ready → Running → Finished) | Medium | 🔲 Future |
| 31 | Email/contacts/todos redesign (currently disabled, pending redesign) | Medium | 🔲 Future |
| 32 | Calendar tools (new, doesn't exist yet) | Medium | 🔲 Future |

---

## Phase 18: Event-Driven Triggers, Smart Routing & Self-Evolution — 🔲 FUTURE

### 18.1 Event-Driven Agent Triggers

The main agent should be activatable by external events, not just user messages. Three trigger types:

| Trigger Type | Mechanism | Examples |
|-------------|-----------|----------|
| **Cron / Scheduled** | APScheduler or `croniter` + asyncio task | "Check email every 30 min", "Daily standup summary at 9am", "Weekly report every Friday" |
| **Webhook** | HTTP endpoint (FastAPI route) that creates an agent run | GitHub push → code review, Stripe payment → receipt, Slack mention → response |
| **File Watch** | `watchfiles` / `inotify` on a directory | New file in `data/inbox/` → process, CSV updated → re-analyze, config change → reload |

**Implementation:**

- New `TriggerManager` in `src/triggers/` — registers, schedules, and dispatches triggers
- Each trigger creates an `AgentLoop.run()` call with the event payload as the initial user message
- Triggers are persisted in `data/private/triggers.db` (SQLite, same pattern as work_queue)
- New tools: `trigger_create` (cron/webhook/file), `trigger_list`, `trigger_delete`
- Webhook triggers expose a unique URL: `POST /webhook/{trigger_id}`
- Cron triggers use `APScheduler` or `croniter` for scheduling
- File watch triggers use `watchfiles` (already a dependency via uvicorn)

### 18.2 Smart Subagent Routing (Duration-Aware Orchestration)

When a task is expected to take 10+ seconds, the main agent should automatically route it to a subagent rather than blocking the main conversation. This requires:

1. **Duration estimation**: LLM assesses task complexity (rough categories: <5s instant, 5-30s moderate, 30s+ heavy)
2. **Auto-delegation**: For moderate/heavy tasks, the main agent creates/invoke a subagent with appropriate tools and a timeout
3. **Progress reporting**: Main agent informs the user that a subagent is working, checks progress, and delivers results when done

**Implementation:**

- Add `estimated_duration` field to tool annotations or a simple heuristic (tool name → expected range)
- Main agent system prompt includes routing guidance: "For tasks expected to take 10+ seconds, create a subagent"
- `subagent_invoke` already supports `max_llm_calls` and `timeout` — these are set based on duration estimate
- No new tools needed — existing `subagent_create` + `subagent_invoke` + `subagent_progress` cover the workflow
- The main agent can poll `subagent_progress` while the subagent works

### 18.3 Self-Evolution (Hermes-Agent Pattern)

Inspired by Hermes-type agents that modify their own behavior, prompts, and tools based on experience. Details to be designed, but high-level goals:

| Capability | Description | Example |
|-----------|-------------|---------|
| **Prompt self-improvement** | Agent refines its own system prompt based on task outcomes | After 5 failed email drafts, update the email-writing prompt template |
| **Tool creation** | Agent creates new tool definitions (Python code) for repetitive tasks | "I keep formatting JSON the same way — let me create a `json_format` tool" |
| **Skill self-improvement** | Agent improves existing skills based on feedback | Better research queries after user corrections |
| **Memory consolidation** | Agent periodically revisits and consolidates its long-term memory | Merge related memories, delete obsolete ones, create insight summaries |
| **Behavioral adaptation** | Agent adjusts its behavior based on user preferences | Learns user prefers brief responses, adjusts style |

**Design considerations (to be finalized):**

- Self-modifications must be auditable (log all changes, allow rollback)
- Prompt changes should be diff-based, not wholesale replacements
- Tool creation should follow the existing `skill_create` pattern (generates SKILL.md + optional scripts)
- Safety rails: destructive self-modifications require approval (HITL for tool creation, auto-approve for prompt tuning if non-destructive)

### 18.x Implementation Priority

| # | Task | Priority | Depends on |
|---|------|----------|-----------|
| 33 | `TriggerManager` + `trigger_create/list/delete` tools + cron scheduling | High | — |
| 34 | Webhook trigger endpoint (`POST /webhook/{trigger_id}`) | High | #33 |
| 35 | File watch triggers (`watchfiles` on directory) | Medium | #33 |
| 36 | Duration estimation heuristic (tool annotations or LLM-based) | Medium | — |
| 37 | Auto-delegation system prompt guidance + routing logic | Medium | #36 |
| 38 | Self-evolution design document | High | — |
| 39 | Prompt self-improvement mechanism | Medium | #38 |
| 40 | Tool creation from agent (auto `skill_create`) | Low | #38 |
| 41 | Memory consolidation agent (periodic revisit) | Medium | — |
| 42 | Behavioral adaptation (user preference learning) | Low | #39, #41 |

---

## Phase 11: Subagent V1 — ✅ DONE

SQLite work_queue-backed coordination with supervisor pattern. Full design in `docs/SUBAGENT_RESEARCH.md`.

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/sdk/subagent_models.py` | 98 | `AgentDef`, `SubagentResult`, `TaskStatus`, `TaskCancelledError`, `MaxCallsExceededError`, `CostLimitExceededError` |
| `src/sdk/work_queue.py` | 254 | `WorkQueueDB` (aiosqlite, per-user at `data/private/subagents/work_queue.db`) |
| `src/sdk/middleware_progress.py` | 85 | `ProgressMiddleware` (progress updates, doom loop detection) |
| `src/sdk/middleware_instruction.py` | 58 | `InstructionMiddleware` (cancel signal, course-correction injection) |
| `src/sdk/coordinator.py` | 327 | `SubagentCoordinator` (create/update/invoke/cancel/instruct/delete) |
| `tests/sdk/test_subagent_v1.py` | — | 38 tests (all passing) |

### 8 V1 Tools (in `src/sdk/tools_core/subagent.py`)

| Tool | Purpose |
|------|---------|
| `subagent_create` | Create AgentDef, persist to disk |
| `subagent_update` | Amend existing AgentDef (partial update) |
| `subagent_invoke` | Insert task into work_queue + run AgentLoop with middlewares |
| `subagent_list` | List AgentDefs + active tasks |
| `subagent_progress` | Check task status/progress |
| `subagent_instruct` | Inject course-correction into running subagent |
| `subagent_cancel` | Set cancel_requested flag |
| `subagent_delete` | Remove AgentDef + cancel running tasks |

### Key Design Decisions

- **Config frozen at invocation**: `work_queue.config` — amendments don't affect running tasks
- **No recursion**: `disallowed_tools` defaults include all `subagent_*` tools
- **Cost tracking**: `SubagentCoordinator.invoke()` uses `AgentLoop.run()`, wrapped in `asyncio.wait_for(timeout)`
- **Doom loop detection**: Same tool+args called 3x → `progress.stuck = true` + auto-instruction
- **Cancel via flag**: `InstructionMiddleware` checks `cancel_requested` before each LLM call
- **Cost limit**: Checked by `ProgressMiddleware` after each model call

### Deferred to Phase 12+

- DAG dependencies between subagents
- Worker pools / priority queue
- Webhooks / callbacks
- Handoff mode / model-driven routing (`delegate_to_{name}` auto-generation)
- `access_memory` / `access_messages` flags
- Structured output in SubagentResult
- Session resumption / AgentDef versioning

---

## HybridDB — ✅ DONE

`src/sdk/hybrid_db.py` (~1143 lines): SQLite + FTS5 + ChromaDB with journal-based self-healing.

All three domain stores now backed by HybridDB:

| Store | File | Status |
|-------|------|--------|
| `MessageStore` | `src/storage/messages.py` | ✅ HybridDB |
| `MemoryStore` | `src/storage/memory.py` | ✅ HybridDB |
| `AppStorage` | `src/sdk/tools_core/apps_storage.py` | ✅ HybridDB |
| `SubagentScheduler` | `src/subagent/scheduler.py` | ❌ Still raw SQLite |

---

## Disabled Tools (Pending Redesign)

Email (8 tools), contacts (6 tools), and todos (5 tools) are disabled pending redesign. They will be reimplemented as skills using external CLI tools rather than built-in IMAP/database tools:

| Domain | Current | Target |
|--------|---------|--------|
| **Email** | Built-in IMAP/SMTP tools | `gws` skill (Google Workspace CLI) or `m365` skill |
| **Contacts** | Built-in SQLite CRUD | Part of `gws`/`m365` skill, or lightweight built-in |
| **Todos** | Built-in SQLite CRUD | Part of app ecosystem, or lightweight built-in |
| **Calendar** | Doesn't exist | `gws` skill or `m365` skill |

---

## Architecture Research — Agent Loops Compared

### Claw Code (Rust, ultraworkers/claw-code)

- **Agent loop**: `ConversationRuntime<C, T>` — generic ReAct with injectable API client + tool executor
- **Permission**: 3-tier (`ReadOnly` < `WorkspaceWrite` < `DangerFullAccess`) + rule-based policy engine + shell hooks
- **Hooks**: PreToolUse / PostToolUse user shell scripts that can approve/deny/modify
- **MCP**: Full lifecycle (spawn → init → discover → invoke → shutdown), namespaced `mcp__server__tool`, degraded-mode for partial failures
- **Skills**: File-based discovery (`.claw/skills/`), loaded on-demand via `Skill` tool
- **Session**: JSONL per-worktree, auto-compaction at 100K tokens
- **Workers**: State machine (Spawning → TrustRequired → ReadyForPrompt → Running → Finished)
- **Parallel tools**: Sequential (one at a time per turn)
- **Plugin system**: `plugin.json` manifest, subprocess execution

### OpenCode (TypeScript, anomalyco/opencode)

- **Agent loop**: ReAct with subagents via `@mention` and `task` tool
- **Permission**: `allow`/`deny`/`ask` per tool + bash glob patterns
- **Skills**: Same SKILL.md format, discovery-based, loaded by `skill({ name })` tool
- **MCP**: Local (stdio) + Remote (HTTP/OAuth), tools appear as regular tools, lazy loading
- **TUI**: SolidJS terminal UI with tool rendering, permission dialogs, session navigation
- **Session**: SQLite + compaction agents + git snapshots for undo/redo
- **Parallel tools**: Sequential within an agent turn
- **Plugin system**: `@opencode-ai/plugin` SDK with Zod schemas, lifecycle hooks, TUI slots

### Our Executive Assistant (Python)

- **Agent loop**: `AgentLoop` async ReAct with guardrails, handoffs, tracing
- **Permission**: `ToolAnnotations` (readOnly, destructive, idempotent, openWorld) + auto-approval + HITL interrupts
- **Middleware**: `MemoryMiddleware`, `SummarizationMiddleware`, `SkillMiddleware` (discovery-based)
- **MCP**: `MCPToolBridge` — MCP tools registered as `mcp__{server}__{tool}`, degraded-mode, dynamic reload
- **Skills**: Discovery-based — `skills_list` tool with dynamic descriptions, `skills_load` for full content
- **Session**: HybridDB MessageStore + SummarizationMiddleware (no checkpoints)
- **Subagents**: SQLite work_queue + `SubagentCoordinator` + `ProgressMiddleware` + `InstructionMiddleware`
- **Parallel tools**: Classified (parallel_safe / sequential / interrupt), `asyncio.gather()` for safe batch
- **Subagents V2**: Parallel execution, dynamic spawn, agent teams (planned below)
- **Workspaces**: Multi-project isolation with scoped conversation, memory, files, and subagents

---

## Phase 23: Workspaces — Multi-Project Isolation

> An executive assistant handles multiple projects. Each project gets its own Workspace with scoped conversation history, memory, files, subagents, and custom AI instructions. Modeled on Perplexity Spaces + Claude Code project scoping.

**Current state:** One `user_id` = one conversation stream = one memory bank = one flat file directory. Everything bleeds together. The agent searching "Q2 budget" returns facts from "Home Renovation." Files from all projects share one folder. No way to give different AI instructions per project.

**Goal:** Named Workspaces that isolate context, reduce token waste, and make the agent context-aware per project.

### Architecture

```
~/Executive Assistant/
├── Workspaces/
│   ├── Q2 Planning/
│   │   ├── files/              ← budget.xlsx, strategy.md
│   │   ├── conversation.app.db ← scoped chat history
│   │   ├── memory/             ← scoped HybridDB: "Q2 budget is $2.4M"
│   │   ├── subagents/          ← research-agent, writer (workspace-scoped)
│   │   └── instructions.yaml   ← "Respond like a Product Manager. Use AEST."
│   │
│   ├── Home Renovation/
│   │   ├── files/              ← quotes.pdf, floorplan.png
│   │   ├── conversation.app.db
│   │   └── ...
│   │
│   └── Personal/
│       └── ...
│
├── Skills/                     ← global: available to all workspaces
├── Memory/global/              ← user-level facts: "Eddy lives in Melbourne"
├── Subagents/global/           ← user-level agents: research-agent (shared)
└── data/                       ← internal: email, contacts, todos
```

### Scoping Rules

| Resource | Workspace scope | Global scope | Default |
|----------|----------------|-------------|---------|
| **Conversation** | `data/workspaces/{id}/conversation.app.db` | None — always scoped | Workspace |
| **Memory** | `data/workspaces/{id}/memory/` | `data/users/{uid}/global_memory/` | Workspace |
| **Files** | `Workspaces/{name}/files/` | None | Workspace |
| **Subagents** | `data/workspaces/{id}/subagents/` | `data/users/{uid}/subagents/` | Workspace (user-global fallback) |
| **Skills** | — | `Skills/` (always global) | Global |
| **AI Instructions** | Per-workspace `instructions.yaml` | System-wide default | Workspace overrides global |

### LLM Impact: Net Token Reduction

**No additional API calls.** Workspace context is injected into the existing system prompt. The net effect is a token **reduction** for users with multiple projects:

| Factor | Single-session (current) | Multi-workspace (new) |
|--------|-------------------------|----------------------|
| **System prompt** | ~1500 chars (skills + rules) | ~1600 chars (+ workspace name + custom instructions) |
| **Conversation history** | All messages from all topics | Only this workspace's messages |
| **Memory search** | Must filter across all domains | Pre-filtered by workspace |
| **Example: 3 projects, 50 msgs each** | 150 messages in context | 50 messages in context |

The conversation history reduction (150 → 50 messages) saves **far more tokens** than the ~100 extra chars for workspace context. A net win.

### Subagent Scoping (Claude Code Model)

```
Subagent lookup order (highest priority first):
1. Workspace-scoped: data/workspaces/{id}/subagents/
2. User-global:       data/users/{uid}/subagents/

If agent_researcher exists in both → workspace version wins.
If only in user-global → that version is used.
If neither → agent doesn't know about it.
```

Workspace subagents have access to workspace files + memory by default. User-global subagents get current workspace context injected.

### Implementation

| Step | What | Lines |
|------|------|-------|
| 1 | `Workspace` model: id, name, description, custom_instructions, created_at | ~40 |
| 2 | `DataPaths` updated with workspace-scoped paths | ~30 |
| 3 | `workspace_create/list/switch/delete` tools for the agent | ~120 |
| 4 | System prompt includes workspace name + custom instructions | ~20 |
| 5 | Conversation history filtered by workspace_id | ~30 (SQL WHERE clause) |
| 6 | Memory search defaults to workspace scope (`scope` parameter for global) | ~50 |
| 7 | Subagent registry scoped: workspace-first, user-fallback | ~80 |
| 8 | Flutter sidebar: workspace switcher dropdown + "New Workspace" button | ~200 |
| 9 | Flutter WorkspacePanel: shows workspace files, subagents, instructions | ~150 |

### Dependencies

- ✅ `DataPaths` with per-user isolation (exists)
- ✅ `HybridDB` with per-collection scoping (exists)
- ✅ `SubagentCoordinator` with agent defs (exists)
- ✅ Flutter sidebar with icons (exists)
- ❌ `Workspace` model (new)
- ❌ Workspace-scoped conversation/memory/file paths (new)
- ❌ Workspace CRUD tools (new)
- ❌ Flutter workspace switcher (new)

### Edge Cases

| Scenario | Handling |
|----------|----------|
| User deletes workspace | Move files to archive, purge conversation + memory |
| Agent needs cross-workspace info | `memory_search(query, scope="global")` |
| No workspace selected | Auto-create "Default" on first launch |
| Workspace with custom instructions conflicts with system prompt | Workspace instructions appended to system prompt, not replacing it |
| Subagent created in workspace A used in workspace B | User-global agents only. Workspace agents are scoped. |


## Cross-Reference Documents

- [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md) — Data paths, app sharing, deployment models
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Self-hosted .dmg/.exe, hosted container architecture, team layer
- [AGENTS.md](./AGENTS.md) — Build/lint/test commands, coding style, current architecture
- [docs/HYBRIDDB_SPEC.md](./docs/HYBRIDDB_SPEC.md) — HybridDB design specification
- [docs/FLUTTER_UX_PLAN.md](./docs/FLUTTER_UX_PLAN.md) — Flutter UI/UX design system, navigation, screen specs
