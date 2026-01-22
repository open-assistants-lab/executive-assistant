# Flow & Agent Registry Redesign Plan

## Updated Recap (with clarifications)

You want to redesign flows so they are **lighter to create** and reference **registered mini‑agents**, while also **teaching the main assistant stronger problem‑solving behaviors**.

Key points (with your clarifications):
1) **Mini‑agent registry**
   - Mini agents live under `./data/{user_id}/agents/`.
   - Each agent’s DSL/definition is persisted in a local DB (DuckDB or SQLite—needs a recommendation).
   - These agents can be reused across flows.

2) **Simplified flow creation**
   - A flow should be created with minimal metadata: `id`, `name`, `description`, and selection of one or more existing agents.
   - Flow creation should not require full inline AgentSpec.
   - You want to avoid oversimplification—flows still need to carry scheduling, notifications, and execution metadata (see “Current FlowSpec” below).

3) **Main agent behavior (problem‑solving discipline)**
   - Always **clarify/recap** requirements.
   - **Research** complex topics/jargon with tools.
   - **Decompose** large problems into smaller steps.
   - Design mini‑agents **test‑driven**, and use tools to test.
   - Present **multiple solution approaches** and recommend the viable path.
   - Provide **alternatives** when the primary path is blocked.
   - Items 5 & 6 apply to complex problems.

## Current Flow Design (to avoid oversimplifying)

Current FlowSpec (in code) includes:
- `flow_id`, `name`, `description`, `owner`
- `agents` (AgentSpec inline)
- `schedule_type`: immediate / scheduled / recurring
- `schedule_time` or `cron_expression`
- `notification_channels`, `notify_on_complete`, `notify_on_failure`
- `run_mode` (normal/emulated)
- `middleware` (limits/retries/tool emulator)

Execution pipeline:
- APScheduler polls `scheduled_flows` in Postgres and executes FlowSpec.
- Each agent runs with limited middleware and toolset.
- Flow tools are excluded from flow agents.
- Flow results can be pushed to notification channels.

So “simplified flow creation” should keep:
- schedule, notification, run_mode, middleware
- but replace inline AgentSpec with **references to registered mini‑agents**.



## Constraints
- Mini agents should use **≤5 tools** (hard cap 10). Prefer ≤5.
- Mini-agent middleware limits must be **separate from main agent**.
  - Main agent sets per-flow tool/model limits & retries for mini agents.
  - Hard cap: ≤10 for model/tool call limits.
- Handoff: only pass the **immediately previous agent output** to the next agent (no full history fan‑out).


## Detailed Plan

### Phase 1 — Agent Registry (per‑user)

**1. Storage decision (DuckDB vs SQLite)**
- SQLite: simpler, already used for DB tools; fits per‑user file storage; good for small structured data.
- DuckDB: stronger analytics but larger footprint; more overhead for tiny agent registry.

**Recommendation:** SQLite for agent registry (low overhead, consistent with other per‑user files). We can keep DuckDB for analytics workloads only.

**2. Agent registry file layout**
- Folder: `./data/users/{user_id}/agents/`
- DB file: `agents.db` (SQLite)
- Optional: store raw DSL snapshots as `.json`/`.yaml` files for backup/export.

**3. Agent schema (SQLite)**
```
CREATE TABLE agents (
  id TEXT PRIMARY KEY,        -- user-scoped agent id
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  model TEXT NOT NULL,
  tools TEXT NOT NULL,         -- JSON list
  system_prompt TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP
);
```

**4. Agent tools (new)**
- `create_agent` (validate + save)
- `list_agents`
- `get_agent`
- `update_agent`
- `delete_agent`

These tools are admin‑only initially or user‑scoped depending on access model.

### Phase 2 — FlowSpec refactor

**1. New FlowSpec shape**
- Keep: `name`, `description`, schedule fields, notifications, run_mode, middleware
- Replace `agents` inline with **agent references**:
  - `agent_ids: ["agent_a", "agent_b"]`

**2. Flow execution update**
- At run time, resolve agent_ids → AgentSpec from registry.
- Build execution chain in order.
- Validate missing agents early; fail flow with clear error.
- Pass only the immediately previous agent output to the next agent.

**3. Flow creation UX**
- `create_flow` accepts minimal payload + agent_ids list.
- Optionally allow inline AgentSpec for advanced users (feature flag).

### Phase 3 — Main Agent Behavior Updates


**Flow/Agent Design Framework (v1):**
1) **Clarify & Recap** — restate goal, scope, constraints, success criteria.
2) **Research (when needed)** — use tools to resolve jargon/unknowns.
3) **Decompose** — break into stages with explicit inputs/outputs.
4) **Design Options** — propose 1–3 viable approaches; recommend one.
5) **Test-Driven Build** — define expected output schema + minimal test cases; run tools to validate.
6) **Validate & Handoff** — verify outputs match schema before passing forward.
7) **Fallbacks** — suggest alternatives when blocked.

**1. System prompt reinforcement**
Add compact rules to system prompt:
- “Clarify/recap requirements before complex actions.”
- “Use tools to research jargon/complex topics.”
- “Break large problems into sub‑tasks.”
- “Design mini‑agents test‑driven and run tests with tools.”
- “Offer alternative approaches when stuck.”

**2. Skill guidance**
- Add a new skill doc: `problem_solving.md` (short checklist + examples).
- Ensure progressive disclosure: only loaded when needed.

### Phase 4 — Tooling & Tests

**Tests**
- Unit tests for agent registry CRUD.
- Flow creation w/ agent_ids only.
- Flow run resolves agent_ids correctly.
- Error handling when agent missing.
- Ensure no change in scheduling/notifications.

**Migration**
- No backward compatibility required (per your note).
- Remove inline AgentSpec assumption in flows.

## Risks / Open Questions

- Do we allow **inline AgentSpec** as a fallback? (optional flag)
- Should agent IDs be unique per user or globally namespaced?
- Should we allow sharing agents across users/groups later?

## Next Step (if you approve)

1) Confirm SQLite vs DuckDB for agent registry.  
2) I’ll implement Phase 1 + Phase 2 changes and update docs/skills.  
3) Add a minimal problem‑solving skill + system prompt lines.
