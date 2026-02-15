# AGENTS.md

AI coding agents working on this repository should follow these guidelines.

## Build Commands

```bash
# Install dependencies
make dev                    # Install with dev dependencies
make install                # Production only

# Run tests
make test                   # All tests with coverage (80% minimum)
make test-unit              # Unit tests only
make test-integration       # Integration tests only

# Single test file
make test-file FILE=tests/unit/llm/test_openai.py

# Or with pytest directly
uv run pytest tests/unit/llm/test_openai.py -v
uv run pytest tests/unit/config/test_settings.py::TestParseModelString -v
uv run pytest -k "test_openai" -v

# Code quality
make lint                   # Ruff linter
make format                 # Ruff formatter
make typecheck              # MyPy type checking

# Before committing
make lint format test
```

## Project Architecture

```
executive-assistant/
├── src/
│   ├── agent/            # Deep Agents factory, prompts, subagents
│   ├── middleware/       # Custom middleware (memory, logging, rate-limit)
│   ├── memory/           # Memory DB interface (SQLite + FTS5 + vec)
│   ├── config/           # Pydantic settings from .env
│   ├── llm/              # LLM provider abstraction
│   │   ├── base.py       # Abstract provider class
│   │   ├── factory.py    # Provider factory & auto-detection
│   │   ├── errors.py     # LLM-specific exceptions
│   │   └── providers/    # 17+ provider implementations
│   ├── observability/    # Langfuse tracing (optional)
│   ├── storage/          # Postgres + per-user storage
│   ├── api/              # FastAPI endpoints
│   ├── telegram/         # Telegram bot
│   ├── skills/           # Built-in skills (SKILL.md files)
│   ├── acp/              # ACP server for IDE integration
│   └── cli/              # Typer CLI
├── tests/
│   ├── unit/             # Fast, isolated tests
│   ├── integration/      # Database/API tests
│   └── conftest.py       # Shared fixtures
├── data/                 # Persistent data (gitignored)
│   ├── config.yaml       # App-level configuration
│   ├── shared/           # Team resources
│   └── users/            # Per-user data
└── docker/               # Docker configuration
```

## Code Style

### Imports
```python
# Standard library first (alphabetically)
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Third-party (alphabetically)
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

# Local imports last (alphabetically)
from src.config.settings import get_settings
from src.llm.errors import LLMError
```

### Type Hints
- Always use type hints for function parameters and return types
- Use `from __future__ import annotations` for forward references
- Prefer `list[str]` over `List[str]`, `dict[str, Any]` over `Dict[str, Any]`
- Use `| None` for optional types, not `Optional[str]`
- Use `TYPE_CHECKING` block for import-time type-only imports

```python
if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel
```

### Error Handling
```python
# Use custom exceptions from src.llm.errors
from src.llm.errors import LLMConfigurationError, LLMProviderNotFoundError

def create_chat_model(model: str) -> BaseChatModel:
    if not self.api_key:
        raise LLMConfigurationError(
            "OpenAI API key is required",
            provider="openai",
        )
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `OpenAIProvider`, `MemoryContextMiddleware`)
- Functions/variables: `snake_case` (e.g., `get_llm`, `user_id`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MODEL_PREFIX_TO_PROVIDER`)
- Private methods/variables: `_leading_underscore`
- Type variables: `T` or `TModel`
- Pydantic models: `PascalCase` with `Field()` for descriptions

### Pydantic Models
```python
class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="List of chat messages")
    model: str | None = Field(None, description="Model in format provider/model-name")
    temperature: float = Field(0.7, ge=0, le=2)
```

### Functions
- Keep functions focused on a single responsibility
- Use docstrings for public functions
- Return early to reduce nesting

```python
def get_llm(
    model: str,
    provider: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Get an LLM instance for the specified model and provider.

    Args:
        model: Model name (e.g., 'gpt-4o')
        provider: Provider name (e.g., 'openai'). Auto-detected if None.
        **kwargs: Additional arguments passed to the LLM constructor.

    Returns:
        Configured LLM instance.

    Raises:
        LLMProviderNotFoundError: If provider is not registered.
        LLMConfigurationError: If API key is missing.
    """
```

## Model Selection

Users specify models as `provider/model-name`:
```python
# Examples (one per provider):
# - openai/gpt-5.2
# - anthropic/claude-opus-4-6
# - ollama/qwen3-coder-next
# - google/gemini-2.5-pro

from src.llm import get_llm

llm = get_llm(provider="openai", model="gpt-5.2")
llm = get_llm(model="openai/gpt-5.2")  # Auto-detects provider
```

## Storage

Per-user storage structure:
```
/data/users/{user_id}/
├── .memory/
│   └── memory.db           # SQLite + FTS5 + vec
├── .journal/
│   └── journal.db          # SQLite + FTS5 + vec
├── .vault/
│   └── vault.db            # Encrypted secrets vault
├── skills/                 # User-specific skills
├── .mcp.json              # User MCP servers
└── projects/              # User project files
```

## Testing Guidelines

### Unit Tests
- Mock external dependencies (LLM APIs, databases)
- Test one thing per test function
- Use fixtures from `conftest.py`
- 80% coverage minimum

```python
def test_get_llm_raises_for_unknown_provider() -> None:
    with pytest.raises(LLMProviderNotFoundError):
        get_llm(provider="unknown", model="model")


def test_detect_provider_from_model() -> None:
    assert detect_provider_from_model("gpt-4o") == "openai"
    assert detect_provider_from_model("claude-3-opus") == "anthropic"
    assert detect_provider_from_model("unknown-model") is None
```

### Test Naming
- Test files: `test_<module>.py`
- Test classes: `Test<Feature>`
- Test functions: `test_<behavior>`

### Fixtures
Use fixtures from `conftest.py`:
- `clean_env` - Reset all singletons and env vars
- `mock_env_with_openai` - Environment with OpenAI configured
- `mock_env_with_anthropic` - Environment with Anthropic configured
- `temp_data_path` - Temporary data directory
- `temp_user_path` - Temporary user directory

## Configuration

All configuration via environment variables in `.env`:
- `AGENT_NAME=Executive Assistant` - Customizable agent name
- `DEFAULT_MODEL=openai/gpt-4o` - Main chat model
- `SUMMARIZATION_MODEL=openai/gpt-4o-mini` - Summarization tasks
- `DATABASE_URL=postgresql://...` - Postgres for checkpoints
- `DATA_PATH=/data` - Base path for all data
- `LANGFUSE_ENABLED=false` - Toggle Langfuse tracing
- `TELEGRAM_ENABLED=false` - Toggle Telegram bot
- `TAVILY_API_KEY=` or `FIRECRAWL_API_KEY=` - Web search

## Middleware

Custom middleware in `src/middleware/`:
- `MemoryContextMiddleware` - Inject memories into prompts
- `MemoryLearningMiddleware` - Auto-extract memories from conversations
- `LoggingMiddleware` - Log all agent activity to JSONL
- `CheckinMiddleware` - Periodic check-in with user
- `RateLimitMiddleware` - Rate limit requests

## Skills

Skills use `SKILL.md` files with YAML frontmatter:
```markdown
---
name: coding
description: Software development tasks
version: "1.0.0"
tags: [coding, development, debugging]
---

# Coding Skill

Instructions for coding tasks...
```

## When Adding New Features

1. Write failing tests first (TDD)
2. Implement minimum code to pass
3. Add edge case tests
4. Run `make lint format test` before committing
5. Ensure 80%+ test coverage

## Common Patterns

### Adding a New LLM Provider

1. Create `src/llm/providers/new_provider.py`:
```python
class NewProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "new_provider"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings) -> NewProvider:
        return cls(api_key=settings.llm.new_provider_api_key)

    def create_chat_model(self, model: str, **kwargs) -> BaseChatModel:
        from langchain_newprovider import ChatNewProvider
        return ChatNewProvider(model=model, api_key=self.api_key, **kwargs)
```

2. Add to `src/llm/providers/__init__.py`
3. Add env key to `src/config/settings.py`
4. Add to `.env.example`
5. Write tests in `tests/unit/llm/providers/test_new_provider.py`

### Adding a New Tool

Add tools in `src/agent/factory.py`:
```python
@tool
def my_new_tool(arg: str) -> str:
    """Tool description for the LLM.

    Args:
        arg: Argument description

    Returns:
        Result description
    """
    # Implementation
    return "result"
```

### Adding a New Middleware

Create in `src/middleware/`:
```python
from langchain.agents.middleware import AgentMiddleware

class MyMiddleware(AgentMiddleware):
    def before_model(self, state, runtime):
        # Pre-model logic
        return None

    def after_model(self, state, runtime):
        # Post-model logic
        return None
```
