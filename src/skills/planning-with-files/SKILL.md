---
name: planning-with-files
description: Agent-internal Manus-style planning for complex tasks
---

# Planning Skill

Agent uses this skill internally for managing complex multi-step tasks.

## When Agent Activates

Agent MUST activate this skill when:
- User request has 3+ distinct steps
- Task involves research followed by implementation
- Task spans multiple tool calls/sessions
- User asks to "plan" something

## CRITICAL: Agent MUST Create Planning Files

When this skill is activated, the agent MUST immediately:

1. **Extract topic** from user request (e.g., "Japan trip" → `japan-trip`)
2. **Create planning directory** (relative to workspace):
   ```
   planning/{topic}/
   ├── task_plan.md
   ├── findings.md
   └── progress.md
   ```
3. **Write initial content** to each file

## Plan Name Extraction

| User Request | Plan Name |
|--------------|-----------|
| "Plan my Japan trip" | `japan-trip` |
| "Research AI news" | `research-ai-news` |
| "Build a todo app" | `build-todo-app` |

Rules:
- Lowercase only
- Spaces → hyphens
- Keep short and descriptive

## Agent Workflow (MUST FOLLOW)

1. **Extract topic** → `plan_name`
2. **Create directory**: `planning/{plan_name}/`
3. **Write task_plan.md** with phases:
   ```markdown
   # Task: {plan_name}

   ## Phases
   - [ ] Phase 1: Research
   - [ ] Phase 2: Planning
   - [ ] Phase 3: Implementation
   - [ ] Phase 4: Review

   ## User Request
   {exact user request}
   ```
4. **Write findings.md** (start empty or with research)
5. **Write progress.md** with log:
   ```markdown
   # Progress: {plan_name}

   ## Session Log
   - Started: {timestamp}
   
   ## Completed
   
   ## Errors
   
   ## Next Steps
   ```
6. **Update progress** after each step (checkboxes, new entries)
7. **Before each decision** → Re-read relevant file
8. **On error** → Log to progress.md
9. **On completion** → Mark all phases done

## Key Points

- MUST create actual files (not just talk about them)
- Use filesystem tools (write_file, read_file, etc.)
- Progress tracked via checkbox updates in task_plan.md
- Errors logged in progress.md
- Files enable session recovery

## Files Location

```
planning/{plan_name}/
├── task_plan.md   # Phase checklist
├── findings.md   # Research/data
└── progress.md   # Session logs
```
