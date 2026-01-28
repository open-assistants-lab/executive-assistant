# User-Specific Prompt Plan

## Goal
Allow each user to set a private system prompt that is applied without restart and does not inflate global prompt costs.

## Scope
- Per-user prompt only (thread-scoped)
- Optional and minimal by default
- Applied at runtime without restarting the agent

## UX
- `/prompt set <text>` — save a user prompt
- `/prompt show` — display current prompt
- `/prompt clear` — remove user prompt
- `/prompt append <text>` — optional

## Storage Model
- Path: `data/users/{thread_id}/prompts/prompt.md`
- Format: plain markdown or text
- Enforce size cap (e.g., 1–2k characters) to control token cost

## Merge Order
- Admin prompt
- Base system prompt
- User prompt
- Channel appendix

## Runtime Behavior
- Load user prompt dynamically per request
- Cache per thread with mtime check (optional)
- If missing or empty, skip entirely

## Safety
- Don’t allow user prompt to override system safety policies
- Add lint step (strip null bytes, normalize whitespace)

## Implementation Steps
1) Add `user_prompt_storage.py` helpers (read/write/clear)
2) Add `/prompt` management commands
3) Update prompt assembly to include user prompt at runtime
4) Add size + content validation
5) Add tests for merge order and empty prompt

## Success Criteria
- User can set/clear prompt via command
- Prompt is applied immediately without restart
- System prompt remains lean and stable
