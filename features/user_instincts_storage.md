# User Instincts Storage Spec (Single File per User)

## Goal
Store all instincts for a user in a single file to keep storage simple and portable while supporting confidence updates and compaction.

## Storage Location
- Path: `data/users/{thread_id}/instincts/instincts.jsonl`
- Snapshot: `data/users/{thread_id}/instincts/instincts.snapshot.json` (optional, for compaction)

## File Format
### A) Append-only event log (preferred)
Each line is a JSON object representing an “instinct event.”

Event types:
- `create` — new instinct
- `confirm` — confidence up
- `contradict` — confidence down
- `decay` — scheduled/periodic decay
- `disable` / `enable` — user control
- `delete` — removal

Example JSONL lines:
```json
{"event":"create","id":"prefer-json-output","trigger":"user asks for export","action":"return JSON output","confidence":0.5,"domain":"format","source":"session-observation","evidence":"user corrected output format","ts":"2026-01-28T10:15:00Z"}
{"event":"confirm","id":"prefer-json-output","delta":0.05,"ts":"2026-01-29T11:10:00Z"}
```

### B) Snapshot file (optional)
A single JSON object keyed by instinct id with the current resolved state.

Example:
```json
{
  "prefer-json-output": {
    "id": "prefer-json-output",
    "trigger": "user asks for export",
    "action": "return JSON output",
    "confidence": 0.55,
    "domain": "format",
    "source": "session-observation",
    "evidence": ["user corrected output format"],
    "last_updated": "2026-01-29T11:10:00Z",
    "status": "enabled"
  }
}
```

## Read Strategy
- Load snapshot if present for fast startup
- Replay JSONL events after snapshot timestamp to reach current state
- If no snapshot, replay full JSONL (bounded by size policy)

## Write Strategy
- Append events to JSONL (atomic append)
- Periodically compact into snapshot (e.g., every N events or daily)
- Snapshot write should be atomic (write temp + rename)

## Concurrency & Integrity
- Use file lock when writing JSONL
- Validate JSON schema per event
- Ignore malformed lines but log them

## Confidence Model
- Initial confidence: 0.3–0.85 based on observation count
- Confirm: +0.05
- Contradict: -0.1
- Decay: -0.02/week
- Delete threshold: <0.2

## Size Management
- JSONL max size (e.g., 5–10 MB)
- Auto-compaction into snapshot and truncate JSONL

## Exports
- `/instincts export` returns snapshot JSON
- `/instincts import` appends `create` events with `source="import"`

## Success Criteria
- Single file per user is sufficient for daily use
- Fast reads via snapshot + delta replay
- Safe concurrent updates and compaction

## What Are Instincts?
Instincts are small, atomic behavior rules the assistant learns over time (trigger → action) with confidence scoring.

## Instincts vs Memory
- Memory stores facts and information (what is true).
- Instincts influence behavior (what to do when X happens).

## Examples
**Memory (facts):**
- "User prefers emails on weekdays only."
- "Project deadline is 2026-03-15."

**Instincts (behavior rules):**
- Trigger: "User asks for an export" → Action: "Return JSON format by default."
- Trigger: "User requests a plan" → Action: "Ask for scope and constraints first."
