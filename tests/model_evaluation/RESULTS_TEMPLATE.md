# Model Evaluation Results

## Test Configuration
- **Date**: 2025-02-03
- **Agent**: Executive Assistant (Ken)
- **Test Environment**: Local (Ollama Cloud models)

## Models Under Test

| Model | Size | Notes |
|-------|------|-------|
| gpt-oss:20b-cloud | 20B | Baseline |
| kimi-k2.5:cloud | TBD | Moonshot AI |
| minimax-m2.1:cloud | TBD | MiniMax |
| deepseek-v3.2:cloud | TBD | DeepSeek |
| qwen3-next:80b-cloud | 80B | Alibaba Qwen |

## Evaluation Metrics

### 1. Conversational Quality (1-5)
- 1 = Poor, robotic, off-tone
- 3 = Average, functional but generic
- 5 = Excellent, natural, warm, professional

### 2. Instruction Following (PASS/FAIL)
- Follows system prompts correctly
- Adheres to onboarding flow
- Respects formatting requirements

### 3. Information Extraction (PASS/FAIL + Details)
- Extracts name correctly
- Identifies role accurately
- Captures user goals/preferences
- Creates memories with proper keys/types

### 4. Response Relevance (1-5)
- Suggestions match user's role
- Recommendations are actionable
- Response addresses user's stated needs

### 5. Tool Usage Accuracy (PASS/FAIL)
- Correct tool selection
- Proper JSON parameter formatting
- Error handling when tools fail

### 6. Reasoning Quality (1-5)
- Logical flow of suggestions
- Connects user role to relevant tools
- Prioritizes suggestions appropriately

### 7. Performance Metrics
- Response time (seconds)
- Token usage (input + output)

---

## Test Results

### Scenario 1: Simple Onboarding
User message: "hi"

| Model | Conv. Quality | Instr. Follow | Time | Tokens | Notes |
|-------|--------------|--------------|------|--------|-------|
| gpt-oss:20b-cloud | | | | | |
| kimi-k2.5:cloud | | | | | |
| minimax-m2.1:cloud | | | | | |
| deepseek-v3.2:cloud | | | | | |
| qwen3-next:80b-cloud | | | | | |

### Scenario 2: Role-Based Onboarding
User message: "I'm a data analyst. I need to track my daily work logs."

| Model | Info Extract | Role | Goal | Suggest. Quality | Notes |
|-------|-------------|------|------|-----------------|-------|
| gpt-oss:20b-cloud | | | | | |
| kimi-k2.5:cloud | | | | | |
| minimax-m2.1:cloud | | | | | |
| deepseek-v3.2:cloud | | | | | |
| qwen3-next:80b-cloud | | | | | |

### Scenario 3: Tool Creation
User message: "Yes please create it"

| Model | Tool Usage | Schema | Reasoning | Notes |
|-------|-----------|--------|-----------|-------|
| gpt-oss:20b-cloud | | | | |
| kimi-k2.5:cloud | | | | |
| minimax-m2.1:cloud | | | | | |
| deepseek-v3.2:cloud | | | | | |
| qwen3-next:80b-cloud | | | | | |

---

## Overall Rankings (after testing)

### Best Conversational Quality
1.
2.
3.

### Best Instruction Following
1.
2.
3.

### Best Tool Usage
1.
2.
3.

### Fastest Response Time
1.
2.
3.

### Most Token Efficient
1.
2.
3.

---

## Manual Evaluation Notes

### gpt-oss:20b-cloud
- *Strengths*:
- *Weaknesses*:
- *Recommendation*:

### kimi-k2.5:cloud
- *Strengths*:
- *Weaknesses*:
- *Recommendation*:

### minimax-m2.1:cloud
- *Strengths*:
- *Weaknesses*:
- *Recommendation*:

### deepseek-v3.2:cloud
- *Strengths*:
- *Weaknesses*:
- *Recommendation*:

### qwen3-next:80b-cloud
- *Strengths*:
- *Weaknesses*:
- *Recommendation*:

---

## Final Recommendation

**Best Overall Model**:

**Best for Tool Usage**:

**Best for Conversational Quality**:

**Best Value (performance/quality)**:
