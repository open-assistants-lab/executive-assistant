# EA: Subagent Generation — Agent Proposes, User Approves

2026-06-03

## Context

The current `subagent_create` tool gives the main agent 16 parameters (name, model,
tools, skills, system_prompt, max_llm_calls, cost_limit_usd, etc.) and asks it to
configure a subagent from scratch in one turn. This is inherently unreliable: the
LLM must know exact tool names from the registry, choose appropriate limits, write
a well-engineered system prompt, and get all 16 fields right in one shot.

Claude Code solves this with a dedicated `/agents` TUI where "Generate with Claude"
creates the definition in a guided flow, completely separate from normal agent
execution. The agent then only delegates by name: `subagent_start("researcher",
"task prompt")`.

We need the same separation of concerns, but without leaving the conversation.

## Summary

**Two-phase flow: agent generates, user approves.**

### Phase 1: Agent generates from natural language

The user describes what they want inline. The main agent calls a new
`subagent_generate` tool that builds a complete AgentDef from a natural-language
requirements string:

```
User: I need a subagent that researches companies using web search and writes a SWOT summary.

Agent: [calls subagent_generate(requirements="research companies using web search, produce SWOT analysis with competitor comparison")]

→ Returns a fully populated AgentDef with pre-filled fields
```

The `subagent_generate` tool does the exploration work:

1. Reads available tools from registry → picks `search_web`, `scrape_url`, `files_write`
2. Reads available skills → picks `deep-research` if relevant
3. Reads available models → picks `sonnet` for research work
4. Generates system prompt from the requirements
5. Returns the complete AgentDef

### Phase 2: UI confirms with pre-filled editable form

The tool returns, and the Flutter UI shows a "Generated Subagent" card with all
fields pre-filled. Every field is editable inline:

```
┌─── Subagent Generated ──────────────────────────┐
│                                                   │
│ Name:       [ company-researcher          ]       │
│ Description:[ Researches companies, produces ]    │
│             [ SWOT analysis                  ]    │
│ Model:      [sonnet ▼]                            │
│ Tools:      [✅ search_web] [✅ scrape_url]       │
│             [✅ files_write] [ ] shell_execute    │
│             [ +2 more ▼      ]                    │
│ Skills:     [✅ deep-research] [✅ summarize]     │
│ Limits:     [50] llm calls  [$1.00] budget        │
│             [300] seconds timeout                 │
│                                                   │
│ System Prompt:                                    │
│ ┌─────────────────────────────────────────────┐  │
│ │ You are a research analyst. When given a    │  │
│ │ company name:                               │  │
│ │ 1. Search for company information           │  │
│ │ 2. Identify competitors                     │  │
│ │ 3. Produce SWOT analysis                    │  │
│ │ 4. Write structured markdown summary        │  │
│ └─────────────────────────────────────────────┘  │
│                                                   │
│ [Refine with feedback]    [Save & Create]         │
└───────────────────────────────────────────────────┘
```

**Controls:**

- `Save & Create` — persists the AgentDef to disk, adds to the subagents list,
  available for `subagent_start` immediately. Closes the card.
- `Refine with feedback` — opens a text field: *"Add tools for financial data"* →
  sends feedback back to the agent → agent calls `subagent_generate` again with
  the updated requirements → card refreshes with new pre-filled values.

### Key properties

- **Agent proposes, never decides alone** — the user always has the final edit
- **All fields editable** — name, model, tools, skills, limits, system prompt
- **Iterative refinement** — feedback loop without restarting the flow
- **No 16-parameter hallucination** — the agent generates from requirements,
  not from remembering tool names
- **Mirrors Claude Code `/agents` → "Generate with Claude"** but stays in the
  conversation context

## Backend Changes

### New tool: `subagent_generate`

```
subagent_generate(requirements: str) → AgentDef (pre-filled, not persisted)
```

The tool:
1. Calls `get_native_tools()` → gets available tool names + descriptions
2. Calls `get_available_skills()` → gets available skill names + descriptions
3. Reads model registry → gets available model IDs
4. Uses the main agent's LLM to select tools, skills, model, and generate
   system prompt from the requirements
5. Returns an `AgentDef` with all fields populated — **but does not save it**

The AgentDef is returned as a structured result that the Flutter UI renders
as the editable card.

## Frontend Changes

### New widget: `GeneratedSubagentCard`

Replaces the current "New Subagent" create dialog (or appears alongside it).

State management:
- Receives `AgentDef` from the `subagent_generate` tool result
- Each field is an editable `TextField` / `DropdownButton` / `ChipList`
- "Save" calls `POST /subagents` with the (possibly edited) AgentDef
- "Refine" sends feedback text → agent re-generates → card refreshes

### Integration with conversation

The card should appear in the conversation stream as a rich widget, not a
separate dialog. This keeps the user in flow — they see the agent's generation
alongside the conversation context that prompted it.

## Non-Goals

- Replacing the existing "Create new subagent" dialog from scratch —
  this is an additional path, not a removal.
- `subagent_generate` triggering automatically — the agent must be asked
  explicitly by the user (or calls it when `subagent_create` would be called
  today).
- Real-time streaming of the generation — the card appears when the tool
  result returns, not during generation.

## Evaluation Pipeline (mirrors skill-creator)

Creating a subagent is a prompt-engineering task. The same evaluation loop
from the `skill-creator` meta-skill applies directly to subagents. A shipped
`subagent-creator` skill will guide the agent through:

### 1. Capture Intent

Interview the user:
1. What should this subagent do?
2. When should it be delegated to? (description triggering)
3. What model, tools, skills, limits?
4. What's the expected output format?

### 2. Draft the AgentDef

Generate `PROFILE.md` + `config.yaml` based on the interview. The same
`subagent_generate` tool produces the draft. User approves before next step.

### 3. Create Test Cases

2-3 realistic task prompts the user would actually delegate to this subagent.
Saved as `evals/evals.json`:

```json
{
  "agent_name": "company-researcher",
  "evals": [
    {"id": 1, "prompt": "Research Tesla's competitive position in EV market..."},
    {"id": 2, "prompt": "Analyze Apple's supply chain vulnerabilities..."},
    {"id": 3, "prompt": "Compare Coca-Cola and PepsiCo business models..."}
  ]
}
```

### 4. Run Tests (Baseline Comparison)

For each test case, spawn two subagents in parallel:
- **With-agent**: the drafted subagent, executing the test prompt
- **Baseline**: a general-purpose agent (no specialist config), same prompt

Captures: outputs, timing (duration_ms), tokens, cost.

### 5. Grade + Aggregate

- **Grading**: assertion-based (objectively verifiable output checks) +
  qualitative human review for subjective outputs
- **Aggregate**: `benchmark.json` with pass rate, mean ± stddev for time and
  tokens, delta vs baseline
- **Viewer**: browser-based review UI with "Outputs" tab (per-test-case
  review + feedback) and "Benchmark" tab (stats summary)

### 6. Iterate

User reviews outputs, provides feedback. Agent generalizes from feedback,
improves the system prompt + config, reruns tests into `iteration-N+1/`.
Repeat until the user is satisfied or no meaningful improvement.

### 7. Description Optimization

The `description` field in PROFILE.md frontmatter is the primary mechanism
that determines when the main agent delegates to this subagent. After the
subagent is finalized:

- Generate 20 trigger eval queries (10 should-trigger, 10 near-miss
  should-not-trigger)
- User reviews the eval set
- Optimization loop: 60/40 train/test split, evaluate, refine description,
  iterate up to 5x
- Apply the `best_description` to PROFILE.md

## Relationship to Skill Creator

Skills and subagents use **the same open standard format** (Agentskills.io
spec). A subagent's `PROFILE.md` is structurally identical to a skill's
`SKILL.md` — YAML frontmatter (`name`, `description`) + markdown body.
Subagents add config fields (`model`, `tools`, `skills`, limits) that
skills don't need, but the creation + evaluation pipeline is identical.

A shipped `subagent-creator` skill will mirror `skill-creator` exactly,
differing only in:
- Output format: `PROFILE.md` + `config.yaml` instead of `SKILL.md`
- Tool selection: picks from registry instead of assuming fixed tools
- Model selection: picks from model registry
- Config validation: `validate_agent_def()` before saving

Both skills can share the same eval infrastructure (`evals.json`,
`benchmark.json`, grading, viewer).

## Open Questions

1. Should `subagent_generate` be a new tool or overload `subagent_create`
   with a `generate` flag? Leaning toward new tool for clarity.

2. Should the card show tool descriptions alongside names? (e.g., tooltip or
   subtitle for each tool). Leaning toward yes — helps the user validate
   the agent's choices.

3. Can the user also create a subagent from scratch with the same card (empty
   fields, manual fill)? Leaning toward yes — same UI, two entry points:
   manual and auto-generated.

4. Should `subagent-creator` be a shipped seed subagent (always available)
   or a skill that the main agent loads? Leaning toward a shipped subagent
   definition, since it needs tools and model config that skills don't
   typically carry.
