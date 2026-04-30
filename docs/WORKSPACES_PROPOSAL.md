# Workspaces — Multi-Project Isolation for EA

> An executive assistant handles multiple projects. Each project gets its own Workspace with scoped conversation history, memory, files, subagents, and custom AI instructions. Modeled on Perplexity Spaces + Claude Code project scoping.

**Status:** Proposal / peer review  
**Author:** Eddy Xu  
**Date:** April 30, 2026

---

## 1. Research — How Competitors Organize Work

### Perplexity Spaces

Perplexity Spaces are named, persistent research environments. Each Space has:
- **Custom AI instructions** that guide all searches within the space
- **Uploaded files** (50MB limit, Pro) that the AI references across queries
- **Persistent context** — returning days later, all accumulated research is still available
- **Shared Spaces** — collaborators see all searches, AI draws on collective knowledge
- **5M+ Spaces** created as of March 2026 — users clearly want multi-space organization

Spaces are free (3 Spaces) to Pro (unlimited). This is their killer feature — it makes Perplexity feel like a partner that remembers each project independently.

### Claude Code

Claude Code uses a **hierarchical configuration model** with 5 scoping levels for subagents and 3 for memory:

```
Subagent lookup (priority order):
  Org managed → Session (--agents CLI flag) → Project (.claude/agents/) →
  User (~/.claude/agents/) → Plugin

Memory scope:
  User (~/.claude/agent-memory/) → Project (.claude/agent-memory/) →
  Local (uncommitted)
```

Sessions are tied to directories. Each session starts with a fresh context window. `CLAUDE.md` provides project-level instructions loaded every session. The key insight: **sessions are disposable, configuration is persistent.** You don't "save a session" — you save configuration that makes every new session smarter.

### Codex Desktop (OpenAI)

Codex uses **project directories** with `.codex/` config files and `AGENTS.md` for instructions. Subagents are project-scoped by default, with fallback to enterprise-managed and personal config layers. The model is simpler than Claude's — three scopes (enterprise, project, personal) vs five.

### Common Pattern

All three platforms share one architecture: **scoped configuration that persists across sessions.** The "workspace" or "project" is a container for:
1. Files relevant to that project
2. Custom AI instructions (tone, domain, role)
3. Scoped memory/context (isolated from other projects)
4. Scoped agents/subagents (defined per-project or shared globally)

None of them treat a user as a single flat bucket. They all have some form of project isolation.

---

## 2. Current State — What EA Does Today

### The Single-Bucket Model

```
user_id: "default_user"
  ├── conversation.app.db    ← ALL topics mixed together
  ├── memory/                ← facts from Q2 Planning + Home Renovation + personal
  ├── Workspace/             ← files from ALL projects in one folder
  ├── Skills/                ← global: available everywhere
  └── subagents/             ← global: available everywhere
```

### Where This Hurts

| Problem | Example |
|---------|---------|
| **Conversation pollution** | Agent discussing Q4 strategy in the same thread where you asked about dinner reservations 10 minutes ago |
| **Memory cross-contamination** | `memory_search("budget")` returns "Home renovation budget is $50K" when you meant "Q2 marketing budget" |
| **File clutter** | `Workspace/` contains `budget.xlsx` (Q2), `budget.xlsx` (personal), `floorplan.png` — different projects, same directory |
| **No per-project AI instructions** | Every conversation uses the same system prompt — can't tell the agent "respond like a PM" for one project and "I'm a first-time renovator" for another |
| **Subagent sprawl** | All subagents are global — research-agent, writer, data-processor all visible everywhere, even when irrelevant |
| **No context switching** | To "switch projects," you must mentally reset — there's no concept of "I'm in the Q2 Planning workspace now" |

### The Hard Reality

The single-session model works for a solo desktop app with one user and one topic at a time. It breaks when the agent handles multiple projects, learns facts across domains, and needs to give contextual responses per project. Every competitor recognized this and built workspace scoping.

---

## 3. The Proposal — Workspaces

### What a Workspace Is

A **Workspace** is a named, isolated project container within a user's account:

```
~/Executive Assistant/
├── Workspaces/
│   ├── Q2 Planning/
│   │   ├── files/              ← budget.xlsx, strategy.md
│   │   ├── conversation.app.db ← scoped chat history
│   │   ├── memory/             ← scoped HybridDB
│   │   ├── subagents/          ← research-agent, writer
│   │   └── instructions.yaml   ← "Respond like a Product Manager"
│   │
│   ├── Home Renovation/
│   │   ├── files/              ← quotes.pdf, floorplan.png
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

| Resource | Workspace Scope | Global Scope | Default |
|----------|----------------|-------------|---------|
| **Conversation** | Always scoped to workspace | — | Workspace |
| **Memory** | Default: workspace-scoped | `memory_search(query, scope="global")` | Workspace |
| **Files** | Workspace-scoped only | — | Workspace |
| **Subagents** | Workspace-scoped | User-global fallback | Workspace-first |
| **Skills** | — | Always global | Global |
| **AI Instructions** | Per-workspace `instructions.yaml` | System-wide default | Workspace overrides |

**Files are always workspace-scoped.** No concept of "global files." A file in Q2 Planning can't be accidentally read in Home Renovation. If needed, the user copies it between workspaces.

**Memory defaults to workspace-scoped.** The agent searching "what's the budget?" in Q2 Planning only searches Q2 Planning memories. If the agent needs user-level facts ("where does Eddy live?"), it calls `memory_search(query, scope="global")`.

**Subagents follow Claude Code's priority model:**

```
Lookup order:
1. Workspace-scoped: data/workspaces/{id}/subagents/researcher/
2. User-global:       data/users/{uid}/subagents/global/researcher/

If researcher exists in both → workspace version wins (override).
If only in user-global → that version is used (shared).
If neither → agent doesn't know about it.
```

**Skills are always global.** Skills are knowledge modules ("how to deep research") — not project-specific tools. The same deep-research skill works in every workspace.

### Why Not Completely Global or Completely Scoped?

**Completely global** (current model) fails because context bleeds across projects. Memory, files, conversation — all mixed.

**Completely scoped** (everything in workspace, nothing shared) fails because:
- User preferences (name, location, timezone) should be known everywhere
- Skills are reusable knowledge — re-creating "deep-research" per workspace is wasteful
- A general-purpose research subagent should work across projects

The hybrid model (workspace-scoped by default, global opt-in) gives the right balance.

---

## 4. LLM Impact Analysis

### Token Comparison: Single-Session vs Multi-Workspace

**Scenario: 3 projects, 50 messages per project. User is in Q2 Planning.**

| Component | Single-Session (current) | Multi-Workspace (new) | Delta |
|-----------|-------------------------|----------------------|-------|
| System prompt | ~1,500 chars | ~1,600 chars (+ workspace name + instructions) | +100 |
| Conversation history | ~150 messages (all projects) | ~50 messages (Q2 Planning only) | **-100 msgs** |
| Memory context | All domains mixed | Workspace-filtered | Cleaner, fewer tokens |
| Agent instructions | Global only | Global + workspace override | +50-200 chars |

**No additional LLM API calls.** Workspace context is injected into the existing system prompt. The net token impact is a **reduction** for users with >1 project — the conversation history shrink (150 → 50 messages) far outweighs the small workspace context overhead.

For a single-project user (the default), there's a trivial ~150-char overhead for the workspace name + instructions. Negligible.

### Session Model — Lightweight Switching

Workspace switching is **instant and stateless** — no reload, no restart:

```
User clicks Q2 Planning in workspace switcher
  → Agent state resets: workspace_id = "q2-planning"
  → Conversation loaded: q2-planning/app.db
  → Memory scoped: data/workspaces/q2-planning/memory/
  → Files shown: Workspaces/Q2 Planning/files/
  → System prompt includes: workspace name + custom instructions
  → Next agent turn reflects new workspace context
```

The Flutter app doesn't need to disconnect/reconnect WebSocket. Workspace state is in the agent provider. Switching workspaces is a state mutation — the WS connection stays alive.

---

## 5. Subagent Scoping

### How Subagents Resolve

When the main agent calls `subagent_invoke("researcher", ...)`:

```python
def resolve_subagent(workspace_id: str, user_id: str, name: str) -> AgentDef | None:
    # 1. Check workspace-scoped (override)
    ws_path = f"data/workspaces/{workspace_id}/subagents/{name}/"
    if exists(ws_path):
        return load_agent_def(ws_path)
    
    # 2. Check user-global (fallback)
    user_path = f"data/users/{user_id}/subagents/global/{name}/"
    if exists(user_path):
        return load_agent_def(user_path)
    
    return None
```

### What Subagents Inherit

| Property | Workspace-scoped subagent | User-global subagent |
|----------|--------------------------|----------------------|
| Tool access | Defined in agent def | Defined in agent def |
| System prompt | Agent def + workspace instructions | Agent def only |
| Allowed files | Current workspace files | Current workspace files |
| Memory access | Current workspace memory | Current workspace memory |
| Skills access | Global skills | Global skills |

Workspace-scoped subagents get the workspace's custom AI instructions injected. User-global subagents don't — they're purposefully generic.

### Cross-Workspace Subagents

A subagent created in Q2 Planning cannot be invoked from Home Renovation. To share a subagent across workspaces, create it at the user-global level. This is by design — workspace subagents are customized for their context.

---

## 5.5 How Subagents Work with Workspaces

### Creation

When the main agent or user creates a subagent within a workspace:

```
User: "create a research subagent for Q2 planning"
  → workspace-scoped: Workspaces/Q2 Planning/subagents/researcher/
  → Workspace instructions injected into subagent system prompt:
      "Respond as a Senior Product Manager. Use AEST timezone."
  → Subagent inherits access to workspace files + workspace memory
  → Only callable from Q2 Planning workspace
```

If created at user-global level:

```
User: "create a research subagent for general use"
  → user-global: data/users/{uid}/subagents/global/researcher/
  → No workspace instructions injected (generic agent)
  → Access to current workspace files + memory when invoked
  → Callable from any workspace
```

### Invocation

When the main agent calls `subagent_invoke("researcher", "find competitor pricing")`:

```python
def resolve_and_invoke(name, task, workspace_id, user_id):
    # 1. Look up: workspace-scoped first
    agent_def = workspace_agents.get(name)
    
    # 2. Fallback: user-global
    if not agent_def:
        agent_def = global_agents.get(name)
    
    if not agent_def:
        return f"No subagent named '{name}' found."
    
    # 3. Inject workspace context
    if agent_def.is_workspace_scoped:
        # Already has workspace instructions baked in
        context = agent_def.system_prompt
    else:
        # User-global: inject current workspace context at invocation time
        ws = load_workspace(workspace_id)
        context = f"{agent_def.system_prompt}\n\n[Workspace: {ws.name}]\n{ws.custom_instructions}"
    
    # 4. Create isolated AgentLoop with scoped tools + memory
    loop = AgentLoop(
        provider=model,
        tools=agent_def.allowed_tools,
        system_prompt=context,
        middlewares=[ProgressMiddleware(workspace_id=ws_id),
                     MemoryMiddleware(workspace_id=ws_id)],
        user_id=user_id,
    )
    return await coordinator.invoke(loop, task)
```

### What Subagents See

| Context | Workspace-scoped subagent | User-global subagent |
|---------|--------------------------|----------------------|
| **Files** | Its workspace's files only | Current workspace's files at invocation time |
| **Memory** | Its workspace's memory only | Current workspace's memory at invocation time |
| **System prompt** | Agent def prompt + workspace instructions (baked in) | Agent def prompt + workspace instructions (injected) |
| **Skills** | All global skills | All global skills |
| **Tools** | As specified in agent def | Same |
| **Sibling subagents** | ❌ Not aware of other subagents | ❌ Not aware |

### Example: Q2 Planning Workspace

```
Workspace: Q2 Planning
  ├── subagents/
  │   ├── researcher/      ← workspace-scoped: knows Q2 context
  │   │   └── config.yaml: "Research competitor pricing, market trends."
  │   │                    "Respond as a PM. Use AEST."
  │   └── writer/          ← workspace-scoped: knows Q2 context
  │       └── config.yaml: "Write executive summaries, briefs, reports."
  │                        "Respond as a PM. Keep it under 2 pages."
  └── instructions.yaml: "Respond as a Senior Product Manager. Use AEST."

User-global: data/users/{uid}/subagents/global/
  └── general-researcher/  ← user-global: any workspace can use this
      └── config.yaml: "General web research agent. No domain-specific tone."
```

**Scenario:** User in Q2 Planning says "research our top 3 competitors"

1. Agent resolves `researcher` → finds workspace-scoped version (Q2 context baked in)
2. Spawns subagent with Q2 instructions: "Respond as a PM. Use AEST."
3. Subagent searches web, writes findings to workspace files
4. Returns summary to main agent
5. Main agent reads workspace files, crafts response

If the user instead invokes `general-researcher`:
1. Agent resolves → not in workspace, falls back to user-global
2. Spawns with workspace instructions injected at runtime
3. Same result, but the subagent wasn't pre-configured for Q2

---

## 5.6 How Skills Work with Workspaces

Skills support **two location scopes**, following opencode's model (project-scoped + global). The lookup order is: workspace → user-global → system.

### Skill Storage Locations

```
Workspace-scoped:                          User-global:
Workspaces/Q2 Planning/skills/             ~/Executive Assistant/Skills/
  ├── researcher/SKILL.md                    ├── deep-research/SKILL.md
  └── writer/SKILL.md                        ├── planning-with-files/SKILL.md
                                              ├── subagent-manager/SKILL.md
Workspaces/Home Renovation/skills/            └── skill-creator/SKILL.md
  └── contractor-finder/SKILL.md
                                            System (seeded on first run):
Workspaces/Personal/skills/                 src/skills/
  (empty by default)                          ├── deep-research/
                                              ├── planning-with-files/
                                              ├── subagent-manager/
                                              └── skill-creator/
```

### Lookup Order

```python
def resolve_skill(name: str, workspace_id: str, user_id: str) -> Skill | None:
    # 1. Workspace-scoped (override)
    ws_path = DataPaths(workspace_id=workspace_id).workspace_skills_dir() / name / "SKILL.md"
    if ws_path.exists():
        return parse_skill_file(ws_path)
    
    # 2. User-global (fallback)
    global_path = DataPaths(user_id=user_id).global_skills_dir() / name / "SKILL.md"
    if global_path.exists():
        return parse_skill_file(global_path)
    
    # 3. System (seeded to user-global on first run)
    return None  # System skills already copied to user-global on first launch
```

### When to Use Each Scope

| Create at this scope | When |
|---------------------|------|
| **Workspace** | The skill is specific to this project ("Q2 competitor analysis skill") |
| **User-global** | The skill applies across all projects ("email triage", "deep research") |
| **Override** | Create workspace version with same name as global version → workspace wins |

### What opencode Does

opencode supports the same pattern. They search these locations in priority order:
1. Project: `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`
2. Global: `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/`
3. Walk up directory tree from CWD

EA's equivalent: workspace `skills/` directories in priority order, then user-global `Skills/`, then system `src/skills/`.

### Example: Override Scenario

```
Global Skills/:
  └── deep-research/SKILL.md
      description: "Multi-step web research with summarization"
      instructions: "Search web → scrape top 5 results → summarize"

Workspaces/Q2 Planning/skills/:
  └── deep-research/SKILL.md
      description: "Multi-step web research — Q2 Planning edition"
      instructions: "Search web → scrape top 10 results → categorize by competitor
                     → generate comparison table → save to workspace files"

Agent in Q2 Planning → skills_load("deep-research") → loads workspace version ✅
Agent in Home Renovation → skills_load("deep-research") → loads user-global version ✅
```

### Skill Discovery with Workspace Scoping

The system prompt shows all available skills with their source:

```
## Available Skills

- **deep-research** [workspace: Q2 Planning]: Multi-step web research with competitor analysis
- **researcher** [workspace: Q2 Planning]: Q2-specific research agent
- **writer** [workspace: Q2 Planning]: Executive summary writer
- **planning-with-files** [global]: Agent-internal Manus-style planning
- **subagent-manager** [global]: Guide for creating and managing subagents
- **skill-creator** [global]: Create new skills
```

Workspace-scoped skills take priority by position (listed first). The `[workspace]` / `[global]` tag helps the agent understand which version it's using.

### Skill Creation Scoping

| `skill_create` parameter | Behavior |
|--------------------------|----------|
| No `workspace` parameter | Creates in user-global `Skills/` |
| `workspace_name: "Q2 Planning"` | Creates in workspace-scoped `Workspaces/Q2 Planning/skills/` |
| Same name exists in both | Creates in the specified scope. Existing in other scope is unaffected. |

### Migration Impact

No migration needed. The existing user-global `Skills/` directory stays as-is. Workspace skills are new — empty by default. System skills remain seeded to user-global on first run.

---

## 5.7 How Memory Works with Workspaces

### Two-Tier Memory Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Memory Storage                        │
│                                                        │
│  Workspace Memory (default)         Global Memory      │
│  ┌──────────────────────────┐    ┌──────────────────┐  │
│  │ Q2 Planning/             │    │ user-level facts: │  │
│  │  "budget is $2.4M"       │    │  "Eddy lives in   │  │
│  │  "launch date: June 15"  │    │   Melbourne"      │  │
│  │  "competitor X dropped" │    │  "prefers terse"  │  │
│  │                          │    │  "timezone: AEST" │  │
│  └──────────────────────────┘    └──────────────────┘  │
│                                                        │
│  Home Renovation/                                      │
│  ┌──────────────────────────┐                          │
│  │  "budget is $50K"        │                          │
│  │  "contractor: ABC Build" │                          │
│  └──────────────────────────┘                          │
└────────────────────────────────────────────────────────┘
```

### How the Agent Decides Where to Search

```python
def memory_search(query: str, user_id: str, workspace_id: str = "personal",
                  scope: str = "workspace") -> str:
    """
    scope="workspace": Search workspace memory only (default).
    scope="global": Search user-level memory only.
    """
    if scope == "global":
        store = get_memory_store(user_id, workspace_id, scope=SCOPE_GLOBAL)
    else:
        store = get_memory_store(user_id, workspace_id, scope=SCOPE_WORKSPACE)
    return store.search(query)
```

### When to Use Each Scope

| Question type | Scope | Example |
|--------------|-------|---------|
| Project-specific facts | `workspace` (default) | "What's our Q2 budget?" → Q2 Planning memory |
| User preferences / identity | `global` | "Where does Eddy live?" → global memory |
| Cross-project comparison | `global` + filter | "What budgets do I have across all projects?" |

### Extraction Pipeline

The `MemoryMiddleware` writes to the correct scope based on fact domain:

```
Conversation in Q2 Planning:
  User: "Our Q2 budget is $2.4M"
  → Extracted: {domain: "project", ...}
  → Writes to: Workspaces/Q2 Planning/memory/  ← workspace-scoped

Conversation in any workspace:
  User: "I moved to Melbourne from Sydney"
  → Extracted: {domain: "personal", ...}
  → Writes to: Memory/global/                   ← user-level fact
  → Supersedes: old "Sydney" entry in global memory
```

### Memory Search Prompt Guidance

The agent's system prompt includes:

```
## Memory Search Rules

- When the user asks "what do you know about..." or about project details,
  use memory_search(query) — searches the current workspace.
- When the user asks "what's my..." or about personal identity/preferences,
  use memory_search(query, scope="global").
- When you're unsure, search workspace first, then global if not found.
```

### Correction Flow Across Workspaces

```
Q2 Planning workspace:
  User: "Actually, the budget is $2.8M, not $2.4M"
  Agent: memory_search("budget") → finds workspace entry → corrects to $2.8M

Home Renovation workspace:
  User: "What's my budget?" (meaning renovation budget)
  Agent: memory_search("budget") → finds "budget is $50K" → correct
  
  The Q2 correction ($2.4M → $2.8M) doesn't leak into Home Renovation.
  Both "budget" facts exist in different scopes. No conflict.
```

### What HybridDB Stores Per Scope

| Collection | Workspace Memory | Global Memory |
|-----------|-----------------|---------------|
| `facts` | ✅ Project facts | ✅ User identity facts |
| `preferences` | ✅ Workspace-specific prefs (tone, format) | ✅ User-wide prefs (timezone, name) |
| `corrections` | ✅ In-workspace corrections | ✅ Cross-workspace value updates |
| `connections` | ✅ Workspace-local relationships | ✅ User-level relationships |

---

## 6. Implementation Plan

### Revised Estimate (Post Codebase Review)

The initial estimate was ~720 lines (500 backend + 220 Flutter). A thorough review of all call sites in `src/sdk/`, `src/storage/`, and `src/http/` reveals additional plumbing needed across the stack. The core loop abstractions (AgentLoop, providers, tool decorator, guardrails, handoffs, tracing, MCP bridge, subagent models) remain genuinely untouched — the impact is parameter-level passthrough and path routing, not architectural change.

| Step | What | Lines | Risk | Dependencies |
|------|------|-------|------|-------------|
| 1 | `Workspace` model: id, name, description, custom_instructions, created_at | ~40 | Low | — |
| 2 | `DataPaths` updated with workspace-scoped paths (~10 methods need workspace variants) | ~60 | Low | Step 1 |
| 3 | `workspace_create/list/switch/current/delete` agent tools | ~150 | Low | Steps 1-2 |
| 4 | System prompt includes workspace name + custom instructions (`runner.py`) | ~25 | Low | Step 1 |
| 5 | Conversation history scoped: `get_message_store(user_id, workspace_id)`, plumbing through 7 callers (HTTP REST, WS, MemoryMiddleware, memory tools, consolidation) | ~60 | Medium | Step 3 |
| 6 | File tools workspace-scoped: `_resolve_path()` across `filesystem.py`, `file_search.py`, `file_versioning.py`, `shell.py` | ~60 | Medium | Step 2 |
| 7 | Memory search defaults to workspace scope (`scope` parameter), new `workspace_id` on `get_memory_store()` across 33 call sites + 10 HTTP memories endpoints + extraction pipeline | ~130 | ⚠️ High | Step 2 |
| 8 | Subagent coordinator scoped: workspace-first lookup, user-global fallback, `list_defs()` returns both | ~40 | Low | Steps 1-2 |
| 9 | `WorkQueueDB` schema: add `workspace_id` column + index, filter on `check_progress()` queries | ~40 | Medium | Step 2 |
| 10 | Migration: rename `~/EA/Workspace/` → `Workspaces/Personal/files/`, auto-create Personal on first launch, import old conversation + memory | ~50 | Medium | Steps 1,5,7 |
| 11 | Flutter: workspace switcher in sidebar header | ~200 | Medium | Flutter router |
| 12 | Flutter: workspace panel (files, subagents, instructions) | ~150 | Medium | Step 11 |

**Total: ~1,005 lines** (655 backend + 350 Flutter). Estimate: **5-7 days**.

---

## 6.1 Detailed Implementation Plan

### Pre-Work: Branch + Test Baseline

```bash
git checkout -b feat/workspaces
uv run pytest tests/sdk/ -q --tb=short  # confirm 470+ pass
uv run pytest tests/api/ -q --tb=short  # confirm 38+ pass
flutter test                              # confirm 96+ pass
```

### Day 1: Core Model + Data Paths (Steps 1-2)

**File: `src/sdk/workspace_models.py` (NEW, ~40 lines)**

```python
@dataclass
class Workspace:
    id: str              # "q2-planning"
    name: str            # "Q2 Planning"
    description: str     # "" 
    custom_instructions: str  # ""
    created_at: str
    updated_at: str

WORKSPACE_DEFAULT = Workspace(
    id="personal", name="Personal", description="Default workspace",
    custom_instructions="", created_at="", updated_at=""
)
```

**File: `src/storage/paths.py` (MODIFY, ~60 lines)**

Add workspace-scoped path methods to `DataPaths`:

```python
class DataPaths:
    def __init__(self, ..., workspace_id: str | None = None):
        self.workspace_id = workspace_id
    
    def workspace_base(self) -> Path:
        """Base directory for all workspaces."""
        return Path.home() / "Executive Assistant" / "Workspaces"
    
    def current_workspace_dir(self) -> Path:
        """Current workspace directory."""
        ws_id = self.workspace_id or "personal"
        return self.workspace_base() / ws_id
    
    def workspace_conversation_dir(self) -> Path:
        p = self.current_workspace_dir() / "conversation.app.db"
        return p
    
    def workspace_memory_dir(self) -> Path:
        p = self.current_workspace_dir() / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    def workspace_files_dir(self) -> Path:
        p = self.current_workspace_dir() / "files"
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    def workspace_subagents_dir(self) -> Path:
        p = self.current_workspace_dir() / "subagents"
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    def global_memory_dir(self) -> Path:
        p = Path.home() / "Executive Assistant" / "Memory" / "global"
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    def global_subagents_dir(self) -> Path:
        return self._user_base / "subagents" / "global"
```

**Migration logic in `DataPaths.__init__`:**

```python
# On first access after upgrade, migrate legacy paths
legacy_workspace = Path.home() / "Executive Assistant" / "Workspace"
new_personal = self.workspace_base() / "personal" / "files"
if legacy_workspace.exists() and not new_personal.exists():
    self.workspace_base().mkdir(parents=True, exist_ok=True)
    legacy_workspace.rename(new_personal)
```

**Backward compat: `workspace_dir()` method:**

```python
def workspace_dir(self) -> Path:
    """Deprecated: use workspace_files_dir() instead."""
    return self.workspace_files_dir()
```

**Test:** `uv run python -c "from src.storage.paths import DataPaths; dp = DataPaths(workspace_id='test'); print(dp.workspace_files_dir())"`

---

### Day 2: Conversation + Memory Scoping (Steps 5, 7)

**File: `src/storage/messages.py` — `get_message_store()` (MODIFY, ~20 lines)**

```python
def get_message_store(user_id: str, workspace_id: str | None = None) -> MessageStore:
    ws_id = workspace_id or "personal"
    paths = DataPaths(user_id=user_id, workspace_id=ws_id)
    db_path = paths.workspace_conversation_dir()
    # ... open/create HybridDB at db_path
```

**File: `src/storage/memory.py` — `get_memory_store()` (MODIFY, ~30 lines)**

```python
def get_memory_store(
    user_id: str,
    workspace_id: str | None = None,
    scope: str = SCOPE_WORKSPACE,
) -> MemoryStore:
    ws_id = workspace_id or "personal"
    paths = DataPaths(user_id=user_id, workspace_id=ws_id)
    db_path = paths.workspace_memory_dir() if scope == SCOPE_WORKSPACE else paths.global_memory_dir()
    # ... open/create HybridDB at db_path
```

**File: `src/sdk/tools_core/memory.py` — `memory_search()` (MODIFY, ~30 lines)**

```python
def memory_search(
    query: str,
    user_id: str = "default_user",
    workspace_id: str | None = None,
    scope: str = "workspace",  # "workspace" | "global"
) -> str:
    memory_store = get_memory_store(user_id, workspace_id, scope)
    # ... existing search logic, now scoped
```

**Call-site updates (~100 lines across 7 files):**

| File | Change |
|------|--------|
| `src/http/routers/conversation.py` | Accept `workspace_id` query param in `/conversation` and `/conversation/stream`, pass to `get_message_store()` |
| `src/http/routers/ws.py` | Read `workspace_id` from first WS message, pass to all store calls |
| `src/http/routers/memories.py` | Add `workspace_id` query param to all 10 endpoints |
| `src/sdk/middleware_memory.py` | Accept `workspace_id` in constructor, pass to `get_memory_store()` |
| `src/storage/consolidation.py` | Accept `workspace_id`, pass to factory calls |

**Test:** Send a message in workspace A, switch to workspace B, verify conversation history is isolated.

---

### Day 3: File Tools + System Prompt (Steps 4, 6)

**File: `src/sdk/tools_core/filesystem.py` (MODIFY, ~40 lines)**

Update `_resolve_path()` to use workspace-scoped directory:

```python
def _resolve_path(path: str | None, user_id: str, workspace_id: str | None = None) -> Path:
    ws_id = workspace_id or "personal"
    root_path = DataPaths(user_id=user_id, workspace_id=ws_id).workspace_files_dir()
    # ... existing logic, now scoped to workspace
```

**Files to update (`workspace_id` passthrough, ~20 lines each):**

| File | Tools |
|------|-------|
| `tools_core/filesystem.py` | 6 tools: `files_list/read/write/edit/delete/mkdir` |
| `tools_core/file_search.py` | 2 tools: `files_glob_search`, `files_grep_search` |
| `tools_core/file_versioning.py` | 4 tools: `files_versions_list/restore/delete/clean` |
| `tools_core/shell.py` | 1 tool: `shell_execute` |

**File: `src/sdk/runner.py` — `_get_system_prompt()` (MODIFY, ~15 lines)**

```python
def _get_system_prompt(user_id: str, workspace_id: str | None = None) -> str:
    ws_id = workspace_id or "personal"
    ws = _get_workspace(ws_id)  # load from workspace config
    prompt = base_prompt + skills_context + f"\n\nuser_id: {user_id}"
    if ws and ws.custom_instructions:
        prompt += f"\n\n## Current Workspace: {ws.name}"
        prompt += f"\n{ws.custom_instructions}"
    return prompt
```

---

### Day 4: Workspace Tools + Subagent Scoping (Steps 3, 8, 9)

**File: `src/sdk/tools_core/workspace.py` (NEW, ~150 lines)**

```python
from src.sdk.tools import tool
from src.sdk.workspace_models import Workspace, WORKSPACE_DEFAULT

_CURRENT_WORKSPACES: dict[str, str] = {}  # user_id -> workspace_id

def get_current_workspace(user_id: str) -> str:
    return _CURRENT_WORKSPACES.get(user_id, "personal")

@tool
def workspace_create(name: str, description: str = "", instructions: str = "") -> str:
    """Create a new workspace."""
    ws = Workspace(id=name.lower().replace(" ", "-"), name=name,
                   description=description, custom_instructions=instructions,
                   created_at=datetime.now().isoformat(),
                   updated_at=datetime.now().isoformat())
    # Create directories: files/, memory/, conversation/, subagents/
    paths = DataPaths(workspace_id=ws.id)
    paths.workspace_files_dir()
    paths.workspace_memory_dir()
    paths.workspace_subagents_dir()
    # Save workspace config
    ...
    return f"Created workspace: {name}"

@tool
def workspace_list() -> str:
    """List all workspaces."""
    ...

@tool
def workspace_switch(name: str, user_id: str = "default_user") -> str:
    """Switch to a different workspace."""
    _CURRENT_WORKSPACES[user_id] = name.lower().replace(" ", "-")
    return f"Switched to workspace: {name}"

@tool
def workspace_current(user_id: str = "default_user") -> str:
    """Get current workspace info."""
    ...

@tool
def workspace_delete(name: str, user_id: str = "default_user") -> str:
    """Delete a workspace (archive files, purge conversation + memory)."""
    ...
```

**File: `src/sdk/coordinator.py` — subagent scoping (MODIFY, ~40 lines)**

```python
def _resolve_agent_def(self, name: str, workspace_id: str | None = None) -> AgentDef | None:
    # 1. Workspace-scoped
    ws_path = DataPaths(workspace_id=workspace_id).workspace_subagents_dir() / name
    if (ws_path / "config.yaml").exists():
        return load_agent_def(ws_path)
    # 2. User-global fallback
    global_path = DataPaths(user_id=self.user_id).global_subagents_dir() / name
    if (global_path / "config.yaml").exists():
        return load_agent_def(global_path)
    return None
```

**File: `src/sdk/work_queue.py` (MODIFY, ~40 lines)**

```sql
-- Migration: add workspace_id column to work_queue
ALTER TABLE work_queue ADD COLUMN workspace_id TEXT DEFAULT 'personal';
CREATE INDEX idx_work_queue_workspace ON work_queue(workspace_id, status);
```

**File: `src/sdk/tools_core/subagent.py` — update tools (MODIFY, ~30 lines)**

```python
def subagent_invoke(..., workspace_id: str | None = None):
    ws_id = workspace_id or get_current_workspace(user_id)
    # ... pass ws_id to coordinator and work_queue
```

---

### Day 5: HTTP Plumbing + Migration (Steps 10)

**File: `src/http/routers/workspace.py` (MODIFY, add ~50 lines)**

```python
@router.get("/workspace/json")
async def list_workspace_json(user_id: str = "default_user", workspace_id: str = "personal"):
    paths = DataPaths(user_id=user_id, workspace_id=workspace_id)
    workspace_dir = paths.workspace_files_dir()
    # ... existing listing logic, already scoped to workspace
```

**File: `src/http/routers/conversation.py` — REST handler (MODIFY, ~10 lines)**

```python
@router.post("/message")
async def handle_message(
    user_id: str = "default_user",
    workspace_id: str = "personal",  # NEW
    message: str = ...,
):
    conversation = get_message_store(user_id, workspace_id)
    ...
```

**File: `src/http/routers/ws.py` — WebSocket handler (MODIFY, ~15 lines)**

```python
# On first message, extract workspace_id
workspace_id: str = "personal"
...
if isinstance(msg, UserMessage):
    ws = getattr(msg, "workspace_id", None)
    if ws:
        workspace_id = ws
    conversation = get_message_store(user_id, workspace_id)
    ...
```

**Migration (standalone script, ~50 lines):**

```python
# scripts/migrate_workspaces.py
def migrate():
    """Rename ~/EA/Workspace/ -> ~/EA/Workspaces/Personal/files/"""
    legacy = Path.home() / "Executive Assistant" / "Workspace"
    new = Path.home() / "Executive Assistant" / "Workspaces" / "Personal" / "files"
    if legacy.exists() and not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(new))
    
    """Move conversation DB to workspace-scoped location"""
    old_conv = Path("data/users/default_user/conversation/app.db")
    new_conv = Path.home() / "Executive Assistant" / "Workspaces" / "Personal" / "conversation.app.db"
    if old_conv.exists() and not new_conv.exists():
        new_conv.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_conv), str(new_conv))
    
    """Move memory to workspace-scoped location (keep copy in global/) """
    old_mem = Path("data/users/default_user/memory")
    new_mem = Path.home() / "Executive Assistant" / "Workspaces" / "Personal" / "memory"
    if old_mem.exists() and not new_mem.exists():
        shutil.copytree(str(old_mem), str(new_mem))
```

---

### Day 6: Flutter — Workspace Switcher (Step 11)

**File: `lib/providers/workspace_provider.dart` (NEW, ~80 lines)**

```dart
final currentWorkspaceProvider = StateProvider<String>((ref) => 'personal');

final workspaceListProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final host = ref.read(hostProvider);
  final userId = ref.read(userIdProvider);
  final url = Uri.parse('http://$host/workspace/json?user_id=$userId');
  final response = await http.get(url);
  final data = jsonDecode(response.body);
  return List<Map<String, dynamic>>.from(data['workspaces'] ?? []);
});

class WorkspaceNotifier extends StateNotifier<String> {
  WorkspaceNotifier(this.ref) : super('personal');
  final Ref ref;
  
  void switchWorkspace(String id) {
    state = id;
    ref.read(agentProvider.notifier).clearHistory();
    ref.read(agentProvider.notifier).loadHistory();
  }
}
```

**File: `lib/core/layout/desktop_layout.dart` — sidebar header (MODIFY, ~120 lines)**

Replace the existing logo icon with a workspace switcher:

```dart
// In _Sidebar build():
Padding(
  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 12),
  child: _WorkspaceSwitcher(),
),
```

The `_WorkspaceSwitcher` widget:
- Shows current workspace initial as an avatar circle
- Tap → dropdown with all workspaces
- "+" button → create workspace dialog
- Shows `N` files, `N` subagents under each workspace

---

### Day 7: Flutter — Workspace Panel + Testing (Step 12)

**File: `lib/features/workspace/workspace_panel.dart` (MODIFY, ~150 lines)**

Update the existing workspace panel to show workspace-scoped content:

```dart
// Add to existing WorkspacePanel:
// - Card showing workspace name + custom instructions (editable)
// - Sub-section: Files (already exists)
// - New sub-section: Subagents (list + create button)
// - New sub-section: Memory (link to Memory panel, scoped to workspace)

// Workspace instructions editor:
// - Editable text field
// - Save button → POST /workspace/{id}/instructions
// - "The agent will use these instructions in this workspace"
```

**Testing Checklist:**

| Test | How to verify |
|------|--------------|
| Create workspace | `workspace_create("Test")` → verify directory at `~/EA/Workspaces/Test/` |
| Isolated conversation | Send message in workspace A → switch to B → verify empty |
| Isolated memory | `memory_search("budget")` in workspace A only returns A's memories |
| Global memory | `memory_search("name", scope="global")` returns user-level facts |
| File isolation | `files_list()` in workspace A only shows A's files |
| Subagent scoping | Create subagent in A → try to invoke from B → agent says "not found" |
| Workspace delete | `workspace_delete("Test")` → files archived, conversation purged |
| Migration | Run `scripts/migrate_workspaces.py` → old data at new locations |
| Flutter switcher | Click workspace switcher → dropdown shows all workspaces → switch works |
| Flutter panel | Workspace panel shows name + instructions + files + subagents<br><br>

---

## 6.2 Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Memory scoping breaks existing tests** | Add `workspace_id="personal"` default to all `get_memory_store()` calls — existing behavior preserved. Tests pass without changes. |
| **Migration corrupts data** | Copy, don't move. Run migration with `--dry-run` first. Keep old data for 30 days. |
| **Workspace switching loses conversation** | Each workspace has its own DB. Switching = loading a different file. No data writes during switch. |
| **Performance: many workspaces** | Workspace list is a directory scan + YAML read. 50 workspaces = ~50ms. Negligible. |
| **Global memory grows unbounded** | Global memory only stores user facts (name, location, preferences). Consolidation runs on a schedule. |
| **Subagent name collision** | Workspace-scoped subagent always wins over user-global. Explicit override, no ambiguity. |


### What Genuinely Has Zero Impact

These components required no changes in the codebase review — they are fully workspace-agnostic:

| Component | File(s) | Lines | Why Untouched |
|-----------|---------|-------|---------------|
| **AgentLoop** | `sdk/loop.py` | 1,043 | Receives provider, tools, system_prompt, middlewares — all workspace-scoping is done before construction |
| **LLM providers** | `sdk/providers/ollama.py`, `openai.py`, `anthropic.py`, `gemini.py` | 1,692 | Same model calls, just different context strings |
| **@tool decorator / ToolDefinition** | `sdk/tools.py` | 297 | Tools are unchanged — they receive `workspace_id` as a new parameter, not a decorator change |
| **ToolRegistry** | `sdk/tools.py` | 297 | Registration is workspace-agnostic — scoping is at the coordinator/router layer |
| **Subagent models** | `sdk/subagent_models.py` | 96 | `AgentDef`, `SubagentResult`, `TaskStatus`, `TaskCancelledError` — no workspace concept needed |
| **Skills system** | `sdk/tools_core/skills.py`, `skills/registry.py`, `skills/models.py` | 488 | Skills are global by design — no scoping needed |
| **MCP bridge** | `sdk/tools_core/mcp_bridge.py`, `mcp_manager.py`, `mcp.py`, `mcp_config.py` | 657 | MCP tools are workspace-agnostic |
| **Guardrails** | `sdk/guardrails.py` | 60 | Input/output/tool guardrails don't depend on workspace |
| **Handoffs** | `sdk/handoffs.py` | 92 | Model-driven agent transfer is workspace-agnostic |
| **Tracing** | `sdk/tracing.py` | 204 | Spans are workspace-agnostic |
| **Validation** | `sdk/validation.py` | 158 | JSON repair is workspace-agnostic |
| **HITL / Interrupt** | `sdk/loop.py:107-192` | — | Approvals work identically regardless of workspace |
| **Email / contacts / todos** | `tools_core/email.py`, `contacts.py`, `todos.py` | 1,290 | Not scoped today, not scoped after (user-level data) |
| **Apps** | `tools_core/apps.py` | 742 | Currently per-user, remains per-user |
| **Firecrawl / Browser** | `tools_core/firecrawl.py`, `browser.py` | 1,179 | CLI-backed tools are workspace-agnostic |
| **Model registry** | `sdk/registry.py` | 388 | Provider/model discovery has no workspace concept |

**Untouched total: ~8,100 lines** of the ~16,000-line SDK (50%).

### Call-Site Analysis — Where Workspace Plumbing Hits

#### `get_message_store()` — 7 files, ~17 call sites

| Caller | File | Lines | Change |
|--------|------|-------|--------|
| HTTP REST `/message` | `routers/conversation.py:23,42,68,237` | 4 | Accept `workspace_id` query param |
| WebSocket | `routers/ws.py:294` | 1 | Workspace state on connection |
| MemoryMiddleware (planner path) | `middleware_memory.py:306` | 1 | Inherits from middleware context |
| MemoryMiddleware (baseline path) | `middleware_memory.py:404` | 1 | Inherits from middleware context |
| Memory tools | `tools_core/memory.py:33,92` | 2 | New `workspace_id` parameter |
| Memory consolidation | `storage/memory.py:1198` | 1 | Runs per-workspace |
| Storage module init | `storage/__init__.py:7,15` | 2 | Export signature update |

#### `get_memory_store()` — 6 files, ~33 call sites

| Caller | File | Lines | Change |
|--------|------|-------|--------|
| MemoryMiddleware | `middleware_memory.py:202` | 1 | `workspace_id` on constructor |
| Memory tools (5 tools) | `tools_core/memory.py:93,257,360,413` | 4 | New `workspace_id` parameter per tool |
| Memory consolidation | `storage/consolidation.py:29` | 1 | `workspace_id` passthrough |
| HTTP memories router | `routers/memories.py` (24+ calls across 10 endpoints) | 24 | `workspace_id` query param on all endpoints |
| Storage module init | `storage/memory.py:1399-1410` | 2 | Factory signature update |

#### `get_paths()` — 10 files, ~21 call sites (in `src/sdk/`)

| Caller | File | Lines | Change |
|--------|------|-------|--------|
| Filesystem tools | `tools_core/filesystem.py:27,46,50,315` | 4 | `workspace_dir()` → workspace-scoped |
| File search | `tools_core/file_search.py:15,24,28` | 3 | Same |
| File versioning | `tools_core/file_versioning.py:15,19` | 2 | Same |
| Shell | `tools_core/shell.py:55` | 1 | Same |
| Skills | `tools_core/skills.py:162` | 1 | No change (global) |
| Contacts storage | `tools_core/contacts_storage.py:20` | 1 | No change (user-level) |
| Todos storage | `tools_core/todos_storage.py:19` | 1 | No change (user-level) |
| Email DB | `tools_core/email_db.py:19` | 1 | No change (user-level) |
| Apps | `tools_core/apps.py:78` | 1 | No change (user-level) |
| Coordinator | `coordinator.py:104` | 1 | Scoped via workspace_id |
| Work queue | `work_queue.py:59` | 1 | Scoped via workspace_id |
| Registry | `registry.py:153` | 1 | No change (system path) |
| Tracing | `tracing.py:134` | 1 | No change (system path) |
| MCP config | `tools_core/mcp_config.py:32,47` | 2 | No change (user-level) |

### Highest-Risk Area: Memory Scoping (Step 7)

The memory storage layer (`storage/memory.py`, 1,426 lines) already defines `SCOPE_GLOBAL = "global"` and `SCOPE_PROJECT = "project"` but neither is wired through to callers. The risk is threefold:

1. **Extraction pipeline** (`middleware_memory.py:200-787`) — Memories are extracted every 3 turns from conversation and written to `get_memory_store(self.user_id)`. With workspaces, extraction must write to the *current workspace's* memory store, not a user-level one. The middleware constructor needs `workspace_id`.

2. **HTTP memories API** (`routers/memories.py`) — All 10+ endpoints (list, get, create, update, delete, search, consolidate, connections, sessions, stats) currently take `user_id` only. Each needs `workspace_id` for workspace-scoped operations. This is ~200 lines of parameter changes across a single file.

3. **Consolidation** (`storage/consolidation.py`, 398 lines) — The memory consolidation pipeline (merging duplicate facts, pruning low-confidence memories, generating insights) runs on a per-user schedule. With workspaces, it needs to run *per workspace*, using workspace-specific confidence thresholds and connection graphs.

4. **Tool behavior change** — `memory_search("budget")` currently searches all user memories. With workspace scoping, it searches only the current workspace. The agent must learn to add `scope="global"` when it needs cross-project facts. This is a prompt engineering concern, not a code change.

### Workspace Model

```python
@dataclass
class Workspace:
    id: str              # "q2-planning"
    name: str            # "Q2 Planning"
    description: str     # "Q2 2026 product launch planning"
    custom_instructions: str  # "Respond as a Senior Product Manager. Use AEST timezone."
    created_at: str
    updated_at: str
```

### Workspace Tools

```
workspace_create(name, description?, instructions?)
  → Creates workspace directory + conversation DB + memory DB

workspace_list()
  → Returns all workspaces with name + description

workspace_switch(name)
  → Sets current workspace. Affects all subsequent context.

workspace_current()
  → Returns current workspace name + description + instructions

workspace_delete(name)
  → Archives conversation + memory. Deletes workspace directory.
```

---

## 7. Migration — What Changes, What Stays

### What Changes

| Before | After |
|--------|-------|
| `data/users/{uid}/conversation.app.db` | `data/workspaces/{workspace_id}/conversation.app.db` |
| `data/users/{uid}/memory/` | `data/workspaces/{workspace_id}/memory/` (workspace-scoped) + `data/users/{uid}/global_memory/` (user-global) |
| `~/Executive Assistant/Workspace/` | `~/Executive Assistant/Workspaces/{name}/files/` |
| `data/users/{uid}/subagents/` | `data/workspaces/{id}/subagents/` (workspace) + `data/users/{uid}/subagents/global/` (user-global) |
| System prompt: fixed | System prompt + workspace name + custom instructions |
| Agent tools: all global | Agent tools scoped to current workspace |

### What Stays (Codebase-Verified)

A full review of all `src/sdk/` and `src/storage/` call sites confirms these components require **zero changes** — the workspace scoping is injected at the construction/routing layer, not inside these abstractions.

| Component | File(s) | Lines | Why Truly Untouched |
|-----------|---------|-------|---------------------|
| AgentLoop / ReAct reasoning | `sdk/loop.py` | 1,043 | Receives provider, tools, system_prompt, middlewares — workspace-scoping happens before construction |
| LLM providers | `providers/ollama.py`, `openai.py`, `anthropic.py`, `gemini.py` | 1,692 | Same model calls, just different context strings |
| HITL / interrupt handling | `sdk/loop.py:107-192` | — | `_should_interrupt()`, `Interrupt`, approve/reject — workspace-agnostic |
| `@tool` decorator / ToolDefinition / ToolRegistry | `sdk/tools.py` | 297 | Tools unchanged — they receive `workspace_id` as a new parameter on function signature |
| Skills system | `tools_core/skills.py`, `skills/registry.py`, `skills/models.py`, `skills/storage.py` | 488 | Always global by design — no scoping needed |
| MCP bridge | `tools_core/mcp_bridge.py`, `mcp_manager.py`, `mcp.py`, `mcp_config.py` | 657 | Workspace-agnostic |
| Guardrails | `sdk/guardrails.py` | 60 | Input/output/tool guardrails don't depend on workspace |
| Handoffs | `sdk/handoffs.py` | 92 | Model-driven agent transfer is workspace-agnostic |
| Tracing | `sdk/tracing.py` | 204 | Spans are workspace-agnostic |
| Validation | `sdk/validation.py` | 158 | JSON repair is workspace-agnostic |
| Subagent models (`AgentDef`, `SubagentResult`, etc.) | `sdk/subagent_models.py` | 96 | No workspace concept needed |
| Email / contacts / todos | `tools_core/email.py`, `contacts.py`, `todos.py` | 1,290 | User-level data — not scoped today, not scoped after |
| Apps | `tools_core/apps.py` | 742 | Currently per-user, remains per-user |
| Firecrawl / Browser | `tools_core/firecrawl.py`, `browser.py` | 1,179 | CLI-backed tools — workspace-agnostic |
| Model registry | `sdk/registry.py` | 388 | Provider/model discovery has no workspace concept |
| Flutter chat (center panel) | Flutter | — | Only the sidebar header changes (add workspace switcher) |

**Untouched total: ~8,386 lines** of the ~16,000-line SDK (52%).

### Zero-Risk Rollout

1. Default workspace "Personal" auto-created on first launch
2. Single-project users never notice the change (one workspace = transparent)
3. Multi-project users get isolation without breaking existing conversations
4. Old conversation/memory can be migrated into the "Personal" workspace

---

## 8. Edge Cases

| Scenario | Handling |
|----------|----------|
| **User deletes workspace** | Archive files to `~/.Trash/`, purge conversation + memory |
| **Agent needs cross-workspace info** | `memory_search(query, scope="global")` — explicit opt-in |
| **No workspace selected** | Auto-create "Default" on first launch |
| **Workspace with custom instructions + global system prompt** | Workspace instructions appended, not replacing. Both active. |
| **Subagent created in workspace A, invoked from workspace B** | Not allowed. Workspace subagents are scoped. Create user-global subagent instead. |
| **What happens to current conversation on switch?** | Each workspace has its own conversation DB. Switching loads that workspace's history. No data loss. |
| **Files from workspace A visible in workspace B?** | No. Files are workspace-scoped. Use Finder to copy between workspace directories. |
| **User-global memory search returns too many results** | `scope` parameter with domain filter: `memory_search("budget", scope="global", domain="Q2 Planning")` |
| **Workspace subagent has same name as user-global subagent** | Workspace version overrides. This is intentional — specializations. |

---

## 9. Decision Points for Peer Review

1. **Naming:** "Workspace" vs "Project" vs "Space"? Perplexity uses "Space." The sidebar tab is already "Workspace" (file browser). Consistent naming.

2. **Scope of global memory:** Should user-level memory be a SEPARATE collection (clean split) or a shared collection with workspace filter (simpler SQL)? Separate is cleaner.

3. **Workspace file path:** `~/Executive Assistant/Workspaces/{name}/files/` is clean. But the existing `~/Executive Assistant/Workspace/` directory already has files. Migration: rename `Workspace/` → `Workspaces/Personal/files/` on first launch.

4. **Default workspace name:** "Personal" vs "General" vs "Default"? "Personal" feels right for solo users who aren't thinking in terms of projects yet.

5. **Flutter UX:** Dropdown in sidebar header? Or a modal sheet listing all workspaces with a + button? Dropdown is faster — 1 click to switch. Modal is better for mobile and shows more info.

6. **Should the agent be able to create workspaces?** `workspace_create` tool: yes. An executive might say "create a workspace for Q2 planning" and the agent handles it. File organization + conversation + memory setup — all automated.

7. **Should conversation history span workspaces?** No. Each workspace is an independent thread. Cross-workspace context comes from global memory, not conversation history.

---

## Appendix A: Competitive Reference

| Platform | Unit | Scoping Model | Best Feature |
|----------|------|---------------|-------------|
| **Perplexity Spaces** | Space | Per-Space custom instructions, files, memory | "Respond as a PM" custom AI + persistent context |
| **Claude Code** | Project + Session | 5 scoping levels for agents, 3 for memory | Hierarchical priority — org > project > user |
| **Codex Desktop** | Project directory | Project-scoped, enterprise + personal fallback | Simpler than Claude — 3 scopes |
| **EA (proposed)** | Workspace | Workspace-first, user-global fallback | Hybrid: scoped by default, global when needed |

---

*End of proposal.*
