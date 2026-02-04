# Existing Instincts System Analysis & Three-Tier Integration

**Date**: 2026-02-04
**Finding**: Instincts ARE already implemented! Here's what exists and what needs improvement.

---

## Existing Implementation: What's Already There

### ✅ Core Components (All Implemented!)

```python
# 1. Observer (observer.py)
- Detects corrections ("no, I meant...")
- Detects repetitions ("do it again")
- Detects verbosity preferences ("be brief", "more detail")
- Detects format preferences ("bullets", "json", "markdown")
- Tracks success/failure (satisfaction/frustration patterns)

# 2. Injector (injector.py)
- Loads instincts into system prompt
- Conflict resolution (concise > detailed, urgent > everything)
- Confidence scoring (base + frequency + recency + success rate)
- Domain-based grouping (communication, format, workflow, etc.)
- Adaptive injection (high quality = more instincts)

# 3. Storage (instinct_storage.py)
- JSON-based storage (instincts.jsonl + instincts.snapshot.json)
- Confidence scoring (0.0 to 1.0)
- Temporal decay (halves every 30 days without reinforcement)
- Domains: communication, format, workflow, tool_selection, timing, emotional_state, learning_style, expertise
- Sources: preference-expressed, correction-detected, repetition-confirmed, etc.

# 4. Evolver (evolver.py)
- Clusters instincts into skills
- Creates higher-level abstractions

# 5. Emotional Tracker (emotional_tracker.py)
- Tracks user emotional state
- Detects frustration, confusion, satisfaction

# 6. Profiles (profiles.py)
- User profile presets
- Custom profiles
```

### Current Domains

```python
_ALLOWED_DOMAINS = {
    "communication",      # Communication style (brief, detailed, etc.)
    "format",             # Output format (bullets, json, markdown, etc.)
    "workflow",           # Workflow patterns (repeat, explore, etc.)
    "tool_selection",     # Tool preferences
    "verification",       # Quality standards
    "timing",             # Timing preferences
    "emotional_state",    # ✅ Already there!
    "learning_style",     # ✅ Already there!
    "expertise",          # ✅ Already there!
}
```

---

## What's EXCELLENT (Keep As-Is)

### 1. Confidence Scoring System ✅

```python
# Multi-factor confidence adjustment
final_confidence = (
    base_confidence +           # Initial confidence
    frequency_boost +           # +0.03 per occurrence
    staleness_penalty +         # Decay over time
) * success_multiplier          # Success rate multiplier
```

**Why it's brilliant**:
- Frequency: Patterns seen more often = higher confidence
- Recency: Recent patterns = more relevant
- Success: Patterns that work = reinforced
- Decay: Old patterns fade if not used

### 2. Conflict Resolution ✅

```python
CONFLICT_RESOLUTION = {
    ("timing", "urgent"): {
        "overrides": ["communication:detailed", "communication:explain"],
        "min_confidence": 0.6,
    },
    ("communication", "concise"): {
        "overrides": ["communication:detailed", "communication:elaborate"],
    },
    ("emotional_state", "frustrated"): {
        "overrides": ["workflow:standard"],
        "min_confidence": 0.5,
    },
}
```

**Why it's brilliant**: Prevents contradictory instructions

### 3. Pattern Detection ✅

```python
PATTERNS = {
    "correction": ["no, i meant", "actually?", "wait, that's not"],
    "repetition": ["again", "repeat", "like you did before"],
    "preference_verbosity": [
        (r"be brief", "concise"),
        (r"more detail", "detailed"),
    ],
    "preference_format": [
        (r"bullet points", "bullets"),
        (r"json|csv", "format_preference"),
    ],
}
```

**Why it's brilliant**: Automatic learning without user effort

### 4. Success/Failure Tracking ✅

```python
SATISFACTION_PATTERNS = [
    r"perfect|great|awesome|thanks|exactly what",
    r"👍|✅|🎉|😊",
]

FRUSTRATION_PATTERNS = [
    r"nevermind|forget it|whatever",
    r"^(ok|okay|fine)[!.]*$",
    r"\?+$",  # Multiple question marks
]
```

**Why it's brilliant**: Reinforces what works, discards what doesn't

---

## What's Missing for Three-Tier Integration

### Gap 1: No Integration with Journal ❌

**Problem**: Instincts can't learn time-based patterns from journal

**Example**:
```
Journal shows:
- [Every Monday 9am] User creates weekly reports
- [Every Friday 4pm] User is tired, brief responses
- [Morning interactions] User is detailed, strategic

Current Instincts: ❌ Can't detect these time patterns
Needed: ✅ Temporal instinct learning from journal
```

**Solution**:
```python
# NEW: Journal-based instinct learning
class JournalInstinctLearner:
    """Analyze journal for temporal patterns"""

    def detect_temporal_patterns(self, thread_id):
        """Detect time-based behavioral patterns"""

        # Get journal entries
        entries = journal.get_time_range(
            thread_id=thread_id,
            start=now() - timedelta(days=30),
            end=now()
        )

        # Detect: Monday morning patterns
        monday_mornings = [
            e for e in entries
            if e["timestamp"].weekday() == 0  # Monday
            and e["timestamp"].hour < 12
        ]

        if len(monday_mornings) >= 4:
            # Pattern detected!
            instinct = {
                "trigger": "Monday morning request",
                "action": "be strategic and detailed, focus on planning",
                "domain": "temporal_pattern",
                "confidence": 0.8,
                "source": "journal_analysis",
                "metadata": {
                    "pattern_type": "weekday_morning",
                    "sample_size": len(monday_mornings),
                    "time_range": "last_30_days"
                }
            }

        # Detect: Friday afternoon patterns
        friday_afternoons = [
            e for e in entries
            if e["timestamp"].weekday() == 4  # Friday
            and e["timestamp"].hour >= 14
        ]

        if len(friday_afternoons) >= 4:
            instinct = {
                "trigger": "Friday afternoon",
                "action": "be brief and encouraging, user is tired",
                "domain": "temporal_pattern",
                "confidence": 0.75,
                "source": "journal_analysis",
            }
```

---

### Gap 2: No Integration with Memory ❌

**Problem**: Instincts don't leverage memory facts

**Example**:
```
Memory: "Alice is PM at Acme, sales analytics domain"

User: "Explain the API"
Current Instincts: Generic explanation
Enhanced Instincts: "Skip basics, Alice knows sales domain"
```

**Solution**:
```python
# NEW: Memory-informed instinct application
class MemoryInformedInstincts:
    """Use memory to customize instinct behavior"""

    def apply_with_memory_context(self, instincts, memory):
        """Adjust instinct actions based on memory"""

        enhanced_instincts = []

        for instinct in instincts:
            action = instinct["action"]
            domain = instinct["domain"]

            # User has expertise in this domain?
            if domain == "communication" and memory.get("expertise"):
                # Skip basics if user is expert
                enhanced_instincts.append({
                    **instinct,
                    "action": f"{action} (skip basics, user has expertise)",
                })

            # User's role affects communication style?
            elif domain == "communication":
                role = memory.get("role", "")

                if "PM" in role or "Manager" in role:
                    # PMs prefer bullet points, milestones
                    enhanced_instincts.append({
                        **instinct,
                        "action": f"{action} (use bullet points, focus on milestones)",
                    })

                elif "Developer" in role or "Engineer" in role:
                    # Devs prefer code, technical details
                    enhanced_instincts.append({
                        **instinct,
                        "action": f"{action} (include code, technical details)",
                    })

            else:
                enhanced_instincts.append(instinct)

        return enhanced_instincts
```

---

### Gap 3: No "Projects" Domain ❌

**Problem**: Can't track active projects and their progress

**Example**:
```
User: "Continue the dashboard project"
Current Instincts: Don't know what project is
Needed: ✅ Project tracking instinct
```

**Solution**:
```python
# NEW: Projects domain
_ALLOWED_DOMAINS.add("projects")

class ProjectTracker:
    """Track active projects and their context"""

    def detect_project_mention(self, message, thread_id):
        """Detect when user mentions an active project"""

        # Get recent journal entries for project mentions
        recent_entries = journal.get_time_range(
            thread_id=thread_id,
            start=now() - timedelta(days=7),
        )

        # Extract project names from entries
        projects = extract_projects(recent_entries)

        # Match in current message
        mentioned = [p for p in projects if p.lower() in message.lower()]

        if mentioned:
            return {
                "trigger": f"user mentions project: {mentioned[0]}",
                "action": f"contextualize response around {mentioned[0]} project",
                "domain": "projects",
                "confidence": 0.9,
                "metadata": {
                    "projects": mentioned,
                    "context_from": "journal_analysis"
                }
            }
```

---

### Gap 4: No "Goals/Intentions" Domain ❌

**Problem**: Can't track what user wants to achieve (future-oriented)

**Example**:
```
Memory: What user has (name, role)
Journal: What user did (activity history)
Instincts: How user behaves (patterns)
Goals: ❌ MISSING - What user wants (future intentions)
```

**Why this matters**:
```
User: "Create a report"
Current: Creates generic report
With Goals: Creates report that advances user's Q4 goal
```

---

## Proposed Improvements

### Phase 1: Add Journal Integration (Week 1)

```python
# File: src/executive_assistant/instincts/journal_learner.py

class JournalInstinctLearner:
    """Learn temporal patterns from journal"""

    def analyze_and_learn(self, thread_id):
        """Analyze journal for instinct patterns"""

        # 1. Detect day-of-week patterns
        weekday_patterns = self._detect_weekday_patterns(thread_id)

        # 2. Detect time-of-day patterns
        time_patterns = self._detect_time_patterns(thread_id)

        # 3. Detect project continuity
        project_patterns = self._detect_project_patterns(thread_id)

        # 4. Create/update instincts
        for pattern in weekday_patterns + time_patterns + project_patterns:
            instincts.create_or_update(
                thread_id=thread_id,
                **pattern
            )

    def _detect_weekday_patterns(self, thread_id):
        """Detect patterns like 'Monday = planning'"""
        entries = journal.get_time_range(
            thread_id=thread_id,
            start=now() - timedelta(days=90),  # Last quarter
        )

        patterns = []

        # Group by weekday
        for weekday in range(7):  # 0=Monday, 6=Sunday
            day_entries = [
                e for e in entries
                if e["timestamp"].weekday() == weekday
            ]

            if len(day_entries) >= 8:  # At least 8 occurrences
                # Analyze common themes
                themes = extract_themes(day_entries)

                patterns.append({
                    "trigger": f"{WEEKDAY_NAMES[weekday]} request",
                    "action": themes["dominant_style"],
                    "domain": "temporal_pattern",
                    "confidence": min(0.9, len(day_entries) * 0.05),
                    "source": "journal_weekday_analysis",
                    "metadata": {
                        "weekday": weekday,
                        "sample_size": len(day_entries),
                        "dominant_theme": themes["dominant"]
                    }
                })

        return patterns
```

### Phase 2: Add Memory Integration (Week 1)

```python
# File: src/executive_assistant/instincts/memory_enhancer.py

class MemoryEnhancedInstincts:
    """Enhance instincts with memory context"""

    def enhance_instincts(self, instincts, memory):
        """Add memory-based customization to instincts"""

        enhanced = []

        for instinct in instincts:
            base_action = instinct["action"]
            domain = instinct["domain"]

            # Memory-informed customization
            if domain == "communication":
                enhanced.append({
                    **instinct,
                    "action": self._customize_for_role(base_action, memory),
                })

            elif domain == "tool_selection":
                enhanced.append({
                    **instinct,
                    "action": self._customize_for_expertise(base_action, memory),
                })

            elif domain == "workflow":
                enhanced.append({
                    **instinct,
                    "action": self._customize_for_goals(base_action, memory),
                })

            else:
                enhanced.append(instinct)

        return enhanced

    def _customize_for_role(self, action, memory):
        """Customize communication based on user role"""
        role = memory.get("role", "").lower()

        if "pm" in role or "manager" in role:
            return f"{action} (PM-style: bullet points, milestones, strategic)"
        elif "developer" in role or "engineer" in role:
            return f"{action} (Dev-style: code, technical details, examples)"
        elif "analyst" in role:
            return f"{action} (Analyst-style: data, metrics, visualizations)"
        else:
            return action

    def _customize_for_expertise(self, action, memory):
        """Customize based on user expertise"""
        expertise = memory.get("expertise", [])

        if "python" in expertise:
            return f"{action} (assume Python knowledge, skip basics)"
        elif "sql" in expertise:
            return f"{action} (use SQL examples, query optimization)"
        else:
            return action
```

### Phase 3: Add Projects Domain (Week 2)

```python
# File: src/executive_assistant/instincts/projects.py

class ProjectInstinctTracker:
    """Track active projects and apply project-specific context"""

    def get_project_context(self, thread_id):
        """Get active project context from journal"""

        # Get recent journal entries
        recent = journal.get_time_range(
            thread_id=thread_id,
            start=now() - timedelta(days=7),
        )

        # Extract active projects
        projects = extract_active_projects(recent)

        if projects:
            return {
                "trigger": "active_project_detected",
                "action": f"Contextualize around active projects: {', '.join(projects)}",
                "domain": "projects",
                "confidence": 0.9,
                "metadata": {
                    "active_projects": projects,
                    "context_from": "journal_recent"
                }
            }

        return None
```

---

## Do We Need a Fourth Pillar?

### Current Three Pillars

```
Memory: "Who you are" (Declarative)
  - Name, role, preferences
  - Static facts
  - Present-focused

Journal: "What you did" (Episodic)
  - Activity history
  - Time-based
  - Past-focused

Instincts: "How you behave" (Procedural)
  - Behavioral patterns
  - Learned preferences
  - Action-oriented
```

### What's Missing?

Looking at the knowledge types, we're missing:

#### 1. **Goals/Intentions** (Future-Oriented) ⭐ STRONG CANDIDATE

```
"What you want to achieve"

Examples:
- "Launch sales dashboard by end of Q1"
- "Learn Python this year"
- "Automate daily reporting"
- "Reduce churn rate by 10%"

Why it's different:
- Memory: Has ("knows Python")
- Journal: Did ("studied Python yesterday")
- Instincts: How ("prefers code examples")
- Goals: Wants ("complete Python certification by June")
```

**Use cases**:
- Prioritize tasks that advance goals
- Suggest next steps toward goals
- Track progress toward goals
- Motivate and encourage

**Example**:
```
User: "Create a report"

With Goals:
Goal: "Automate daily reporting by end of Q1"
Response: "I'll create this report with automation in mind,
         since that's your Q1 goal. Should I include
         automation scripts for daily generation?"

Without Goals:
Response: Generic report (no goal alignment)
```

---

#### 2. **Projects** (Track Active Work)

```
"What you're working on"

Examples:
- Sales dashboard project (active, 60% complete)
- Python learning project (ongoing)
- Customer onboarding flow (planned)

Why it's different:
- Journal: Logged "created dashboard component" (activity)
- Projects: Dashboard project is 60% done, blocked on API (state)

**Use cases**:
- Continue conversations contextually
- Track project progress
- Manage multiple concurrent projects
- Blockers, dependencies, milestones

**Example**:
```
User: "Continue the work"

With Projects:
Project: Sales Dashboard (60% complete)
Last step: Created chart components
Next step: Connect to API
Response: "I'll continue the sales dashboard by
         connecting the charts to the API. You're at 60%,
         so we're making good progress toward completion."

Without Projects:
Response: "What work would you like me to continue?"
```

---

#### 3. **Relations** (Knowledge Graph)

```
"How concepts connect"

Examples:
- "Sales dashboard" → uses → "PostgreSQL"
- "Churn analysis" → involves → "Customer data"
- "Q4 report" → part of → "Sales analytics"

Why it's different:
- Memory: Knows "PostgreSQL" exists
- Journal: Logged "used PostgreSQL for dashboard"
- Relations: Dashboard depends on PostgreSQL (connection)

**Use cases**:
- Impact analysis (if I change X, what breaks?)
- Dependency tracking (what does X depend on?)
- Suggest related concepts (you worked on X, maybe also Y?)

**Example**:
```
User: "Drop the customers table"

With Relations:
Relations: customers table → used by → dashboard, reports, API
Response: "Dropping customers table will break 3 things:
         dashboard (source), reports (dependency), API (consumer).
         Are you sure?"

Without Relations:
Response: "Table dropped" (doesn't warn about dependencies)
```

---

## Recommendation: YES, Add Fourth Pillar

### Fourth Pillar: **GOALS** ⭐

**Why goals?**

1. **Future-oriented**: Complements past-focused journal
2. **Motivational**: Explains WHY user does things
3. **Prioritization**: Helps decide what's important
4. **Progress tracking**: Measure advancement toward intentions
5. **Direction**: Provides overall direction and purpose

### How Goals Complete the System

```
Memory: "Alice is PM at Acme" ← Who
Journal: "Built dashboard yesterday" ← What
Instincts: "Prefers bullet points" ← How
Goals: "Launch dashboard by Q1" ← WHY/WHERE
```

**Example interaction**:
```
User: "Create a report"

Memory knows: Alice, PM at Acme
Journal knows: Built dashboard last week
Instincts know: Use bullet points
Goals knows: Goal = "Automate reporting by end of Q1"

Response: "I'll create a brief report for you, Alice.
         Since your goal is automated reporting by Q1,
         should I include automation scripts as
         part of this report? That would advance
         your Q1 objective."
```

**Perfect alignment!** Goals provide the WHY and WHERE.

---

### Alternative: Projects as Fourth Pillar?

**Pros**:
- More actionable than goals
- Tracks current state (not future)
- Natural fit with journal (recent work)

**Cons**:
- Overlaps with journal (what did)
- Less strategic than goals (why doing)

**Verdict**: Projects could be a **sub-system of journal** rather than a separate pillar.

---

## Proposed Four-Pillar System

### Complete Architecture

```
┌─────────────────────────────────────────────────┐
│                                                  │
│  LAYER 1: Memory (Who)                          │
│  - Name, role, preferences                      │
│  - Static facts                                 │
│  - Present-focused                              │
│  Access: Instant (< 5ms)                        │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  LAYER 2: Journal (What)                         │
│  - Activity history with rollups               │
│  - Time-series entries                           │
│  - Past-focused                                  │
│  Access: On-demand (< 30ms)                     │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  LAYER 3: Instincts (How)                        │
│  - Behavioral patterns                           │
│  - Learned preferences                           │
│  - Action-oriented                               │
│  Access: Automatic (< 10ms)                      │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  LAYER 4: Goals (Why/Where)                      │
│  - Future intentions                             │
│  - Objectives & milestones                       │
│  - Progress tracking                            │
│  - Future-focused                                │
│  Access: On-demand (< 20ms)                     │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Goals System Design

### Storage Structure

```python
# Table: goals
CREATE TABLE goals (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,

    -- Goal content
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- 'short_term', 'medium_term', 'long_term'

    -- Time tracking
    target_date TEXT,
    created_at TEXT,
    completed_at TEXT,

    -- Progress
    status TEXT,  -- 'planned', 'in_progress', 'completed', 'abandoned'
    progress REAL,  -- 0.0 to 1.0

    -- Prioritization
    priority INTEGER,  -- 1-10
    importance INTEGER,  -- 1-10

    -- Connections
    parent_goal_id TEXT,  -- Sub-goals
    related_projects JSON,  -- ["dashboard", "api"]
    dependencies JSON,  -- ["learn Python", "get API access"]

    -- Metadata
    tags JSON,
    notes JSON,

    FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
);

-- Indexes
CREATE INDEX idx_goals_status ON goals(status);
CREATE INDEX idx_goals_target ON goals(target_date);
```

### Goal Types

```python
# Short-term (days to weeks)
{
    "title": "Fix critical bug in production",
    "category": "short_term",
    "target_date": "2025-02-07",
    "status": "in_progress",
    "progress": 0.7
}

# Medium-term (months to quarters)
{
    "title": "Automate daily sales reporting",
    "category": "medium_term",
    "target_date": "2025-03-31",
    "status": "in_progress",
    "progress": 0.3,
    "sub_goals": [
        {"title": "Build dashboard", "progress": 1.0},
        {"title": "Create automation script", "progress": 0.5},
        {"title": "Set up scheduling", "progress": 0.0}
    ]
}

# Long-term (quarters to years)
{
    "title": "Learn data science",
    "category": "long_term",
    "target_date": "2025-12-31",
    "status": "in_progress",
    "progress": 0.2,
    "milestones": [
        {"title": "Complete Python course", "by": "2025-03-31"},
        {"title": "Build 5 projects", "by": "2025-06-30"},
        {"title": "Get certification", "by": "2025-09-30"}
    ]
}
```

### Integration with Other Pillars

```python
# Goal-aware context building
def build_enhanced_context(user_message, thread_id):
    """Build context from all four pillars"""

    # 1. Memory (Who)
    memory = memory_storage.load_all(thread_id)

    # 2. Instincts (How)
    instincts = instinct_injector.build_instincts_context(thread_id)

    # 3. Journal (What) - only if needed
    journal = None
    if needs_journal_context(user_message):
        journal = journal.search(user_message, thread_id)

    # 4. Goals (Why/Where) - always check active goals
    goals = goal_storage.get_active_goals(thread_id)

    # Combine all
    context = {
        "memory": memory,
        "instincts": instincts,
        "journal": journal,
        "goals": goals,
    }

    return context
```

### Example: All Four Pillars Working

```
User: "Create a Python script"

↓ Memory (Who)
✅ Alice, PM at Acme
✅ Sales analytics domain
✅ Beginner in Python

↓ Instincts (How)
✅ Keep it brief
✅ Include comments
✅ Use examples

↓ Journal (What)
✅ [Yesterday] Attempted Python automation
✅ [Last week] Took Python course

↓ Goals (Why/Where) ← NEW!
✅ Goal: "Learn data science by end of year"
✅ Milestone: "Complete Python basics by March"
✅ Progress: 20% complete

↓ Perfect response

"I'll create a brief Python script for you, Alice.

Since you're learning Python (20% toward your March
milestone), I'll include comments to help you understand:

```python
# TODO: Load sales data from PostgreSQL
# You can use the psycopg2 library for this
conn = psycopg2.connect(...)
```

This aligns with your data science goal. Want me to
expand this script or explain any part in detail?
(Based on your journal, you attempted automation yesterday
and are taking a Python course, so this builds on both.)"
```

**Magic!** All four pillars contributing to perfect personalization.

---

## Summary

### Existing Instincts: Excellent Foundation ✅

**What's working**:
- Confidence scoring (frequency + recency + success)
- Conflict resolution (concise > detailed)
- Pattern detection (corrections, repetitions, preferences)
- Emotional tracking (frustration, satisfaction)
- Multiple domains (communication, format, workflow, etc.)

**What needs improvement**:
- ❌ No journal integration (can't learn temporal patterns)
- ❌ No memory integration (can't customize based on role/expertise)
- ❌ No projects domain (can't track active work)
- ❌ No time-based patterns (Monday mornings, Friday afternoons)

### Fourth Pillar: GOALS ⭐

**Why goals matter**:
1. Future-oriented (WHY/WHERE)
2. Provides purpose and direction
3. Enables progress tracking
4. Helps prioritization
5. Motivates and encourages

### Implementation Plan

**Week 1**: Fix memory bug + add journal integration to instincts
**Week 2**: Add memory enhancement to instincts
**Week 3**: Add projects domain to journal/instincts
**Week 4**: Implement goals system (fourth pillar)

**All four pillars working together in 1 month!**

---

**Ready to implement?**
1. Memory fix (2-4 hours) - Critical bug
2. Instincts journal integration (3-5 days)
3. Goals system (1 week) - Fourth pillar!

All systems will work harmoniously together! 🎯
