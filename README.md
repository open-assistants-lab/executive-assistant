# Executive Assistant

A production-grade personal agent built on Deep Agents SDK with multi-LLM support, designed for deployment via Docker for teams.

**Name your agent** via `AGENT_NAME` in your config - defaults to "Executive Assistant".

## Features

- **Deep Agents SDK Integration**
  - Task planning with todo lists
  - Virtual filesystem with user isolation
  - Subagent spawning for context isolation
  - Postgres checkpoints for thread persistence
  - Web tools (Tavily/Firecrawl search, scrape, crawl, map)
  - Human-in-the-loop support

- **17+ LLM Providers** with tool-calling support
  - OpenAI, Anthropic, Google Gemini, Azure OpenAI
  - Groq, Mistral, Cohere, Together AI, Fireworks
  - DeepSeek, xAI (Grok)
  - Ollama (local/cloud), OpenRouter
  - Minimax, Qwen (Alibaba), Zhipu AI (GLM)
  - HuggingFace

- **User-Isolated Storage**
  - `/user/` - Private user data (memories, projects, notes)
  - `/shared/` - Team-shared resources (skills, knowledge)
  - CompositeBackend with FilesystemBackend (virtual_mode=True)

- **Production Ready**
  - PostgreSQL for agent checkpoints
  - Docker deployment
  - Langfuse observability (optional)

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Copy and configure environment
cp .env.example .env

# Start Postgres (Docker)
docker run -d --name ea-postgres \
    -e POSTGRES_USER=ea \
    -e POSTGRES_PASSWORD=testpassword123 \
    -e POSTGRES_DB=ea_db \
    -p 5432:5432 \
    postgres:16-alpine

# Create data directory
mkdir -p data/users data/shared/skills

# Run development server
uv run uvicorn src.api.main:app --reload
```

## Filesystem Architecture

### Host Machine
```
data/                           # DATA_PATH
├── config.yaml                 # App-level configuration
├── shared/                     # Team resources
│   ├── .mcp.json               # Team MCP servers
│   ├── skills/                 # Admin-managed skills
│   └── knowledge/              # Shared knowledge base
└── users/
    └── {user_id}/              # User-isolated data
        ├── .memory/            # Memory DB (SQLite + FTS5 + vec)
        ├── .journal/           # Journal DB
        ├── .vault/             # Encrypted secrets vault
        ├── skills/             # User-specific skills
        ├── .mcp.json           # User MCP servers
        └── projects/           # User project files
```

### Agent Virtual Paths
```
/user/          →  data/users/{user_id}/      (user's private data)
/shared/        →  data/shared/               (team resources)
/workspace/     →  StateBackend               (ephemeral, per-thread)
```

## CLI Commands

```bash
# Single message to your Executive Assistant
uv run ea message "What is LangGraph?"

# Interactive conversation
uv run ea interactive

# With specific user/thread
uv run ea message "Hello" --user user-123 --thread my-thread

# Show configuration
uv run ea config

# List LLM providers
uv run ea models

# Start API server
uv run ea serve --port 8000

# Start Telegram bot
uv run ea telegram

# Start ACP server for IDE integration
uv run ea acp
```

## Configuration

```bash
# .env

# Name your Executive Assistant
AGENT_NAME=Executive Assistant

# Default model (format: provider/model-name)
# Fast examples: openai/gpt-5-nano, anthropic/claude-haiku-4-5, google/gemini-2.5-flash-lite, groq/openai/gpt-oss-20b
DEFAULT_MODEL=ollama/qwen3-coder-next

# Database for checkpoints
DATABASE_URL=postgresql://ea:password@localhost:5432/ea_db

# Data path
DATA_PATH=/data

# Search (Tavily OR Firecrawl - pick one)
TAVILY_API_KEY=tvly-...
# OR
FIRECRAWL_API_KEY=...
FIRECRAWL_BASE_URL=https://api.firecrawl.dev/v1

# Ollama Cloud
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your-key
```

## API Endpoints

### Send Message
```bash
POST /api/v1/message
{
  "message": "Research LangGraph and save summary to /user/projects/",
  "user_id": "user-123",
  "thread_id": "optional-thread-id"
}
```

### Streaming
```bash
POST /api/v1/message/stream
{
  "message": "Write a Python script",
  "stream": true
}
```

### Summarize (utility)
```bash
POST /api/v1/summarize
{
  "text": "Long text to summarize...",
  "max_length": 200
}
```

## Skills

Skills use `SKILL.md` files with frontmatter:

```markdown
---
name: coding
description: Software development tasks
version: 1.0.0
---

# Coding Skill

Instructions for coding tasks...
```

Skill locations:
- `/data/shared/skills/` - Team skills (admin-managed)
- `/data/users/{user_id}/skills/` - User skills

## Docker

```yaml
# docker-compose.yml
services:
  ea:
    build: .
    volumes:
      - ./data:/data
    environment:
      - DATABASE_URL=postgresql://ea:password@postgres:5432/ea_db
      - AGENT_NAME=Executive Assistant
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ea
      POSTGRES_PASSWORD: password
      POSTGRES_DB: ea_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Project Structure

```
executive-assistant/
├── src/
│   ├── agent/            # Deep Agents factory
│   ├── middleware/       # Custom middleware
│   ├── memory/           # Memory DB interface
│   ├── skills/           # Built-in skills
│   ├── acp/              # ACP server for IDE
│   ├── config/           # Pydantic settings
│   ├── llm/              # 17+ LLM providers
│   ├── api/              # FastAPI endpoints
│   ├── telegram/         # Telegram bot
│   └── cli/              # Typer CLI
├── docs/
│   └── API_CONTRACT.md   # API contract for desktop app
├── data/                 # Persistent data (gitignored)
│   ├── shared/
│   └── users/
└── docker/
```

## Development

```bash
make test          # Run tests
make lint format   # Lint and format
make typecheck     # Type check
```

## License

MIT
