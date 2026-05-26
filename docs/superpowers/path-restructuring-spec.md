# Path Restructuring Spec

## Design Context

This spec was developed during an autoresearch implementation session.
The conversation that shaped it:

### Triggers

1. **Autoresearch needed git** — the `ResearchLoop` used in-memory backups but the workspace is git-versioned. Git branch isolation (branch → eval → merge/discard) is crash-safe and supports multi-file experiments, but targets (prompts, skills, subagent configs) were spread across `~/Executive Assistant/` and `data/` — no single repo.
2. **Path split** — user data lived under `data/users/{id}/` (configurable) while workspaces, global memory, and solo skills lived under `~/Executive Assistant/` (hardcoded). Two roots, no git on either.
3. **Multi-tenant mode** — Docker containers per user with team shared volumes. The existing `data/users/{id}/` structure doesn't map naturally to per-container `~/`.

### Key Decisions Made

| Decision | Why |
|---|---|
| **Single root at `~/Executive Assistant/`** | Consolidates all user data under one tree, one `.git` |
| **Configurable via `ea_root`** | Multi-tenant containers can set a different root per tenant |
| **UUID workspaces** | Eliminates name collision between user and team workspaces; rename doesn't change directory path |
| **Lowercase → uppercase subdirs** | Skills, Subagents, Files, Memory for consistency across scopes |
| **Team volume at `{ea_team_root}/{id}/` or `~/EA/Teams/{id}/`** | Configurable for server-side, client-side fallback |
| **AGENTS.md replaces `settings.agent.system_prompt`** | Same seed pattern as skills; editable by user; removes hardcoded string from config |
| **Prompt order is resequencable** | `PROMPT_ORDER` setting controls injection sequence of user/workspace/team sections |
| **User → workspace → team priority** | User prompt → user skills → ws prompt → ws skills → team prompt → team skills → team ws prompt → team ws skills |
| **Seeding from `src/prompt_seed/AGENTS.md` and `src/skills_seed/`** | Identical mechanism — first-run copy, marker file prevents re-seed |

### What Stays in `data/`

Project-level data only: model cache, logs, traces, templates, job scheduler DBs.

Everything user-level moves to `~/Executive Assistant/`.

---

## Goals

1. Consolidate all user data under `~/Executive Assistant/` — single root, single `.git`
2. Cleanly separate user, team, and workspace scopes
3. Support per-container `.git` for autoresearch versioning
4. Replace `data/users/{id}/`, `data/teams/{id}/`, and split `~/...`/`data/...` with a unified tree
5. Keep all existing tool names and APIs identical — pure infrastructure change

---

## 1. Directory Layout

### Solo mode (desktop / single-user container)

```
~/Executive Assistant/
├── AGENTS.md              # User prompt (was data/users/{id}/config/prompt.txt)
├── Skills/                # User-level skills (was data/users/{id}/skills/)
├── Subagents/             # User-level subagents (was data/users/{id}/subagents/)
├── Teams/                 # (empty in solo mode)
├── Workspaces/
│   └── {workspace_id}/
│       ├── Skills/        # ⬆ upper (was lowercase)
│       ├── Subagents/     # ⬆ upper (was lowercase)
│       ├── Files/         # ⬆ upper (was lowercase)
│       ├── Memory/        # ⬆ upper (was lowercase)
│       ├── conversation.app.db
│       └── .mcp.json
├── Memory/
│   └── global/            # Cross-workspace memory
├── Email/
│   ├── emails.db
│   └── gmail_cache/
├── Contacts/
│   └── contacts.db
├── Todos/
│   └── todos.db
├── Conversation/
│   ├── messages.db
│   └── vectors/
├── Research/              # Experiment results (was data/private/research/)
├── Companion/
│   ├── notifications.db
│   └── memory.db
├── config.yaml            # User EA config
└── .mcp.json
```

### Team mode (Docker multi-user)

```
User container (~/Executive Assistant/):
├── AGENTS.md              # User's personal prompt
├── Skills/                # User's personal skills
├── Subagents/             # User's personal subagents
├── Workspaces/            # User's personal workspaces
├── Memory/global/
├── Email/
├── Contacts/
├── Todos/
└── ...                    # Same structure as solo

Shared team volume (configurable: /mnt/ea-teams/{team_id}/ or ~/Executive Assistant/Teams/{team_id}/):
├── AGENTS.md              # Team prompt (overrides user in team context)
├── Skills/                # Team shared skills
├── Subagents/             # Team shared subagents
├── Files/                 # Team file storage
├── Memory/
├── Workspaces/
│   └── {workspace_id}/
│       ├── Skills/
│       ├── Subagents/
│       ├── Files/
│       ├── Memory/
│       ├── conversation.app.db
│       └── .mcp.json
└── .mcp.json
```

- **Client-side (solo)**: team root = `~/Executive Assistant/Teams/{team_id}/`
- **Server-side (multi-tenant)**: team root = `settings.ea_team_root / {team_id}` (e.g., `/mnt/ea-teams/{team_id}/`)

### Multi-tenancy

Same as solo mode — each container gets its own `~/Executive Assistant/`. Teams use a shared volume.

---

## 2. Scope Definitions

**User scope**: data private to one user, at `~/Executive Assistant/`.

**Team scope**: data shared across team members, at `{team_root}/{team_id}/`.

**Workspace scope**: data scoped to one workspace, at either user or team root depending on whether the workspace belongs to a team.

Resolution priority for all scoped lookups: **user → workspace → team** (workspace overrides user by name, team overrides workspace by name).

### UUID Workspaces

Workspace `id` switches from slugified name to UUID:

```python
@dataclass
class Workspace:
    id: str            # UUID, set at creation (never changes)
    name: str          # User-friendly, can be renamed
    description: str = ""
    prompt: str = ""
    model_override: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_name(cls, name: str) -> Workspace:
        import uuid
        return cls(id=str(uuid.uuid4()), name=name.strip(), ...)
```

**Implications:**
- Directory path `~/EA/Workspaces/{uuid}/` — never changes on rename
- No collisions between user and team workspaces
- Existing workspaces with slug IDs keep their IDs (backward compat)
- LLM never shows UUIDs to users — `workspace_list` returns `{name, id}`, LLM uses `id` internally

### Context Injection Order (Configurable)

Current assembly: `base + user_prompt + skills + workspace`

New assembly (default order):
1. **User Prompt** — `## User Instructions\n{~/EA/AGENTS.md}` (seeded from `src/prompt_seed/AGENTS.md` on first run)
2. **User Skills** — skill descriptions from `~/EA/Skills/`
3. **Workspace Prompt** — `## Workspace Instructions\n{ws.prompt}`
4. **Workspace Skills** — skill descriptions from `~/EA/Workspaces/{uuid}/Skills/`
5. **Team Prompt** — `## Team Instructions\n{team_root/AGENTS.md}`
6. **Team Skills** — skill descriptions from `{team_root}/Skills/`
7. **Team Workspace Prompt** — `## Team Workspace Instructions\n{team_ws.prompt}`
8. **Team Workspace Skills** — skill descriptions from `{team_root}/Workspaces/{uuid}/Skills/`

**Resequencable** via a `settings.prompt_order` list:

```python
PROMPT_ORDER: list[str] = [
    "user_prompt", "user_skills",
    "workspace_prompt", "workspace_skills",
    "team_prompt", "team_skills",
    "team_workspace_prompt", "team_workspace_skills",
]
```

Changing the list reorders injection. Any omitted section is skipped.

### Prompt Seeding

`settings.agent.system_prompt` is removed. Instead:

```
src/prompt_seed/AGENTS.md  ──first run──▶  ~/Executive Assistant/AGENTS.md
```

Same pattern as `src/skills_seed/` — a `.prompt_seeded` marker prevents overwrite. The seed file is the new canonical default, editable by users.

---

## 3. Path Resolution (DataPaths)

### Constructor

```python
class DataPaths:
    def __init__(
        self,
        deployment=None,
        user_id=None,
        team_id=None,
        workspace_id=None,
        data_path=None,        # kept for backward compat (cache, logs)
        ea_root=None,          # ~/Executive Assistant/ by default
        ea_team_root=None,     # team volume root, None for solo
    ):
```

### Root

```python
@property
def root(self) -> Path:
    """Primary user data root."""
    return Path(
        self._ea_root
        or settings.ea_root
        or Path.home() / "Executive Assistant"
    )

@property
def team_root(self) -> Path | None:
    """Team volume root. None in solo mode."""
    if not self.team_id:
        return None
    root = self._ea_team_root or settings.ea_team_root
    if root:
        return Path(root) / self.team_id
    # Client-side fallback: ~/Executive Assistant/Teams/{team_id}/
    return self.root / "Teams" / self.team_id
```

### User-scoped

| New Method | Path | Replaces |
|---|---|---|
| `user_prompt_path()` | `root / "AGENTS.md"` | `_user_base() / config/prompt.txt` |
| `user_skills_dir()` | `root / "Skills"` | `skills_dir()` (solo path) |
| `user_subagents_dir()` | `root / "Subagents"` | `global_subagents_dir()` + `subagents_dir()` |
| `user_memory_dir()` | `root / "Memory" / "global"` | `global_memory_dir()` |
| `email_dir()` | `root / "Email"` | `_user_base() / email` |
| `email_db()` | `root / "Email" / "emails.db"` | `_user_base() / email / emails.db` |
| `gmail_cache_dir()` | `root / "Email" / "gmail_cache"` | `_user_base() / gmail_cache` |
| `contacts_dir()` | `root / "Contacts"` | `_user_base() / contacts` |
| `contacts_db()` | `root / "Contacts" / "contacts.db"` | `_user_base() / contacts / contacts.db` |
| `todos_dir()` | `root / "Todos"` | `_user_base() / todos` |
| `todos_db()` | `root / "Todos" / "todos.db"` | `_user_base() / todos / todos.db` |
| `conversation_dir()` | `root / "Conversation"` | `_user_base() / conversation` |
| `conversation_db()` | `root / "Conversation" / "messages.db"` | `_user_base() / conversation / messages.db` |
| `user_apps_dir()` | `root / "Apps"` | `_user_base() / apps` |
| `user_mcp_config()` | `root / ".mcp.json"` | `_user_base() / .mcp.json` |
| `research_dir()` | `root / "Research"` | `data/private/research/` |
| `companion_dir()` | `root / "Companion"` | `_user_base() / companion` |

### Team-scoped

| New Method | Path |
|---|---|
| `team_prompt_path()` | `team_root / "AGENTS.md"` |
| `team_skills_dir()` | `team_root / "Skills"` |
| `team_subagents_dir()` | `team_root / "Subagents"` |
| `team_files_dir()` | `team_root / "Files"` |
| `team_memory_dir()` | `team_root / "Memory"` |
| `team_apps_dir()` | `team_root / "Apps"` |
| `team_contacts_dir()` | `team_root / "Contacts"` |
| `team_todos_dir()` | `team_root / "Todos"` |
| `team_mcp_config()` | `team_root / ".mcp.json"` |

All return `None` when `team_id` is not set.

### Workspace-scoped

```python
def workspace_root(self) -> Path:
    team = self.team_root
    base = team / "Workspaces" if team else self.root / "Workspaces"
    return base / self.workspace_id

def workspace_skills_dir(self) -> Path:    # ⬆ upper S
    return self.workspace_root() / "Skills"

def workspace_subagents_dir(self) -> Path: # ⬆ upper S
    return self.workspace_root() / "Subagents"

def workspace_files_dir(self) -> Path:     # ⬆ upper F
    return self.workspace_root() / "Files"

def workspace_memory_dir(self) -> Path:    # ⬆ upper M
    return self.workspace_root() / "Memory"

def workspace_conversation_path(self) -> Path:
    return self.workspace_root() / "conversation.app.db"

def workspace_cache(self) -> Path:
    return self.workspace_root() / ".file_cache.json"

def versions_dir(self) -> Path:            # stays dotted
    return self.workspace_root() / ".versions"
```

### Kept in `data/` (project-level, not user-level)

| Method | Path | Purpose |
|---|---|---|
| `model_cache_path()` | `{data_path}/cache/models.json` | models.dev registry cache |
| `templates` | `{data_path}/templates` | App templates |
| `logs_dir()` | `{data_path}/logs` | JSONL logs (though actually uses LoggingConfig) |
| `traces_path()` | `{data_path}/traces/traces.jsonl` | Traces |
| `jobs_db_path()` | `{data_path}/jobs.db` | Job scheduler DB |
| `jobs_results_db_path()` | `{data_path}/jobs_results.db` | Job results DB |

`data_path` defaults to `"data"` (project-relative) — unchanged.

### Deprecated / removed

| Method | Removal Reason |
|---|---|
| `_user_base()` | `data/users/{id}/` goes away |
| `user_dir` | Replaced by `root` |
| `skills_dir()` | Split into `user_skills_dir()` / `team_skills_dir()` |
| `global_skills_dir()` | Same as skills_dir, no clearer |
| `global_subagents_dir()` | Replaced by `user_subagents_dir()` |
| `global_memory_dir()` | Replaced by `user_memory_dir()` / `team_memory_dir()` |
| `subagents_dir()` | Replaced by `user_subagents_dir()` |
| `agent_defs_dir()` | Dead code (never called) |
| `user_config_dir()` | Replaced by `user_prompt_path()` |
| `private` (property) | `data/private/` goes away |
| `shared` (property) | `data/shared/` goes away |

Old methods delegate to new ones with a deprecation warning for one release.

### Consolidation target

Currently the workspace base path `~/Executive Assistant/Workspaces/` is hardcoded in **3 places**:
- `paths.py:108` — `DataPaths._workspaces_base()`
- `workspace_models.py:126` — `_default_workspaces_dir()`
- `memory.py:166` — `_list_workspace_ids()`

All three become `DataPaths.root / "Workspaces"`.

---

## 4. Git Strategy

```gitignore
*.db
Memory/
Files/
Email/
Contacts/
Todos/
Conversation/
gmail_cache/
.versions/
.env
*.log
```

`git init` happens once at `~/Executive Assistant/` on first `DataPaths` access in solo mode. `ResearchLoop` checks for `.git` — if absent (team volume, server-side), falls back to in-memory backup.

---

## 5. Migration

One-shot script, gated by `~/.ea_migrated` marker:

```
data/users/{id}/config/prompt.txt         →  ~/Executive Assistant/AGENTS.md
data/users/{id}/skills/{n}/               →  ~/Executive Assistant/Skills/{n}/
data/users/{id}/subagents/                →  ~/Executive Assistant/Subagents/
data/users/{id}/conversation/             →  ~/Executive Assistant/Conversation/
data/users/{id}/memory/                   →  ~/Executive Assistant/Memory/global/
data/users/{id}/email/                    →  ~/Executive Assistant/Email/
data/users/{id}/gmail_cache/              →  ~/Executive Assistant/Email/gmail_cache/
data/users/{id}/contacts/                 →  ~/Executive Assistant/Contacts/
data/users/{id}/todos/                    →  ~/Executive Assistant/Todos/
data/users/{id}/companion/               →  ~/Executive Assistant/Companion/
data/users/{id}/apps/                     →  ~/Executive Assistant/Apps/
data/users/{id}/.mcp.json                →  ~/Executive Assistant/.mcp.json
data/private/research/                    →  ~/Executive Assistant/Research/
~/EA/Workspaces/{id}/skills/ (lowercase)  →  ~/EA/Workspaces/{id}/Skills/
~/EA/Workspaces/{id}/subagents/            →  ~/EA/Workspaces/{id}/Subagents/
~/EA/Workspaces/{id}/files/                →  ~/EA/Workspaces/{id}/Files/
~/EA/Workspaces/{id}/memory/               →  ~/EA/Workspaces/{id}/Memory/
```

Left in place (not moved): `data/teams/{id}/` — these become `{team_root}/{id}/` on the server side. Solo users don't have teams yet.

After migration, `data/users/{id}/` and `data/private/` are empty and safe to remove.

---

## 6. Implementation Order

1. Update `DataPaths` with new root-based path resolution, old-method backward compat
2. Consolidate the 3 hardcoded `Workspaces/` path references
3. Write migration script
4. Update all callers (coordinator, runner, tools, HTTP routers)
5. Add `.gitignore` + `git init` to solo mode
6. Update `ResearchLoop` to detect git and use branches
7. Fix `research.py` hardcoded `data/private/research/` path
8. Add `ea_root` and `ea_team_root` to settings
9. Update tests
10. Run full test suite

---

## 7. No Visible Changes to Users or LLM

- All tool names stay the same
- All tool parameters stay the same (`scope="user"` still works)
- The migration is transparent — files move once, paths are aliased
- `AGENTS.md` is the new canonical name for user prompt
