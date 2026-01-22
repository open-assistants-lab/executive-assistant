# Flows (Scheduled/Immediate Multi-Step Runs)

Use flows when you want the assistant to execute a structured sequence of steps now or on a schedule. Flows do **not** require MCP.

## Flow tools
- `create_flow(...)` (references `agent_ids` from registry)
- `list_flows(status=None)`
- `run_flow(flow_id)`
- `cancel_flow(flow_id)`
- `delete_flow(flow_id)`

## Create agents first
Use `create_agent` to register mini agents per user. Flows reference them by `agent_ids`.

## Input payloads
Flows can pass an `input_payload` (a JSON object) into the **first agent**. If the first agent’s prompt
includes `$flow_input`, it will be replaced with the JSON payload. Subsequent agents only receive
`$previous_output` from the immediately prior agent.

Note:
- If `schedule_type` is `immediate` or `scheduled`, omit `cron_expression`.
- Use `schedule_type: "cron"` (alias for `recurring`) **with** `cron_expression` for recurring flows.
- `input_payload` is **required** whenever the first agent needs external inputs (URLs, IDs, parameters).

Example: input payload + prompt usage
```json
{
  "agent_id": "news_scraper",
  "description": "Scrape article",
  "tools": ["firecrawl_scrape"],
  "system_prompt": "Use firecrawl_scrape on $flow_input.url and return only the markdown."
}
```

## AgentSpec

### Agent Prompt Format (required)
**Structured output:** Define `output_schema` so downstream agents know the shape of the output.

When you define a mini‑agent, write its system prompt in a strict, tool‑calling format so the runtime can actually invoke tools.

**Template (minimal):**
- State **exactly** which tool to call and which input fields to use.
- Use `$flow_input.<field>` **only if** the agent needs flow input (typically the first agent).
- Use `$previous_output` **only if** the agent needs the prior agent’s output.
- Return **only** what the next agent needs (no extra text).

Example:
```
You are the crawl agent.
Call firecrawl_crawl with url=$flow_input.url.
Return only the raw JSON response.
```

Example with chaining:
```
You are the summary agent.
Summarize $previous_output in 3 bullets.
Return only the bullets.
```

**Common mistakes (avoid):**
- Writing descriptive prompts without an explicit tool call.
- Using `{url}` instead of `$flow_input.url`.
- Returning prose plus tool output.

 (required fields)
Each agent must include all required fields:
- `agent_id` (string)
- `description` (string)
- `tools` (list of tool names)
- `system_prompt` (string)

Constraints:
- Mini agents should use **≤5 tools**, hard cap **10 tools**.
- Use `$flow_input` in the first agent prompt to consume `input_payload`.
- Use `$previous_output` to consume the prior agent’s output.
- If you need structured outputs, define `output_schema` in the agent and the flow runner will enforce JSON output.

## Minimal example (immediate)
```json
{
  "name": "test_flow",
  "description": "Test flow",
  "schedule_type": "immediate",
  "agent_ids": ["runner_1"],
  "input_payload": {"url": "https://example.com"},
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
  "description": "Summarize DB data and write a report",
  "schedule_type": "immediate",
  "agent_ids": ["summarizer", "writer"],
  "run_mode": "normal"
}
```

### 4) Multi-step with web + VS + file output
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
During flow research/design/dev, create a hidden workspace to store artifacts:
- `create_flow_project_workspace("project-name")`
- This creates `./data/{user_id}/.{project}/` with:
  - `research.md`
  - `plan.md`
  - `progress.md`
  - `tests.md`


### Example: Create workspace
```
create_flow_project_workspace("weekly-brief")
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