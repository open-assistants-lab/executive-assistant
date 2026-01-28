# User-Specific Skills Plan

## Goal
Enable agents to create and load user-owned skills on demand, without restart. User skills are private to the user (thread context) and should reduce token cost by keeping system prompts lean.

## Non-Goals
- Replacing flows (flows remain for scheduling/orchestration)
- Sharing skills across users/tenants
- Global registry reload on every request

## Current State
- Skills live in markdown files and are loaded at startup into a global SkillsRegistry.
- `load_skill` returns cached content from the registry (no disk lookup).
- Thread context is available via `thread_storage.get_thread_id()`.

## Proposed Features

### 1) User-Owned Skills Storage
- Location: `data/users/{thread_id}/skills/on_demand/*.md`
- Format: same skill markdown schema (Title, Description, Tags, content).
- Ownership: by `thread_id`; no shared scope access.

### 2) Create User Skill Tool
Add a tool (e.g. `create_user_skill`) that:
- Validates `skill_name` (safe filename, normalized)
- Writes a markdown file to the user skills directory
- Includes metadata (author, created_at, tags)
- Returns a confirmation + canonical skill name

Optional: require `confirm_request` before writing.

### 3) Hot-Load Without Restart
Enhance `load_skill` to:
- Check user skills path first (thread-specific)
- If found, parse and return content immediately
- Else, fallback to global registry (system/admin skills)

Optional: file mtime cache per thread to avoid repeated reads.

### 4) Observer → Evolve Pipeline (from Instincts)
Introduce a pipeline that turns user instincts into stable, reusable skills:
- **Observer** captures atomic behavior patterns (instincts) during sessions.
- **Evolve** clusters related instincts into a draft user skill.
- **Approve (HITL)** user reviews and explicitly confirms the new skill before saving.

This keeps skills curated and reduces noise from raw observations.

## Implementation Plan

### A) Storage + Parsing
- Reuse `_parse_skill_file` from `skills/loader.py` (or extract into reusable helper)
- Add a helper to parse a single markdown file into a `Skill`

### B) Creation Tool
- Implement `create_user_skill(name, description, tags, content)`
- Write file under `data/users/{thread_id}/skills/on_demand/`
- Normalize name to `snake_case` and use as filename

### C) Load Skill Tool Changes
- In `load_skill`, resolve thread context
- If user skill exists → parse + return content
- Else → existing registry lookup

### D) (Optional) Management Commands
- `/skill list` for user skills
- `/skill create` for admin/debug usage

### E) Evolve Integration (from Instincts)
- Add a periodic or on-demand evolve job.
- Cluster instincts by domain/trigger similarity.
- Generate a draft skill and require confirmation before write.

## Safety + Validation
- Validate identifiers and filenames (no path traversal)
- Limit max skill size (e.g., 50KB) to avoid prompt abuse
- Store author + timestamp for auditing

## Tradeoffs
- User skills won’t appear in global available list unless a per-user list command is added.
- Slight disk I/O when loading user skills, mitigated by caching.
- Skills remain guidance, not guaranteed execution like flows.

## Rollout Steps
1. Add file parser helper for single skill
2. Add `create_user_skill` tool
3. Update `load_skill` with user-skill lookup
4. Add per-user listing (optional)
5. Smoke test creation + immediate load without restart

## Success Criteria
- User can request “save this as a skill” and get a persistent, private skill.
- `load_skill` can load the newly created skill in the same session without restart.
- No impact on system/admin skills loading.
