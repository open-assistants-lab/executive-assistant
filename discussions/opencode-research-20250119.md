# OpenCode Research - Agent Architecture Insights

**Date:** 2025-01-19
**Author:** Claude (Sonnet 4.5)
**Status:** Research Complete
**Purpose:** Draw inspiration from OpenCode for improving Executive Assistant's day-to-day activity specialization

---

## Executive Summary

**OpenCode** is an open-source AI coding agent (77.3k GitHub stars) built with TypeScript/Bun. While focused on code, their architecture provides excellent patterns for building **general-purpose AI agents** specialized in day-to-day activities.

**Key Takeaway:** OpenCode's strength lies in its **modular tool architecture**, **clear agent modes**, and **detailed tool descriptions** that guide the LLM on when/how to use each tool effectively.

---

## Architecture Overview

### Technology Stack
- **Runtime:** Bun (fast JavaScript runtime)
- **Language:** TypeScript with ESM modules
- **Validation:** Zod schemas
- **Architecture:** Client/Server (TUI frontend + backend server)
- **License:** MIT

### Directory Structure (Key Components)

```
packages/opencode/src/
├── agent/          # Agent implementation, prompts
├── tool/           # Individual tools (bash, read, write, etc.)
├── session/        # Session management
├── storage/        # Persistence layer
├── lsp/            # Language Server Protocol integration
├── shell/          # Shell command execution
├── scheduler/      # Background task scheduling
├── permission/     # Permission system
└── server/         # API server (communicates with TUI via SDK)
```

---

## Agent Modes (Critical Innovation)

OpenCode implements **distinct agent personalities** with different capabilities:

### 1. **build** Mode (Default)
- **Full access** agent for development work
- Can edit files, run commands, make changes
- No permission prompts for destructive operations
- Use case: Active development, implementing features

### 2. **plan** Mode (Read-Only)
- **Read-only** agent for analysis and exploration
- **Denies file edits by default**
- **Asks permission before running bash commands**
- Ideal for:
  - Exploring unfamiliar codebases
  - Planning changes before implementing
  - Code review and analysis
  - Understanding architecture

### 3. **general** Subagent
- Used internally for complex searches and multi-step tasks
- Can be invoked via `@general` in messages
- Handles tasks requiring multiple tool calls

**Why This Matters for Executive Assistant:**
- Different tasks require different permission levels
- Users want to explore without making accidental changes
- Planning mode builds trust by being explicit about permissions

---

## Tool Architecture

### Tool Pattern

Each tool consists of **two files**:

1. **`tool.ts`** - Implementation (TypeScript)
   - Implements `Tool.Info` interface
   - Has `execute()` method
   - Uses Zod schemas for input validation

2. **`tool.txt`** - Description/Prompt (Markdown)
   - **Detailed description** of what the tool does
   - **Usage guidelines** and best practices
   - **When to use** vs when not to use
   - **Example patterns**

### Example: `read.txt`

```markdown
Reads a file from the local filesystem. You can access any file directly by using this tool.

Usage:
- The filePath parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files)
- You have the capability to call multiple tools in a single response.
  It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive a system reminder warning.
```

**Key Insight:** The `.txt` file isn't just documentation - it's **part of the prompt** sent to the LLM, guiding it on proper tool usage.

---

## Available Tools (Day-to-Day Activities)

### File Operations
- **read.ts** - Read files (supports images, PDFs)
- **write.ts** - Write files
- **edit.ts** - Edit files (search and replace)
- **multiedit.ts** - Edit multiple locations in one operation
- **ls.ts** - List directory contents
- **glob.ts** - Find files by pattern

### Search & Discovery
- **grep.ts** - Search file contents
- **codesearch.ts** - Semantic code search
- **glob.ts** - Find files by pattern

### Command Execution
- **bash.ts** - Execute bash commands
- **pty.ts** - Interactive terminal sessions

### Planning & Task Management
- **plan.ts** - Enter/exit planning mode
- **todo.ts** - Todo list management
- **task.ts** - Delegate complex tasks to subagent
- **question.ts** - Ask user for input

### Web Access
- **websearch.ts** - Search the web
- **webfetch.ts** - Fetch web pages

### Code Intelligence
- **lsp.ts** - LSP integration (code completion, definitions, references)

### Permissions & Safety
- **plan-enter.txt / plan-exit.txt** - Transition between modes
- **permission/** - Permission system for dangerous operations

---

## Key Architectural Patterns

### 1. **Separation of Tool Implementation and Description**

```typescript
// read.ts - Implementation
export const read: Tool.Info = {
  name: "read",
  description: "Reads a file from the local filesystem",
  input: z.object({
    filePath: z.string(),
    offset: z.number().optional(),
    limit: z.number().optional(),
  }),
  execute: async (input, context) => {
    // Implementation
  }
}
```

```markdown
<!-- read.txt - Prompt Description -->
Reads a file from the local filesystem. You can access any file directly...

Usage:
- Use absolute paths, not relative paths
- Read multiple files in parallel when possible
- ...
```

**Benefit:** Clear separation, easy to update prompts without changing code.

### 2. **Zod Schema Validation**

All tool inputs validated with Zod schemas:
```typescript
input: z.object({
  filePath: z.string(),
  offset: z.number().optional(),
  limit: z.number().optional(),
})
```

**Benefit:** Type safety, clear error messages before LLM makes mistakes.

### 3. **Namespace-Based Organization**

```typescript
Tool.define(...)
Session.create(...)
Storage.set(...)
Log.create(...)
```

**Benefit:** Clear API boundaries, easier to understand codebase.

### 4. **Result Pattern (No Exceptions)**

Tools return `Result` types instead of throwing exceptions:
```typescript
return Result.ok(data)
return Result.err(error)
```

**Benefit:** Graceful error handling, agent can recover from failures.

### 5. **Detailed Tool Descriptions**

Each tool's `.txt` file includes:
- **What it does** - Clear description
- **When to use** - Usage scenarios
- **Best practices** - How to use effectively
- **Common mistakes** - What to avoid
- **Examples** - Concrete usage patterns

**Example from bash.txt:**
> Execute bash commands. Use this tool when you need to run terminal commands, install packages, or interact with the system.
>
> **Important:** Always use absolute paths. Check command exit codes.

---

## Agent Prompt Engineering

### Prompt Structure

From `src/agent/prompt/`:
- **System prompt** - Core agent behavior
- **Mode-specific prompts** - Different prompts for build vs plan mode
- **Tool descriptions** - `.txt` files injected into prompt
- **Few-shot examples** - Demonstrations of correct usage

### Planning Mode Integration

OpenCode's **plan mode** is particularly innovative:
- Switches to read-only agent
- Injects permission prompts before dangerous operations
- Asks user: "This will edit 3 files. Proceed?"
- Builds trust by being explicit about intentions

---

## Comparison with Executive Assistant

| Aspect | OpenCode | Executive Assistant (Current) |
|--------|----------|------------------|
| **Agent Modes** | build (full), plan (read-only) | Single agent mode |
| **Tool Descriptions** | Separate `.txt` files with detailed prompts | Inline docstrings |
| **Permission Model** | Explicit prompts in plan mode | No permission prompts |
| **Tool Organization** | Namespace-based (Tool.define) | Functional (get_vs_tools, etc.) |
| **Error Handling** | Result pattern (no exceptions) | Mix of exceptions and returns |
| **Validation** | Zod schemas before execution | Basic Pydantic validation |
| **Specialization** | Coding-focused, but general-purpose | Day-to-day activities |

---

## Inspiration for Executive Assistant

### 1. **Add Agent Modes**

```python
# src/executive_assistant/agent/modes.py

class AgentMode(Enum):
    """Agent operational modes."""
    FULL = "full"       # Full access (current behavior)
    PLAN = "plan"       # Read-only exploration
    SAFE = "safe"       # Limited permissions, explicit confirmations

class AgentModeManager:
    """Manage agent mode transitions."""

    def get_mode(self) -> AgentMode:
        """Get current agent mode."""
        return self._mode

    def set_mode(self, mode: AgentMode):
        """Switch agent mode."""
        # Inject mode-specific prompts
        # Update tool permissions
        pass
```

**Benefits:**
- Users can explore without accidental changes
- Builds trust for new users
- Explicit confirmations for destructive operations

### 2. **Separate Tool Descriptions from Implementation**

**Current (Executive Assistant):**
```python
@tool
def read_file(file_path: str) -> str:
    """Read a file from the local filesystem."""
    # Implementation
```

**Inspired by OpenCode:**
```python
# src/executive_assistant/tools/read.py
@tool
def read_file(file_path: str) -> str:
    """Read a file from the local filesystem."""
    # Implementation

# src/executive_assistant/tools/descriptions/read.txt
"""
Reads a file from the local filesystem. You can access any file directly.

Usage:
- Use absolute paths, not relative paths
- Read multiple files in parallel when possible
- Supports text, images, and PDFs
- Returns up to 2000 lines by default
- Use offset/limit for large files

Best Practices:
- Always prefer reading multiple files in batch
- Check if file exists before reading (error handling)
- Use glob_files to find files first if path is uncertain
"""
```

**Benefits:**
- More detailed guidance for LLM
- Easier to update prompts without code changes
- Can include examples and anti-patterns

### 3. **Add Transition Tools**

```python
# src/executive_assistant/tools/mode_transitions.py

@tool
def enter_plan_mode():
    """Enter read-only planning mode.

    In plan mode:
    - All file edits require confirmation
    - Bash commands require permission
    - Ideal for exploring unfamiliar codebases
    - Builds trust by being explicit about changes
    """
    current_mode = AgentMode.PLAN
    return "Entered plan mode. All modifications will require confirmation."

@tool
def exit_plan_mode():
    """Exit planning mode and return to full access mode."""
    current_mode = AgentMode.FULL
    return "Exited plan mode. Full access restored."
```

### 4. **Improve Tool Descriptions**

**Current todo tool:**
```python
def write_todos(todos: list[dict]) -> str:
    """Write todo list to track task progress."""
```

**Improved (OpenCode-style):**
```python
# todos.txt
"""
Write a todo list to track task progress.

When to use:
- Tasks with 3+ steps
- Multi-step research or implementation
- Complex workflows requiring tracking
- NOT for simple Q&A or single operations

Status values:
- pending: Not started
- in_progress: Currently working on
- completed: Finished successfully

Best practices:
- Always mark tasks as in_progress when starting
- Mark tasks as completed immediately after finishing
- Keep tasks focused and actionable
- Break large tasks into smaller sub-tasks

Example:
    write_todos([{
        "content": "Implement email channel",
        "status": "in_progress",
        "activeForm": "Implementing email channel"
    }])
"""
```

### 5. **Add Tool Usage Heuristics**

OpenCode includes explicit guidance on **when to use each tool**:

```markdown
**Tool Selection Heuristics:**
- Group/User db → temporary data during conversation
- Vector Store → persistent facts across conversations
- Todo list → complex tasks (3+ steps, multi-turn)
- OCR → extract text from images/PDFs
```

**For Executive Assistant, add to system prompt:**
```python
def _get_tool_heuristics() -> str:
    return """
**Tool Selection Heuristics:**
- *read_file* → Understand code, check implementations
- *write_file* → Create new files, update configs
- *search_web* → Current information, research
- *create_db_table* → Temporary data during analysis
- *create_vs_collection* → Persistent knowledge across sessions
- *write_todos* → Track 3+ step tasks only
- *execute_python* → Calculations, data processing

**Combining Tools:**
- Example: Research → search_web + create_db_table + write_file(summary)
- Example: Compare products → search_web + ocr + create_db_table + query_db
- Example: Track habits → create_db_table + insert_db_table + query_db
"""
```

### 6. **Parallel Tool Execution**

OpenCode emphasizes parallel tool calls:

```markdown
You have the capability to call multiple tools in a single response.
It is always better to speculatively read multiple files as a batch.
```

**For Executive Assistant:**
- Add to system prompt: "When multiple independent tools are needed, call them in parallel"
- Example: Read multiple files at once instead of sequentially
- LangGraph's parallel execution already supports this

### 7. **Permission Prompts for Destructive Operations**

```python
# src/executive_assistant/tools/confirmation_tool.py

@tool
def confirm_destructive_operation(operation: str, details: str) -> bool:
    """Ask user for confirmation before destructive operation.

    Args:
        operation: Description of operation (e.g., "delete 5 files")
        details: Specific details about what will be affected

    Returns:
        True if user confirms, False otherwise

    When to use:
    - Before deleting files/folders
    - Before dropping database tables
    - Before dropping vector store collections
    - Before any operation that loses data
    """
    # Ask user via channel (Telegram, HTTP, etc.)
    pass
```

### 8. **Add "General" Subagent for Complex Tasks**

OpenCode has a `@general` subagent for complex searches:

```python
# src/executive_assistant/agent/subagents.py

class GeneralSubagent:
    """Handle complex multi-step tasks."""

    async def handle_complex_task(self, task: str) -> str:
        """
        Delegate complex tasks to specialized subagent.

        When to use:
        - Multi-step research requiring multiple searches
        - Tasks requiring synthesis of multiple sources
        - Complex analysis across multiple files

        The subagent has access to all tools and can reason
        through complex workflows step by step.
        """
        # Invoke agent with specialized prompt
        pass
```

---

## Specific Tool Ideas from OpenCode

### 1. **codesearch.ts → semantic_search**

OpenCode has semantic code search via `codesearch.ts`. Executive Assistant could add:
```python
@tool
def semantic_search(query: str, scope: str = "codebase") -> list[dict]:
    """Search codebase semantically (not just keyword match).

    Finds code related to concepts, not just exact string matches.
    Uses embeddings for semantic understanding.

    Example:
        semantic_search("authentication logic") → Finds auth-related files
        semantic_search("error handling") → Finds error patterns
    """
```

### 2. **multiedit.ts → batch_edit**

Edit multiple files in one operation:
```python
@tool
def batch_edit(edits: list[dict]) -> dict:
    """Edit multiple files in a single operation.

    More efficient than multiple write_file calls.
    Atomic - either all succeed or all fail.

    Args:
        edits: List of {file_path, old_string, new_string}

    When to use:
    - Refactoring across multiple files
    - Updating imports across codebase
    - Consistent changes to related files
    """
```

### 3. **external-directory.ts → workspace management**

Manage multiple project directories:
```python
@tool
def add_workspace(path: str, name: str) -> str:
    """Add a workspace directory to monitor.

    Allows agent to work across multiple projects.

    When to use:
    - Working on monorepo with multiple packages
    - Need to reference code in different projects
    - Comparing implementations across repos
    """
```

---

## Implementation Roadmap for Executive Assistant

### Phase 1: Agent Modes (Week 1)
1. Implement `AgentMode` enum (FULL, PLAN, SAFE)
2. Add `enter_plan_mode` and `exit_plan_mode` tools
3. Update system prompt based on current mode
4. Add permission prompts for destructive ops in PLAN mode

### Phase 2: Tool Descriptions (Week 2)
1. Create `src/executive_assistant/tools/descriptions/` directory
2. Extract detailed descriptions from existing tools
3. Add usage guidelines, best practices, examples
4. Inject descriptions into tool definitions

### Phase 3: Improved Heuristics (Week 3)
1. Add tool selection heuristics to system prompt
2. Document when to use each tool category
3. Add examples of tool combinations
4. Include anti-patterns (what NOT to do)

### Phase 4: Advanced Tools (Week 4)
1. Implement `semantic_search` (if not already present)
2. Add `batch_edit` for atomic multi-file edits
3. Implement `general` subagent delegation
4. Add workspace management tools

---

## Open Code References

**Repository:** https://github.com/anomalyco/opencode
**Website:** https://opencode.ai
**License:** MIT

**Key Files to Study:**
- `packages/opencode/src/agent/agent.ts` - Agent implementation
- `packages/opencode/src/tool/*.ts` - Tool implementations
- `packages/opencode/src/tool/*.txt` - Tool descriptions (prompts)
- `packages/opencode/src/agent/prompt/` - System prompts

**Documentation:** https://opencode.ai/docs

---

## Summary

**OpenCode's Key Innovations for Day-to-Day Activities:**

1. **Agent Modes** - Different permission levels for different use cases
2. **Detailed Tool Descriptions** - Separate files guiding LLM on proper usage
3. **Permission Prompts** - Explicit confirmations build trust
4. **Tool Heuristics** - Clear guidance on when to use each tool
5. **Parallel Execution** - Encourage batch operations for efficiency
6. **Subagent Delegation** - Specialized agents for complex tasks

**What Executive Assistant Should Adopt:**

✅ **High Priority:**
- Agent modes (PLAN vs FULL)
- Detailed tool descriptions with best practices
- Permission prompts for destructive operations
- Tool selection heuristics in system prompt

✅ **Medium Priority:**
- Parallel tool execution guidance
- General subagent for complex tasks
- Improved error messages and recovery

⚠️ **Lower Priority:**
- Semantic code search (already have vector store)
- Batch edit operations (nice to have)
- Workspace management (advanced use case)

---

**End of Document**
