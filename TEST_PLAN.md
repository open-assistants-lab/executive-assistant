# Executive Assistant - Integration Test Plan

## Overview

This document defines the integration testing strategy for the Executive Assistant system, covering both HTTP and CLI channels.

---

## Implemented Features

| # | Feature | Type | Implementation |
|---|---------|------|----------------|
| 1 | Skills | Middleware + Tools | `SkillMiddleware` (before_agent), `load_skill`, `list_skills` tools |
| 2 | Filesystem | Tools | `read_file`, `write_file`, `edit_file`, `delete_file`, `list_files` |
| 3 | File Search | Tools | `glob_search`, `grep_search` (not web search) |
| 4 | Todo Tool | Tool | `write_todos` - for AGENT to plan its own tasks |
| 5 | Shell Tool | Tool | `run_shell` - restricted command execution |
| 6 | Memory System | Storage | SQLite + FTS5 + ChromaDB hybrid storage |
| 7 | Memory Tools | Tools | `get_conversation_history`, `search_conversation_hybrid` |
| 8 | Summarization | Middleware | `SummarizationMiddleware` - auto-summarizes at token threshold |
| 9 | TodoList Middleware | Middleware | `TodoListMiddleware` - auto-decomposes complex requests (COMPARISON PENDING) |
| 10 | Checkpoint | Storage | LangGraph `AsyncSqliteSaver` with 7-day retention |
| 11 | User Isolation | Architecture | Separate state per `user_id` via checkpointer/thread_id |

### Not Implemented / Removed
- ~~Firecrawl~~ - config exists but tool not implemented (skip for now)
- ~~Journal~~ - was unused dead config, now removed

---

## Technical Details

### 1. Skills System

**Implementation:**
- `SkillMiddleware` uses `before_agent` hook to inject skill descriptions into system prompt
- Skills stored as `SKILL.md` files with YAML frontmatter
- System skills: `src/skills/{skill_name}/SKILL.md`
- User skills: `data/users/{user_id}/skills/{skill_name}/SKILL.md`
- `load_skill` tool returns full content + updates `runtime.state.skills_loaded`

**Test Approach:** Natural language interaction to verify agent discovers/loads skills

### 2. Filesystem Tools

**Implementation:**
- Tools bound to user directory: `data/users/{user_id}/files/`
- File operations: read, write, edit, delete, list
- Max file size: 10MB (configurable)
- Delete requires HITL (Human-In-The-Loop) approval

**Test Approach:** Natural language to create/edit/manage files

### 3. File Search Tools

**Implementation:**
- `glob_search`: Find files by pattern (e.g., `*.py`, `**/*.json`)
- `grep_search`: Search file contents using regex

**Test Approach:** Natural language to find files

### 4. Todo Tool (`write_todos`)

**Purpose:** For the **AGENT** to track its own planning tasks, NOT for user task management

**Implementation:**
- Actions: list, add, update, delete, replace
- Status: pending, in_progress, completed
- Per-user storage (in-memory for current session)

**Test Approach:** Ask agent to "plan a trip" → agent uses todo internally

### 5. Shell Tool (`run_shell`)

**Implementation:**
- Allowed commands (after config change): `python3`, `node`, `echo`, `date`, `whoami`, `pwd`
- HITL commands: `rm`, `rmdir` (require approval)
- Timeout: 30 seconds
- Max output: 100KB

**Docker Recommendation:**
```dockerfile
# Base Python image already includes python3
FROM python:3.11-slim

# Pre-installed libraries (commonly used)
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    requests \
    beautifulsoup4 \
    lxml \
    openpyxl \
    python-docx \
    Pillow

# Node.js for node command
RUN apt-get update && apt-get install -y nodejs npm
```

**Test Approach:** Natural language to run commands

### 6. Memory System (Storage Layer)

**Architecture:**
```
data/users/{user_id}/.conversation/
├── messages.db       # SQLite with FTS5 for keyword search
└── vectors/         # ChromaDB for semantic search
```

**Components:**
1. **SQLite + FTS5**: Keyword search with BM25 ranking
2. **ChromaDB**: Vector embeddings for semantic search
3. **Hybrid Search**: Combined keyword + vector + recency scoring

**Test Approach:** Create messages → verify storage → search → verify results

### 7. Memory Tools

**Implementation:**
- `get_conversation_history(days=7)`: Get messages by time range
- `search_conversation_hybrid(query)`: Combined search

**Note:** When checkpointer retention = 0, agent relies ONLY on memory tools

**Test Approach:** Create conversation → query history → verify retrieval

### 8. Summarization Middleware

**Implementation:**
- `SummarizationMiddleware` from LangChain
- Trigger: 10,000 tokens (configurable)
- Keep: 10 recent messages
- Reduces token usage in long conversations

**Test Approach:** Send long conversation → verify summarization triggered

### 9. TodoList Middleware

**Purpose:** Decompose **COMPLEX USER REQUESTS** into subtasks automatically

**Implementation:**
- When user asks complex task (e.g., "plan a trip to Japan")
- Middleware automatically calls `write_todos` with subtasks
- Agent then executes subtasks sequentially

**Test Approach:** "Help me plan a trip to Japan" → verify subtasks created

### 10. Checkpoint System

**Implementation:**
- LangGraph `AsyncSqliteSaver` with SQLite backend
- Retention: 7 days (configurable)
- Path: `data/users/{user_id}/.conversation/checkpoints.db`
- Persists agent state (messages, tool outputs) across sessions

**Test Approach:** Send message → restart server → verify memory persists

### 11. User Isolation

**Implementation:**
- Each user has separate:
  - Files: `data/users/{user_id}/files/`
  - Skills: `data/users/{user_id}/skills/`
  - Checkpoint: Separate thread_id per user
  - Memory: Separate SQLite/ChromaDB per user

**Test Approach:** User A writes file → User B cannot read

---

## Test Configuration

### Config Updates Required

```yaml
# config.yaml changes needed:

# 1. Fix message storage extension (not duckdb)
memory:
  messages:
    path: "data/users/{user_id}/.conversation/messages.db"  # NOT .duckdb
  journal:
    path: "data/users/{user_id}/.conversation/journal.db"   # NOT .duckdb

# 2. Enable TodoList middleware
todo_list:
  enabled: true  # was false

# 3. Shell tool - python3 only (remove duplicate)
shell_tool:
  allowed_commands:
    - python3      # removed "python"
    - node
    - echo
    - date
    - whoami
    - pwd
```

### Checkpoint Retention for Memory Testing

Set `retention_days: 0` to test memory tool reliance:
```yaml
memory:
  checkpointer:
    retention_days: 0  # Agent must use memory tools
```

---

## Test Cases

### HTTP Channel: POST /message

| # | Feature | Test | Method | Expected Result |
|---|---------|------|--------|-----------------|
| 1.1 | Skills | List skills | "what skills do I have?" | Returns system + user skills |
| 1.2 | Skills | Load skill | "load sql-analytics skill" | Returns full skill content |
| 1.3 | Skills | Load user skill | "load my-custom-skill" | Returns user skill |
| 1.4 | Skills | Non-existent | "load unknown-skill" | Error + available list |
| 1.5 | Skills | Discovery | "how to extract PDF tables?" | Agent knows skill exists |
| 1.6 | Skills | Constrained tool (no skill) | "write SQL for inventory" | Error: load skill first |
| 1.7 | Skills | Constrained tool (with skill) | "load sql then write query" | Works |
| 1.8 | Skills | User isolation | Different user_id | Different skills shown |
| 1.9 | Skills | New skill | Add skill file, ask list | New skill appears |
| 1.10 | Skills | Natural load | "I need help with SQL" | Agent loads skill |

| 2.1 | Filesystem | List files | "what files do I have?" | File list |
| 2.2 | Filesystem | Read file | "read hello.txt" | File content |
| 2.3 | Filesystem | Write file | "create a file called test.txt with hello world" | File created |
| 2.4 | Filesystem | Edit file | "change test.txt to say hi instead" | File modified |
| 2.5 | Filesystem | Delete file | "delete test.txt" | File deleted |
| 2.6 | Filesystem | Nested path | "create folder/subfolder/file.txt" | Nested created |
| 2.7 | Filesystem | Read missing | "read missing.txt" | Error message |
| 2.8 | Filesystem | Overwrite | "update test.txt with new content" | Overwritten |
| 2.9 | Filesystem | User isolation | User A writes, User B reads | No access |
| 2.10 | Filesystem | Natural create | "please create a notes.txt for me" | File created |

| 3.1 | File Search | Glob py | "find all Python files" | .py files |
| 3.2 | File Search | Glob pattern | "find all JSON files" | .json files |
| 3.3 | File Search | Grep keyword | "search for function definition" | Matches |
| 3.4 | File Search | Grep regex | "find test followed by word" | Regex matches |
| 3.5 | File Search | Empty | "search for xyz123" | No results |
| 3.6 | File Search | Natural | "where is the main function?" | Finds file |

| 4.1 | Todo Tool | Agent planning | "plan a trip to Japan" | Agent uses todo internally |
| 4.2 | Todo Tool | List | "show my tasks" | Agent shows its tasks |
| 4.3 | Todo Tool | User confusion | "add my todo: buy milk" | Agent clarifies purpose |

Note: Todo Tool is for AGENT task planning, NOT user task management

| 5.1 | Shell | Echo | "run echo hello" | Returns "hello" |
| 5.2 | Shell | Python3 | "run python3 -c 'print(1+1)'" | Returns "2" |
| 5.3 | Shell | Node | "run node -e 'console.log(9)'" | Returns "9" |
| 5.4 | Shell | Date | "what's the current date?" | Returns date |
| 5.5 | Shell | Whoami | "who am I?" | Returns user |
| 5.6 | Shell | Disallowed | "run ls" | Error: not allowed |
| 5.7 | Shell | Timeout | "run sleep 60" | Timeout error |
| 5.8 | Shell | Natural | "check the current directory" | Returns pwd |

| 6.1 | Memory Storage | SQLite exists | Check messages.db | File created |
| 6.2 | Memory Storage | FTS5 table | Verify FTS5 | Table exists |
| 6.3 | Memory Storage | ChromaDB | Check vectors/ | Directory created |
| 6.4 | Memory Storage | Message insert | Create message | In DB |
| 6.5 | Memory Storage | Keyword search | FTS5 search | Returns results |
| 6.6 | Memory Storage | Vector search | Semantic search | Returns results |
| 6.7 | Memory Storage | Hybrid | Combined search | Returns results |
| 6.8 | Memory Storage | Count | Count messages | Returns count |

| 7.1 | Memory Tools | History | "what did I tell you before?" | Returns history |
| 7.2 | Memory Tools | Date filter | "what did I say last week?" | Filtered |
| 7.3 | Memory Tools | Search | "find my message about python" | Returns matches |
| 7.4 | Memory Tools | New user | "what did I tell you?" (new) | No messages |
| 7.5 | Memory Tools | Empty search | "search xyz123" | No results |
| 7.6 | Memory Tools | Score | Check scores | Relevance shown |

| 8.1 | Summarization | Config | Check enabled | true |
| 8.2 | Summarization | Trigger | ~10000 tokens | Summarizes |
| 8.3 | Summarization | Keep messages | After summarize | 10 kept |
| 8.4 | Summarization | Quality | Check summary | Coherent |

| 9.1 | TodoList Middleware | **PENDING COMPARISON** | See TodoList vs write_todos comparison below |

**TodoList vs write_todos Comparison (COMPLETED)**

## Test Results

### Test: Complex Task - "Create a Python script that fetches data from an API and saves it to CSV"

#### Approach A: write_todos Tool (Custom)
| # | Criteria | Result | Notes |
|---|----------|--------|-------|
| T1 | Initial Decomposition | ✅ YES | Created 4 subtasks when explicitly asked |
| T2 | Progressive Update | ✅ YES | Updated to ✅ completed after each step |
| T3 | New Discovery | ❌ NO | Didn't add new tasks mid-way |
| T4 | Completion Tracking | ✅ YES | All marked completed |
| T5 | Final Review | ✅ YES | Showed todo list with strikethrough |

**Score: 80/100** - Works when explicitly asked, follows through

**Additional Test - Follow Through:**
- ✅ Created step1.txt, step2.txt, step3.txt as planned
- ✅ Updated todo list after each completion
- ✅ Final state showed all tasks completed

#### Approach B: TodoList Middleware (LangChain)
| # | Criteria | Result | Notes |
|---|----------|--------|-------|
| T1 | Initial Decomposition | ❌ NO | Too conservative - didn't auto-create |
| T2 | Progressive Update | ✅ YES | Updated when explicitly used |
| T3 | New Discovery | ❌ NO | No auto-creation |
| T4 | Completion Tracking | ✅ YES | Shows completed when used |
| T5 | Final Review | ✅ YES | Shows list |

**Score: 40/100** - Only works when explicitly prompted, doesn't auto-decompose

**Additional Test - Follow Through:**
- ✅ Created files when explicitly asked
- ✅ Updated todo list
- ❌ Didn't create initial todo automatically

---

## Conclusion

| Aspect | write_todos | TodoList Middleware |
|--------|-------------|-------------------|
| **Initial Decomposition** | ✅ Only when asked | ❌ Too conservative |
| **Progressive Update** | ❌ Not automatic | N/A |
| **User Control** | ✅ Full control | ❌ No control |
| **Integration** | ✅ Already in system | ✅ Built-in |
| **Customization** | ✅ Full | Limited |

### Verdict

**Neither is perfect.** 

- `write_todos` requires explicit prompting but works when asked
- `TodoListMiddleware` is too conservative - treats most tasks as "simple"

### Recommendation

1. **Keep write_todos** - More reliable for task decomposition
2. **Improve prompt** - Add system prompt to encourage todo usage
3. **Consider alternative** - May need custom implementation for progressive task tracking

**Next Step:** Update agent system prompt to encourage write_todos usage for complex tasks

| 10.1 | Checkpoint | File exists | Check checkpoints.db | Created |
| 10.2 | Checkpoint | Session persist | Message, new request | Remembers |
| 10.3 | Checkpoint | Restart | Restart, ask | Remembers |
| 10.4 | Checkpoint | Thread | Different thread_id | Separate |

| 11.1 | User Isolation | Files | User A writes, B reads | No access |
| 11.2 | User Isolation | Todos | A creates, B lists | Different |
| 11.3 | User Isolation | History | A chats, B chats | Separate |
| 11.4 | User Isolation | Skills | A adds, B lists | Different |

### CLI Channel

Same tests via `ea cli` command interface.

---

## Test Execution Notes

### Natural Language Requirement
Tests MUST use natural language, not:
- ❌ "list_skills tool"
- ✅ "what skills do I have?"

### Limitation Acknowledged
- Current tests use simplified natural language
- Full testing would require diverse phrasings
- Agent may interpret questions differently than expected

---

## Todo Mechanism - VERIFIED WORKING ✅

### Evidence from Logs
```
write_todos.called: {"action": "replace", "user_id": "testhttp1", "todos_count": 3}
write_todos.called: {"action": "replace", "user_id": "testhttp3", "todos_count": 5}
write_todos.called: {"action": "replace", "user_id": "testhttp7", "todos_count": 4}
```

### HTTP Response Fix Applied
Fixed message extraction in `src/http/main.py` to properly extract AI response (skip tool messages).

### Test Results
- Explicit "create todo list for..." → ✅ Shows todo in response
- Complex tasks without explicit → ✅ Agent uses todo internally (proven via logs)
- Files created → ✅ Agent follows through

### Key Finding
The agent DOES use write_todos for complex tasks - verified via logs. The HTTP response fix ensures it's displayed to users.

### TodoList Middleware
- REMOVED from codebase (was unnecessary)
- Custom write_todos tool is sufficient

### TodoList Middleware System Prompt (from LangChain)
```
## `write_todos`

You have access to the `write_todos` tool to help you manage and plan complex objectives.
Use this tool for complex objectives to ensure that you are tracking each necessary step and giving the user visibility into your progress.
This tool is very helpful for planning complex objectives, and for breaking down these larger complex objectives into smaller steps.

It is critical that you mark todos as completed as soon as you are done with a step. Do not batch up multiple steps before marking them as completed.
For simple objectives that only require a few steps, it is better to just complete the objective directly and NOT use this tool.
Writing todos takes time and tokens, use it when it is helpful for managing complex many-step problems! But not for simple few-step requests.

## Important To-Do List Usage Notes to Remember
- The `write_todos` tool should never be called multiple times in parallel.
- Don't be afraid to revise the To-Do list as you go. New information may reveal new tasks that need to be done, or old tasks that are irrelevant.
```

### Test Results: 10 Complex Requests

| Scenario | Configuration | Triggered | Notes |
|----------|--------------|-----------|-------|
| **A** | TodoList Middleware ON | 0/10 | Treats all as "simple" |
| **B** | Manual Prompt | 0/10 | Same as A |

### Key Finding

**Neither triggers automatically.** The agent considers these tasks "simple" enough to complete directly.

### Explicit Request Test

When explicitly asked: "Create a todo list for: [tasks]" → ✅ Works

---

## Test 2: Higher Complexity (Vague Requirements)

### Test Design

The goal is to find what complexity LEVEL triggers todo usage. We test with:
- Vague requirements (no steps specified)
- Multiple ambiguous goals
- Open-ended requests
- Unclear scope

### Test Tasks (10 Vague/Complex Requests)

| # | Task | Complexity Level |
|---|------|-----------------|
| 1 | "Help me organize my entire digital life" | Very High - vague |
| 2 | "I need to migrate my data from old system to new one" | High - unknown scope |
| 3 | "Build something that helps me track everything I do" | High - self-referential |
| 4 | "Create a complete solution for my business" | Very High - undefined |
| 5 | "Make my workflow automated" | High - no specifics |
| 6 | "I have a mess of files everywhere, fix it" | High - undefined scope |
| 7 | "Build me a system that handles all my recurring tasks" | High - open-ended |
| 8 | "Help me understand and optimize my entire codebase" | Very High - massive |
| 9 | "Create a comprehensive reporting system" | High - undefined data |
| 10 | "Build an everything manager for my life" | Very High - unbounded |

### Expected
These should trigger todo usage due to:
- No clear steps
- Unknown scope
- Multiple undefined components
- "Entire", "complete", "everything" keywords

### Test Results

| Test Type | Tasks | Triggered |
|-----------|-------|----------|
| Standard Complex | 10 | 0/10 |
| Vague/High Complexity | 10 | 0/10 |
| Extreme Complexity | - | Timeout |

---

## Final Conclusion

### What Triggers write_todos?

**Only explicit request triggers:**
- ❌ Complex multi-step tasks
- ❌ Vague/open-ended requirements
- ❌ "Entire", "complete", "everything" keywords
- ✅ Explicit: "Create a todo list for..."

### Agent Behavior

The agent decides tasks are "simple enough" to complete directly, regardless of:
- Number of steps implied
- Vagueness of requirements
- Scope keywords

### Recommendation

1. **Keep write_todos** - works when explicitly requested
2. **No middleware advantage** - both behave identically
3. **Consider custom implementation** - if auto-decomposition is critical, need custom middleware that:
   - Detects task complexity programmatically
   - Forces todo creation based on heuristics
   - Or uses different prompting strategy

---

## Baseline Summary

| Scenario | Trigger Rate |
|----------|-------------|
| Explicit "create todo list" | ✅ 100% |
| Complex but defined | ❌ 0% |
| Vague/high complexity | ❌ 0% |
| Extreme/unbounded | Timeout/error |

---

## Final Verdict

| Aspect | write_todos | TodoList Middleware |
|--------|-------------|-------------------|
| Auto-trigger | ❌ 0/10 | ❌ 0/10 |
| Explicit trigger | ✅ Works | ✅ Works |
| Follow through | ✅ Yes | ✅ Yes |

**Conclusion:** Both behave identically. The agent decides what is "complex" vs "simple" - neither approach triggers automatically for the tested tasks.

**Recommendation:** Keep write_todos (simpler), but user must explicitly ask for todo list.
