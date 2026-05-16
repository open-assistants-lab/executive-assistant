# Gmail via gws CLI

Use the `gws` CLI to read, send, and search Gmail. All output is structured JSON.

## Authentication (one-time)

```bash
export GOOGLE_WORKSPACE_CLI_CLIENT_ID="<configured in EA settings>"
export GOOGLE_WORKSPACE_CLI_CLIENT_SECRET="<configured in EA settings>"
gws auth login
# Opens browser → approve → token stored in ~/.config/gws/
```

## Read Emails

```bash
# List recent messages
gws gmail messages list --format json

# Filter: only unread
gws gmail messages list --filter "is:unread" --format json

# Filter: from a specific person
gws gmail messages list --filter "from:alice@example.com" --format json

# Get a specific message by ID
gws gmail messages get --message-id MESSAGE_ID --format json
```

## Search Emails

```bash
# Keyword search
gws gmail messages list --filter "budget report" --format json

# Recent from specific sender
gws gmail messages list --filter "from:boss newer_than:7d" --format json
```

## Send Email

```bash
gws gmail +send --to alice@example.com --cc bob@example.com --subject "Meeting notes" --body "Here are the notes from today"
```

## Reply

```bash
gws gmail +reply --message-id MESSAGE_ID --body "Thanks, got it."
```

## Triage (Quick Inbox Summary)

```bash
gws gmail +triage
# Shows: unread count, sender, subject, date for each unread message
```

## Sync to Local Store

```bash
# EA syncs automatically every 15 minutes
# Force a manual sync:
curl -X POST http://localhost:8080/emails/sync?provider=gmail
```

## Tips

- Always use `--format json` for machine-readable output
- Use `--page-all` to fetch all results (beware: large mailboxes)
- The `+send`, `+reply`, `+triage` helpers are hand-crafted for common workflows
- Messages are stored locally in HybridDB (FTS5 + ChromaDB) for offline search
