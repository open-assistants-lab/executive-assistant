# Event-Driven Agent Invocation — Webhooks & File Watching

## Problem

Currently the agent can only be triggered via direct user messages (REST, SSE, WebSocket). There is no way for external events to trigger the agent asynchronously:

- A Slack message arrives → agent should respond
- An email arrives → agent should triage it
- A file changes locally → agent should process the change
- A GitHub webhook fires → agent should react

## Solution: Event Bus + Agent Invocation

A lightweight **event bus** that receives external events, transforms them into agent messages, and calls `run_sdk_agent_stream()`. Two event sources in v1: **webhooks** (external HTTP) and **file watcher** (local filesystem).

### Event Bus Architecture

```
External Event (Slack webhook, GitHub webhook, email)
    │
    ▼
HTTP Server ──→ POST /events/webhook/{source}
    │
    ▼
Event Registry ──→ maps {source} → handler
    │
    ▼
EventHandler ──→ transforms raw payload → Message.user(content)
    │
    ▼
run_sdk_agent_stream(user_id, messages, ...)
    │
    ▼
Result: agent processes event, may call tools, returns response
    │
    ▼
ResponseHandler ──→ sends response back to source (optional)
```

### Webhook Endpoint

```python
@router.post("/events/webhook/{source}")
async def handle_webhook(source: str, payload: dict, req: Request):
    """Receive an external webhook event and trigger the agent.
    
    Args:
        source: Registered webhook source ("slack", "github", "generic", etc.)
        payload: Raw webhook payload from the external service
    
    The webhook is authenticated via the source's secret (configured in data/private/webhooks.yaml)
    or via the API key header.
    """
```

**Configuration** (`data/private/webhooks.yaml`):
```yaml
sources:
  slack:
    secret: whsec_xxx
    user_id: default_user
    handler: slack
    prompt: "You received a Slack message. Process it and respond if appropriate."
  github:
    secret: whsec_yyy
    user_id: default_user
    handler: github
    prompt: "A GitHub event occurred. Review and respond if action is needed."
```

**Built-in handlers:** Generic (pass raw payload as message), Slack (parse text from message event), GitHub (summarize PR/issue event).

**Authentication:** HMAC signature verification (`req.headers["X-Hub-Signature-256"]`) or shared secret header, configured per source.

### File Watcher

A lightweight directory watcher that triggers the agent on file changes:

```python
class FileWatcher:
    """Watch a directory for file changes and trigger the agent."""

    def __init__(self, watch_dir: Path, user_id: str, patterns: list[str] | None = None):
        self.watch_dir = watch_dir
        self.user_id = user_id
        self.patterns = patterns or ["*"]
        self._last_mtimes: dict[str, float] = {}

    async def poll(self, interval: float = 5.0):
        """Poll for file changes every `interval` seconds."""
        while True:
            changed = self._check_changes()
            for file_path, change_type in changed:
                await self._trigger_agent(file_path, change_type)
            await asyncio.sleep(interval)

    def _check_changes(self) -> list[tuple[Path, str]]:
        """Check for new, modified, or deleted files."""
        ...

    async def _trigger_agent(self, file_path: Path, change_type: str):
        """Send a message to the agent about the file change."""
        msg = f"File changed: {file_path} ({change_type}). Review and take appropriate action."
        messages = [Message.user(msg)]
        async for chunk in run_sdk_agent_stream(self.user_id, messages):
            # Stream results to a log or configured output
            ...
```

**Configuration** (`data/private/file_watch.yaml`):
```yaml
watches:
  - dir: ~/Downloads
    patterns: ["*.pdf", "*.csv"]
    user_id: default_user
    prompt: "A new file was added to Downloads. Process it automatically."
    poll_interval: 10
  - dir: ~/Documents/Inbox
    patterns: ["*"]
    user_id: default_user
    prompt: "A file was added to your Inbox. Handle it according to my workflow."
```

**Change detection:** Simple polling with `os.path.getmtime()` checks. No inotify/FSEvents dependency for v1 (cross-platform simplicity). Files are tracked in a small SQLite DB at `data/private/file_watch_state.db` to persist across restarts.

### Agent System Prompt Context

When triggered by an event, the agent receives a system prompt block describing the event source:

```
This message was triggered by an external event:
  Source: slack
  Event: message received
  Context: You are responding to a Slack message in #general channel

You have access to all your normal tools. If this is a webhook from a service
you have connectors for (Slack, Gmail, etc.), use the connector tools to respond.
```

### Response Handling

Different event sources need different response patterns:

| Source | Response behavior |
|--------|------------------|
| **generic** | Response is logged to `data/logs/webhook_responses/` |
| **slack** | (Future) If Slack connector is connected, response is posted to the thread via connector tool |
| **github** | (Future) Comment on the relevant PR/issue via connector tool |
| **email** | (Future) Reply via Gmail connector tool |
| **file_watch** | Response is logged, file action summary is sent to configured notification channel |

### Security

- Webhook secrets stored in `data/private/webhooks.yaml` (not versioned)
- HMAC verification for GitHub-style webhooks, shared secret header for others
- Rate limiting: max 10 events/minute per source
- Agent invocation scoped to the configured `user_id` — uses that user's tools, connectors, and skills
- No destructive tool auto-approval for webhook-triggered events (always interrupt)

### Implementation Plan

1. `src/http/routers/events.py` — `POST /events/webhook/{source}`, payload parsing, auth verification, handler dispatch
2. `src/events/handlers.py` — `EventHandler` base class + built-in handlers (generic, slack, github)
3. `src/events/file_watcher.py` — `FileWatcher` class with polling + change detection
4. `src/events/config.py` — load `webhooks.yaml` and `file_watch.yaml` configs
5. `src/__main__.py` — `ea watch` subcommand to start file watcher
6. Tests in `tests/events/`