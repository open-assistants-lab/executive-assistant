# OpenAI Models Reference (2025)

**Last Updated:** 2025-01-19
**Provider:** OpenAI
**Website:** https://openai.com/api/pricing/

---

## Model Overview

OpenAI offers a range of models optimized for different use cases, from fast/cost-effective to high-performance reasoning.

---

## Available Models

### GPT-5.2 Series (Latest)

#### **GPT-5.2** ⭐ NEW!
- **Type:** Frontier Grade Model
- **Release:** December 11, 2025
- **Context Window:** 400K tokens
- **Strengths:**
  - **Massive math improvements:** 100% on AIME 2025, 99.4% on HMMT Feb 2025
  - **Huge AGI jump:** ARC-AGI-2 benchmark: 52.9% (vs GPT-5.1's 17.6%)
  - New internal thinking tokens for improved reasoning
  - Better performance on latency-sensitive use cases
  - Stronger agentic capabilities
  - Enhanced multimodal (images, charts, diagrams)
  - More efficient "reasoning effort='none'" mode
- **Pricing:**
  - Similar to GPT-5 (expected $1-3/1M input based on GPT-5 pricing)
- **Use Cases:**
  - Complex mathematical reasoning
  - AGI-level tasks
  - Coding and agentic workflows
  - Long context tasks
- **Trade-offs:** Higher cost, may be slower than GPT-5.1

#### **GPT-5.1**
- **Type:** High Performance Model
- **Release:** 2025
- **Context Window:** 400K tokens
- **Strengths:**
  - Handles complex agentic and coding workloads
  - Faster responses on everyday tasks vs GPT-5.2
  - Multimodal image input support
  - Strong performance across benchmarks
- **Pricing:**
  - Similar to GPT-5 ($1.25/1M input estimated)
- **Use Cases:**
  - Production workloads
  - Coding tasks
  - Multimodal applications
- **Trade-offs:** Lower performance than GPT-5.2 on math/AGI benchmarks

### GPT-5 Series

#### **GPT-5** (Base Model)
- **Type:** Reasoning/General Purpose
- **Context Window:** 400K tokens
- **Strengths:**
  - Superior coding performance: 75% on benchmarks (vs GPT-4o's 31%)
  - SWE-bench Verified: 74.9% (leading)
  - Excellent at math, multimodal reasoning, factual accuracy
  - 24× cheaper than GPT-4
- **Pricing:**
  - Input: $1.25/1M tokens
  - Output: ~$2-5/1M tokens (estimated)
  - Cached input: Discounts available
- **Use Cases:**
  - Complex coding challenges
  - Deep reasoning tasks
  - Multi-step problem solving
  - Large context tasks (400K tokens)
- **Trade-offs:** Higher cost than Mini variants

#### **GPT-5 Mini**
- **Type:** Efficient General Purpose
- **Context Window:** 128K tokens
- **Strengths:**
  - Faster than GPT-5
  - More cost-effective
  - Good for well-defined tasks
- **Pricing:**
  - Input: $0.25/1M tokens
  - Output: $2.00/1M tokens
  - Cached input: $0.025/1M tokens
- **Use Cases:**
  - Well-defined tasks
  - Faster response needed
  - Cost-sensitive applications
- **Trade-offs:** Lower performance than full GPT-5

### GPT-4 Series

#### **GPT-4o**
- **Type:** Multimodal General Purpose
- **Context Window:** 128K tokens
- **Strengths:**
  - Balanced performance
  - Multimodal (text, image, audio)
  - Predictable performance
- **Pricing:**
  - Input: $2.50/1M tokens
  - Output: $10.00/1M tokens
- **Use Cases:**
  - General business applications
  - Multimodal tasks
  - Balanced speed/cost

#### **GPT-4o Mini**
- **Type:** Fast/Cost-Effective
- **Context Window:** 128K tokens
- **Strengths:**
  - Fast response times
  - Very low cost
  - Good quality for simple tasks
- **Pricing:**
  - Input: $0.15/1M tokens
  - Output: $0.60/1M tokens
- **Use Cases:**
  - High-volume simple tasks
  - Quick responses needed
  - Budget-constrained projects

### o1 Series (Reasoning)

#### **o1-preview**
- **Type:** Complex Reasoning
- **Context Window:** ~128K tokens
- **Strengths:**
  - Advanced reasoning capabilities
  - Chain-of-thought processing
- **Pricing:**
  - Input: $15.00/1M tokens
  - Output: $60.00/1M tokens
- **Use Cases:**
  - Scientific reasoning
  - Complex math problems
  - Research tasks
- **Trade-offs:** Very expensive, slower

#### **o1-mini**
- **Type:** Fast Reasoning
- **Strengths:**
  - Faster than o1-preview
  - Good for coding tasks
- **Pricing:**
  - Input: $1.10/1M tokens
  - Output: $4.40/1M tokens
- **Use Cases:**
  - Coding tasks
  - Medium-complexity reasoning

---

## Performance Comparison

| Model | Coding % | SWE-bench | Math (AIME) | AGI (ARC-AGI-2) | Context | Speed | Cost (Input) |
|-------|----------|-----------|-------------|-----------------|---------|-------|--------------|
| **GPT-5.2** ⭐ | ~80% | ~80% | **100%** | **52.9%** | 400K | Medium | ~$2/1M |
| GPT-5.1 | ~77% | ~76% | ~85% | 17.6% | 400K | Fast | ~$1.25/1M |
| GPT-5 | 75% | 74.9% | ~80% | ~15% | 400K | Medium | $1.25/1M |
| GPT-5 Mini | ~50% | ~40% | ~40% | ~5% | 128K | Fast | $0.25/1M |
| GPT-4o | 31% | 30.8% | ~30% | ~3% | 128K | Fast | $2.50/1M |
| GPT-4o Mini | ~25% | ~20% | ~20% | ~2% | 128K | Very Fast | $0.15/1M |
| o1-preview | ~70% | ~65% | ~90% | ~20% | 128K | Slow | $15.00/1M |
| o1-mini | ~40% | ~35% | ~60% | ~8% | 128K | Medium | $1.10/1M |

**Key Insight:** GPT-5.2 represents a **major leap** in AGI capabilities (ARC-AGI-2: 52.9% vs 17.6%).

---

## Recommended Usage

### For Cassey AI Assistant (Updated):
1. **GPT-4o Mini** - Primary model for conversations (fast, cheap, good quality)
2. **GPT-5.1** - For complex tasks requiring AGI-level performance (faster than GPT-5.2)
3. **GPT-5.2** - For mathematical reasoning and AGI-benchmark tasks (when needed)
4. **GPT-4o** - For multimodal tasks (image processing)
5. **GPT-5 Mini** - For cost-effective complex tasks

### Cost Optimization Tips:
- Use **prompt caching** for repeated system prompts
- Use **GPT-4o Mini** for 80% of tasks
- Reserve **GPT-5** for complex tasks only
- Enable **streaming** for better UX

---

## Sources:
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Introducing GPT-5](https://openai.com/index/introducing-gpt-5/)
- [GPT-5 vs GPT-4o API Pricing: 2025 Cost Guide](https://www.creolestudios.com/gpt-5-vs-gpt-4o-api-pricing-comparison/)
- [LLM API Pricing Comparison (2025)](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
