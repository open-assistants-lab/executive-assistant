# EA Talent Tree — Design Discussion

**Date:** 2026-05-27
**Status:** Brainstorming in progress
**Context:** Gamification system to retain users — the longer they use EA, the more features they unlock

---

## 1. Core Mechanism

### Token as Currency

- **No XP abstraction.** Tokens are the direct currency.
- **Earning rate:** 1 input token = 1 currency token, 1 output token = 1 currency token (1:1 for both)
- **All usage counts:** conversations, subagents, companion background cycles — everything that burns LLM tokens
- Stored in `token_ledger` table per user: `total_input_tokens`, `total_output_tokens`, `balance`

### Cost Models (all three used, depends on feature)

| Cost Type | Analogy | Example |
|---|---|---|
| **Unlock cost** (one-time) | Buying the tool | Skill Weaver: 80K tokens to unlock permanently |
| **Usage cost** (per-run) | Ammo per shot | Subagent invocation: 1K tokens per run |
| **Usage cost** (per-month) | Subscription | Global Orchestrator: 15K/month for cross-ws subagents |

### Feature Gate

Every tool call passes through `FeatureGate.check(tool_name, user_id)`:
- If the tool's talent is unlocked AND user has balance for usage cost → execute
- If locked → returns structured error with talent name, cost, user balance, and shortfall
- The agent receives this as tool output and can relay to the user

---

## 2. Talent Tree (5 Branches)

Only skills, subagents, apps, self-improvement, and memory capacity are gated. Everything else is free.

### Branch 1: Skill Weaver

```
Skill Weaver (80K tokens, one-time, usage: free)
  └─ All skill tools: skills_list, skills_load, skills_search, skill_create, skill_delete
  └─ Workspace-scoped only

  └─ Global Crafter (120K tokens, one-time, per-create: 500 tokens)
      └─ Lifts scope to user-level — skills visible across all workspaces
```

### Branch 2: Delegator

```
Delegator (120K tokens, one-time, per-invocation: 1K)
  └─ All subagent tools: subagent_create, start, delegate, list, check, instruct, cancel
  └─ Workspace-scoped only

  └─ Global Orchestrator (180K tokens, one-time, per-month: 15K)
      └─ Lifts scope to user-level — cross-workspace subagents
```

### Branch 3: App Builder

```
App Builder (150K tokens, one-time, write ops: 300 per-run)
  └─ All app tools (14 tools): create, insert, update, delete, columns, query, search
```

### Branch 4: Self-Improver

```
Self-Improver (200K tokens, one-time, per-experiment: 2K)
  └─ research_start, research_list
  └─ Enables EA to optimize prompts, skills, subagents via controlled A/B experiments
```

### Branch 5: Memory Capacity (choose your cap)

Memory is a growing asset, not a gated tool. User chooses which tier to stop at. Insight generation unlocks at 250+ stored facts.

```
100 facts — FREE (default, basic recall)

  └─ 250 facts (50K tokens, one-time)
      └─ Insights unlock — EA spots trends and patterns across your data

      └─ 500 facts (100K tokens, one-time)
          └─ Cross-workspace recall — search memories across all projects

          └─ 1,000 facts (200K tokens, one-time)
              └─ Full recall — year+ retention, deep pattern detection
```

### Free (always available)

Files (read/write/edit/list/search/versioning), email (read/list/search/send/sync/connect), browser (22 tools), shell, MCP, contacts (read/write), todos (read/write), companion, summarize, basic memory search

---

## 3. Data Model

```sql
-- Token ledger per user
CREATE TABLE token_ledger (
    user_id TEXT PRIMARY KEY,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    balance INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- What the user has unlocked
CREATE TABLE user_unlocks (
    user_id TEXT NOT NULL,
    talent_id TEXT NOT NULL,
    unlocked_at TEXT NOT NULL,
    PRIMARY KEY (user_id, talent_id)
);

-- Usage tracking for per-run/per-month billing
CREATE TABLE usage_log (
    user_id TEXT NOT NULL,
    talent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tokens_deducted INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
```

---

## 4. Open Questions

1. **SkillTarget evaluation stub** — `evaluate()` returns 0.5 (neutral). Real trigger-rate eval needs benchmark queries + a way to detect skill activation. Documented in `docs/skill-eval-stub-review.md`.
2. **Memory capacity enforcement** — How does the system actually cap facts? Soft-cap (stop extracting new facts at limit, prune old ones) or hard-cap (error)?
3. **Token balance display** — Where does the user see their balance? Flutter sidebar? Chat message?
4. **Talent tree visibility** — How does the user discover locked features? Inline when a tool fails? A dedicated talent tree panel?
