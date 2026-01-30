# User Customization Architecture

## Visual Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Request                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Prompt Assembly Pipeline                     │
└─────────────────────────────────────────────────────────────────┘

Current Flow:
┌────────┐    ┌────────┐    ┌────────┐    ┌─────────┐
│  Admin │ →  │  Base  │ →  │Channel │ →  │   LLM   │
│ Prompt │    │ Prompt │    │Appendix│    │         │
└────────┘    └────────┘    └────────┘    └─────────┘

Proposed Flow:
┌────────┐    ┌────────┐    ┌─────────┐    ┌────────┐    ┌─────────┐
│  Admin │ →  │  Base  │ →  │  User   │ →  │Channel │ →  │   LLM   │
│ Prompt │    │ Prompt │    │ Prompt  │    │Appendix│    │         │
└────────┘    └────────┘    └─────────┘    └────────┘    └─────────┘
                              ↑
                              │
                         Per-user
                      data/users/{tid}/
                          prompts/
```

---

## Storage Hierarchy

```
data/
├── admins/                          # Admin-scoped (global)
│   ├── prompts/
│   │   └── prompt.md               # Admin prompt (applies to all users)
│   ├── skills/
│   │   ├── on_start/               # Loaded at startup
│   │   └── on_demand/              # Available via load_skill
│   └── mcp/
│       └── servers.json            # Admin MCP servers
│
├── shared/                          # Organization-wide
│   ├── files/
│   ├── tdb/
│   └── vdb/
│
└── users/                           # Thread-scoped (per user)
    └── {thread_id}/                 # e.g., "telegram:123456"
        ├── prompts/                 # ← NEW: User prompts
        │   └── prompt.md
        ├── skills/                  # ← NEW: User skills
        │   └── on_demand/
        │       ├── planning.md
        │       └── my_workflow.md
        ├── mcp/                     # ← NEW: User MCP configs
        │   ├── local.json           # stdio servers
        │   └── remote.json          # http/sse servers (future)
        ├── files/                   # (existing)
        ├── tdb/                     # (existing)
        └── vdb/                     # (existing)
```

---

## Skill Loading Priority

```
┌─────────────────────────────────────────────────────────────┐
│                    load_skill("planning")                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Is user logged in?   │
                └───────────┬───────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                YES                   NO
                 │                     │
                 ▼                     ▼
    ┌─────────────────────┐    ┌──────────────┐
    │ Check user skills:  │    │ Skip to      │
    │ data/users/{tid}/   │    │ global       │
    │ skills/on_demand/   │    │ registry     │    ← Priority order
    │ planning.md         │    │              │
    └─────────┬───────────┘    └──────┬───────┘
              │                       │
         Exists?                      │
              │                       │
      ┌───────┴───────┐              │
      │               │              │
     YES              NO             │
      │               │              │
      ▼               └──────────────┤
    Return              ┌────────────┘
    content            ▼
                      ┌───────────────────┐
                      │ Check global:     │
                      │ skills/content/   │
                      │ on_demand/        │
                      │ planning.md       │
                      └─────────┬─────────┘
                                │
                           Exists?
                                │
                        ┌───────┴───────┐
                        │               │
                       YES              NO
                        │               │
                        ▼               ▼
                     Return         Return
                     content        None
```

---

## MCP Tool Integration

### Approach 1: Agent Rebuild (Simple, Phase 2)

```
User runs: /mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /path
                            │
                            ▼
                ┌───────────────────────┐
                │ Write to:             │
                │ data/users/{tid}/     │
                │ mcp/local.json        │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Detect config change  │
                │ Invalidate cache      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Next message from      │
                │ user triggers rebuild  │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Load MCP config       │
                │ Connect to servers    │
                │ Fetch tool schemas    │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Merge tools:          │
                │ - Global (71 tools)   │
                │ - Admin MCP           │
                │ - User MCP (new)      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Rebuild agent         │
                │ Cache per thread      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Process message with  │
                │ new agent             │
                └───────────────────────┘
```

### Tool Naming Convention

```
Global Tools:
- read_file
- write_file
- create_tdb_table
...

Admin MCP Tools:
- mcp.admin.filesystem.read
- mcp.admin.brave_search.search
...

User MCP Tools:
- mcp.user.filesystem.read
- mcp.user.github.list_issues
...
```

---

## Per-Thread Agent Cache

```
Thread 1 (telegram:123)                    Thread 2 (telegram:456)
┌──────────────────────┐                   ┌──────────────────────┐
│ Agent Instance A     │                   │ Agent Instance B     │
│ - Global tools       │                   │ - Global tools       │
│ - Admin MCP          │                   │ - Admin MCP          │
│ - User MCP: 2 svrs   │                   │ - User MCP: 0 svrs   │
│ Cache time: 10:00    │                   │ Cache time: 10:05    │
└──────────────────────┘                   └──────────────────────┘

When User 1 adds MCP server:
1. Update local.json
2. Invalidate cache for thread 1 only
3. Thread 2 continues using old agent
4. Thread 1 rebuilds on next message
```

---

## Command Structure (Proposed)

### Current Commands (Keep)
```
/start    - Start conversation
/reset    - Reset thread
/debug    - Toggle debug mode
/mem      - Memory management
/reminder - Reminder management
/meta     - Storage summary
```

### Proposed New Commands (Grouped)

**Option A: Separate Commands (Original Plan)**
```
/prompt set/show/clear/append  - User prompts
/mcp add/list/remove/edit     - User MCP
/skill create/list/delete     - User skills
```

**Option B: Grouped Commands (Recommended)**
```
/config prompt set/show/clear - User prompts
/config mcp add/list/remove   - User MCP
/config skill list/delete     - User skills
```

**Rationale**:
- Reduces command clutter
- Logical grouping ("configuration")
- Easier to discover
- Consistent with `/storage` idea

---

## Observer → Evolve Pipeline (Phase 3)

```
┌─────────────────────────────────────────────────────────────┐
│                    User Session                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Observer Agent                             │
│  - Captures atomic behaviors (instincts)                    │
│  - Records: trigger, action, pattern                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    Instincts accumulate
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Evolve Agent                               │
│  - Clusters related instincts                               │
│  - Identifies patterns (e.g., "always uses TDB for todos")   │
│  - Generates draft skill                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Human-in-the-Loop Approval                      │
│  - Presents draft skill to user                             │
│  - User edits/approves/rejects                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    Save to user skills
                            │
                            ▼
                Available via load_skill()
```

**Example Instinct → Skill Evolution**:

```
Instinct 1: "track todo for me" → create_tdb_table("todos")
Instinct 2: "add to my todos" → insert_tdb_table("todos")
Instinct 3: "list my todos" → query_tdb("SELECT * FROM todos")
            │
            ▼ (Evolve clusters these)
            │
Draft Skill:
```markdown
# Personal Todo Management

Description: Manage personal todos using TDB

Tags: productivity, todos

## Overview
When user wants to track personal tasks:
- Use create_tdb_table("todos", columns="task,status,priority")
- Use insert_tdb_table to add tasks
- Use query_tdb to list tasks
```
            │
            ▼ (User approves)
            │
Saved to: data/users/{tid}/skills/on_demand/todo_management.md
```

---

## Safety Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Input Validation                  │
│  - Max prompt size: 2000 chars                               │
│  - Filename sanitization                                     │
│  - JSON schema validation for MCP configs                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: Content Filtering                 │
│  - Keyword blocking (jailbreak, ignore instructions, etc.)   │
│  - MCP command sanitization                                 │
│  - Skill content validation                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: Prompt Assembly                   │
│  - Admin prompt (policies)                                   │
│  - Base prompt (role)                                        │
│  - User prompt (preferences) ← Cannot override policies      │
│  - Channel appendix (formatting)                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Layer 4: Runtime Guards                    │
│  - MCP timeouts (30s)                                        │
│  - Tool call rate limits                                     │
│  - File size limits                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Performance Considerations

### File I/O Optimization

```
Current (on every request):
┌────────┐     ┌────────┐     ┌────────┐
│ Prompt │ ─→  │ Disk   │ ─→  │ Return │
│ Load   │     │ I/O    │     │        │
└────────┘     └────────┘     └────────┘

Optimized (cached):
┌────────┐     ┌────────┐     ┌────────┐
│ Prompt │ ─→  │ Memory │ ─→  │ Return │
│ Load   │     │ Cache  │     │        │
└────────┘     └────────┘     └────────┘
                     │
                     ├─ Valid (mtime < 60s) → Return
                     └─ Invalid (mtime > 60s) → Disk I/O
```

### Agent Cache Management

```
LRU Cache (max 100 threads):
┌─────────────────────────────────────────────┐
│ Thread 1: Agent A (last used: 1s ago)      │
│ Thread 2: Agent B (last used: 5s ago)      │
│ Thread 3: Agent C (last used: 10s ago)     │
│ ...                                         │
│ Thread 100: Agent Z (last used: 1h ago)    │
└─────────────────────────────────────────────┘
         │
         │ Thread 101 requests
         ▼
┌─────────────────────────────────────────────┐
│ Evict Thread 100 (oldest)                  │
│ Build new agent for Thread 101              │
└─────────────────────────────────────────────┘
```

---

## Migration Path

```
Phase 1: Foundation (Week 1-2)
  ├─ User Prompts
  │  ├─ Storage module
  │  ├─ Commands (/prompt)
  │  └─ Integration
  │
  └─ User Skills (Basic)
     ├─ Extend loader
     ├─ Create tool
     └─ Testing

Phase 2: User MCP (Week 3-4)
  ├─ Config storage
  ├─ Commands (/mcp)
  ├─ Agent rebuild mechanism
  └─ Error handling

Phase 3: Advanced (Week 5+)
  ├─ Remote MCP
  ├─ Observer → Evolve
  └─ Optimization
```

---

## Key Takeaways

1. **Per-user storage**: `data/users/{thread_id}/` for all customization
2. **Skill priority**: User skills override system skills
3. **Prompt order**: Admin → Base → User → Channel
4. **MCP approach**: Agent rebuild with per-thread caching (Phase 2)
5. **Command grouping**: Consider `/config` to reduce clutter
6. **Safety first**: Multiple validation layers
7. **Phased rollout**: Start simple (prompts), iterate to complex (MCP)
