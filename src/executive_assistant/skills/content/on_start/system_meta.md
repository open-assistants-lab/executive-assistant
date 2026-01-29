# System Meta-Patterns (Quick Reference)

Description: Overview of how the agent learns and adapts (full guide: `load_skill("system_patterns")`)

Tags: core, system, meta, learning

---

## Quick Overview

The agent improves over time through **system-level patterns** (unlike user-facing patterns in `common_patterns.md`).

### Key Patterns

| Pattern | Purpose | Learn More |
|---------|---------|------------|
| **Observer → Evolve** | Learn from interactions | `load_skill("system_patterns")` |
| **Token Budget** | Manage context efficiently | `load_skill("system_patterns")` |
| **Middleware Stack** | Execution order matters | Built-in, automatic |
| **Context Propagation** | ThreadContextMiddleware | Built-in, automatic |

---

## Observer → Evolve (Learning)

**Concept:** Agent observes your patterns and adapts behavior.

```
Your actions → Observe → Store in Memory → Rollup → Evolve → Personalize
```

**Example:**
- You say "add X" → Agent creates todo (not reminder)
- Pattern detected → Memory: "User prefers todos for 'add X'"
- Repeated 10x → Confidence: 90%
- Promoted to rule → Agent auto-creates todos when you say "add X"

**Status:** 🚧 Planned (see `/features/memory_time_tiers_plan.md`)

---

## When to Use

**Load full guide (`load_skill("system_patterns")`) when:**
- Explaining how the agent learns
- Debugging token usage
- Understanding middleware behavior
- Implementing Observer-Evolve

---

## Quick Decision Tree

```
Want to understand how agent learns?
└─→ Load `system_patterns` (full guide)

Need to combine tools for a task?
└─→ See `common_patterns.md` (user workflows)

Choosing storage (TDB vs ADB vs VDB)?
└─→ See `decision_tree.md`
```

---

## See Also

- `common_patterns.md` - User-facing workflow patterns
- `decision_tree.md` - Storage decision guide
- `quick_reference.md` - Tool reference
- `/features/memory_time_tiers_plan.md` - Observer-Evolve implementation
