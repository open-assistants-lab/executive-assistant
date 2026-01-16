# Workflow Design: Chain of Executors

## Goal

Enable Cassey to create workflows on-the-fly with scheduling (one-off or recurring) using a chain of `create_agent()` executors.

## Key Principles

1. **Simplicity**: Each executor is a `create_agent()` with specific tools and prompt
2. **Structured Flow**: Previous executor's structured output → next executor's input
3. **No Explicit Control Flow**: Loops embedded in prompt (e.g., "run 5 times", "for each item")
4. **Full Observability**: Track all executor outputs, tool calls, and errors for troubleshooting

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Cassey                              │
│  (create_agent with workflow tools)                         │
│                                                             │
│  Tool: create_workflow()                                    │
│  Input: List of executor specs                              │
│  Output: workflow_id                                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Creates
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Workflow Storage                        │
│  workflows table stores:                                     │
│  - workflow_id, name, status                                 │
│  - executors[] (JSON array)                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Execution time
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Executor Chain                              │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐│
│  │ Executor 1   │───▶│ Executor 2   │───▶│ Executor 3   ││
│  │              │    │              │    │              ││
│  │ create_agent │    │ create_agent │    │ create_agent ││
│  │              │    │              │    │              ││
│  │ Tools: [...] │    │ Tools: [...] │    │ Tools: [...] ││
│  │ Prompt:      │    │ Prompt:      │    │ Prompt:      ││
│  │ "You are     │    │ "Previous    │    │ "Previous     ││
│  │  first..."   │    │  result:     │    │  result:     ││
│  │              │    │  {...}"      │    │  {...}"      ││
│  │              │    │              │    │              ││
│  │ Structured   │    │ Structured   │    │ Structured   ││
│  │ Output       │    │ Output       │    │ Output       ││
│  └──────────────┘    └──────────────┘    └──────────────┘│
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Shared Workflow Context                       │ │
│  │  - All structured outputs accumulated                 │ │
│  │  - Shared variables                                  │ │
│  │  - Execution state                                    │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Executor Specification

```python
from pydantic import BaseModel
from typing import Literal, Optional

class ExecutorSpec(BaseModel):
    """Definition of a single executor in the workflow."""

    executor_id: str
    name: str
    description: str

    # Agent configuration
    model: str  # e.g., "gpt-4o", "gpt-4o-mini"
    tools: list[str]  # Tool names from Cassey's registry
    system_prompt: str

    # Structured output schema
    output_schema: dict  # What this executor returns

    # Behavior (embedded in prompt, not explicit control flow)
    # Examples:
    # - "Call search_tool up to 5 times collecting results"
    # - "For each item in previous output, call process_tool"
    # - "Keep calling fetch_tool until status='complete'"
    iteration_hint: Optional[str] = None

class WorkflowSpec(BaseModel):
    """Workflow definition."""

    workflow_id: str
    name: str
    description: str

    # Chain of executors
    executors: list[ExecutorSpec]

    # Scheduling
    schedule_type: Literal["immediate", "scheduled", "recurring"]
    schedule_time: Optional[str] = None
    cron_expression: Optional[str] = None

    # Notification
    notify_on_complete: bool = False
    notify_on_failure: bool = True
```

---

## Prompt Injection with Structured Outputs

### Approach: Structured Prompt Injection

Previous executor outputs are injected as structured JSON in the next executor's prompt:

```python
# Build input with structured previous outputs
messages = [
    SystemMessage(content=executor_spec.system_prompt),
    HumanMessage(content=f"""Previous executor outputs:
{json.dumps(previous_outputs, indent=2)}

Now execute your task.""")
]
```

### Why Prompt Injection (vs State)?

| Aspect | Prompt Injection | Custom State |
|--------|------------------|--------------|
| Simplicity | ✅ Simpler, no custom state | ❌ More complex setup |
| Schema enforcement | ✅ Structured JSON | ✅ Native enforcement |
| Debuggability | ✅ Clear data flow | ✅ State inspection |
| Token efficiency | ✅ Only what's needed | ✅ Binary format |
| LangGraph nativity | ⚠️ Works with create_agent | ✅ Native pattern |

**Verdict**: Prompt injection with structured JSON gives us the right balance.

---

## Example Workflow

```python
workflow_spec = {
    "workflow_id": "daily_price_monitor",
    "name": "Daily Competitor Price Monitor",
    "description": "Check competitor prices and alert on changes",

    "executors": [
        {
            "executor_id": "fetch_prices",
            "name": "Price Fetcher",
            "description": "Fetch prices from multiple competitors",

            "model": "gpt-4o-mini",
            "tools": ["search_web"],

            "system_prompt": """You are a price fetcher.

Your job: Fetch current prices for these products:
- Apple iPhone 15 Pro (ASIN: B08X12345)
- Samsung Galaxy S24 (ASIN: B08X67890)

For EACH product, search Amazon and Walmart.
Build a structured result with all prices.

Return JSON with this schema:
{
    "prices": [
        {"product": "str", "competitor": "str", "price": "float", "url": "str"}
    ]
}

Iteration hint: Search each product+competitor combination (4 total searches).""",

            "output_schema": {
                "prices": [{"product": "str", "competitor": "str", "price": "float", "url": "str"}]
            }
        },

        {
            "executor_id": "compare_prices",
            "name": "Price Comparator",
            "description": "Compare against historical data and check thresholds",

            "model": "gpt-4o",
            "tools": ["query_db"],  # Has access to historical prices

            "system_prompt": """You are a price comparator.

Previous executor output is available as $previous_output.

Your job:
1. Query the price_history table for these products
2. Compare current prices with most recent historical price
3. Flag any price changes > 10%
4. Return structured list of alerts

Return JSON with this schema:
{
    "alerts": [
        {"product": "str", "old_price": "float", "new_price": "float", "change_percent": "float"}
    ],
    "summary": "str"
}""",

            "output_schema": {
                "alerts": [{"product": "str", "old_price": "float", "new_price": "float", "change_percent": "float"}],
                "summary": "str"
            }
        },

        {
            "executor_id": "send_alerts",
            "name": "Alert Sender",
            "description": "Send notifications for price alerts",

            "model": "gpt-4o-mini",
            "tools": ["send_message", "write_file"],

            "system_prompt": """You are an alert sender.

Previous executor output is available as $previous_output.

Your job:
1. If there are alerts, send a message with the summary
2. Also save the alert details to price_alerts.txt
3. Return confirmation

No alerts? Just log "No price alerts today" to file.

Return JSON with this schema:
{
    "status": "str",  // "sent" | "no_alerts" | "failed"
    "message_count": "int",
    "file_saved": "bool"
}""",

            "output_schema": {
                "status": "str",
                "message_count": "int",
                "file_saved": "bool"
            }
        }
    ],

    "schedule_type": "recurring",
    "cron_expression": "0 9 * * MON-FRI",  # Weekdays at 9am
    "notify_on_complete": true,
    "notify_on_failure": true
}
```

---

## Loops in Prompt (No Explicit Control Flow)

Loops are embedded in the prompt, not as explicit workflow constructs:

| Loop Type | Prompt Example |
|-----------|---------------|
| **Fixed count** | "Call search_tool exactly 5 times with different queries" |
| **For each** | "For each item in $previous_output.prices, call process_tool" |
| **Until condition** | "Keep calling fetch_tool until status='complete' or max 10 tries" |
| **While true** | "While items remain in the list, process them one by one" |

The agent handles iteration internally, returning aggregated results in structured output.

---

## Database Schema

### Workflow Definitions

```sql
-- Workflow definitions (created by Cassey)
CREATE TABLE workflows (
    id              SERIAL PRIMARY KEY,
    workflow_id     UUID DEFAULT gen_random_uuid(),  -- Public ID
    user_id         VARCHAR(255) NOT NULL,
    thread_id       VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,

    -- Workflow definition (JSON)
    executors       JSONB NOT NULL,  -- Array of ExecutorSpec objects

    -- Scheduling
    schedule_type   VARCHAR(20) NOT NULL,  -- 'immediate', 'scheduled', 'recurring'
    cron_expression VARCHAR(100),            -- NULL for one-off
    next_run_time   TIMESTAMP,

    -- Status
    status          VARCHAR(20) DEFAULT 'active',  -- active, paused, archived

    -- Execution tracking
    total_runs      INTEGER DEFAULT 0,
    successful_runs INTEGER DEFAULT 0,
    failed_runs     INTEGER DEFAULT 0,

    -- Timestamps
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_schedule CHECK (
        schedule_type IN ('immediate', 'scheduled', 'recurring')
    )
);

CREATE INDEX idx_workflows_user ON workflows(user_id);
CREATE INDEX idx_workflows_next_run ON workflows(next_run_time)
    WHERE status = 'active' AND next_run_time IS NOT NULL;
```

### Workflow Runs

```sql
-- Individual workflow execution runs
CREATE TABLE workflow_runs (
    id              SERIAL PRIMARY KEY,
    run_id          UUID DEFAULT gen_random_uuid(),
    workflow_id     INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    user_id         VARCHAR(255) NOT NULL,
    thread_id       VARCHAR(255) NOT NULL,

    -- Execution tracking
    status          VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    current_executor INTEGER,
    total_executors INTEGER,

    -- Results
    result          JSONB,
    error_message   TEXT,

    -- Timestamps
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_workflow_runs_workflow ON workflow_runs(workflow_id);
CREATE INDEX idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX idx_workflow_runs_created ON workflow_runs(created_at);
```

### Executor Runs (Troubleshooting & Auditing)

```sql
-- Executor runs (each executor in each workflow execution)
CREATE TABLE workflow_executor_runs (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID NOT NULL,              -- Parent workflow run
    executor_id         VARCHAR(255) NOT NULL,       -- executor_id from spec
    executor_name       VARCHAR(255) NOT NULL,

    -- Input
    input_data          JSONB,                      -- What this executor received

    -- Execution
    model               VARCHAR(100),               -- e.g., "gpt-4o"
    tools_used          JSONB,                      -- List of tools actually called

    -- Output
    status              VARCHAR(20),                -- success, failed, skipped
    structured_output   JSONB,                      -- The structured output

    -- Metrics
    total_tokens        INTEGER,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    duration_ms         INTEGER,

    -- Error handling
    error_message       TEXT,
    retry_count         INTEGER DEFAULT 0,

    -- Timing
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,

    CONSTRAINT valid_status CHECK (status IN ('success', 'failed', 'skipped'))
);

CREATE INDEX idx_executor_runs_run ON workflow_executor_runs(run_id);
CREATE INDEX idx_executor_runs_status ON workflow_executor_runs(status);
CREATE INDEX idx_executor_runs_executor ON workflow_executor_runs(executor_id);

-- Tool call details (for granular auditing)
CREATE TABLE workflow_tool_calls (
    id                  SERIAL PRIMARY KEY,
    executor_run_id     INTEGER REFERENCES workflow_executor_runs(id),

    tool_name           VARCHAR(255) NOT NULL,
    tool_input          JSONB,
    tool_output         JSONB,

    status              VARCHAR(20),                -- success, failed, timeout
    error_message       TEXT,
    duration_ms         INTEGER,

    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);

CREATE INDEX idx_tool_calls_executor ON workflow_tool_calls(executor_run_id);
```

---

## Update: Recommendations (2026-01-16)

### 1) Explicit loop control (code-owned, not prompt-owned)
Add a `loop` field to `ExecutorSpec` so the runtime enforces iteration limits and stop conditions:

```python
class LoopSpec(BaseModel):
    type: Literal["none", "for_each", "repeat_until"]
    input_path: Optional[str] = None
    max_items: Optional[int] = None
    max_iters: Optional[int] = None
    predicate_path: Optional[str] = None
    predicate_value: Optional[str] = None
```

### 2) Structured output validation + retry
Enforce JSON-only output and validate via Pydantic/JSON schema. On validation failure, retry with a correction prompt (bounded, e.g., 2-3 retries).

### 3) Large output handling (DB/KB/file refs)
If executor output exceeds a threshold, store the full payload in DB/KB/file and pass only a `summary` + `output_ref` to the next executor:

```json
{
  "summary": "Fetched 120 prices; 8 alerts over 10% change.",
  "output_ref": {
    "type": "file",
    "path": "data/users/<thread_id>/workflows/<run_id>/executor_fetch_prices.json"
  },
  "meta": {"count": 120}
}
```

### 4) Replace scheduled_jobs
Use workflows as the only scheduled execution mechanism:
1. Scheduler queries due workflows and creates `workflow_runs`.
2. Drop `scheduled_jobs` + tools after migration (optional if you plan a clean break).

### 5) Tool registry snapshot/versioning
Store a tool manifest snapshot + hash when a workflow is created. At runtime, fail or warn if current tools differ:

```json
{
  "version": "2026-01-16",
  "hash": "sha256:...",
  "tools": [{"name": "search_web", "args": {"query": "str"}}]
}
```

### 6) Cancellation/resume + partial success
Track `current_executor` and per-executor outcomes. On failure, mark the run `partial_success`, keep the last successful output, and allow resume from the next executor.

---

## Mini-Spec: Workflow Tables (lean, resumable)

### workflows
```sql
CREATE TABLE workflows (
    id                  SERIAL PRIMARY KEY,
    workflow_id         UUID DEFAULT gen_random_uuid(),
    user_id             VARCHAR(255) NOT NULL,
    thread_id           VARCHAR(255) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,

    executors           JSONB NOT NULL,

    tool_manifest_hash  TEXT,
    tool_manifest_json  JSONB,
    tool_manifest_version TEXT,

    schedule_type       VARCHAR(20) NOT NULL,
    schedule_time       TIMESTAMP,
    cron_expression     VARCHAR(100),
    next_run_time       TIMESTAMP,

    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
```

### workflow_runs
```sql
CREATE TABLE workflow_runs (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID DEFAULT gen_random_uuid(),
    workflow_id         INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    user_id             VARCHAR(255) NOT NULL,
    thread_id           VARCHAR(255) NOT NULL,

    status              VARCHAR(30) DEFAULT 'pending',
    current_executor    INTEGER DEFAULT 0,
    total_executors     INTEGER,

    final_output_ref    JSONB,
    final_output_summary TEXT,
    error_message       TEXT,

    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

### workflow_executor_runs
```sql
CREATE TABLE workflow_executor_runs (
    id                  SERIAL PRIMARY KEY,
    workflow_run_id     INTEGER REFERENCES workflow_runs(id) ON DELETE CASCADE,
    executor_id         VARCHAR(255) NOT NULL,
    executor_name       VARCHAR(255) NOT NULL,

    input_ref           JSONB,
    input_summary       TEXT,

    structured_output_ref JSONB,
    structured_output_summary TEXT,

    status              VARCHAR(20),
    tools_used          JSONB,
    error_message       TEXT,
    duration_ms         INTEGER,

    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);
```

### workflow_tool_calls (optional, debug-only)
```sql
CREATE TABLE workflow_tool_calls (
    id                  SERIAL PRIMARY KEY,
    executor_run_id     INTEGER REFERENCES workflow_executor_runs(id),
    tool_name           VARCHAR(255) NOT NULL,
    tool_input_ref      JSONB,
    tool_output_ref     JSONB,
    status              VARCHAR(20),
    error_message       TEXT,
    duration_ms         INTEGER,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);
```

### output_ref shape
```json
{
  "type": "file|kb|db",
  "path": "data/users/<thread_id>/workflows/<run_id>/executor_x.json",
  "kb_id": "optional",
  "table": "optional",
  "row_id": "optional"
}
```

---

## Is this bloated?
It can be, if you enable full tool-call auditing and store full payloads inline. A lean path:
- Phase 1: `workflows` + `workflow_runs` + `workflow_executor_runs` only, store summaries + file refs.
- Phase 2 (optional): `workflow_tool_calls` table and tool payload refs when debugging is needed.
- Store the tool manifest hash by default, and store the full manifest JSON only when `DEBUG_WORKFLOWS=true`.

## What Gets Tracked

| Field | Purpose | Example |
|-------|---------|---------|
| `input_data` | What executor received | Previous outputs + task |
| `structured_output` | What executor returned | Prices summary |
| `tools_used` | Which tools were called | ["search_web", "query_db"] |
| `tool_calls` | Detailed tool calls | Full input/output per tool |
| `total_tokens` | Cost tracking | 1234 prompt, 567 completion |
| `duration_ms` | Performance | 2500ms |
| `error_message` | Troubleshooting | "Search API timed out" |

---

## Tools for Cassey

```python
@tool
def create_workflow(
    name: str,
    description: str,
    executors: list[dict],
    schedule_type: str = "immediate",
    schedule_time: str = None,
    cron_expression: str = None,
    user_id: str = None,
    thread_id: str = None
) -> str:
    """
    Create a workflow from a chain of executors.

    Each executor is a create_agent() with:
    - model: Which LLM to use
    - tools: List of tool names to include
    - system_prompt: What this executor does
    - output_schema: Expected structured output
    - iteration_hint: (Optional) How to iterate (embedded in prompt)

    The workflow executes executors sequentially, passing each
    executor's output to the next executor's prompt.

    Args:
        name: Workflow name
        description: What this workflow does
        executors: List of executor specifications
        schedule_type: 'immediate', 'scheduled', or 'recurring'
        schedule_time: For 'scheduled', when to run (natural language)
        cron_expression: For 'recurring', cron expression
        user_id: Your user ID
        thread_id: Current thread ID

    Returns:
        workflow_id for tracking/scheduling

    Example:
        executors = [
            {
                "executor_id": "fetch",
                "name": "Fetcher",
                "model": "gpt-4o-mini",
                "tools": ["search_web"],
                "system_prompt": "Search for prices...",
                "output_schema": {"prices": [{"product": "str", "price": "float"}]},
                "iteration_hint": "Search all 5 products"
            },
            {
                "executor_id": "summarize",
                "name": "Summarizer",
                "model": "gpt-4o",
                "tools": ["execute_python"],
                "system_prompt": "Previous output: {previous_output}. Summarize...",
                "output_schema": {"summary": "str", "avg_price": "float"}
            }
        ]
        create_workflow("Price Monitor", "Check prices", executors)
    """
    pass

@tool
def schedule_workflow(
    workflow_id: str,
    schedule_type: str,
    schedule_time: str = None,
    cron_expression: str = None,
    user_id: str = None
) -> str:
    """
    Schedule a workflow for execution.

    Args:
        workflow_id: ID from create_workflow()
        schedule_type: When to run
            - 'immediate': Run now
            - 'scheduled': Run once at schedule_time
            - 'recurring': Run on cron schedule
        schedule_time: For 'scheduled', natural language like "tomorrow 9am"
        cron_expression: For 'recurring', cron like "0 9 * * *" or "daily at 9am"
        user_id: Your user ID

    Returns:
        Scheduled job information
    """
    pass

@tool
def list_workflows(
    user_id: str,
    status: str = None
) -> list[dict]:
    """List your workflows."""
    pass

@tool
def get_workflow_run(
    run_id: str,
    user_id: str
) -> dict:
    """
    Get detailed execution history for a workflow run.

    Shows each executor, what it did, tool calls, outputs, and any errors.
    """
    pass

@tool
def list_failed_runs(
    user_id: str,
    workflow_id: str = None,
    limit: int = 10
) -> list[dict]:
    """List failed workflow runs for troubleshooting."""
    pass

@tool
def cancel_workflow(
    workflow_id: str = None,
    schedule_type: str = None,
    user_id: str = None
) -> str:
    """Cancel a workflow or scheduled runs."""
    pass

@tool
def run_workflow(
    workflow_id: str,
    user_id: str,
    thread_id: str
) -> dict:
    """Execute a workflow immediately (synchronous)."""
    pass
```

---

## Execution Engine

```python
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

class WorkflowExecutor:
    """Execute a workflow as a chain of create_agent() calls."""

    def __init__(self, cassey_tools_registry):
        self.tools_registry = cassey_tools_registry

    async def execute_workflow(
        self,
        workflow: WorkflowSpec,
        user_id: str,
        thread_id: str
    ) -> dict:
        """Execute the workflow executor by executor."""

        # Shared context across all executors
        context = {
            "workflow_id": workflow.workflow_id,
            "user_id": user_id,
            "thread_id": thread_id,
            "executor_outputs": {},  # Accumulated outputs
            "current_executor_index": 0
        }

        results = []

        # Execute each executor in sequence
        for i, executor_spec in enumerate(workflow.executors):
            context["current_executor_index"] = i

            try:
                # Build prompt with previous outputs
                system_prompt = self._build_prompt(executor_spec, context)

                # Get tools for this executor
                tools = await self._get_tools(executor_spec.tools)

                # Create the agent
                agent = create_agent(
                    model=executor_spec.model,
                    tools=tools,
                    prompt=system_prompt
                )

                # Invoke the agent
                result = await agent.ainvoke({
                    "messages": [
                        HumanMessage(content="Execute your task.")
                    ]
                })

                # Extract and track structured output
                structured_output = self._extract_structured_output(
                    result,
                    executor_spec.output_schema
                )

                # Store in context and database
                context["executor_outputs"][executor_spec.executor_id] = structured_output
                context["previous_output"] = structured_output

                # Track executor run for auditing
                await self._track_executor_run(
                    run_id=context["run_id"],
                    executor_spec=executor_spec,
                    input_data=context.get("previous_output"),
                    output_data=structured_output,
                    status="success"
                )

                results.append({
                    "executor_id": executor_spec.executor_id,
                    "status": "success",
                    "output": structured_output
                })

            except Exception as e:
                # Track failure
                await self._track_executor_run(
                    run_id=context["run_id"],
                    executor_spec=executor_spec,
                    input_data=context.get("previous_output"),
                    output_data=None,
                    status="failed",
                    error_message=str(e)
                )

                results.append({
                    "executor_id": executor_spec.executor_id,
                    "status": "failed",
                    "error": str(e)
                })

                break

        return {
            "workflow_id": workflow.workflow_id,
            "status": "completed" if all(r["status"] == "success" for r in results) else "failed",
            "executor_results": results,
            "final_output": context.get("previous_output")
        }

    def _build_prompt(self, executor_spec: ExecutorSpec, context: dict) -> str:
        """Build system prompt with previous outputs injected."""

        prompt = executor_spec.system_prompt

        # Inject previous outputs as structured JSON
        if "previous_output" in context:
            prompt = prompt.replace(
                "$previous_output",
                json.dumps(context["previous_output"], indent=2)
            )

        return prompt

    async def _get_tools(self, tool_names: list[str]) -> list:
        """Get tools by name from Cassey's registry."""
        from cassey.tools.registry import get_all_tools

        all_tools = await get_all_tools()
        tool_map = {tool.name: tool for tool in all_tools}

        return [tool_map[name] for name in tool_names if name in tool_map]
```

---

## Example Trace Output

```json
{
  "run_id": "uuid-1234",
  "workflow_id": "daily_price_monitor",
  "status": "failed",
  "started_at": "2025-01-16T09:00:00Z",
  "completed_at": "2025-01-16T09:02:30Z",

  "executor_runs": [
    {
      "executor_id": "fetch_prices",
      "status": "success",
      "duration_ms": 45000,
      "tokens": {"prompt": 1200, "completion": 800, "total": 2000},

      "structured_output": {
        "prices": [
          {"product": "iPhone 15", "competitor": "Amazon", "price": 999, "url": "..."}
        ]
      },

      "tool_calls": [
        {
          "tool": "search_web",
          "input": {"query": "Amazon iPhone 15 Pro price"},
          "output": {"results": [...]},
          "duration_ms": 2500
        },
        {
          "tool": "search_web",
          "input": {"query": "Walmart iPhone 15 Pro price"},
          "output": {"results": [...]},
          "duration_ms": 2100
        }
      ]
    },

    {
      "executor_id": "compare_prices",
      "status": "failed",
      "duration_ms": 120000,
      "error_message": "Database query timeout after 120s",

      "tool_calls": [
        {
          "tool": "query_db",
          "input": {"sql": "SELECT * FROM price_history WHERE..."},
          "status": "failed",
          "error_message": "Query timed out",
          "duration_ms": 120000
        }
      ]
    }
  ]
}
```

---

## Implementation Checklist

- [ ] Create workflow tables migration
- [ ] Implement `WorkflowStorage` class
- [ ] Implement `WorkflowExecutor` class
- [ ] Create workflow tools for Cassey
- [ ] Add workflow processing to scheduler
- [ ] Implement executor run tracking
- [ ] Implement tool call tracking
- [ ] Add troubleshooting tools (get_workflow_run, list_failed_runs)
- [ ] Add CLI/dashboard view for traces
- [ ] Documentation

---

## Summary

| Component | Design |
|-----------|--------|
| **Executor** | `create_agent()` with specific tools and prompt |
| **Prompt** | Includes previous executor's structured output as JSON |
| **Loops** | Embedded in prompt (e.g., "call tool 5 times", "for each item") |
| **Flow** | Sequential chain, output → input |
| **Tracking** | Full audit of executors, tool calls, tokens, timing |
| **Error handling** | Stop on failure, track errors for troubleshooting |
| **Complexity** | Minimal - just agent chain with structured outputs |

This keeps it barebone: agents execute, prompts guide behavior (including loops), structured output flows between them, and everything is tracked for observability.
