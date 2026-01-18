# Ollama Cloud Models Reference (2025)

**Last Updated:** 2025-01-19
**Provider:** Ollama (Cloud Service)
**Website:** https://ollama.com/cloud
**Pricing:** Free tier available, Pro $20/mo, Max $100/mo

---

## What is Ollama Cloud?

Ollama Cloud is a service that allows you to run larger, more powerful models on datacenter-grade hardware without requiring powerful local GPUs. Models with the `:cloud` tag are automatically offloaded to Ollama's cloud infrastructure while maintaining the same API compatibility as local models.

### Key Benefits:
- **Speed:** Run models on datacenter-grade hardware for faster inference
- **Larger Models:** Access models too large for consumer hardware
- **Privacy:** Ollama does not log prompt or response data
- **Battery Life:** Offload compute from your local machine
- **Compatibility:** Works with Ollama's CLI, App, API, and JavaScript/Python libraries
- **No API Changes:** Same API as local models, just add `:cloud` tag

### Pricing Tiers:
| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | Free access to cloud models, web search, page fetching |
| **Pro** | $20/mo | Higher usage limits than Free |
| **Max** | $100/mo | 5× higher usage limits than Pro |

**Note:** Usage-based pricing coming soon. Premium model requests (e.g., Gemini 3 Pro Preview) don't count toward hourly/weekly limits.

---

## Available Cloud Models

### 🌟 MiniMax M2:cloud

**Downloads:** 40K
**Tags:** `tools`, `thinking`, `cloud`
**Context:** Not specified in data

**Overview:**
MiniMax M2 is a high-efficiency large language model built for coding and agentic workflows. **Ranked #1 among open-source models globally** by Artificial Analysis composite intelligence score.

**Key Features:**
- **Superior Intelligence:** Ranks #1 among open-source models globally (AA Intelligence: 61)
- **Advanced Coding:** Engineered for end-to-end developer workflows, multi-file edits, coding-run-fix loops
- **Agent Performance:** Excels at complex, long-horizon toolchains across shell, browser, retrieval, code runners
- **Efficient Design:** 10B activated parameters (230B total), lower latency and cost

**Benchmark Highlights:**
| Benchmark | Score | Comparison |
|-----------|-------|------------|
| **SWE-bench Verified** | 69.4 | Competitive with GPT-5 (74.9) |
| **Multi-SWE-Bench** | 36.2 | Beats Claude Sonnet 4.5 (44.3) on multilingual |
| **Terminal-Bench** | 46.3 | Significantly beats Claude Sonnet 4 (36.4) |
| **BrowseComp-zh** | 48.5 | Strong Chinese web browsing |
| **GAIA (text)** | 75.7 | Excellent agentic performance |
| **HLE (w/ tools)** | 31.8 | Good reasoning with tools |

**Artificial Analysis Intelligence: 61** (vs Claude Sonnet 4.5: 63, GPT-5: 69)

**Best For:**
- Coding and agentic workflows
- Multi-file editing and terminal tasks
- Complex tool chains and browser automation
- Production deployments requiring speed + quality

**How to Use:**
```bash
ollama run minimax-m2:cloud
```

---

### 🌟 DeepSeek V3.2:cloud

**Downloads:** 14.8K
**Tags:** `tools`, `thinking`, `cloud`
**Context:** 160K tokens

**Overview:**
DeepSeek-V3.2 harmonizes high computational efficiency with superior reasoning and agent performance through three key technical breakthroughs.

**Key Features:**
- **DeepSeek Sparse Attention (DSA):** Efficient attention mechanism that reduces computational complexity while preserving performance, optimized for long-context scenarios
- **Scalable RL Framework:** Performs comparably to GPT-5 through scaled post-training compute
- **Agentic Task Synthesis:** Novel pipeline for generating training data at scale for tool-use scenarios

**Technical Innovations:**
1. **DSA:** Specifically optimized for long-context scenarios
2. **Reinforcement Learning:** Robust RL protocol with scaled post-training
3. **Tool Integration:** Systematic agentic post-training for complex environments

**Best For:**
- Long-context reasoning tasks (160K tokens)
- Agentic workflows requiring tool use
- Complex reasoning challenges
- When you need GPT-5-level performance at lower cost

**How to Use:**
```bash
ollama run deepseek-v3.2:cloud
```

---

### 🌟 GLM-4.7:cloud

**Downloads:** 14.3K
**Tags:** `tools`, `thinking`, `cloud`
**Context:** 198K tokens
**Release:** December 2025

**Overview:**
GLM-4.7 advances coding capability with clear gains over GLM-4.6 across multiple benchmarks. **Beats GPT-5.2 and Claude in several benchmarks.**

**Key Features:**
- **Core Coding:** Significant improvements in multilingual agentic coding and terminal-based tasks
- **Vibe Coding:** Major step forward in UI quality (cleaner webpages, better slides)
- **Tool Using:** Significant improvements on τ²-Bench and BrowseComp
- **Complex Reasoning:** HLE benchmark: 42.8% (+12.4% over GLM-4.6)

**Benchmark Improvements:**
| Benchmark | GLM-4.7 | GLM-4.6 | Improvement |
|-----------|---------|---------|-------------|
| **SWE-bench** | 73.8% | 68.0% | +5.8% |
| **SWE-bench Multilingual** | 66.7% | 53.8% | +12.9% |
| **Terminal Bench 2.0** | 41.0% | 24.5% | +16.5% |
| **HLE** | 42.8% | 30.4% | +12.4% |

**Agent Framework Support:**
- Claude Code
- Kilo Code
- Cline
- Roo Code

**Best For:**
- Coding assistance (best-in-class performance)
- Multilingual coding tasks
- Terminal-based workflows
- UI generation (vibe coding)
- Mathematical reasoning
- Complex tool-using scenarios

**How to Use:**
```bash
ollama run glm-4.7:cloud
```

---

### 🌟 Gemini 3 Flash Preview:cloud

**Downloads:** 38.7K
**Tags:** `vision`, `tools`, `thinking`, `cloud`
**Context:** Not specified

**Overview:**
Gemini 3 Flash offers frontier intelligence built for speed at a fraction of the cost. **Demonstrates that speed and scale don't have to come at the cost of intelligence.**

**Key Features:**
- **Frontier Performance:** PhD-level reasoning on GPQA Diamond (90.4%)
- **Humanity's Last Exam:** 33.7% without tools (rivals larger frontier models)
- **MMMU Pro:** 81.2% (state-of-the-art, comparable to Gemini 3 Pro)
- **Significantly Outperforms:** Gemini 2.5 Pro across multiple benchmarks

**Benchmark Highlights:**
| Benchmark | Score | Significance |
|-----------|-------|--------------|
| **GPQA Diamond** | 90.4% | PhD-level reasoning |
| **HLE (no tools)** | 33.7% | Rivals larger frontier models |
| **MMMU Pro** | 81.2% | State-of-the-art, comparable to Gemini 3 Pro |

**Best For:**
- Speed-critical applications requiring frontier intelligence
- Multimodal tasks (vision + text)
- PhD-level reasoning and knowledge benchmarks
- When you need Gemini 3 Pro quality at Flash speed

**How to Use:**
```bash
ollama run gemini-3-flash-preview:cloud
```

---

### GPT-OSS:cloud

**Downloads:** 6M
**Tags:** `tools`, `thinking`, `cloud`
**Sizes:** 20B, 120B

**Overview:**
OpenAI's open-weight models designed for powerful reasoning, agentic tasks, and versatile developer use cases. **Partnership between Ollama and OpenAI.**

**Available Models:**
- `gpt-oss:20b-cloud` - Smaller, faster variant
- `gpt-oss:120b-cloud` - Larger, more capable variant

**Best For:**
- General-purpose reasoning and agentic tasks
- Development workflows
- Open-source model preferences with OpenAI quality
- When you need OpenAI-level performance with open weights

**How to Use:**
```bash
ollama run gpt-oss:120b-cloud
# or
ollama run gpt-oss:20b-cloud
```

---

### Qwen3-VL:cloud

**Downloads:** 1.1M
**Tags:** `vision`, `tools`, `thinking`, `cloud`
**Sizes:** 2B, 4B, 8B, 30B, 32B, 235B

**Overview:**
The most powerful vision-language model in the Qwen model family to date.

**Key Features:**
- **Visual Agent Capabilities:** Can operate computer and mobile interfaces
- **GUI Recognition:** Recognizes GUI elements, understands button functions, calls tools
- **OS World:** Top global performance on benchmarks
- **Text-Centric Performance:** Matches Qwen3-235B-A22B on text-based tasks
- **Truly "text-grounded, multimodal powerhouse"**

**Best For:**
- Vision-language tasks requiring strong text capabilities
- GUI automation and computer control
- Mobile interface interaction
- When you need both vision and strong language understanding

**How to Use:**
```bash
ollama run qwen3-vl:235b-cloud
```

---

### Qwen3-Coder:cloud

**Downloads:** 2.2M
**Tags:** `tools`, `cloud`
**Sizes:** 30B, 480B

**Overview:**
Alibaba's performant long context models for agentic and coding tasks.

**Best For:**
- Coding assistance
- Long-context tasks
- Agentic workflows
- Programming education

**How to Use:**
```bash
ollama run qwen3-coder:480b-cloud
```

---

### Gemma 3:cloud

**Downloads:** 30.2M
**Tags:** `vision`, `cloud`
**Sizes:** 270M, 1B, 4B, 12B, 27B

**Overview:**
The current, most capable model that runs on a single GPU (when not on cloud). Now available on cloud for even better performance.

**Key Features:**
- **Quantization Aware Trained (QAT):** Preserves similar quality as half precision (BF16) with 3× lower memory
- **Single GPU Capable:** Can run locally on consumer hardware if needed
- **Cloud Option:** Available on cloud for faster inference

**Best For:**
- Lightweight applications
- Local development (can switch between local/cloud)
- Cost-effective deployment
- When you need Google's latest Gemma capabilities

**How to Use:**
```bash
ollama run gemma3:4b-cloud
```

---

### Nemotron 3 Nano:cloud

**Downloads:** 115.5K
**Tags:** `cloud`
**Size:** 30B

**Overview:**
Nemotron 3 Nano - A new standard for efficient, open, and intelligent agentic models by NVIDIA.

**Best For:**
- Agentic workflows
- Efficient deployment
- NVIDIA ecosystem integration

**How to Use:**
```bash
ollama run nemotron-3-nano:30b-cloud
```

---

### Devstral Small 2:cloud

**Downloads:** 99.3K
**Tags:** `vision`, `tools`, `cloud`
**Size:** 24B

**Overview:**
24B model that excels at using tools to explore codebases, editing multiple files and power software engineering agents.

**Best For:**
- Software engineering agents
- Codebase exploration
- Multi-file editing
- Development workflows

**How to Use:**
```bash
ollama run devstral-small-2:cloud
```

---

### Devstral 2:cloud

**Downloads:** 49.4K
**Tags:** `tools`, `cloud`
**Size:** 123B

**Overview:**
123B model that excels at using tools to explore codebases, editing multiple files and power software engineering agents.

**Best For:**
- Complex software engineering tasks
- Large-scale codebase exploration
- Advanced development workflows

**How to Use:**
```bash
ollama run devstral-2:cloud
```

---

### Ministral 3:cloud

**Downloads:** 266.4K
**Tags:** `vision`, `tools`, `cloud`
**Sizes:** 3B, 8B, 14B

**Overview:**
The Ministral 3 family is designed for edge deployment, capable of running on a wide range of hardware.

**Best For:**
- Edge deployment (with option to use cloud)
- Resource-constrained environments
- Lightweight applications

**How to Use:**
```bash
ollama run ministral-3:8b-cloud
```

---

### Other Notable Cloud Models

#### DeepSeek V3.1:cloud
- **Tags:** `tools`, `thinking`, `cloud`
- **Size:** 671B
- **Features:** Hybrid model supporting both thinking and non-thinking modes

#### Qwen3-Next:cloud
- **Tags:** `tools`, `thinking`, `cloud`
- **Size:** 80B
- **Features:** Strong parameter efficiency and inference speed

#### Gemini 3 Pro Preview:cloud
- **Tags:** `cloud`
- **Features:** Google's most intelligent model with SOTA reasoning and multimodal understanding (premium model request)

#### GLM-4.6:cloud
- **Tags:** `cloud`
- **Features:** Advanced agentic, reasoning and coding capabilities (predecessor to GLM-4.7)

#### Kimi K2:cloud
- **Tags:** `cloud`
- **Features:** State-of-the-art mixture-of-experts (MoE) language model

#### Cogito 2.1:cloud
- **Tags:** `cloud`
- **Size:** 671B
- **License:** MIT (commercial use allowed)

#### RNJ-1:cloud
- **Tags:** `tools`, `cloud`
- **Size:** 8B
- **Features:** Optimized for code and STEM, MIT license

---

## Performance Comparison Table

| Model | Parameters | Strengths | AA Intelligence | Best For | Context |
|-------|------------|-----------|-----------------|----------|---------|
| **MiniMax M2** | 10B/230B | Coding, Agents | 61 | **Agentic workflows** | - |
| **GLM-4.7** | - | Coding, Reasoning | High | **Coding (best-in-class)** | 198K |
| **Gemini 3 Flash** | - | Speed, Reasoning | High | **Fast frontier intelligence** | - |
| **DeepSeek V3.2** | - | Reasoning, Long-context | 57 | **Long-context (160K)** | 160K |
| **GPT-OSS** | 20B/120B | General, Agents | Medium-High | **OpenAI quality** | - |
| **Qwen3-Coder** | 30B/480B | Coding | Medium | **Coding tasks** | - |
| **Qwen3-VL** | 2B-235B | Vision-Language | Medium | **Multimodal** | - |
| **Gemma 3** | 270M-27B | Lightweight | Low-Medium | **Lightweight apps** | - |

---

## API Usage

### OpenAI-Compatible API

Ollama Cloud provides an OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama'  # Required but unused
)

response = client.chat.completions.create(
    model="minimax-m2:cloud",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Ollama Python Library

```python
from ollama import chat

response = chat(
    model='minimax-m2:cloud',
    messages=[{'role': 'user', 'content': 'Hello!'}],
)
print(response.message.content)
```

### Ollama JavaScript Library

```javascript
import ollama from 'ollama';

const response = await ollama.chat({
  model: 'minimax-m2:cloud',
  messages: [{role: 'user', content: 'Hello!'}],
});
console.log(response.message.content);
```

### CLI

```bash
ollama run minimax-m2:cloud
```

### cURL

```bash
curl http://localhost:11434/api/chat \
  -d '{
    "model": "minimax-m2:cloud",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## When to Use Ollama Cloud

### Use Ollama Cloud when:
- You don't have powerful local GPUs
- You need to run models too large for your hardware
- You want faster inference than local hardware can provide
- You want to save battery life on laptops
- You need access to premium models (e.g., Gemini 3 Pro Preview)
- You want to preserve local compute resources for other tasks

### Avoid Ollama Cloud when:
- Privacy requirements prevent data leaving your premises
- You have powerful local hardware and want zero cost
- Network latency is unacceptable
- You need offline capability

---

## Comparison: Ollama Cloud vs. Other Providers

| Feature | Ollama Cloud | OpenAI | Anthropic | Zhipu |
|---------|--------------|--------|-----------|-------|
| **Local Option** | ✅ Yes (switch between local/cloud) | ❌ No | ❌ No | ❌ No |
| **Free Tier** | ✅ Yes | ❌ No | ❌ No | ✅ Yes (GLM-4 Flash) |
| **Open Models** | ✅ Mostly | ❌ No | ❌ No | ✅ Yes (GLM-4.7) |
| **Privacy** | ✅ No logging | ✅ Enterprise options | ✅ Constitutional AI | ⚠️ Chinese provider |
| **Pricing** | Free/$20/$100 + usage-based coming | Pay-per-token | Pay-per-token | Pay-per-token |
| **API Compatibility** | ✅ OpenAI-compatible | OpenAI native | Custom API | OpenAI-compatible |
| **Top Model** | MiniMax M2 / GLM-4.7 | GPT-5.2 | Claude Opus 4.5 | GLM-4.7 |

---

## Recommended Configuration for Cassey

### Primary Model: **MiniMax M2:cloud**
**Why:** #1 ranked open-source model globally, excellent for coding and agentic workflows

### Secondary Model: **GLM-4.7:cloud**
**Why:** Best-in-class coding performance, beats GPT-5.2/Claude in several benchmarks

### Reasoning Model: **DeepSeek V3.2:cloud**
**Why:** DSA for efficient long-context (160K), GPT-5-comparable performance

### Fast Model: **Gemini 3 Flash Preview:cloud**
**Why:** Frontier intelligence built for speed, GPQA Diamond 90.4%

### Configuration Example:

```yaml
llm:
  default_provider: ollama
  ollama:
    default_model: minimax-m2:cloud      # Primary (agentic workflows)
    reasoning_model: deepseek-v3.2:cloud  # Long-context reasoning
    coding_model: glm-4.7:cloud           # Best-in-class coding
    fast_model: gemini-3-flash-preview:cloud  # Fast responses
    api_base: http://localhost:11434
```

---

## Cost Comparison (Estimated)

**Monthly Cost for 10,000 Messages** (500 input + 500 output tokens per message):

| Provider/Model | Monthly Cost | Notes |
|----------------|--------------|-------|
| **Ollama Cloud (Free Tier)** | $0 | With rate limits |
| **Ollama Cloud (Pro)** | $20 | Higher limits |
| **Ollama Cloud (Max)** | $100 | 5× Pro limits |
| GLM-4 Flash (Zhipu) | $0 | Free tier with rate limits |
| GPT-4o Mini (OpenAI) | $3.75 | Per 1M tokens pricing |
| Claude Haiku 4.5 | $7.50 | Per 1M tokens pricing |
| GLM-4.7 (Zhipu) | ~$12 | Per 1M tokens pricing |

**Note:** Ollama Cloud usage-based pricing coming soon, which may change these estimates.

---

## Sources:
- [Ollama Cloud](https://ollama.com/cloud)
- [Ollama Cloud Models Search](https://ollama.com/search?c=cloud)
- [MiniMax M2 on Ollama](https://ollama.com/library/minimax-m2:cloud)
- [DeepSeek V3.2 on Ollama](https://ollama.com/library/deepseek-v3.2)
- [GLM-4.7 on Ollama](https://ollama.com/library/glm-4.7)
- [Gemini 3 Flash Preview on Ollama](https://ollama.com/library/gemini-3-flash-preview:cloud)
