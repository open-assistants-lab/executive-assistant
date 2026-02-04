# Proposal: Align Four Pillars with LangChain Terminology

**Date**: 2026-02-04
**Proposal**: Use LangChain's established memory type terminology

---

## Current vs Proposed Terminology

### Current (Our Custom Terms)

| Pillar | Our Term | Type |
|--------|----------|------|
| Memory | "Who you are" | Declarative |
| Journal | "What you did" | Episodic |
| Instincts | "How you behave" | Procedural |
| Goals | "Why/Where" | Future intentions |

---

### Proposed (LangChain Aligned) ✅

| Pillar | New Term | Type | LangChain Reference |
|--------|----------|------|-------------------|
| **Memory** | **"Who you are"** | **Semantic** | Semantic Memory |
| Journal | "What you did" | Episodic | Episodic Memory |
| Instincts | "How you behave" | Procedural | Procedural Memory |
| Goals | "Why/Where" | Intentions | - |

---

## Why This Alignment Makes Sense

### 1. Industry Standard 🏆

**LangChain** is the leading framework for building LLM applications. Their memory system documentation defines three types:

> - **Semantic Memory**: "Who you are"
> - **Episodic Memory**: "What you did"
> - **Procedural Memory**: "How you behave"

**Source**: [LangChain Memory Documentation](https://docs.langchain.com/oss/python/concepts/memory#semantic-memory)

**Impact**:
- ✅ Developers familiar with LangChain will immediately understand
- ✅ Consistent with ecosystem we might use/integrate with
- ✅ Proven concepts validated by production use
- ✅ Better onboarding for new developers

---

### 2. Better Terminology

**"Semantic" vs "Declarative"**:

| Aspect | Declarative | Semantic |
|--------|-------------|----------|
| Meaning | Grammar term (declarative sentences) | Meaning-based term (semantic knowledge) |
| Clarity | Technical linguistic concept | More intuitive for developers |
| Industry | Linguistics, AI | AI/LLM domain |
| Familiarity | Academic | Practical |

**Winner**: **Semantic** ✅

---

### 3. Four Pillars with LangChain Terminology

```
┌─────────────────────────────────────────────────┐
│                                                  │
│  All Pillars: LangChain-Aligned Terminology      │
│                                                  │
│  Semantic:  "Who you are" (Facts, identity)      │
│  Episodic:  "What you did" (Events, experiences)   │
│  Procedural: "How you behave" (Patterns, skills)    │
│  Intentions: "Why/Where" (Goals, plans)            │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Complete Four-Pillar Definitions (Updated)

### 1. Semantic Memory: "Who You Are"

**What it stores**:
- User identity (name, role, company)
- Preferences (communication style, format preferences)
- Facts about the user (location, timezone, team)
- Constraints and requirements
- Context information

**Examples**:
```
- Name: Alice
- Role: Product Manager at Acme Corp
- Location: San Francisco, PST
- Prefers: Brief responses, bullet points
- Team: Sales Analytics
```

**Access**: Instant lookup (key-value queries)

---

### 2. Episodic Memory: "What You Did"

**What it stores**:
- Time-based activities and events
- Chronological record of actions
- Experiences and accomplishments
- Activity history with automatic rollups

**Examples**:
```
[Feb 4 10:00] Created work_log table
[Feb 4 14:30] Added customer data schema
[Daily] Built work log tracking system
[Weekly] Focused on sales analytics infrastructure
```

**Access**: Time-range + semantic search

---

### 3. Procedural Memory: "How You Behave"

**What it stores**:
- Learned behavioral patterns
- Automatic responses
- Skill-based knowledge
- Trigger-action pairs with confidence scores

**Examples**:
```
• When user asks for reports → Use bullet points
• Morning requests → User is productive, be detailed
• "Make it brief" → User is busy, keep it concise
• Works on sales → Suggest visualizations first
```

**Access**: Automatic pattern matching

---

### 4. Intentions: "Why/Where" (New Pillar)

**What it stores**:
- Goals and objectives
- Plans and roadmaps
- Future intentions
- Target dates and milestones
- Progress tracking

**Examples**:
```
- Launch sales dashboard by EOM
- Complete API integration next sprint
- Learn Python basics this quarter
- Automate weekly reporting by Q2
```

**Access**: Goal queries, progress tracking

---

## Benefits of Alignment

### 1. Developer Familiarity ✅

**Before** (custom terms):
- "Declarative knowledge"
- New devs need to learn custom terminology

**After** (LangChain terms):
- "Semantic memory" - immediately understood
- Leverages existing LangChain knowledge
- Easier onboarding

### 2. Better Documentation ✅

When explaining the system:
- "We use semantic memory (like LangChain)"
- "Episodic memory tracks your activities"
- "Procedural memory learns your patterns"

**Versus**:
- "We use declarative knowledge" (requires explanation)
- "Memory stores who you are" (custom concept)

### 3. Ecosystem Compatibility ✅

**If integrating with LangChain**:
- Same terminology = less confusion
- Easier to map concepts
- Shared documentation understanding

### 4. Proven Concepts ✅

LangChain has:
- Validated these concepts in production
- Refined terminology through real-world use
- Established best practices
- Community knowledge base

---

## Migration Impact (if renaming "memory" → "semantic")

### Files to Update

**Storage**:
- `mem_storage.py` → `semantic_storage.py`
- `mem.db` → `semantic.db` (or keep as profile.db for clarity)

**Functions**:
- `get_mem_storage()` → `get_semantic_storage()`
- `_get_relevant_memories()` → `_get_relevant_semantic()`

**Variable Names**:
- `memory` → `semantic`
- `memories` → `semantic_facts`

**Tests**:
- All test files and test names
- 24 test files across memory tests

**Documentation**:
- All markdown files mentioning "declarative"
- All references to memory types
- Comments in code

**Config**:
- `memory:` section in config.yaml

---

## Terminology Comparison

| Aspect | Custom (Old) | LangChain (New) | Winner |
|--------|--------------|-----------------|--------|
| Industry Standard | Custom | LangChain | **LangChain** |
| Developer Familiarity | Low | High | **LangChain** |
| Documentation | Ours | LangChain + Ours | **LangChain** |
| Ecosystem | Standalone | Integrated | **LangChain** |
| Precision | Declarative | Semantic | **LangChain** |
| Clarity | Medium | High | **LangChain** |

---

## Recommendation

### ✅ **Align with LangChain Terminology**

**Change**:
- Replace "Declarative knowledge" → "Semantic knowledge"
- Keep pillar names: Memory, Journal, Instincts, Goals
- Update descriptions to reference LangChain types

**Rationale**:
1. **Industry Standard**: LangChain is the leading framework
2. **Better Terminology**: "Semantic" is more intuitive than "declarative"
3. **Developer Familiarity**: Leverages existing LangChain knowledge
4. **Future Integration**: Easier if integrating with LangChain
5. **Proven**: Validated by production use

---

## Updated Four-Pillar Descriptions

### For Developers

```
Semantic Memory (Memory): "Who you are"
- User identity and facts
- Preferences and context
- Instant lookup for personalization

Episodic Memory (Journal): "What you did"
- Time-based activities
- Event history with rollups
- Semantic + keyword search

Procedural Memory (Instincts): "How you behave"
- Learned behavioral patterns
- Automatic pattern matching
- Confidence-based adaptation

Intentions (Goals): "Why/Where"
- Future objectives and plans
- Progress tracking
- Change detection
```

### For Documentation

```
Our unified context system consists of four complementary pillars:

1. Semantic Memory (like LangChain's Semantic Memory):
   Stores facts about who the user is - their identity, preferences,
   and contextual information.

2. Episodic Memory (like LangChain's Episodic Memory):
   Tracks what the user has done - a time-based record of activities
   and experiences with automatic hierarchical rollups.

3. Procedural Memory (like LangChain's Procedural Memory):
   Encodes how the user behaves - learned patterns and automatic responses
   based on observed interactions.

4. Intentions (Goals):
   Captures why the user is working - future intentions, goals, and plans
   with automatic progress tracking and change detection.
```

---

## Decision

**Proposal**: Use LangChain's established terminology

**Action Items**:
1. ✅ Keep pillar names: Memory, Journal, Instincts, Goals
2. ✅ Update descriptions to reference LangChain types
3. ⏳ Rename "memory" → "semantic" for storage layer (optional, separate task)

**Benefits**:
- Industry standard terminology
- Better developer onboarding
- Leverages LangChain's knowledge base
- More intuitive descriptions

**Status**: Ready for implementation with updated terminology

---

## Commit Message Suggestion

```
docs: align four pillars with LangChain terminology

Updated terminology to match LangChain's memory types:
- Memory: "Who you are" → Semantic Memory (not Declarative)
- Journal: "What you did" → Episodic Memory (same)
- Instincts: "How you behave" → Procedural Memory (same)
- Goals: "Why/Where" → Intentions (same)

Benefits:
- Industry standard (LangChain)
- Better terminology ("semantic" > "declarative")
- Developer familiarity
- Ecosystem alignment

Reference: https://docs.langchain.com/oss/python/concepts/memory

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Ready for Feedback

**Question**: Should I proceed with this terminology update?

1. ✅ Yes, update all descriptions to reference LangChain types
2. ⏳ Wait until after Week 4 (complete system first)
3. 📝 Make "memory" → "semantic" rename as well
4. ❌ Keep current terminology, just add LangChain references

Recommendation: ✅ **Yes, update now** - small change, big clarity win
