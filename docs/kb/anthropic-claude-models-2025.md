# Anthropic Claude Models Reference (2025)

**Last Updated:** 2025-01-19
**Provider:** Anthropic
**Website:** https://platform.claude.com/docs/en/about-claude/models/overview

---

## Model Overview

Anthropic offers three main Claude models, each optimized for different use cases: Opus (maximum intelligence), Sonnet (balanced), and Haiku (fastest).

---

## Available Models

### Claude Opus 4.5

#### **Characteristics**
- **Type:** Maximum Intelligence
- **Release:** November 2025
- **Context Window:** 200K tokens
- **Strengths:**
  - Highest intelligence in Claude family
  - Surgical precision in reasoning
  - Depth in complex multi-step reasoning
  - Beats Sonnet 4.5 on internal benchmarks
  - Uses fewer tokens than Sonnet for same tasks
- **Use Cases:**
  - Complex reasoning tasks
  - Specialized domains (medical, legal, scientific)
  - Multi-step problem solving
  - Projects requiring maximum depth and accuracy
  - Research and analysis
- **Trade-offs:**
  - Slower performance
  - Higher cost
  - Overkill for simple tasks

### Claude Sonnet 4.5

#### **Characteristics**
- **Type:** Balanced Performance
- **Release:** 2025
- **Context Window:** 200K tokens
- **Strengths:**
  - Best balance of quality, speed, and capability
  - 2× faster than Claude 2/2.1 with higher intelligence
  - Maintains context effectively
  - Handles multi-file code discussions well
  - Ideal for sustained daily workloads
- **Use Cases:**
  - Daily sustained use
  - Most general business applications
  - Balanced workloads
  - Conversational AI
  - Code assistance
  - Content generation
- **Trade-offs:**
  - Not as fast as Haiku
  - Not as capable as Opus for complex tasks

### Claude Haiku 4.5

#### **Characteristics**
- **Type:** Speed & Cost Optimized
- **Release:** 2025
- **Context Window:** 200K tokens
- **Strengths:**
  - Fastest Claude model
  - Lowest latency
  - Highest throughput
  - Most cost-effective
  - Safest model (fewest deviation behaviors)
  - Enhanced safety features
- **Use Cases:**
  - High-volume simple tasks
  - Speed-critical applications
  - Cost-sensitive projects
  - Simple Q&A
  - Content classification
  - Quick responses
- **Trade-offs:**
  - Can be shallow in reasoning
  - Not suitable for complex tasks

---

## Performance Comparison

| Model | Intelligence | Speed | Cost | Best For |
|-------|--------------|-------|------|----------|
| **Opus 4.5** | ⭐⭐⭐⭐⭐ | ⭐⭐ | $$$$ | Complex reasoning, specialized tasks |
| **Sonnet 4.5** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $$ | Daily use, balanced workloads |
| **Haiku 4.5** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $ | High-volume, speed-critical tasks |

### Relative Performance

**Speed:** Haiku > Sonnet > Opus
**Intelligence:** Opus > Sonnet > Haiku
**Cost Efficiency:** Haiku > Sonnet > Opus

---

## Model Selection Guide

### Choose Opus 4.5 when:
- Task requires maximum intelligence and depth
- Multi-step complex reasoning needed
- Specialized domain knowledge required
- Cost and speed are not primary concerns
- Accuracy is critical

**Examples:**
- Medical diagnosis assistance
- Legal research and analysis
- Scientific research
- Complex coding tasks with architecture decisions

### Choose Sonnet 4.5 when:
- You need balanced performance
- Sustained daily usage
- General business applications
- Most conversational AI workloads
- Cost and speed both matter

**Examples:**
- Customer support chatbot
- Code assistant
- Content generation
- Data analysis
- Document review

### Choose Haiku 4.5 when:
- Speed is critical
- High volume of simple tasks
- Budget is a constraint
- Tasks don't require deep reasoning
- Fast response time is UX priority

**Examples:**
- Simple Q&A
- Content classification
- Sentiment analysis
- Quick summarization
- High-volume customer queries

---

## Pricing (Estimated)

*Note: Exact pricing varies by region and usage tier. Contact Anthropic for accurate quotes.*

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Relative Cost |
|-------|----------------------|----------------------|---------------|
| Opus 4.5 | ~$15.00 | ~$75.00 | Very High |
| Sonnet 4.5 | ~$3.00 | ~$15.00 | Medium |
| Haiku 4.5 | ~$0.25 | ~$1.25 | Low |

---

## Recommended Usage for Cassey

### Primary Model: **Claude Sonnet 4.5**
- Best balance for conversational AI
- Good quality without breaking the bank
- Sufficient for most user tasks

### Secondary Model: **Claude Haiku 4.5**
- Use for simple queries
- Quick responses for basic questions
- Cost savings on high-volume tasks

### Premium Tier: **Claude Opus 4.5**
- Reserve for complex coding tasks
- Deep analysis requests
- When user explicitly requests higher quality

### Recommended Configuration:

```yaml
llm:
  anthropic:
    default_model: claude-sonnet-4-20250514  # Sonnet 4.5
    fast_model: claude-haiku-4-20250514      # Haiku 4.5
    premium_model: claude-opus-4-20250514     # Opus 4.5 (if needed)
```

---

## Safety Features

All Claude models include:
- Constitutional AI training
- Harmlessness training
- Avoidance of harmful content
- Transparency about limitations

**Haiku 4.5** has the fewest deviation behaviors, making it Anthropic's safest model.

---

## Context Window

All Claude 4.5 models support **200K token context windows**, enabling:
- Long conversations
- Large document analysis
- Multi-file code discussions
- Extended context retention

---

## Sources:
- [Models overview - Claude Docs](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Introducing Claude Opus 4.5](https://www.anthropic.com/news/claude-opus-4-5)
- [Claude Haiku 4.5 vs Sonnet 4.5: Detailed Comparison 2025](https://www.creolestudios.com/claude-haiku-4-5-vs-sonnet-4-5-comparison/)
- [Claude AI Models 2025: Opus vs Sonnet vs Haiku Guide](https://dev.to/dr_hernani_costa/claude-ai-models-2025-opus-vs-sonnet-vs-haiku-guide-24mn)
- [Sonnet 4.5 vs Haiku 4.5 vs Opus 4.1 — Which Claude model actually works best](https://medium.com/@ayaanhaider.dev/sonnet-4-5-vs-haiku-4-5-vs-opus-4-1-which-claude-model-actually-works-best-in-real-projects-7183c0dc2249)
