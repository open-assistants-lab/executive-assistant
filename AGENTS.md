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
uv run ea cli        # Start CLI
uv run ea http      # Start HTTP server
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
    logger.error("validation_error", {"error": str(e)})
    raise
except Exception as e:
    logger.error("unexpected_error", {"error": str(e), "error_type": type(e).__name__})
    raise
```

---

## 3. Logging Best Practices

### Always Use the Logger
```python
from src.logging import get_logger, timer

logger = get_logger()

# Use timer for operations with duration tracking
with timer("operation_name", {"key": "value"}, channel="cli") as t:
    result = await do_work()
    
# Log at appropriate levels
logger.debug("detailed_info", {"data": "..."})
logger.info("action_completed", {"result": "..."})
logger.warning("potential_issue", {"warning": "..."})
logger.error("operation_failed", {"error": "..."})
```

### Log Format
Follow the standard format in `data/logs/YYYY-MM-DD.jsonl`:
```json
{
  "timestamp": "2026-02-20T03:00:00.000000Z",
  "user_id": "default",
  "event": "agent.response",
  "level": "info",
  "channel": "cli",
  "data": {"response": "Hello!"}
}
```

### Log Levels
- **debug**: Verbose debugging info (development only)
- **info**: Normal operation events
- **warning**: Potential issues that don't break functionality
- **error**: Errors that need attention

### Sensitive Data
The logger automatically redacts fields containing: `api_key`, `password`, `secret`, `token`, `key`

---

## 4. Test Driven Development (TDD)

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
    # Use the timer/context manager pattern in tests
    from src.logging import get_logger
    logger = get_logger()
    
    with logger.timer("test_agent") as t:
        result = await agent.ainvoke(...)
    
    assert result is not None
```

---

## 5. Project Structure

```
executive-assistant/
├── src/
│   ├── __init__.py          # Package entry
│   ├── __main__.py          # CLI entry point
│   ├── cli/main.py          # CLI interface
│   ├── http/main.py         # HTTP API
│   ├── telegram/main.py     # Telegram bot
│   ├── agents/factory.py   # Agent factory
│   ├── config/settings.py   # Configuration
│   ├── llm/providers.py    # LLM providers
│   ├── logging.py           # Logging module
│   ├── storage/            # Storage utilities
│   └── memory/            # Memory system
├── tests/
│   ├── unit/              # Unit tests
│   └── integration/         # Integration tests
├── docker/                 # Docker files
├── config.yaml            # Main configuration
└── pyproject.toml         # Project config
```

---

## 6. Configuration

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

## 7. Documentation

- Use docstrings for all public functions
- Type hints for all functions
- Comments for complex logic only
- Keep TODO.md updated

---

## 8. Dependencies

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
