# Planning

Description: Learn to break down tasks, estimate effort, create schedules, and plan projects effectively.

Tags: personal, planning, tasks, estimation, scheduling, projects

## Overview

Planning transforms vague goals into actionable steps. This skill covers:

1. **Task Breakdown** - Decompose goals into subtasks
2. **Effort Estimation** - Estimate time and resources
3. **Scheduling** - Create realistic timelines
4. **Risk Assessment** - Identify potential blockers

**Key Principle:** Good planning prevents surprises. Invest time upfront to save time later.

---

## ⚠️ Important: Agent Todos vs User Todos

**There are TWO types of todos - don't confuse them!**

### 1. Agent Todos (write_todos)
- **Purpose:** Track the agent's internal execution steps
- **Storage:** Ephemeral state during agent run (cleared after completion)
- **Example:** "Step 1: Search web", "Step 2: Create table", "Step 3: Insert data"
- **Tool:** `write_todos` (built-in LangChain tool)
- **When to use:** ONLY for tracking complex multi-step agent workflows

### 2. User Todos (TDB)
- **Purpose:** Store the user's personal tasks and todo lists
- **Storage:** Persistent TDB (SQLite) tables
- **Example:** "meert ZK", "create companies for Steve", "call mom"
- **Tools:** `create_tdb_table`, `insert_tdb_table`, `query_tdb_table`, `update_tdb_table`
- **When to use:** When the user asks to "track my todos", "add to my todo list", etc.

### Quick Decision Tree

```
User asks: "track my todos" or "add this to my todo list"
  ↓
Use TDB (create todos table, insert records)

Agent needs to track multi-step execution plan
  ↓
Use write_todos (shows progress to user)
```

### User Todo Pattern (TDB)

```python
# Create todos table
create_tdb_table(
    "todos",
    columns="task,status,priority,due_date,notes"
)

# Add user's todos
insert_tdb_table("todos", [
    {"task": "meert ZK", "status": "pending", "priority": "high"},
    {"task": "create companies for Steve", "status": "pending", "priority": "medium"}
])

# Query pending todos
query_tdb("SELECT * FROM todos WHERE status = 'pending' ORDER BY priority DESC")

# Mark as complete
update_tdb_table(
    "todos",
    '{"status": "completed"}',
    where="id = 1"
)
```

---

---

## Planning Framework

```
┌─────────────────────────────────────────────────────────────┐
│                      Planning Process                          │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐ │
│  │  Goal   │───▶│ Breakdown│───▶│ Estimate │───▶│Plan  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────┘ │
│       │              │               │            │      │
│       ▼              ▼               ▼            ▼      │
│  What         Subtasks         Time &        Schedule  │
│  Why          Dependencies     Resources     Milestones │
│  Success      Sequence         Complexity    Risks     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Define Goals

**Clear goals have:**
- **Specific outcome** - What exactly will be done?
- **Success criteria** - How will we know it's complete?
- **Constraints** - Time, budget, resources
- **Dependencies** - What must happen first?

### Goal Template

```python
# Create goals table
create_tdb_table(
    "goals",
    columns="title,description,success_criteria,deadline,priority,status"
)

# Add goal
insert_tdb_table(
    "goals",
    '[{"title": "Launch Website", "description": "Deploy company website with all features", "success_criteria": "All features work, performance benchmarks met", "deadline": "2025-03-31", "priority": "high", "status": "planning"}]'
)
```

---

## Step 2: Break Down Tasks

**Decompose goals into manageable subtasks.**

### Task Breakdown Patterns

**Hierarchical Breakdown:**
```python
# Main task
"Launch Website"
├── "Design homepage"
│   ├── "Create wireframes"
│   ├── "Design mockups"
│   └── "Get approval"
├── "Develop backend"
│   ├── "Set up transactional database"
│   ├── "Build API"
│   └── "Write tests"
└── "Develop frontend"
    ├── "Build components"
    ├── "Integrate API"
    └── "Deploy to production"
```

**Implement with TDB:**
```python
# Create tasks with hierarchy
create_tdb_table(
    "tasks",
    columns="title,parent_id,status,estimate,dependencies"
)

# Add subtasks
insert_tdb_table("tasks", [
    {"title": "Launch Website", "parent_id": null, "status": "in_progress"},
    {"title": "Design homepage", "parent_id": 1, "status": "pending"},
    {"title": "Create wireframes", "parent_id": 2, "status": "pending"},
    {"title": "Design mockups", "parent_id": 2, "status": "pending"}
])
```

---

## Step 3: Estimate Effort

**Estimate time, complexity, and resources.**

### Estimation Techniques

**Bottom-Up Estimation:**
```python
# Estimate each subtask
estimates = {
    "Create wireframes": 2,  # hours
    "Design mockups": 4,
    "Get approval": 1,
    "Set up transactional database": 3,
    "Build API": 16,
    "Write tests": 8,
    "Build components": 12,
    "Integrate API": 6,
    "Deploy to production": 2
}

total = sum(estimates.values())
buffer = total * 0.2  # 20% buffer
realistic_total = total + buffer

# Save estimates
create_tdb_table(
    "task_estimates",
    columns="task,estimate_hours,complexity,notes"
)
```

**Complexity Assessment:**
```python
# Rate complexity (1-5)
complexity = {
    "Create wireframes": 2,  # Low
    "Design mockups": 3,     # Medium
    "Build API": 5,          # High
    "Write tests": 4,        # Medium-High
    "Deploy": 3              # Medium
}
```

### Factors Affecting Estimates

- **Task familiarity** - Done before vs new
- **Dependencies** - Blocking vs independent
- **Resources** - Available vs need to acquire
- **Complexity** - Simple vs complex
- **Uncertainty** - Clear requirements vs vague

**Add buffers:**
- Low complexity: +10-20%
- Medium complexity: +20-30%
- High complexity: +30-50%

---

## Step 4: Schedule Tasks

**Create realistic timeline with milestones.**

### Scheduling Patterns

**Sequential Tasks:**
```python
# Tasks that depend on each other
create_tdb_table(
    "schedule",
    columns="task,start_date,end_date,predecessors"
)

insert_tdb_table("schedule", [
    {"task": "Create wireframes", "start_date": "2025-01-20", "end_date": "2025-01-21", "predecessors": ""},
    {"task": "Design mockups", "start_date": "2025-01-22", "end_date": "2025-01-25", "predecessors": "Create wireframes"},
    {"task": "Get approval", "start_date": "2025-01-26", "end_date": "2025-01-26", "predecessors": "Design mockups"}
])
```

**Parallel Tasks:**
```python
# Tasks that can happen simultaneously
parallel_tasks = [
    {"task": "Build backend API", "start": "2025-01-20", "end": "2025-02-05", "dependencies": ""},
    {"task": "Build frontend UI", "start": "2025-01-20", "end": "2025-02-03", "dependencies": ""}
]
# Can work on both at same time
```

**Milestone Scheduling:**
```python
# Define milestones
create_tdb_table(
    "milestones",
    columns="name,target_date,dependencies,status"
)

insert_tdb_table("milestones", [
    {"name": "Design Complete", "target_date": "2025-01-31", "dependencies": "", "status": "pending"},
    {"name": "Development Complete", "target_date": "2025-02-28", "dependencies": "Design Complete", "status": "pending"},
    {"name": "Testing Complete", "target_date": "2025-03-15", "dependencies": "Development Complete", "status": "pending"},
    {"name": "Launch", "target_date": "2025-03-31", "dependencies": "Testing Complete", "status": "pending"}
])
```

---

## Risk Assessment

**Identify potential problems and plan mitigations.**

### Risk Register

```python
create_tdb_table(
    "risks",
    columns="risk,probability,impact,mitigation,status"
)

insert_tdb_table("risks", [
    {"risk": "Scope creep", "probability": "high", "impact": "high", "mitigation": "Clear requirements, change control process", "status": "monitoring"},
    {"risk": "Technical challenges", "probability": "medium", "impact": "high", "mitigation": "Prototype early, research solutions", "status": "monitoring"},
    {"risk": "Resource constraints", "probability": "medium", "impact": "medium", "mitigation": "Buffer in estimates, prioritize tasks", "status": "accepted"}
])
```

### Risk Analysis

```python
# Calculate risk score
# Risk Score = Probability × Impact
for risk in risks:
    risk_score = risk['probability'] * risk['impact']
    if risk_score >= 9:  # High probability × High impact
        print(f"🔴 HIGH RISK: {risk['risk']}")
    elif risk_score >= 4:
        print(f"🟡 MEDIUM RISK: {risk['risk']}")
    else:
        print(f"🟢 LOW RISK: {risk['risk']}")
```

---

## Common Planning Scenarios

### Scenario 1: Software Project

```python
# Goal: Launch new feature
goal = "Launch user authentication feature"

# Breakdown
tasks = [
    {"task": "Design login UI", "estimate": 4, "dependencies": []},
    {"task": "Build auth API", "estimate": 12, "dependencies": []},
    {"task": "Implement OAuth", "estimate": 16, "dependencies": ["Build auth API"]},
    {"task": "Write tests", "estimate": 8, "dependencies": ["Implement OAuth"]},
    {"task": "Documentation", "estimate": 4, "dependencies": ["Implement OAuth"]}
]

# Schedule (parallel where possible)
schedule = [
    {"task": "Design login UI", "week": 1},
    {"task": "Build auth API", "week": "1-2"},
    {"task": "Implement OAuth", "week": "2-3"},
    {"task": "Write tests", "week": "3"},
    {"task": "Documentation", "week": "3"}
]
```

### Scenario 2: Learning Goal

```python
# Goal: Learn new technology
goal = "Learn LangGraph framework"

# Breakdown into phases
phases = [
    {"phase": "Basics", "tasks": ["Read docs", "Build hello world", "Understand concepts"], "weeks": 1},
    {"phase": "Intermediate", "tasks": ["Build multi-agent system", "Learn state management", "Implement tools"], "weeks": 2},
    {"phase": "Advanced", "tasks": ["Build production app", "Optimize performance", "Add testing"], "weeks": 2}
]

# Track progress
create_tdb_table(
    "learning_plan",
    columns="goal,phase,task,status,week_completed"
)
```

### Scenario 3: Event Planning

```python
# Goal: Organize conference
goal = "Team offsite conference"

# Breakdown by category
tasks_by_category = {
    "Venue": ["Research venues", "Get quotes", "Book location"],
    "Content": ["Plan agenda", "Invite speakers", "Prepare materials"],
    "Logistics": ["Arrange catering", "Setup A/V", "Send invitations"],
    "Follow-up": ["Collect feedback", "Share recordings", "Write summary"]
}

# Timeline
timeline = {
    "8 weeks before": "Research venues, set budget",
    "6 weeks before": "Book venue, invite speakers",
    "4 weeks before": "Plan agenda, prepare materials",
    "2 weeks before": "Send invitations, finalize logistics",
    "1 week before": "Final checklists, confirm arrangements",
    "Day of event": "Execute plan",
    "1 week after": "Collect feedback, send thank-yous"
}
```

---

## Planning Tools & Queries

### Task Queries

**Show task hierarchy:**
```python
# Recursive query to show task tree
query_tdb("""
    WITH RECURSIVE task_tree AS (
        SELECT title, id, parent_id, 1 as level
        FROM tasks
        WHERE parent_id IS NULL
        UNION ALL
        SELECT t.title, t.id, t.parent_id, tt.level + 1
        FROM tasks t
        INNER JOIN task_tree tt ON t.parent_id = tt.id
    )
    SELECT
        repeat('  ', level - 1) || title as task_tree
    FROM task_tree
    ORDER BY id
""")
```

**Find next tasks:**
```python
# Tasks ready to start (dependencies complete)
query_tdb("""
    SELECT t.title
    FROM tasks t
    WHERE t.status = 'pending'
    AND NOT EXISTS (
        SELECT 1 FROM task_dependencies td
        WHERE td.task_id = t.id
        AND td.depends_on NOT IN (
            SELECT id FROM tasks WHERE status = 'complete'
        )
    )
""")
```

**Critical path:**
```python
# Longest path through tasks
query_tdb("""
    WITH task_paths AS (
        SELECT
            title,
            estimate_hours,
            parent_id,
            estimate_hours as path_hours
        FROM tasks
    )
    SELECT title, path_hours
    FROM task_paths
    ORDER BY path_hours DESC
""")
```

### Progress Tracking

**Milestone progress:**
```python
query_tdb("""
    SELECT
        name,
        target_date,
        COUNT(CASE WHEN status = 'complete' THEN 1 END) * 100.0 / COUNT(*) as progress
    FROM milestones
    GROUP BY name, target_date
""")
```

---

## Best Practices

### ✅ DO

- **Break down tasks** - Until each is 1-3 days
- **Estimate realistically** - Add buffers for uncertainty
- **Identify dependencies** - What must come first?
- **Plan milestones** - Checkpoints along the way
- **Assess risks** - What could go wrong?
- **Track progress** - Update status regularly
- **Adjust plans** - Revise as needed
- **Document assumptions** - What are we assuming?

### ❌ DON'T

- **Don't plan in isolation** - Get input from others
- **Don't ignore dependencies** - Respect task sequence
- **Don't underestimate** - Be realistic, not optimistic
- **Don't skip risk assessment** - Identify blockers early
- **Don't set unrealistic deadlines** - Under-promise, over-deliver
- **Don't plan once and forget** - Plans change, update them
- **Don't forget buffers** - Leave time for surprises
- **Don't ignore constraints** - Work within limits

---

## Quick Reference

**Planning Steps:**
1. Define goal (what, why, success criteria)
2. Break down (subtasks, hierarchy)
3. Estimate (time, complexity, resources)
4. Schedule (timeline, milestones)
5. Assess risks (what could go wrong?)

**Task Breakdown:**
- Create tasks table with parent_id
- Break down until 1-3 days each
- Identify dependencies
- Sequence appropriately

**Estimation:**
- Bottom-up (sum subtasks)
- Add buffer (10-50% based on complexity)
- Consider familiarity, dependencies, uncertainty
- Document assumptions

**Scheduling:**
- Sequential vs parallel tasks
- Milestones as checkpoints
- Critical path analysis
- Buffer time for risks

**Tracking:**
- Update status regularly
- Monitor milestones
- Adjust for changes
- Communicate progress

---

## Summary

**Planning Process:**
1. **Define** - Clear goals with success criteria
2. **Break down** - Hierarchical task decomposition
3. **Estimate** - Realistic time with buffers
4. **Schedule** - Timeline with milestones
5. **Assess** - Identify and mitigate risks

**Good Planning:**
- Breaks down complex goals
- Sets realistic expectations
- Identifies dependencies
- Anticipates problems
- Enables tracking
- Supports decisions

**Tools:**
- TDB for task lists, estimates, schedules
- VDB for planning documents, research
- Files for saved plans, reports

**Remember:** Plans are guides, not guarantees. Update as you learn more.

Good planning prevents poor performance. Invest time upfront to save time later.
