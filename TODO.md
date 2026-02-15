# Executive Assistant - Implementation TODO

Tracking implementation progress for the Executive Assistant deep agent.

---

## ✅ Completed

### Core Infrastructure
- [x] Project structure (`pyproject.toml`, `Makefile`, `Dockerfile`)
- [x] Pydantic settings with environment variables
- [x] PostgreSQL connection manager
- [x] User storage system (`UserStorage`)
- [x] Configurable agent name (`AGENT_NAME` in config)

### LLM Providers (17/23)
- [x] OpenAI
- [x] Anthropic
- [x] Google (Gemini)
- [x] Azure OpenAI
- [x] Groq
- [x] Mistral
- [x] Cohere
- [x] Together AI
- [x] Fireworks
- [x] DeepSeek
- [x] xAI (Grok)
- [x] HuggingFace
- [x] OpenRouter
- [x] Ollama (local + cloud)
- [x] Minimax
- [x] Qwen (Alibaba)
- [x] Zhipu AI (GLM)
- [ ] AWS Bedrock (pending)
- [ ] NVIDIA NIM (pending)
- [ ] Databricks (pending)
- [ ] IBM Watsonx (pending)
- [ ] Llama.cpp (pending)

### Observability
- [x] Langfuse integration (`src/observability/langfuse.py`)

### Deep Agents Integration
- [x] Agent factory with Postgres checkpoints
- [x] CompositeBackend with FilesystemBackend
- [x] User-isolated storage (`/user/`, `/shared/`)
- [x] System prompts for Ken

### Web Tools
- [x] Tavily web search
- [x] Firecrawl scrape (custom URL support)
- [x] Firecrawl crawl
- [x] Firecrawl map
- [x] Firecrawl search (fallback if no Tavily)

### Built-in Skills
- [x] Coding skill (`src/skills/coding/`)
- [x] Research skill (`src/skills/research/`)
- [x] Writing skill (`src/skills/writing/`)

### API & Interfaces
- [x] FastAPI application with lifespan
- [x] Health endpoints (`/health`, `/health/ready`)
- [x] Message endpoints (`/message`, `/message/stream`)
- [x] Summarize endpoint (`/summarize`)
- [x] Telegram bot (deep agent only, removed simple mode)
- [x] CLI with Typer (`ken message`, `ken interactive`, `ken serve`)
- [x] ACP server for IDE integration
- [x] Consolidated to deep agent only (removed simple LLM endpoints)

### Configuration
- [x] `.env.example` with all options
- [x] Firecrawl base URL configuration
- [x] Ollama cloud API key support

---

## 🚧 In Progress

### Memory System
- [x] MemoryDB interface and stub implementation
- [ ] SQLite + FTS5 + sqlite-vec setup
- [ ] Memory DB schema (semantic, episodic, procedural)
- [ ] Memory tools (add/update/search/forget)
- [ ] Memory import/export

### Middleware
- [x] MemoryContextMiddleware
- [x] MemoryLearningMiddleware
- [x] LoggingMiddleware
- [x] CheckinMiddleware
- [x] RateLimitMiddleware
- [x] MemoryDB stub (in-memory, for development)

---

## 📋 Pending

### Week 1-2: Memory & Personal Tools
- [ ] Memory system implementation
  - [ ] `.memory/memory.db` with FTS5 + vec
  - [ ] Local embedding model (all-MiniLM-L6-v2)
  - [ ] MemoryContextMiddleware (inject into prompts)
  - [ ] MemoryLearningMiddleware (auto-extract)
  - [ ] Memory tools: add, update, search, forget, export, import
- [ ] Journal system
  - [ ] `.journal/journal.db` with FTS5 + vec
  - [ ] Roll-up tables (hourly, daily, weekly, monthly, yearly)
  - [ ] Automatic roll-up jobs
- [ ] Personal tools
  - [ ] Todo CRUD
  - [ ] Reminder CRUD
  - [ ] Note CRUD
  - [ ] Bookmark CRUD
  - [ ] Password vault (encrypted)

### Week 2-3: MCP & Middleware
- [ ] MCP client integration
  - [ ] Stateful session support
  - [ ] Shared MCP config (`/data/shared/.mcp.json`)
  - [ ] User MCP config (`/data/users/{user_id}/.mcp.json`)
  - [ ] MCP test endpoint
- [ ] Additional middleware
  - [ ] LoggingMiddleware
  - [ ] CheckinMiddleware
  - [ ] RateLimitMiddleware
  - [ ] HumanInTheLoopMiddleware (for skill confirmation)

### Week 3-4: API & Check-in
- [ ] API endpoints per contract
  - [ ] Thread management (status, runs, cancel)
  - [ ] Memory endpoints
  - [ ] Journal endpoints
  - [ ] Todo/Reminder/Note endpoints
  - [ ] Password endpoints
  - [ ] Bookmark endpoints
  - [ ] MCP management endpoints
  - [ ] Skill management endpoints
  - [ ] Config endpoints
- [ ] Check-in service
  - [ ] Periodic check-in logic
  - [ ] Configurable checklist
  - [ ] Active hours support

### Week 4: Skills Evolution
- [ ] Instinct extraction from conversations
- [ ] Confidence scoring
- [ ] Instinct clustering
- [ ] Skill generation (with HITL approval)
- [ ] Skill import/export

### Future
- [ ] Desktop app (Tauri) - separate repo
- [ ] Additional LLM providers (Bedrock, NVIDIA, etc.)
- [ ] Calendar integration (OAuth)
- [ ] Email integration (OAuth)
- [ ] Contact integration (OAuth)

---

## 📁 Folder Structure (Target)

```
data/
├── config.yaml              # App-level configuration
├── logs/                    # Audit logs
│   └── agent-{date}.jsonl
├── shared/
│   ├── .mcp.json           # Team MCP servers
│   ├── skills/             # Team skills
│   └── knowledge/          # Shared knowledge
└── users/
    └── {user_id}/
        ├── .memory/
        │   └── memory.db   # SQLite + FTS5 + vec
        ├── .journal/
        │   └── journal.db  # SQLite + FTS5 + vec
        ├── .vault/
        │   └── vault.db    # Encrypted SQLite
        ├── skills/         # User skills
        ├── .mcp.json       # User MCP servers
        └── projects/       # User project files
```

---

## 🔧 Middleware Stack

### Built-in (from LangChain/deepagents)
| Middleware | Status | Notes |
|------------|--------|-------|
| TodoListMiddleware | ✅ | Included in deepagents |
| FilesystemMiddleware | ✅ | Included in deepagents |
| SummarizationMiddleware | ✅ | Included in deepagents |
| SubagentMiddleware | ✅ | Included in deepagents |
| HumanInTheLoopMiddleware | 📋 | For skill confirmation |
| ToolRetryMiddleware | 📋 | Retry failed tools |

### Custom (Ken-specific)
| Middleware | Status | Purpose |
|------------|--------|---------|
| MemoryContextMiddleware | ✅ | Inject memories into prompts |
| MemoryLearningMiddleware | ✅ | Auto-extract memories |
| LoggingMiddleware | ✅ | Audit all actions |
| CheckinMiddleware | ✅ | Periodic check-in |
| RateLimitMiddleware | ✅ | Rate limit requests |

---

## 📚 Documentation

- [x] `README.md` - Project overview
- [x] `AGENTS.md` - AI agent guidelines
- [x] `docs/API_CONTRACT.md` - API contract for desktop app

---

## 🧪 Testing

- [ ] Unit tests for memory system
- [ ] Unit tests for journal system
- [ ] Unit tests for middleware
- [ ] Integration tests for API
- [ ] E2E tests for agent

---

Last updated: 2025-02-15
