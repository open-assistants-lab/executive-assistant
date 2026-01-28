# Multi-Agent Architecture: Executive Assistant, Orchestrator, Workers

> Archived: Orchestrator/worker agents are disabled in the current runtime. This doc is kept for reference only.

## Concept

Executive Assistant can delegate to specialized agents. The hierarchy is:

- **Executive Assistant** = Main agent with full tool access. Handles requirements & goals with users.
- **Orchestrator** = Task & flow specialist. Receives concrete tasks, creates workers, handles scheduling.
- **Workers** = Task-specific agents that do the actual work.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Executive Assistant                                │
│  - Has all tools                                        │
│  - Can delegate to Orchestrator                         │
│  - Aggregates results                                   │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│                 Orchestrator                            │
│  - Scheduling & workflows                               │
│  - Can SPAWN workers                                    │
│  - Handles dependencies, retries, chains                │
│  - Tools: spawn_worker, schedule_flow, list_flows         │
└─────────────────────────────────────────────────────────┘
         │           │           │
         ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Worker   │ │ Worker   │ │ Worker   │
    │: Price   │ │: Report  │ │: Scraper │
    │  Checker │ │  Writer  │ │          │
    └──────────┘ └──────────┘ └──────────┘

Workers: Task-specific, cannot spawn anything
```

## Implementation Pattern

```python
# Executive Assistant delegates to Orchestrator
@tool
def delegate_to_orchestrator(task: str, flow: str, schedule: str = None) -> str:
    """Delegate a concrete task and flow to the Orchestrator.

    NOTE: Requirements & goals should already be agreed with the user.
    This tool is for the actual execution plan.

    The Orchestrator will:
    - Create appropriate workers for the task
    - Set up schedules if needed
    - Handle dependencies and workflows

    Args:
        task: Concrete task to execute (e.g., "Check Amazon price for B08X12345")
        flow: Execution flow with conditions, e.g.:
            - "fetch price → if < $100 notify, else log to transactional database"
            - "check API → if error retry 3x, else continue"
            - "scrape data → if empty send alert, else save to file"
        schedule: Optional schedule (e.g., "daily at 9am", "hourly")

    USE THIS FOR:
    - Recurring/automated tasks with clear execution flow
    - Multi-step workflows with dependencies
    - Tasks requiring specialized workers

    DO NOT USE FOR:
    - Simple one-off questions (use tools directly)
    - Gathering requirements (talk to user instead)
    """
    # The Orchestrator agent handles the rest

# Orchestrator can spawn workers
def spawn_worker(name: str, tools: list[str], prompt: str) -> str:
    """Create a new worker agent.

    Only the Orchestrator can call this. Workers cannot spawn other workers.
    """
    # Creates a worker with specific tools and prompt
```

## Tool Assignment

| Agent | Tools |
|-------|-------|
| **Executive Assistant** | All tools + `delegate_to_orchestrator` |
| **Orchestrator** | `spawn_worker`, `schedule_flow`, `list_flows`, `cancel_flow` |
| **Workers** | Task-specific subset (e.g., `web_search` + `execute_python` for price checker) |

## Key Design Decisions

### 1. **Only Orchestrator Spawns Workers**

**Why**: Prevents infinite spawn loops and keeps hierarchy clean.

- Executive Assistant cannot spawn (only delegates to Orchestrator)
- Workers cannot spawn (only do their job)
- Orchestrator is the only spawner (designed to do so responsibly)

### 2. **Dynamic Worker Creation**

The Orchestrator creates workers on demand based on the task:

```python
# Orchestrator decides: "I need a price checker worker"
worker = spawn_worker(
    name="price_checker_001",
    tools=["web_search", "execute_python"],
    prompt="Check prices, compare to threshold, output result"
)
```

### 3. **Clear Separation: Requirements vs Execution**

| Phase | Who | Responsibility |
|-------|-----|----------------|
| **Requirements & Goals** | Executive Assistant + User | "I need daily price alerts under $100" |
| **Task & Flow** | Executive Assistant → Orchestrator | "Check price, compare, notify if below" |
| **Execution** | Orchestrator → Workers | Spawn workers, schedule, run |

Executive Assistant handles the "what do we want?" conversation with the user.
Orchestrator handles the "how do we execute?" implementation.

## Conditional Flows

Workers (with Python capability) handle conditions and loops:

| Flow Pattern | Example |
|--------------|---------|
| **If/else** | "If price < $100 notify, else log to transactional database" |
| **For loop** | "For each product in list → check price → if < $100 add to alert list" |
| **While loop** | "While API returns more pages → fetch results → append to file" |
| **Retry loop** | "Check API → if error retry 3x → if still fails, send alert" |
| **Multi-branch** | "If new user → send welcome, if returning → send recap, if churned → send win-back" |
| **Threshold check** | "If CPU > 80% → alert, if CPU > 90% → critical alert" |
| **Exists check** | "If file exists → append, else create new" |
| **Until condition** | "Repeat every 5 minutes until status = 'complete', then notify" |

The Orchestrator translates the flow description into a worker prompt with appropriate logic:

```python
# Orchestrator generates worker prompt
WORKER_PROMPT = """You are a Price Checker.
1. Fetch the price for product B08X12345
2. If price < $100: write to price_alert_message.txt
3. If price >= $100: append to price_history.csv with timestamp
"""

# Example with for loop
MULTI_PRODUCT_CHECKER = """You are a Multi-Product Price Checker.
Products: ["B08X12345", "B08X67890", "B08X11111"]

For each product in the list:
1. Fetch price from Amazon
2. If price < $100: add to alert list
3. If price >= $100: log to price_history.csv

After checking all products: if alert_list not empty, send summary notification
"""
```

## Comparison: Simple vs Prefect vs Temporal

### Build Ourselves (Recommended)

**Pros**:
- ✅ Zero new dependencies
- ✅ Full control over behavior
- ✅ Simple mental model
- ✅ Easy to customize
- ✅ Subagents = just `create_agent(tools, prompt)`

**Cons**:
- ❌ Need to write retry logic
- ❌ No built-in UI
- ❌ Manual error handling

**Best for**:
- Single-server deployment
- Custom workflows
- Learning/AI research
- MVP/prototyping

### Prefect (prefect.io)

**Pros**:
- ✅ Battle-tested workflow engine
- ✅ Built-in retries, backoff, caching
- ✅ Nice UI for monitoring
- ✅ Distributed execution support
- ✅ Scheduled workflows

**Cons**:
- ❌ New dependency to learn
- ❌ Overkill for simple use cases
- ❌ May conflict with LangGraph's state machine
- ❌ Additional infrastructure

**Best for**:
- Production data pipelines
- Multi-worker deployments
- Complex dependencies
- Teams wanting visual debugging

### Temporal

**Pros**:
- ✅ Durable execution
- ✅ Long-running workflows
- ✅ Strong consistency

**Cons**:
- ❌ Heavy infrastructure (needs Temporal server)
- ❌ Go/Java-first (Python SDK secondary)
- ❌ Overkill for AI agent workflows

**Best for**:
- Enterprise workflows
- Multi-step transactions
- Very long-running processes

## Recommendation

**Start simple (no Prefect)**:

1. Implement subagents with `create_agent(tools, prompt)`
2. Add basic scheduling with APScheduler (already installed)
3. Add event triggers (webhooks, file watch)
4. Custom retry logic if needed

**Consider Prefect later if**:
- You need robust retry/backoff at scale
- You want a visual workflow debugger
- You're deploying multiple workers
- You need distributed execution

## Hybrid Approach (Future)

```python
# Orchestrator creates a worker that uses Prefect for specific workflows
from prefect import flow, task

@flow
def complex_pipeline():
    # Prefect handles retries, caching, orchestration
    result1 = extract_data()
    result2 = transform(result1)
    result3 = load(result2)
    return result3

# Orchestrator wraps this in a worker
pipeline_worker = spawn_worker(
    tools=[run_pipeline],
    prompt="Execute the complex data pipeline"
)
```

## Agent Lifecycle

```
1. Executive Assistant discusses with user
   User: "I need to know when this product drops below $100"
   Executive Assistant: "I can set up a daily price check. Should I alert you via Telegram?"
   User: "Yes, daily at 9am"

2. Executive Assistant delegates to Orchestrator
   delegate_to_orchestrator(
       task="Check Amazon price for B08X12345",
       flow="""
       1. Fetch price from Amazon
       2. If price < $100 → send Telegram notification
       3. If price >= $100 → log to price_history table
       """,
       schedule="daily at 9am"
   )

3. Orchestrator creates worker(s)
   spawn_worker("price_checker", tools=["web_search", "execute_python"], prompt="...")

4. Orchestrator schedules the worker
   schedule_flow(worker_id, cron="0 9 * * *")

5. Worker executes on schedule
   At 9am daily: worker runs its task
```

## Orchestrator Prompt

```python
ORCHESTRATOR_PROMPT = """You are an Orchestrator specializing in scheduling and workflows.

Your responsibilities:
- Understand the user's task requirements
- Create appropriate workers with specific tools and prompts
- Set up schedules (daily, hourly, cron expressions)
- Handle job dependencies and chains
- Add retry logic for failed jobs
- Report back what you've set up

When creating workers:
- Give them clear, specific prompts
- Only give them the tools they need
- Consider error cases

Tools available:
- spawn_worker(name, tools, prompt): Create a new worker
- schedule_flow(worker_id, schedule): Set up execution time
- list_flows(): Show all scheduled flows
- cancel_flow(flow_id): Cancel a scheduled flow
"""

## No New Dependencies

For the simple approach:
- `create_react_graph()`: Already implemented in `src/executive_assistant/agent/graph.py`
- APScheduler: Already installed for reminders
- Python exec(): Already used in python_tool
- File/transactional database tools: Already implemented

## Implementation Plan

1. **Phase 1**: Transactional Database schema for workers and flows
   - `workers` table (name, tools[], prompt, user_id, created_at)
   - `scheduled_flows` table (from scheduled_flows_design.md)

2. **Phase 2**: Implement Orchestrator
   - `delegate_to_orchestrator` tool for Executive Assistant
   - Orchestrator agent with specialized prompt
   - `spawn_worker`, `schedule_flow`, `list_flows`, `cancel_flow` tools for Orchestrator

3. **Phase 3**: Worker execution
   - Scheduler invokes workers at scheduled times
   - Workers run with their assigned tools and prompts
   - Result logging and error handling

## Status

**Design complete.** Hierarchy established:
- Executive Assistant → Orchestrator → Workers
- Only Orchestrator can spawn workers
- Clear separation: requirements (Executive Assistant+User) vs execution (Orchestrator)

Implementation pending after scheduled flows system foundation is complete.
