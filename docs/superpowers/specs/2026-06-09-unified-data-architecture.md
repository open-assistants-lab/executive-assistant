# Unified Data Architecture — Email, Contacts, Calendar, Todos

## Problem

Email, contacts, and todos are currently three separate SQLite databases with no shared schema, no cross-domain queries, and no external sync. Calendar events don't exist at all. Key issues:

- **IMAP passwords stored in plaintext** — no encryption, no OAuth
- **Email→Contact auto-parsing is dead code** — never wired into sync
- **No external sync** — no Google Contacts, Google Tasks, Todoist, Apple Reminders
- **No full-text search** — bare `LIKE` queries only
- **Three separate SQLite engines per user** — wasteful, no cross-domain JOINs

## Solution

A single **HybridDB** database per user (`data/users/{user_id}/agents.db`) that unifies email, contacts, calendar, and todos. Local storage is the source of truth; external services sync to it via connectors, but **local data stays local unless the user explicitly asks to push it to a connected service**. The system works like Apple Mail/Calendar/Reminders — local-first, sync with multiple accounts (IMAP, Gmail, Google Workspace, etc.), and everything is searchable in one place.

```
data/users/{user_id}/
└── agents.db              ← HybridDB (SQLite + FTS5 + ChromaDB)
    ├── emails             ← unified across all accounts
    ├── contacts           ← local + synced from connectors
    ├── events             ← local + synced from connectors
    ├── todos              ← local + synced from connectors
    ├── accounts           ← connector accounts (IMAP, Gmail, GWS, CalDAV)
    └── sync_log           ← per-account sync state
```

### Account model (unified)

A single `accounts` table stores all connected accounts regardless of provider type:

```sql
CREATE TABLE accounts (
    id              TEXT PRIMARY KEY,
    imap_host       TEXT,                       -- IMAP host (for imap providers)
    imap_port       INTEGER,                    -- IMAP port (for imap providers)
    smtp_host       TEXT,                       -- SMTP host (for imap providers)
    smtp_port       INTEGER,                    -- SMTP port (for imap providers)
    provider        TEXT NOT NULL,              -- "imap", "gmail", "google_workspace", "caldav", "exchange"
    name            TEXT NOT NULL,              -- user-visible label
    email           TEXT NOT NULL,
    auth_type       TEXT NOT NULL,              -- "password", "oauth", "app_password"
    auth_data       TEXT,                       -- encrypted JSON (token, password, etc.)
    status          TEXT DEFAULT 'active',      -- "active", "error", "expired"
    last_sync       INTEGER,
    sync_interval   INTEGER DEFAULT 300,        -- seconds
    created_at      INTEGER NOT NULL
);
```

**Provider types:**

| Provider | Auth | Sync method | Sync scope |
|----------|------|-------------|------------|
| `imap` | Password (encrypted) | IMAP via `imap_tools` | Email only |
| `gmail` | OAuth via ConnectKit | Gmail API | Email + contacts |
| `google_workspace` | OAuth via `gws` CLI | GWS CLI | Email + contacts + todos + calendar |
| `caldav` | Password (encrypted) | CalDAV via `caldav` library | Calendar only |
| `exchange` | OAuth via ConnectKit | Microsoft Graph | Email + contacts + todos (Future) |

**Email is added via connectors**, not a standalone `email_connect` tool. The connector system handles auth, discovery, and account creation.

### Unified Email Storage

```sql
CREATE TABLE emails (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    folder          TEXT NOT NULL,
    message_id      TEXT NOT NULL,              -- IMAP UID or API message ID
    from_addr       TEXT,
    from_name       TEXT,
    to_addrs        TEXT,
    cc_addrs        TEXT,
    bcc_addrs       TEXT,
    subject         TEXT,
    body_text       LONGTEXT,                  -- HybridDB FTS content
    body_html       TEXT,
    timestamp       INTEGER NOT NULL,
    received_at     INTEGER NOT NULL,
    in_reply_to     TEXT,
    thread_id       TEXT,
    references      TEXT,
    read            INTEGER DEFAULT 0,
    flagged         INTEGER DEFAULT 0,
    has_attachments INTEGER DEFAULT 0,
    attachments     TEXT,                      -- JSON metadata (filename, size, type)
    labels          TEXT,                      -- JSON array of labels/tags
    synced_at       INTEGER,
    UNIQUE(account_id, message_id)
);
```

HybridDB auto-indexes `body_text` (LONGTEXT) for FTS5, making email content searchable alongside contacts and todos.

### Unified Contacts Storage

```sql
CREATE TABLE contacts (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    phone           TEXT,
    company         TEXT,
    notes           LONGTEXT,                  -- HybridDB FTS content
    photo_url       TEXT,
    source          TEXT NOT NULL,              -- "local", "gmail", "google_workspace", "imap_auto"
    source_id       TEXT,                       -- external service contact ID (for sync)
    account_id      TEXT,                       -- which account synced this (NULL for local)
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER
);
```

**How contacts are populated:**

| Source | Auto/manual | When |
|--------|-------------|------|
| `local` | Manual via `contacts_add` | User creates manually |
| `imap_auto` | Auto from emails during IMAP sync | On every IMAP sync |
| `gmail` | Auto from Gmail contacts API | On Gmail connector sync |
| `google_workspace` | Auto from Google Contacts API | On GWS connector sync |

**Deduplication:** Contacts are merged by email address across sources. If `john@example.com` exists from IMAP auto-parse and also from Google Contacts, the Google Contacts version takes priority (richer data). Merge logic preserves all fields:
- Fields with non-null values from higher-priority source win
- Fields with null from higher-priority source fall back to lower-priority source
- `source` field stores a single value — the highest-priority source. On merge, it's updated to the higher-priority source.
- `source_id` and `account_id` are updated to the higher-priority source's values on merge.

### Unified Todos Storage

```sql
CREATE TABLE todos (
    id              TEXT PRIMARY KEY,
    content         LONGTEXT,                  -- HybridDB FTS content
    status          TEXT DEFAULT 'pending',    -- "pending", "in_progress", "completed", "cancelled"
    priority        INTEGER DEFAULT 0,
    due_date        INTEGER,                   -- unix timestamp for the deadline
    remind_at       INTEGER,                   -- unix timestamp for the reminder alert
    completed_at    INTEGER,
    email_id        TEXT,                      -- FK to emails.id (if extracted from email)
    contact_id      TEXT,                      -- FK to contacts.id (if assigned to contact)
    source          TEXT NOT NULL,              -- "local", "google_workspace", "gmail_extracted"
    source_id       TEXT,                       -- external service todo ID (for sync)
    account_id      TEXT,                       -- which account synced this (NULL for local)
    list_name       TEXT,                       -- for services with multiple lists (GWS, Todoist)
    repeat_rule     TEXT,                       -- JSON: {"frequency":"weekly","interval":1,"days":[1]}
    tags            TEXT,                       -- JSON array: ["work", "follow-up"]
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER
);
```

**Reminder mechanism:**

The `remind_at` field (separate from `due_date`) determines when the user should be alerted. For events, `remind_before` stores seconds before start (converted to an absolute time for scheduling). A lightweight reminder scheduler runs alongside the sync workers:

```python
class ReminderScheduler:
    """Check for upcoming reminders and deliver notifications."""

    def __init__(self, agents_db: AgentsDB):
        self.db = agents_db

    async def check(self) -> list[dict]:
        """Return todos and events with pending reminders within the next 5 minutes."""
        now = int(time.time())
        window = now + 300
        results = []

        # Todos with explicit remind_at
        results.extend(await self.db.query("todos",
            where=f"remind_at IS NOT NULL AND remind_at <= {window} AND remind_at > {now} "
                  f"AND status IN ('pending', 'in_progress')",
        ))

        # Events where start_time - remind_before is within the window
        results.extend(await self.db.query("events",
            where=f"remind_before IS NOT NULL "
                  f"AND (start_time - remind_before) <= {window} "
                  f"AND (start_time - remind_before) > {now} "
                  f"AND status = 'confirmed'",
        ))

        return results

    async def deliver(self, reminder: dict) -> None:
        """Deliver reminder based on available channels."""
        # Channel 1: Console/CLI output (shown on next agent interaction)
        # Channel 2: Desktop notification (via shell_execute with terminal-notifier or osascript)
        # Channel 3: Push notification (via connector if available)
        ...
```

**Recurrence (`repeat_rule`):**

JSON field supporting Apple Reminders-style recurrence:

```json
{"frequency": "daily", "interval": 1}
{"frequency": "weekly", "interval": 1, "days": [1]}           // every Monday
{"frequency": "weekly", "interval": 2, "days": [1, 3]}        // every 2 weeks, Mon+Wed
{"frequency": "monthly", "interval": 1, "day": 15}            // 15th of every month
{"frequency": "yearly", "interval": 1, "month": 3, "day": 15} // March 15th yearly
```

When a recurring todo is completed, the system auto-creates the next instance:
1. Complete current todo (set `status='completed'`, `completed_at=now`)
2. Calculate next date from `repeat_rule` + current `due_date`
3. Insert new todo row with the next date, `status='pending'`, `source='local'`
4. The new todo's `remind_at` is set based on the next date (default: 15 minutes before)

**Smart lists (virtual, not stored):**

FTS5 + HybridDB search enables smart list queries without dedicated columns:

| Smart list | Query |
|-----------|-------|
| Overdue | `due_date < now AND status IN ('pending','in_progress')` |
| Due today | `due_date = today` |
| Has reminder | `remind_at IS NOT NULL AND remind_at <= window AND status IN ('pending','in_progress')` |
| This week | `due_date BETWEEN start_of_week AND end_of_week` |
| High priority | `priority >= 3 AND status = 'pending'` |

### Unified Calendar Events Storage

```sql
CREATE TABLE events (
    id              TEXT PRIMARY KEY,
    title           LONGTEXT,                  -- HybridDB FTS content
    description     LONGTEXT,                  -- HybridDB FTS content
    location        TEXT,
    start_time      INTEGER NOT NULL,          -- unix timestamp
    end_time        INTEGER NOT NULL,          -- unix timestamp
    all_day         INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'confirmed',  -- "confirmed", "tentative", "cancelled"
    visibility      TEXT DEFAULT 'default',    -- "default", "public", "private"
    remind_before   INTEGER,                   -- seconds before start (e.g., 600 = 10 min)
    organizer       TEXT,                      -- email of organizer
    attendees       TEXT,                      -- JSON array: [{"email":"...","status":"accepted"}]
    recurrence_rule TEXT,                      -- RFC 5545 RRULE string
    recurring_event_id TEXT,                   -- original event ID for recurrence exceptions
    source          TEXT NOT NULL,              -- "local", "google_workspace", "caldav"
    source_id       TEXT,                       -- external service event ID (for sync)
    account_id      TEXT,                       -- which account synced this (NULL for local)
    calendar_name   TEXT,                       -- for services with multiple calendars
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER
);
```

**How events are populated:**

| Source | Auto/manual | When |
|--------|-------------|------|
| `local` | Manual via `event_create` | User creates via tool |
| `google_workspace` | Sync from Google Calendar | On GWS connector sync |
| `caldav` | Sync from CalDAV server (iCloud, Fastmail) | On CalDAV connector sync |

**Calendar tools (new):**

| Tool | Signature | Annotations | Description |
|------|-----------|-------------|-------------|
| `event_list` | `date_from?, date_to?, limit=50, user_id` | `read_only=True, idempotent=True` | List events in a date range |
| `event_get` | `event_id, user_id` | `read_only=True, idempotent=True` | Get single event details |
| `event_create` | `title, start_time, end_time, description?, location?, user_id` | _(none)_ | Create a new event |
| `event_update` | `event_id, title?, start_time?, end_time?, description?, user_id` | _(none)_ | Update event fields |
| `event_delete` | `event_id, user_id` | `destructive=True` | Delete an event |
| `event_search` | `query, date_from?, date_to?, limit=20, user_id` | `read_only=True, idempotent=True` | FTS search on title + description |
| `event_respond` | `event_id, response, user_id` | _(none)_ | Accept/decline/tentative for an invitation |

**Calendar → Todo integration:** Events with attendees where the user is a participant → the agent can auto-suggest follow-up todos after the event ends.

### Sync Architecture

Each connector account has a **sync worker** that runs periodically (configurable interval per account):

```
┌─────────────────────────────────────────────────────┐
│                    agents.db                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌──────┐ │
│  │  emails  │  │ contacts │  │  todos   │ │events│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ └──┬───┘ │
│       │              │             │           │     │
│       ▼              ▼             ▼           ▼     │
│  ┌─────────────────────────────────────────┐         │
│  │              sync_log                    │         │
│  │  account_id, table, last_token, state   │         │
│  └─────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
        │              │             │           │
        ▼              ▼             ▼           ▼
   ┌────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐
   │  IMAP  │   │  Gmail   │   │  GWS     │   │ CalDAV │
   │  sync  │   │  API     │   │  CLI     │   │  sync  │
   └────────┘   └──────────┘   └──────────┘   └────────┘
```

The `sync_log` table tracks checkpoint state per account per table:

```sql
CREATE TABLE sync_log (
    account_id  TEXT NOT NULL,
    table_name  TEXT NOT NULL,                 -- "emails", "contacts", "events", "todos"
    last_token  TEXT,                          -- pagination cursor or UID
    last_sync   INTEGER NOT NULL,
    state       TEXT DEFAULT 'idle',           -- "idle", "syncing", "error"
    error_msg   TEXT,
    PRIMARY KEY (account_id, table_name)
);
```

**Sync workflow:**
1. Sync worker picks up an account
2. Reads `last_token` from `sync_log` for each table the provider supports
3. Calls provider to fetch changes since that token
4. Upserts into the unified `agents.db` tables
5. Updates `last_token` and `last_sync`
6. For IMAP: also auto-inserts contacts into `contacts` with `source='imap_auto'`

**Sync is one-directional by default (external → local):** The sync worker pulls changes from the external service into `agents.db`. Local data (`source='local'`) is never pushed to connected services unless the user explicitly requests it (see "Writeback" below).

**Writeback (local → external) is opt-in, per-item:** If the user says "move this todo to Google Tasks," the agent changes the todo's `source` to `google_workspace` and sets `source_id` to the new external ID after creating it. The next sync cycle then recognizes it as an external item. Without this explicit step, local data stays local. This matches Apple's model — creating a reminder on your iPhone doesn't push it to Google Calendar unless you explicitly share it.

### Connector Integration

**Existing connectors (ConnectKit, `gws` CLI)** are the entry point for adding accounts. The flow:

1. User connects via connector endpoint (e.g., `POST /connectors/connect` with Gmail OAuth)
2. Connector creates an account entry in `agents.db.accounts`
3. Connector starts an initial sync (first batch)
4. Background sync scheduler picks it up for periodic sync

**New account types added via connectors:**

| Connector | Currently | After this change |
|-----------|-----------|-------------------|
| ConnectKit OAuth | Gmail API tools | Gmail API sync → emails + contacts to agents.db |
| `gws` CLI | Ad-hoc CLI calls | GWS sync → emails + contacts + todos to agents.db |
| IMAP connector | `email_connect` tool (hardcoded) | IMAP connector account → IMAP sync to agents.db |

### Search

HybridDB provides per-table FTS5 + ChromaDB. Cross-domain search queries each table and merges results:

```python
# Search across all data domains
def search_all(agents_db: HybridDB, query: str, limit: int = 20) -> dict:
    """Search emails, contacts, events, and todos. Return merged results."""
    results = {}
    fts_columns = {
        "emails": "body_text",
        "contacts": "notes",
        "events": "title",
        "todos": "content",
    }
    for table, column in fts_columns.items():
        rows = agents_db.search(table, column, query, mode="hybrid", limit=limit)
        results[table] = rows
    return results
```

This replaces the current per-domain `LIKE`-only search with FTS5 + ChromaDB semantic search across all four data domains.

### Removal of `email_connect` tool

The `email_connect` tool is removed. IMAP accounts are added through the connector system instead:
- `POST /connectors/connect` with IMAP params (email, password, host, port)
- The IMAP connector stores encrypted credentials in `agents.db.accounts`
- The IMAP sync worker handles periodic sync via the existing `imap_tools` library

### Tools update

**Email tools** (`email_list`, `email_get`, `email_search`, `email_send`): Unchanged API, but backed by `agents.db` instead of `email_db.py`. Accept `account_id` instead of `account_name` (or support both with migration).

**Contacts tools** (`contacts_list`, `contacts_get`, `contacts_add`, `contacts_update`, `contacts_delete`, `contacts_search`): Unchanged API, backed by `agents.db`. Auto-forward to external service if the contact has a `source` that supports writeback (e.g., Google Workspace).

**Todos tools** (`todos_list`, `todos_add`, `todos_update`, `todos_delete`, `todos_extract`): Unchanged API, backed by `agents.db`. Auto-forward to external service if the todo has a `source` that supports writeback.

**Removed:**
- `email_connect` — replaced by connector system
- `email_disconnect` — replaced by connector disconnection
- `email_accounts` — replaced by connector status
- `email_sync` — automatic via sync workers

### Flutter front-end views

The Flutter app provides basic read-only or simple CRUD views for each data domain. The agent remains the primary interface for complex operations (writing emails, triaging inboxes, scheduling across calendars, extracting todos from emails). The Flutter views let the user browse, search, and do quick actions without talking to the agent.

| Domain | Flutter view | Features | Agent handles |
|--------|-------------|----------|---------------|
| **Accounts** | Settings panel | List connected accounts, connect/disconnect providers (Gmail OAuth, IMAP, GWS, CalDAV), re-auth on expiry | Creating new accounts, resolving auth errors |
| **Email** | Inbox list + email detail | Browse folders, read emails, search (FTS), flag/star, mark read | Writing replies, composing new emails, inbox triage, filters, smart search |
| **Contacts** | Contact list + detail | Browse contacts, search (FTS), view name/email/phone/company | Adding contacts from email, merging duplicates, enriching from external services |
| **Calendar** | Week/day view | View events, browse by date range, search (FTS) | Creating/editing/deleting events, scheduling across calendars, finding free slots |
| **Todos** | Todo list | Browse by status (pending/in-progress/completed), search (FTS), quick add | LLM extraction from email, suggesting follow-ups, recurrence scheduling |

**Implementation note:** The Flutter app needs no local database — it queries `agents.db` through REST endpoints (`GET /emails`, `GET /contacts`, `GET /events`, `GET /todos`). The agent writes to `agents.db` through its tools. This keeps the Flutter app thin and the data access path uniform: everything flows through the same API that powers the agent.

### Cross-tool integration (now wired)

| Relationship | How it works | Status |
|-------------|-------------|--------|
| Email → Contact | During IMAP sync, auto-insert contacts from From/To/Cc with `source='imap_auto'` | **WIRED** (was dead code) |
| Email → Todo | `todos_extract` queries `agents.db.emails`, writes to `agents.db.todos` with `email_id` FK | **PRESERVED** |
| Contact → Todo | `todos.contact_id` FK links todos to contacts | **NEW** |
| Email → Event | Auto-suggest calendar event from email (flight confirmation, meeting request) | **NEW** |
| Event → Todo | Auto-suggest follow-up todo after event ends | **NEW** |
| Cross-domain search | Single HybridDB query across emails, contacts, events, and todos | **NEW** |
| Todo writeback | If user says "move this to Google Tasks", change `source` and sync creates it externally | **OPT-IN** |
| Event writeback | If user says "add this to Google Calendar", change `source` and sync creates it externally | **OPT-IN** |
| Contact writeback | If user says "sync this contact", change `source` and sync creates it externally | **OPT-IN** |

### Migration

**No migration.** The three legacy DBs are deleted. The new `agents.db` starts empty. Users reconnect their accounts via connectors and data is fetched fresh from the server. This avoids the complexity of schema mapping and data transformation from the old per-domain SQLite files. Legacy paths (`Email/emails.db`, `Contacts/contacts.db`, `Todos/todos.db`) are deleted on first access of the new system.

### Implementation plan

1. `src/storage/agents_db.py` — `AgentsDB` class wrapping HybridDB with schema creation, cleanup of legacy DB paths
2. `src/sdk/tools_core/email_db.py` — Rewrite to use `AgentsDB` instead of standalone SQLite
3. `src/sdk/tools_core/contacts_storage.py` — Rewrite to use `AgentsDB`
4. `src/sdk/tools_core/todos_storage.py` — Rewrite to use `AgentsDB`
5. `src/sdk/tools_core/email_sync.py` — Add auto-contact-insert during sync (wire the dead code)
6. `src/connectors/imap.py` — IMAP connector that creates accounts + runs sync workers
7. `src/sync/scheduler.py` — Background sync scheduler managing per-account workers
8. Remove `email_connect`, `email_disconnect`, `email_accounts`, `email_sync` tools
9. REST endpoints for Flutter views (`GET /emails`, `GET /contacts`, `GET /events`, `GET /todos`)
10. Tests in `tests/storage/test_agents_db.py`, `tests/sdk/test_email_new.py`