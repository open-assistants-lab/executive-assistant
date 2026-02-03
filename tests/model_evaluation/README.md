# Model Evaluation Guide

## Purpose

Evaluate multiple Ollama Cloud models for use with the Executive Assistant to determine:
- Which model provides the best conversational experience
- Which model follows instructions most reliably
- Which model handles tool usage best
- Performance characteristics (latency, token usage)

## Models to Test

1. **gpt-oss:20b-cloud** (Baseline)
2. **kimi-k2.5:cloud**
3. **minimax-m2.1:cloud**
4. **deepseek-v3.2:cloud**
5. **qwen3-next:80b-cloud**

## Test Scenarios

### Scenario 1: Simple Onboarding
**Input**: "hi"

**What to evaluate**:
- Does the agent introduce itself?
- Does it ask about the user's role/goals?
- Is the tone warm and inviting?
- Does it explain WHY it's asking?

### Scenario 2: Role-Based Onboarding
**Input**: "I'm a data analyst. I need to track my daily work logs."

**What to evaluate**:
- Does it extract "data analyst" as the role?
- Does it capture "track daily work logs" as the goal?
- Are the suggested tools relevant to data analysis?
- Does it offer to create something specific?

### Scenario 3: Tool Creation
**Input**: "Yes please create it"

**What to evaluate**:
- Does it call `create_tdb_table` tool?
- Is the schema appropriate for the use case?
- Does it handle errors gracefully?
- Does it complete the workflow?

## Running Tests

### Step 1: Set Model

Edit `src/executive_assistant/config/settings.py` or use environment variable:

```bash
export DEFAULT_LLM_MODEL="gpt-oss:20b-cloud"
# or
export DEFAULT_LLM_MODEL="kimi-k2.5:cloud"
# etc
```

### Step 2: Start Agent

```bash
uv run executive_assistant
```

### Step 3: Run Test Script (in another terminal)

```bash
# From project root
python tests/model_evaluation/test_models.py
```

### Step 4: Manual Evaluation

The test script will:
- Send messages to the agent
- Capture responses
- Measure latency and tokens
- Save results to `model_evaluation_results.json`

You will need to manually evaluate:
- Conversational quality (1-5)
- Instruction following (PASS/FAIL)
- Information extraction (PASS/FAIL + details)
- Response relevance (1-5)
- Tool usage (PASS/FAIL)

### Step 5: Update RESULTS_TEMPLATE.md

Transfer your manual evaluations to the results template.

## Test Order

1. Test all models on Scenario 1 (simple onboarding)
2. Identify top performers
3. Test top performers on Scenarios 2 & 3
4. Fill in RESULTS_TEMPLATE.md
5. Determine overall rankings

## Evaluation Criteria

### ✅ PASS Criteria

**Conversational Quality**: Score ≥ 3/5
- Warm and professional tone
- Introduces agent
- Asks relevant questions

**Instruction Following**: PASS
- Follows onboarding flow
- Doesn't skip steps
- Calls tools when prompted

**Information Extraction**: PASS
- Extracts role correctly (± minor variation)
- Captures main goal
- Uses create_memory() properly

**Response Relevance**: Score ≥ 4/5
- Suggestions match user's stated role
- Recommendations are specific and actionable

**Tool Usage**: PASS
- Calls correct tool
- Parameters are properly formatted
- Handles errors appropriately

### ❌ FAIL Criteria

- Robotic or overly formal tone
- Misses key information
- Suggests irrelevant tools
- Fails to call tools when needed
- Tool parameters are malformed
- Crashes or hangs

## Expected Timeline

- Scenario 1 (all models): ~30 minutes
- Scenarios 2-3 (top models): ~45 minutes
- Manual evaluation: ~30 minutes
- Total: ~2 hours

## Notes

- Each test uses a fresh user_id to avoid cached state
- Delete test user folders between models for fair comparison
- Monitor agent logs for any errors or warnings
- Save interesting responses for qualitative comparison
