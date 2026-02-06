# Conversation → Skill Feature - Complete User Guide

## Overview

The Ken Executive Assistant can **learn from your conversations** and convert behavioral patterns into reusable skills. This is the **Conversation → Skill** feature.

---

## How It Works

### Step 1: Build Patterns Through Conversations

Over several conversations, the agent learns your preferences:

```
Conversation 1:
User: "Summarize the Q3 sales data"
Agent: [Provides detailed summary]
Agent: [Learns: User might want summaries]

Conversation 2:
User: "What's the executive summary of Q3?"
Agent: [Provides detailed summary]
Agent: [Learns: User prefers summaries over details]

Conversation 3:
User: "Give me the key highlights only"
Agent: [Provides concise summary]
Agent: [Instinct created: "User prefers concise summaries"]
```

---

### Step 2: Evolve Instincts into Skills

Once you have 2+ related instincts, ask the agent to evolve them:

```
User: "evolve_instincts()"
```

The agent will:
1. Analyze all learned patterns from your conversations
2. Cluster related instincts by domain (communication, workflow, etc.)
3. Generate draft skills with high confidence (60%+)
4. Present draft skill IDs for your approval

**Example Output:**
```
Generated 2 draft skills:

1. [communication_concise_123]
   Domain: Communication
   Confidence: 85%
   Description: Response Style Guide: Concise

2. [workflow_analytics_456]
   Domain: Workflow
   Confidence: 72%
   Description: Tool Selection: Analytics-focused
```

---

### Step 3: Approve and Save

Approve the draft skill to save it permanently:

```
User: "approve_evolved_skill('communication_concise_123')"
```

The agent will:
- Save it as a user skill in your conversation
- Apply it automatically in future conversations
- All future responses will follow this pattern

---

## Complete Example Workflow

### Session 1-3: Build Pattern
```
# Multiple conversations where you ask for concise outputs
"Summarize this report"
"What's the executive summary?"
"Give me the highlights only"
```

### Session 4: Check Learned Patterns
```
User: "list_instincts()"
Agent: "Found 3 learned patterns:
       - Prefers concise summaries (confidence: 0.85)
       - Uses DuckDB for analytics (confidence: 0.72)
       - Asks follow-up questions (confidence: 0.68)"
```

### Session 5: Evolve into Skills
```
User: "evolve_instincts()"
Agent: "Generated 2 draft skills from your conversation patterns:

       ✅ communication_concise_123
          - Response Style Guide: Concise
          - Confidence: 85%

       ✅ analytics_workflow_456
          - Tool Selection: Analytics-focused
          - Confidence: 72%

       To approve: approve_evolved_skill('draft_id')"
```

### Session 6: Approve & Use
```
User: "approve_evolved_skill('communication_concise_123')"
Agent: "✅ Skill 'Response Style Guide: Concise' saved!"

User: "What's in this report?"
Agent: [Now automatically gives concise summary]
```

---

## Domains Tracked

The system clusters patterns into these domains:

| Domain | What It Tracks | Example Skill Name |
|--------|---------------|------------------|
| **Communication** | Response style, verbosity | Response Style Guide |
| **Format** | Output format preferences | Output Format Guide |
| **Workflow** | Preferred tool sequences | Workflow Patterns |
| **Tool Selection** | Frequently used tools | Tool Selection Guide |
| **Verification** | Quality standards | Quality Verification |
| **Timing** | When to do things | Timing & Scheduling |

---

## Available Commands

### 1. **View Learned Patterns**
```
list_instincts()
```
Shows all patterns learned from your conversations with confidence scores.

---

### 2. **Evolve Patterns into Skills**
```
evolve_instincts()
```
Analyzes your conversations and generates draft skills from patterns.
- Requires 2+ related instincts
- Only generates skills with 60%+ confidence
- Creates draft skills with detailed behavioral patterns

---

### 3. **Approve and Save Skills**
```
approve_evolved_skill('draft_id')
```
Approves a draft skill and saves it as a permanent user skill.
- Available in all future conversations
- Automatically applied by the agent
- Stored in: `data/users/{thread_id}/skills/on_demand/`

---

### 4. **Export Patterns**
```
export_instincts()
```
Exports all learned patterns as JSON for backup or analysis.

---

## Tips for Best Results

### ✅ Do:
- **Be consistent** - Use the same patterns 3+ times for better learning
- **Give feedback** - Correct the agent when it doesn't follow your preference
- **Wait before evolving** - Have 10+ conversations before evolving
- **Review drafts** - Check the generated skill content before approving
- **Use descriptive names** - Name skills meaningfully when creating manually

### ❌ Don't:
- **Evolve too early** - Need sufficient conversation history (20+ messages)
- **Approve blindly** - Review the skill content first
- **Create too many** - Focus on your strongest patterns
- **Ignore confidence scores** - Only approve high-confidence skills (70%+)

---

## Technical Details

### Confidence Threshold
- **Instinct Creation:** Auto-created when patterns repeat
- **Skill Generation:** Requires 60%+ average confidence
- **Clustering:** Groups instincts by semantic similarity

### Skill Storage
- **Location:** `data/users/{thread_id}/skills/on_demand/{skill_name}.md`
- **Format:** Markdown with behavioral patterns, guidelines, examples
- **Loading:** Automatic via `load_skill()` or natural language

### Priority
- **User skills** take precedence over system skills
- **Evolved skills** are user skills
- **Higher confidence** = better skill quality

---

## Troubleshooting

**Q: evolve_instincts() returns no drafts?**
A: You need at least 2 related instincts with 60%+ confidence. Have more conversations first.

**Q: approve_evolved_skill() fails?**
A: Check the draft_id exactly. It must match the ID from evolve_instincts() output.

**Q: Skill not being applied?**
A: Skills are context-aware. Try using explicit trigger phrases the skill expects.

---

## Quick Reference

```bash
# Check learned patterns
list_instincts()

# Generate draft skills from conversations
evolve_instincts()

# Approve a specific skill
approve_evolved_skill('draft_id')

# Export all patterns for backup
export_instincts()
```

---

**Status:** ✅ Fully implemented and working!

**Key Files:**
- `/Users/eddy/Developer/Langgraph/ken/src/executive_assistant/instincts/evolver.py`
- `/Users/eddy/Developer/Langgraph/ken/src/executive_assistant/tools/instinct_tools.py`

**Tools Available:**
- `evolve_instincts()` - Generate draft skills
- `approve_evolved_skill(draft_id)` - Approve & save
- `list_instincts()` - View patterns
- `export_instincts()` - Export backup
