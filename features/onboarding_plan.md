# Onboarding Plan (Inspired by Moltbot)

## Goal
Provide a guided, low-friction onboarding flow that sets up channels, models, storage, and safety defaults, and validates the install with a diagnostic check.

## Core Principles
- **Wizard-first**: one command to get a working assistant.
- **Safe by default**: allowlist + pairing on channels.
- **Validate early**: run diagnostics before the first real use.

## UX Flow
1) **Welcome + prerequisites**
   - Check Python env + required services
   - Verify API keys present (LLM + optional tools)

2) **Model selection**
   - Choose provider (OpenAI/Anthropic/etc.)
   - Set default + fast models

3) **Channel setup**
   - Telegram (token + allowlist)
   - Optional HTTP channel
   - Optional future channels (Slack/Discord)

4) **Storage setup**
   - Confirm data directories
   - Initialize DBs (TDB/VDB/memory)

5) **Safety defaults**
   - Enable allowlist
   - Pairing / DM-only policy for new contacts

6) **Test run**
   - Send a message to verify end-to-end
   - Run `doctor` checks

## CLI Commands
- `exec_assistant onboard` — guided setup
- `exec_assistant doctor` — diagnostics + repair hints
- `exec_assistant status` — show configured channels/models/tools

## Implementation Steps
1) Add a CLI wizard (prompt users for config + write to `.env` / config file)
2) Add a `doctor` command (validate env, DBs, channel connectivity)
3) Add a simple sample workflow test
4) Add docs + quickstart
5) Auto-trigger onboarding when no memory exists (e.g., after `/reset mem`)

## Success Criteria
- New user can go from empty repo → working assistant in <10 minutes
- Issues are detected early with actionable errors
- Safer defaults for messaging channels
- Missing memory triggers onboarding to re-establish preferences
