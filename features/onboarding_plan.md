# Onboarding Plan

**Two Types of Onboarding:**

## 1. Setup Onboarding (System Installation)
*Getting Executive Assistant running for the first time.*

## 2. User Onboarding (Teaching Users)
*Helping users learn how to interact effectively with the agent.*

---

## Part 1: Setup Onboarding

### Goal
Provide a guided, low-friction onboarding flow that sets up channels, models, storage, and safety defaults, and validates the install with a diagnostic check.

### Core Principles
- **Wizard-first**: one command to get a working assistant.
- **Safe by default**: allowlist + pairing on channels.
- **Validate early**: run diagnostics before the first real use.

### UX Flow
1) **Welcome + prerequisites**
   - Check Python env + required services
   - Verify API keys present (LLM + optional tools)

2) **Model selection**
   - Choose provider (OpenAI/Anthropic/etc.)
   - Set default + fast models

3) **Channel setup**
   - Telegram (token + allowlist)
   - Optional HTTP channel
   - Optional future channels (Slack/Discord)

4) **Storage setup**
   - Confirm data directories
   - Initialize DBs (TDB/VDB/memory)

5) **Safety defaults**
   - Enable allowlist
   - Pairing / DM-only policy for new contacts

6) **Test run**
   - Send a message to verify end-to-end
   - Run `doctor` checks

### CLI Commands
- `exec_assistant onboard` — guided setup
- `exec_assistant doctor` — diagnostics + repair hints
- `exec_assistant status` — show configured channels/models/tools

### Implementation Steps
1) Add a CLI wizard (prompt users for config + write to `.env` / config file)
2) Add a `doctor` command (validate env, DBs, channel connectivity)
3) Add a simple sample workflow test
4) Add docs + quickstart
5) Auto-trigger setup onboarding when no memory exists (e.g., after `/reset mem`)

### Success Criteria
- New user can go from empty repo → working assistant in <10 minutes
- Issues are detected early with actionable errors
- Safer defaults for messaging channels
- Missing memory triggers setup onboarding to re-establish preferences

---

## Part 2: User Onboarding

### Goal
Help users introduce themselves and learn how to interact effectively with Executive Assistant, making onboarding feel natural and conversational.

### Core Principles
- **Conversation-first**: Learn through chat, not forms
- **Organic learning**: Extract info naturally from interaction
- **Guided discovery**: Teach through examples, not documentation
- **Personalized**: Adapt onboarding to user's apparent expertise level

### When to Trigger User Onboarding

**Automatic Detection:**
```python
def should_show_user_onboarding(thread_id: str) -> bool:
    """Check if user onboarding is needed."""
    memories = get_mem_storage().list_memories(thread_id)
    instincts = get_instinct_storage().list_instincts(thread_id)

    # Trigger if very little is known about user
    return len(memories) + len(instincts) < 5
```

**Triggers:**
- First interaction with new thread
- User says "help" or "hi"
- Very vague request that suggests unfamiliarity

### Onboarding Conversation Flow

#### Step 1: Welcome & Introduction 🎯

**Agent Message:**
```
Welcome! I'm your personal AI assistant. I'm here to help with tasks,
questions, and organizing information.

Let me help you get started!
```

**If user seems unfamiliar (vague requests):**
```
Before we dive in, let me quickly help you get the most out of our interactions.
This will take just 30 seconds. Ready?
```

#### Step 2: Get to Know You 💬

**Agent Message:**
```
First, tell me a bit about yourself so I can help you better:

🎯 Your Role:
   What do you do? (developer, manager, analyst, student, etc.)
   What do you work on? (projects, domains, goals)

⚙️ Your Preferences:
   How do you like to communicate?
   - Brief and direct, or detailed explanations?
   - Formal or casual?
   - Technical or simple language?

🔧 Your Expertise:
   What are your strengths? (coding, writing, analysis, etc.)
   What areas need more explanation?

Example:
"I'm a senior data scientist working on ML models.
I prefer brief responses with code examples. Skip basic explanations,
but do explain ML concepts when relevant."
```

**Store What We Learn:**
```python
# Auto-extracted from user's response:
create_memory(
    content="User is senior data scientist",
    memory_type="profile",
    key="role",
    confidence=0.9
)

create_memory(
    content="Prefers brief responses with code examples",
    memory_type="preference",
    key="communication_style",
    confidence=0.9
)

create_memory(
    content="Expert: ML, coding, data analysis",
    memory_type="profile",
    key="expertise",
    confidence=0.9
)
```

#### Step 3: How to Talk to Me 📝

**Agent Message (Personalized to User):**

**For Beginner Users:**
```
Great! Here's how to get the best results:

✅ **Be Specific:**
   "Create a table named timesheets" → Better than "make a table"
   "Search for Python asyncio tutorials" → Better than "search for python"

✅ **Provide Context:**
   "I need to track my daily tasks as a data scientist"
   → Better than "I need to track stuff"

✅ **Be Clear:**
   "Remind me every weekday at 9am to review yesterday's commits"
   → Better than "remind me about commits"

Don't worry about being perfect! I'll learn your style as we go.
```

**For Expert Users:**
```
Got it! I can see you're experienced. I'll:
- Be direct and concise
- Skip basic explanations unless relevant
- Use technical terminology
- Assume knowledge of best practices

Feel free to give me brief instructions - I'll understand!
```

#### Step 4: What I Can Do 🛠️

**Show Relevant Capabilities (based on user's role/expertise):**

**For Data Scientist:**
```
Here's what I can help you with:

📊 **Data Work:**
   - Create and query databases (SQL, DuckDB, etc.)
   - Analyze data with Python
   - Export results (CSV, JSON, plots)

🔍 **Research:**
   - Web search for papers, tutorials
   - Save findings to knowledge base
   - Generate summaries

⏰ **Organization:**
   - Track experiments, runs, results
   - Set reminders for reviews, deadlines
   - Manage project notes

📝 **Documentation:**
   - Generate code docs
   - Create README files
   - Write API documentation

What would you like to work on first?
```

#### Step 5: I Learn As We Go 🧠

**Agent Message:**
```
One last thing: I get smarter with every conversation.

I'll learn:
- ✅ Your preferences (how you like things done)
- � Your expertise areas (what you know)
- � Your communication style (brief vs detailed)
- ✅ Patterns in your work (projects, tools, workflows)

So don't worry about explaining your preferences every time -
once I learn it, I'll remember!

Ready to start? What would you like help with?
```

### Complete Example: Expert User Onboarding

```
User: "hi"

Agent: """
Welcome! I'm your personal AI assistant.

Let me help you get started!

First, tell me a bit about yourself so I can help you better:

🎯 Your Role:
   What do you do? (developer, manager, analyst, student, etc.)
   What do you work on? (projects, domains, goals)

⚙️ Your Preferences:
   How do you like to communicate?
   - Brief and direct, or detailed explanations?
   - Formal or casual?
   - Technical or simple language?

🔧 Your Expertise:
   What are your strengths? (coding, writing, analysis, etc.)
   What areas need more explanation?

Example:
"I'm a senior data scientist working on ML models.
I prefer brief responses with code examples. Skip basic explanations,
but do explain ML concepts when relevant."

What would you like help with?
"""

User: "I'm a senior ML engineer. I work on computer vision models.
I prefer direct answers. Skip basics."

Agent: """
Got it! I can see you're experienced.

I'll remember:
✅ Role: Senior ML engineer, computer vision
✅ Style: Direct answers, no fluff
✅ Expertise: ML, computer vision
✅ No basic explanations needed

Here's what I can help with:

📊 **Data Work:**
   - Create/query databases (SQL, vector stores)
   - Process images/videos with OCR
   - Analyze datasets with Python

🔍 **Research:**
   - Web search for papers, tutorials
   - Save findings to knowledge base
   - Generate summaries

⏰ **Organization:**
   - Track experiments, results
   - Set reminders for deadlines
   - Manage project notes

Ready? What would you like help with?
"""

User: "Set up a vector database for image embeddings"

Agent: [Directly provides code, no explanations, assumes CV knowledge]
```

### Advanced: Onboarding via Profile Presets

**For users who want quick setup:**

```python
# Provide preset profiles
PRESETS = {
    "senior_dev": {
        "style": "brief, technical",
        "assume_knowledge": ["python", "sql", "git"],
        "skip_basics": True,
    },
    "business_user": {
        "style": "friendly, explanations",
        "assume_knowledge": [],
        "skip_basics": False,
    },
    "data_scientist": {
        "style": "balanced, code examples",
        "assume_knowledge": ["python", "statistics", "ml"],
        "skip_basics": ["python", "stats"],
    },
}
```

**Agent can ask:**
```
Would you like to start with a preset profile?
- Senior Developer (brief, technical)
- Business User (friendly, explanatory)
- Data Scientist (balanced, code examples)
- Custom (tell me your preferences)
```

---

## Implementation Plan

### Phase 1: Onboarding Detection (Week 1)

**File:** `src/executive_assistant/channels/base.py`

```python
def should_show_onboarding(thread_id: str) -> bool:
    """Detect if user needs onboarding."""
    try:
        # Check if user has interacted before
        memories = get_mem_storage().list_memories(thread_id)
        instincts = get_instinct_storage().list_instincts(thread_id)

        known_about_user = len(memories) + len(instincts)

        # Also check message patterns
        # - "hi", "hello" alone = new user
        # - Vague "help" without context

        return known_about_user < 5
    except:
        return False
```

### Phase 2: Onboarding Messages (Week 2)

**File:** `src/executive_assistant/skills/on_demand/user_onboarding.md`

**Create onboarding script** with:
- Welcome message
- Introduction questions
- Teaching by example
- Capabilities overview

### Phase 3: Integration with Agent (Week 2-3)

**Modify:** `src/executive_assistant/channels/base.py`

```python
async def _should_show_onboarding(self, message: str, thread_id: str) -> bool:
    """Check if onboarding is appropriate."""

    # Don't onboard if user is already in conversation
    if len(self._get_conversation_history(thread_id)) > 5:
        return False

    # Check if user needs onboarding
    if should_show_onboarding(thread_id):
        return True

    return False


async def get_onboarding_message(self, thread_id: str) -> str:
    """Load onboarding message content."""

    from executive_assistant.skills.on_demand.user_onboarding import (
        get_welcome_message,
        get_capabilities_message,
    )

    # Check what we already know
    memories = get_mem_storage().list_memories(thread_id)
    user_profile = extract_user_profile(memories)

    return get_welcome_message(user_profile)
```

### Phase 4: Context-Aware Help (Week 3)

**Vague request handler** uses existing memories:

```python
async def handle_vague_request(self, message: str, thread_id: str) -> str:
    """Handle vague requests with personalized help."""

    memories = get_mem_storage().list_memories(thread_id)

    # Extract user info
    role = find_memory_by_key(memories, "role")
    expertise = find_memory_by_key(memories, "expertise")
    recent_work = find_recent_context(memories)

    if role and expertise:
        # Personalized help
        return f"""
I'd love to help, {role}!

Based on your work on {recent_work}, I can help with:
{get_relevant_capabilities(expertise)}

What would you like to do?
"""
    else:
        # Generic help with examples
        return get_generic_help_with_examples()
```

---

## Success Metrics

### Quantitative
- **Onboarding completion rate**: % users who complete introduction
- **Time to first effective task**: < 2 minutes after onboarding
- **Vague request reduction**: 50% decrease in "help" requests
- **User satisfaction**: Conversation continuation rate

### Qualitative
- Users feel welcomed and understood
- Learning curve is gentle, not overwhelming
- Expert users feel respected (not talked down to)
- Beginner users feel supported (not overwhelmed)

---

## Summary

### Two Types of Onboarding

1. **Setup Onboarding** (Current focus)
   - Get assistant running
   - Configure channels, models, storage
   - Validate installation
   - **CLI wizard approach**

2. **User Onboarding** (NEW - this document)
   - Introduce agent capabilities
   - Teach effective prompting
   - Learn about user naturally
   - **Conversational approach**

### Key Principle: Organic Learning

**DON'T:**
- ❌ Create "skill levels" or "literacy scores"
- ❌ Track "prompt quality metrics"
- ❌ Categorize users into boxes

**DO:**
- ✅ Extract info naturally from conversation
- ✅ Detect patterns over time
- ✅ Adapt responses based on learning
- ✅ Use memories/instincts flexibly

### Success Means

**The agent gets to know each user as a unique individual**, not as a data point in a category.

Just like a human assistant would! 🎯
