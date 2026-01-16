# Event System Design

## Concept

Event-triggered job execution alongside time-triggered scheduling. Jobs can be run by:
- **Scheduler** (time-based): "Run at 9am daily"
- **Events** (trigger-based): "Run when webhook received / file changed / command given"

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Job Execution Layer (Unified)              │
│  - execute_job(job_id, trigger_source)                 │
│  - Same execution path for all triggers                 │
└─────────────────────────────────────────────────────────┘
         ▲                                    │
         │                                    │
┌────────────────────┐              ┌─────────────────┐
│  Time Triggers     │              │  Event Triggers  │
│  - Scheduler (60s) │              │  - Webhooks      │
│  - due_time check  │              │  - File watcher  │
│                    │              │  - Chat commands │
└────────────────────┘              │  - Manual trigger │
                                     │  - Job completion │
                                     └─────────────────┘
```

## Event Sources

| Event Type | How to Trigger | Implementation | Extra Lib? |
|------------|----------------|-----------------|-----------|
| **Webhook** | HTTP POST to endpoint | FastAPI route → execute_job() | No |
| **File watch** | File created/changed | Check mtime in 60s loop | No |
| **Chat command** | User says "run job now" | Agent calls run_job() tool | No |
| **Database** | Row inserted/updated | App-level callback | No |
| **Manual** | Direct API/tool call | run_job(job_id) tool | No |
| **Job completion** | Job finishes → chain next | Scheduler creates next instance | No |

**Total extra dependencies: 0**

## Database Note

**DuckDB does NOT have NOTIFY** (PostgreSQL feature). DuckDB is embedded, no pub/sub mechanism.

For database-triggered events, use application-level polling or callbacks instead.

## File Watcher Implementation

### Option A: `watchdog` library
```python
pip install watchdog  # ~100KB, pure Python
```
- Uses OS native file events (inotify/FSEvents)
- Near-zero CPU when idle
- Well-tested, cross-platform

### Option B: Custom polling (CHOSEN)
```python
# Add to scheduler's 60s loop - no new dependency!
async def _check_file_triggers():
    for job in watched_jobs:
        if file_modified_since_last_check(job):
            await execute_job(job.id, trigger_source='file_watch')
```

**Why Option B:**
- No extra dependency
- Scheduler already polls every 60s
- File check is cheap (stat() call)
- Latency: ~60s max (acceptable per requirements)

## Core Function (Shared Entry Point)

```python
async def execute_job(job_id: int, trigger_source: str):
    """Execute a scheduled job immediately.

    Args:
        job_id: The job to run
        trigger_source: 'scheduler' | 'webhook' | 'file_watch' | 'manual' | 'completion'
    """
    job = await storage.get_job(job_id)

    # Set thread_id context for sandbox
    set_thread_id(job.thread_id)

    # Execute script in sandbox
    result = await run_job_script(job.script_path, job.thread_id)

    # Check for message file → send to Telegram
    await send_job_output_if_exists(job)

    # Handle recurrence if needed
    if job.recurrence and trigger_source == 'scheduler':
        await schedule_next_instance(job)

    # Handle chaining (if job has depends_on_this)
    await trigger_dependent_jobs(job.id)

    return result
```

## Webhook Endpoint

```python
@app.post("/webhook/{job_id}")
async def webhook_trigger(job_id: int, secret: str = None):
    """Trigger a job via webhook."""
    # Optional: verify secret for security
    job = await storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = await execute_job(job_id, trigger_source='webhook')
    return {"status": "triggered", "result": result}
```

## Manual Trigger Tool

```python
@tool
def run_job(job_id: int) -> str:
    """Execute a scheduled job immediately without waiting for its scheduled time.

    Useful for:
    - Testing jobs before scheduling
    - Manual re-run of failed jobs
    - On-demand execution

    Args:
        job_id: The ID of the job to run

    Returns:
        Job execution result
    """
    # Calls execute_job() synchronously
```

## File Watcher Implementation (No New Lib)

```python
# In scheduler.py, add to the 60s loop
_file_mtimes = {}  # Cache last seen mtimes

async def _check_file_triggers():
    """Check for file modifications on watched jobs."""
    watched = await storage.get_watched_jobs()

    for job in watched:
        file_path = get_job_file_path(job)

        if not file_path.exists():
            continue

        current_mtime = file_path.stat().st_mtime
        last_mtime = _file_mtimes.get(job.id)

        if last_mtime is None:
            _file_mtimes[job.id] = current_mtime
        elif current_mtime > last_mtime:
            # File was modified!
            _file_mtimes[job.id] = current_mtime
            await execute_job(job.id, trigger_source='file_watch')
```

## Job Chaining

Jobs can trigger other jobs on completion:

```sql
ALTER TABLE scheduled_jobs ADD COLUMN triggers_on_completion INTEGER[];
```

```python
# After job completes, trigger its children
async def trigger_dependent_jobs(parent_job_id: int):
    children = await storage.get_jobs_that_trigger_on(parent_job_id)
    for child in children:
        await execute_job(child.id, trigger_source='completion')
```

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Webhook abuse** | Optional secret parameter, rate limiting |
| **Unauthorized execution** | Check job belongs to user_id making request |
| **File watch loops** | Don't re-trigger if job modified the file itself |
| **Resource exhaustion** | Job queue, max concurrent jobs |

## Resource Impact

| Component | CPU | Memory | Dependencies |
|-----------|-----|--------|--------------|
| Webhook handling | Minimal (per request) | Minimal | None (FastAPI exists) |
| File watching (polling) | Negligible (stat() calls) | ~100 bytes for mtime cache | None |
| Job execution | Same as scheduled jobs | Same as scheduled jobs | None |
| **Total** | **Negligible** | **~100 bytes** | **0 new libs** |

## Implementation Order

1. **Phase 1**: Time-based scheduler (original plan)
2. **Phase 2**: Add `execute_job()` unified function
3. **Phase 3**: Add manual trigger tool + webhook endpoint
4. **Phase 4**: Add file watcher (60s poll)
5. **Phase 5**: Add job chaining (triggers_on_completion)

## Status

**Design complete.** Implementation pending after Phase 1 (time-based scheduler) is complete.
