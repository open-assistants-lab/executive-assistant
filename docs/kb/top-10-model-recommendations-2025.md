# Top 10 LLM Models for Executive Assistant AI (2025)

**Date:** 2025-01-19
**Purpose:** Model selection for performance testing and production deployment

---

## Executive Summary

Based on comprehensive research of OpenAI, Anthropic, Zhipu, and Ollama models, here are my top 10 recommended models for Executive Assistant AI assistant, ranked by suitability for conversational AI workloads.

**🔄 UPDATED:** Now prioritizing **Ollama Cloud models** for cloud-first deployment strategy (no local GPU required).

---

## Top 10 Models (Ranked)

### 🥇 #1: MiniMax M2:cloud (Ollama Cloud) ⭐ NEW!
**Best Overall for Executive Assistant (Cloud-First)**

#### Why #1:
- **Intelligence:** Ranked #1 among open-source models globally (AA Intelligence: 61)
- **Speed:** High-efficiency design (10B activated/230B total parameters)
- **Cost:** Free tier available, Pro $20/mo, Max $100/mo
- **Quality:** Competitive with GPT-5 and Claude Sonnet 4.5
- **Agentic:** Built specifically for agentic workflows and coding
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Benchmark Performance:
- **SWE-bench Verified:** 69.4 (competitive with GPT-5's 74.9)
- **Terminal-Bench:** 46.3 (significantly beats Claude Sonnet 4's 36.4)
- **Multi-SWE-Bench:** 36.2 (excellent multilingual coding)
- **GAIA (text):** 75.7 (superior agentic performance)
- **AA Intelligence:** 61 (vs Claude Sonnet 4.5: 63, GPT-5: 69)

#### Use Cases:
- **Primary model for Executive Assistant AI assistant**
- Coding and agentic workflows
- Multi-file editing and terminal tasks
- Complex tool chains and browser automation
- Production deployments requiring speed + quality

#### Trade-offs:
- Newer model (less battle-tested than GPT-4/Claude)
- Requires internet connection (cloud-only)

---

### 🥈 #2: GLM-4.7:cloud (Ollama Cloud) ⭐ NEW!
**Best for Coding Tasks**

#### Why #2:
- **Performance:** Beats GPT-5.2 and Claude in several benchmarks
- **Coding:** Best-in-class coding performance (SWE-bench: 73.8%)
- **Improvements:** +5.8% SWE-bench, +12.9% multilingual, +16.5% terminal over GLM-4.6
- **Context:** 198K tokens (excellent for long conversations)
- **Vibe Coding:** Major step forward in UI quality
- **Reasoning:** HLE 42.8% (+12.4% over GLM-4.6)
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Use Cases:
- **Primary coding model for Executive Assistant**
- Multilingual coding tasks
- Terminal-based workflows
- UI generation (vibe coding)
- Mathematical reasoning
- Complex tool-using scenarios

#### Trade-offs:
- Newer model (less community testing)
- Chinese provider (Zhipu AI)
- Potential latency outside Asia

---

### 🥉 #3: Gemini 3 Flash Preview:cloud (Ollama Cloud) ⭐ NEW!
**Best for Speed + Frontier Intelligence**

#### Why #3:
- **Speed:** Built for speed at a fraction of the cost
- **Intelligence:** GPQA Diamond 90.4% (PhD-level reasoning)
- **HLE:** 33.7% without tools (rivals larger frontier models)
- **MMMU Pro:** 81.2% (state-of-the-art)
- **Multimodal:** Vision + text capabilities
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Use Cases:
- **Fast responses with frontier intelligence**
- Speed-critical applications
- Multimodal tasks (vision + text)
- PhD-level reasoning and knowledge benchmarks
- When you need Gemini 3 Pro quality at Flash speed

#### Trade-offs:
- Preview model (may have stability issues)
- Newer release (less battle-tested)

---

### #4: GPT-4o Mini (OpenAI)
**Best for Production Workloads (Non-Cloud)**

#### Why #4:
- **Speed:** Expected TTFT 2-5s (3-6× faster than GPT-5 Mini)
- **Cost:** $0.15/1M input, $0.60/1M output (very affordable)
- **Quality:** Excellent for 95% of conversational tasks
- **Maturity:** Battle-tested, reliable, excellent ecosystem
- **Context:** 128K tokens (sufficient for long conversations)

#### Use Cases:
- Production workloads when Ollama Cloud is unavailable
- High-volume tasks
- When you need OpenAI ecosystem reliability
- Backup to Ollama Cloud models

#### Trade-offs:
- Not as capable as GPT-5 for complex reasoning
- Higher cost than Ollama Cloud free tier
- No local option (API-only)

---

### #5: DeepSeek V3.2:cloud (Ollama Cloud) ⭐ NEW!
**Best for Long-Context Reasoning**

#### Why #5:
- **DSA:** DeepSeek Sparse Attention for efficient long-context
- **Context:** 160K tokens (excellent for long conversations)
- **Reasoning:** Performs comparably to GPT-5
- **Agent Performance:** Superior agentic task synthesis
- **Efficiency:** Reduces computational complexity while preserving performance
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Use Cases:
- **Long-context reasoning tasks**
- Complex multi-step problem solving
- Agentic workflows requiring tool use
- When you need GPT-5-level performance at lower cost

#### Trade-offs:
- Newer model (less tested)
- May have latency issues (cloud-dependent)

---

### #6: Claude Haiku 4.5 (Anthropic)
**Best for Speed & Safety (Non-Cloud)**

#### Why #6:
- **Speed:** Fastest Claude model (likely TTFT 1-3s)
- **Cost:** ~$0.25/1M input, $1.25/1M output (very affordable)
- **Safety:** Anthropic's safest model with fewest deviation behaviors
- **Quality:** Good for simple to medium complexity tasks
- **Context:** 200K tokens (largest context window)

#### Use Cases:
- Quick responses for simple queries
- High-volume customer support
- When safety is critical
- Backup to Ollama Cloud models

#### Trade-offs:
- Can be shallow in reasoning
- Not suitable for complex multi-step tasks
- Higher cost than Ollama Cloud free tier

---

### #7: GPT-OSS 120B:cloud (Ollama Cloud) ⭐ NEW!
**Best Open-Weight General Purpose Model**

#### Why #7:
- **OpenAI Quality:** OpenAI's open-weight models
- **Agentic:** Designed for powerful reasoning and agentic tasks
- **Flexibility:** Open weights with OpenAI-level quality
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Use Cases:
- General-purpose tasks requiring OpenAI quality
- Open-source preference with OpenAI performance
- Agentic workflows
- Development workflows

#### Trade-offs:
- Less documentation than proprietary models
- Newer to Ollama Cloud ecosystem

---

### #8: Claude Sonnet 4.5 (Anthropic)
**Best Balance (Non-Cloud)**

#### Why #8:
- **Quality:** Higher intelligence than Haiku
- **Speed:** 2× faster than Claude 2, good TTFT
- **Balance:** Ideal for sustained daily workloads
- **Context:** 200K tokens (excellent)
- **Maturity:** Well-tested, reliable

#### Use Cases:
- Production workloads when Ollama Cloud unavailable
- Business applications
- Quality-focused applications
- Backup to Ollama Cloud models

#### Trade-offs:
- More expensive (~$3/1M input, $15/1M output)
- Not as fast as Haiku/GPT-4o Mini
- Higher cost than Ollama Cloud

---

### #9: Qwen3-Coder 480B:cloud (Ollama Cloud) ⭐ NEW!
**Best Large-Scale Coding Model**

#### Why #9:
- **Specialization:** Alibaba's performant coding model
- **Size:** 480B parameters for complex coding tasks
- **Long Context:** Excellent for large codebases
- **No Local GPU:** Runs on Ollama's cloud infrastructure

#### Use Cases:
- Complex coding assistance
- Large-scale code review
- Programming education
- Technical documentation

#### Trade-offs:
- Larger model (may be slower)
- Specialized for coding (not general conversational AI)

---

### #10: GLM-4 Flash (Zhipu)
**Best Free Tier (API)**

#### Why #10:
- **Cost:** 100% FREE (with rate limits)
- **Performance:** Decent quality
- **Context:** 128K tokens

#### Use Cases:
- Development and testing
- Prototyping
- Low-volume applications
- Learning and experimentation

#### Trade-offs:
- Rate limits apply
- May have queue delays
- Not production-ready for high volume

---

## Summary Table

| Rank | Model | Provider | TTFT (est) | Cost/1M | Quality | Best For | Deployment |
|------|-------|----------|------------|---------|---------|----------|------------|
| 🥇 | **MiniMax M2** | Ollama Cloud | 2-5s | $0 (free tier) | ⭐⭐⭐⭐⭐ | **Agentic workflows** | Cloud |
| 🥈 | **GLM-4.7** | Ollama Cloud | 3-6s | $0 (free tier) | ⭐⭐⭐⭐⭐ | **Coding** | Cloud |
| 🥉 | **Gemini 3 Flash** | Ollama Cloud | 1-4s | $0 (free tier) | ⭐⭐⭐⭐⭐ | **Speed + frontier intelligence** | Cloud |
| 4 | **GPT-4o Mini** | OpenAI | 2-5s | $0.60 | ⭐⭐⭐⭐ | Production, speed | API |
| 5 | **DeepSeek V3.2** | Ollama Cloud | 4-8s | $0 (free tier) | ⭐⭐⭐⭐⭐ | Long-context (160K) | Cloud |
| 6 | **Claude Haiku 4.5** | Anthropic | 1-3s | $1.25 | ⭐⭐⭐ | Speed, safety | API |
| 7 | **GPT-OSS 120B** | Ollama Cloud | 4-8s | $0 (free tier) | ⭐⭐⭐⭐ | Open-weight general | Cloud |
| 8 | **Claude Sonnet 4.5** | Anthropic | 3-6s | $15.00 | ⭐⭐⭐⭐ | Balance | API |
| 9 | **Qwen3-Coder 480B** | Ollama Cloud | 4-10s | $0 (free tier) | ⭐⭐⭐⭐⭐ | Large-scale coding | Cloud |
| 10 | **GLM-4 Flash** | Zhipu | 5-10s | $0 | ⭐⭐⭐ | Free tier | API |

**🔥 Key Insight:** **Ollama Cloud dominates the top 10** with 5 models in top positions, offering competitive performance at zero cost (free tier).

---

---

## My Top 3 Recommendations for Performance Testing

Based on Executive Assistant's requirements (conversational AI, speed critical, quality important, **cloud-first deployment**), here are the **top 3 Ollama Cloud models to test**:

### 1️⃣ **MiniMax M2:cloud** (Ollama Cloud) ⭐ PRIMARY RECOMMENDATION
**Why:** Ranked #1 among open-source models globally, specifically built for agentic workflows and coding.

**Expected Performance:**
- TTFT: 2-5s (high-efficiency design)
- Total time: 5-9s
- Tokens/sec: 70-110 tok/s
- Quality: Competitive with GPT-5 and Claude Sonnet 4.5

**Benchmark Strengths:**
- SWE-bench Verified: 69.4 (near GPT-5's 74.9)
- Terminal-Bench: 46.3 (beats Claude Sonnet 4's 36.4)
- GAIA (text): 75.7 (excellent agentic performance)
- AA Intelligence: 61 (vs Claude Sonnet 4.5: 63, GPT-5: 69)

**Test Setup:**
```bash
# Ensure Ollama is running
ollama serve

# Test MiniMax M2 via Ollama Cloud
ollama run minimax-m2:cloud
```

**Benchmark Command (adapt existing script):**
```bash
# Using Ollama's OpenAI-compatible API
export OLLAMA_API_BASE="http://localhost:11434/v1"
export OLLAMA_API_KEY="ollama"

uv run python scripts/llm_benchmark.py \
  --providers openai \
  --models minimax-m2:cloud \
  --scenarios simple_qa simple_explanation web_search_single \
  --iterations 3 \
  --api-base http://localhost:11434/v1
```

---

### 2️⃣ **GLM-4.7:cloud** (Ollama Cloud) ⭐ CODING SPECIALIST
**Why:** Best-in-class coding performance, beats GPT-5.2 and Claude in several benchmarks.

**Expected Performance:**
- TTFT: 3-6s
- Total time: 6-11s
- Tokens/sec: 60-100 tok/s
- Quality: Superior coding capabilities

**Benchmark Strengths:**
- SWE-bench: 73.8% (best-in-class)
- SWE-bench Multilingual: 66.7% (+12.9% over GLM-4.6)
- Terminal Bench 2.0: 41% (+16.5% over GLM-4.6)
- HLE: 42.8% (+12.4% over GLM-4.6)
- Context: 198K tokens

**Test Setup:**
```bash
ollama run glm-4.7:cloud
```

**Benchmark Command:**
```bash
uv run python scripts/llm_benchmark.py \
  --providers openai \
  --models glm-4.7:cloud \
  --scenarios simple_qa simple_explanation web_search_single db_operation \
  --iterations 3 \
  --api-base http://localhost:11434/v1
```

---

### 3️⃣ **Gemini 3 Flash Preview:cloud** (Ollama Cloud) ⭐ SPEED + INTELLIGENCE
**Why:** Frontier intelligence built for speed - PhD-level reasoning at Flash speeds.

**Expected Performance:**
- TTFT: 1-4s (potentially the fastest)
- Total time: 4-8s
- Tokens/sec: 90-150 tok/s
- Quality: GPQA Diamond 90.4% (PhD-level)

**Benchmark Strengths:**
- GPQA Diamond: 90.4% (PhD-level reasoning)
- HLE (no tools): 33.7% (rivals larger frontier models)
- MMMU Pro: 81.2% (state-of-the-art)
- Multimodal: Vision + text capabilities

**Test Setup:**
```bash
ollama run gemini-3-flash-preview:cloud
```

**Benchmark Command:**
```bash
uv run python scripts/llm_benchmark.py \
  --providers openai \
  --models gemini-3-flash-preview:cloud \
  --scenarios simple_qa simple_explanation web_search_single \
  --iterations 3 \
  --api-base http://localhost:11434/v1
```

---

## Recommended Testing Strategy

### Phase 1: Speed Comparison (Quick Win)
Test the 3 Ollama Cloud models with simple scenarios to confirm speed improvements.

**Expected Outcome:**
- All 3 should be significantly faster than GPT-5 Mini (12.75s)
- Target: <8s average response time
- MiniMax M2 and Gemini 3 Flash should be fastest (1-5s TTFT)

### Phase 2: Quality Assessment
If speed is acceptable, test quality with complex Executive Assistant-specific scenarios:
- `db_operation` (database interactions)
- `research_and_store` (tool use workflows)
- `long_context` (memory retention)
- `coding_tasks` (if using Python tool)

**Expectations:**
- **MiniMax M2:** Excellent for agentic workflows and coding
- **GLM-4.7:** Superior for coding tasks (73.8% SWE-bench)
- **Gemini 3 Flash:** Best for speed + PhD-level reasoning

### Phase 3: Production Decision
Based on results:
- **If MiniMax M2 performs best:** Use as primary (agentic workflows, best balance)
- **If GLM-4.7 excels at coding:** Use as coding model (best-in-class)
- **If Gemini 3 Flash is fastest:** Use for simple queries (speed-critical)
- **All 3 can be used:** Specialized roles for each model

---

## Configuration Recommendations (Ollama Cloud-First)

### Recommended Configuration (Multi-Model Strategy):

```yaml
llm:
  default_provider: ollama
  ollama:
    api_base: http://localhost:11434
    api_key: ollama  # Required but unused

    # Primary model for general conversational AI
    default_model: minimax-m2:cloud

    # Specialized models
    coding_model: glm-4.7:cloud           # Best-in-class coding
    reasoning_model: deepseek-v3.2:cloud  # Long-context (160K)
    fast_model: gemini-3-flash-preview:cloud  # Fastest responses

    # Alternative options
    # general_model: gpt-oss:120b-cloud    # OpenAI quality open weights
    # multimodal_model: qwen3-vl:235b-cloud  # Vision + text

  # Fallback to API providers if Ollama Cloud unavailable
  openai:
    api_key: ${OPENAI_API_KEY}
    default_model: gpt-4o-mini  # Backup

  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    default_model: claude-haiku-4-20250514  # Backup
```

### Alternative: Single-Model Configuration (Simpler)

```yaml
llm:
  default_provider: ollama
  ollama:
    api_base: http://localhost:11434
    default_model: minimax-m2:cloud  # Use MiniMax M2 for everything
```

---

## Cost Comparison (Monthly Estimate)

Assuming **10,000 messages/month**, **500 input tokens** + **500 output tokens** per message:

| Model | Monthly Cost | Annual Cost | Notes |
|-------|--------------|-------------|-------|
| **Ollama Cloud (Free Tier)** | **$0** | **$0** | With rate limits |
| Ollama Cloud (Pro) | $20 | $240 | Higher limits |
| Ollama Cloud (Max) | $100 | $1,200 | 5× Pro limits |
| GLM-4 Flash (Zhipu) | $0 | $0 | Free tier with rate limits |
| GPT-4o Mini (OpenAI) | $3.75 | $45 | Per 1M tokens pricing |
| Claude Haiku 4.5 | $7.50 | $90 | Per 1M tokens pricing |
| GLM-4.7 (Zhipu API) | ~$12 | ~$144 | Per 1M tokens pricing |
| GPT-5 Mini (OpenAI) | $11.25 | $135 | Per 1M tokens pricing |
| Claude Sonnet 4.5 | $90.00 | $1,080 | Per 1M tokens pricing |

**🏆 Winner:** **Ollama Cloud (Free Tier)** at **$0/month** for production use (with rate limits).

**Note:** Ollama Cloud usage-based pricing coming soon, which may affect these estimates.

---

## Final Recommendation (Cloud-First Strategy)

**Primary Recommendation:** **Use MiniMax M2:cloud as Executive Assistant's primary model.**

**Why MiniMax M2:cloud:**
1. ✅ **#1 ranked open-source model globally** (AA Intelligence: 61)
2. ✅ **Built for agentic workflows** (Executive Assistant's primary use case)
3. ✅ **Excellent coding performance** (SWE-bench: 69.4)
4. ✅ **Free tier available** (no API costs)
5. ✅ **No local GPU required** (cloud deployment)
6. ✅ **OpenAI-compatible API** (easy integration)

**Secondary Models:**
- **GLM-4.7:cloud** for coding tasks (best-in-class 73.8% SWE-bench)
- **Gemini 3 Flash Preview:cloud** for speed-critical queries (fastest TTFT)
- **DeepSeek V3.2:cloud** for long-context reasoning (160K tokens)

**Fallback Options (if Ollama Cloud unavailable):**
- **GPT-4o Mini** (OpenAI) - Reliable backup, excellent speed
- **Claude Haiku 4.5** (Anthropic) - Fast and safe

**Testing Priority:**
1. Start with **MiniMax M2:cloud** benchmarking
2. Test **GLM-4.7:cloud** for coding-specific workflows
3. Test **Gemini 3 Flash Preview:cloud** for speed comparison
4. Measure actual performance vs. expectations
5. Make final decision based on real-world Executive Assistant workflows

---

## Next Steps

1. **Set up Ollama** (if not already installed):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Create Ollama Cloud account** (for free tier):
   - Visit https://ollama.com/cloud
   - Sign up for free tier

3. **Run benchmarks** on the top 3 Ollama Cloud models:
   ```bash
   # Test MiniMax M2:cloud
   ollama run minimax-m2:cloud

   # Test GLM-4.7:cloud
   ollama run glm-4.7:cloud

   # Test Gemini 3 Flash Preview:cloud
   ollama run gemini-3-flash-preview:cloud
   ```

4. **Analyze results**:
   - Look for TTFT <5s, total time <8s
   - Compare quality across Executive Assistant workflows
   - Check rate limits on free tier

5. **Quality check** - Test with real Executive Assistant workflows:
   - Conversational interactions
   - Tool use (db operations, web search)
   - Memory retention (long context)

6. **Make decision** - Choose primary model based on:
   - Speed (TTFT and total response time)
   - Quality (benchmark performance)
   - Cost (free tier limits)
   - Reliability (uptime, consistency)

7. **Update config** - Deploy winning model to production:
   ```yaml
   llm:
     default_provider: ollama
     ollama:
       api_base: http://localhost:11434
       default_model: minimax-m2:cloud  # Or your chosen model
   ```

8. **Monitor usage** - Track free tier limits:
   - Upgrade to Pro ($20/mo) if needed
   - Consider Max ($100/mo) for high-volume production

---

## Summary: Why Ollama Cloud is the Best Choice for Executive Assistant

### Key Advantages:
1. **Cost:** $0/month (free tier) vs. $3.75-$90/month for API providers
2. **Performance:** Competitive with GPT-5/Claude Sonnet 4.5
3. **No Local GPU:** Runs on Ollama's cloud infrastructure
4. **Flexibility:** Easy switching between models (just change `:cloud` tag)
5. **Privacy:** Ollama does not log prompt or response data
6. **OpenAI-Compatible:** Drop-in replacement for existing OpenAI integrations

### Recommended Models Summary:
| Rank | Model | Best For | Cost | Why |
|------|-------|----------|------|-----|
| 🥇 | **MiniMax M2:cloud** | Agentic workflows | Free | #1 open-source, built for agents |
| 🥈 | **GLM-4.7:cloud** | Coding | Free | Best-in-class coding (73.8% SWE-bench) |
| 🥉 | **Gemini 3 Flash:cloud** | Speed | Free | Fastest + PhD-level reasoning |

### Final Verdict:
**Ollama Cloud + MiniMax M2:cloud** offers the best combination of:
- ✅ Performance (competitive with GPT-5)
- ✅ Cost ($0 free tier)
- ✅ Ease of use (no local GPU)
- ✅ Specialization (agentic workflows)

---

**Sources:**
- [Ollama Cloud](https://ollama.com/cloud)
- [Ollama Cloud Models Search](https://ollama.com/search?c=cloud)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Models overview - Claude Docs](https://platform.claude.com/docs/en/about-claude/models/overview)
- [ZHIPU AI - Open Platform](https://open.bigmodel.cn/)
- Full provider documentation in `docs/kb/`:
  - `docs/kb/ollama-cloud-models-2025.md` (NEW)
  - `docs/kb/openai-models-2025.md`
  - `docs/kb/anthropic-claude-models-2025.md`
  - `docs/kb/zhipu-glm-models-2025.md`
