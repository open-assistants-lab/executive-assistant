# Workflow Design: Chain of Executors (Temporal-Based)

## Goal

Enable Cassey to create workflows on-the-fly with scheduling (one-off or recurring) using a chain of `create_agent()` executors, backed by Temporal for durable execution.

## Key Principles

1. **Simplicity**: Each executor is a `create_agent()` with specific tools and prompt
2. **Structured Flow**: Previous executor's structured output → next executor's input
3. **Durable Execution**: Temporal handles scheduling, retries, and state persistence
4. **Full Observability**: Temporal Web UI + workflow tracking for troubleshooting

---

## Temporal Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VM 1: Cassey Application                         │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Temporal Worker                                                   │ │
│  │                                                                   │ │
│  │  - Polls Temporal Server for workflow/activity tasks               │ │
│  │  - Executes workflow chains (executors)                           │ │
│  │  - Runs activities (agent calls, tool invocations)                │ │
│  │  - Connects to Cassey tools, SQLite, PostgreSQL                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                            ↕ gRPC (port 7233)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Network connection
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                      VM 2: Temporal Server (Self-Hosted)              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Temporal Server                                                   │ │
│  │                                                                   │ │
│  │  - Stores workflow state                                         │ │
│  │  - Manages durable timers                                         │ │
│  │  - Dispatches work to workers                                     │ │
│  │  - Provides observability UI (port 8080)                         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Frontend: 7233 (gRPC) │ UI: 8080 (web dashboard)                      │
│  PostgreSQL: Temporal's own state store                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Architecture with Temporal

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
                            │ Starts Temporal workflow
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Workflow                          │
│  (Durable, scheduled, retryable)                              │
│                                                             │
│  - Schedules itself at due_time (durable timer)              │
│  - Executes executor chain as activities                    │
│  - Tracks state across retries                               │
│  - Completes → sends notification if requested               │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Execution time
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Executor Chain (Activities)                 │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐│
│  │ Executor 1   │───▶│ Executor 2   │───▶│ Executor 3   ││
│  │              │    │              │    │              ││
│  │ Activity     │    │ Activity     │    │ Activity     ││
│  │              │    │              │    │              ││
│  │ Tools: [...] │    │ Tools: [...] │    │ Tools: [...] ││
│  │ Prompt:      │    │ Prompt:      │    │ Prompt:      ││
│  │ "You are     │    │ "Previous    │    │ "Previous     ││
│  │  first..."   │    │  result:     │    │  result:     ││
│  │              │    │  {...}"      │    │  {...}"      ││
│  │              │    │              │    │              ││
│  │ Structured   │    │ Structured   │    │ Structured   ││
│  │ Output       │    │ Output       │    │ Output       ││
│  │ (Retryable!)  │    │ (Retryable!)  │    │ (Retryable!)  ││
│  └──────────────┘    └──────────────┘    └──────────────┘││
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Shared Workflow Context (Temporal State)      │ │
│  │  - All structured outputs accumulated                 │ │
│  │  - Current executor index                              │ │
│  │  - Retry counts                                         │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Temporal Concepts Mapping

| Concept | Temporal Equivalent | Purpose |
|---------|-------------------|---------|
| **Workflow** | Temporal Workflow | Durable chain of activities |
| **Executor** | Activity | Single unit of work (agent call) |
| **Workflow definition** | Input to workflow | WorkflowSpec passed to `start_workflow()` |
| **Workflow execution** | Workflow Execution | Single run of a workflow (with run_id) |
| **Executor output** | Activity result | Return value from activity |
| **Scheduling** | Durable timer / Cron | `await asyncio.sleep()` or cron schedule |
| **Retry** | Retry Policy | Automatic activity retry on failure |
| **Observability** | Temporal Web UI | View history, search traces |
| **Worker** | Temporal Worker | Process that executes workflows/activities |

---

## Executor Specification

```python
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class ExecutorSpec(BaseModel):
    """Definition of a single executor (Temporal Activity) in the workflow."""

    executor_id: str
    name: str
    description: str

    # Agent configuration
    model: str  # e.g., "gpt-4o", "gpt-4o-mini"
    tools: list[str]  # Tool names from Cassey's registry
    system_prompt: str

    # Structured output schema
    output_schema: dict  # What this executor returns

    # Temporal activity configuration
    timeout_seconds: int = 300  # Activity timeout
    max_retries: int = 3  # Retry on failure
    retry_backoff: int = 60  # Seconds between retries

    # Loop control (code-owned, not prompt-owned)
    loop: Optional["LoopSpec"] = None

class LoopSpec(BaseModel):
    """Explicit loop control for executors."""
    type: Literal["none", "for_each", "repeat_until", "repeat_count"]
    input_path: Optional[str] = None  # JSONPath to iterate over (e.g., "$.prices")
    max_items: Optional[int] = None  # Max iterations
    max_iters: Optional[int] = None  # Max loop iterations
    predicate_path: Optional[str] = None  # JSONPath to check condition
    predicate_value: Optional[str] = None  # Value to compare against

class WorkflowSpec(BaseModel):
    """Workflow definition (passed to Temporal workflow)."""

    workflow_id: str
    name: str
    description: str

    # Chain of executors
    executors: list[ExecutorSpec]

    # Scheduling (Temporal handles this)
    schedule_type: Literal["immediate", "scheduled", "recurring"]
    schedule_time: Optional[datetime] = None  # For one-off scheduled
    cron_expression: Optional[str] = None  # For recurring (Temporal cron)

    # Notification
    notify_on_complete: bool = False
    notify_on_failure: bool = True
    notification_channel: Literal["telegram", "email", "web", "none"] = "telegram"

    # Temporal options
    workflow_timeout: Optional[int] = None  # Total workflow timeout (seconds)
    workflow_idempotency_key: Optional[str] = None  # For deduplication
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

### Why Prompt Injection (vs Temporal State)?

| Aspect | Prompt Injection | Temporal State |
|--------|------------------|---------------|
| Simplicity | ✅ Simpler, no custom state | ⚠️ More complex setup |
| Schema enforcement | ✅ Structured JSON | ✅ Native enforcement |
| Debuggability | ✅ Clear data flow | ✅ State inspection |
| Token efficiency | ✅ Only what's needed | ✅ Binary format |
| LangGraph nativity | ⚠️ Works with create_agent | ✅ Native pattern |

**Verdict**: Prompt injection with structured JSON gives us the right balance. Temporal stores the workflow state, but we pass outputs between activities via prompt injection.

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

## Database Schema (Simplified with Temporal)

With Temporal, many tracking tables become optional since Temporal provides built-in observability.

### Required Tables

```sql
-- Workflow definitions (created by users via Cassey)
CREATE TABLE workflows (
    id                  SERIAL PRIMARY KEY,
    workflow_id         UUID DEFAULT gen_random_uuid(),  -- Public ID
    user_id             VARCHAR(255) NOT NULL,
    thread_id           VARCHAR(255) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,

    -- Workflow definition (JSON)
    executors           JSONB NOT NULL,  -- Array of ExecutorSpec objects

    -- Temporal references
    temporal_workflow_id TEXT,             -- Temporal's workflow ID (for cancellation)
    task_queue          TEXT DEFAULT 'cassey-workflows',  -- Temporal task queue

    -- Status
    status              VARCHAR(20) DEFAULT 'active',  -- active, paused, archived

    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'archived'))
);

CREATE INDEX idx_workflows_user ON workflows(user_id);
CREATE INDEX idx_workflows_status ON workflows(status);
```

### Optional Tables (for additional metadata)

```sql
-- Optional: Link Temporal execution IDs to your workflow_id
CREATE TABLE workflow_executions (
    id                  SERIAL PRIMARY KEY,
    workflow_id         INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    temporal_run_id     TEXT NOT NULL,       -- Temporal's execution ID
    temporal_workflow_id TEXT NOT NULL,  -- Temporal's workflow ID

    -- Quick status lookup (optional, can query Temporal UI instead)
    status              VARCHAR(20),        -- running, completed, failed, cancelled
    final_output_summary TEXT,              -- Human-readable result

    started_at          TIMESTAMP DEFAULT NOW(),
    completed_at        TIMESTAMP
);

CREATE INDEX idx_workflow_executions_temporal ON workflow_executions(temporal_run_id);
```

### What Temporal Provides (No Tables Needed)

| What You Need | Temporal Provides |
|---------------|------------------|
| **Workflow runs history** | Temporal Web UI → Workflow Executions |
| **Activity (executor) runs** | Temporal Web UI → Workflow → Activities |
| **Tool call details** | Temporal Events History |
| **Retry history** | Temporal Shows all retry attempts |
| **Timing data** | Temporal tracks duration per activity |
| **Error messages** | Temporal shows stack traces |
| **Scheduling state** | Temporal shows timers, cron schedules |

**Result:** You need 1 table instead of 4. Temporal handles the rest.

---

## Temporal Workflow Implementation

### Workflow Definition

```python
from temporalio import workflow, activity
from datetime import timedelta, datetime

@workflow.defn
class CasseyWorkflow:
    """Cassey workflow that executes a chain of executors (activities)."""

    @workflow.run
    async def run(self, spec: WorkflowSpec) -> dict:
        """Execute the workflow executor by executor."""

        # Calculate delay if scheduled
        if spec.schedule_type == "scheduled" and spec.schedule_time:
            delay = (spec.schedule_time - datetime.now()).total_seconds()
            if delay > 0:
                await workflow.sleep(delay)

        # Shared context across executors
        context = {
            "workflow_id": spec.workflow_id,
            "user_id": spec.user_id,
            "executor_outputs": {}
        }

        results = []

        # Execute each executor as an activity
        for i, executor_spec in enumerate(spec.executors):
            try:
                # Execute the activity (with retry policy)
                output = await workflow.execute_activity(
                    run_executor,
                    args=[executor_spec, context["executor_outputs"]],
                    retry_policy=RetryPolicy(
                        max_attempts=executor_spec.max_retries,
                        initial_retry=timedelta(seconds=executor_spec.retry_backoff)
                    ),
                    start_to_close_timeout=timedelta(seconds=executor_spec.timeout_seconds)
                )

                # Store output for next executor
                context["executor_outputs"][executor_spec.executor_id] = output
                results.append({
                    "executor_id": executor_spec.executor_id,
                    "status": "success",
                    "output": output
                })

            except Exception as e:
                # Activity failed after retries
                results.append({
                    "executor_id": executor_spec.executor_id,
                    "status": "failed",
                    "error": str(e)
                })

                # Notify on failure if requested
                if spec.notify_on_failure:
                    await workflow.execute_activity(
                        send_notification,
                        args=[spec.user_id, f"Workflow failed: {spec.name}"]
                    )

                raise  # Stop workflow execution

        # All executors completed successfully
        final_output = context.get("last_executor_output")

        # Notify on complete if requested
        if spec.notify_on_complete:
            await workflow.execute_activity(
                send_notification,
                args=[spec.user_id, f"Workflow completed: {spec.name}"]
            )

        return {
            "workflow_id": spec.workflow_id,
            "status": "completed",
            "executor_results": results,
            "final_output": final_output
        }


# Recurring workflow (using Temporal Cron)
@workflow.defn
class CasseyRecurringWorkflow:
    """Recurring workflow that executes on a schedule."""

    @workflow.run
    async def run(self, spec: WorkflowSpec) -> None:
        """Execute workflow repeatedly on cron schedule."""

        # This workflow uses Temporal's cron feature
        # Cron scheduling is configured when starting the workflow

        # Execute the main workflow logic
        main_workflow = CasseyWorkflow()
        result = await main_workflow.run(spec)

        # Workflow will be re-scheduled by Temporal's cron


# Activity: Single Executor
@activity.defn
def run_executor(executor_spec: ExecutorSpec, previous_outputs: dict) -> dict:
    """Execute a single executor (agent with tools)."""

    # Build prompt with previous outputs
    prompt = executor_spec.system_prompt
    if previous_outputs:
        prompt = prompt.replace(
            "$previous_output",
            json.dumps(previous_outputs, indent=2)
        )

    # Get tools for this executor
    tools = get_tools_by_name(executor_spec.tools)

    # Create and invoke the agent
    agent = create_agent(
        model=executor_spec.model,
        tools=tools,
        prompt=prompt
    )

    result = await agent.ainvoke({
        "messages": [HumanMessage(content="Execute your task.")]
    })

    # Extract and validate structured output
    structured_output = extract_structured_output(
        result,
        executor_spec.output_schema
    )

    return structured_output


# Activity: Send notification
@activity.defn
def send_notification(user_id: str, message: str) -> bool:
    """Send notification to user via specified channel."""
    # Implementation: send via Telegram, email, etc.
    pass
```

### Starting Workflows from Cassey

```python
from temporalio.client import Client

# Connect to Temporal Server
client = await Client.connect("temporal.vm2.internal:7233")

async def create_workflow(spec: WorkflowSpec) -> str:
    """Create and start a Temporal workflow."""

    # Save workflow to PostgreSQL
    workflow_id = await save_workflow_to_db(spec)

    # Start Temporal workflow
    if spec.schedule_type == "immediate":
        # Run immediately
        handle = await client.start_workflow(
            CasseyWorkflow.run,
            args=[spec],
            id=f"workflow-{workflow_id}",
            task_queue="cassey-workflows"
        )

    elif spec.schedule_type == "scheduled":
        # Run at specific time
        handle = await client.start_workflow(
            CasseyWorkflow.run,
            args=[spec],
            id=f"workflow-{workflow_id}",
            start_delay=timedelta_until(spec.schedule_time),
            task_queue="cassey-workflows"
        )

    elif spec.schedule_type == "recurring":
        # Run on cron schedule
        handle = await client.start_workflow(
            CasseyRecurringWorkflow.run,
            args=[spec],
            id=f"workflow-{workflow_id}-cron",
            task_queue="cassey-workflows",
            cron_expression=spec.cron_expression
        )

    # Store Temporal workflow ID
    await update_workflow_temporal_id(workflow_id, handle.id)

    return workflow_id
```

---

## Temporal Cron Format

Temporal uses standard 5-field cron expressions:

```
Field:     Min  Hour  Day  Month  Weekday
Example:    0    9    *    *     MON-FRI

Examples:
"0 9 * * *"           → Daily at 9am
"0 9 * * MON-FRI"     → Weekdays at 9am
"0 */4 * * *"        → Every 4 hours
"0 0 * * MON"         → Weekly on Monday at midnight
"0 9 1 * *"          → First day of month at 9am
```

Temporal also supports intervals:
```python
# Instead of cron, use sleep and continue-as-new
while True:
    await workflow.execute_activity(do_daily_task)
    await workflow.sleep(timedelta(days=1))
```

---

## Loops in Prompt vs Code

With Temporal, you can choose where to handle iteration:

| Loop Type | In Prompt | In Code (Temporal) |
|-----------|-----------|-------------------|
| **Fixed count** | "Call tool 5 times" | Loop over activities |
| **For each** | "For each item in $previous_output" | `for item in items: await activity()` |
| **Until condition** | "Keep calling until status='complete'" | `while not done: await activity()` |

**Recommendation:** Use code-owned loops for iteration over arrays, prompt-owned for tool-level loops.

```python
# Code-owned loop (cleaner, more reliable)
if executor_spec.loop and executor_spec.loop.type == "for_each":
    items = jsonpath(previous_outputs, executor_spec.loop.input_path)
    results = []
    for item in items[:executor_spec.loop.max_items]:
        result = await workflow.execute_activity(
            process_item,
            args=[item, previous_outputs]
        )
        results.append(result)
    return {"results": results}
```

---

## Update: Recommendations (2026-01-16) with Temporal

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

## Mini-Spec: Workflow Tables (Simplified with Temporal)

### workflows (only required table)
```sql
CREATE TABLE workflows (
    id                  SERIAL PRIMARY KEY,
    workflow_id         UUID DEFAULT gen_random_uuid(),
    user_id             VARCHAR(255) NOT NULL,
    thread_id           VARCHAR(255) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,

    -- Workflow definition (JSON)
    executors           JSONB NOT NULL,

    -- Temporal references
    temporal_workflow_id TEXT,
    task_queue          TEXT DEFAULT 'cassey-workflows',

    -- Scheduling (for queryability)
    schedule_type       VARCHAR(20) NOT NULL,
    schedule_time       TIMESTAMP,
    cron_expression     VARCHAR(100),

    -- Tool manifest snapshot (for validation)
    tool_manifest_hash  TEXT,
    tool_manifest_json  JSONB,

    -- Status
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'archived'))
);
```

### Optional Tables (for convenience, Temporal has the source of truth)

```sql
-- Optional: Quick lookup of recent executions (mirrors Temporal state)
CREATE TABLE workflow_executions (
    id                  SERIAL PRIMARY KEY,
    workflow_id         INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    temporal_run_id     TEXT NOT NULL,

    status              VARCHAR(20),
    final_output_summary TEXT,

    started_at          TIMESTAMP DEFAULT NOW(),
    completed_at        TIMESTAMP
);
```

**Note:** With Temporal, you get full observability via the Temporal Web UI:
- Workflow runs history
- Activity (executor) runs
- Tool call details
- Retry history
- Timing data
- Error messages

The PG tables are mainly for your app's quick queries. Temporal is the source of truth.

---

## Is this bloated?
**No.** With Temporal handling the heavy lifting:
- **Phase 1**: Just `workflows` table. Temporal tracks everything else.
- **Phase 2** (optional): `workflow_executions` for quick status lookups without querying Temporal API.
- Tool manifest hash stored by default; full manifest only when `DEBUG_WORKFLOWS=true`.

## What Temporal Tracks (No Tables Needed)

| What You Need | Temporal Provides |
|---------------|------------------|
| **Workflow runs history** | Temporal Web UI → Workflow Executions |
| **Activity (executor) runs** | Temporal Web UI → Workflow → Activities |
| **Tool call details** | Temporal Events History |
| **Retry history** | Temporal Shows all retry attempts |
| **Timing data** | Temporal tracks duration per activity |
| **Error messages** | Temporal shows stack traces |
| **Scheduling state** | Temporal shows timers, cron schedules |

---

## Tools for Cassey (Temporal-Based)

```python
from temporalio.client import Client

# Temporal client connection (singleton)
_temporal_client: Client | None = None

async def get_temporal_client() -> Client:
    """Get or create Temporal client connection."""
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = await Client.connect("temporal.vm2.internal:7233")
    return _temporal_client


@tool
async def create_workflow(
    name: str,
    description: str,
    executors: list[dict],
    schedule_type: str = "immediate",
    schedule_time: str = None,
    cron_expression: str = None,
    notify_on_complete: bool = False,
    notify_on_failure: bool = True,
    notification_channel: str = "telegram",
    user_id: str = None,
    thread_id: str = None
) -> str:
    """
    Create a workflow from a chain of executors (backed by Temporal).

    Each executor is a create_agent() with:
    - executor_id: Unique ID for this executor
    - name: Display name
    - model: Which LLM to use
    - tools: List of tool names to include
    - system_prompt: What this executor does (use $previous_output for injection)
    - output_schema: Expected structured output (JSON schema)
    - timeout_seconds: Activity timeout (default 300)
    - max_retries: Retry count on failure (default 3)
    - loop: Optional loop control (for_each, repeat_until, repeat_count)

    The workflow executes executors sequentially, passing each
    executor's output to the next executor's prompt via $previous_output.

    Args:
        name: Workflow name
        description: What this workflow does
        executors: List of executor specifications
        schedule_type: 'immediate', 'scheduled', or 'recurring'
        schedule_time: For 'scheduled', when to run (ISO datetime or natural language)
        cron_expression: For 'recurring', cron like "0 9 * * MON-FRI"
        notify_on_complete: Send notification when workflow completes
        notify_on_failure: Send notification when workflow fails
        notification_channel: 'telegram', 'email', 'web', or 'none'
        user_id: Your user ID
        thread_id: Current thread ID

    Returns:
        workflow_id for tracking/cancellation

    Example:
        executors = [
            {
                "executor_id": "fetch",
                "name": "Fetcher",
                "model": "gpt-4o-mini",
                "tools": ["search_web"],
                "system_prompt": "Search for prices. Return structured output.",
                "output_schema": {"prices": [{"product": "str", "price": "float"}]},
                "timeout_seconds": 300,
                "max_retries": 3
            },
            {
                "executor_id": "summarize",
                "name": "Summarizer",
                "model": "gpt-4o",
                "tools": ["execute_python"],
                "system_prompt": "Previous: $previous_output. Summarize.",
                "output_schema": {"summary": "str", "avg_price": "float"}
            }
        ]
        await create_workflow("Price Monitor", "Check prices", executors, "recurring", cron_expression="0 9 * * *")
    """
    from cassey.workflows.storage import save_workflow_to_db
    from cassey.workflows.temporal_workflows import CasseyWorkflow, CasseyRecurringWorkflow

    client = await get_temporal_client()

    # Build WorkflowSpec
    spec = WorkflowSpec(
        workflow_id=str(uuid.uuid4()),
        name=name,
        description=description,
        executors=[ExecutorSpec(**e) for e in executors],
        schedule_type=schedule_type,
        schedule_time=parse_schedule_time(schedule_time) if schedule_time else None,
        cron_expression=cron_expression,
        notify_on_complete=notify_on_complete,
        notify_on_failure=notify_on_failure,
        notification_channel=notification_channel
    )

    # Save to PostgreSQL
    db_id = await save_workflow_to_db(spec, user_id, thread_id)

    # Start Temporal workflow
    if spec.schedule_type == "immediate":
        handle = await client.start_workflow(
            CasseyWorkflow.run,
            args=[spec],
            id=f"workflow-{spec.workflow_id}",
            task_queue="cassey-workflows"
        )
    elif spec.schedule_type == "scheduled":
        # Calculate delay for scheduled start
        delay_seconds = (spec.schedule_time - datetime.now()).total_seconds()
        handle = await client.start_workflow(
            CasseyWorkflow.run,
            args=[spec],
            id=f"workflow-{spec.workflow_id}",
            task_queue="cassey-workflows",
            start_delay=timedelta(seconds=delay_seconds)
        )
    elif spec.schedule_type == "recurring":
        handle = await client.start_workflow(
            CasseyRecurringWorkflow.run,
            args=[spec],
            id=f"workflow-{spec.workflow_id}-cron",
            task_queue="cassey-workflows",
            cron_expression=spec.cron_expression
        )

    # Update with Temporal workflow ID
    await update_workflow_temporal_id(db_id, handle.id)

    return spec.workflow_id


@tool
async def list_workflows(
    user_id: str,
    status: str = None
) -> list[dict]:
    """List your workflows.

    Args:
        user_id: Your user ID
        status: Filter by 'active', 'paused', or 'archived'

    Returns:
        List of workflows with scheduling info
    """
    from cassey.workflows.storage import get_workflows_by_user
    return await get_workflows_by_user(user_id, status)


@tool
async def get_workflow_execution(
    workflow_id: str,
    run_id: str = None
) -> dict:
    """
    Get detailed execution history from Temporal.

    Shows each executor, tool calls, outputs, retries, and any errors.
    Uses Temporal Web UI data via Temporal API.

    Args:
        workflow_id: Workflow ID from create_workflow()
        run_id: Specific run ID (optional, defaults to latest)

    Returns:
        Execution details with executor runs, tool calls, timing
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(f"workflow-{workflow_id}")

    if run_id:
        handle = handle.get_execution_run(run_id)

    # Get workflow history from Temporal
    history = await handle.fetch_history()
    return parse_temporal_history(history)


@tool
async def list_workflow_executions(
    workflow_id: str,
    status: str = None,
    limit: int = 10
) -> list[dict]:
    """
    List executions of a workflow.

    Args:
        workflow_id: Workflow ID
        status: Filter by 'running', 'completed', 'failed', 'cancelled'
        limit: Max results

    Returns:
        List of executions with status and timestamps
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(f"workflow-{workflow_id}")

    executions = await handle.query(lambda: f"list_executions({status}, {limit})")
    return executions


@tool
async def cancel_workflow(
    workflow_id: str,
    run_id: str = None
) -> str:
    """
    Cancel a running workflow or its scheduled runs.

    Args:
        workflow_id: Workflow ID
        run_id: Specific run to cancel (optional)

    Returns:
        Cancellation status
    """
    client = await get_temporal_client()
    handle = client.get_workflow_handle(f"workflow-{workflow_id}")

    if run_id:
        handle = handle.get_execution_run(run_id)

    await handle.cancel()
    return f"Cancelled workflow {workflow_id}"


@tool
async def pause_workflow(
    workflow_id: str
) -> str:
    """Pause a workflow (stops future executions until resumed)."""
    from cassey.workflows.storage import set_workflow_status
    await set_workflow_status(workflow_id, "paused")
    return f"Paused workflow {workflow_id}"


@tool
async def resume_workflow(
    workflow_id: str
) -> str:
    """Resume a paused workflow."""
    from cassey.workflows.storage import set_workflow_status
    await set_workflow_status(workflow_id, "active")
    return f"Resumed workflow {workflow_id}"
```

---

## Execution Engine (Temporal Worker)

**Note:** With Temporal, the execution engine is handled by the Temporal Worker process.
The worker polls Temporal Server for workflow/activity tasks and executes them.

### Worker Setup

```python
from temporalio.worker import Worker
from temporalio.client import Client
from cassey.workflows.temporal_workflows import CasseyWorkflow, CasseyRecurringWorkflow
from cassey.workflows.temporal_activities import (
    run_executor,
    send_notification
)

async def run_worker():
    """Run the Temporal worker for Cassey workflows."""

    # Connect to Temporal Server
    client = await Client.connect("temporal.vm2.internal:7233")

    # Create and run worker
    worker = Worker(
        client,
        task_queue="cassey-workflows",
        workflows=[CasseyWorkflow, CasseyRecurringWorkflow],
        activities=[run_executor, send_notification],
    )

    print("Worker started, listening for workflow/activity tasks...")
    await worker.run()


# Run worker (separate process or within Cassey app)
if __name__ == "__main__":
    asyncio.run(run_worker())
```

### Activity: Run Executor

```python
from temporalio import activity
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

@activity.defn
def run_executor(executor_spec: ExecutorSpec, previous_outputs: dict) -> dict:
    """Execute a single executor (agent with tools)."""

    # Build prompt with previous outputs
    prompt = executor_spec.system_prompt
    if previous_outputs:
        prompt = prompt.replace(
            "$previous_output",
            json.dumps(previous_outputs, indent=2)
        )

    # Get tools for this executor
    tools = get_tools_by_name(executor_spec.tools)

    # Create and invoke the agent
    agent = create_agent(
        model=executor_spec.model,
        tools=tools,
        prompt=prompt
    )

    result = await agent.ainvoke({
        "messages": [HumanMessage(content="Execute your task.")]
    })

    # Extract and validate structured output
    structured_output = extract_structured_output(
        result,
        executor_spec.output_schema
    )

    return structured_output
```

### Activity: Send Notification

```python
@activity.defn
def send_notification(user_id: str, message: str, channel: str = "telegram") -> bool:
    """Send notification to user via specified channel."""

    if channel == "telegram":
        return send_telegram_message(user_id, message)
    elif channel == "email":
        return send_email(user_id, message)
    elif channel == "web":
        return send_web_notification(user_id, message)
    else:
        return True  # "none" channel
```

---

## Example Trace Output (Temporal)

Temporal provides traces via the Web UI at `http://temporal.vm2.internal:8080`

### Workflow Execution View

```
Workflow: workflow-daily_price_monitor
Run ID: 123e4567-e89b-12d3-a456-426614174000
Status: Failed
Started: 2026-01-17 09:00:00 UTC
Completed: 2026-01-17 09:02:30 UTC

┌─────────────────────────────────────────────────────────────────────┐
│ Event History                                                       │
├─────────────────────────────────────────────────────────────────────┤
│ 1. WorkflowExecutionStarted                                        │
│ 2. TimerStarted (delay until 09:00:00)                             │
│ 3. TimerFired                                                      │
│ 4. ActivityTaskScheduled: run_executor(fetch_prices)               │
│ 5. ActivityTaskStarted: run_executor(fetch_prices)                 │
│ 6. ActivityTaskCompleted: run_executor(fetch_prices)               │
│    - Result: {"prices": [...]}                                     │
│    - Duration: 45s                                                 │
│ 7. ActivityTaskScheduled: run_executor(compare_prices)             │
│ 8. ActivityTaskStarted: run_executor(compare_prices)               │
│ 9. ActivityTaskFailed: run_executor(compare_prices)                │
│    - Error: Database query timeout after 120s                      │
│    - Retry 1/3 scheduled (backoff: 60s)                            │
│ 10. TimerStarted (retry backoff)                                   │
│ 11. TimerFired                                                     │
│ 12. ActivityTaskScheduled: run_executor(compare_prices)            │
│ 13. ActivityTaskStarted: run_executor(compare_prices)              │
│ 14. ActivityTaskFailed: run_executor(compare_prices)               │
│    - Error: Database query timeout after 120s                      │
│    - Retry 2/3 scheduled (backoff: 60s)                            │
│ ...                                                                 │
│ 20. WorkflowExecutionFailed                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Activity Details (clickable in UI)

```
Activity: run_executor
Executor: fetch_prices
Status: Completed
Duration: 45s
Retry Attempts: 0

Input:
{
  "executor_spec": {
    "executor_id": "fetch_prices",
    "model": "gpt-4o-mini",
    "tools": ["search_web"],
    "system_prompt": "Search for prices...",
    "output_schema": {"prices": [...]}
  },
  "previous_outputs": {}
}

Result:
{
  "prices": [
    {"product": "iPhone 15", "competitor": "Amazon", "price": 999, "url": "..."},
    {"product": "iPhone 15", "competitor": "Walmart", "price": 989, "url": "..."}
  ]
}
```

### JSON Export (via Temporal API)

```json
{
  "workflow_id": "daily_price_monitor",
  "run_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "failed",
  "started_at": "2026-01-17T09:00:00Z",
  "completed_at": "2026-01-17T09:02:30Z",

  "activities": [
    {
      "activity_id": "run_executor:fetch_prices",
      "status": "completed",
      "duration_ms": 45000,
      "retry_count": 0,
      "result": {
        "prices": [
          {"product": "iPhone 15", "competitor": "Amazon", "price": 999}
        ]
      }
    },
    {
      "activity_id": "run_executor:compare_prices",
      "status": "failed",
      "duration_ms": 120000,
      "retry_count": 3,
      "error_message": "Database query timeout after 120s",
      "last_failure": {
        "error": "Database query timeout after 120s",
        "stack_trace": "..."
      }
    }
  ]
}
```

---

## Implementation Checklist

### Temporal Server Setup
- [ ] Deploy Temporal Server on VM 2 (self-hosted)
- [ ] Configure PostgreSQL for Temporal's state store
- [ ] Set up Temporal Web UI (port 8080)
- [ ] Configure task queues (cassey-workflows, cassey-reminders)

### Cassey Application
- [ ] Create workflows table in PostgreSQL
- [ ] Implement `WorkflowSpec`, `ExecutorSpec`, `LoopSpec` dataclasses
- [ ] Create `cassey/workflows/temporal_workflows.py` with workflow definitions
- [ ] Create `cassey/workflows/temporal_activities.py` with activities
- [ ] Implement Temporal worker integration in Cassey app
- [ ] Create workflow tools (create_workflow, list_workflows, cancel_workflow, etc.)
- [ ] Implement `save_workflow_to_db`, `get_workflows_by_user` storage functions
- [ ] Add tool manifest snapshotting (hash + JSON)

### Testing
- [ ] Test immediate workflow execution
- [ ] Test scheduled workflows (delayed start)
- [ ] Test recurring workflows (cron)
- [ ] Test activity retry behavior
- [ ] Test notification on complete/failure
- [ ] Test workflow cancellation

### Documentation
- [ ] Document Temporal architecture (VM 1 vs VM 2)
- [ ] Document workflow creation syntax
- [ ] Document executor spec format
- [ ] Document Temporal Web UI usage

---

## Summary

| Component | Design (Temporal-Based) |
|-----------|------------------------|
| **Executor** | `create_agent()` as Temporal activity |
| **Prompt** | Includes previous executor's output via `$previous_output` |
| **Loops** | Code-owned via `LoopSpec` (for_each, repeat_until, repeat_count) |
| **Flow** | Sequential chain, activities within Temporal workflow |
| **Tracking** | Temporal Web UI provides full observability |
| **Error handling** | Temporal RetryPolicy with configurable backoff |
| **Scheduling** | Temporal durable timers + cron for recurring workflows |
| **Infrastructure** | VM 1: Cassey + Worker → VM 2: Temporal Server |

**Key benefit:** Temporal provides durable execution, automatic retries, built-in scheduling, and full observability out of the box. You focus on defining executor chains; Temporal handles the rest.

---

## Implementation Recommendations (2025-01-18)

### Feasibility: **Highly Feasible**

This design leverages proven patterns:
- **Temporal integration**: Well-established patterns, mature Python SDK
- **Executor chain pattern**: Simple sequential flow, maps cleanly to activities
- **Prompt injection**: `$previous_output` substitution is straightforward
- **Schema design**: Simplified by leveraging Temporal's built-in tracking

### Phased Implementation Approach

#### Phase 1: Core (MVP) - No Temporal Required
```
User creates workflow → PostgreSQL stores spec → Direct execution → Results delivered
```

**Goal**: Validate patterns before adding Temporal complexity

- Single executor, immediate execution
- Skip Temporal initially - just run `create_agent()` directly
- Validate structured output pattern
- Add prompt injection (`$previous_output`)
- Basic workflow CRUD tools

**Deliverables**:
- `workflows` table in PostgreSQL
- `WorkflowSpec`, `ExecutorSpec`, `LoopSpec` dataclasses
- `create_workflow()`, `list_workflows()`, `cancel_workflow()` tools
- Simple execution runner (no Temporal yet)

#### Phase 2: Add Temporal for Durability
```python
# Deploy Temporal (can be same VM initially)
TEMPORAL_HOST=temporal.gongchatea.com.au
TEMPORAL_PORT=7233
```

- Deploy Temporal Server (or use existing instance)
- Convert executor to Temporal activity
- Add `RetryPolicy` with exponential backoff
- Implement Temporal worker

**Deliverables**:
- Temporal worker process
- `CasseyWorkflow` class with `run()` method
- `run_executor` activity
- Connection handling + reconnection logic

#### Phase 3: Scheduling
- Scheduled workflows (one-off at specific time via `workflow.sleep()`)
- Recurring workflows (cron expression)
- Workflow pause/resume

**Deliverables**:
- `CasseyRecurringWorkflow` class
- Cron scheduling integration
- Pause/resume state management

#### Phase 4: Observability & Advanced
- Temporal Web UI integration
- Code-owned loops (`for_each`, `repeat_until`)
- Large output handling (file/VS refs)
- Workflow resume from failed executor

### Real-World Examples

```python
# 1. Daily price monitor
executors = [fetch_prices, compare_prices, send_alerts]
schedule = "0 9 * * MON-FRI"  # Weekdays 9am

# 2. Weekly report generator
executors = [query_db, analyze_trends, write_report, email_summary]
schedule = "0 9 * * MON"  # Mondays 9am

# 3. Social media monitor
executors = [search_mentions, sentiment_analysis, flag_high_risk]
schedule = "0 */4 * * *"  # Every 4 hours

# 4. Invoice processor
executors = [read_email, extract_invoice_data, record_to_db, notify_finance]
schedule = "0 10 * * MON-FRI"  # Weekdays 10am
```

### Potential Issues & Mitigations

| Issue | Mitigation |
|-------|------------|
| **Structured output reliability** | LLMs may return malformed JSON. Add validation + retry with correction prompt (2-3 attempts max) |
| **Context window limits** | Long executor chains accumulate outputs. Use `output_ref` pattern for large data (store in file/VS, pass reference) |
| **Tool drift** | Tools change over time. Implement `tool_manifest_hash` - validate at runtime, warn on mismatch |
| **Temporal ops overhead** | 2-VM setup adds complexity. Use single-VM for development, split for production |
| **Loop enforcement** | Code-owned loops (`LoopSpec`) are more reliable than prompt-owned. Start with prompt-owned, add code-owned later |

### Missing Pieces to Consider

| Piece | Why It Matters | Priority |
|-------|----------------|----------|
| **Workflow templates** | Users shouldn't write raw JSON | High |
| **Natural language → WorkflowSpec** | "Monitor prices daily" → generate executor chain | Medium |
| **Workflow versioning** | What happens when I update a workflow? | Medium |
| **Resource limits** | Max executors? Max run time? | Medium |
| **Multi-tenant isolation** | Workspace-scoped vs user-scoped | Low |
| **Testing workflow** | How to test before scheduling? | High |

### Environment Configuration

Add to `.env`:
```bash
# Temporal Configuration
TEMPORAL_HOST=temporal.gongchatea.com.au
TEMPORAL_PORT=7233
TEMPORAL_NAMESPACE=default  # Usually 'default' for self-hosted
TEMPORAL_TASK_QUEUE=cassey-workflows
TEMPORAL_CLIENT_TIMEOUT=30  # Seconds
TEMPORAL_CONNECTION_RETRY=3
```

---

## Temporal API Implementation (2025-01-18)

### gRPC vs REST: What's Required?

| Operation | gRPC | REST | Required For Cassey |
|-----------|------|------|---------------------|
| **Start workflow** | ✅ | ✅ | gRPC recommended |
| **Worker poll for tasks** | ✅ | ❌ | **gRPC required** |
| **Activity execution** | ✅ | ❌ | **gRPC required** |
| **Query workflow state** | ✅ | ✅ | REST sufficient |
| **List workflows** | ✅ | ✅ | REST sufficient |
| **Get workflow history** | ✅ | ⚠️ | gRPC recommended |
| **Cancel workflow** | ✅ | ✅ | REST sufficient |
| **Signal workflow** | ✅ | ❌ | gRPC required |

**Verdict**: gRPC is **required for workers**. REST can handle basic management operations but not the core workflow execution.

### Why gRPC?

| Aspect | gRPC | REST |
|--------|------|------|
| **Performance** | Binary Protocol Buffers, faster | JSON, slower |
| **Bidirectional streaming** | ✅ Native support | ❌ Not supported |
| **Type safety** | Strong typing with .proto schemas | Loose JSON schemas |
| **Code generation** | Auto-generated client SDKs | Manual request handling |
| **Worker long-polling** | ✅ Efficient (keep connection open) | ❌ Requires repeated polling |
| **Workflow heartbeating** | ✅ Built-in | ❌ Requires custom implementation |

**For Cassey**: The worker needs to:
1. Long-poll for workflow/activity tasks (requires persistent connection)
2. Send heartbeats during long-running activities
3. Receive signals mid-execution

These require gRPC's bidirectional streaming. REST would need constant polling which is inefficient.

### Implementation Approach

#### Phase 1: Configuration (✅ Complete)

**`src/cassey/config/settings.py`**:
```python
# Temporal Configuration
TEMPORAL_HOST: str | None = None
TEMPORAL_PORT: int = 7233
TEMPORAL_NAMESPACE: str = "default"
TEMPORAL_TASK_QUEUE: str = "cassey-workflows"
TEMPORAL_CLIENT_TIMEOUT: int = 30
TEMPORAL_CONNECTION_RETRY: int = 3

@property
def temporal_enabled(self) -> bool:
    """Check if Temporal is configured and enabled."""
    return bool(self.TEMPORAL_HOST)

@property
def temporal_target(self) -> str:
    """Get the Temporal server target (host:port)."""
    if not self.TEMPORAL_HOST:
        raise ValueError("TEMPORAL_HOST not configured")
    return f"{self.TEMPORAL_HOST}:{self.TEMPORAL_PORT}"
```

#### Phase 2: Client Factory (Next)

**`src/cassey/workflows/temporal_client.py`** (to be created):
```python
"""Temporal client factory and connection management."""

from temporalio.client import Client, ConnectError
from cassey.config import settings

_temporal_client: Client | None = None

async def get_temporal_client() -> Client:
    """Get or create Temporal client connection (singleton)."""
    global _temporal_client

    if _temporal_client is not None:
        return _temporal_client

    if not settings.temporal_enabled:
        raise RuntimeError(
            "Temporal is not configured. Set TEMPORAL_HOST in environment."
        )

    try:
        _temporal_client = await Client.connect(
            settings.temporal_target,
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        return _temporal_client
    except ConnectError as e:
        raise RuntimeError(
            f"Failed to connect to Temporal at {settings.temporal_target}: {e}"
        )


async def close_temporal_client():
    """Close the Temporal client connection."""
    global _temporal_client
    if _temporal_client is not None:
        # Note: temporalio Client doesn't have explicit close in older versions
        # Just clear the reference
        _temporal_client = None
```

#### Phase 3: Health Check (Next)

**`src/cassey/workflows/health.py`** (to be created):
```python
"""Temporal health check utilities."""

import asyncio
from cassey.config import settings


async def check_temporal_connection() -> dict:
    """Check TCP connection to Temporal server (no SDK required)."""
    if not settings.TEMPORAL_HOST:
        return {
            "status": "not_configured",
            "host": None,
            "reachable": False
        }

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.TEMPORAL_HOST, settings.TEMPORAL_PORT),
            timeout=5.0
        )
        writer.close()
        await writer.wait_closed()
        return {
            "status": "ok",
            "host": settings.TEMPORAL_HOST,
            "port": settings.TEMPORAL_PORT,
            "reachable": True
        }
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
        return {
            "status": "error",
            "host": settings.TEMPORAL_HOST,
            "port": settings.TEMPORAL_PORT,
            "reachable": False,
            "error": str(e)
        }


async def check_temporal_grpc() -> dict:
    """Check gRPC connection to Temporal (requires temporalio)."""
    try:
        from temporalio.client import Client
    except ImportError:
        return {
            "status": "sdk_missing",
            "message": "temporalio package not installed"
        }

    if not settings.temporal_enabled:
        return {
            "status": "not_configured",
            "message": "TEMPORAL_HOST not set"
        }

    try:
        client = await Client.connect(
            settings.temporal_target,
            namespace=settings.TEMPORAL_NAMESPACE,
        )

        # Basic health check - get service capabilities
        # This doesn't require any workflows to exist
        workflow_service = client.workflow_service

        return {
            "status": "ok",
            "host": settings.temporal_target,
            "namespace": settings.TEMPORAL_NAMESPACE,
            "connected": True
        }
    except Exception as e:
        return {
            "status": "error",
            "host": settings.temporal_target,
            "namespace": settings.TEMPORAL_NAMESPACE,
            "connected": False,
            "error": str(e)
        }
```

#### Phase 4: Tests (✅ Complete)

**`tests/test_temporal_api.py`** includes:

1. **Configuration tests**: Verify settings loading, properties
2. **Connection test**: TCP connectivity (no SDK required)
3. **gRPC tests**: With `temporalio` package (skipped if not installed)
4. **Model validation tests**: `WorkflowSpec`, `ExecutorSpec`
5. **Helper tests**: Cron parsing, prompt injection, retry policy

**Run tests**:
```bash
# Basic tests (no temporalio required)
TEMPORAL_HOST=temporal.gongchatea.com.au uv run pytest tests/test_temporal_api.py -v

# With temporalio installed
uv add temporalio
TEMPORAL_HOST=temporal.gongchatea.com.au uv run pytest tests/test_temporal_api.py::TestTemporalConnection -v
```

### Connection Test Results (2025-01-18)

```
✅ TCP connection to temporal.gongchatea.com.au:7233 - SUCCESS
⏭️ gRPC connection - SKIPPED (temporalio not installed)
```

### Dependencies

```bash
# Required for workers (Core)
uv add temporalio

# Optional: For development
uv add temporalio[dev]
```

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cassey Application                         │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Temporal Client (singleton)                                  │ │
│  │                                                               │ │
│  │  - Connects to TEMPORAL_HOST:7233 via gRPC                  │ │
│  │  - Namespace: TEMPORAL_NAMESPACE                             │ │
│  │  - Task Queue: TEMPORAL_TASK_QUEUE                           │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                            ↕ gRPC (persistent)                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ gRPC over TCP
                            │
┌─────────────────────────────────────────────────────────────────┐
│                      Temporal Server                              │
│  temporal.gongchatea.com.au:7233                                │
│                                                                         │
│  - Receives workflow start requests                               │
│  - Dispatches tasks to workers                                    │
│  - Stores workflow state                                          │
│  - Provides Web UI at port 8080                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Next Steps

1. ✅ **Install temporalio**: `uv add temporalio` (completed: v1.21.1)
2. ✅ **Create client factory**: `src/cassey/workflows/temporal_client.py` (completed)
3. ✅ **Create health check**: `src/cassey/workflows/health.py` (completed)
4. ⏳ **Implement workflow definitions**: `CasseyWorkflow`, `CasseyRecurringWorkflow`
5. ⏳ **Implement worker**: Process that polls for and executes activities

---

## gRPC Implementation Status (2025-01-18)

### Completed Components

#### 1. Dependency Installation
```bash
uv add temporalio  # Installed v1.21.1
```

#### 2. Client Factory Module
**File**: `src/cassey/workflows/temporal_client.py`

| Function | Description |
|----------|-------------|
| `get_temporal_client()` | Singleton client connection with async lock |
| `close_temporal_client()` | Cleanup connection |
| `reset_temporal_client()` | For testing only |
| `run_worker()` | Run Temporal worker for Cassey workflows |
| `create_workflow()` | Start a Temporal workflow execution |
| `describe_workflow()` | Get workflow execution description |
| `cancel_workflow()` | Cancel a running workflow |
| `query_workflow()` | Query a workflow with a query method |

#### 3. Health Check Module
**File**: `src/cassey/workflows/health.py`

| Function | Description |
|----------|-------------|
| `check_tcp_connection()` | TCP health check (no SDK required) |
| `check_grpc_connection()` | Full gRPC health check with SDK |
| `check_temporal_health()` | Combined health report |
| `format_health_result()` | Format for display/logging |

#### 4. Package Structure
```
src/cassey/workflows/
├── __init__.py       # Package exports
├── temporal_client.py # Client factory + worker functions
└── health.py         # Health check utilities
```

### Test Results

**Environment**: `TEMPORAL_HOST=temporal.gongchatea.com.au`

```
============================= test session starts ==============================
collected 17 items

tests/test_temporal_api.py::TestTemporalSettings::test_temporal_settings_defaults PASSED
tests/test_temporal_api.py::TestTemporalSettings::test_temporal_enabled_property PASSED
tests/test_temporal_api.py::TestTemporalSettings::test_temporal_target_property PASSED
tests/test_temporal_api.py::TestTemporalConnection::test_connection PASSED
tests/test_temporal_api.py::TestTemporalConnection::test_grpc_connection_with_temporalio PASSED
tests/test_temporal_api.py::TestTemporalConnection::test_list_namespaces PASSED
tests/test_temporal_api.py::TestTemporalConnection::test_describe_namespace SKIPPED
tests/test_temporal_api.py::TestTemporalMocked::test_temporal_properties_with_host PASSED
tests/test_temporal_api.py::TestTemporalMocked::test_get_temporal_client_factory PASSED
tests/test_temporal_api.py::TestTemporalMocked::test_workflow_spec_model PASSED
tests/test_temporal_api.py::TestTemporalMocked::test_workflow_spec_validation PASSED
tests/test_temporal_api.py::TestTemporalWorkflowTools::test_create_workflow_tool_signature PASSED
tests/test_temporal_api.py::TestTemporalWorkflowTools::test_list_workflows_tool_signature PASSED
tests/test_temporal_api.py::TestTemporalHelpers::test_build_temporal_target PASSED
tests/test_temporal_api.py::TestTemporalHelpers::test_parse_cron_expression PASSED
tests/test_temporal_api.py::TestTemporalHelpers::test_executor_output_injection PASSED
tests/test_temporal_api.py::TestTemporalHelpers::test_retry_policy_calculation PASSED

=================== 16 passed, 1 skipped in 0.49s ===================
```

### Health Check Output

```
Temporal Health: HEALTHY
  Message: Temporal is healthy at temporal.gongchatea.com.au:7233
  TCP: healthy (11.35ms) - TCP connection successful
  gRPC: healthy (134.02ms) - gRPC connection successful (namespace: default)
```

### Implementation Notes

1. **ConnectError Fix**: The `temporalio` SDK doesn't export `ConnectError`. Connection errors are raised as `RuntimeError`. Both `temporal_client.py` and `health.py` were updated to catch `RuntimeError`.

2. **Singleton Pattern**: The client uses an async lock to ensure thread-safe singleton creation across async tasks.

3. **Worker Support**: The `run_worker()` function is ready to run workflows and activities once they're defined.

### Remaining Work

| Task | Status | Description |
|------|--------|-------------|
| `CasseyWorkflow` class | ⏳ Pending | Workflow definition with executor chain |
| `CasseyRecurringWorkflow` class | ⏳ Pending | Cron-based recurring workflow |
| `run_executor` activity | ⏳ Pending | Activity that calls `create_agent()` |
| `send_notification` activity | ⏳ Pending | Activity for notifications |
| `WorkflowSpec` models | ⏳ Pending | Pydantic models for workflow/executor specs |
| Database schema | ⏳ Pending | `workflows` table in PostgreSQL |
| Tool integration | ⏳ Pending | `create_workflow` tool for agents |

---

## Observability Design (2025-01-18)

### Goal

Track everything that happens in a workflow execution:
1. **Flow Creation**: What workflow was created based on user input
2. **Agent Configuration**: Input, output, tools, prompt for each executor
3. **Loop Execution**: Iteration details and exit conditions
4. **Additional**: Token usage, timing, tool calls, errors

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Observability Layer                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. workflow_creation_log   (DB table)                           │
│     - Original user request                                      │
│     - Generated WorkflowSpec (full JSON)                         │
│     - Created by, timestamp                                      │
│                                                                   │
│  2. workflow_execution_log  (DB table)                           │
│     - Temporal run_id, workflow_id                               │
│     - Each executor: config + input + output + duration          │
│     - Loop iterations                                             │
│     - Tool calls                                                  │
│                                                                   │
│  3. workflow_trace.json    (File per execution)                  │
│     - Complete execution trace                                   │
│     - Easy to load and analyze                                   │
│                                                                   │
│  4. Temporal Event History  (Built-in)                           │
│     - Retries, errors, timing                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema for Observability

```sql
-- 1. Workflow Creation Log - Track how workflows are created
CREATE TABLE workflow_creation_log (
    id SERIAL PRIMARY KEY,
    workflow_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    group_id VARCHAR(255) NOT NULL,

    -- Input
    user_request TEXT,                    -- Original user input
    generated_spec JSONB NOT NULL,        -- Full WorkflowSpec

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    -- Optional: If AI generated the workflow
    generated_by VARCHAR(100),             -- 'user' | 'agent'
    generation_model VARCHAR(100),          -- Which LLM created it
    generation_prompt TEXT                  -- Prompt used to generate
);

-- 2. Workflow Execution Log - Summary of each run
CREATE TABLE workflow_execution_log (
    id SERIAL PRIMARY KEY,
    workflow_id UUID NOT NULL,
    temporal_run_id TEXT NOT NULL,

    -- Execution metadata
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20),                     -- running, completed, failed, cancelled

    -- Summary
    total_duration_ms INT,
    total_token_usage INT,
    executor_count INT,
    loop_iterations JSONB,                  -- {executor_id: iteration_count}

    -- Full trace (compressed JSON)
    execution_trace JSONB                   -- Complete detailed trace
);

-- 3. Executor Execution Detail - Per-executor tracking
CREATE TABLE workflow_executor_log (
    id SERIAL PRIMARY KEY,
    execution_log_id INT REFERENCES workflow_execution_log(id) ON DELETE CASCADE,
    executor_id VARCHAR(255) NOT NULL,
    executor_index INT NOT NULL,            -- Position in chain

    -- Configuration (what was used)
    model VARCHAR(100),
    tools JSONB,                           -- List of tool names used
    system_prompt TEXT,                     -- The prompt (with injected values)
    expected_output_schema JSONB,

    -- Input
    input_data JSONB,                       -- What went in (previous outputs)

    -- Output
    output_data JSONB,                      -- What came out
    output_summary TEXT,                    -- Human-readable summary

    -- Execution
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    token_usage JSONB,                      -- {input: int, output: int}
    retry_count INT DEFAULT 0,

    -- Loop details
    loop_type VARCHAR(50),                  -- null | for_each | repeat_until | repeat_count
    loop_iterations JSONB,                  -- Array of iteration results

    -- Status
    status VARCHAR(20),                     -- completed | failed | cancelled
    error_message TEXT,

    -- Tool calls made
    tool_calls JSONB                        -- [{tool, input, output, duration_ms}]
);

CREATE INDEX idx_workflow_creation_workflow ON workflow_creation_log(workflow_id);
CREATE INDEX idx_workflow_execution_run ON workflow_execution_log(temporal_run_id);
CREATE INDEX idx_workflow_executor_execution ON workflow_executor_log(execution_log_id);
```

### Example Trace Output

```json
// workflow_trace.json
{
  "trace_id": "wf_20250118_123456",
  "workflow_id": "daily-price-monitor",
  "temporal_run_id": "abc123-def456",
  "started_at": "2025-01-18T09:00:00Z",
  "completed_at": "2025-01-18T09:03:45Z",
  "status": "completed",

  "creation": {
    "user_request": "Monitor competitor prices daily at 9am and alert me if any change >10%",
    "created_by": "user:telegram:123456",
    "created_at": "2025-01-17T14:30:00Z"
  },

  "executors": [
    {
      "executor_id": "fetch_prices",
      "index": 0,
      "model": "claude-3-5-haiku-20241022",
      "tools": ["search_web"],

      "prompt": "You are a price fetcher.\nPrevious outputs: {}\nSearch for iPhone 15 prices...",
      "prompt_template": "You are a price fetcher.\nPrevious outputs: $previous_output\nSearch for {products}",
      "prompt_variables": {
        "previous_output": "{}",
        "products": "iPhone 15, Samsung S24"
      },

      "input": {},
      "output": {
        "prices": [
          {"product": "iPhone 15", "store": "Amazon", "price": 999},
          {"product": "iPhone 15", "store": "Walmart", "price": 989}
        ]
      },

      "loop": null,
      "tool_calls": [
        {"tool": "search_web", "query": "iPhone 15 price Amazon", "duration_ms": 2340},
        {"tool": "search_web", "query": "iPhone 15 price Walmart", "duration_ms": 2100}
      ],

      "started_at": "2025-01-18T09:00:01Z",
      "completed_at": "2025-01-18T09:00:30Z",
      "duration_ms": 29000,
      "token_usage": {"input": 500, "output": 200},
      "status": "completed"
    },
    {
      "executor_id": "compare_prices",
      "index": 1,
      "model": "claude-sonnet-4-5-20250929",
      "tools": ["query_db"],

      "prompt": "You are a price comparator.\nPrevious outputs: {\"prices\": [...]}\nCompare with historical...",
      "prompt_template": "You are a price comparator.\nPrevious outputs: $previous_output\n...",
      "prompt_variables": {
        "previous_output": "{\"prices\": [...]}"
      },

      "input": {"prices": [...]},
      "output": {
        "alerts": [
          {"product": "iPhone 15", "old_price": 949, "new_price": 999, "change_percent": 5.3}
        ],
        "summary": "1 price alert triggered (iPhone 15 on Amazon: $949→$999, +5.3%)"
      },

      "loop": {
        "type": "for_each",
        "input_path": "$.prices",
        "iterations": 2,
        "items": [
          {"iteration": 0, "item": "{...}", "result": "{...}"},
          {"iteration": 1, "item": "{...}", "result": "{...}"}
        ]
      },

      "started_at": "2025-01-18T09:00:31Z",
      "completed_at": "2025-01-18T09:02:00Z",
      "duration_ms": 89000,
      "token_usage": {"input": 1500, "output": 300},
      "status": "completed"
    },
    {
      "executor_id": "send_alerts",
      "index": 2,
      "model": "claude-3-5-haiku-20241022",
      "tools": ["send_message"],

      "prompt": "You are an alert sender.\nPrevious outputs: {\"alerts\": [...]}",
      "prompt_variables": {
        "previous_output": "{\"alerts\": [...]}"
      },

      "input": {"alerts": [...], "summary": "..."},
      "output": {
        "status": "sent",
        "message_count": 1,
        "recipients": ["telegram:123456"]
      },

      "loop": null,
      "tool_calls": [
        {"tool": "send_message", "recipient": "telegram:123456", "message": "...", "duration_ms": 500}
      ],

      "started_at": "2025-01-18T09:02:01Z",
      "completed_at": "2025-01-18T09:02:45Z",
      "duration_ms": 44000,
      "token_usage": {"input": 800, "output": 100},
      "status": "completed"
    }
  ],

  "summary": {
    "total_duration_ms": 162000,
    "total_token_usage": {"input": 2800, "output": 600},
    "executor_count": 3,
    "total_tool_calls": 4,
    "status": "completed"
  }
}
```

### What's Tracked

| Level | What to Track | Why |
|-------|--------------|-----|
| **Workflow Creation** | User input → WorkflowSpec, who created it, timestamp | Reproducibility |
| **Executor Config** | Model, tools, prompt (with `$previous_output` injected), output schema | Debug failures |
| **Prompt Variables** | Template vs. actual values (what was substituted) | Understand data flow |
| **Loop Execution** | Iteration count, each iteration's input/output, exit condition | Verify logic |
| **Tool Calls** | Tool name, input, output, duration, timestamp | Performance analysis |
| **Token Usage** | Input/output tokens per executor | Cost tracking |
| **Errors** | Error messages, stack traces, retry attempts | Debug failures |

### Query Interface

```python
@tool
async def get_workflow_trace(
    workflow_id: str,
    run_id: str = None
) -> str:
    """
    Get detailed execution trace for a workflow.

    Shows:
    - What user requested
    - How each agent was configured (model, tools, prompt)
    - Input/output for each executor
    - Prompt variable substitutions
    - Loop iterations with details
    - Tool calls made (with timing)
    - Token usage and timing

    Args:
        workflow_id: Workflow ID from create_workflow()
        run_id: Specific execution run (optional, defaults to latest)

    Returns:
        Formatted trace output (readable summary)
    """
    # Query workflow_execution_log, workflow_executor_log
    # Return formatted string
    pass


@tool
async def get_workflow_trace_json(
    workflow_id: str,
    run_id: str = None
) -> dict:
    """
    Get execution trace as JSON (for programmatic access).

    Returns the full trace object with all details.
    """
    pass


@tool
async def list_workflow_runs(
    workflow_id: str,
    limit: int = 10
) -> list[dict]:
    """
    List recent runs of a workflow.

    Returns summary of each run (status, duration, timestamp).
    """
    pass
```

### Implementation Module

**File**: `src/cassey/workflows/observability.py`

```python
"""Workflow observability and logging."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from pathlib import Path
import json

from cassey.config import settings


@dataclass
class ToolCallRecord:
    """Record of a single tool call."""
    tool: str
    input: dict
    output: dict
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExecutorTrace:
    """Trace of a single executor execution."""
    executor_id: str
    index: int

    # Configuration
    model: str
    tools: list[str]
    prompt_template: str
    prompt_variables: dict[str, Any]
    system_prompt: str  # After variable substitution
    expected_output_schema: dict

    # Execution
    started_at: str
    completed_at: str | None = None
    duration_ms: int | None = None
    token_usage: dict[str, int] | None = None
    retry_count: int = 0
    status: str = "running"  # running, completed, failed, cancelled

    # Data
    input_data: dict | None = None
    output_data: dict | None = None
    output_summary: str | None = None

    # Loop
    loop_type: str | None = None
    loop_iterations: list[dict] | None = None

    # Tool calls
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    # Error
    error_message: str | None = None


@dataclass
class WorkflowTrace:
    """Complete workflow execution trace."""

    # Metadata
    trace_id: str
    workflow_id: str
    temporal_run_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    status: str = "running"

    # Creation info
    user_request: str | None = None
    created_by: str | None = None
    created_at: str | None = None

    # Executors
    executors: list[ExecutorTrace] = field(default_factory=list)

    # Summary
    total_duration_ms: int | None = None
    total_token_usage: dict[str, int] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "trace_id": self.trace_id,
            "workflow_id": self.workflow_id,
            "temporal_run_id": self.temporal_run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "creation": {
                "user_request": self.user_request,
                "created_by": self.created_by,
                "created_at": self.created_at,
            },
            "executors": [
                {
                    "executor_id": e.executor_id,
                    "index": e.index,
                    "model": e.model,
                    "tools": e.tools,
                    "prompt_template": e.prompt_template,
                    "prompt_variables": e.prompt_variables,
                    "system_prompt": e.system_prompt,
                    "expected_output_schema": e.expected_output_schema,
                    "input": e.input_data,
                    "output": e.output_data,
                    "loop": {
                        "type": e.loop_type,
                        "iterations": e.loop_iterations,
                    } if e.loop_type else None,
                    "tool_calls": [
                        {
                            "tool": tc.tool,
                            "input": tc.input,
                            "output": tc.output,
                            "duration_ms": tc.duration_ms,
                            "timestamp": tc.timestamp,
                        }
                        for tc in e.tool_calls
                    ],
                    "started_at": e.started_at,
                    "completed_at": e.completed_at,
                    "duration_ms": e.duration_ms,
                    "token_usage": e.token_usage,
                    "status": e.status,
                    "error_message": e.error_message,
                }
                for e in self.executors
            ],
            "summary": {
                "total_duration_ms": self.total_duration_ms,
                "total_token_usage": self.total_token_usage,
                "executor_count": len(self.executors),
                "total_tool_calls": sum(len(e.tool_calls) for e in self.executors),
                "status": self.status,
            }
        }


async def save_workflow_trace(
    trace: WorkflowTrace,
    workflow_id: str,
) -> None:
    """Save workflow trace to file and database.

    Args:
        trace: The workflow trace to save
        workflow_id: Workflow ID for file naming
    """
    # 1. Save to file (full JSON)
    traces_dir = settings.get_group_workflows_path(workflow_id) / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    trace_file = traces_dir / f"{trace.trace_id}.json"
    with open(trace_file, "w") as f:
        json.dump(trace.to_dict(), f, indent=2)

    # 2. Save to database (summary + reference)
    # TODO: Implement database logging
    # await db.execute("""
    #     INSERT INTO workflow_execution_log ...
    # """)


def format_trace_summary(trace: WorkflowTrace) -> str:
    """Format a workflow trace for human reading.

    Args:
        trace: The workflow trace

    Returns:
        Formatted multi-line string
    """
    lines = [
        f"Workflow Trace: {trace.workflow_id}",
        f"Run ID: {trace.temporal_run_id}",
        f"Status: {trace.status.upper()}",
        f"Started: {trace.started_at}",
    ]

    if trace.completed_at:
        lines.append(f"Completed: {trace.completed_at}")

    if trace.user_request:
        lines.append(f"\nUser Request: {trace.user_request}")

    lines.append(f"\nExecutors ({len(trace.executors)}):")
    lines.append("-" * 60)

    for executor in trace.executors:
        lines.append(f"\n{executor.index + 1}. {executor.executor_id}")
        lines.append(f"   Model: {executor.model}")
        lines.append(f"   Tools: {', '.join(executor.tools) or 'none'}")
        lines.append(f"   Status: {executor.status}")

        if executor.duration_ms:
            lines.append(f"   Duration: {executor.duration_ms}ms")

        if executor.token_usage:
            lines.append(f"   Tokens: {executor.token_usage}")

        if executor.input_data:
            lines.append(f"   Input: {json.dumps(executor.input_data, indent=6)[:200]}...")

        if executor.output_summary:
            lines.append(f"   Output: {executor.output_summary}")

        if executor.loop_type:
            lines.append(f"   Loop: {executor.loop_type} ({len(executor.loop_iterations or [])} iterations)")

        if executor.tool_calls:
            lines.append(f"   Tool Calls: {len(executor.tool_calls)}")
            for tc in executor.tool_calls:
                lines.append(f"     - {tc.tool}: {tc.duration_ms}ms")

        if executor.error_message:
            lines.append(f"   Error: {executor.error_message}")

    return "\n".join(lines)
```

### Updated Implementation Plan

| Task | Status | Description |
|------|--------|-------------|
| `WorkflowSpec` models | ⏳ Pending | Pydantic models for workflow/executor specs |
| `Observability` module | ⏳ Pending | Trace classes + logging functions |
| Database schema | ⏳ Pending | `workflows` + observability tables |
| `CasseyWorkflow` class | ⏳ Pending | Workflow definition with executor chain + tracing |
| `CasseyRecurringWorkflow` class | ⏳ Pending | Cron-based recurring workflow |
| `run_executor` activity | ⏳ Pending | Activity that calls `create_agent()` + records trace |
| `send_notification` activity | ⏳ Pending | Activity for notifications |
| Tool integration | ⏳ Pending | `create_workflow`, `get_workflow_trace` tools |
