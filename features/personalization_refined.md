# Personalization Strategy: Organic Learning Through Existing Systems

**Date:** 2025-02-02
**Status:** Refined Strategy
**Related:** [ux_improvements_plan.md](./ux_improvements_plan.md), [onboarding_plan.md](./onboarding_plan.md)

---

## Core Philosophy

**Executive Assistant learns about users organically through existing systems - NOT through rigid metrics or scores.**

Instead of tracking "AI literacy: 7/10" or "prompt quality: 3/5", the system learns:
- **Behavioral patterns**: What user does repeatedly
- **Preferences**: What user says they like/dislike
- **Corrections**: When user corrects the agent
- **Communication style**: How user expresses themselves
- **Expertise areas**: What user knows about

This creates a **rich, nuanced understanding** of each user without artificial categories.

---

## What Already Works ✅

### 1. **Memory System** (Organic Learning)

**Types Stored:**
- `profile` - User's role, expertise, background
- `preference` - What user likes/dislikes
- `style` - Communication patterns
- `fact` - Objective information
- `constraint` - Limitations
- `context` - Current situation

**How It Learns:**
- Auto-extraction from conversations (when enabled)
- User can explicitly create memories
- Temporal versioning tracks changes over time
- Full-text search finds relevant memories

**Example:**
```
User: "I'm a senior Python developer working on AI systems"
→ Memory created (type: profile)

User: "Can you show me the code?"
→ Agent provides code

User: "Actually, can you explain what this does instead?"
→ Memory updated: "Prefers explanations over code"
```

### 2. **Instincts System** (Pattern Detection)

**Automatic Learning:**
```python
# Observer detects patterns automatically:
- Corrections: "no, i meant", "actually, wait"
- Repetitions: "like you did before", "same as last time"
- Preferences: "be brief", "more detail", "use JSON"
- Format choices: "bullet points", "table format"
```

**Stored as Instincts:**
```python
{
  "trigger": "user corrects previous response",
  "action": "acknowledge and adjust immediately",
  "domain": "communication",
  "confidence": 0.85,
  "source": "correction-detected"
}
```

**Applied to Responses:**
```
## Behavioral Patterns
Apply these learned preferences:

### Communication
- **Acknowledge corrections immediately** (always apply)
- **Skip explanations, go straight to code** (confidence: 0.8)
- **Be concise** (when: technical topics)

### Format
- **Use code blocks** (always)
- **Add comments only when requested**
```

### 3. **Memory Injection** (Context Awareness)

Every message includes up to 5 relevant memories:
```
[User Memory]
- User is senior engineer (expert)
- Prefers concise responses
- Working on Project Alpha
- Likes JSON format
- Has PostgreSQL access

[User Message]
Create a database table
```

---

## What We Should Add

### Priority 1: Enable Auto-Extraction ✅ (FIXED)

**Change:** Default from `False` to `True`

**Impact:** Agent automatically learns about users without manual memory creation.

---

### Priority 2: User Onboarding 🆕

**Goal:** Help users introduce themselves and learn effective prompting

**Implementation:**

```python
# First-time user detection
def is_first_time_user(thread_id: str) -> bool:
    """Check if user is new (few/no memories or instincts)."""
    memories = get_mem_storage().list_memories(thread_id)
    instincts = get_instinct_storage().list_instincts(thread_id)

    return len(memories) + len(instincts) < 5


async def show_onboarding_message(user_message: str, thread_id: str) -> str:
    """Provide onboarding for first-time users."""

    if not is_first_time_user(thread_id):
        return None  # Already onboarded

    return """
Welcome! I'm your personal AI assistant. Let me help you get started.

## Step 1: Introduce Yourself 🎯

Tell me a bit about yourself so I can help you better:
- What's your role? (developer, manager, analyst, etc.)
- What do you work on? (projects, tasks, goals)
- Any preferences? (brief vs detailed, formal vs casual)

Example:
"I'm a senior dev working on Project Alpha. I prefer brief responses
and skip basic explanations - I know my stuff."

## Step 2: How to Talk to Me 💬

I work best with clear, specific requests:

✅ Good:
"Create a timesheet table with columns: date, project, hours, description"

❌ Vague:
"make me a table for data"

✅ Specific:
"Remind me to review PRs every weekday at 3pm"

❌ Unclear:
"remind me about stuff"

## Step 3: I Learn From You 🧠

The more we interact, the better I'll understand:
- Your preferences (I'll remember them)
- Your communication style
- Your expertise areas
- How you like to work

So don't worry about being "perfect" - just be yourself!

Ready to start? What would you like help with?
"""
```

**Storage:**
```python
# Track onboarding completion
create_memory(
    content="User completed onboarding",
    memory_type="context",
    key="onboarding_complete",
    confidence=1.0
)
```

---

### Priority 3: Enhanced Vague Request Handling 🆕

**Current:** Struggles with "help", "i need thing"

**Improved:** Uses memories to provide personalized help

```python
def handle_vague_request_with_context(user_message: str, thread_id: str) -> str:
    """Handle vague requests using what we know about the user."""

    # Check what we know about this user
    memories = get_relevant_memories(thread_id, "profile preference style", limit=10)

    # Build personalized help
    role = get_from_memories(memories, "role", "user")
    expertise = get_from_memories(memories, "expertise", "general")
    recent_work = get_from_memories(memories, "recent", "projects")

    if role and expertise:
        return f"""
I'd love to help, {role}!

Based on your work on {recent_work}, I can help with:
📊 Data analysis: "Analyze my timesheet data"
🔍 Web research: "Find recent articles about {expertise}"
📝 Documentation: "Generate docs for my code"
💼 Automation: "Create scripts for repetitive tasks"

What would you like to do?
"""
    else:
        # Generic help with examples
        return """
I'd love to help! Could you be more specific?

Here are some things I can do:
📊 Track work: "Log 4 hours to Project Alpha"
🔍 Search web: "Find recent LangChain updates"
⏰ Reminders: "Remind me to review PRs at 3pm"
📈 Analyze: "Show my productivity this week"

What would you like help with?
"""
```

---

## What We DON'T Need (Removed from Previous Plan)

### ❌ **"AI Literacy Score"** - Too Rigid

**Bad Approach:**
```python
# DON'T DO THIS
ai_literacy = calculate_literacy_score(user_messages)
# → 7.2/10 (arbitrary number)
# → "Beginner" category (artificial box)
```

**Why It's Bad:**
- Reduces rich behavior to a single number
- Puts users in boxes (beginner/intermediate/expert)
- Can change day-to-day
- Doesn't capture nuance

### ❌ **"Prompt Quality Metric"** - Too Mechanical

**Bad Approach:**
```python
# DON'T DO THIS
quality_score = measure_prompt_quality(user_message)
# → 0.65/1.0 (arbitrary)
# → Track over time: 0.65 → 0.68 → 0.71
```

**Why It's Bad:**
- Quality is context-dependent
- What's "bad" for one task might be perfect for another
- User might improve in areas not measured
- Doesn't capture WHY something works or doesn't

### ❌ **Explicit Skill Level Tracking** - Not Organic

**Bad Approach:**
```python
# DON'T DO THIS
user_skill_level = "intermediate"  # Stored as fixed attribute
adjust_response_complexity(user_skill_level)
```

**Why It's Bad:**
- User might be expert in Python but beginner in data analysis
- Static label doesn't adapt to context
- Doesn't capture growth
- Unnecessary categorization

---

## What ACTUALLY Works: Organic Learning

### Example 1: Learning Communication Style ✅

**Without Explicit Tracking:**

**Conversation 1:**
```
User: "Create a users table"
Agent: [Provides detailed explanation of schema]

User: "Actually, skip the explanation. Just the code."
Agent: [Creates instinct: "user prefers direct code, no explanations"]
```

**Conversation 2 (later):**
```
User: "Create an orders table"
Agent: [Injects instinct from learning]
```

**System Prompt Includes:**
```
### Communication
- **Provide code directly, skip explanations** (confidence: 0.8)
- Don't explain basic SQL concepts
```

**Result:** Agent adapted WITHOUT a "skill level" label!

### Example 2: Learning Expertise Areas ✅

**Organic Memory Creation:**

```
User: "I need to deploy this FastAPI app"
Agent: [Helps with deployment]

User: "Actually, I know FastAPI well. Just help with the Docker part."
→ Memory created: "User is expert at FastAPI, needs Docker help"

User (later): "Set up a new API endpoint"
Agent: [Checks memories, sees FastAPI expertise]
→ "I'll create a FastAPI endpoint. What should it do?"
```

**Result:** Agent learned expertise area naturally, no "skill level" needed!

### Example 3: Detecting Frustration ✅

**Emotional State Detection:**

```
User: "whatever, nevermind"
→ Detect frustration pattern
→ Store as context memory

Agent: [Adjusts response]
"I sense you're frustrated. Let me try a different approach.
What would be most helpful?"
```

**Result:** Emotional intelligence without "frustration score"!

---

## Enhanced Observer: What to Add

### Add to `instincts/observer.py`:

```python
class InstinctObserver:
    """Observer for detecting behavioral patterns."""

    # EXISTING PATTERNS (already implemented):
    PATTERNS = {
        "correction": {...},
        "repetition": {...},
        "preference_verbosity": {...},
        "preference_format": {...},
    }

    # NEW PATTERNS TO ADD:
    FRUSTRATION_PATTERNS = {
        "triggers": [
            r"\bnevermind\b",
            r"\bforget it\b",
            r"\bwhatever\b",
            r"^(ok|okay|fine)[!.]*$",
            r"\?+$",
            r"(.*)\1{2,}",  # Stuttering
        ],
        "default_instinct": {
            "trigger": "user shows frustration",
            "action": "be extra helpful, offer alternatives, break down tasks",
            "domain": "communication",
        },
    }

    EXPLICIT_INTRODUCTION_PATTERNS = {
        "triggers": [
            r"i'm a .+ (developer|engineer|analyst|manager)",
            r"i work (on|for|at)",
            r"my (role|job|position) is",
            r"i'm (senior|junior|lead)",
        ],
        "default_instinct": {
            "trigger": "user introduces themselves",
            "action": "extract role, expertise, work context into memories",
            "domain": "workflow",
        },
    }

    def observe_message(self, user_message: str, ...):
        # EXISTING: Check for corrections, repetitions, preferences
        detected.extend(self._check_corrections(user_message))
        detected.extend(self._check_repetitions(user_message))
        detected.extend(self._check_preferences(user_message))

        # NEW: Check for frustration
        detected.extend(self._check_frustration(user_message))

        # NEW: Check for self-introduction
        detected.extend(self._check_introductions(user_message))

        return detected
```

---

## Complete Personalization Flow

```
┌─────────────────────────────────────────────┐
│ 1. User sends message                          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 2. Observer detects patterns                   │
│  ✓ Corrections ("no, I meant...")           │
│  ✓ Repetitions ("like before")               │
│  ✓ Preferences ("be brief")                   │
│  ✓ Frustration ("nevermind") ← NEW           │
│  ✓ Self-introductions ("I'm a dev...") ← NEW│
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 3. System builds personalization context     │
│  ✓ Memories (profile, preference, style)      │
│  ✓ Instincts (behavioral patterns)           │
│  ✓ Context (current work, frustration state)   │
│  ✓ Expertise areas (learned organically)      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 4. Inject into system prompt                 │
│  "User is senior engineer (expert)"           │
│  "Prefers concise responses"                  │
│  "Working on Project Alpha"                  │
│  "Seems frustrated - be extra helpful"        │
│  "Skip basic explanations"                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 5. LLM generates personalized response      │
│  Adapted to user's style, expertise, state    │
└─────────────────────────────────────────────┘
```

---

## Example: New User Journey

### First Interaction (Onboarding)

```
User: "hi"
Agent: """
Welcome! I'm your personal AI assistant.

Let me help you get started:

## Step 1: Introduce Yourself 🎯
Tell me about yourself:
- Your role and expertise
- What you're working on
- Your preferences

Example: "I'm a senior dev working on AI systems.
I prefer brief responses and skip explanations."

## Step 2: How to Talk to Me 💬
Be specific: "Create a table with columns: date, task, hours"
Not vague: "make me a table"

## Step 3: I Learn As We Go 🧠
I'll remember your preferences and adapt.

Ready? What would you like help with?
"""

User: "I'm a senior data scientist working on ML models.
I prefer concise responses and hate basic explanations."

→ Memories created:
- profile: "Senior data scientist, ML expert"
- preference: "Concise responses"
- constraint: "Dislikes basic explanations"

→ Instincts created:
- communication: "be brief, skip basics"
- workflow: "assume technical knowledge"
```

### Second Interaction (Personalized)

```
User: "Create a linear regression model"
Agent: [Checks memories, sees ML expertise]
[Checks instincts, sees "be brief" rule]

"```python
from sklearn.linear_model import LinearRegression
model = LinearRegression()
```

Done. Want me explain the parameters or just use it?
"""
```

### Third Interaction (Learning from Correction)

```
User: "Actually, can you show me how to use it?"
Agent: "Sure! Here's how to use LinearRegression:..."

[Observer detects: user asked for explanation]
→ Instinct updated: "ML expert but wants explanations sometimes"
→ Confidence: 0.6 (still prefers brevity but flexible)
```

### Fourth Interaction (Frustration Detected)

```
User: "whatever, nevermind"
Agent: "I sense you're frustrated. What would be most helpful?
- Break this down into smaller steps?
- Try a different approach?
- Focus on something else?"
```

---

## Success Metrics (Organic Learning)

Instead of measuring "prompt quality", track:

✅ **Conversation Continuation Rate**: Do users keep chatting?
✅ **Correction Frequency**: Decreases over time as agent learns?
✅ **Task Success Rate**: Improves as personalization increases?
✅ **User Satisfaction**: Implicit signals (longer conversations, positive feedback)

❌ **DON'T Measure:**
- Arbitrary "literacy scores"
- "Prompt quality" metrics
- "Skill levels" as static labels

---

## Implementation Plan

**📘 Complete Roadmap**: See [instincts_system_roadmap.md](./instincts_system_roadmap.md) for comprehensive instincts system evolution (4 phases, ~13 days).

### Phase 1: Enable Auto-Extraction ✅
- Change default from `False` to `True` (DONE)
- Test auto-extraction works

### Phase 2: Add Onboarding Flow 🆕
- Detect first-time users
- Show introduction message
- Guide them through self-introduction
- Teach effective prompting with examples
- Mark onboarding complete

### Phase 3: Enhanced Vague Request Handling 🆕
- Use existing memories to personalize help
- Show examples based on user's role/expertise
- Reference user's actual work/projects
- Suggest relevant next steps

### Phase 4: Add Frustration Detection 🆕
- Detect frustration patterns
- Adjust response style
- Offer alternatives
- De-escalate situations

### Phase 5: Enhanced Observer 🆕
- Add frustration pattern detection
- Add self-introduction detection
- Extract context from introductions
- Create relevant memories/instincts

### Phase 6+: Instincts System Evolution 🚀
See [instincts_system_roadmap.md](./instincts_system_roadmap.md) for:
- **Quick Wins** (1 day): Missing sources, conflict resolution, metadata utilization
- **Important Enhancements** (3 days): Temporal decay, staleness detection, success tracking
- **Architecture Expansion** (4 days): New domains, emotional tracking, expertise mapping
- **Advanced Intelligence** (5 days): Cross-pattern recognition, confidence calibration

---

## Key Principles

### ✅ DO:

1. **Learn organically** through existing systems
2. **Detect patterns** in natural conversation
3. **Adapt responses** based on learned behaviors
4. **Store nuanced memories** (not scores)
5. **Track emotional state** (frustration)
6. **Guide new users** with onboarding
7. **Use examples** from user's actual context

### ❌ DON'T:

1. **Create artificial metrics** (literacy scores, quality ratings)
2. **Categorize users** (beginner/intermediate/expert)
3. **Track "prompt quality"** as a metric
4. **Reduce rich behavior** to numbers
5. **Create static profiles** that don't adapt
6. **Make assumptions** based on limited data

---

## Conclusion

**Executive Assistant learns about users through:**
1. **Memories** - What they tell us (facts, preferences, style)
2. **Instincts** - Patterns we detect (corrections, repetitions)
3. **Observations** - Emotional state, context

**NOT through:**
- ❌ Numerical scores
- ❌ Skill level labels
- ❌ Quality metrics

This creates a **rich, adaptive system** that gets to know each user naturally over time, just like a human assistant would!

**The key insight:** Don't measure and categorize - **learn and adapt**! 🎯
