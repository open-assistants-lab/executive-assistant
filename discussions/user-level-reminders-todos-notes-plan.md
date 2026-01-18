# Temporal-Based User Features: Reminders, Todos, Notes, Workflows

> **Last Updated:** 2025-01-18
> **Status:** Partially Implemented (Reminders interim, others pending)

## Goal

Implement group-level storage and Temporal-based scheduling for:
1. **Reminders** - Single-step scheduled notifications (Temporal)
2. **Todos** - Task tracking with custom fields (SQLite)
3. **Notes** - Knowledge base with semantic search (DuckDB KB)
4. **Workflows** - Multi-step automation chains (Temporal)

---

## Current Implementation Status

| Component | Status | Storage | Scheduler |
|-----------|--------|---------|-----------|
| **Reminders** | ⚠️ Interim | PostgreSQL | APScheduler (polling) |
| **Reminders** | 🎯 Target | PostgreSQL | Temporal (durable timers) |
| **Todos** | ❌ Not Started | Group SQLite | N/A |
| **Notes** | ⚠️ Partial | DuckDB KB | N/A |
| **Workflows** | ❌ Not Started | PostgreSQL | Temporal (chains) |

---

## Architecture (Target Design)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VM 1: Cassey Application                         │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Temporal Worker                                                   │ │
│  │                                                                   │ │
│  │  - Polls Temporal Server for workflow/activity tasks               │ │
│  │  - Executes reminder workflows (single activity)                   │ │
│  │  - Executes automation workflows (executor chains)                │ │
│  │  - Runs activities (agent calls, tool invocations)                │ │
│  │  - Connects to Cassey tools, SQLite, PostgreSQL, DuckDB           │ │
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
│  │  - Manages durable timers (reminders)                            │ │
│  │  - Manages cron schedules (recurring workflows)                  │ │
│  │  - Dispatches work to workers                                     │ │
│  │  - Provides observability UI (port 8088)                        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Frontend: 7233 (gRPC) │ UI: 8088 (web dashboard)                      │
│  PostgreSQL: Temporal's state store (can share Cassey's DB)            │
│                                                                         │
│  Task Queues:                                                          │
│  - cassey-reminders  → Single-step reminder workflows                 │
│  - cassey-workflows  → Multi-step automation chains                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                                    │
│                                                                         │
│  3-Level Hierarchy:                                                    │
│                                                                         │
│  Level 1: data/shared/                                                 │
│  ├── shared.db                 ← Admin write, everyone read             │
│                                                                         │
│  Level 2: data/groups/{group_id}/   (was: workspaces/)                  │
│  ├── db/db.sqlite             ← Todos (SQLite, group data)              │
│  │   ├── todos                (with user-defined extensions)            │
│  │   └── _schema_registry     (tracks user customizations)             │
│  ├── kb/kb.db                 ← Notes (DuckDB + VSS + FTS)              │
│  │   └── notes collection     (with metadata JSON)                     │
│  └── files/                   ← File storage                            │
│                                                                         │
│  Level 3: data/users/{user_id}/                                         │
│  └── (personal data, not shared in groups)                             │
│                                                                         │
│  PostgreSQL (Centralized):                                              │
│  ├── reminders                ← Reminder records                        │
│  ├── workflows                ← Workflow definitions                    │
│  ├── conversations            ← LangGraph checkpoints                   │
│  └── ...                     ← Other app data                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Reminders (Temporal - Single-Step Workflows)

### Concept

Reminders are **single-executor workflows** with Temporal managing durable timers:
- **Workflow:** Sleep until due_time → send notification
- **Recurring:** Use Temporal cron for daily/weekly schedules
- **Storage:** PostgreSQL `reminders` table (already exists)
- **Benefit:** Durable (survives restarts), sub-second precision

### Workflow Definition

```python
"""src/cassey/temporal_workflows.py"""

from datetime import timedelta
from temporalio import workflow, activity

@workflow.defn
class ReminderWorkflow:
    """Single-step reminder workflow: sleep until due, then notify."""

    @workflow.run
    async def run(self, group_id: str, reminder_id: int, due_time: str) -> None:
        """Wait until due_time, then send notification."""
        from datetime import datetime

        due_dt = datetime.fromisoformat(due_time.replace('Z', '+00:00'))
        delay_seconds = (due_dt - datetime.now()).total_seconds()

        if delay_seconds > 0:
            # Durable sleep: Temporal persists state even across restarts
            await workflow.sleep(timedelta(seconds=delay_seconds))

        # Time's up! Send notification
        await workflow.execute_activity(
            send_reminder_notification,
            args=[group_id, reminder_id],
            start_to_close_timeout=timedelta(seconds=30)
        )


@activity.defn
def send_reminder_notification(group_id: str, reminder_id: int) -> bool:
    """Fetch reminder from PostgreSQL and send notification."""
    from cassey.storage.reminder import get_reminder_storage

    storage = await get_reminder_storage()
    reminder = await storage.get_by_id(reminder_id)

    if not reminder or reminder.status != 'pending':
        return False

    # Send via channel (telegram, email, etc.)
    # Implementation varies by channel
    send_message(reminder.thread_ids, reminder.message)

    # Mark as sent
    await storage.mark_sent(reminder_id)

    # Handle recurring reminders
    if reminder.is_recurring:
        from cassey.utils.cron import parse_cron_next
        next_due = parse_cron_next(reminder.recurrence, datetime.now())
        await storage.create(
            user_id=reminder.user_id,
            thread_ids=reminder.thread_ids,
            message=reminder.message,
            due_time=next_due,
            recurrence=reminder.recurrence,
        )

    return True
```

### Updated Reminder Tools (Temporal)

```python
"""src/cassey/tools/reminder_tools.py (updated)"""

from temporalio.client import Client

@tool
async def reminder_set(
    message: str,
    time: str,
    recurrence: str = "",
) -> str:
    """Set a reminder using Temporal for durable scheduling."""
    from temporalio.client import Client

    storage = await _get_storage()
    thread_id = get_thread_id()

    # Parse time
    due_time = _parse_time_expression(time)

    # Save to PostgreSQL first
    reminder = await storage.create(
        user_id=thread_id,
        thread_ids=[thread_id],
        message=message,
        due_time=due_time,
        recurrence=recurrence or None,
    )

    # Connect to Temporal Server
    client = await Client.connect("temporal.vm2.internal:7233")

    # Start Temporal workflow for the reminder
    workflow_id = f"reminder-{thread_id}-{reminder.id}"

    if recurrence:
        # Recurring reminder - use Temporal cron
        cron_expr = parse_recurrence_to_cron(recurrence)
        await client.start_workflow(
            ReminderWorkflow.run,
            args=[thread_id, reminder.id, "$$NOW"],
            id=workflow_id,
            task_queue="cassey-reminders",
            cron_expression=cron_expr
        )
    else:
        # One-time reminder
        await client.start_workflow(
            ReminderWorkflow.run,
            args=[thread_id, reminder.id, due_time.isoformat()],
            id=workflow_id,
            task_queue="cassey-reminders"
        )

    return f"Reminder set for {due_time.strftime('%Y-%m-%d %H:%M')}. ID: {reminder.id}"


@tool
async def reminder_cancel(reminder_id: int) -> str:
    """Cancel a pending reminder."""
    from temporalio.client import Client

    storage = await _get_storage()
    thread_id = get_thread_id()

    # Verify ownership
    reminder = await storage.get_by_id(reminder_id)
    if not reminder or reminder.user_id != thread_id:
        return f"Reminder {reminder_id} not found."

    # Cancel Temporal workflow
    client = await Client.connect("temporal.vm2.internal:7233")
    workflow_id = f"reminder-{thread_id}-{reminder_id}"
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()

    # Mark as cancelled in PostgreSQL
    await storage.cancel(reminder_id)

    return f"Reminder {reminder_id} cancelled."
```

### Current (Interim) vs Target

| Aspect | Current (APScheduler) | Target (Temporal) |
|--------|------------------------|------------------|
| **Polling** | Every 60 seconds | Event-driven |
| **Durable** | ❌ Lost on restart | ✅ Survives restarts |
| **Precision** | 60-second granularity | Sub-second |
| **Cron** | Manual recalculation | Native cron support |
| **Observability** | Custom logging | Temporal Web UI |

---

## Feature 2: Todos (SQLite - No Workflow Needed)

### Concept

Todos are **simple CRUD** - no automation needed:
- **Storage:** Per-group SQLite `todos` table
- **Schema:** Base columns + user-extensible via ALTER TABLE
- **Tools:** `todo_add`, `todo_list`, `todo_complete`, `add_todo_field`

### Schema

```sql
CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',      -- todo, in_progress, done
    priority TEXT DEFAULT 'medium',   -- low, medium, high
    due_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_due_date ON todos(due_date);
```

### Tools

```python
"""src/cassey/tools/todo_tools.py"""

from langchain_core.tools import tool
from cassey.storage.sqlite_db_storage import get_sqlite_db
from cassey.storage.group_storage import get_workspace_id

@tool
async def todo_add(
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: str = None,
    **kwargs
) -> str:
    """Add a todo to your group.

    Args:
        title: Todo title
        description: Additional details
        priority: low, medium, high
        due_date: Due date (natural language or ISO format)
        **kwargs: Any custom fields (sprint, assignee, tags, etc.)

    Returns:
        Confirmation message.
    """
    from cassey.utils.time_parser import parse_natural_time

    db = get_sqlite_db()
    ensure_todo_schema()

    # Parse due date
    if due_date:
        due_date = parse_natural_time(due_date).isoformat()

    # Add custom columns if provided
    for key, value in kwargs.items():
        add_custom_column_if_not_exists('todos', key, value)

    # Build SQL with custom fields
    columns = ['title', 'description', 'status', 'priority', 'due_date']
    values = [title, description, 'todo', priority, due_date]

    for key, value in kwargs.items():
        columns.append(key)
        values.append(value)

    placeholders = ', '.join(['?'] * len(columns))
    db.execute(f"INSERT INTO todos ({', '.join(columns)}) VALUES ({placeholders})", values)
    db.commit()

    return f"✅ Todo added: {title}"


@tool
async def todo_list(status: str = None) -> str:
    """List your todos.

    Args:
        status: Filter by status (todo, in_progress, done). Empty for all.

    Returns:
        Formatted list of todos.
    """
    db = get_sqlite_db()
    ensure_todo_schema()

    if status:
        cursor = db.execute("SELECT * FROM todos WHERE status = ? ORDER BY created_at DESC", [status])
    else:
        cursor = db.execute("SELECT * FROM todos ORDER BY created_at DESC")

    rows = cursor.fetchall()
    if not rows:
        return "No todos found."

    # Format results
    lines = [f"{'ID':<5} {'Status':<12} {'Priority':<10} {'Title'}"]
    lines.append("-" * 80)

    for row in rows:
        id_, title, desc, status, priority, due_date, created_at, completed_at = row
        status_emoji = {"todo": "📝", "in_progress": "🔄", "done": "✅"}.get(status, "📌")
        priority_mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "")
        lines.append(f"{id_:<5} {status_emoji} {status:<10} {priority_mark} {title}")

    return "\n".join(lines)


@tool
async def todo_complete(todo_id: int) -> str:
    """Mark a todo as complete.

    Args:
        todo_id: The ID of the todo to complete

    Returns:
        Confirmation message.
    """
    db = get_sqlite_db()
    ensure_todo_schema()

    db.execute("""
        UPDATE todos
        SET status = 'done', completed_at = datetime('now')
        WHERE id = ?
    """, [todo_id])
    db.commit()

    return f"✅ Todo {todo_id} marked as complete"


@tool
async def add_todo_field(field_name: str, field_type: str = "TEXT") -> str:
    """Add a custom field to todos.

    Use this to customize your todos table for your specific needs.

    Args:
        field_name: Name of the field to add (e.g., "sprint", "assignee")
        field_type: Data type: TEXT, INTEGER, REAL, BOOLEAN

    Returns:
        Confirmation message.

    Examples:
        add_todo_field("sprint", "INTEGER")
        add_todo_field("assignee", "TEXT")
    """
    db = get_sqlite_db()
    add_custom_column_if_not_exists('todos', field_name, None)
    return f"✅ Added field '{field_name}' to todos"
```

### Storage Helper

```python
"""src/cassey/storage/todo_storage.py"""

from cassey.storage.sqlite_db_storage import get_sqlite_db

def ensure_todo_schema() -> None:
    """Create todos table if not exists."""
    db = get_sqlite_db()
    if not db.table_exists("todos"):
        db.execute("""
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'todo',
                priority TEXT DEFAULT 'medium',
                due_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date)")
        db.commit()


def add_custom_column_if_not_exists(table: str, column: str, value=None) -> None:
    """Add a custom column to a table if it doesn't exist."""
    db = get_sqlite_db()

    # Check if column exists
    cursor = db.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if column not in existing_columns:
        # Infer type from value
        if value is not None:
            if isinstance(value, bool):
                col_type = "BOOLEAN"
            elif isinstance(value, int):
                col_type = "INTEGER"
            elif isinstance(value, float):
                col_type = "REAL"
            elif isinstance(value, (list, dict)):
                col_type = "TEXT"  # Store as JSON
            else:
                col_type = "TEXT"
        else:
            col_type = "TEXT"

        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        db.commit()
```

---

## Feature 3: Notes (DuckDB KB - No Workflow Needed)

### Concept

Notes use **existing KB infrastructure**:
- **Storage:** DuckDB with hybrid FTS+VSS (already implemented)
- **Tools:** Dedicated note tools on top of KB collections
- **Metadata:** title, tags, updated_at stored in JSON

### Tools

```python
"""src/cassey/tools/note_tools.py"""

from langchain_core.tools import tool
from cassey.storage.duckdb_storage import create_duckdb_collection, get_duckdb_collection, list_duckdb_collections
from cassey.storage.group_storage import get_workspace_id

@tool
async def note_save(
    title: str,
    content: str,
    tags: list[str] = None,
    **kwargs
) -> str:
    """Save a note to your knowledge base.

    Notes are stored with semantic + fulltext search.

    Args:
        title: Note title
        content: Note content (markdown supported)
        tags: List of tags for organization
        **kwargs: Any additional metadata (category, color, pin, etc.)

    Returns:
        Confirmation message.

    Examples:
        note_save("Meeting Notes", "# Discussed Q1 roadmap...", tags=["planning"])
        note_save("Ideas", "Random thought...", category="personal", color="blue")
    """
    from datetime import datetime

    storage_id = get_workspace_id()
    metadata = {
        "title": title,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "tags": tags or [],
        **kwargs
    }

    # Get or create notes collection
    collections = list_duckdb_collections(storage_id=storage_id)
    if "notes" not in collections:
        collection = create_duckdb_collection(
            storage_id=storage_id,
            collection_name="notes",
            documents=[]
        )
    else:
        collection = get_duckdb_collection(storage_id, "notes")

    # Add note
    collection.add_documents([{
        "content": content,
        "metadata": metadata
    }])

    tag_str = f" (tags: {', '.join(tags)})" if tags else ""
    return f"✅ Note saved: {title}{tag_str}"


@tool
async def note_search(query: str, limit: int = 5) -> str:
    """Search your notes.

    Uses both semantic search (finds related content) and full-text search.

    Args:
        query: Search query
        limit: Maximum results (default: 5)

    Returns:
        Formatted search results.
    """
    from cassey.storage.duckdb_storage import list_duckdb_collections, get_duckdb_collection

    storage_id = get_workspace_id()
    collections = list_duckdb_collections(storage_id=storage_id)

    if "notes" not in collections:
        return "No notes collection found. Save a note first."

    collection = get_duckdb_collection(storage_id, "notes")
    results = collection.search(query=query, limit=limit, search_type="hybrid")

    if not results:
        return f"No notes found for '{query}'."

    output = f"Notes matching '{query}':\n\n"
    for r in results[:limit]:
        metadata = r.metadata or {}
        title = metadata.get("title", "Untitled")
        content_preview = r.content[:150].replace("\n", " ") + "..." if len(r.content) > 150 else r.content
        tags = metadata.get("tags", [])
        tag_str = f" #{' #'.join(tags)}" if tags else ""
        score_str = f"[{r.score:.2f}] " if r.score >= 0 else ""
        output += f"📝 {title}{tag_str}\n{score_str}{content_preview}\n\n"

    return output


@tool
async def note_list(limit: int = 10) -> str:
    """List recent notes.

    Args:
        limit: Maximum number of notes to show

    Returns:
        Formatted list of recent notes.
    """
    from cassey.storage.duckdb_storage import list_duckdb_collections, get_duckdb_collection

    storage_id = get_workspace_id()
    collections = list_duckdb_collections(storage_id=storage_id)

    if "notes" not in collections:
        return "No notes collection found."

    collection = get_duckdb_collection(storage_id, "notes")
    docs = collection.documents

    if not docs:
        return "No notes found."

    lines = [f"Recent notes (showing {min(limit, len(docs))}):\n"]

    for i, (doc_id, content) in enumerate(list(docs.items())[:limit]):
        # Get metadata from search to get title
        result = collection.search(content[:50], limit=1)
        if result:
            metadata = result[0].metadata or {}
            title = metadata.get("title", "Untitled")
            tags = metadata.get("tags", [])
            tag_str = f" #{' #'.join(tags)}" if tags else ""
            lines.append(f"{i+1}. {title}{tag_str}")
        else:
            lines.append(f"{i+1}. {content[:50]}...")

    return "\n".join(lines)
```

---

## Feature 4: Workflows (Temporal - Multi-Step Automation)

### Concept

Workflows are **multi-executor automation chains**:
- **Each executor:** `create_agent()` with specific tools + prompt
- **Flow:** Sequential chain, previous output → next input
- **Scheduling:** Immediate, scheduled (due time), or recurring (cron)
- **Storage:** PostgreSQL `workflows` table + Temporal execution tracking

### Data Models

```python
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class ExecutorSpec(BaseModel):
    """Definition of a single executor (Temporal Activity)."""

    executor_id: str
    name: str
    description: str

    # Agent configuration
    model: str  # e.g., "gpt-4o", "gpt-4o-mini"
    tools: list[str]  # Tool names from Cassey's registry
    system_prompt: str

    # Structured output schema
    output_schema: dict

    # Temporal activity configuration
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_backoff: int = 60

class WorkflowSpec(BaseModel):
    """Workflow definition (passed to Temporal)."""

    workflow_id: str
    name: str
    description: str

    # Chain of executors
    executors: list[ExecutorSpec]

    # Scheduling
    schedule_type: Literal["immediate", "scheduled", "recurring"]
    schedule_time: Optional[datetime] = None
    cron_expression: Optional[str] = None

    # Notification
    notify_on_complete: bool = False
    notify_on_failure: bool = True
    notification_channel: Literal["telegram", "email", "web", "none"] = "telegram"
```

### Temporal Workflow (Multi-Step)

```python
"""src/cassey/temporal_workflows.py"""

@workflow.defn
class CasseyWorkflow:
    """Multi-step workflow that executes a chain of executors."""

    @workflow.run
    async def run(self, spec: WorkflowSpec) -> dict:
        """Execute the workflow executor by executor."""

        # Calculate delay if scheduled
        if spec.schedule_type == "scheduled" and spec.schedule_time:
            delay = (spec.schedule_time - datetime.now()).total_seconds()
            if delay > 0:
                await workflow.sleep(timedelta(seconds=delay))

        # Shared context across executors
        executor_outputs = {}
        results = []

        # Execute each executor as an activity
        for i, executor_spec in enumerate(spec.executors):
            try:
                # Execute the activity with retry policy
                output = await workflow.execute_activity(
                    run_executor_activity,
                    args=[executor_spec, executor_outputs],
                    retry_policy=RetryPolicy(
                        max_attempts=executor_spec.max_retries,
                        initial_retry=timedelta(seconds=executor_spec.retry_backoff)
                    ),
                    start_to_close_timeout=timedelta(seconds=executor_spec.timeout_seconds)
                )

                # Store output for next executor
                executor_outputs[executor_spec.executor_id] = output
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
                        send_notification_activity,
                        args=[spec.notification_channel, f"Workflow failed: {spec.name}"]
                    )

                raise  # Stop workflow execution

        # All executors completed successfully
        if spec.notify_on_complete:
            await workflow.execute_activity(
                send_notification_activity,
                args=[spec.notification_channel, f"Workflow completed: {spec.name}"]
            )

        return {
            "workflow_id": spec.workflow_id,
            "status": "completed",
            "executor_results": results
        }


@activity.defn
def run_executor_activity(executor_spec: ExecutorSpec, previous_outputs: dict) -> dict:
    """Execute a single executor (agent with tools)."""
    from cassey.tools.registry import get_tools_by_name

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
    from langchain.agents import create_agent
    from langchain_core.messages import HumanMessage

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


@activity.defn
def send_notification_activity(channel: str, message: str) -> bool:
    """Send notification to user via specified channel."""
    if channel == "telegram":
        # Send via Telegram
        pass
    elif channel == "email":
        # Send via email
        pass
    return True
```

### Example: Price Monitoring Workflow

```python
workflow_spec = {
    "workflow_id": "daily_price_monitor",
    "name": "Daily Competitor Price Monitor",
    "description": "Check competitor prices and alert on changes",

    "executors": [
        {
            "executor_id": "fetch_prices",
            "name": "Price Fetcher",
            "model": "gpt-4o-mini",
            "tools": ["search_web"],
            "system_prompt": """Fetch prices for:
- Apple iPhone 15 Pro
- Samsung Galaxy S24

Search Amazon and Walmart. Return JSON:
{
    "prices": [
        {"product": "str", "competitor": "str", "price": "float", "url": "str"}
    ]
}""",
            "output_schema": {
                "prices": [{"product": "str", "competitor": "str", "price": "float", "url": "str"}]
            }
        },
        {
            "executor_id": "compare_prices",
            "name": "Price Comparator",
            "model": "gpt-4o",
            "tools": ["query_db"],
            "system_prompt": """Previous output: $previous_output

Compare with historical data. Flag changes > 10%. Return:
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
            "model": "gpt-4o-mini",
            "tools": ["send_message"],
            "system_prompt": """Previous output: $previous_output

Send message with summary. Return:
{
    "status": "str",
    "message_count": "int"
}""",
            "output_schema": {"status": "str", "message_count": "int"}
        }
    ],

    "schedule_type": "recurring",
    "cron_expression": "0 9 * * MON-FRI",  # Weekdays at 9am
    "notify_on_complete": False,
    "notify_on_failure": True
}
```

### Workflow Tools

```python
"""src/cassey/tools/workflow_tools.py"""

from temporalio.client import Client

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
    notification_channel: str = "telegram"
) -> str:
    """Create a workflow from a chain of executors (backed by Temporal).

    Each executor is a create_agent() with:
    - executor_id: Unique ID
    - name: Display name
    - model: Which LLM to use
    - tools: List of tool names
    - system_prompt: What this executor does (use $previous_output for injection)
    - output_schema: Expected structured output (JSON schema)

    Args:
        name: Workflow name
        description: What this workflow does
        executors: List of executor specifications
        schedule_type: 'immediate', 'scheduled', or 'recurring'
        schedule_time: For 'scheduled', when to run (natural language or ISO datetime)
        cron_expression: For 'recurring', cron like "0 9 * * MON-FRI"
        notify_on_complete: Send notification when workflow completes
        notify_on_failure: Send notification when workflow fails
        notification_channel: 'telegram', 'email', 'web', or 'none'

    Returns:
        workflow_id for tracking/cancellation

    Example:
        executors = [
            {
                "executor_id": "fetch",
                "name": "Fetcher",
                "model": "gpt-4o-mini",
                "tools": ["search_web"],
                "system_prompt": "Search for prices. Return JSON.",
                "output_schema": {"prices": [{"product": "str", "price": "float"}]}
            }
        ]
        await create_workflow("Price Monitor", executors, "recurring", cron_expression="0 9 * * *")
    """
    from datetime import datetime

    client = await Client.connect("temporal.vm2.internal:7233")

    # Parse schedule time if provided
    parsed_time = None
    if schedule_time:
        parsed_time = parse_natural_time(schedule_time)

    # Build WorkflowSpec
    spec = WorkflowSpec(
        workflow_id=str(uuid.uuid4()),
        name=name,
        description=description,
        executors=[ExecutorSpec(**e) for e in executors],
        schedule_type=schedule_type,
        schedule_time=parsed_time,
        cron_expression=cron_expression,
        notify_on_complete=notify_on_complete,
        notify_on_failure=notify_on_failure,
        notification_channel=notification_channel
    )

    # Save to PostgreSQL
    db_id = await save_workflow_to_db(spec)

    # Start Temporal workflow
    if spec.schedule_type == "immediate":
        handle = await client.start_workflow(
            CasseyWorkflow.run,
            args=[spec],
            id=f"workflow-{spec.workflow_id}",
            task_queue="cassey-workflows"
        )
    elif spec.schedule_type == "scheduled":
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

    return spec.workflow_id


@tool
async def list_workflows(status: str = None) -> str:
    """List your workflows.

    Args:
        status: Filter by 'active', 'paused', or 'archived'

    Returns:
        List of workflows with scheduling info.
    """
    workflows = await get_workflows_by_user(get_workspace_id(), status)

    if not workflows:
        return "No workflows found."

    lines = [f"{'ID':<10} {'Name':<25} {'Schedule':<20} {'Status'}"]
    lines.append("-" * 80)

    for wf in workflows:
        schedule = f"{wf['schedule_type']}"
        if wf.get('cron_expression'):
            schedule = f"{wf['cron_expression']}"
        elif wf.get('schedule_time'):
            schedule = f"{wf['schedule_time']}"
        lines.append(f"{wf['workflow_id']:<10} {wf['name']:<25} {schedule:<20} {wf['status']}")

    return "\n".join(lines)


@tool
async def cancel_workflow(workflow_id: str) -> str:
    """Cancel a workflow.

    Args:
        workflow_id: Workflow ID from create_workflow

    Returns:
        Cancellation status.
    """
    client = await Client.connect("temporal.vm2.internal:7233")
    handle = client.get_workflow_handle(f"workflow-{workflow_id}")
    await handle.cancel()

    await set_workflow_status(workflow_id, "paused")
    return f"Cancelled workflow {workflow_id}"
```

---

## Temporal Server Setup

### Docker Compose (Separate VM)

```yaml
# docker-compose.yml for Temporal VM
version: '3.8'

services:
  temporal:
    image: temporalio/auto-setup:1.21
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgres
      - NAMESPACES=default,cassey
    ports:
      - "7233:7233"
    depends_on:
      - postgres
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  temporal-web:
    image: temporalio/web:1.21
    environment:
      - TEMPORAL_GRPC_ENDPOINT=temporal:7233
    ports:
      - "8088:8088"
    depends_on:
      - temporal
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 128M

  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
      POSTGRES_DB: temporal
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Minimal VM Specs

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 1 vCPU | 2 vCPU |
| **RAM** | 1 GB | 2 GB |
| **Disk** | 10 GB | 20 GB |

**Cost:** ~$5-6/month (DigitalOcean basic droplet)

---

## Database Schema

### PostgreSQL Tables

```sql
-- Reminders (already exists)
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    thread_ids TEXT[] NOT NULL,
    message TEXT NOT NULL,
    due_time TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'pending',
    recurrence TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT
);

-- Workflows
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

    -- Scheduling
    schedule_type       VARCHAR(20) NOT NULL,
    schedule_time       TIMESTAMP,
    cron_expression     VARCHAR(100),

    -- Status
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'archived'))
);

CREATE INDEX idx_workflows_user ON workflows(user_id);
CREATE INDEX idx_workflows_status ON workflows(status);
```

### SQLite Tables (Per-Group)

```sql
-- Todos (in data/groups/{group_id}/db/db.sqlite)
CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_due_date ON todos(due_date);
```

---

## Temporal Worker (Runs in Cassey App)

```python
"""src/cassey/temporal_worker.py"""

import asyncio
from temporalio.worker import Worker
from temporalio.client import Client

async def run_temporal_worker():
    """Run the Temporal worker for Cassey reminders and workflows."""
    client = await Client.connect("temporal.vm2.internal:7233")

    worker = Worker(
        client,
        task_queue="cassey-reminders",
        workflows=[ReminderWorkflow],
        activities=[send_reminder_notification],
    )

    print("Temporal worker started for reminders...")
    await worker.run()


# In main.py, add:
# asyncio.create_task(run_temporal_worker())
```

---

## Implementation Timeline

| Phase | Tasks | Status |
|-------|-------|--------|
| **1. Reminders (Interim)** | APScheduler + PostgreSQL | ✅ Complete |
| **2. KB Infrastructure** | DuckDB + FTS + VSS | ✅ Complete |
| **3. Temporal Server** | Deploy on separate VM | ❌ Todo |
| **4. Temporal Worker** | Implement reminder workflows + activities | ❌ Todo |
| **5. Update Reminder Tools** | Use Temporal instead of APScheduler | ❌ Todo |
| **6. Todos Storage** | SQLite schema + CRUD | ❌ Todo |
| **7. Todo Tools** | Agent tools for todos | ❌ Todo |
| **8. Note Tools** | Dedicated note-taking tools | ❌ Todo |
| **9. Workflow Infrastructure** | WorkflowSpec, multi-step workflows | ❌ Todo |
| **10. Workflow Tools** | create_workflow, list_workflows, cancel_workflow | ❌ Todo |
| **11. Schema Registry** | Custom column support | ❌ Todo |
| **12. Tests** | Test all functionality | ⚠️ Partial |

---

## Summary

| Component | Storage | Scheduler | Status |
|-----------|---------|-----------|--------|
| **Reminders** | PostgreSQL | APScheduler → Temporal | ⚠️ Interim → 🎯 Planned |
| **Todos** | SQLite (per-group) | N/A | ❌ Not Started |
| **Notes** | DuckDB KB (per-group) | N/A | ⚠️ Partial |
| **Workflows** | PostgreSQL | Temporal (chains) | ❌ Not Started |

**Key points:**
1. **Temporal unifies scheduling** for both reminders and workflows
2. **APScheduler is interim** - can be deprecated/removed after Temporal is live
3. **No data migration needed** - same PostgreSQL schema
4. **Todos/Notes remain simple** - no Temporal complexity needed
5. **Workflows add power** - multi-step automation with executor chains
