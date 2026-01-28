# Flows & Agent Builder Guide

# Flows (Scheduled/Immediate Multi-Step Runs)

Use flows when you want the assistant to execute a structured sequence of steps now or on a schedule. Flows do **not** require MCP.

## Flow tools
- `create_flow(...)` (references `agent_ids` from registry)
- `list_flows(status=None)`
- `run_flow(flow_id)`
- `cancel_flow(flow_id)`
- `delete_flow(flow_id)`

Note: If a user asks to list/see flows, always call `list_flows` and report its output (do not infer from memory).

## Flow mode (same feature as flows)
Flow mode is the same flows feature, but it puts the assistant into build/test mode for agents + flows. Trigger it with `/flow on` or prefix `FLOW MODE:`.

## Create agents first
Use `create_agent` to register mini agents per user. Flows reference them by `agent_ids`.

## Input payloads
Flows can pass an `flow_input` (a JSON object) into the **first agent**. If the first agent’s prompt
includes `$input`, it will be replaced with the JSON payload. Subsequent agents only receive
`$output` from the immediately prior agent.

Note:
- If `schedule_type` is `immediate` or `scheduled`, omit `cron_expression`.
- Use `schedule_type: "cron"` (alias for `recurring`) **with** `cron_expression` for recurring flows.
- `flow_input` is **required** whenever the first agent needs external inputs (URLs, IDs, parameters).

Example: input payload + prompt usage
```json
{
  "agent_id": "news_scraper",
  "description": "Scrape article",
  "tools": ["firecrawl_scrape"],
  "system_prompt": "You will receive $input as JSON. Parse it and call firecrawl_scrape with its url field. Return only markdown."
}
```

## AgentSpec

### Agent Prompt Format (required)
**Structured output:** Define `output_schema` so downstream agents know the shape of the output.

When you define a mini‑agent, write its system prompt in a strict, tool‑calling format so the runtime can actually invoke tools.

**Template (minimal):**
- State **exactly** which tool to call and which input fields to use.
- `$input` and `$output` are **JSON strings** (no dot‑notation interpolation).
- Tell the agent to **parse JSON** and extract fields it needs.
- Return **only** what the next agent needs (no extra text).

Example:
```
You are the crawl agent.
Parse $input JSON and call firecrawl_crawl with its url field.
Return only the raw JSON response.
```

Example with chaining:
```
You are the summary agent.
Parse $output JSON and summarize its text in 3 bullets.
Return only the bullets.
```

**Short input/output example (non‑file):**
```
$input example: {"url":"https://example.com"}
$output example: {"markdown":"# Title\nContent..."}
```

**Common mistakes (avoid):**
- Writing descriptive prompts without an explicit tool call.
- Using `{url}` instead of `$input.url`.
- Returning prose plus tool output.

 (required fields)
Each agent must include all required fields:
- `agent_id` (string)
- `description` (string)
- `tools` (list of tool names)
- `system_prompt` (string)

Constraints:
- Mini agents should use **≤5 tools**, hard cap **10 tools**.
- Use `$input` in the first agent prompt to consume `flow_input`.
- Use `$output` to consume the prior agent’s output.
- If you need structured outputs, define `output_schema` in the agent and the flow runner will enforce JSON output.

## Minimal example (immediate)
```json
{
  "name": "test_flow",
  "description": "Test flow",
  "schedule_type": "immediate",
  "agent_ids": ["runner_1"],
  "flow_input": {"url": "https://example.com"},
  "run_mode": "normal"
}
```

## Scheduled example (cron)
```json
{
  "name": "daily_brief",
  "description": "Daily 9am summary",
  "schedule_type": "cron",
  "cron_expression": "0 9 * * *",
  "agent_ids": ["summarizer"],
  "run_mode": "normal"
}
```


## Execute‑Python prompt checklist (quick)
Use this when a mini‑agent uses `execute_python` so it’s deterministic and returns the right thing.

**Template:**
```
You are a Python execution agent. Use only the execute_python tool.
Goal: <what must be produced>
Inputs: $input.<field>, $output (if needed)
Outputs: Print ONLY <exact output>
Constraints: <no extra text / no network / must write to output/...>
Success: <single pass/fail criterion>
Do: <required steps>
Don’t: <forbidden steps>
```

**Example:**
```
You are a Python execution agent. Use only the execute_python tool.
Goal: Download PDF from $input.url to output/invoice.pdf
Outputs: Print ONLY output/invoice.pdf
Constraints: No extra text. Ensure output/ exists.
Success: output/invoice.pdf exists and is >0 bytes.
```

**Deterministic option:**
- If you need maximum reliability, embed a concrete code block and instruct:
  "Call execute_python with exactly this code (no edits)."

## Important
- You must **create agents first** (using `create_agent`).
- `create_flow` only accepts `agent_ids` (no inline agents).

## Notes
- schedule_type aliases: `once` → `scheduled`, `cron` → `recurring`.
- Flow agents cannot call flow tools (no nesting).


## Examples (progressive)

### 1) Single-step, immediate
```json
{
  "name": "ping",
  "description": "Quick sanity run",
  "schedule_type": "immediate",
  "agent_ids": ["ping_agent"],
  "run_mode": "normal"
}
```

### 2) Single-step, scheduled (cron)
```json
{
  "name": "daily_checkin",
  "description": "Daily status note",
  "schedule_type": "cron",
  "cron_expression": "0 9 * * *",
  "agent_ids": ["checkin"],
  "run_mode": "normal"
}
```



### 2b) Single-step, one-off at a specific time
```json
{
  "name": "one_off_reminder_flow",
  "description": "Run once at a specific time",
  "schedule_type": "once",
  "schedule_time": "2026-02-01 09:30",
  "agent_ids": ["notifier"],
  "run_mode": "normal"
}
```

### 3) Two-step, immediate (handoff)
```json
{
  "name": "summary_and_report",
  "description": "Summarize TDB data and write a report",
  "schedule_type": "immediate",
  "agent_ids": ["summarizer", "writer"],
  "run_mode": "normal"
}
```

### 4) Multi-step with web + VDB + file output
```json
{
  "name": "weekly_market_watch",
  "description": "Collect, store, and summarize weekly market notes",
  "schedule_type": "cron",
  "cron_expression": "0 8 * * 1",
  "agent_ids": ["collector", "summarizer"],
  "run_mode": "normal"
}
```


## Troubleshooting
- If you see “agent_id not found”, create the agent first using `create_agent`, then reference it by `agent_ids`.
- If you see “Field required” errors when creating an agent, supply all AgentSpec fields listed above.


### Create an agent (AgentSpec)
When calling `create_agent`, you MUST include AgentSpec fields. Flows reference agents by `agent_ids`.

Example:
```json
{
  "agent_id": "demo_agent",
  "description": "Do the task",
  "tools": ["execute_python"],
  "system_prompt": "Run the task and return the output."
}
```


## Flow Project Workspace
During flow research/design/dev, create a hidden flow project to store artifacts:
- `create_flow_project("project-name")`
- This creates `./data/{thread_id}/.{project}/` with:
  - `research.md`
  - `plan.md`
  - `progress.md`
  - `tests.md`


### Example: Create flow project
```
create_flow_project("weekly-brief")
```

## Flow/Agent Design Framework (progressive)

### Level 1 — Quick (simple tasks)
1) **Clarify & Recap** — restate the goal and success criteria in 1–2 sentences.
2) **Decompose** — list the minimal steps and required inputs.
3) **Validate & Handoff** — confirm outputs match the expected format before continuing.

### Level 2 — Standard (multi‑step tasks)
1) **Clarify & Recap** — include scope + constraints.
2) **Research (if needed)** — resolve jargon/unknowns before designing.
3) **Decompose** — define stages with explicit inputs/outputs.
4) **Design Options** — propose 1–3 viable approaches; recommend one.
5) **Test‑Driven Build** — define expected output schema + minimal test cases; run tools to validate.
6) **Validate & Handoff** — verify outputs before passing to the next agent.

### Level 3 — Complex (high‑risk or long flows)
1) **Clarify & Recap** — confirm scope, constraints, success criteria, and failure modes.
2) **Research** — use tools to validate assumptions and gather facts.
3) **Decompose** — break into stages with explicit I/O contracts.
4) **Design Options** — compare 1–3 approaches with trade‑offs; choose one.
5) **Test‑Driven Build** — design tests per stage; run tools to verify each stage.
6) **Validate & Handoff** — enforce schema checks between stages.
7) **Fallbacks** — if blocked, propose alternatives or a simplified path.

---

# Flow + Agent Builder Guide

This skill teaches how to design **mini‑agents** and **flows** that actually run tools, return structured outputs, and pass clean inputs between steps. Use this when creating agents or troubleshooting flow failures.

## Available tools (common)
Web:
- `search_web` (search results)
- `firecrawl_scrape` (single page → markdown)
- `firecrawl_crawl` (site crawl → job id)
- `firecrawl_check_status` (poll crawl)
- `playwright_scrape` (JS-heavy pages; requires Playwright install)

Files/TDB/VDB:
- `write_file`, `read_file`, `list_files`
- `query_tdb`, `create_tdb_table`, `list_tdb_tables`
- `create_vdb_collection`, `add_vdb_documents`, `search_vdb`

## Flow mode (same feature as flows)
Use `/flow on` or prefix `FLOW MODE:` to enter flow mode. This is the same flows feature, but it puts the assistant into build/test mode for agents + flows.

## Quick test (single agent)
Use `run_agent` to test a mini‑agent without creating a flow:
```
run_agent(agent_id="web_crawl_agent", flow_input={"url":"https://example.com"})
```

## Level 1 — Minimal working flow
**Goal:** single agent that calls one tool and returns a single value.

**Mini‑agent prompt template:**
```
You are the crawl agent.
Call firecrawl_scrape with url=$input.url.
Return only the markdown string.
```

**Flow requirements:**
- `flow_input` must include required fields (e.g., `url`).
- First agent prompt must reference `$input` if you pass `flow_input`.

## Level 2 — Structured output + chaining
**Goal:** multi‑agent flow with defined JSON outputs.

**AgentSpec rules:**
- `output_schema` must describe the JSON keys you return.
- Prompt must say “Return JSON matching output_schema.”
- Use `$output` only when needed.

**Example (extract → summarize):**
```
You are the summary agent.
Summarize $output in 3 bullets.
Return JSON matching output_schema with key `summary`.
```


## Execute‑Python prompt checklist (use for `execute_python` agents)
Use this template for Python agents so they reliably run code and return the right output.

**Template:**
```
You are a Python execution agent. Use only the execute_python tool.

Goal:
- <what must be produced>

Inputs:
- $input.<field> = <meaning>
- $output = <meaning> (if needed)

Outputs:
- Print ONLY: <exact string or JSON to print>

Constraints:
- <no extra text / no network / must write to output/...>

Success:
- <single pass/fail criterion>

Do:
- <required steps>

Don’t:
- <forbidden steps>
```

**Example:**
```
You are a Python execution agent. Use only the execute_python tool.

Goal:
- Download a PDF from $input.url and save it to output/invoice.pdf.

Inputs:
- $input.url = PDF URL

Outputs:
- Print ONLY the file path: output/invoice.pdf

Constraints:
- No extra text.
- Create output/ if missing.

Success:
- output/invoice.pdf exists and is > 0 bytes.

Do:
- Use urllib.request.urlretrieve.
- Ensure output folder exists.

Don’t:
- Print anything else.
```

## Level 3 — Test‑driven flow design (framework)
Use this framework for complex flows:
1) Clarify & recap goal, scope, constraints, success criteria.
2) Research unknowns (use tools) before designing.
3) Decompose into stages with explicit inputs/outputs.
4) Propose 1–3 designs; recommend one.
5) Define output_schema + small test cases per stage.
6) Validate each stage output before chaining.
7) If blocked, suggest alternatives or simplified path.

## Common failures + fixes
- **Unknown tool(s):** use tool names exactly as registered (see list above).
- **Empty outputs:** prompt did not explicitly call a tool.
- **Recursion limit:** model kept “thinking” without tool call → fix prompt.
- **Wrong inputs:** use `$input.<field>` not `{field}`.

## Quick checklist (before running)
- Agent tools list ≤ 5 (max 10).
- Prompt contains explicit tool call.
- First agent uses `$input` if payload provided.
- Later agents use `$output` if needed.
- output_schema is defined and referenced.
