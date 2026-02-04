# Goal Dynamics: Detection & Update System

**Date**: 2026-02-04
**Challenge**: Goals change over time - how do we detect and update?

---

## Goal Lifecycle

### Complete Lifecycle

```
[Planned] → [Active] → [Paused] → [Completed/Abandoned] → [Archived]
    ↓           ↓          ↓            ↓              ↓
 Created    Being worked  On hold    Done/gave up    Kept for history
```

### State Transitions

```python
GOAL_STATES = {
    "planned": "Created but not started yet",
    "active": "Currently being worked on",
    "paused": "Temporarily on hold (may resume)",
    "completed": "Successfully achieved",
    "abandoned": "User lost interest/cancelled",
    "archived": "Old completed/abandoned goals (read-only)",
}
```

---

## Detection Mechanisms

### 1. Explicit User Statements (Direct)

**Pattern**: User directly states goal change

```
User: "I changed my mind about the dashboard"
→ Detect: Goal change mentioned
→ Action: Prompt user for clarification

User: "I don't want to learn Python anymore"
→ Detect: Abandonment stated
→ Action: Mark goal as abandoned, archive

User: "I finished the automation!"
→ Detect: Completion stated
→ Action: Mark as completed, congratulate

User: "Put the dashboard project on hold for now"
→ Detect: Pause requested
→ Action: Mark as paused, note reason
```

**Implementation**:
```python
class GoalChangeDetector:
    """Detect explicit goal changes in user messages"""

    EXPLICIT_PATTERNS = {
        "abandonment": [
            r"i don't want to.*anymore",
            r"forget about (the )?.*goal",
            r"not interested in.*anymore",
            r"cancel (the )?.*goal",
            r"nevermind (the )?.*goal",
        ],
        "completion": [
            r"i finished.*",
            r"(completed|done|achieved).*(goal|objective|target)",
            r"successfully (built|created|finished).*",
        ],
        "pause": [
            r"put.*on hold",
            r"pause (the )?.*(project|goal)",
            r"come back to.*later",
            r"focus on.*instead",
        ],
        "change": [
            r"i changed my mind about",
            r"instead of.*i want to",
            r"let's (switch|change).*to",
            r"new goal instead",
        ],
        "progress_update": [
            r"i'm (%|\d+).*done with",
            r"made progress on",
            r"(moved forward|advanced).*(toward|on)",
        ],
    }

    def detect_explicit_change(self, message, thread_id):
        """Detect explicit goal changes in message"""

        active_goals = goals.get_active_goals(thread_id)

        for change_type, patterns in self.EXPLICIT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return {
                        "type": change_type,
                        "confidence": 0.9,  # High confidence (explicit)
                        "source": "explicit_statement",
                        "detected_at": utc_now(),
                        "message": message,
                    }

        return None
```

---

### 2. Journal Pattern Analysis (Implicit)

**Pattern**: Journal shows user stopped working on goal

```
Goal: "Learn Python by March 31"
Journal shows:
  - [Jan] 15 Python-related entries
  - [Feb] 8 Python-related entries
  - [Mar 1-15] 0 Python-related entries ← Stopped working

→ Detect: Goal abandonment (implicit)
→ Action: Ask user "Still working on Python goal?"
```

**Implementation**:
```python
class GoalStagnationDetector:
    """Detect stalled or abandoned goals from journal"""

    def analyze_goal_activity(self, goal_id, thread_id):
        """Check if goal is still being actively pursued"""

        goal = goals.get_goal(goal_id, thread_id)
        if not goal:
            return None

        # Get journal entries since goal was last updated
        entries = journal.get_time_range(
            thread_id=thread_id,
            start=goal["updated_at"],
            end=utc_now(),
            limit=100,
        )

        # Check for goal-related activity
        goal_keywords = extract_keywords(goal["title"], goal["description"])
        relevant_entries = [
            e for e in entries
            if any(kw in e["content"].lower() for kw in goal_keywords)
        ]

        # Calculate activity metrics
        time_since_update = (utc_now() - parse_datetime(goal["updated_at"])).days
        recent_activity = len(relevant_entries)

        # Detect stagnation
        if time_since_update > 30 and recent_activity == 0:
            return {
                "type": "stagnation",
                "confidence": 0.8,
                "reason": f"No activity for {time_since_update} days",
                "source": "journal_analysis",
            }

        elif time_since_update > 14 and recent_activity < 2:
            return {
                "type": "potential_stagnation",
                "confidence": 0.6,
                "reason": f"Low activity recently ({recent_activity} entries in {time_since_update} days)",
                "source": "journal_analysis",
            }

        return None
```

---

### 3. Progress Tracking (Continuous)

**Pattern**: Progress bar moves or stalls

```
Goal: "Automate reporting (target: March 31)"
Progress updates:
  - Week 1: 10% → 20% → 25% (moving)
  - Week 2: 25% → 30% → 35% (slowing)
  - Week 3: 35% → 35% → 35% (stalled for 21 days)

→ Detect: Stalled progress
→ Action: Check if user wants to continue or pivot
```

**Implementation**:
```python
class ProgressTracker:
    """Track progress and detect stall patterns"""

    def check_progress_velocity(self, goal_id, thread_id):
        """Check if progress has stalled"""

        goal = goals.get_goal(goal_id, thread_id)
        progress_history = goal.get("progress_history", [])

        if len(progress_history) < 3:
            return None  # Not enough data

        # Calculate recent velocity
        recent = progress_history[-3:]
        velocities = [
            recent[i]["progress"] - recent[i-1]["progress"]
            for i in range(1, len(recent))
        ]

        avg_velocity = sum(velocities) / len(velocities)

        # Detect stall
        if avg_velocity < 0.01:  # Less than 1% progress per update
            days_stalled = (utc_now() - parse_datetime(recent[-1]["timestamp"])).days

            return {
                "type": "progress_stall",
                "confidence": min(0.9, 0.5 + (days_stalled * 0.02)),  # Increases over time
                "reason": f"Progress stalled at {goal['progress']}% for {days_stalled} days",
                "source": "progress_tracking",
            }

        return None
```

---

### 4. Target Date Passed (Time-based)

**Pattern**: Target date arrives, goal not complete

```
Goal: "Launch dashboard by March 31"
Today: April 15

→ Detect: Target date passed
→ Action: Ask user "Still working on dashboard launch? Update target date?"
```

**Implementation**:
```python
class TargetDateMonitor:
    """Monitor target dates and check for expired goals"""

    def check_target_dates(self, thread_id):
        """Check if any target dates have passed"""

        active_goals = goals.get_active_goals(thread_id)
        overdue = []

        for goal in active_goals:
            target_date = parse_datetime(goal["target_date"])
            today = utc_now().date()

            if target_date.date() < today:
                overdue.append({
                    "goal_id": goal["id"],
                    "goal_title": goal["title"],
                    "target_date": goal["target_date"],
                    "days_overdue": (today - target_date.date()).days,
                    "current_progress": goal["progress"],
                })

        return overdue
```

---

### 5. Journal Contradiction Detection (Inference)

**Pattern**: Journal shows activity contradicting goal

```
Goal: "Learn Python" (active)
Journal shows:
  - [Yesterday] "Decided to focus on R instead"
  - [Today] "R is so much better than Python"

→ Detect: Goal abandonment (implicit contradiction)
→ Action: Confirm with user
```

**Implementation**:
```python
class ContradictionDetector:
    """Detect contradictions between goals and journal activity"""

    def detect_goal_contradictions(self, thread_id):
        """Find goals that contradict journal activity"""

        active_goals = goals.get_active_goals(thread_id)
        recent_entries = journal.get_time_range(
            thread_id=thread_id,
            start=utc_now() - timedelta(days=7),
        )

        contradictions = []

        for goal in active_goals:
            goal_keywords = extract_keywords(goal["title"], goal["description"])

            # Check for contradictory statements
            for entry in recent_entries:
                content_lower = entry["content"].lower()

                # Contradiction patterns
                if any(kw in content_lower for kw in goal_keywords):
                    if is_contradiction(entry["content"], goal):
                        contradictions.append({
                            "goal_id": goal["id"],
                            "entry_id": entry["id"],
                            "type": "contradiction",
                            "confidence": 0.7,
                            "reason": f"Journal entry contradicts '{goal['title']}'",
                            "evidence": entry["content"][:100],
                        })

        return contradictions
```

---

## Update Mechanisms

### Automatic Updates

```python
class GoalUpdater:
    """Automatically update goals based on detected changes"""

    def handle_detected_change(self, change_event, thread_id):
        """Process detected goal change"""

        change_type = change_event["type"]
        confidence = change_event["confidence"]

        # High confidence changes (> 0.8) → Auto-update
        # Medium confidence (0.5-0.8) → Confirm with user
        # Low confidence (< 0.5) → Monitor only

        if confidence >= 0.8:
            self._auto_update(change_event, thread_id)

        elif confidence >= 0.5:
            self._confirm_and_update(change_event, thread_id)

        else:
            # Log for monitoring
            logger.info(f"Low-confidence goal change detected: {change_type}")

    def _auto_update(self, event, thread_id):
        """Automatically update goal (high confidence)"""

        if event["type"] == "completion":
            goals.complete_goal(
                goal_id=event["goal_id"],
                thread_id=thread_id,
                completion_note=f"Auto-detected completion: {event['message']}"
            )

            # Trigger celebration
            self._celebrate_goal_completion(event["goal_id"], thread_id)

        elif event["type"] == "stagnation":
            goals.update_goal(
                goal_id=event["goal_id"],
                thread_id=thread_id,
                updates={"status": "paused", "pause_reason": event["reason"]}
            )

        elif event["type"] == "progress_stall":
            # Don't auto-update, but flag for review
            goals.flag_for_review(
                goal_id=event["goal_id"],
                thread_id=thread_id,
                flag_reason=event["reason"]
            )
```

---

### User Confirmation Flow

```python
class GoalConfirmationFlow:
    """Confirm goal changes with user before applying"""

    def confirm_and_update(self, event, thread_id):
        """Ask user to confirm goal change"""

        goal = goals.get_goal(event["goal_id"], thread_id)

        # Build confirmation message
        if event["type"] == "abandonment":
            message = f"""
I noticed you mentioned: "{event['message']}"

Does this mean you want to abandon your goal:
"{goal['title']}" (currently {goal['progress']}% complete)?

Options:
1. Yes, abandon this goal
2. No, keep working on it
3. Pause it temporarily
4. Update the goal instead

What would you like to do?
"""

        elif event["type"] == "stagnation":
            message = f"""
I noticed your goal "{goal['title']}" hasn't seen progress
in {event.get('stall_duration', 'a while')}.

Your last update was {event['last_progress_date']} and it's
currently at {goal['progress']}% complete.

Should I:
1. Pause this goal for now?
2. Update the target date?
3. Mark it as abandoned?
4. Leave it as is?

What would you prefer?
"""

        # Send to user and wait for response
        response = await send_message(thread_id, message)
        return self._handle_confirmation_response(response, event, thread_id)
```

---

## Update Strategies

### Strategy 1: Soft Updates (Suggested Changes)

```python
# Don't immediately change goal state
# Instead, mark it and ask user

goals.flag_goal(
    goal_id="goal_123",
    flag="potential_abandonment",
    reason="No activity for 30 days",
    detected_at="2025-02-04T10:00:00Z"
)

# User sees:
"""
📊 Goal Status Check

Goal: "Learn Python"
Status: ⚠️ Potential Abandonment
Reason: No activity detected for 30 days
Last progress: 25% (Jan 15)

Is this goal still active?
[Yes, continue] [Pause it] [Abandon]
"""
```

---

### Strategy 2: Progressive Updates (Gradual)

```python
# Phase 1: Flag
goals.flag_goal(goal_id, "review_needed", reason="Target date passed")

# Phase 2: Downgrade priority
goals.update_goal(goal_id, priority=original_priority - 2)

# Phase 3: Mark as stale
goals.update_goal(goal_id, status="stale", last_activity=old_date)

# Phase 4: Archive (after confirmation)
goals.archive_goal(goal_id, reason="No response to 3 prompts")
```

---

### Strategy 3: Smart Inference (Context-Aware)

```python
class SmartGoalUpdater:
    """Make intelligent inferences about goal state"""

    def infer_goal_state(self, goal_id, thread_id):
        """Infer current goal state from all available context"""

        goal = goals.get_goal(goal_id, thread_id)

        # Factor 1: Recent journal activity
        recent_journal = journal.get_time_range(
            thread_id=thread_id,
            start=utc_now() - timedelta(days=14)
        )
        journal_activity_score = calculate_goal_relevance(
            recent_journal,
            goal["keywords"]
        )

        # Factor 2: Progress velocity
        progress_velocity = calculate_progress_velocity(goal_id)

        # Factor 3: Time since last update
        staleness = (utc_now() - parse_datetime(goal["updated_at"])).days

        # Factor 4: User mood/emotional state
        user_emotion = emotions.get_current_state(thread_id)
        emotion_score = {
            "frustrated": -0.3,
            "confused": -0.2,
            "satisfied": +0.2,
            "motivated": +0.3,
        }.get(user_emotion, 0.0)

        # Combine factors
        combined_score = (
            journal_activity_score * 0.3 +
            progress_velocity * 0.3 +
            (1.0 - min(staleness / 90, 1.0)) * 0.2 +  # Staleness penalty
            emotion_score * 0.2
        )

        # Map to state
        if combined_score > 0.7:
            return {"inferred_state": "active", "confidence": combined_score}
        elif combined_score > 0.4:
            return {"inferred_state": "paused", "confidence": combined_score}
        else:
            return {"inferred_state": "abandoned", "confidence": combined_score}
```

---

## Goal Versioning

### Track Changes Over Time

```python
# Goal history table
CREATE TABLE goal_versions (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    version INTEGER NOT NULL,

    -- Version snapshot
    title TEXT,
    description TEXT,
    target_date TEXT,
    priority INTEGER,

    -- Change metadata
    change_type TEXT,  -- 'created', 'updated', 'paused', 'completed', 'abandoned'
    change_reason TEXT,
    changed_at TEXT,

    -- Snapshot
    snapshot JSON,  -- Full goal state at this version

    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

# Example
goal_id: "goal_123"
version 1: Created (Jan 1) - "Launch dashboard by Q1"
version 2: Updated (Feb 1) - "Added automation requirement"
version 3: Paused (Feb 15) - "Focusing on other priorities"
version 4: Resumed (Mar 1) - "Back to dashboard project"
version 5: Completed (Mar 30) - "Dashboard launched!"
```

---

## Conflict Resolution

### Multiple Goals, Limited Resources

```python
class GoalPrioritizer:
    """Manage conflicts when user has competing goals"""

    def detect_conflicts(self, thread_id):
        """Find goals that conflict for resources"""

        active_goals = goals.get_active_goals(thread_id)

        # Check for:
        # 1. Time conflicts (target dates too close)
        # 2. Priority conflicts (high priority goals competing)
        # 3. Resource conflicts (learning Python vs learning R)

        conflicts = []

        for i, goal1 in enumerate(active_goals):
            for goal2 in active_goals[i+1:]:
                if goals_conflict(goal1, goal2):
                    conflicts.append({
                        "goal1": goal1,
                        "goal2": goal2,
                        "conflict_type": detect_conflict_type(goal1, goal2),
                    })

        return conflicts

    def suggest_resolution(self, conflicts, thread_id):
        """Suggest how to resolve goal conflicts"""

        for conflict in conflicts:
            if conflict["conflict_type"] == "time_overlap":
                return {
                    "suggestion": f"Goal '{conflict['goal1']['title']}' "
                                   f"and '{conflict['goal2']['title']}' both "
                                   f"target {conflict['goal1']['target_date']}. "
                                   f"Consider sequencing them or adjusting "
                                   f"target dates.",
                    "options": [
                        f"Prioritize '{conflict['goal1']['title']}'",
                        f"Prioritize '{conflict['goal2']['title']}'",
                        f"Adjust '{conflict['goal1']['title']}' target date",
                    ]
                }

            elif conflict["conflict_type"] == "resource_limit":
                return {
                    "suggestion": f"You have multiple learning goals "
                                   f"('{conflict['goal1']['title']}' and "
                                   f"'{conflict['goal2']['title']}'). "
                                   f"Consider focusing on one at a time.",
                    "options": [
                        f"Pause '{conflict['goal2']['title']}'",
                        f"Pause '{conflict['goal1']['title']}'",
                        f"Reduce scope for both",
                    ]
                }
```

---

## Automatic Status Updates

### Journal-Driven Progress

```python
class JournalProgressUpdater:
    """Update goal progress based on journal activity"""

    def update_progress_from_journal(self, thread_id):
        """Scan journal and auto-update goal progress"""

        active_goals = goals.get_active_goals(thread_id)

        for goal in active_goals:
            # Get journal entries since last progress update
            entries = journal.get_time_range(
                thread_id=thread_id,
                start=goal["updated_at"],
            )

            # Check for progress indicators
            progress_indicators = [
                r"made (?:some )?progress",
                r"(moved forward|advanced)",
                r"(completed|finished|done).*(?:\d+)%?",
                r"step (\d+) of (\d+)",
            ]

            total_progress = 0
            for entry in entries:
                for pattern in progress_indicators:
                    match = re.search(pattern, entry["content"], re.IGNORECASE)
                    if match:
                        # Extract progress percentage
                        if r"\d+%" in entry["content"]:
                            # Extract percentage
                            percent = extract_percentage(entry["content"])
                            total_progress = max(total_progress, percent)
                        elif "step" in entry["content"].lower():
                            # Calculate from "step X of Y"
                            step, total = match.groups()
                            total_progress = max(total_progress, (int(step) / int(total)) * 100)

            # Update if significant progress made
            if total_progress > goal["progress"] + 5:  # At least 5% increase
                goals.update_goal(
                    goal_id=goal["id"],
                    thread_id=thread_id,
                    updates={
                        "progress": total_progress,
                        "progress_history": goal.get("progress_history", []) + [{
                            "progress": total_progress,
                            "timestamp": utc_now(),
                            "source": "journal_detection",
                            "evidence": f"Auto-detected from {len(entries)} journal entries"
                        }]
                    }
                )

                logger.info(
                    f"Auto-updated goal progress: {goal['title']} "
                    f"({goal['progress']:.0f}% → {total_progress:.0f}%)"
                )
```

---

## Update Frequency

### Check Triggers

```python
# Scheduler for periodic checks

class GoalMaintenanceScheduler:
    """Periodic maintenance and checks"""

    def setup_schedules(self):
        """Set up automated checks"""

        # Daily: Check for target dates passed
        self.scheduler.add_job(
            self.check_target_dates,
            trigger='cron',
            hour=0,  # Midnight
            id='check_target_dates'
        )

        # Weekly: Check for stagnation
        self.scheduler.add_job(
            self.check_stagnation,
            trigger='cron',
            day_of_week='mon',
            hour=9,
            id='check_stagnation'
        )

        # Weekly: Check for contradictions
        self.scheduler.add_job(
            self.check_journal_contradictions,
            trigger='cron',
            day_of_week='fri',
            hour=16,
            id='check_contradictions'
        )

        # Monthly: Review and suggest archiving
        self.scheduler.add_job(
            self.suggest_archival,
            trigger='cron',
            day=1,
            hour=10,
            id='suggest_archival'
        )
```

---

## Summary: Complete Goal Lifecycle System

### Detection Mechanisms

| Method | Detects | Frequency | Confidence |
|--------|---------|-----------|------------|
| **Explicit statements** | User says "I changed my mind" | Per message | 0.9 |
| **Journal analysis** | Stopped activity, contradictions | Daily | 0.7 |
| **Progress tracking** | Stalled progress | Weekly | 0.6 |
| **Target date** | Date passed | Daily | 1.0 |
| **Smart inference** | Combined signals | Weekly | 0.5 |

### Update Strategies

| Strategy | When | Example |
|----------|------|---------|
| **Auto-update** | High confidence (≥0.8) | User: "I finished it!" → Mark complete |
| **Confirm first** | Medium confidence (0.5-0.8) | Stalled for 30 days → Ask user |
| **Soft flag** | Low confidence (<0.5) | Slow progress → Mark for review |
| **Manual trigger** | User request | User: "Update my goals" |

### Lifecycle States

```
Planned → Active → Paused → Completed/Abandoned → Archived
   ↓         ↓        ↓              ↓             ↓
Created   Working   On hold    Done/gave up    Read-only
```

---

## Example Scenarios

### Scenario 1: Goal Completed

```
User: "I finally finished the dashboard!"

↓ Detection
Event: Explicit completion
Confidence: 0.9 (explicit statement)

↓ Action
System: "Congratulations! 🎉"
- Mark goal as completed (100%)
- Archive to history
- Ask: "What's next? Want to set a new goal?"
```

### Scenario 2: Goal Abandoned

```
[30 days pass]
[No journal entries mentioning goal]
[No progress updates]

↓ Detection
Event: Journal stagnation
Confidence: 0.7 (30 days inactivity)

↓ Action
System: "📊 Goal Status Check"
"Your goal 'Launch dashboard' hasn't seen activity in 30 days.
Should I:
- Pause this goal for now?
- Mark it as abandoned?
- Update the target date?"

User: "Yeah, I lost interest"
System: Marks as abandoned, archives
```

### Scenario 3: Goal Changed

```
User: "I want to focus on R instead of Python"

↓ Detection
Event: Explicit contradiction
Confidence: 0.8 (direct statement)

↓ Action
System: "I noticed you mentioned focusing on R instead of Python.
Should I:
- Archive 'Learn Python' goal?
- Create new 'Learn R' goal?
- Keep both active?"

User: "Yes, archive Python and create R goal"
System: Archives old, creates new
```

### Scenario 4: Target Date Missed

```
Target: March 31
Today: April 15
Progress: 60%

↓ Detection
Event: Target date passed (15 days overdue)
Confidence: 1.0 (objective fact)

↓ Action
System: "📅 Goal Reminder"
"Your goal 'Launch dashboard' was targeted for March 31
but it's now April 15 (60% complete).

Should I:
- Update target date to April 30?
- Mark as paused?
- Keep the original date (it's aspirational)?"
```

---

## Implementation Plan

### Phase 1: Core Detection (Week 1)

- ✅ Explicit statement detection
- ✅ Target date monitoring
- ✅ Basic progress tracking

### Phase 2: Journal Integration (Week 2)

- ✅ Stagnation detection from journal
- ✅ Contradiction detection
- ✅ Activity-based progress updates

### Phase 3: Confirmation Flows (Week 3)

- ✅ User confirmation dialogs
- ✅ Soft flagging system
- ✅ Smart inference engine

### Phase 4: Full Automation (Week 4)

- ✅ Automatic status updates
- ✅ Scheduled maintenance jobs
- ✅ Goal versioning system
- ✅ Conflict resolution

---

## Key Design Decisions

### 1. Never Delete - Always Archive

**Why**: Goals are valuable even if abandoned

```python
# Instead of deleting
goals.delete(goal_id)  # ❌ Don't do this

# Archive
goals.archive(goal_id)  # ✅ Keeps history
```

**Benefits**:
- User might want to resume later
- Historical data for patterns
- Learning what works/doesn't work

---

### 2. Progressive Verification

**Why**: Avoid false positives, respect user agency

```python
# Don't do this
if stagnation_detected:
    goals.abandon(goal_id)  # ❌ Too aggressive

# Do this instead
if stagnation_detected:
    goals.flag(goal_id, "review_needed")  # ✅ Soft approach
    ask_user_confirmation()  # ✅ User decides
```

---

### 3. Multi-Signal Confirmation

**Why**: Single signal can be wrong

```python
# Combine multiple signals
confidence = (
    explicit_statement * 0.5 +
    journal_contradiction * 0.3 +
    target_date_passed * 0.2
)

if confidence >= 0.7:
    # Update only when multiple signals agree
    update_goal()
else:
    # Monitor for additional signals
    monitor_goal()
```

---

### 4. User is Always in Control

**Why**: It's their goals, not the system's

```python
# Always offer options
"""
Your goal seems stalled:
- Keep it as is
- Pause it temporarily
- Update the target
- Abandon it

What would you prefer?
"""

# Never auto-abandon without confirmation
if not user_confirmed:
    keep_goal_active()
```

---

## Summary

### Detection: 5 Mechanisms

1. **Explicit statements** - User says "I changed my mind"
2. **Journal analysis** - No activity for 30 days
3. **Progress tracking** - Stalled at same % for weeks
4. **Target dates** - Date passed, goal incomplete
5. **Smart inference** - Combined signals

### Updates: 4 Strategies

1. **Auto-update** - High confidence (≥0.8)
2. **Confirm first** - Medium confidence (0.5-0.8)
3. **Soft flag** - Low confidence (<0.5)
4. **Manual trigger** - User request

### Lifecycle: 6 States

1. **Planned** → Created but not started
2. **Active** → Being worked on
3. **Paused** → Temporarily on hold
4. **Completed** → Successfully achieved 🎉
5. **Abandoned** → User lost interest
6. **Archived** → Read-only history

### Key Principles

✅ **Never delete** - Always archive for history
✅ **Progressive verification** - Multiple signals before action
✅ **User control** - Always offer options, never auto-abandon
✅ **Version tracking** - Keep history of all changes
✅ **Smart inference** - Combine signals for accuracy

**Goals system will gracefully handle change!** 🎯
