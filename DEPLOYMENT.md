# EA Deployment Architecture

## Overview

Executive Assistant supports two deployment modes:

1. **Self-hosted (Solo)** — Individual installs EA on their primary device. .dmg (macOS) / .exe (Windows) with sandboxed CLIs. Zero terminal needed.
2. **Hosted server (Team)** — Team/enterprise deployment. Each user gets their own container on a shared server. Team-shared data is accessible via read-only mounts.

Both modes share the same codebase. The only difference is where data lives, how CLIs run, and whether the team layer is active.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     SELF-HOSTED (Solo)                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  EA.app / EA.exe                                           │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐ │ │
│  │  │ EA Server    │  │ SQLite +     │  │ Firecrawl CLI     │ │ │
│  │  │ (FastAPI)    │  │ ChromaDB    │  │ (bundled Node)    │ │ │
│  │  │              │  │ (per-user)   │  │                   │ │ │
│  │  │              │  │             │  │ Browser-Use CLI   │ │ │
│  │  │              │  │             │  │ OR Agent-Browser   │ │ │
│  │  │              │  │             │  │ (bundled Rust)    │ │ │
│  │  │              │  │             │  │                   │ │ │
│  │  │              │  │             │  │ Playwright +      │ │ │
│  │  │              │  │             │  │ Chromium           │ │ │
│  │  └──────────────┘  └─────────────┘  └──────────────────┘ │ │
│  │                                                             │ │
│  │  data/private/                                             │ │
│  │  ├── email/emails.db                                       │ │
│  │  ├── contacts/contacts.db                                  │ │
│  │  ├── todos/todos.db                                        │ │
│  │  ├── conversation/messages.db                             │ │
│  │  ├── memory/                                               │ │
│  │  ├── skills/                                               │ │
│  │  ├── .mcp.json                                             │ │
│  │  └── workspace/                                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Desktop 2 │  │  Laptop  │  │  Phone   │                       │
│  │ (thin    │  │ (thin    │  │ (thin   │  ── All connect via    │
│  │  client) │  │  client) │  │  client)│     mesh VPN / LAN    │
│  └──────────┘  └──────────┘  └──────────┘     to primary       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      HOSTED SERVER (Team)                        │
│                                                                  │
│  ┌────────────────────────────────┐  ┌────────────────────────┐ │
│  │  Admin Panel (open source)     │  │  Traefik / Nginx      │ │
│  │  - User management             │  │  - TLS termination     │ │
│  │  - API key management          │  │  - Reverse proxy       │ │
│  │  - Team data management        │  │  - Per-user routing    │ │
│  │  - Audit logs                  │  │                        │ │
│  │  - Cost tracking              │  │                        │ │
│  └────────────────────────────────┘  └────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Alice's       │  │ Bob's        │  │ Carol's       │  ...   │
│  │ Container     │  │ Container    │  │ Container     │         │
│  │ ┌────────────┐│  │ ┌────────────┐│  │ ┌────────────┐│         │
│  │ │EA Server   ││  │ │EA Server   ││  │ │EA Server   ││         │
│  │ │SQLite+Chrom││  │ │SQLite+Chrom││  │ │SQLite+Chrom││         │
│  │ │Agent-Browse││  │ │Agent-Browse││  │ │Agent-Browse││         │
│  │ │Firecrawl   ││  │ │Firecrawl   ││  │ │Firecrawl   ││         │
│  │ │(self-host) ││  │ │(self-host) ││  │ │(self-host) ││         │
│  │ └────────────┘│  │ └────────────┘│  │ └────────────┘│         │
│  │ data/private/ │  │ data/private/ │  │ data/private/ │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                   │
│         └──────────────────┴──────────────────┘                   │
│                            │                                      │
│                ┌───────────┴───────────┐                          │
│                │  Team Data (read-only │                          │
│                │  mount from admin)    │                          │
│                │  data/teams/{id}/     │                          │
│                └───────────────────────┘                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Shared Services                                          │   │
│  │ ├── Firecrawl (self-hosted Docker — shared instance)     │   │
│  │ ├── Redis (session management, rate limiting)             │   │
│  │ └── Headscale (mesh VPN for desktop proxy, optional)    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Three-Layer Data Model

All data is organized in three layers, resolved in order: **personal → team → system** (first match wins for overrides; merged views are agent-side).

| Layer | Path | Owner | Mutability | Example |
|-------|------|-------|------------|---------|
| **System** | `src/skills/`, `src/assets/` | Shipped with app | Immutable | Built-in skills, default templates |
| **Team** | `data/teams/{team_id}/` | Team admins (via admin panel) | Admin-write, member-read | Org skill overrides, shared apps, team contacts |
| **Personal** | `data/private/` | Individual user | Fully editable | Personal skills, personal todos, conversation history |

### Why three layers (not two, not four)

**Two layers (personal + system) is insufficient for teams.** The original design before team support had exactly two layers. The problem: system skills are too rigid (can't customize without forking the repo), and personal data is too fragmented (every user reinvents the same company-specific skill). Teams need a middle layer where an admin can say "our org uses this pandoc skill" without forking the codebase or having every user set it up individually.

**Four layers would add org → team → personal → system.** This was considered but rejected because:
- EA is per-team, not per-organization (no multi-team org management yet)
- Adding an org layer would require org-provisioning, org admins, org-team relationships — a full multi-tenant system that's out of scope
- If org support is needed later, it fits naturally as a new layer above team with the same read-only mount pattern

### Why personal → team → system resolution order

**Personal wins because the user explicitly chose to override.** If a user created a personal skill named `pandoc`, they did so because the team/system version didn't meet their needs. Silently ignoring their override would break their workflow.

**Team wins over system because team context is more specific.** A team's "how we deploy" skill is more relevant than the generic system default. The system layer is a fallback for when neither personal nor team has an answer.

### Why team data is read-only in user containers

SQLite uses file-level locking for writes. When two processes write to the same `.db` file simultaneously, one gets `SQLITE_BUSY` or, worse, corruption on network filesystems (NFS doesn't support POSIX file locks reliably). In team deployment, multiple user containers would all read `data/teams/{team_id}/contacts/contacts.db` — if any of them could also write, we'd have a concurrent-write problem.

**Alternative considered: PostgreSQL for team data.** This would support concurrent writes, but it adds operational complexity (a database server, migrations, backups, connection pooling) for a feature that most teams don't need heavy write throughput on. Team contacts/todos/memory are read-heavy, write-light — typically updated by an admin a few times per day. PostgreSQL is overkill.

**Alternative considered: SQLite WAL mode with retry.** WAL mode allows concurrent readers with one writer, but it still requires a single writer. We'd need a distributed lock or leader election to decide which container is the writer — adding complexity without solving the fundamental "who writes?" question.

**Read-only mount is the simplest solution that works:** the admin service is the single writer. User containers never lock the file for writing. Zero concurrent-write risk. Zero additional infrastructure.

In **solo deployment**, the team layer doesn't exist (`team_id=None`). All team tools are unregistered. Every tool operates on personal data only.

In **team deployment**, the team layer is a **read-only mount** in each user's container. Only the admin container (or admin API) can write to team data. This eliminates SQLite concurrent-write issues — each user container reads team data, never writes it.

---

## Team Identity: Admin-Provisioned

Team membership is determined at **container provisioning time**, not at runtime:

```yaml
# docker-compose.alice.yml — set by admin when creating the container
services:
  alice-ea:
    image: executive-assistant:latest
    environment:
      - EA_DEPLOYMENT=team
      - EA_TEAM_ID=engineering    # Admin sets this. Baked into container.
```

### Why admin-provisioned (not JWT or config file)

**The container IS the identity boundary.** In EA's deployment model, each user gets their own Docker container with their own filesystem, SQLite databases, and process space. There is no shared application server where multiple users hit the same process. This means:

- There is no "switch user" flow — Alice's container only ever serves Alice
- There is no "switch team" flow within a running container — the team assignment is part of the container spec
- Adding JWT claims or auth protocols would solve a problem that doesn't exist (multi-user single-process), while adding complexity (token rotation, expiry, revocation)

**Rejected alternatives:**

| Approach | Why rejected |
|----------|-------------|
| **JWT `team_id` claim** | Solves multi-user single-process auth (which we don't have). Adds JWT issuance, rotation, revocation infrastructure. A container that only serves one user doesn't need dynamic identity. |
| **Config file `team_id`** | No validation — any user can edit `config.yaml` to set `team_id="engineering"` and gain read access to that team's data. Security requires that the admin controls team assignment, not the user. |
| **Environment variable, user-set** | Same problem as config file — user modifies their own `.env`. Read-only mounts prevent writes, but don't prevent a user from pointing their container at a different team's volume. Admin provisioning is the only model where the admin controls both the `EA_TEAM_ID` and the volume mount target. |

**How team changes work**: If Alice moves from engineering to product, the admin destroys Alice's engineering container and creates a new product container with `EA_TEAM_ID=product` and the product team's volume mounted. Alice's personal data (`data/private/`) is preserved by reusing the same personal volume — only the team mount changes.

---

## Data by Category

### Skills

| Layer | Path | Behavior |
|-------|------|----------|
| System | `src/skills/` | Built-in skills, read-only |
| Team | `data/teams/{team_id}/skills/` | Admin-curated, overrides system skills by name |
| Personal | `data/private/skills/` | User-created, shadows team and system by name |

**Already implemented**: `SkillRegistry` supports three layers with deduplication. `skills_list` shows source tag `(built-in)`, `(team)`, `(personal)`.

### Files / Workspace

| Layer | Path | Behavior |
|-------|------|----------|
| System | `src/assets/` | Read-only templates/defaults |
| Team | `data/teams/{team_id}/files/` | Shared workspace, admin-write, member-read |
| Personal | `data/private/workspace/` | Personal files |

### Apps (Structured Data)

| Layer | Path | Behavior |
|-------|------|----------|
| Team | `data/teams/{team_id}/apps/` | Shared databases (project tracker, CRM), admin-write |
| Personal | `data/private/apps/` | Personal apps |

### Contacts

| Layer | Path | Behavior |
|-------|------|----------|
| Team | `data/teams/{team_id}/contacts/` | Org directory, admin-write, member-read |
| Personal | `data/private/contacts/` | Personal contacts |

### Todos

| Layer | Path | Behavior |
|-------|------|----------|
| Team | `data/teams/{team_id}/todos/` | Team tasks, assignable to members, admin-write |
| Personal | `data/private/todos/` | Personal tasks |

### Email

| Layer | Path | Behavior |
|-------|------|----------|
| Personal | `data/private/email/` | Always personal (auth-bound to individual) |

**No team layer**. Email credentials are inherently per-user. A future "shared inbox" feature would be a separate system.

### Memory

| Layer | Path | Behavior |
|-------|------|----------|
| Team | `data/teams/{team_id}/memory/` | Admin-curated org knowledge, admin-write only |
| Personal | `data/private/memory/` | Conversation history, personal insights, auto-generated |

**Team memory is curated, not organic.** Only admins write to team memory (via `team_memory_add` tool). It contains intentional organizational knowledge: "we use React 19", "deploy via ArgoCD", "standup is at 10am". Auto-generated insights from conversations stay personal.

### Why team memory must be admin-only (not auto-generated)

**The core risk is agent pollution across team members.** Our `MemoryMiddleware` auto-extracts facts from conversations — "Alice prefers dark mode", "the client deadline is Friday", "I'm frustrated with the API". If these auto-extracted insights went into team memory, every team member's agent would see them. A single confused extraction (e.g., writing "I prefer dark mode" as a team fact) would affect every agent in the team.

**The blast radius scales linearly with team size.** A 20-person team with auto-written team memory means 20 agents potentially writing incorrect, personal, or contradictory facts that all other agents then read. This is the "dreaming" problem identified in Google's Always-On Memory Agent — without deterministic boundaries, cross-pollinating memories becomes a compliance and correctness nightmare.

**Admin curation solves this by inserting a human gate.** An admin decides what constitutes "team knowledge" vs "personal observation." The cost is manual effort; the benefit is correctness and auditability.

**Alternative considered: member-writable team memory with review queue.** Members could write to team memory, but new entries would be in a "pending" state until an admin approves. This was rejected because:
- It adds UI complexity (review queue, approval workflow)
- Pending facts would be invisible to agents, creating a confusing gap between "I wrote this" and "the team sees this"
- The admin still has to review everything — the manual effort is the same, but now with more latency

**Alternative considered: automated fact classification.** The LLM could classify each extracted fact as "personal" or "team-relevant" before writing. This was rejected because:
- LLM classification is unreliable for edge cases ("deploy via ArgoCD" — is that team knowledge or just one project's choice?)
- A single misclassification still pollutes team memory for everyone
- It doesn't solve the blast radius problem — just shifts it from "always wrong" to "sometimes wrong"

### MCP Config

| Layer | Path | Behavior |
|-------|------|----------|
| System | Bundled defaults | Shared server configs |
| Team | `data/teams/{team_id}/.mcp.json` | Company-wide MCP servers, admin-write |
| Personal | `data/private/.mcp.json` | Personal MCP servers |

`MCPManager` merges configs at startup: personal → team → system. Same namespaced tool names work regardless.

### Agent Config (Policy vs Preference)

| Layer | Path | What it controls |
|-------|------|-----------------|
| Team | `data/teams/{team_id}/config.yaml` | **Policy**: guardrails, cost limits, allowed/disallowed tools, model restrictions |
| Personal | Per-user settings / `config.yaml` | **Preferences**: model choice, tone, summarization settings |

**Team policy always wins.** A user cannot override a guardrail or bypass a cost limit set by team config.

**Why team policy must override personal preferences**: In a team deployment, the organization is responsible for the agent's behavior — cost overruns, data exfiltration, and tool misuse affect the org, not just the individual. If a user could override `blocked_tools: ["shell_execute"]` in their personal config, the team's security policy would be advisory, not enforceable. Team policy must be enforced at the infrastructure level, not merely suggested.

**Enforcement mechanism**: At `AgentLoop` startup, the loop reads team config `allowed_tools`/`blocked_tools` and **excludes blocked tools from the tool registry entirely**. The LLM never sees them — there's no tool to call, so no prompt engineering can bypass the restriction. This is stronger than runtime-checking (which could fail if the LLM tries creative workarounds like calling a different tool that wraps the blocked one).

Team config schema:

```yaml
# data/teams/{team_id}/config.yaml
allowed_tools: ["*"]          # or ["email_*", "contacts_*", "todos_*"]
blocked_tools: ["shell_execute", "files_delete"]  # overrides allowed_tools
max_cost_usd: 10.0           # daily cost limit per user
allowed_models: ["*"]        # or ["ollama:*", "anthropic:claude-3-*"]
guardrails:
  input:
    - type: regex
      pattern: "(?i)(social\\s+security|credit\\s+card)"
      action: block
  output:
    - type: pii_filter
      action: redact
```

---

## Team Tools: Toolset Pattern (Not Scope Parameters)

Instead of adding `scope="personal"` / `scope="team"` to existing tools (10+ tools, typo risk, parameter pollution), team mode registers **separate team tools** that only exist when `team_id` is set.

```python
# Solo mode: only personal tools exist
contacts_list()          # personal contacts

# Team mode: personal tools + team tools
contacts_list()          # personal contacts (unchanged)
team_contacts_list()    # team contacts (read-only for non-admins)
team_contacts_search()  # search team directory
```

### Why toolset pattern beats scope parameter

**The scope parameter approach** would add `scope: Literal["personal", "team"]` (or worse, `scope: str`) to every tool that can access team data — approximately 10+ tools. This was the original proposal.

| Problem | Scope parameter | Toolset pattern |
|---------|----------------|-----------------|
| **Typo risk** | `scope="tema"` silently returns personal results (no error) | `team_contacts_lista()` → tool not found, immediate error |
| **Tool annotations** | Same tool needs different `readOnly`/`destructive` annotations depending on scope. This is impossible in `ToolAnnotations` — they're per-tool, not per-call. | Each tool has one set of annotations that's always correct |
| **Solo compatibility** | Must handle `scope="team"` when team doesn't exist — return empty? Error? Silent fallback? | Team tools simply don't exist. No edge cases. |
| **LLM clarity** | "contacts_list(scope='team')" — the LLM must remember to pass scope. Training data rarely includes scope parameters. | "team_contacts_list()" — the name IS the scope. LLMs handle name-differentiated tools well (similar to how they handle `files_list` vs `files_read`). |
| **Existing tool changes** | Every personal tool gains a new parameter. All tool callers, tests, and middleware must be updated. | Zero changes to existing personal tools. Team tools are additive. |
| **Progressive disclosure** | The LLM sees the same tool name with different modes. It must infer when to use which mode. | The LLM sees two distinct tools. It chooses based on intent — same pattern as `skills_list` vs `skills_search`. |

**The one disadvantage of toolset pattern**: more registered tools (10-15 additional team tools). This slightly increases the tool list the LLM sees. But in solo mode, these tools don't exist — zero overhead. In team mode, the additional tools are self-documenting and serve a clear purpose. The LLM cost of a slightly larger tool list is negligible compared to the cost of scope-related bugs.

| Aspect | `scope=` parameter | Separate team tool |
|--------|-------------------|-------------------|
| Typo risk | `scope="tema"` silently falls through | Tool doesn't exist — immediate error |
| Existing tools | Every tool gains new parameter | Zero changes to existing tools |
| LLM clarity | "contacts_list(scope='team')" ambiguous | "team_contacts_list()" self-documenting |
| Annotations | Same tool, different scopes need different annotations | Each tool has correct annotations naturally |
| Solo compatibility | Must handle `scope="team"` when team doesn't exist | Team tools simply unregistered |

**Team tool registry:**

| Personal Tool | Team Tool | Team Annotations |
|--------------|-----------|-----------------|
| `files_list` | `team_files_list` | `readOnly=True` |
| `contacts_list` | `team_contacts_list` | `readOnly=True` |
| `contacts_search` | `team_contacts_search` | `readOnly=True` |
| `todos_list` | `team_todos_list` | `readOnly=True` |
| `memory_search` | `team_memory_search` | `readOnly=True` |
| — | `team_memory_add` | `destructive=True`, admin-only |
| — | `team_skills_create` | `destructive=True`, admin-only |
| — | `team_contacts_add` | `destructive=True`, admin-only |

### Merged Views: Agent-Side, Not Storage-Side

The original proposal had `contacts_list` "merge both layers, deduplicating by email." This conflates two different operations:

1. **Override resolution** (which skill wins?) — personal → team → system, first match wins. This is unambiguous.
2. **Union merge** (show all contacts from both sources) — which record wins when both have the same email but different phone numbers?

These are fundamentally different operations. Override resolution is for "give me the best version of X." Union merge is for "show me everything from both sources." A fixed "deduplicate by email" in the storage layer can't serve both.

**Why agent-side merge is better:**

| Aspect | Storage-side merge (original) | Agent-side merge (toolset pattern) |
|--------|-------------------------------|-----------------------------------|
| **Dedup rules** | Hardcoded: "prefer personal" always | Per-call: LLM decides based on context |
| **False merges** | Two different people with same email get merged | LLM calls both tools, sees both, decides |
| **Missing data** | Storage silently picks one version, user never sees the alternative | Both versions visible, user can choose |
| **Flexibility** | New merge rule = code change | New merge rule = prompt change |

The LLM merges data by calling both tools:

```python
# Agent wants "all contacts":
# 1. Calls contacts_list() → personal contacts
# 2. Calls team_contacts_list() → team contacts
# 3. Combines, deduplicates by email, prefers personal on conflict
```

Optionally, a convenience tool `all_contacts()` does this in one call:

```python
def all_contacts() -> list[Contact]:
    personal = contacts_list()
    team = team_contacts_list() if team_id else []
    return deduplicate_by_email(personal + team, prefer="personal")
```

**Deduplication preference is per-call, not global.** Sometimes personal wins (user overrode a phone number), sometimes you want merged (show all, tag source). The toolset pattern lets the LLM choose.

---

## DataPaths API

`DataPaths` (in `src/storage/paths.py`) supports both deployment modes:

```python
class DataPaths:
    def __init__(self, deployment=None, data_path=None, user_id=None, team_id=None):
        # team_id=None means solo deployment (team layer disabled)

    # Personal paths (always available)
    def skills_dir(self) -> Path          # data/private/skills/
    def apps_dir(self) -> Path            # data/private/apps/
    def contacts_dir(self) -> Path        # data/private/contacts/
    def todos_dir(self) -> Path           # data/private/todos/
    def memory_dir(self) -> Path          # data/private/memory/
    def workspace_dir(self) -> Path      # data/private/workspace/
    def email_dir(self) -> Path           # data/private/email/

    # Team paths (return None if team_id not set)
    # NOTE: These do NOT auto-mkdir. Directories are created
    # by the admin service, not by user containers.
    def team_skills_dir(self) -> Path | None     # data/teams/{team_id}/skills/
    def team_apps_dir(self) -> Path | None        # data/teams/{team_id}/apps/
    def team_contacts_dir(self) -> Path | None    # data/teams/{team_id}/contacts/
    def team_todos_dir(self) -> Path | None       # data/teams/{team_id}/todos/
    def team_memory_dir(self) -> Path | None      # data/teams/{team_id}/memory/
    def team_files_dir(self) -> Path | None       # data/teams/{team_id}/files/
    def team_mcp_config_path(self) -> Path | None # data/teams/{team_id}/.mcp.json
    def team_config_path(self) -> Path | None     # data/teams/{team_id}/config.yaml
```

**No `data/shared/` directory.** The old `shared/` layer (from Phase 8 multi-user model) is replaced by the `teams/` layer. `shared_apps_dir()` is removed.

### Why `shared/` was removed in favor of `teams/`

The original `data/shared/` directory was designed for a generic multi-user model where any user could write to shared data. This had two problems:

1. **No access control.** `shared/` was world-writable — any user could modify or delete any shared data. This is fine for a two-person startup, dangerous for a 20-person team.
2. **No team scoping.** `shared/` was one global namespace. If the company had two teams, they'd share one `shared/` directory. There was no way to isolate team A's contacts from team B's contacts.

The `teams/` layer fixes both: access is admin-write-only (via read-only mounts), and data is scoped per `team_id`.

**`mkdir` fix**: Team path methods do NOT call `mkdir(parents=True)`. This was a bug — merely accessing a team path created the directory (and potentially an empty SQLite DB if storage auto-initializes). In team mode, if a user's agent calls `team_todos_dir()` before the team has set up todos, an empty directory should NOT be created.

**Why this matters**: Auto-mkdir causes dirty state. An agent referencing `team_todos_dir()` would create `data/teams/{team_id}/todos/` on disk. If the storage layer also auto-initializes an empty `todos.db`, subsequent checks for "does team todos exist?" would say yes — but the database is empty because it was created by accident, not by the admin. Team directories are created by the admin service, not by user containers accessing paths. Calling a team path method on a non-existent directory returns `None` (or the path without creating it — caller checks existence).

`get_paths()` is keyed by `(user_id, team_id)`:

```python
def get_paths(user_id=None, team_id=None) -> DataPaths:
    # Caches per (user_id, team_id) pair
    # In solo mode, team_id is None → team_* methods return None
```

---

## SkillRegistry Three-Layer Support

```python
class SkillRegistry:
    def __init__(self, system_dir="src/skills", user_id=None, team_skills_dir=None):
        self.system_storage = SystemSkillStorage(system_dir)
        self.team_storage = TeamSkillStorage(team_skills_dir) if team_skills_dir else None
        self.user_storage = UserSkillStorage(user_id) if user_id else None

    def get_all_skills(self) -> list[Skill]:
        # Deduplicates by name with order: user → team → system

    def get_skill(self, skill_name: str) -> Skill | None:
        # Resolution: user → team → system

    def get_skill_source(self, skill_name: str) -> str | None:
        # Returns "user", "team", or "system"
```

---

## Progressive Disclosure for Skills

Previous design violated progressive disclosure by injecting all skill names into the `skills_list` tool description on every LLM turn. The agent never *chose* to discover — discovery was forced.

**New flow:**

1. `skills_list()` — returns available skills with name, description, source tag. Agent calls when it needs to discover capabilities.
2. `skills_search(query)` — search for skills matching a keyword. Useful when the catalog grows large.
3. `skills_load(skill_name)` — returns full skill content. No skill content enters context until explicitly loaded.

No skill data is baked into tool definitions or system prompts.

---

## Middleware Behavior

| Middleware | Personal | Team |
|-----------|---------|------|
| `SummarizationMiddleware` | Conversation-level, always personal | N/A |
| `SkillMiddleware` | Reads all 3 layers | Reads all 3 layers |
| `MemoryMiddleware` | Writes personal, reads personal only | Writes personal, reads personal + team (team is read-only) |

Middleware doesn't have "team middleware" — it operates on layered data.

---

## Team Data Write Architecture

**Problem**: SQLite doesn't support concurrent writes from multiple containers. Team data (contacts, todos, apps, memory, skills, config) lives at `data/teams/{team_id}/`, which multiple user containers read simultaneously.

**Solution**: Team data is **read-only in user containers**. Write access goes through the admin service only.

```
┌─────────────────────────────────────────────────────┐
│  Admin Service (single writer)                      │
│  ├── Write: team_contacts, team_todos, team_skills  │
│  ├── Write: team_memory, team_config                │
│  └── Exposes: admin API for CRUD + team_data tools  │
│                                                      │
│  data/teams/{team_id}/  ←── admin writes here       │
│                              │                       │
│              ┌───────────────┼───────────────┐      │
│              ▼               ▼               ▼      │
│         Alice's          Bob's          Carol's     │
│         Container        Container      Container   │
│         (read-only       (read-only     (read-only  │
│          mount)          mount)         mount)      │
└─────────────────────────────────────────────────────┘
```

Per-user container spec:

```yaml
# docker-compose.alice.yml
services:
  alice-ea:
    image: executive-assistant:latest
    restart: unless-stopped
    mem_limit: 2g
    cpus: 2.0
    env_file: users/alice/.env
    volumes:
      - users/alice/data:/app/data/private   # personal data (read-write)
      - teams/engineering/data:/app/data/teams/engineering:ro  # team data (read-only)
    ports:
      - "127.0.0.1:8081:8080"
    environment:
      - EA_DEPLOYMENT=team
      - EA_TEAM_ID=engineering
      - EA_AUTH_JWT_SECRET=${JWT_SECRET}
      - EA_FIRECRAWL_URL=http://firecrawl:3002
      - EA_BROWSER_TOOL=playwright
      - EA_ADMIN_URL=http://ea-admin:8090
```

Note the `:ro` (read-only) mount flag on the team volume. User containers physically cannot write to team data.

---

## Migration: Solo → Team

**Principle: Personal data is portable, team data is attached.** Joining a team adds a layer; leaving removes it. Neither operation mutates personal data.

### Why this principle matters

**Anti-pattern: "promote personal to team" mutations.** When joining a team, a naive approach would be to copy the user's personal contacts into the team directory, or merge their personal memory into team memory. This causes two problems:

1. **Data creep.** Alice's 200 personal contacts (including mom's landline) suddenly appear in the team directory. Team members see irrelevant data, and the team's signal-to-noise ratio degrades.
2. **No clean exit.** If Alice leaves the team, which contacts were "hers" vs "the team's"? They're mixed. You can't cleanly unmerge after a merge.

**The correct model: layers are additive, not mutating.** Joining a team mounts a new read-only layer. Alice's personal data stays personal. The team's data appears as a separate layer. Alice's agent can see both, but they remain distinct. If Alice leaves, the team volume is unmounted — her personal data is untouched.

If Alice wants her personal contacts in the team directory, that's a **deliberate copy** action by the admin, not an automatic merge. The admin chooses which of Alice's contacts are team-relevant.

```
Solo → Team:
1. ea export → alice-backup.tar.gz (existing feature)
2. Admin creates alice's team container, imports backup
3. Alice's personal data is untouched — same data/private/ structure
4. Team layer is additive — admin configures team contacts, skills, config
5. Alice gets EA_TEAM_ID=engineering in her env → team tools appear
6. Zero changes to alice's personal data

Team → Solo (or different team):
1. ea export → alice-backup.tar.gz
2. Remove EA_TEAM_ID from env → team tools disappear
3. Alice's personal data still works independently
4. If joining new team, admin imports into new container with new EA_TEAM_ID

Promoting personal data to team:
1. Admin calls team_contacts_add() with data from user's export
2. Or: admin panel has "promote to team" UI action
3. Data is copied, not moved — personal copy stays
```

---

## Deployment Mode Summary

| | Individual (Solo) | Team |
|---|---|---|
| `get_paths()` | `get_paths(user_id)` | `get_paths(user_id, team_id)` |
| Team layer | Doesn't exist, `team_*` methods return `None` | `data/teams/{team_id}/` (read-only mount) |
| Team tools | Not registered | Registered alongside personal tools |
| Resolution | personal → system | personal → team → system |
| MCP merge | personal + system | personal + team + system |
| Config enforcement | Personal preferences only | Team policy overrides personal |
| Team data writes | N/A | Admin service only (single writer) |
| Admin tools | N/A | `team_memory_add`, `team_contacts_add`, `team_skills_create`, `team_config_update` |
| Skill override | User shadows system | User shadows team, team shadows system |
| Team identity | N/A | `EA_TEAM_ID` env var (admin-provisioned) |

---

## Self-Hosted (Individual)

### Install methods

| Method | Who | How |
|--------|-----|-----|
| **.dmg** (macOS) | Non-technical users | Drag EA.app to Applications. Double-click. Done. |
| **.exe** (Windows) | Non-technical users | Run installer. Done. |
| **pip** | Developers | `pip install -e ".[cli,http]"` then `ea http` |
| **Docker** | Self-hosters | `docker compose up` |

### .app / .exe bundle contents

```
EA.app (macOS)                           EA.exe (Windows)
├── Contents/                             ├── EA/
│   ├── MacOS/ea                          │   ├── ea.exe
│   │   ├── Python runtime                │   │   ├── Python runtime
│   │   └── src/ (your code)              │   │   └── src/ (your code)
│   ├── Resources/                        │   └── resources/
│   │   ├── agent-browser/               │       ├── agent-browser/
│   │   │   └── bin/agent-browser         │       │   └── agent-browser.exe
│   │   │       (standalone Rust binary)  │       │       (standalone Rust binary)
│   │   ├── firecrawl/                   │       ├── firecrawl/
│   │   │   └── bin/firecrawl             │       │   └── firecrawl.exe
│   │   │       (pkg'd Node.js binary)    │       │       (pkg'd Node.js binary)
│   │   └── playwright/                  │       └── playwright/
│   │       └── chromium/                │           └── chromium/
│   │           (headless browser, ~350MB)│               (headless browser)
│   └── data/                             │
│       (user data, symlinked to          │
│        ~/Library/Application Support/)  │
```

### CLI sandboxing

Each CLI is bundled inside the app. The `CLIToolAdapter` resolves binaries by checking bundled paths before system PATH:

```python
class CLIToolAdapter:
    cli_name: str

    def _find_binary(self) -> str | None:
        bundled = self._bundled_path()
        if bundled and os.path.isfile(bundled):
            return bundled
        return shutil.which(self.cli_name)

    def _bundled_path(self) -> str | None:
        if sys.platform == "darwin":
            base = Path(sys.executable).parent.parent / "Resources"
        elif sys.platform == "win32":
            base = Path(sys.executable).parent / "resources"
        else:
            base = Path(sys.executable).parent / "resources"
        return str(base / self.cli_name / "bin" / self.cli_name)
```

### Multi-device (primary + companions)

| Device | Role | Data | CLIs | Connection |
|--------|------|------|------|------------|
| Primary desktop | Full EA | Local SQLite/ChromaDB | Full (firecrawl, browser, shell, filesystem) | Runs EA server |
| Other desktop | Thin client | None | None | Connects to primary via LAN or Tailscale |
| Phone | Thin client | None | None | Connects to primary via Tailscale |

No desktop-to-desktop sync — that path leads to SQLite corruption and merge conflicts.

---

## Hosted Server (Team) — What Changes

| Aspect | Self-hosted | Team/hosted |
|--------|-------------|-------------|
| **Deployment** | Local .dmg | Docker container per user |
| **Data** | Local SQLite/ChromaDB per user | Same — personal data on server, team data read-only mount |
| **Firecrawl** | CLI (local) or API key | Self-hosted Firecrawl Docker (shared) |
| **Browser** | Agent-Browser CLI (local) | Playwright direct (on server) |
| **Filesystem/shell** | Full access to local files | Scoped to container `/app/data/private/` only |
| **Auth** | None (localhost) | JWT (shared secret per user) |
| **Config** | `config.yaml` local | Personal preferences + team policy (team wins) |
| **Team data** | N/A | Read-only mount, admin writes |
| **Audit** | Local JSON logs | Pushed to admin API |
| **Model/API keys** | User's own | Team-shared (admin panel manages) |

### Deployment config detection

```python
# src/config/settings.py
class DeploymentMode(str, Enum):
    SOLO = "solo"      # Individual, local
    TEAM = "team"      # Hosted, per-user container, team layer active

class Settings(BaseSettings):
    deployment: DeploymentMode = DeploymentMode.SOLO
    team_id: str | None = None  # Set by admin at container provisioning

    # Solo settings
    firecrawl_url: str | None = None      # None = use CLI
    browser_tool: str = "agent-browser"   # agent-browser | browser-use | playwright

    # Team settings
    admin_url: str | None = None          # Team admin API
    auth_jwt_secret: str | None = None    # JWT for team mode
```

---

## What's NOT in this Design

1. **Team admin UI / API** — Needs a separate design (auth, role-based access, team CRUD endpoints)
2. **Shared inbox** — Email is per-user by nature; shared inbox is a separate system
3. **Real-time collaboration** — No multi-user writes to same DB at the same time
4. **Team billing / usage aggregation** — Separate concern
5. **Team vault / shared secrets** — Will be designed in a future phase (see `docs/VAULT_DESIGN.md`)
6. **Fork detection** — QoL feature for tracking when a personal skill was forked from a team/system skill; future work
7. **Real-time team data sync** — When team skills/apps/config change, running agents pick up changes on next tool call (not via filesystem watch or push notification)

---

## Implementation Priority

| Phase | What | Mode |
|-------|------|------|
| **Now** | Swap Browser-Use CLI → Agent-Browser in EA | Self-hosted |
| **Now** | Build .dmg / .exe bundle (PyInstaller + bundled CLIs) | Self-hosted |
| **Now** | Dockerize EA (single-user Dockerfile) | Foundation for hosted |
| **Next** | Refactor `DataPaths` — remove `shared/`, add `team_*` methods (no auto-mkdir) | Both |
| **Next** | Implement team toolset pattern — `team_contacts_list`, `team_files_list`, etc. | Team |
| **Next** | Auth layer (JWT) for HTTP API | Both |
| **Next** | Team config enforcement in AgentLoop (tool registry filtering) | Team |
| **Later** | Admin service (team data writer, user management, policy engine) | Hosted |
| **Later** | `ea export` / `ea import` for solo→team migration | Both |
| **Later** | Multi-user compose + Traefik | Hosted |
| **Later** | Litestream for SQLite replication (optional) | Self-hosted with sync |

---

## Already Done

1. ✅ Deleted `apps_storage.py`, migrated to direct `HybridDB` usage in `apps.py`
2. ✅ Fixed `hybrid_db.py` import paths
3. ✅ Refactored `skills_list` — removed `_DynamicSkillListTool` dynamic injection
4. ✅ Added `skills_search` tool for keyword search
5. ✅ `skills_list` and `skills_search` show source tags `(built-in)`, `(team)`, `(personal)`
6. ✅ `DataPaths` — added `team_id` parameter and `team_*` methods
7. ✅ `SkillRegistry` — three-layer support with `TeamSkillStorage` and deduplication
8. ✅ `SkillStorage` — added `TeamSkillStorage` class
9. ✅ All 464 SDK tests + 14 app/hybrid tests passing

---

## Remaining Work for This Design

1. 🔲 Remove `data/shared/` and `shared_apps_dir()` from `DataPaths` — replaced by `teams/` layer
2. 🔲 Fix team path methods — remove `mkdir(parents=True)` calls (team dirs created by admin, not user containers)
3. 🔲 Implement team toolset pattern — register `team_*` tools when `team_id` is set
4. 🔲 Implement team config enforcement — filter tool registry based on `allowed_tools`/`blocked_tools` from team config
5. 🔲 Document team config schema fields and enforcement timing
6. 🔲 Update `DeploymentConfig` in settings.py with `team_id` field