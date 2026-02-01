# Configuration Guide

Complete guide to configuring Executive Assistant for your deployment.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration Overview](#configuration-overview)
- [Required Settings](#required-settings)
- [LLM Providers](#llm-providers)
- [Channels](#channels)
- [Database Setup](#database-setup)
- [Advanced Configuration](#advanced-configuration)
- [Environment-Specific Setups](#environment-specific-setups)
- [Troubleshooting](#troubleshooting)
- [Configuration Reference](#configuration-reference)

---

## Quick Start

### 1. Copy Environment Template

```bash
cp docker/.env.example docker/.env
```

### 2. Add Your API Keys

Edit `docker/.env` and add:

```bash
# Choose ONE LLM provider (only one is required!)
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# Or use Anthropic:
# DEFAULT_LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Add your channel tokens
TELEGRAM_BOT_TOKEN=your-bot-token-here

# Add database password
POSTGRES_PASSWORD=your-secure-password

# Add external services
FIRECRAWL_API_KEY=fc-your-key-here
```

### 3. Start the Application

```bash
docker compose up -d
```

That's it! Executive Assistant will start with default configuration.

---

## Configuration Overview

Executive Assistant uses a **layered configuration system** (higher priority overrides lower):

1. **Environment Variables** (`.env`) - Secrets and environment-specific overrides
2. **Config File** (`docker/config.yaml`) - Application defaults
3. **Code Defaults** - Fallback values in Python code

### Configuration Files

| File | Purpose | Committed to Git? |
|------|---------|-------------------|
| `docker/.env` | Your actual secrets and overrides | ❌ NO (contains API keys) |
| `docker/.env.example` | Template for new deployments | ✅ Yes |
| `docker/config.yaml` | Application defaults | ✅ Yes |

**Important:** Never commit `docker/.env` to version control! It's excluded by `.gitignore`.

---

## Required Settings

### Minimum Required Variables

To run Executive Assistant, you need these in `docker/.env`:

#### 1. LLM Provider (Choose ONE)

```bash
# Option 1: OpenAI (Recommended)
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...

# Option 2: Anthropic (Claude)
DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Option 3: Zhipu AI
DEFAULT_LLM_PROVIDER=zhipu
ZHIPUAI_API_KEY=...

# Option 4: Ollama
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_MODE=cloud
OLLAMA_CLOUD_API_KEY=...
# For local Ollama, no API key needed
```

**You only need ONE provider's API key**, not all of them!

#### 2. Channel Configuration

```bash
# At least one channel required
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http

# Telegram (if using telegram channel)
TELEGRAM_BOT_TOKEN=8371069399:AAH...
# Optional: TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
```

#### 3. Database

```bash
# PostgreSQL password
POSTGRES_PASSWORD=your-secure-password
```

#### 4. External Services

```bash
# Firecrawl (web search + scraping)
FIRECRAWL_API_KEY=fc-...
```

---

## LLM Providers

Executive Assistant supports multiple LLM providers. Choose based on your needs:

### OpenAI

**Best for:** General purpose, fast responses, cost-effective

```bash
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
```

**Models in config.yaml:**
- `default_model: gpt-5.2-2025-12-11` - High quality reasoning
- `fast_model: gpt-5-mini-2025-08-07` - Quick responses

**Pricing:** Check [OpenAI pricing](https://openai.com/pricing)

### Anthropic (Claude)

**Best for:** Complex reasoning, long context, nuanced responses

```bash
DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Models in config.yaml:**
- `default_model: claude-haiku-4-5-20251001` - Fast and efficient
- `fast_model: claude-haiku-4-5-20251001` - Same model

**Pricing:** Check [Anthropic pricing](https://www.anthropic.com/pricing)

### Zhipu AI

**Best for:** Chinese language support, cost-effective option

```bash
DEFAULT_LLM_PROVIDER=zhipu
ZHIPUAI_API_KEY=...
```

**Models in config.yaml:**
- `default_model: glm-4-plus` - High quality
- `fast_model: glm-4-flash` - Fast responses

**Pricing:** Check [Zhipu AI pricing](https://open.bigmodel.cn/pricing)

### Ollama

**Best for:** Privacy, local deployment, no API costs

```bash
# Cloud mode (requires API key)
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_MODE=cloud
OLLAMA_CLOUD_API_KEY=...

# Local mode (no API key needed)
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_MODE=local
```

**Models in config.yaml:**
- `default_model: gpt-oss:20b-cloud` - Cloud model
- `fast_model: gpt-oss:20b-cloud` - Same model
- Configure in `config.yaml` under `ollama.local_url`

**Setup:** Install Ollama locally or use [Ollama Cloud](https://ollama.com)

### Switching Providers

Simply change `DEFAULT_LLM_PROVIDER` in `.env` and restart:

```bash
# In docker/.env
DEFAULT_LLM_PROVIDER=anthropic

# Restart
docker compose restart executive_assistant
```

No other configuration changes needed!

---

## Channels

Channels are how you interact with Executive Assistant.

### Telegram

**Setup:**

1. Create a bot via [@BotFather](https://t.me/botfather) on Telegram
2. Copy the bot token
3. Add to `.env`:

```bash
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
TELEGRAM_BOT_TOKEN=8371069399:AAH...
AGENT_NAME=YourBotName
```

**Optional Webhook** (for production):

```bash
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
TELEGRAM_WEBHOOK_SECRET=your-random-secret
```

### HTTP Channel

**Setup:**

```bash
EXECUTIVE_ASSISTANT_CHANNELS=http
```

**Configuration in `config.yaml`:**

```yaml
channels:
  http:
    host: "0.0.0.0"
    port: 8000
```

**Override in `.env` (optional):**

```bash
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
```

**Access:** `http://localhost:8000` (or your server IP)

### Using Multiple Channels

```bash
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
```

Both channels will be active simultaneously.

---

## Database Setup

Executive Assistant uses PostgreSQL for persistent storage.

### Quick Start (Docker)

```bash
docker compose up -d postgres
```

The database is automatically initialized with:
- Database: `executive_assistant_db`
- User: `executive_assistant`
- Password: (from `POSTGRES_PASSWORD` in `.env`)

### External PostgreSQL

To use an external PostgreSQL instance:

```bash
# In docker/.env
POSTGRES_HOST=your-postgres-server.com
POSTGRES_PORT=5432
POSTGRES_USER=executive_assistant
POSTGRES_DB=executive_assistant_db
POSTGRES_PASSWORD=your-secure-password
```

**Or in `docker/config.yaml`:**

```yaml
storage:
  postgres:
    host: your-postgres-server.com
    port: 5432
    user: executive_assistant
    db: executive_assistant_db
```

**Note:** `.env` values take precedence over `config.yaml`.

### Storage Hierarchy

Executive Assistant uses a 3-level storage hierarchy:

```
data/
├── shared/          # Shared knowledge across all users
├── users/           # Per-user data
│   └── telegram:123/
│       ├── files/   # User files
│       └── stores/  # User databases
└── admins/          # Admin-only data
```

**Override paths in `.env` (optional):**

```bash
SHARED_ROOT=./data/shared
USERS_ROOT=./data/users
ADMINS_ROOT=./data/admins
```

---

## Advanced Configuration

### Admin Access

Configure admin users and threads in `docker/config.yaml`:

```yaml
admin:
  # Admin user IDs (comma-separated)
  user_ids: [123456789, 987654321]

  # Admin thread IDs (comma-separated)
  thread_ids: [telegram:6282871705]
```

**How to find your Telegram ID:**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID

### Vector Store (Knowledge Retrieval)

Configure in `docker/config.yaml`:

```yaml
vector_store:
  # Embedding model for semantic search
  embedding_model: "all-MiniLM-L6-v2"
  embedding_dimension: 384
  chunk_size: 3000  # Chunk size for documents
```

**Supported models:** Any sentence-transformers model

### Memory (User Learning)

Executive Assistant automatically extracts and remembers information about you.

Configure in `docker/config.yaml`:

```yaml
memory:
  auto_extract: true      # Auto-extract from messages
  confidence_min: 0.6     # Minimum confidence to save
  max_per_turn: 3         # Max memories per message
  extract_model: fast     # Model variant for extraction
  extract_provider: null  # Use default provider
  extract_temperature: 0.0
```

**What it learns:**
- Your preferences
- Recurring patterns
- Important facts you mention
- Communication style

### Summarization Middleware

Automatically summarizes long conversations to manage context.

Configure in `docker/config.yaml`:

```yaml
middleware:
  summarization:
    enabled: true
    max_tokens: 12000      # Trigger summarization at this size
    target_tokens: 2000    # Target size after summarization
```

**How it works:**
- When conversation reaches ~12,000 tokens, older messages are summarized
- Most recent ~2,000 tokens preserved verbatim
- Summary + recent messages = efficient context usage

### Call Limits

Prevent runaway agent execution.

Configure in `docker/config.yaml`:

```yaml
middleware:
  model_call_limit: 50   # Max LLM calls per message
  tool_call_limit: 100   # Max tool calls per message
```

### Logging

Configure in `docker/.env`:

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG
```

**Or in `docker/config.yaml`:**

```yaml
logging:
  level: DEBUG
  file: logs/executive_assistant.log  # Optional log file
```

### Timezone

Configure in `docker/.env`:

```bash
TZ=Australia/Sydney
```

**Or in `docker/config.yaml`:**

```yaml
# Set system timezone
environment:
  TZ: Australia/Sydney
```

**Format:** IANA timezone database format (e.g., `UTC`, `America/New_York`, `Europe/London`)

---

## Environment-Specific Setups

### Development

**`docker/.env` for development:**

```bash
# Use fast models for quick iteration
DEFAULT_LLM_PROVIDER=openai
LOG_LEVEL=DEBUG

# Local database
POSTGRES_HOST=localhost

# HTTP channel for testing
EXECUTIVE_ASSISTANT_CHANNELS=http
HTTP_PORT=8000
```

### Production

**`docker/.env` for production:**

```bash
# Use high-quality models
DEFAULT_LLM_PROVIDER=anthropic

# Production database
POSTGRES_HOST=postgres.production.example.com
POSTGRES_PASSWORD=very-secure-password

# Telegram with webhook
EXECUTIVE_ASSISTANT_CHANNELS=telegram
TELEGRAM_WEBHOOK_URL=https://bot.example.com/webhook
TELEGRAM_WEBHOOK_SECRET=random-secret-string

# Minimal logging
LOG_LEVEL=WARNING
```

### Testing

**`docker/.env` for testing:**

```bash
# Use free/local provider
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_MODE=local

# In-memory database for fast tests
POSTGRES_HOST=localhost

# Debug mode
LOG_LEVEL=DEBUG
```

---

## Troubleshooting

### "No LLM API key found"

**Problem:** Executive Assistant can't find any API keys.

**Solution:**
1. Check that you set ONE provider's API key in `.env`
2. Verify the key is not commented out (no `#` at start of line)
3. Ensure `DEFAULT_LLM_PROVIDER` matches the key you set

```bash
# Correct:
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...

# Wrong (key is commented):
DEFAULT_LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-proj-...
```

### "PostgreSQL connection failed"

**Problem:** Can't connect to database.

**Solutions:**
1. Ensure PostgreSQL is running:
   ```bash
   docker compose ps postgres
   ```

2. Check connection settings in `.env`:
   ```bash
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_PASSWORD=your-password
   ```

3. Verify password matches between `.env` and PostgreSQL:
   ```bash
   docker compose exec postgres psql -U executive_assistant -d executive_assistant_db
   ```

### "Firecrawl API key not configured"

**Problem:** Web search not working.

**Solution:**
```bash
# Add to docker/.env
FIRECRAWL_API_KEY=fc-your-key-here

# Get a key at: https://firecrawl.dev
```

### Telegram bot not responding

**Problem:** Bot doesn't reply to messages.

**Solutions:**
1. Verify bot token is correct:
   ```bash
   # Test token
   curl https://api.telegram.org/bot<TOKEN>/getMe
   ```

2. Check bot is running:
   ```bash
   docker compose ps executive_assistant
   docker compose logs executive_assistant
   ```

3. Ensure channel is enabled:
   ```bash
   EXECUTIVE_ASSISTANT_CHANNELS=telegram,http
   ```

### Configuration not taking effect

**Problem:** Changes to `.env` or `config.yaml` not working.

**Solutions:**
1. Restart the application:
   ```bash
   docker compose restart executive_assistant
   ```

2. Check for typos in variable names:
   ```bash
   # Correct:
   DEFAULT_LLM_PROVIDER=openai

   # Wrong (typo):
   DEFAULT_LLM_PROVDER=openai
   ```

3. Verify priority: `.env` overrides `config.yaml`

4. Check file is being read:
   ```bash
   docker compose exec executive_assistant env | grep DEFAULT_LLM_PROVIDER
   ```

---

## Configuration Reference

### Complete .env Example

```bash
# ============================================================================
# Executive Assistant Environment Configuration
# ============================================================================
# This file contains ONLY secrets and environment-specific overrides.
# Application defaults are in config.yaml.
#
# ⚠️ NEVER commit this file to version control!
# ============================================================================

# ============================================================================
# REQUIRED: LLM Provider
# ============================================================================
# Choose your LLM provider: anthropic, openai, zhipu, ollama
# You only need to set the API key for your chosen provider.
DEFAULT_LLM_PROVIDER=openai

# Anthropic (Claude) - Required only if DEFAULT_LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-xxx

# OpenAI - Required only if DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...

# Zhipu AI - Required only if DEFAULT_LLM_PROVIDER=zhipu
# ZHIPUAI_API_KEY=...

# Ollama (cloud or local) - Required only if DEFAULT_LLM_PROVIDER=ollama
# Note: No API key needed for local Ollama, only cloud mode requires key
# OLLAMA_MODE=cloud
# OLLAMA_CLOUD_API_KEY=...

# ============================================================================
# REQUIRED: Channels
# ============================================================================
# Active channels (comma-separated: telegram,http)
EXECUTIVE_ASSISTANT_CHANNELS=telegram,http

# Telegram Bot
TELEGRAM_BOT_TOKEN=8371069399:AAH...
# TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
# TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

# HTTP Channel (override config.yaml defaults)
# HTTP_HOST=0.0.0.0
# HTTP_PORT=8000

# ============================================================================
# REQUIRED: Database
# ============================================================================
POSTGRES_PASSWORD=your-secure-password-here

# Optional: Remote PostgreSQL (overrides config.yaml)
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_USER=executive_assistant
# POSTGRES_DB=executive_assistant_db

# ============================================================================
# REQUIRED: External Services
# ============================================================================
# Firecrawl (web scraping + search)
# Used for: search_web, firecrawl_scrape, firecrawl_crawl tools
FIRECRAWL_API_KEY=fc-your-firecrawl-api-key
# FIRECRAWL_API_URL=https://firecrawl.research-stack.gongchatea.com.au

# ============================================================================
# OPTIONAL: Overrides
# ============================================================================
# Override config.yaml values if needed for your environment

# Agent customization
# AGENT_NAME=Executive Assistant

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG

# Time zone
TZ=Australia/Sydney

# Storage paths (for custom deployments)
# USERS_ROOT=./data/users
# SHARED_ROOT=./data/shared
# ADMINS_ROOT=./data/admins
```

### Environment Variable Reference

| Variable | Required? | Default | Description |
|----------|-----------|---------|-------------|
| `DEFAULT_LLM_PROVIDER` | Yes | `openai` | LLM provider: anthropic, openai, zhipu, ollama |
| `OPENAI_API_KEY` | If using OpenAI | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | - | Anthropic API key |
| `ZHIPUAI_API_KEY` | If using Zhipu | - | Zhipu AI API key |
| `OLLAMA_MODE` | If using Ollama | `cloud` | Ollama mode: cloud or local |
| `OLLAMA_CLOUD_API_KEY` | If using Ollama cloud | - | Ollama cloud API key |
| `EXECUTIVE_ASSISTANT_CHANNELS` | Yes | `telegram,http` | Active channels (comma-separated) |
| `TELEGRAM_BOT_TOKEN` | If using Telegram | - | Telegram bot token |
| `TELEGRAM_WEBHOOK_URL` | No | - | Telegram webhook URL |
| `TELEGRAM_WEBHOOK_SECRET` | No | - | Telegram webhook secret |
| `HTTP_HOST` | No | `0.0.0.0` | HTTP channel host |
| `HTTP_PORT` | No | `8000` | HTTP channel port |
| `POSTGRES_HOST` | No | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_USER` | No | `executive_assistant` | PostgreSQL user |
| `POSTGRES_DB` | No | `executive_assistant_db` | PostgreSQL database |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL password |
| `FIRECRAWL_API_KEY` | Yes | - | Firecrawl API key |
| `AGENT_NAME` | No | `Executive Assistant` | Agent display name |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `TZ` | No | `UTC` | Timezone |
| `USERS_ROOT` | No | `./data/users` | User data directory |
| `SHARED_ROOT` | No | `./data/shared` | Shared data directory |
| `ADMINS_ROOT` | No | `./data/admins` | Admin data directory |

---

## Getting Help

### Check Application Status

```bash
# View application logs
docker compose logs executive_assistant

# Follow logs in real-time
docker compose logs -f executive_assistant

# Check all services
docker compose ps
```

### Validate Configuration

```bash
# Test configuration by starting application
docker compose up executive_assistant

# Check for errors in startup logs
docker compose logs executive_assistant | grep -i error
```

### Common Issues

| Issue | Solution |
|-------|----------|
| API key not working | Regenerate key from provider dashboard |
| Database connection failed | Check PostgreSQL is running and password is correct |
| Bot not responding | Verify bot token and check bot is running |
| Configuration ignored | Restart application after changing `.env` |
| Context too long | Adjust `middleware.summarization.max_tokens` |

---

## Best Practices

### Security

1. **Never commit `.env` to git** - It's excluded by `.gitignore` for a reason
2. **Rotate API keys regularly** - Especially if exposed accidentally
3. **Use strong passwords** - For PostgreSQL and webhook secrets
4. **Limit admin access** - Only grant admin to trusted users
5. **Use webhooks in production** - Don't rely on polling for Telegram

### Performance

1. **Choose the right LLM provider** - Balance cost vs. speed vs. quality
2. **Enable summarization** - Prevents context from growing too large
3. **Set appropriate call limits** - Prevent runaway agent execution
4. **Use fast models for simple tasks** - Configure `fast_model` appropriately

### Maintenance

1. **Regular backups** - Backup PostgreSQL database and `data/` directory
2. **Monitor logs** - Check `logs/executive_assistant.log` regularly
3. **Update dependencies** - Keep LangChain and LangGraph updated
4. **Test configuration changes** - Test in development before production

---

## Further Reading

- [README.md](../README.md) - Main project documentation
- [features/CONFIG_OPTIMIZATION_PLAN.md](../features/CONFIG_OPTIMIZATION_PLAN.md) - Configuration design decisions
- [LangChain Documentation](https://python.langchain.com/) - Understanding LangChain integration
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) - State management and workflows

---

**Last Updated:** 2025-02-02

**Need help?** Open an issue on [GitHub](https://github.com/mgmtcnsltng/executive_assistant/issues)
