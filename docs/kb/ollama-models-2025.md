# Ollama Popular Models Reference (2025)

**Last Updated:** 2025-01-19
**Provider:** Ollama (Open Source Aggregator)
**Website:** https://ollama.com/library/
**License:** Various (mostly Apache 2.0, MIT)

---

## Model Overview

Ollama provides easy access to 100+ open-source large language models that can run locally or via cloud APIs. No API costs, full privacy, and complete control.

---

## Popular Model Families (2025)

### Llama (Meta)

#### **Llama 4**
- **Parameters:** Maverick (medium), Scout (small)
- **Release:** 2025
- **Strengths:**
  - Reportedly outperforms GPT-4o and Gemini 2.0 Flash
  - State-of-the-art open-source performance
  - Multimodal capabilities
- **Use Cases:**
  - Production applications
  - General purpose tasks
  - When you need top open-source performance

#### **Llama 3.3 70B**
- **Parameters:** 70B
- **Strengths:**
  - Performance comparable to 405B parameter models
  - Much lower computational cost
  - Excellent balance of performance and efficiency
- **Use Cases:**
  - Cost-effective deployment
  - When you can't run 400B+ models
  - Production workloads

#### **Llama 3.2**
- **Parameters:** 1B, 3B (small), 11B, 90B (medium)
- **Strengths:**
  - Multiple sizes for different hardware
  - Good for edge deployment
  - Decent performance
- **Use Cases:**
  - Edge devices
  - Resource-constrained environments
  - Local development

---

### Qwen (Alibaba)

#### **Qwen 3**
- **Parameters:** Various sizes
- **Release:** 2025
- **Strengths:**
  - Strong performer in reasoning and coding
  - Bilingual Chinese/English
  - Competitive with Llama
- **Use Cases:**
  - Coding tasks
  - Chinese language applications
  - General reasoning

#### **Qwen-Coder V2**
- **Type:** Code-specialized
- **Strengths:**
  - One of 2025's leaders for coding projects
  - Excellent code generation
  - Strong debugging capabilities
- **Use Cases:**
  - Code assistance
  - Code review
  - Programming tasks

#### **Qwen 2**
- **Parameters:** 0.5B - 72B
- **Strengths:**
  - Multiple sizes available
  - Listed among top small language models
  - Good performance/efficiency balance
- **Use Cases:**
  - Various deployment scenarios
  - Resource-constrained environments

---

### Mistral

#### **Mistral 7B**
- **Parameters:** 7B
- **Strengths:**
  - Foundation model with strong performance
  - Efficient architecture
  - Good quality for size
- **Use Cases:**
  - Resource-constrained deployments
  - Local development
  - Base for fine-tuning

#### **Mistral Nemo**
- **Parameters:** 12B
- **Strengths:**
  - Listed among top small language models
  - Good performance
  - Efficient
- **Use Cases:**
  - Balanced performance and resource usage
  - Production deployment

---

### DeepSeek

#### **DeepSeek V3.2** ⭐ NEW!
- **Type:** High-Efficiency Reasoning Model
- **Release:** 2025
- **Strengths:**
  - Harmonizes high computational efficiency with superior reasoning
  - **DSA (DeepSeek Sparse Attention)** in V3.2-Exp variant
  - Performance approaching O3 and Gemini 2.5 Pro
  - Better long-context performance
  - Reduces compute cost with minimal impact on output quality
  - Excellent agent performance
- **Use Cases:**
  - Complex reasoning tasks
  - Long-context applications
  - Agentic workflows
  - Cost-efficient deployment
- **Availability:** `deepseek-v3.2` on Ollama
- **Trade-offs:** Requires good hardware for local deployment
- **Sources:**
  - [Ollama DeepSeek-V3.2](https://ollama.com/library/deepseek-v3.2)
  - [Introducing DeepSeek-V3.2-Exp](https://api-docs.deepseek.com/news/news250929)
  - [Complete Guide to DeepSeek Models](https://www.bentoml.com/blog/the-complete-guide-to-deepseek-models-from-v3-to-r1-and-beyond)

#### **DeepSeek V3.1**
- **Type:** Advanced Reasoning Model
- **Strengths:**
  - Improved over V3
  - Better reasoning capabilities
  - Strong benchmark performance
- **Use Cases:**
  - General reasoning
  - Problem solving
  - Coding tasks
- **Availability:** Available on Ollama

#### **DeepSeek R1**
- **Type:** Reasoning model
- **Strengths:**
  - Strong reasoning capabilities
  - Mentioned among top open-source LLMs
  - Good for complex tasks
- **Use Cases:**
  - Complex reasoning
  - Problem solving
  - Research tasks

#### **DeepSeek-Coder-V2**
- **Type:** Code-specialized
- **Strengths:**
  - Dominates coding tasks in 2025
  - Excellent code generation
  - Strong programming abilities
- **Use Cases:**
  - Code assistance
  - Development tools
  - Programming education

---

### MiniMax

#### **MiniMax M2** ⭐ NEW!
- **Type:** Agentic Workflow Model
- **Release:** October 28, 2025
- **Parameters:** 10B activated (230B total)
- **Strengths:**
  - **50% faster inference** than previous models
  - **95% MMLU accuracy** (predicted)
  - Optimized for **interactive agents and agentic workflows**
  - Multilingual coding excellence (beyond Python)
  - High-efficiency responses
  - Multimodal API support
  - Concise, high-throughput outputs
  - Scalable query processing
- **Use Cases:**
  - **Agentic workflows** (best-in-class)
  - Mobile app development
  - Interactive AI agents
  - Multilingual coding
  - Cost-sensitive production
- **Availability:** `minimax-m2` and `minimax-m2.1` on Ollama
- **Special:** Free access on Ollama Cloud until Nov 7, 2025
- **Trade-offs:** Newer model, less community testing
- **Why It Matters:** Described as "one of the most balanced open-source agents" with performance rivaling proprietary models

#### **MiniMax M2.1**
- **Type:** Enhanced Agentic Model
- **Strengths:**
  - Improved over M2
  - Better performance
  - Enhanced features
- **Use Cases:** Same as M2 but with better performance

#### **MiniMax M1**
- **Type:** Large-Scale Open Weight
- **Strengths:**
  - World's first open-weight, large-scale model
  - Efficient scaling of test-time compute
  - Focus on language model agents
- **Use Cases:** Research, agent development

---

### Phi (Microsoft)

#### **Phi-3.5**
- **Parameters:** Various small sizes
- **Strengths:**
  - Compact and efficient
  - Good quality for small size
  - Microsoft-optimized
- **Use Cases:**
  - Edge deployment
  - Mobile applications
  - Resource-constrained environments

---

### Gemma (Google)

#### **Gemma2**
- **Parameters:** 2B - 27B
- **Strengths:**
  - Strong small model option
  - Google-optimized
  - Good performance/size ratio
- **Use Cases:**
  - Lightweight applications
  - Local development
  - Cost-effective deployment

---

## Performance Comparison

| Model Family | Top Model | Parameters | Performance | Hardware Needed | Best For |
|--------------|-----------|------------|-------------|-----------------|----------|
| **Llama** | Llama 4 Maverick | Medium | ⭐⭐⭐⭐⭐ | High | Production, general use |
| **Llama** | Llama 3.3 70B | 70B | ⭐⭐⭐⭐ | Medium-High | Cost-effective production |
| **Qwen** | Qwen 3 | Various | ⭐⭐⭐⭐ | Medium | Coding, bilingual |
| **Qwen** | Qwen-Coder V2 | Various | ⭐⭐⭐⭐⭐ | Medium | **Coding tasks** |
| **Mistral** | Mistral 7B | 7B | ⭐⭐⭐ | Low | Resource-constrained |
| **DeepSeek** | DeepSeek V3.2 | Various | ⭐⭐⭐⭐⭐ | Medium | **Reasoning, agents** |
| **DeepSeek** | DeepSeek-Coder-V2 | Various | ⭐⭐⭐⭐⭐ | Medium | **Coding tasks** |
| **MiniMax** | MiniMax M2 | 230B/10B | ⭐⭐⭐⭐⭐ | Medium | **Agentic workflows** |
| **Phi** | Phi-3.5 | Small | ⭐⭐⭐ | Very Low | Edge, mobile |
| **Gemma** | Gemma2 | 2B-27B | ⭐⭐⭐ | Low-Medium | Lightweight apps |

---

## Quantization Guide

Ollama models use quantization to reduce memory and improve speed.

### Recommended Quantization Levels:

| Quantization | Quality | Speed | Memory | Use Case |
|--------------|---------|-------|--------|----------|
| **Q5_K_M** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | **Recommended sweet spot** |
| **Q4_K_M** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Low | Fast inference |
| **Q6_K** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | High | Maximum quality |
| **Q8_0** | ⭐⭐⭐⭐⭐ | ⭐⭐ | Very High | Near-original quality |
| **Q3_K** | ⭐⭐ | ⭐⭐⭐⭐⭐ | Very Low | Maximum speed |

**Recommendation:** Use **Q5_K_M** for best balance of quality and performance.

---

## Hardware Requirements

### By Model Size:

| Parameter Range | VRAM Needed | RAM Needed | Examples |
|----------------|-------------|------------|----------|
| **1B-3B** | 4GB | 8GB | Phi-3.5, Gemma2 2B |
| **7B-8B** | 6-8GB | 16GB | Mistral 7B, Qwen 7B |
| **14B-15B** | 12GB | 24GB | Qwen 14B |
| **27B-35B** | 20GB | 48GB | Gemma2 27B |
| **70B** | 48GB | 96GB | Llama 3.3 70B |
| **100B+** | 80GB+ | 128GB+ | Llama 4, GLM-4.5 |

### Recommendations:
- **Mac M1/M2/M3:** Can run up to 70B models (unified memory)
- **NVIDIA GPUs:** RTX 3090/4090 for up to 70B
- **Consumer CPUs:** Up to 14B models
- **Multi-GPU:** For 100B+ models

---

## Top 10 Models for Cassey (2025)

### For Conversational AI:
1. **Llama 3.3 70B** - Best balance, near GPT-4 level
2. **Qwen 3 72B** - Strong bilingual, great reasoning
3. **Mistral Nemo 12B** - Good performance, efficient

### For Coding Tasks:
4. **DeepSeek-Coder-V2** - Best open-source coder
5. **Qwen-Coder V2** - Excellent code generation
6. **Llama 3.3 70B** - Good coding capabilities

### For Agentic Workflows:
7. **MiniMax M2** - Best-in-class for agents (95% MMLU, 50% faster)
8. **DeepSeek V3.2** - Excellent reasoning with DSA, approaches O3 performance

### For Resource-Constrained:
9. **Phi-3.5** - Smallest capable model
10. **Gemma2 9B** - Good quality, small size

---

## Recommended Usage for Cassey

### Primary Local Model: **Llama 3.3 70B (Q5_K_M)**
- Near GPT-4 performance
- Runs on consumer GPUs (RTX 3090/4090)
- Excellent quality/price ratio

### For Agentic Workflows: **MiniMax M2** ⭐ (NEW!)
- Best-in-class for agents
- 95% MMLU, 50% faster inference
- Free on Ollama Cloud until Nov 7, 2025

### For Reasoning: **DeepSeek V3.2** ⭐ (NEW!)
- Approaches O3 and Gemini 2.5 Pro performance
- DSA for efficient long-context
- Excellent for complex reasoning

### Coding: **DeepSeek-Coder-V2**
- Best open-source for code
- Fast and accurate

### Lightweight: **Phi-3.5**
- For edge deployment
- Quick responses

### Recommended Configuration:

```yaml
llm:
  ollama:
    default_model: llama3.3:70b        # Primary
    agent_model: minimax-m2             # Agentic workflows
    reasoning_model: deepseek-v3.2      # Complex reasoning
    coding_model: deepseek-coder-v2     # Coding
    fast_model: phi-3.5                 # Lightweight
```

---

## Pros and Cons

### Pros:
- **Zero API costs** - Run locally, free after download
- **Privacy** - Data never leaves your machine
- **Control** - Full control over model and updates
- **No rate limits** - Run as many requests as you want
- **Customizable** - Fine-tune, quantize, modify
- **Offline** - Works without internet

### Cons:
- **Hardware requirements** - Need good GPU/CPU
- **Setup complexity** - More complex than API calls
- **Maintenance** - You handle updates and hosting
- **Performance** - Generally behind GPT-5/Claude Opus
- **Support** - No official support, community only
- **Model updates** - Manual updates required

---

## When to Use Ollama

### Use Ollama when:
- Budget is $0 (no API costs)
- Privacy is critical (data stays local)
- You have good hardware
- You want full control
- You're okay with slightly lower performance
- You need offline capability

### Avoid Ollama when:
- You don't have powerful hardware
- You need the absolute best performance (GPT-5/Claude Opus)
- You want simple setup
- You need official support
- Hardware cost > API cost

---

## Installation

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download a model
ollama pull llama3.3:70b

# Run a model
ollama run llama3.3:70b

# List models
ollama list

# API server (runs on port 11434)
ollama serve
```

---

## API Integration

Ollama provides OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama'  # Required but unused
)

response = client.chat.completions.create(
    model="llama3.3:70b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## Sources:
- [Ollama Library](https://ollama.com/library/)
- [10 Best Open-Source LLM Models (2025 Updated)](https://huggingface.co/blog/daya-shankar/open-source-llms)
- [Ollama Models List 2025: 100+ Models Compared](https://skywork.ai/blog/llm/ollama-models-list-2025-100-models-compared/)
- [Top 9 Large Language Models as of January 2026](https://www.shakudo.io/blog/top-9-large-language-models)
- [Top 10 open source LLMs for 2025](https://www.instaclustr.com/education/open-source-ai/top-10-open-source-llms-for-2025/)
- [The 11 best open-source LLMs for 2025](https://blog.n8n.io/open-source-llms/)
