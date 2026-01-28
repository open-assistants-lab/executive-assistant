# LangGraph Studio Setup

## Overview

Executive Assistant can now be debugged and visualized using [LangGraph Studio](https://github.com/langchain-ai/langgraph-studio), a visual debugging tool for LangGraph applications.

## What Was Implemented

### New Files

| File | Purpose |
|------|---------|
| `langgraph.json` | LangGraph Studio configuration file |
| `src/executive_assistant/dev_server.py` | Dev server entry point for Studio |

### Modified Files

| File | Changes |
|------|---------|
| `pyproject.toml` | Added LangGraph dev dependencies |
| `src/executive_assistant/dev_server.py` | Fixed `AGENT_SYSTEM_PROMPT` import error |

## Changes Detail

### `src/executive_assistant/dev_server.py` Fix

**Problem**: Code referenced `settings.AGENT_SYSTEM_PROMPT` which doesn't exist in Settings class.

**Solution**: Changed to use `DEFAULT_SYSTEM_PROMPT` from `executive_assistant.config.constants`.

```python
# Before:
from executive_assistant.config import create_model, settings
system_prompt=settings.AGENT_SYSTEM_PROMPT,

# After:
from executive_assistant.config import create_model
from executive_assistant.config.constants import DEFAULT_SYSTEM_PROMPT
system_prompt=DEFAULT_SYSTEM_PROMPT,
```

## Usage

### Starting the Dev Server

```bash
# Use the langgraph CLI (this is the current working entrypoint)
langgraph dev
```

Note: When you restart Executive Assistant for testing, also restart `langgraph dev` so Studio reflects the latest graph.

### Runtime Selection

Studio now respects `AGENT_RUNTIME` from `docker/.env`:
- `AGENT_RUNTIME=langchain` (default) shows the LangChain agent runtime
- `AGENT_RUNTIME=custom` shows the existing custom LangGraph graph

### Accessing LangGraph Studio

1. Open Studio at: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
2. API endpoint: http://127.0.0.1:2024

### Features Available in Studio

- Visual graph representation
- Create new threads
- Send messages and trace execution
- Inspect state at each step
- Debug tool calls
- View checkpoint history

## Dependencies Added

```toml
langchain-core>=1.2.0
langgraph>=1.0.6
langgraph-api>=0.6.0
langgraph-checkpoint>=4.0.0
langgraph-cli>=0.4.0
langgraph-runtime-inmem>=0.22.0
```

Note: These are currently listed as project dependencies (not dev-only).

## Impact Assessment

**Does this affect Executive Assistant's regular operation?**

**No.** These changes only affect the LangGraph Studio dev server.

- The main Executive Assistant application (Telegram bot, HTTP server) does NOT use `dev_server.py`
- Production code uses different entry points in `src/executive_assistant/main.py`
- `dev_server.py` is ONLY used when running `langgraph dev` for local debugging

## Executive Assistant Runtime Entrypoint

For normal operation (Telegram/HTTP/etc), the console script `executive_assistant` points to:

- `src/executive_assistant/main.py:run_main`

This is the central entrypoint that instantiates channels based on `EXECUTIVE_ASSISTANT_CHANNELS`
(e.g., `telegram`, `http`, and future channels like email). It is not tied to Telegram;
Telegram is just the default if `EXECUTIVE_ASSISTANT_CHANNELS` is not set.

## Configuration

### `langgraph.json`

```json
{
  "dependencies": ["."],
  "graphs": {
    "executive_assistant": {
      "path": "src.executive_assistant.dev_server:get_graph",
      "title": "Executive Assistant AI Agent",
      "description": "Multi-channel ReAct agent with memory, KB, and tools"
    }
  },
  "env": "docker/.env"
}
```

## Notes

- Uses `MemorySaver` for in-memory checkpointing (non-persistent)
- Server auto-reloads on file changes
- Runs on port 2024 by default
