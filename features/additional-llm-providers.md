# Additional LLM Providers Integration Plan

## Overview

This document outlines the plan for integrating additional LLM providers into the Executive Assistant:
- **Gemini** (Google)
- **Qwen** (Alibaba/Tongyi)
- **Kimi K2** (Moonshot AI)
- **MiniMax M2**

## Current Architecture Review

The existing system uses a factory pattern in `src/executive_assistant/config/llm_factory.py`:
- `LLMFactory.create(provider, model, **kwargs)` returns `BaseChatModel` instances
- Provider-specific methods: `_create_openai`, `_create_anthropic`, `_create_zhipu`, `_create_ollama`
- Configuration via `docker/config.yaml` and environment variables

---

## 1. Gemini (Google) Integration

### LangChain Package
```bash
pip install langchain-google-genai
```

### Environment Variables
```bash
# Gemini API Key (primary)
GOOGLE_API_KEY=your-google-api-key
# Alternative (fallback)
GEMINI_API_KEY=your-gemini-api-key

# Optional: Force Vertex AI backend
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

### Configuration (config.yaml)
```yaml
llm:
  default_provider: openai  # can be gemini

  gemini:
    default_model: gemini-2.5-flash
    fast_model: gemini-2.5-flash
    # Optional: Vertex AI settings
    vertexai: false
    project: null
    location: us-central1
```

### Implementation
```python
@staticmethod
def _create_gemini(model: str = "default", **kwargs) -> ChatGoogleGenerativeAI:
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.GOOGLE_API_KEY and not settings.GEMINI_API_KEY:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")

    model_name = _get_model_config("gemini", model)
    api_key = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY

    # Vertex AI backend detection
    config = get_llm_config().get("gemini", {})
    vertexai = config.get("vertexai", False)

    params = {
        "model": model_name,
        "api_key": api_key,
        "temperature": kwargs.get("temperature", 1.0),  # Gemini 3.0+ defaults to 1.0
        "max_tokens": kwargs.get("max_tokens", None),
        "timeout": kwargs.get("timeout", None),
        "max_retries": kwargs.get("max_retries", 2),
    }

    if vertexai or settings.GOOGLE_CLOUD_PROJECT:
        params.update({
            "vertexai": True,
            "project": settings.GOOGLE_CLOUD_PROJECT or config.get("project"),
            "location": config.get("location", "us-central1"),
        })

    return ChatGoogleGenerativeAI(**params)
```

### Major Models to Support

#### Gemini 3 Series (Latest - Nov/Dec 2025)

| Model | Context | Features | Best For |
|-------|---------|----------|----------|
| `gemini-3-pro-preview` | 1M+ tokens | Thinking, multimodal, tool calling | Most intelligent, complex reasoning, coding, agentic tasks |
| `gemini-3-pro-image-preview` | 65K input / 32K output | Image generation | Text-to-image generation |
| `gemini-3-flash-preview` | 1M+ tokens | Thinking, multimodal, tool calling | Most balanced, speed + scale + intelligence |

#### Gemini 2.5 Series (June 2025)

| Model | Context | Features | Best For |
|-------|---------|----------|----------|
| `gemini-2.5-flash` | 1M+ tokens | Thinking, multimodal, tool calling | Best price-performance, large scale processing (default) |
| `gemini-2.5-flash-lite` | 1M+ tokens | Ultra-fast, cost-efficient | High throughput, simple tasks |
| `gemini-2.5-pro` | 1M+ tokens | Advanced thinking, multimodal | Complex reasoning, math, STEM, long context |
| `gemini-2.5-flash-image` | 65K input / 32K output | Image generation | Fast image generation |
| `gemini-2.5-flash-preview-09-2025` | 1M+ tokens | Preview features | Testing latest capabilities |
| `gemini-2.5-flash-lite-preview-09-2025` | 1M+ tokens | Preview features | Testing latest lite capabilities |

#### Specialized Models

| Model | Context | Features | Best For |
|-------|---------|----------|----------|
| `gemini-2.5-flash-preview-tts` | 8K input / 16K output | Text-to-speech | Voice synthesis |
| `gemini-2.5-pro-preview-tts` | 8K input / 16K output | High-quality TTS | Professional voice output |
| `gemini-2.5-flash-native-audio-preview-12-2025` | 131K input / 8K output | Audio input/output | Audio processing |

#### Deprecated (Shut down March 31, 2026)
- `gemini-2.0-flash`
- `gemini-2.0-flash-lite`

**Recommendation:**
- **Default**: `gemini-2.5-flash` (best price-performance, production-ready)
- **Fast**: `gemini-2.5-flash-lite` (ultra-fast, high throughput)
- **High Performance**: `gemini-3-pro-preview` (most intelligent, complex tasks)
- **Multimodal**: `gemini-3-pro-preview` (images, video, audio, PDF)
- **Image Gen**: `gemini-2.5-flash-image` (stable) or `gemini-3-pro-image-preview`

---

## 2. Qwen (Alibaba) Integration

### LangChain Package
```bash
pip install langchain-qwq
```

### Environment Variables
```bash
# Alibaba DashScope API Key
DASHSCOPE_API_KEY=your-dashscope-api-key
```

### Configuration (config.yaml)
```yaml
llm:
  qwen:
    default_model: qwen-flash
    fast_model: qwen-flash
```

### Implementation
```python
@staticmethod
def _create_qwen(model: str = "default", **kwargs) -> ChatQwen:
    from langchain_qwq import ChatQwen

    if not settings.DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY not set")

    model_name = _get_model_config("qwen", model)

    return ChatQwen(
        model=model_name,
        api_key=settings.DASHSCOPE_API_KEY,
        max_tokens=kwargs.get("max_tokens", 3_000),
        temperature=kwargs.get("temperature", 0.7),
        timeout=kwargs.get("timeout", None),
        max_retries=kwargs.get("max_retries", 2),
    )
```

### Major Models to Support

#### Commercial API Models (Alibaba Cloud)

| Model | Context | Best For |
|-------|---------|----------|
| `qwen-max-latest` | Up to 32K tokens | Most capable, complex tasks |
| `qwen-plus-latest` | Up to 32K tokens | Balanced performance |
| `qwen-flash` | 8K tokens | Fast, cost-effective (default) |
| `qwen-turbo-latest` | 8K tokens | Fast, simple tasks |
| `qwen-vl-max-latest` | Variable | Image/video understanding |
| `qwen-vl-plus-latest` | Variable | Vision, balanced |
| `qwq-32b-preview` | 32K tokens | Advanced reasoning |
| `qvq-72b-preview` | Variable | Multimodal reasoning |
| `qwen-coder-plus` | Variable | Code generation |
| `qwen2.5-coder-32b-instruct` | Variable | Coding tasks |

**Note**: Models with `-latest` suffix automatically point to the latest stable version.

#### Open Source Weights (For Local Deployment)

**Qwen3-Next Series** (Sept 2025 - High Efficiency):

| Model | Type | Context | Features |
|-------|------|---------|----------|
| `Qwen/Qwen3-Next-80B-A3B-Instruct` | Instruct | 262K-1M tokens | **10x throughput** for 32K+ context, hybrid attention, extreme efficiency |

**Qwen3-Next Highlights:**
- **Ultra-Efficient**: 80B total / 3B activated parameters (High-Sparsity MoE)
- **10x Inference Speed**: For contexts over 32K tokens
- **Performs on par with Qwen3-235B-A22B** on many benchmarks
- **Hybrid Attention**: Gated DeltaNet + Gated Attention
- **Native 262K context**, extensible to 1M+ tokens with YaRN
- **Non-thinking only** (no thinking mode)

**Qwen3-2507 Series** (Jan 2026, 256K-1M tokens):

| Model | Type | Context | Features |
|-------|------|---------|----------|
| `Qwen/Qwen3-235B-A22B-Instruct-2507` | Instruct | 256K-1M tokens | Non-thinking, general-purpose |
| `Qwen/Qwen3-235B-A22B-Thinking-2507` | Thinking | 256K-1M tokens | Complex reasoning, math, coding |
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | Instruct | 256K-1M tokens | Non-thinking, balanced |
| `Qwen/Qwen3-30B-A3B-Thinking-2507` | Thinking | 256K-1M tokens | Reasoning, medium size |
| `Qwen/Qwen3-4B-Instruct-2507` | Instruct | 256K-1M tokens | Lightweight, non-thinking |
| `Qwen/Qwen3-4B-Thinking-2507` | Thinking | 256K-1M tokens | Lightweight, reasoning |

**Qwen3 (Qwen3-2504)** (April 2025):
- `Qwen/Qwen3-8B` - Base model
- `Qwen/Qwen3-14B` - Medium size
- `Qwen/Qwen3-32B` - Large size

**Recommendation for LangChain Integration:**
- **Default (API)**: `qwen-flash` (fast, cost-effective)
- **Fast (API)**: `qwen-turbo-latest`
- **High Performance (API)**: `qwen-max-latest`
- **Coding (API)**: `qwen-coder-plus` or `qwen2.5-coder-32b-instruct`
- **Vision (API)**: `qwen-vl-max-latest`
- **Reasoning (API)**: `qwq-32b-preview`

For local deployment via Ollama/vLLM/SGLang:
- **Efficient Long Context**: `Qwen/Qwen3-Next-80B-A3B-Instruct` ⭐ (10x throughput, 262K-1M context)
- **General Use**: `qwen3:8b`
- **Complex Reasoning**: `qwen3:30b-a3b-thinking-2507`
- **Lightweight**: `qwen3:4b`

---

## 3. Kimi K2 (Moonshot AI) Integration

### API Type
**OpenAI-Compatible API** - Can use standard `ChatOpenAI` with custom base URL

### Environment Variables
```bash
# Moonshot AI API Key
MOONSHOT_API_KEY=your-moonshot-api-key

# Optional: Custom base URL
MOONSHOT_API_BASE=https://api.moonshot.ai/v1
```

### Configuration (config.yaml)
```yaml
llm:
  kimi:
    default_model: kimi-k2-5
    fast_model: kimi-k2-5
    api_base: https://api.moonshot.ai/v1
```

### Implementation
```python
@staticmethod
def _create_kimi(model: str = "default", **kwargs) -> ChatOpenAI:
    from langchain_openai import ChatOpenAI

    if not settings.MOONSHOT_API_KEY:
        raise ValueError("MOONSHOT_API_KEY not set")

    model_name = _get_model_config("kimi", model)
    config = get_llm_config().get("kimi", {})
    api_base = config.get("api_base", "https://api.moonshot.ai/v1")

    return ChatOpenAI(
        model=model_name,
        api_key=settings.MOONSHOT_API_KEY,
        base_url=api_base,
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 8192),
        timeout=kwargs.get("timeout", None),
        max_retries=kwargs.get("max_retries", 2),
    )
```

### Major Models to Support

| Model | Context | Features | Best For |
|-------|---------|----------|----------|
| `kimi-k2.5` | 256K tokens | Native multimodal, agentic, agent swarm | Latest, most capable (default) |
| `kimi-k2` | 256K tokens | Long context, coding | Long context, coding |
| `kimi-k2-coder` | 256K tokens | Code generation | Coding tasks |
| `kimi-k2-reasoner` | 256K tokens | Complex reasoning | Reasoning tasks |

**Key Features:**
- **Agent Swarm**: Kimi K2.5 can coordinate up to 100 specialized AI agents simultaneously
- **4.5x Faster Execution**: Parallel processing approach vs sequential
- **50.2% on Humanity's Last Exam**: Strong benchmark performance
- **76% Lower Cost**: Compared to other frontier models

**Recommendation:**
- **Default**: `kimi-k2.5` (latest, multimodal, agent capabilities)
- **Fast**: `kimi-k2.5` (same - uses agent swarm for speed)
- **Specialized**: `kimi-k2-coder` (for coding tasks)
- **Long Context**: Any Kimi model (256K tokens)

---

## 4. MiniMax M2 Integration

### API Type
**OpenAI-Compatible OR Anthropic-Compatible API** - Two options available

### Environment Variables
```bash
# MiniMax API Key
MINIMAX_API_KEY=your-minimax-api-key

# Optional: Group ID (for multi-project setups)
MINIMAX_GROUP_ID=your-group-id
```

### Configuration (config.yaml)
```yaml
llm:
  minimax:
    default_model: MiniMax-M2
    fast_model: MiniMax-M2
    # Choose API type: openai or anthropic
    api_type: openai  # or 'anthropic'
    api_base: https://api.minimax.io/v1
```

### Implementation
```python
@staticmethod
def _create_minimax(model: str = "default", **kwargs) -> Union[ChatOpenAI, ChatAnthropic]:
    config = get_llm_config().get("minimax", {})
    api_type = config.get("api_type", "openai")

    if not settings.MINIMAX_API_KEY:
        raise ValueError("MINIMAX_API_KEY not set")

    model_name = _get_model_config("minimax", model)
    api_base = config.get(
        "api_base",
        "https://api.minimax.io/v1" if api_type == "openai" else "https://api.minimax.io/anthropic"
    )

    if api_type == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            api_key=settings.MINIMAX_API_KEY,
            base_url=api_base,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 204800),  # Ultra-long context!
            timeout=kwargs.get("timeout", None),
            max_retries=kwargs.get("max_retries", 2),
        )
    else:  # OpenAI-compatible (default)
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=settings.MINIMAX_API_KEY,
            base_url=api_base,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 204800),
            timeout=kwargs.get("timeout", None),
            max_retries=kwargs.get("max_retries", 2),
        )
```

### Major Models to Support

#### Text Models

| Model | Context | Features | Best For |
|-------|---------|----------|----------|
| `MiniMax-M2.1` | 204,800 tokens | Polyglot programming, precision code refactoring | Latest, coding (default) |
| `MiniMax-M2` | 204,800 tokens | Agentic, ultra-long context | General agentic tasks |
| `MiniMax-M2-Stable` | 204,800 tokens | High concurrency | Production workloads |
| `MiniMax-M2-Turbo` | 204,800 tokens | Faster responses | Low-latency needs |
| `MiniMax-Text-01` | 204,800 tokens | Previous generation text model | Legacy support |

#### Speech Models (TTS)

| Model | Features | Best For |
|-------|----------|----------|
| `Speech-2.6` | More human, instantly responsive | Agent voice (latest) |
| `Speech-2.5` | Broad language coverage, high voice similarity | Multilingual TTS |
| `Speech-02-turbo` | Hyper-realistic, fast | Real-time voice |
| `Speech-02-hd` | Hyper-realistic, high quality | Professional voice output |

#### Other Models

| Model | Features | Best For |
|-------|----------|----------|
| `Music-2.5` | Direct the Detail, Define the Real | Music generation |
| `Music-2.0` | Enhanced musical expression | Music generation |
| `Music-1.5` | 4-minute songs | Longer music |
| `MiniMax-Hailuo-2.3` | Video generation, 1080p, 10 seconds | High-quality video |
| `MiniMax-Hailuo-2.3-Fast` | Faster video generation | Quick video |
| `MiniMax-VL-01` | Vision-language | Image understanding |
| `Image-01` | Text-to-image, multiple sizes | Image generation |

**Key Features:**
- **Ultra-Long Context**: 204,800 tokens (~150K words)
- **Extremely Low Cost**: $0.3 per million input tokens
- **Agentic Capabilities**: Tool use, function calling
- **Reasoning Mode**: `reasoning_split=True` for thought process

**Recommendation:**
- **Default**: `MiniMax-M2.1` (latest, best for coding)
- **Fast**: `MiniMax-M2-Turbo`
- **Production**: `MiniMax-M2-Stable` (high concurrency)
- **Long Context**: Any MiniMax M2 model (204,800 tokens)
- **Voice**: `Speech-2.6` (most human)
- **Multilingual**: `Speech-2.5` (broad language coverage)

---

## 5. Settings Configuration

Add to `src/executive_assistant/config/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing ...

    # Gemini / Google
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    # Qwen / Alibaba
    DASHSCOPE_API_KEY: Optional[str] = None

    # Kimi / Moonshot
    MOONSHOT_API_KEY: Optional[str] = None
    MOONSHOT_API_BASE: str = "https://api.moonshot.ai/v1"

    # MiniMax
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_GROUP_ID: Optional[str] = None
```

---

## 6. Dependencies (pyproject.toml)

```toml
[project.optional-dependencies]
# ... existing ...
llm-extra = [
    "langchain-google-genai>=4.0.0",
    "langchain-qwq>=0.1.0",
    # Kimi uses existing langchain-openai
    # MiniMax uses existing langchain-openai or langchain-anthropic
]
```

---

## 7. Validation

Add to `src/executive_assistant/config/llm_factory.py`:

```python
# Model name patterns for validation
MODEL_PATTERNS = {
    # ... existing ...
    "gemini": r"^(gemini|gemini-2\.5|gemini-3)(?:-[a-z]+)?(?:-[0-9]+(?:-[0-9]+)?)?$",
    "qwen": r"^qwen(?:-[a-z0-9]+)?(?:-latest)?$",
    "kimi": r"^kimi-k2(?:-[a-z0-9]+)?$",
    "minimax": r"^(MiniMax-)?M2(?:-[a-z]+)?$",
}
```

---

## 8. Provider Feature Comparison

| Feature | Gemini | Qwen | Kimi | MiniMax |
|---------|--------|------|------|---------|
| **LangChain Package** | `langchain-google-genai` | `langchain-qwq` | `langchain-openai`* | `langchain-openai`* |
| **Tool Calling** | ✅ | ✅ | ✅ | ✅ |
| **Structured Output** | ✅ | ✅ | ✅ | ✅ |
| **Multimodal (Vision)** | ✅ | ✅ | ✅ | ❌ (VL only) |
| **Streaming** | ✅ | ✅ | ✅ | ✅ |
| **Async** | ✅ | ✅ | ✅ | ✅ |
| **Token Usage** | ✅ | ✅ | ✅ | ✅ |
| **Max Context** | 1M+ tokens | 32K (API) / 1M (local) | 256K tokens | 204,800 tokens |
| **Thinking Support** | ✅ (Gemini 3, 2.5) | ✅ (Qwen3-Thinking, QwQ) | ✅ | ✅ (reasoning mode) |
| **Computer Use** | ✅ (Gemini 2.5) | ❌ | ❌ | ❌ |
| **Image Generation** | ✅ (Flash Image) | ❌ | ❌ | ✅ (Image-01) |
| **Video Understanding** | ✅ | ✅ (VL models) | ✅ | ✅ (Hailuo) |
| **Audio Generation** | ✅ (TTS models) | ❌ | ❌ | ✅ (Speech models) |
| **Music Generation** | ❌ | ❌ | ❌ | ✅ (Music models) |
| **Agent Swarm** | ❌ | ❌ | ✅ (K2.5) | ❌ |
| **Open Source Weights** | ❌ | ✅ (Qwen3) | ✅ (K2) | ❌ |
| **Local Deployment** | ❌ | ✅ (Ollama/vLLM) | ✅ (Ollama) | ❌ |

*Uses OpenAI-compatible API

---

## 9. Recommended Model Selection by Use Case

### General Chat / Assistant
- **Fast**: `qwen-flash`, `gemini-2.5-flash-lite`, `MiniMax-M2-Turbo`
- **Balanced**: `gemini-2.5-flash`, `kimi-k2.5`, `qwen-plus-latest`
- **High Quality**: `gemini-3-pro-preview`, `qwen-max-latest`, `MiniMax-M2.1`

### Coding
- **Fast**: `qwen-coder-plus`, `kimi-k2-coder`
- **Advanced**: `MiniMax-M2.1`, `gemini-3-pro-preview`, `qwq-32b-preview`
- **Local**: `Qwen3-30B-A3B-Instruct-2507`

### Long Context
- **Ultra-Long**: `MiniMax-M2.1` (204,800 tokens), `kimi-k2.5` (256K tokens)
- **Very Long**: `gemini-3-pro-preview` (1M+ tokens), `gemini-2.5-pro` (1M+ tokens)
- **Extended Local (Efficient)**: `Qwen/Qwen3-Next-80B-A3B-Instruct` ⭐ (262K-1M tokens, **10x throughput**)
- **Extended Local (Standard)**: `Qwen3-235B-A22B` (up to 1M tokens with vLLM/SGLang)

### Multimodal (Vision)
- **Images**: `gemini-3-pro-preview`, `qwen-vl-max-latest`, `kimi-k2.5`
- **Video**: `gemini-3-pro-preview`, `qwen-vl-max-latest`
- **Audio**: `gemini-3-pro-preview`, `MiniMax Speech-2.6`

### Agentic / Tool Use
- **Best**: `gemini-3-pro-preview`, `MiniMax-M2.1`, `kimi-k2.5` (agent swarm)
- **Good (Efficient)**: `Qwen/Qwen3-Next-80B-A3B-Instruct` ⭐ (10x throughput for 32K+ context)
- **Good**: `qwen-max-latest`, `Qwen3-235B-A22B-Thinking-2507`

### Reasoning / Thinking
- **Best**: `gemini-3-pro-preview` (thinking), `Qwen3-235B-A22B-Thinking-2507`, `qwq-32b-preview`
- **Good**: `gemini-2.5-pro`, `qvq-72b-preview`

### Image Generation
- **Stable**: `gemini-2.5-flash-image`
- **Latest**: `gemini-3-pro-image-preview`
- **Alternative**: `MiniMax Image-01`

### Cost-Effective
- **Ultra-Low Cost**: `MiniMax-M2.1` ($0.3/M input tokens)
- **Low Cost**: `qwen-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`
- **Free Tier**: MiniMax-M2 had free API call promotion (check current status)

---

## 10. Implementation Checklist

- [ ] Add environment variables to `.env.example`
- [ ] Update `config.yaml` with new provider sections
- [ ] Add new provider methods to `LLMFactory`
- [ ] Update `Settings` class with new API keys
- [ ] Add model name validation patterns
- [ ] Update `pyproject.toml` with new dependencies
- [ ] Update `README.md` with provider documentation
- [ ] Add provider-specific tests
- [ ] Test each provider independently
- [ ] Update documentation

---

## 11. Migration Guide for Users

To switch to a new provider:

1. **Set API key** in `.env`:
   ```bash
   # For Gemini
   GOOGLE_API_KEY=your-key

   # For Qwen
   DASHSCOPE_API_KEY=your-key

   # For Kimi
   MOONSHOT_API_KEY=your-key

   # For MiniMax
   MINIMAX_API_KEY=your-key
   ```

2. **Update config** in `docker/config.yaml`:
   ```yaml
   llm:
     default_provider: gemini  # or qwen, kimi, minimax
   ```

3. **Restart** the application

---

## 12. Notes and Considerations

### Gemini
- **Temperature**: Gemini 3.0+ defaults to `1.0` (not `0.7`)
- **Backend Auto-Detection**: Automatically switches between Gemini API and Vertex AI
- **Thinking Models**: Use `thinking_level` for Gemini 3+, `thinking_budget` for Gemini 2.5

### Qwen
- **Regional API**: May need regional endpoints depending on location
- **Vision Models**: Separate model IDs for VL (Vision Language) models

### Kimi/Moonshot
- **OpenAI-Compatible**: Uses standard OpenAI SDK with custom base URL
- **China Region**: May have separate endpoint for China region

### MiniMax
- **Ultra-Long Context**: 204,800 tokens is one of the largest available
- **Low Cost**: Extremely competitive pricing ($0.3/M input tokens)
- **Two API Types**: Choose OpenAI or Anthropic compatible interface
- **Speech**: Separate TTS API available

---

## Summary

| Provider | Package | API Type | Top Model | Max Context | Best For |
|----------|---------|----------|-----------|-------------|----------|
| **Gemini** | `langchain-google-genai` | Native | `gemini-3-pro-preview` | 1M+ tokens | Most intelligent, complex reasoning, agentic |
| **Qwen** | `langchain-qwq` | Native | `qwen-max-latest` (API) or `Qwen3-Next-80B-A3B` (local) ⭐ | 32K (API) / 1M (local) | Balanced, efficient, 10x long-context throughput |
| **Kimi** | `langchain-openai`* | OpenAI-compatible | `kimi-k2.5` | 256K tokens | Agent swarm, long context, multimodal |
| **MiniMax** | `langchain-openai`* | OpenAI/Anthropic-compatible | `MiniMax-M2.1` | 204,800 tokens | Ultra-long context, lowest cost, coding |

All providers support:
- ✅ Tool calling / function calling
- ✅ Structured output
- ✅ Streaming responses
- ✅ Async operations
- ✅ Token usage tracking
- ✅ Multimodal capabilities (vision)

### Quick Selection Guide

| Need | Recommended Provider | Model |
|------|---------------------|-------|
| **Most Intelligent** | Gemini | `gemini-3-pro-preview` |
| **Best Price-Performance** | Gemini | `gemini-2.5-flash` |
| **Lowest Cost** | MiniMax | `MiniMax-M2.1` ($0.3/M input) |
| **Ultra-Long Context** | MiniMax | `MiniMax-M2.1` (204K tokens) |
| **Local Deployment** | Qwen | `Qwen3-30B-A3B-Instruct-2507` |
| **Agent Capabilities** | Kimi | `kimi-k2.5` (agent swarm) |
| **Coding** | MiniMax | `MiniMax-M2.1` |
| **Multimodal** | Gemini | `gemini-3-pro-preview` |
| **Fast/High Throughput** | Gemini | `gemini-2.5-flash-lite` |
| **Production Scale** | MiniMax | `MiniMax-M2-Stable` |
