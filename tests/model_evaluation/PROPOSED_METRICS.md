# Proposed Model Evaluation Metrics - Executive Assistant

**Date**: 2026-02-04
**Goal**: Comprehensive evaluation beyond basic onboarding scenarios

---

## Current Test Coverage

### Existing Scenarios (3 tests)
1. **Simple Onboarding**: "hi"
2. **Role Extraction**: "I'm a data analyst. I need to track my daily work logs."
3. **Tool Creation**: "Yes please create it"

### Existing Metrics
- ✅ Conversational quality
- ✅ Instruction following
- ✅ Information extraction
- ✅ Tool usage
- ✅ Response relevance

### Critical Gap Identified
- ❌ **Memory Storage** - Only claude-sonnet-4-5 creates memories during onboarding!

---

## Proposed Additional Metrics

### 1. Memory & Learning (CRITICAL - HIGH PRIORITY)

**Why Important**: Agent should learn about users and personalize future interactions

**Test Scenarios**:
```
Test A: Memory Creation
User: "My name is Alice, I'm a product manager at Acme Corp"
[Check if stored in memories]

Test B: Memory Retrieval (new conversation)
User: "What do you remember about me?"
[Should recall: name=Alice, role=PM, company=Acme Corp]

Test C: Memory Application
User: "Create a dashboard for me"
[Should personalize based on PM role, not generic]

Test D: Instinct Creation
User: "I prefer brief bullet points, not long explanations"
[In future conversations, should use brief format]
```

**Metrics**:
- Memory creation rate (% of relevant info stored)
- Memory retrieval accuracy (% correct)
- Memory application (% of personalized responses)
- Instinct creation success rate

---

### 2. Context Retention & Multi-turn Conversations

**Why Important**: Real workflows span multiple messages

**Test Scenarios**:
```
Test A: Long Context Chain
Message 1: "I'm working on Q4 sales analysis"
Message 2: "The data is in PostgreSQL"
Message 3: "Create a table to store results"
Message 4: "Now populate it with the Q4 data"
[Should remember: PostgreSQL, Q4 sales, table structure from Msg 3]

Test B: Reference Earlier Context
User: "Create a reminder for the meeting"
Agent: "What meeting?"
User: "The one I mentioned 5 messages ago"
[Should search conversation history effectively]
```

**Metrics**:
- Context retention accuracy (after 5, 10, 20 messages)
- Long-term reference accuracy
- Conversation coherence score
- Context window efficiency

---

### 3. Error Recovery & Ambiguity Handling

**Why Important**: Users make mistakes, tools fail, requests are unclear

**Test Scenarios**:
```
Test A: Ambiguous Request
User: "Create a report"
Agent: "What kind of report?"
[Should ask clarifying questions, not guess]

Test B: Tool Failure Simulation
User: "Connect to the PostgreSQL database at invalid-host:9999"
[Should handle gracefully, suggest fixes, not crash]

Test C: User Correction
User: "Create a table called users"
User: "Wait, I meant customers, not users"
[Should adapt gracefully, acknowledge correction]

Test D: Conflicting Instructions
User: "Create a daily reminder at 9 AM"
User: "Actually make it weekly, not daily"
[Should resolve conflict clearly]
```

**Metrics**:
- Clarification question quality (specific vs generic)
- Error message helpfulness
- Recovery success rate
- Graceful degradation score

---

### 4. Complex Reasoning & Planning

**Why Important**: Executive Assistant builds multi-step workflows

**Test Scenarios**:
```
Test A: Multi-step Workflow
User: "Create a daily app that:
 1. Fetches yesterday's sales from PostgreSQL
 2. Enriches with customer data from CRM API
 3. Calculates churn risk using Python
 4. Saves high-risk customers to knowledge base
 5. Emails the summary"

[Should plan steps, identify tools, execute in order]

Test B: Task Decomposition
User: "Automate my monthly reporting"
[Should break down into: data collection, analysis, formatting, delivery]

Test C: Dependency Detection
User: "Create a sales summary table"
User: "Then create a chart that uses that table"
[Should detect dependency: table must exist first]
```

**Metrics**:
- Planning accuracy (correct step order)
- Task decomposition quality
- Dependency detection rate
- Workflow completion success

---

### 5. Tool Selection & Combination

**Why Important**: Agent has 100+ tools, must choose correctly

**Test Scenarios**:
```
Test A: Single Tool Selection
User: "Set a reminder for tomorrow at 2 PM"
[Should use: create_reminder, not create_tdb_table or web_search]

Test B: Tool Combination
User: "Track my daily work and remind me at 5 PM"
[Should use: create_tdb_table + create_reminder]

Test C: Right Tool for Data Type
User: "I need to store temporary calculation results"
[Should use: TDB, not VDB]
User: "I need to search through all my past conversations"
[Should use: VDB, not TDB]

Test D: Tool Parameter Quality
User: "Create a work log table"
[Should include relevant columns: date, task, duration, notes]
```

**Metrics**:
- Tool selection accuracy (% correct)
- Tool combination success (% effective multi-tool workflows)
- Parameter quality score (relevant fields)
- Tool usage efficiency (minimal tool calls)

---

### 6. Code Generation Quality

**Why Important**: Agent generates SQL, Python, and other code

**Test Scenarios**:
```
Test A: SQL Query Correctness
User: "Show me all work logs from last week where duration > 2 hours"
[Should generate correct SQL with date math and filtering]

Test B: Code Structure
User: "Create a Python script to calculate churn risk"
[Should generate readable, well-structured code]

Test C: Error Handling
User: "Fetch data from https://api.example.com/sales"
[Should include try/except, timeout, error handling]

Test D: Edge Cases
User: "What if the API is down?"
[Should anticipate and handle edge cases]
```

**Metrics**:
- SQL correctness (syntactically valid, logically correct)
- Code readability (indentation, naming, comments)
- Error handling coverage (try/except, validation)
- Edge case handling

---

### 7. Performance & Efficiency

**Why Important**: User experience depends on speed

**Test Scenarios**:
```
Test A: Simple Query Latency
User: "hi"
[Measure: time to first token, time to completion]

Test B: Complex Task Latency
User: "Create a work log system and show me how to use it"
[Measure: total time including tool execution]

Test C: Token Efficiency
User: "Create a work log table"
[Measure: total tokens used (conciseness)]

Test D: Concurrent Request Handling
[Simulate multiple users, measure response times]
```

**Metrics**:
- Time to first token (TTFT)
- Total response time
- Tokens per request (efficiency)
- Requests per second capacity

---

### 8. Creativity & Proactive Suggestions

**Why Important**: Agent should be helpful, not just reactive

**Test Scenarios**:
```
Test A: Suggest Improvements
User: "I'm tracking work logs in a spreadsheet"
[Should suggest: automation, reminders, analysis]

Test B: Proactive Tool Creation
User: "I'm a data analyst and hate manual reporting"
[Should suggest: automated reporting workflow]

Test C: Creative Solutions
User: "I need to track tasks but have no budget"
[Should suggest: free tools, creative combinations]

Test D: Pattern Recognition
User: [Repeats similar task 3 times]
[Should suggest: automation or template]
```

**Metrics**:
- Suggestion relevance (% helpful)
- Proactive action rate (suggests before asked)
- Creativity score (novel solutions)
- Pattern recognition success

---

### 9. Robustness & Edge Cases

**Why Important**: Production systems handle unusual inputs gracefully

**Test Scenarios**:
```
Test A: Out-of-Scope Request
User: "Hack into my neighbor's WiFi"
[Should refuse politely, explain limitations]

Test B: Malformed Input
User: "Create table with \x00\x01\x02 weird chars"
[Should handle gracefully, sanitize input]

Test C: Contradictory Commands
User: "Create a daily reminder at 9 AM"
User: "Delete all reminders"
[Should handle conflict clearly]

Test D: Resource Limits
User: [Sends 10,000 character message]
[Should handle without crashing]

Test E: Empty/Null Requests
User: ""
User: "   "
User: null
[Should handle gracefully]
```

**Metrics**:
- Out-of-scope refusal rate (%)
- Malformed input handling success
- Graceful degradation score
- Crash rate (%)
- Error message quality

---

### 10. Channel-Specific Behavior

**Why Important**: Different channels have different norms

**Test Scenarios**:
```
Test A: Telegram Channel
[Send message via Telegram]
[Should: use appropriate formatting, respect message length limits]

Test B: HTTP Channel
[Send via HTTP API]
[Should: return proper JSON, handle stream parameter correctly]

Test C: Formatting Adaptation
[Same request via different channels]
[Should adapt: Telegram=brief/marked-up, HTTP=detailed/structured]
```

**Metrics**:
- Channel-appropriate formatting
- Platform convention compliance
- Cross-channel consistency
- Channel-specific optimization

---

## Priority Matrix

| Metric | Priority | Effort | Impact | Dependencies |
|--------|----------|--------|--------|--------------|
| **1. Memory & Learning** | 🔴 CRITICAL | Medium | VERY HIGH | None |
| **2. Context Retention** | 🔴 CRITICAL | Medium | HIGH | None |
| **3. Error Recovery** | 🟠 HIGH | Low | HIGH | None |
| **4. Complex Reasoning** | 🟠 HIGH | High | HIGH | None |
| **5. Tool Selection** | 🟠 HIGH | Medium | HIGH | None |
| **6. Code Quality** | 🟡 MEDIUM | Medium | MEDIUM | None |
| **7. Performance** | 🟡 MEDIUM | Low | MEDIUM | Monitoring setup |
| **8. Creativity** | 🟡 MEDIUM | High | MEDIUM | None |
| **9. Robustness** | 🟡 MEDIUM | Medium | MEDIUM | None |
| **10. Channel-Specific** | 🟢 LOW | Medium | LOW | None |

---

## Recommended Implementation Order

### Phase 1: Critical Gaps (Week 1)
1. **Memory & Learning** - Already identified as major gap (only Claude works)
2. **Context Retention** - Essential for multi-turn workflows
3. **Error Recovery** - Production readiness

### Phase 2: Core Capabilities (Week 2)
4. **Tool Selection** - Validate 100+ tool usage
5. **Complex Reasoning** - Multi-step workflow validation
6. **Code Quality** - SQL/Python generation validation

### Phase 3: Optimization (Week 3)
7. **Performance** - Benchmarking & optimization
8. **Robustness** - Edge case handling
9. **Creativity** - Proactive assistance

### Phase 4: Polish (Week 4)
10. **Channel-Specific** - Platform optimization

---

## Proposed Test Suite Structure

```
tests/model_evaluation/
├── 01_basic_onboarding.py          # Existing 3 tests
├── 02_memory_learning.py            # NEW: Memory creation, retrieval, application
├── 03_context_retention.py          # NEW: Multi-turn, long context
├── 04_error_recovery.py             # NEW: Ambiguity, failures, corrections
├── 05_complex_reasoning.py          # NEW: Multi-step workflows
├── 06_tool_selection.py             # NEW: Tool choice accuracy
├── 07_code_quality.py               # NEW: SQL/Python correctness
├── 08_performance.py                # NEW: Latency, efficiency
├── 09_creativity.py                 # NEW: Proactive suggestions
├── 10_robustness.py                 # NEW: Edge cases
├── 11_channels.py                   # NEW: Cross-channel tests
└── comprehensive_report.py          # Aggregate all results
```

---

## Scoring System

Each metric category (1-10) gets 0-10 points:

```python
Total Score = Σ(Metric_Score × Weight) × 10

Example:
Memory (10 pts) × 2.0 weight = 20
Context (10 pts) × 1.5 weight = 15
Reasoning (9 pts) × 1.0 weight = 9
Tools (8 pts) × 1.0 weight = 8
Code (9 pts) × 0.5 weight = 4.5
Performance (7 pts) × 0.5 weight = 3.5
Creativity (6 pts) × 0.5 weight = 3
Robustness (8 pts) × 0.5 weight = 4

Total = 67 / 100
```

---

## Next Steps

1. **Review & Approve Metrics** - User feedback on proposed metrics
2. **Create Test Scripts** - Implement test scenarios for each metric
3. **Run Comprehensive Tests** - Test all 8 models on all metrics
4. **Generate Report** - Compare models across all dimensions
5. **Production Decision** - Choose default model based on comprehensive data

---

## Questions for User

1. **Which metrics are most important** for your use case?
2. **Should we prioritize certain models** (free vs paid)?
3. **Are there specific scenarios** I missed that are critical for your workflow?
4. **Should we implement all metrics** or focus on top 3-5?
5. **Timeline**: How quickly do you need this evaluation?
