# Executive Assistant - Agent Guidelines

This document provides guidelines for agents working on this codebase.

---

## 1. Build, Lint, and Test Commands

### Installation
```bash
# Install with all dependencies
uv pip install -e ".[cli,http,telegram,dev]"

# Install specific extras
uv pip install -e ".[cli]"      # CLI only
uv pip install -e ".[http]"      # HTTP API only
uv pip install -e ".[telegram]"  # Telegram bot only
uv pip install -e ".[dev]"      # Development tools
```

### Running the Application
```bash
uv run ea cli        # Start CLI (with streaming support)
uv run ea http      # Start HTTP server (with SSE streaming)
uv run ea telegram  # Start Telegram bot
```

### Linting and Type Checking
```bash
# Run ruff linter
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check src/ --fix

# Run mypy type checker
uv run mypy src/
```

### Testing (TDD - Test Driven Development)
```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/unit/test_config.py

# Run a single test function
uv run pytest tests/unit/test_config.py::test_agent_config_valid

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run tests in watch mode
uv run pytest --watch

# Run persona evaluation (100 interactions per persona)
uv run python tests/evaluation/evaluate.py
```

### Docker
```bash
# Start PostgreSQL
cd docker && docker compose up -d

# Stop PostgreSQL
cd docker && docker compose down

# Build and run app in Docker
cd docker && docker compose up --build
```

---

## 2. Code Style Guidelines

### Python Version
- Minimum: Python 3.11
- Use modern Python features (type hints, structural pattern matching)

### Imports (PEP 8 + Ruff)
```python
# Standard library first
import os
import json
from pathlib import Path
from typing import Any, Optional

# Third-party libraries
from dotenv import load_dotenv
from pydantic import Field
from fastapi import FastAPI

# Local imports (absolute)
from src.config import get_settings
from src.llm import create_model_from_config

# Sort imports with: uv run ruff check src/ --fix
```

### Formatting
- Line length: 100 characters
- Use Black-compatible formatting via Ruff
- 4 spaces for indentation (no tabs)

### Type Hints (Required)
```python
# Use type hints for all function signatures
def process_message(message: str, user_id: str = "default") -> dict[str, Any]:
    ...

# Use | for unions (Python 3.10+)
def get_value(key: str | None) -> str:
    ...

# Use Optional for nullable
def find_item(name: Optional[str]) -> Item | None:
    ...
```

### Naming Conventions
- **Variables/functions**: `snake_case` (e.g., `get_logger`, `user_id`)
- **Classes**: `PascalCase` (e.g., `ExecutiveAssistantCLI`, `Logger`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private members**: `_leading_underscore` (e.g., `_internal_state`)

### Tool Naming Pattern
All tools must follow `category_{verb}` pattern:
```python
# Email tools
email_connect, email_disconnect, email_accounts
email_list, email_get, email_search
email_send, email_sync

# Contacts tools
contacts_list, contacts_get, contacts_add, contacts_update, contacts_delete, contacts_search

# Todos tools
todos_list, todos_add, todos_update, todos_delete, todos_extract

# File tools
files_glob_search, files_grep_search, files_list, files_read, files_write, files_edit, files_delete

# Other tools
shell_execute, time_get, memory_get_history, memory_search, skills_list, skills_load
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str = Field(default="Executive Assistant")
    model: str = Field(default="ollama:minimax-m2.5")
    
    class Config:
        env_prefix = "AGENT_"
        extra = "ignore"  # Allow extra fields from env
```

### Error Handling
```python
# Use specific exceptions
try:
    result = await agent.ainvoke({"messages": messages})
except ValueError as e:
    logger.error("validation_error", {"error": str(e)}, user_id=user_id)
    raise
except Exception as e:
    logger.error("unexpected_error", {"error": str(e), "error_type": type(e).__name__}, user_id=user_id)
    raise
```

---

## 3. Logging Best Practices

### Always Use the Logger
```python
from src.app_logging import get_logger, timer

logger = get_logger()

# Use timer for operations with duration tracking
with timer("operation_name", {"key": "value"}, user_id=user_id, channel="cli") as t:
    result = await do_work()
    
# Log at appropriate levels - CRITICAL: pass user_id as parameter, not in data dict
logger.debug("detailed_info", {"data": "..."}, user_id=user_id)
logger.info("action_completed", {"result": "..."}, user_id=user_id)
logger.warning("potential_issue", {"warning": "..."}, user_id=user_id)
logger.error("operation_failed", {"error": "..."}, user_id=user_id)

# For system-wide events without specific user
logger.info("system_event", {"info": "..."}, user_id="system")
```

### Log Format
Follow the standard format in `data/logs/YYYY-MM-DD.jsonl`:
```json
{
  "timestamp": "2026-02-20T03:00:00.000000Z",
  "user_id": "alice_test",
  "event": "agent.response",
  "level": "info",
  "channel": "cli",
  "data": {"response": "Hello!"}
}
```

### CRITICAL: user_id Must Be Passed as Parameter
```python
# CORRECT - user_id as separate parameter
logger.info("event_name", {"key": "value"}, user_id=user_id)

# WRONG - user_id inside data dict (this will show "default" in logs)
logger.info("event_name", {"key": "value", "user_id": user_id})
```

### Log Levels
- **debug**: Verbose debugging info (development only)
- **info**: Normal operation events
- **warning**: Potential issues that don't break functionality
- **error**: Errors that need attention

### Sensitive Data
The logger automatically redacts fields containing: `api_key`, `password`, `secret`, `token`, `key`

---

## 4. Per-User Database Isolation

### Database Structure
All user data is isolated per-user under `data/users/{user_id}/`:
```
data/users/{user_id}/
├── email/
│   └── emails.db         # User's emails
├── contacts/
│   └── contacts.db       # User's contacts
├── todos/
│   └── todos.db          # User's todos
└── conversation/
    └── messages.db       # User's conversation history
```

### Database Access Pattern
```python
from src.tools.email.db import get_engine
from src.tools.contacts.storage import get_db_path
from src.tools.todos.storage import TodosStorage

# Email - uses SQLAlchemy
engine = get_engine(user_id)

# Contacts - direct SQLite path
db_path = get_db_path(user_id)

# Todos - storage class
storage = TodosStorage(user_id, base_dir)
```

---

## 5. Streaming Support

### CLI Streaming
The CLI supports real-time streaming responses:
```python
from src.agents.manager import run_agent_stream

# In CLI handler
async for chunk in run_agent_stream(user_id, messages, message):
    chunk_type = getattr(chunk, "type", None)
    if chunk_type == "tool":
        print(f"Tool: {chunk.content}")
    elif chunk_type == "ai":
        print(chunk.content, end="")
```

### HTTP Streaming (SSE)
The HTTP endpoint `/message/stream` returns Server-Sent Events:
```python
# Response format
data: {"type": "tool", "content": "..."}
data: {"type": "ai", "content": "..."}
data: {"type": "done", "content": "final response"}
```

---

## 6. Test Driven Development (TDD)

### Test Structure
```python
# tests/unit/test_module.py
import pytest

class TestModuleName:
    """Tests for module_name."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        result = basic_function()
        assert result == expected

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function."""
        result = await async_function()
        assert result is not None
```

### Test Naming
- `test_<function_name>_<scenario>`
- `test_<class_name>_<method_name>_<scenario>`

### Test Fixtures
```python
@pytest.fixture
def sample_config():
    """Sample config for testing."""
    return {"key": "value"}
```

### Async Testing
```python
@pytest.mark.asyncio
async def test_agent_response():
    """Test agent response."""
    from src.app_logging import get_logger
    logger = get_logger()
    
    with logger.timer("test_agent", user_id="test") as t:
        result = await agent.ainvoke(...)
    
    assert result is not None
```

### Testing Required Fields
Always test that tools validate required parameters:
```python
def test_tool_requires_user_id(self):
    """Test tool requires user_id."""
    from src.tools.module import tool_function

    result = tool_function.invoke({"param": "value"})
    assert "Error: user_id is required" in result
```

---

## 7. Project Structure

```
executive-assistant/
├── src/
│   ├── __init__.py              # Package entry
│   ├── __main__.py              # CLI entry point
│   ├── app_logging.py           # Logging module
│   ├── cli/main.py              # CLI interface (with streaming)
│   ├── http/main.py             # HTTP API (with SSE streaming)
│   ├── telegram/main.py         # Telegram bot
│   ├── agents/
│   │   ├── factory.py           # Agent factory with middleware
│   │   └── manager.py           # Agent pool, run_agent, run_agent_stream
│   ├── config/settings.py       # Configuration
│   ├── llm/providers.py         # LLM providers
│   ├── storage/                 # Storage utilities
│   │   ├── conversation.py     # Message storage
│   │   ├── checkpoint.py        # LangGraph checkpointing
│   │   └── user.py             # User management
│   ├── tools/
│   │   ├── email/              # Email tools (IMAP sync, send, read)
│   │   │   ├── account.py      # email_connect, disconnect, accounts
│   │   │   ├── db.py           # Per-user email database
│   │   │   ├── read.py         # email_list, get, search
│   │   │   ├── send.py         # email_send (new, reply, reply_all)
│   │   │   └── sync.py         # email_sync, interval sync, rate limiting
│   │   ├── contacts/           # Contacts tools
│   │   │   ├── storage.py      # Per-user contacts database
│   │   │   └── tools.py        # contacts CRUD
│   │   ├── todos/              # Todos tools
│   │   │   ├── storage.py      # Per-user todos database
│   │   │   └── tools.py        # todos CRUD + LLM extraction
│   │   ├── filesystem.py       # files_list, read, write, edit, delete
│   │   ├── file_search.py      # files_glob_search, files_grep_search
│   │   ├── shell.py            # shell_execute
│   │   ├── memory.py           # memory_get_history, memory_search
│   │   ├── time.py             # time_get
│   │   ├── firecrawl.py        # scrape_url, search_web, crawl_url, etc.
│   │   └── vault/              # Credential storage
│   └── skills/                 # Skills system
│       ├── middleware.py       # SkillMiddleware
│       ├── registry.py         # SkillRegistry
│       └── tools.py            # skills_list, skills_load
├── tests/
│   ├── unit/                   # Unit tests
│   │   ├── test_email_tools.py
│   │   ├── test_contacts_tools.py
│   │   ├── test_todos_tools.py
│   │   ├── test_filesystem_tools.py
│   │   ├── test_other_tools.py
│   │   ├── test_middleware.py
│   │   └── test_background_services.py
│   └── evaluation/             # Persona evaluation
│       ├── personas.py         # 10 persona definitions
│       └── evaluate.py         # Evaluation runner
├── docker/                     # Docker files
├── config.yaml                # Main configuration
└── pyproject.toml             # Project config
```

---

## 8. Configuration

### Environment Variables
- Use `.env` for local development
- Use `.env.example` as template
- All config via `src/config/settings.py`

### Config Priority
1. Environment variables (highest)
2. `.env` file
3. `config.yaml`
4. Default values (lowest)

---

## 9. Persona Evaluation

### Running Evaluation
```bash
# Run full evaluation (10 personas × 100 interactions = 1000 total)
uv run python tests/evaluation/evaluate.py

# Results saved to data/evaluations/
```

### Available Personas
| ID | Name | Style |
|----|------|-------|
| p1 | Direct Dave | Terse, short commands |
| p2 | Polite Pam | Formal, polite |
| p3 | Casual Chris | Informal, casual |
| p4 | Questioning Quinn | Inquisitive |
| p5 | Storytelling Sam | Narrative, gives context |
| p6 | Commanding Chris | Authoritative |
| p7 | Emoji Eva | Expressive, uses emojis |
| p8 | Minimalist Mike | Extremely brief |
| p9 | Technical Terry | Technical, precise |
| p10 | Confused Clara | Uncertain, needs help |

### Evaluation Metrics
- **Accuracy**: Successful responses / Total interactions
- **Tool Calls**: Number of tools invoked
- **Tool Errors**: Failed tool executions
- **Context Maintained**: Agent stays on topic
- **Hallucinations**: Fabricated information

---

## 10. Dependencies

### Adding Dependencies
```bash
# Add runtime dependency
uv add package_name

# Add development dependency
uv add --dev package_name

# Add to specific group
uv add --group cli package_name
```

### Version Pinning
- Use minimum versions in `pyproject.toml` (e.g., `>=1.0.0`)
- Lock versions in `uv.lock` (committed to repo)
