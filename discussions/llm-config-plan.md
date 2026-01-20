# LLM Configuration Enhancement Plan

## Goal

Make all LLM-related configurations controllable via `.env` file, including:
1. Main agent provider and model selection
2. Memory extraction provider and model
3. Ollama local vs cloud mode
4. **Strict validation** - refuse to start if models are misconfigured

---

## Peer Review Findings & Fixes

### Issue 1: Field Validator Syntax Bug (Lines 266-274)

**Problem:** The validator for `OLLAMA_CLOUD_API_KEY` won't work because pydantic field validators receive the raw value before field assignment, and `info.data.get("OLLAMA_API_KEY")` won't contain the parsed value.

**Fix:** Use `@model_validator` to handle cross-field dependencies after all fields are parsed:

```python
@model_validator(mode="after")
@classmethod
def map_ollama_api_key(cls, settings: "Settings") -> "Settings":
    """Map legacy OLLAMA_API_KEY to OLLAMA_CLOUD_API_KEY."""
    if not settings.OLLAMA_CLOUD_API_KEY and settings.OLLAMA_API_KEY:
        settings.OLLAMA_CLOUD_API_KEY = settings.OLLAMA_API_KEY
    return settings
```

### Issue 2: Empty String Validator Won't Work (Line 294)

**Problem:** You cannot validate multiple fields with a single `@field_validator` - the decorator only applies to the field it decorates.

**Fix:** Use separate validators or `@model_validator`:

```python
@field_validator("MEM_EXTRACT_PROVIDER", mode="before")
@classmethod
def empty_string_to_none_extract(cls, v: str | None) -> str | None:
    """Convert empty strings to None."""
    return v or None

@field_validator("OCR_STRUCTURED_PROVIDER", mode="before")
@classmethod
def empty_string_to_none_ocr(cls, v: str | None) -> str | None:
    """Convert empty strings to None."""
    return v or None
```

### Issue 3: MEM_EXTRACT_MODEL Hardcoded to OpenAI (Line 283)

**Problem:** `MEM_EXTRACT_MODEL: str = "gpt-4o-mini"` assumes OpenAI. If user's provider is Anthropic, this will fail at runtime.

**Fix:** Use the alias system so it respects the configured provider:

```python
# Before:
MEM_EXTRACT_MODEL: str = "gpt-4o-mini"

# After:
MEM_EXTRACT_MODEL: str = "fast"  # Maps to provider's fast model
```

### Issue 4: No Model Validation

**Problem:** If user sets `ANTHROPIC_FAST_MODEL=gpt-4o-mini` (wrong provider!), it will fail at runtime with a cryptic error.

**Fix:** Add startup validation that checks model names against allowed patterns and refuses to start if invalid.

---

## Current State

```python
# src/executive_assistant/config/settings.py

DEFAULT_LLM_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] = "anthropic"

# Ollama Cloud Configuration
OLLAMA_API_KEY: str | None = None
OLLAMA_CLOUD_URL: str = "https://ollama.com"

# Memory Extraction (hardcoded, not used yet)
MEM_EXTRACT_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] = "openai"
MEM_EXTRACT_MODEL: str = "gpt-4o-mini"
```

```python
# src/executive_assistant/config/llm_factory.py

MODEL_CONFIGS = {
    "anthropic": {
        "default": "claude-sonnet-4-5-20250929",
        "fast": "claude-3-5-haiku-20241022",
    },
    "openai": {
        "default": "gpt-5.1",
        "fast": "gpt-4o-mini",
    },
    "zhipu": {
        "default": "glm-4-plus",
        "fast": "glm-4-flash",
    },
    "ollama": {
        "default": "deepseek-v3.2:cloud",
        "fast": "deepseek-v3.2:cloud",
        "cloud": "deepseek-v3.2:cloud",
    },
}
```

---

## Proposed Changes

### 1. No Default Models - Explicit Configuration Required

**Change philosophy:** `MODEL_CONFIGS` no longer contains default models. Users MUST configure models via `.env`. If not configured, Executive Assistant refuses to start with a clear error message.

```python
# NEW: MODEL_CONFIGS only contains model aliases for validation
# No default model names - users must provide them
MODEL_ALIASES = ["default", "fast"]

# Provider-specific model name patterns for validation
MODEL_PATTERNS = {
    "anthropic": r"^claude-",  # Must start with "claude-"
    "openai": r"^(gpt|o1)-",   # Must start with "gpt-" or "o1-"
    "zhipu": r"^glm-",         # Must start with "glm-"
    "ollama": r".+",            # Any pattern allowed for Ollama
}
```

### 2. Startup Validation Function

```python
def validate_llm_config() -> None:
    """Validate LLM configuration on startup.

    Raises:
        ValueError: If configuration is invalid, with descriptive message.
    """
    import re
    import logging

    logger = logging.getLogger(__name__)
    errors = []

    provider = settings.DEFAULT_LLM_PROVIDER

    # Check provider-specific model overrides
    provider_upper = provider.upper()
    default_model = getattr(settings, f"{provider_upper}_DEFAULT_MODEL", None)
    fast_model = getattr(settings, f"{provider_upper}_FAST_MODEL", None)

    # Check global overrides as fallback
    if not default_model:
        default_model = settings.DEFAULT_LLM_MODEL
    if not fast_model:
        fast_model = settings.FAST_LLM_MODEL

    # Validate models are set
    if not default_model:
        errors.append(
            f"No default model configured for provider '{provider}'. "
            f"Set {provider_upper}_DEFAULT_MODEL or DEFAULT_LLM_MODEL."
        )
    if not fast_model:
        errors.append(
            f"No fast model configured for provider '{provider}'. "
            f"Set {provider_upper}_FAST_MODEL or FAST_LLM_MODEL."
        )

    # Validate model name patterns
    pattern = MODEL_PATTERNS.get(provider)
    if pattern:
        if default_model and not re.match(pattern, default_model):
            errors.append(
                f"Invalid default model '{default_model}' for {provider}. Please check model name."
            )
        if fast_model and not re.match(pattern, fast_model):
            errors.append(
                f"Invalid fast model '{fast_model}' for {provider}. Please check model name."
            )

    # Validate Ollama-specific config
    if provider == "ollama":
        if settings.OLLAMA_MODE == "cloud" and not settings.OLLAMA_CLOUD_API_KEY:
            errors.append(
                "OLLAMA_MODE=cloud requires OLLAMA_CLOUD_API_KEY to be set. "
                "Use OLLAMA_MODE=local for local Ollama (no API key required)."
            )

    # Check API key for cloud providers
    if provider in ["anthropic", "openai", "zhipu"]:
        api_key_var = f"{provider_upper}_API_KEY"
        if provider == "zhipu":
            api_key_var = "ZHIPUAI_API_KEY"
        if not getattr(settings, api_key_var, None):
            errors.append(
                f"{api_key_var} not set for {provider} provider."
            )

    if errors:
        error_msg = "LLM configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"LLM config validated: {provider} (default={default_model}, fast={fast_model})")
```

### 3. Main Agent Model Override (All Providers)

```python
# New env vars - global overrides
DEFAULT_LLM_MODEL: str | None = None  # Override default model (all providers)
FAST_LLM_MODEL: str | None = None      # Override fast model (all providers)

# Provider-specific model overrides (optional, higher priority)
ANTHROPIC_DEFAULT_MODEL: str | None = None
ANTHROPIC_FAST_MODEL: str | None = None
OPENAI_DEFAULT_MODEL: str | None = None
OPENAI_FAST_MODEL: str | None = None
ZHIPU_DEFAULT_MODEL: str | None = None
ZHIPU_FAST_MODEL: str | None = None
OLLAMA_DEFAULT_MODEL: str | None = None
OLLAMA_FAST_MODEL: str | None = None
```

**Priority Order (highest to lowest):**
1. Provider-specific env var (e.g., `ANTHROPIC_DEFAULT_MODEL`)
2. Global override env var (e.g., `DEFAULT_LLM_MODEL`)
3. **Error: No default configured** (was: Hardcoded `MODEL_CONFIGS` defaults)

### 4. Memory Extraction Config (Fixed)

```python
# Now uses alias system instead of hardcoded model
MEM_EXTRACT_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = None
MEM_EXTRACT_MODEL: str = "fast"  # Changed from "gpt-4o-mini"
MEM_EXTRACT_TEMPERATURE: float = 0.0

# If MEM_EXTRACT_PROVIDER not set, use DEFAULT_LLM_PROVIDER
# If MEM_EXTRACT_MODEL is "default" or "fast", resolve via provider's config
```

### 5. OCR Structured Output Config

```python
OCR_STRUCTURED_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = None
OCR_STRUCTURED_MODEL: str = "fast"  # Can be "default", "fast", or specific model name
```

### 6. Ollama Local vs Cloud Mode

```python
# Ollama Configuration
OLLAMA_MODE: Literal["cloud", "local"] = "cloud"

# Cloud Mode (requires API key)
OLLAMA_CLOUD_API_KEY: str | None = None
OLLAMA_CLOUD_URL: str = "https://ollama.com"

# Local Mode (no API key needed)
OLLAMA_LOCAL_URL: str = "http://localhost:11434"

# Backward compatibility: map old OLLAMA_API_KEY to OLLAMA_CLOUD_API_KEY
OLLAMA_API_KEY: str | None = None  # Deprecated
```

**API Key Handling:**

| Mode | API Key Required | Which Env Var |
|------|-----------------|---------------|
| `OLLAMA_MODE=local` | No | None (local Ollama doesn't need key) |
| `OLLAMA_MODE=cloud` | Yes | `OLLAMA_CLOUD_API_KEY` |

**Backward Compatibility:**
- Existing `OLLAMA_API_KEY` will be mapped to `OLLAMA_CLOUD_API_KEY` via `@model_validator`
- If both set, `OLLAMA_CLOUD_API_KEY` takes priority

---

## Complete `.env` Example

```bash
# ============================================================================
# LLM Configuration - REQUIRED
# ============================================================================
# You MUST configure at least one provider's models for Executive Assistant to start.

# Main Agent Provider (choose one)
DEFAULT_LLM_PROVIDER=anthropic
# DEFAULT_LLM_PROVIDER=openai
# DEFAULT_LLM_PROVIDER=zhipu
# DEFAULT_LLM_PROVIDER=ollama

# ----------------------------------------------------------------------------
# Anthropic Configuration
# ----------------------------------------------------------------------------
# Required when DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_DEFAULT_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_FAST_MODEL=claude-3-5-haiku-20241022

# ----------------------------------------------------------------------------
# OpenAI Configuration
# ----------------------------------------------------------------------------
# Required when DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_DEFAULT_MODEL=gpt-4o
OPENAI_FAST_MODEL=gpt-4o-mini

# ----------------------------------------------------------------------------
# Zhipu Configuration
# ----------------------------------------------------------------------------
# Required when DEFAULT_LLM_PROVIDER=zhipu
ZHIPUAI_API_KEY=xxxxx
ZHIPU_DEFAULT_MODEL=glm-4-plus
ZHIPU_FAST_MODEL=glm-4-flash

# ----------------------------------------------------------------------------
# Ollama Configuration
# ----------------------------------------------------------------------------
# Required when DEFAULT_LLM_PROVIDER=ollama

# Ollama Mode: "cloud" (requires API key) or "local" (no API key)
OLLAMA_MODE=local

# Cloud Mode Settings (when OLLAMA_MODE=cloud)
# OLLAMA_CLOUD_API_KEY=your_ollama_cloud_api_key
# OLLAMA_CLOUD_URL=https://ollama.com

# Local Mode Settings (when OLLAMA_MODE=local)
# No API key needed for local!
OLLAMA_LOCAL_URL=http://localhost:11434

# Ollama models (required)
OLLAMA_DEFAULT_MODEL=llama3.2
OLLAMA_FAST_MODEL=llama3.2

# Note: For backward compatibility, old OLLAMA_API_KEY still works
# (automatically mapped to OLLAMA_CLOUD_API_KEY)

# ----------------------------------------------------------------------------
# Global Model Overrides (Optional)
# ----------------------------------------------------------------------------
# These apply to all providers but are overridden by provider-specific vars
# DEFAULT_LLM_MODEL=claude-sonnet-4-5-20250929
# FAST_LLM_MODEL=claude-3-5-haiku-20241022

# ============================================================================
# Memory Extraction Configuration (Optional)
# ============================================================================

# Provider for memory extraction (defaults to DEFAULT_LLM_PROVIDER if not set)
# MEM_EXTRACT_PROVIDER=anthropic

# Model for memory extraction
# Use "default", "fast", or specific model name
MEM_EXTRACT_MODEL=fast  # Uses provider's fast model
# MEM_EXTRACT_MODEL=default  # Uses provider's default model
# MEM_EXTRACT_MODEL=claude-3-5-haiku-20241022  # Specific model name

MEM_EXTRACT_TEMPERATURE=0.0

# ============================================================================
# OCR Structured Output Configuration (Optional)
# ============================================================================

# Provider for OCR structured output (defaults to DEFAULT_LLM_PROVIDER if not set)
# OCR_STRUCTURED_PROVIDER=anthropic

# Model for OCR structured output
# "fast" is recommended for OCR (cheaper/faster models)
OCR_STRUCTURED_MODEL=fast
# OCR_STRUCTURED_MODEL=default
```

---

## Implementation Changes

### File: `src/executive_assistant/config/settings.py`

```python
from pydantic import BaseModel, FieldValidationInfo, field_validator, model_validator


class Settings(BaseSettings):
    # ============================================================================
    # LLM Configuration
    # ============================================================================

    DEFAULT_LLM_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] = "anthropic"

    # Global Model Overrides (apply to all providers)
    DEFAULT_LLM_MODEL: str | None = None
    FAST_LLM_MODEL: str | None = None

    # Provider-Specific Model Overrides (higher priority)
    ANTHROPIC_DEFAULT_MODEL: str | None = None
    ANTHROPIC_FAST_MODEL: str | None = None
    OPENAI_DEFAULT_MODEL: str | None = None
    OPENAI_FAST_MODEL: str | None = None
    ZHIPU_DEFAULT_MODEL: str | None = None
    ZHIPU_FAST_MODEL: str | None = None
    OLLAMA_DEFAULT_MODEL: str | None = None
    OLLAMA_FAST_MODEL: str | None = None

    # API Keys
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ZHIPUAI_API_KEY: str | None = None

    # ============================================================================
    # Ollama Configuration
    # ============================================================================

    OLLAMA_MODE: Literal["cloud", "local"] = "cloud"

    # Cloud Mode
    OLLAMA_CLOUD_API_KEY: str | None = None
    OLLAMA_CLOUD_URL: str = "https://ollama.com"

    # Local Mode
    OLLAMA_LOCAL_URL: str = "http://localhost:11434"

    # Backward compatibility (deprecated, maps to CLOUD_API_KEY)
    OLLAMA_API_KEY: str | None = None

    @model_validator(mode="after")
    @classmethod
    def map_ollama_api_key_to_cloud(cls, settings: "Settings") -> "Settings":
        """Map legacy OLLAMA_API_KEY to OLLAMA_CLOUD_API_KEY."""
        if not settings.OLLAMA_CLOUD_API_KEY and settings.OLLAMA_API_KEY:
            settings.OLLAMA_CLOUD_API_KEY = settings.OLLAMA_API_KEY
        return settings

    # ============================================================================
    # Memory Extraction
    # ============================================================================

    MEM_AUTO_EXTRACT: bool = False
    MEM_CONFIDENCE_MIN: float = 0.6
    MEM_MAX_PER_TURN: int = 3
    MEM_EXTRACT_MODEL: str = "fast"  # Changed: was "gpt-4o-mini"
    MEM_EXTRACT_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = None
    MEM_EXTRACT_TEMPERATURE: float = 0.0

    @field_validator("MEM_EXTRACT_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_extract(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None

    # ============================================================================
    # OCR Structured Output
    # ============================================================================

    OCR_STRUCTURED_PROVIDER: Literal["anthropic", "openai", "zhipu", "ollama"] | None = None
    OCR_STRUCTURED_MODEL: str = "fast"

    @field_validator("OCR_STRUCTURED_PROVIDER", mode="before")
    @classmethod
    def empty_string_to_none_ocr(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional provider field."""
        return v or None
```

### File: `src/executive_assistant/config/llm_factory.py`

```python
import re
import logging

from executive_assistant.config import settings

logger = logging.getLogger(__name__)

# Model aliases (no default models - users must configure)
MODEL_ALIASES = ["default", "fast"]

# Provider-specific model name patterns for validation
MODEL_PATTERNS = {
    "anthropic": r"^claude-",  # Must start with "claude-"
    "openai": r"^(gpt|o1)-",   # Must start with "gpt-" or "o1-"
    "zhipu": r"^glm-",         # Must start with "glm-"
    "ollama": r".+",            # Any pattern allowed for Ollama
}


def validate_llm_config() -> None:
    """Validate LLM configuration on startup.

    Raises:
        ValueError: If configuration is invalid, with descriptive message.
    """
    errors = []

    provider = settings.DEFAULT_LLM_PROVIDER

    # Check provider-specific model overrides
    provider_upper = provider.upper()
    default_model = getattr(settings, f"{provider_upper}_DEFAULT_MODEL", None)
    fast_model = getattr(settings, f"{provider_upper}_FAST_MODEL", None)

    # Check global overrides as fallback
    if not default_model:
        default_model = settings.DEFAULT_LLM_MODEL
    if not fast_model:
        fast_model = settings.FAST_LLM_MODEL

    # Validate models are set
    if not default_model:
        errors.append(
            f"No default model configured for provider '{provider}'. "
            f"Set {provider_upper}_DEFAULT_MODEL or DEFAULT_LLM_MODEL."
        )
    if not fast_model:
        errors.append(
            f"No fast model configured for provider '{provider}'. "
            f"Set {provider_upper}_FAST_MODEL or FAST_LLM_MODEL."
        )

    # Validate model name patterns
    pattern = MODEL_PATTERNS.get(provider)
    if pattern:
        if default_model and not re.match(pattern, default_model):
            errors.append(
                f"Invalid default model '{default_model}' for {provider}. Please check model name."
            )
        if fast_model and not re.match(pattern, fast_model):
            errors.append(
                f"Invalid fast model '{fast_model}' for {provider}. Please check model name."
            )

    # Validate Ollama-specific config
    if provider == "ollama":
        if settings.OLLAMA_MODE == "cloud" and not settings.OLLAMA_CLOUD_API_KEY:
            errors.append(
                "OLLAMA_MODE=cloud requires OLLAMA_CLOUD_API_KEY to be set. "
                "Use OLLAMA_MODE=local for local Ollama (no API key required)."
            )

    # Check API key for cloud providers
    if provider in ["anthropic", "openai", "zhipu"]:
        api_key_var = f"{provider_upper}_API_KEY"
        if provider == "zhipu":
            api_key_var = "ZHIPUAI_API_KEY"
        if not getattr(settings, api_key_var, None):
            errors.append(
                f"{api_key_var} not set for {provider} provider."
            )

    if errors:
        error_msg = "LLM configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"LLM config validated: {provider} (default={default_model}, fast={fast_model})")


def _get_model_config(provider: str, model: str = "default") -> str:
    """Get model name from config or env override.

    Priority (highest to lowest):
    1. Provider-specific env var (e.g., ANTHROPIC_DEFAULT_MODEL)
    2. Global env var (DEFAULT_LLM_MODEL or FAST_LLM_MODEL)
    3. Error: No model configured (was: Hardcoded MODEL_CONFIGS defaults)

    Args:
        provider: LLM provider (anthropic, openai, zhipu, ollama)
        model: Model variant (default, fast) or specific model name

    Returns:
        Model name string

    Raises:
        ValueError: If no model is configured
    """
    provider_upper = provider.upper()

    # If not an alias, return as-is (specific model name)
    if model not in MODEL_ALIASES:
        return model

    # Check provider-specific env var first (highest priority)
    env_var = f"{provider_upper}_{model.upper()}_MODEL"
    env_value = getattr(settings, env_var, None)
    if env_value:
        return env_value

    # Check global env vars
    global_var = f"{model.upper()}_LLM_MODEL"
    global_value = getattr(settings, global_var, None)
    if global_value:
        return global_value

    # No model configured - raise error
    raise ValueError(
        f"No model configured for {provider} '{model}'. "
        f"Set {env_var} or {global_var} in your .env file."
    )


def _get_ollama_config() -> tuple[str, str, str | None]:
    """Get Ollama base_url, model, and API key based on mode.

    Returns:
        (base_url, model, api_key or None)

    Raises:
        ValueError: If cloud mode selected but no API key configured
    """
    # Check for provider-specific override first
    provider_model = getattr(settings, "OLLAMA_DEFAULT_MODEL", None)

    if settings.OLLAMA_MODE == "local":
        base_url = settings.OLLAMA_LOCAL_URL
        model = provider_model or settings.OLLAMA_LOCAL_MODEL
        api_key = None  # Local doesn't need API key
    else:  # cloud
        api_key = settings.OLLAMA_CLOUD_API_KEY
        if not api_key:
            raise ValueError(
                "OLLAMA_CLOUD_API_KEY not set for Ollama Cloud mode. "
                "Set OLLAMA_CLOUD_API_KEY or use OLLAMA_MODE=local for local Ollama."
            )
        base_url = settings.OLLAMA_CLOUD_URL
        model = provider_model or settings.OLLAMA_CLOUD_MODEL

    return base_url, model, api_key


@staticmethod
def _create_ollama(model: str = "default", **kwargs) -> BaseChatModel:
    """Create Ollama model (cloud or local)."""
    base_url, ollama_model, api_key = _get_ollama_config()

    # Handle "fast" variant
    if model == "fast":
        provider_fast = getattr(settings, "OLLAMA_FAST_MODEL", None)
        if provider_fast:
            ollama_model = provider_fast

    # Build ChatOllama kwargs
    ollama_kwargs = {
        "model": ollama_model,
        "base_url": base_url,
        "temperature": kwargs.get("temperature", 0.7),
        "num_ctx": kwargs.get("max_tokens", 4096),
    }

    # Only add API key for cloud mode
    if api_key:
        client_kwargs = kwargs.pop("client_kwargs", {})
        client_kwargs.setdefault("headers", {})
        client_kwargs["headers"]["Authorization"] = f"Bearer {api_key}"
        ollama_kwargs["client_kwargs"] = client_kwargs

    ollama_kwargs.update(kwargs)
    return ChatOllama(**ollama_kwargs)
```

### Startup Integration

Add to application startup (e.g., `src/executive_assistant/channels/management_commands.py` or main entry point):

```python
from executive_assistant.config.llm_factory import validate_llm_config

# Call during application initialization
try:
    validate_llm_config()
except ValueError as e:
    logger.error(str(e))
    print(f"\n{e}\n")
    print("Please configure your LLM settings in .env file.")
    sys.exit(1)
```

---

## Summary of Env Vars

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| **Provider Selection** |
| `DEFAULT_LLM_PROVIDER` | No | `anthropic` | Main LLM provider |
| **Global Model Overrides** |
| `DEFAULT_LLM_MODEL` | Yes* | `None` | Default model for all providers |
| `FAST_LLM_MODEL` | Yes* | `None` | Fast model for all providers |
| **Anthropic** |
| `ANTHROPIC_API_KEY` | Yes† | `None` | Anthropic API key |
| `ANTHROPIC_DEFAULT_MODEL` | Yes* | `None` | Anthropic default model |
| `ANTHROPIC_FAST_MODEL` | Yes* | `None` | Anthropic fast model |
| **OpenAI** |
| `OPENAI_API_KEY` | Yes† | `None` | OpenAI API key |
| `OPENAI_DEFAULT_MODEL` | Yes* | `None` | OpenAI default model |
| `OPENAI_FAST_MODEL` | Yes* | `None` | OpenAI fast model |
| **Zhipu** |
| `ZHIPUAI_API_KEY` | Yes† | `None` | Zhipu API key |
| `ZHIPU_DEFAULT_MODEL` | Yes* | `None` | Zhipu default model |
| `ZHIPU_FAST_MODEL` | Yes* | `None` | Zhipu fast model |
| **Ollama** |
| `OLLAMA_MODE` | No | `cloud` | `cloud` or `local` |
| `OLLAMA_CLOUD_API_KEY` | ‡ | `None` | API key for ollama.com |
| `OLLAMA_CLOUD_URL` | No | `https://ollama.com` | Ollama Cloud endpoint |
| `OLLAMA_LOCAL_URL` | No | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_DEFAULT_MODEL` | Yes* | `None` | Ollama default model |
| `OLLAMA_FAST_MODEL` | Yes* | `None` | Ollama fast model |
| **Memory Extraction** |
| `MEM_EXTRACT_PROVIDER` | No | `None` | Provider (defaults to main) |
| `MEM_EXTRACT_MODEL` | No | `fast` | Model variant for extraction |
| `MEM_EXTRACT_TEMPERATURE` | No | `0.0` | Temperature for extraction |
| **OCR Structured Output** |
| `OCR_STRUCTURED_PROVIDER` | No | `None` | Provider (defaults to main) |
| `OCR_STRUCTURED_MODEL` | No | `fast` | Model variant for OCR |

*Required: At least one of global or provider-specific model must be set.
†Required: API key required when using that provider.
‡Required: Only when `OLLAMA_MODE=cloud`.

---

## Where "fast" Model Is Used

| Location | Current Model | Purpose |
|----------|---------------|---------|
| **OCR Structured Output** | `fast` → provider's fast model | Extract structured data from OCR results |
| **LangChain Middleware** | (optional) | Summarization, topic classification (if enabled) |
| **Memory Extraction** | (not implemented yet) | Extract facts from conversations |

**"fast" resolves to provider's configured fast model:**
- Anthropic: `ANTHROPIC_FAST_MODEL` (e.g., `claude-3-5-haiku-20241022`)
- OpenAI: `OPENAI_FAST_MODEL` (e.g., `gpt-4o-mini`)
- Zhipu: `ZHIPU_FAST_MODEL` (e.g., `glm-4-flash`)
- Ollama: `OLLAMA_FAST_MODEL` (user-defined)

---

## Migration Notes

1. **Breaking change** - Users MUST configure models via `.env`. No fallback defaults.
2. **Validation on startup** - Executive Assistant will refuse to start with clear error messages if misconfigured.
3. **Backward compatible** - `OLLAMA_API_KEY` maps to `OLLAMA_CLOUD_API_KEY`.
4. **Model pattern validation** - Catches provider mismatches (e.g., `gpt-4o` for Anthropic).

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/executive_assistant/config/settings.py` | Add new env vars, fix validators, change MEM_EXTRACT_MODEL default |
| `src/executive_assistant/config/llm_factory.py` | Add `validate_llm_config()`, update `_get_model_config()`, add `_get_ollama_config()`, update `_create_ollama()` |
| `src/executive_assistant/main.py` | Call `validate_llm_config()` on startup |
| `.env.example` | Update with all new options, mark required fields |
| `.env` | Update with new configuration format |

---

## Implementation Status

**Status: ✅ COMPLETE** (2025-01-17)

All proposed changes have been implemented and tested for syntax correctness.

### Files Modified

| File | Lines Changed | Description |
|------|---------------|-------------|
| `src/executive_assistant/config/settings.py` | ~50 | Added LLM env vars, Ollama mode config, fixed validators |
| `src/executive_assistant/config/llm_factory.py` | ~330 | Complete rewrite: validation, model resolution, Ollama config |
| `src/executive_assistant/main.py` | ~10 | Added startup validation call |
| `.env.example` | ~50 | Updated LLM configuration section |
| `.env` | ~50 | Updated with new configuration format |
| `discussions/llm-config-plan.md` | Updated | This document |

### Implementation Details

#### 1. Settings (`src/executive_assistant/config/settings.py`)

Added environment variables:
```python
# Global Model Overrides
DEFAULT_LLM_MODEL: str | None = None
FAST_LLM_MODEL: str | None = None

# Provider-Specific Model Overrides
ANTHROPIC_DEFAULT_MODEL: str | None = None
ANTHROPIC_FAST_MODEL: str | None = None
OPENAI_DEFAULT_MODEL: str | None = None
OPENAI_FAST_MODEL: str | None = None
ZHIPU_DEFAULT_MODEL: str | None = None
ZHIPU_FAST_MODEL: str | None = None
OLLAMA_DEFAULT_MODEL: str | None = None
OLLAMA_FAST_MODEL: str | None = None

# Ollama Mode
OLLAMA_MODE: Literal["cloud", "local"] = "cloud"
OLLAMA_CLOUD_API_KEY: str | None = None
OLLAMA_CLOUD_URL: str = "https://ollama.com"
OLLAMA_LOCAL_URL: str = "http://localhost:11434"
```

Fixed validators:
- Changed from `@field_validator` to `@model_validator` for OLLAMA_API_KEY mapping
- Split `empty_string_to_none` into separate validators for each field

Changed defaults:
- `MEM_EXTRACT_MODEL`: `"gpt-4o-mini"` → `"fast"`
- `MEM_EXTRACT_PROVIDER`: `"openai"` → `None` (defaults to main provider)

#### 2. LLM Factory (`src/executive_assistant/config/llm_factory.py`)

Removed `MODEL_CONFIGS` with hardcoded defaults. Added:

```python
MODEL_ALIASES = ["default", "fast"]

MODEL_PATTERNS = {
    "anthropic": r"^claude-",
    "openai": r"^(gpt|o1)-",
    "zhipu": r"^glm-",
    "ollama": r".+",
}
```

New functions:
- `validate_llm_config()` - Startup validation with pattern matching
- `_get_model_config()` - Model resolution with priority order
- `_get_ollama_config()` - Ollama mode-based config
- `get_model_for_extraction()` - Helper for memory extraction
- `get_model_for_ocr()` - Helper for OCR structured output

#### 3. Startup Validation (`src/executive_assistant/main.py`)

```python
from executive_assistant.config.llm_factory import validate_llm_config

async def main() -> None:
    configure_logging()

    # Validate LLM configuration on startup
    try:
        validate_llm_config()
    except ValueError as e:
        print(f"\n{e}\n")
        print("Please configure your LLM settings in .env file.")
        sys.exit(1)

    model = create_model()
    ...
```

### Validation Behavior

Executive Assistant will refuse to start with helpful error messages:

```
LLM configuration validation failed:
  - No default model configured for provider 'anthropic'. Set ANTHROPIC_DEFAULT_MODEL or DEFAULT_LLM_MODEL.
  - No fast model configured for provider 'anthropic'. Set ANTHROPIC_FAST_MODEL or FAST_LLM_MODEL.
  - ANTHROPIC_API_KEY not set for anthropic provider.

Please configure your LLM settings in .env file.
```

### Testing

- Syntax check passed for all modified modules
- Import validation successful
- Startup validation logic implemented

### Migration Path for Users

1. Update `.env` with new LLM configuration format
2. Set at least one provider's models (default + fast)
3. Set API key for cloud providers
4. For Ollama: choose `OLLAMA_MODE=cloud` or `OLLAMA_MODE=local`
