# Ollama Provider Routing Fix

**Date:** 2026-05-31
**Status:** Approved

## Problem

The factory's Ollama routing is broken when `OLLAMA_API_KEY` and `OLLAMA_BASE_URL` are set in `.env`. These env vars force ALL `ollama:*` model strings to route through `OllamaCloud` (direct cloud API), making it impossible to reach local Ollama models without clearing env vars.

Additionally, `raise_if_context_overflow()` crashes on streaming httpx responses by accessing `response.text` before the body is read, masking the real error with `ResponseNotRead`.

## Current Behavior

```
ollama:<model>       → if OLLAMA_API_KEY or OLLAMA_BASE_URL contains "ollama.com" → OllamaCloud
                     → otherwise → OpenAIProvider (localhost:11434/v1)
ollama-cloud:<model> → same logic as above (identical branch, not distinct)
```

Both prefixes resolve identically. Env vars override the prefix intent.

## New Behavior

```
ollama:<model>       → always OpenAIProvider at localhost:11434/v1
ollama-cloud:<model> → always OllamaCloud at ollama.com/api/chat
```

Prefix is the sole routing signal. Env vars provide credentials/URLs for their respective target only.

## Env Var Semantics

| Env Var | Used by | Default |
|---------|---------|---------|
| `OLLAMA_LOCAL_BASE_URL` | `ollama:` prefix | `http://localhost:11434/v1` |
| `OLLAMA_BASE_URL` | `ollama-cloud:` prefix | `https://ollama.com` |
| `OLLAMA_API_KEY` | `ollama-cloud:` prefix only | (none) |

## Changes

### 1. `src/sdk/providers/base.py` — `raise_if_context_overflow()`

Wrap `response.text` access in try/except to handle streaming responses:

```python
if response is not None:
    try:
        text_parts.append(str(getattr(response, "text", "")))
    except Exception:
        pass
```

**Already implemented.**

### 2. `src/sdk/providers/factory.py` — Split Ollama routing

`_resolve_provider_type()`:
- `"ollama"` → `("ollama", "")`
- `"ollama-cloud"` → `("ollama-cloud", "")`

`create_provider()`:
- `resolved_type == "ollama"` → `OpenAIProvider(base_url=OLLAMA_LOCAL_BASE_URL or "http://localhost:11434/v1")`
- `resolved_type == "ollama-cloud"` → `OllamaCloud(base_url=OLLAMA_BASE_URL or "https://ollama.com", api_key=OLLAMA_API_KEY)`

No shared branch. No env-var-driven routing logic.

### 3. No provider class changes

`OllamaCloud` and `OpenAIProvider` are unchanged. Only the factory routing logic changes.

## Model String Examples

| String | Provider | Endpoint |
|--------|----------|----------|
| `ollama:gemma4:e4b` | OpenAIProvider | localhost:11434/v1 |
| `ollama:qwen2.5-coder:14b` | OpenAIProvider | localhost:11434/v1 |
| `ollama:qwen3.5:cloud` | OpenAIProvider | localhost:11434/v1 (local proxies to cloud) |
| `ollama-cloud:minimax-m2.5` | OllamaCloud | ollama.com/api/chat |
| `ollama-cloud:qwen3-coder-next` | OllamaCloud | ollama.com/api/chat |

## Testing

- Existing provider factory tests updated for new routing
- New test: `ollama:gemma4:e4b` → `OpenAIProvider` even when `OLLAMA_API_KEY` is set
- New test: `ollama-cloud:minimax-m2.5` → `OllamaCloud`
- Verify streaming works end-to-end through AgentLoop with local model
