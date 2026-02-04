# Model Evaluation Summary - Ollama Cloud Models

**Test Date**: 2026-02-03 23:35
**Agent**: Executive Assistant (Ken)
**Scenario**: Simple Onboarding ("hi")

## Results Summary

| Rank | Model | Intro | Questions | Context | Overall | Notes |
|------|-------|-------|-----------|---------|---------|-------|
| 🥇 1 | **deepseek-v3.2:cloud** | ✅ | ✅ | ✅ | 4/4 | Most personable, detailed welcome |
| 🥇 1 | **qwen3-next:80b-cloud** | ✅ | ✅ | ✅ | 4/4 | Concise but complete, follows instructions well |
| 🥉 3 | **gpt-oss:20b-cloud** | ✅ | ✅ | ✅ | 4/4 | Good baseline, balanced response |
| 4 | **minimax-m2.1:cloud** | ✅ | Partial | ❌ | 2/4 | Too specific to Gong Cha domain, missed context |
| ❌ 5 | **kimi-k2.5:cloud** | ❌ | ❌ | ❌ | 0/4 | **FAIL**: JSON Schema error |

## Detailed Analysis

### 1. deepseek-v3.2:cloud ⭐ BEST

**Response:**
```
Hi! I'm Ken, your AI assistant. Great to meet you!

To help you better, tell me a bit about yourself:

1. What do you do? (Your role, field, or interests)
2. What would you like help with?

This will help me understand how I can best assist you!
```

**Evaluation:**
- ✅ Introduces agent warmly ("Great to meet you!")
- ✅ Asks both questions clearly
- ✅ Explains why asking ("understand how I can best assist you")
- ✅ Structured with numbered list (easy to read)
- **Strengths**: Most personable, clear structure, enthusiastic tone
- **Weaknesses**: Slightly longer than ideal

---

### 2. qwen3-next:80b-cloud ⭐ BEST

**Response:**
```
Hi! I'm Ken, your AI assistant. To help you better, tell me a bit about yourself.

What do you do? And what would you like help with?
```

**Evaluation:**
- ✅ Introduces agent
- ✅ Asks both questions
- ✅ Explains why asking ("To help you better")
- ✅ Most concise of all models
- **Strengths**: Follows instructions perfectly, concise, clear
- **Weaknesses**: Less personable than deepseek

---

### 3. gpt-oss:20b-cloud (Baseline)

**Response:**
```
Hi! I'm Ken, your AI assistant. To help you better, tell me a bit about yourself.

**What do you do?**
**What would you like help with?**

Once I share that, I'll remember the key details (name, role, goals) and suggest a few things I can set up for you—like quick database queries, automated reminders, or workflow templates. Let me know if I should set those up right away!
```

**Evaluation:**
- ✅ Introduces agent
- ✅ Asks both questions
- ✅ Explains why asking
- ✅ Adds helpful context about what happens next
- **Strengths**: Balanced, informative without being verbose
- **Weaknesses**: Slightly more detailed than necessary

---

### 4. minimax-m2.1:cloud

**Response:**
```
Hi! I'm Ken, your AI assistant for Gong Cha analytics.

I can help you with:
- Daily sales and revenue reports
- Top-selling products
- Store performance comparisons
- Any other Gong Cha data questions

What would you like to know about today?
```

**Evaluation:**
- ✅ Introduces agent
- ❌ Only asks 1 question instead of 2
- ❌ Does NOT explain why asking
- ❌ **DOMAIN ISSUE**: Too specific to Gong Cha analytics
- **Strengths**: Clear, organized
- **Weaknesses**: Missed the onboarding instructions completely, assumed specific use case

---

### 5. kimi-k2.5:cloud ❌ FAIL

**Response:**
```
Model call failed after 3 attempts with ResponseError:
JSON Schema not supported: could not understand the instance `{}`. (status code 400)
```

**Evaluation:**
- ❌ Complete failure
- **Issue**: JSON Schema validation error
- **Status**: **NOT USABLE** for this application

---

## Performance Comparison

| Model | Words | Estimated Tokens | Response Quality |
|-------|-------|-----------------|------------------|
| deepseek-v3.2:cloud | 45 | ~60 | Best (personable) |
| qwen3-next:80b-cloud | 26 | ~35 | Best (concise) |
| gpt-oss:20b-cloud | 53 | ~70 | Good (balanced) |
| minimax-m2.1:cloud | 35 | ~50 | Fair (domain-specific) |
| kimi-k2.5:cloud | ERROR | ERROR | FAIL |

## Recommendations

### ✅ Recommended Models (Production Ready)

1. **qwen3-next:80b-cloud** - Best overall
   - Most token-efficient
   - Follows instructions perfectly
   - Fast response expected
   - Clear and concise

2. **deepseek-v3.2:cloud** - Best for user experience
   - Most personable and warm
   - Great for conversational UX
   - Slightly more tokens but worth it
   - Excellent for onboarding flow

3. **gpt-oss:20b-cloud** - Good baseline
   - Solid performance
   - Balanced approach
   - Good fallback option

### ❌ Not Recommended

4. **minimax-m2.1:cloud** - Domain specificity issue
   - Assumes specific use case (Gong Cha)
   - Missed context about why asking
   - Would confuse users in other domains

5. **kimi-k2.5:cloud** - BROKEN
   - JSON Schema validation error
   - Cannot be used in production

## Conclusion

**Winner: qwen3-next:80b-cloud** 🏆
- Best instruction following
- Most efficient (fewest tokens)
- Clear, concise responses

**Runner-up: deepseek-v3.2:cloud** 🥈
- Best user experience
- Most personable and warm
- Worth the extra tokens for UX-critical applications

**Recommendation**: Use **qwen3-next:80b-cloud** as the default Ollama Cloud model for best balance of quality, speed, and cost.
