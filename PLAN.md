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
| **8** | Data Architecture + App Sharing + Folder Cleanup | 🔄 Current |
| **9** | Extract & Open Source SDK | 🔲 Future |

**377 SDK tests passing. Agent runs end-to-end on all 3 channels (CLI, HTTP, WebSocket).**

---

## Completed Work

### Phase 7: Tool Migration — ✅ DONE

All 98 tools migrated from LangChain `@tool` to SDK `@tool` in `src/sdk/tools_core/`:

| Module | Tools | Count |
|--------|-------|-------|
| `time.py` | `time_get` | 1 |
| `shell.py` | `shell_execute` | 1 |
| `filesystem.py` | `files_list`, `files_read`, `files_write`, `files_edit`, `files_delete`, `files_mkdir`, `files_rename` | 7 |
| `file_search.py` | `files_glob_search`, `files_grep_search` | 2 |
| `file_versioning.py` | `files_versions_list`, `files_versions_restore`, `files_versions_delete`, `files_versions_clean` | 4 |
| `todos.py` | `todos_list`, `todos_add`, `todos_update`, `todos_delete`, `todos_extract` | 5 |
| `contacts.py` | `contacts_list`, `contacts_get`, `contacts_add`, `contacts_update`, `contacts_delete`, `contacts_search` | 6 |
| `memory.py` | `memory_get_history`, `memory_search`, `memory_search_all`, `memory_search_insights`, `memory_connect` | 5 |
| `email.py` | `email_connect`, `email_disconnect`, `email_accounts`, `email_list`, `email_get`, `email_search`, `email_send`, `email_sync` | 8 |
| `firecrawl.py` | `scrape_url`, `search_web`, `map_url`, `crawl_url`, `get_crawl_status`, `cancel_crawl`, `firecrawl_status`, `firecrawl_agent` | 8 |
| `browser.py` | `browser_open`, `browser_snapshot`, `browser_click`, `browser_fill`, `browser_type`, `browser_press`, `browser_scroll`, `browser_hover`, `browser_screenshot`, `browser_eval`, `browser_get_title`, `browser_get_text`, `browser_get_html`, `browser_get_url`, `browser_tab_new`, `browser_tab_close`, `browser_back`, `browser_forward`, `browser_wait_text`, `browser_sessions`, `browser_close_all`, `browser_status` | 22* |
| `apps.py` | `app_create`, `app_list`, `app_schema`, `app_delete`, `app_insert`, `app_update`, `app_delete_row`, `app_column_add`, `app_column_delete`, `app_column_rename`, `app_query`, `app_search_fts`, `app_search_semantic`, `app_search_hybrid` | 14 |
| `subagent.py` | `subagent_create`, `subagent_invoke`, `subagent_batch`, `subagent_list`, `subagent_progress`, `subagent_validate`, `subagent_schedule`, `subagent_schedule_cancel`, `subagent_schedule_list`, `subagent_delete` | 10 |
| `mcp.py` | `mcp_list`, `mcp_reload`, `mcp_tools` | 3 |
| `skills.py` | `skills_list`, `skills_load`, `skill_create`, `sql_write_query` | 4 |

*\*browser.py has 22 tools (was 20 in browser_use.py; added `browser_snapshot`, `browser_fill`, `browser_press` replacing `browser_state`, `browser_input`, `browser_keys`; added `browser_hover`, `browser_back`, `browser_forward`; removed `browser_tab_switch`.)*

### Phase 7.5: LangChain Removal — ✅ DONE

- `langchain_adapter.py` — deleted
- `messages.py` — removed `to_langchain()` / `from_langchain()` bridge methods
- `middleware_memory.py` — replaced LangChain imports with SDK provider
- `middleware_summarization.py` — removed LangChain fallback
- `cli/main.py` — rewritten to use SDK runner
- `http/main.py` — lifespan no longer depends on LangChain agent pool
- MCP manager — rewritten to use native `mcp` SDK
- `pyproject.toml` — 7 LangChain deps removed from core (4 moved to `[telegram]` extra)
- `tests/sdk/test_conformance.py` — deleted (LangChain parity tests)
- `tests/sdk/test_messages.py` — removed LangChain interop tests

### Phase 7.6: Browser Tool Replacement — ✅ DONE

- `src/sdk/tools_core/browser.py` — new, using Agent-Browser CLI (Rust, ref-based)
- `src/sdk/tools_core/browser_use.py` — deleted (was Browser-Use CLI, Python-based)
- `native_tools.py` — imports updated, tool names updated

---

## Phase 8: Data Architecture + App Sharing + Folder Cleanup — 🔄 CURRENT

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
| `src/tools/filesystem/tools.py` | HTTP workspace router, Telegram | `src/http/workspace_tools.py` (Telegram pending SDK rewrite) |
| `src/tools/mcp/manager.py` | `sdk/tools_core/mcp.py` | `src/sdk/tools_core/mcp_manager.py` |

After relocating active files, delete:

| Directory | What's Left After Relocation |
|-----------|------------------------------|
| `src/tools/` | Nothing — delete entirely |
| `src/agents/` | Still active (LangChain-based but in use) — blocked on Telegram SDK rewrite |
| `src/llm/` | Still active (LangChain imports) — blocked on Telegram SDK rewrite |
| `src/middleware/` | Still active (LangChain imports) — blocked on Telegram SDK rewrite |

**Telegram blocker**: `src/telegram/main.py` still imports from `src/agents/manager.py` and `src/llm/providers.py`. Telegram bot needs a full SDK rewrite before `agents/`, `llm/`, `middleware/` can be deleted. This is a separate future task.

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

## Architecture Research Summary

Four SDKs/protocols studied; key patterns extracted:

### Vercel AI SDK v6 (TypeScript)
- Structured streaming: `text-start/delta/end`, `tool-input-start/delta/end`, `reasoning-start/delta/end`
- Provider escape hatches: `providerOptions` keyed by provider name
- Tool validation: `repairToolCall()` for malformed JSON

### OpenAI Agents SDK (Python)
- Guardrails: Input/output/tool-level with tripwire semantics
- Handoffs as model-driven tools: `transfer_to_{agent}`
- First-class tracing: Typed spans with pluggable processors

### Google ADK (Python)
- Three-tier state scoping: `app:` / `user:` / session-level with delta-commit
- Event compaction: Compress old events into summaries
- Agent-as-tool vs handoff: Different context passing patterns

### MCP Spec (2025-06-18)
- Tool annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Dual-format results: `content` (human) + `structuredContent` (machine)
- Content annotations: `audience` and `priority` per content block

---

## What We Keep

| Component | Reason |
|-----------|--------|
| `config.yaml` structure | Model configuration format already works |
| Per-user SQLite + ChromaDB | Proven, simple, zero-ops |
| All tool implementations | Migrated decorator, not logic |
| HTTP API CRUD endpoints | Router structure stays |
| WebSocket protocol | Contract locked |
| FastAPI + uvicorn | No LangChain dependency |
| `langchain-mcp-adapters` | Small, isolated MCP client (moved to `[telegram]` extra) |

## What We Removed

| Component | Replacement |
|-----------|-------------|
| `langchain` + `langchain-core` | `sdk/messages.py` + `sdk/tools.py` |
| `langchain-ollama` | `sdk/providers/ollama.py` |
| `langchain-openai` | `sdk/providers/openai.py` |
| `langchain-anthropic` | `sdk/providers/anthropic.py` |
| `langgraph` + 4 sub-packages | `sdk/loop.py` |
| `langsmith` | `sdk/tracing.py` |
| `src/sdk/langchain_adapter.py` | Native tools |
| `src/agents/manager.py` | `sdk/runner.py` |
| `src/middleware/` | `sdk/middleware_*.py` |
| `src/llm/providers.py` | `sdk/providers/` |
| `src/storage/checkpoint.py` | Removed (disabled) |

## What Remains (Blocked on Telegram SDK Rewrite)

| Component | Why It's Still Here |
|-----------|---------------------|
| `src/agents/` | Telegram bot imports `agents/manager.py` |
| `src/llm/providers.py` | Telegram bot imports LangChain providers |
| `src/middleware/` | Telegram bot imports old middlewares |
| `src/tools/` (active storage files) | SDK tools import `storage.py` / `db.py` |
| `src/telegram/` | Needs full SDK rewrite (future task) |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Streaming protocol change breaks Flutter | Backward-compat aliases maintained |
| Data path migration breaks existing users | Auto-migration on first run: `data/users/` → `data/private/` |
| Tool migration introduces bugs | Per-domain test suites already passing |
| Provider-specific features leak | `provider_options` keyed by provider name |
| MCP annotation adoption diverges | Follow MCP spec exactly |
| Telegram bot rewrite scope creep | Separate task, not part of Phase 8 |

---

## Cross-Reference Documents

- [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md) — Data paths, app sharing, deployment models
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Self-hosted .dmg/.exe, hosted container architecture
- [AGENTS.md](./AGENTS.md) — Build/lint/test commands, coding style, current architecture