# LangChain Skills - Research for Executive Assistant Implementation

**Source:** https://docs.langchain.com/oss/python/langchain/multi-agent/skills

## Overview

In the **skills** architecture, specialized capabilities are packaged as invokable "skills" that augment an agent's behavior. Skills are primarily prompt-driven specializations that an agent can invoke on-demand.

This pattern is conceptually identical to `llms.txt` (introduced by Jeremy Howard), which uses tool calling for progressive disclosure of documentation. The skills pattern applies the same approach to specialized prompts and domain knowledge rather than just documentation pages.

## Key Characteristics

1. **Prompt-driven specialization**: Skills are primarily defined by specialized prompts
2. **Progressive disclosure**: Skills become available based on context or user needs
3. **Team distribution**: Different teams can develop and maintain skills independently
4. **Lightweight composition**: Skills are simpler than full sub-agents

## When to Use Skills

Use the skills pattern when you want:
- A single agent with many possible specializations
- No need to enforce specific constraints between skills
- Different teams need to develop capabilities independently

Common examples:
- Coding assistants (skills for different languages or tasks)
- Knowledge bases (skills for different domains)
- Creative assistants (skills for different formats)

## How It Works

### Flow
1. Agent sees lightweight skill descriptions in system prompt
2. When a task requires specialized knowledge, agent calls `load_skill`
3. Full skill content is loaded into conversation as ToolMessage
4. Agent uses the specialized knowledge to complete the task

### Benefits of Progressive Disclosure

- **Reduces context usage** - load only the 2-3 skills needed for a task
- **Enables team autonomy** - different teams can develop specialized skills independently
- **Scales efficiently** - add dozens or hundreds of skills without overwhelming context
- **Simplifies conversation history** - single agent with one conversation thread

### Trade-offs

- **Latency**: Loading skills on-demand requires additional tool calls
- **Workflow control**: Basic implementations rely on prompting - you cannot enforce hard constraints like "always try skill A before skill B" without custom logic

## Basic Implementation Pattern

```python
from langchain.tools import tool
from langchain.agents import create_agent

@tool
def load_skill(skill_name: str) -> str:
    """Load a specialized skill prompt.

    Available skills:
    - write_sql: SQL query writing expert
    - review_legal_doc: Legal document reviewer

    Returns the skill's prompt and context.
    """
    # Load skill content from file/database
    ...

agent = create_agent(
    model="gpt-4o",
    tools=[load_skill],
    system_prompt=(
        "You are a helpful assistant. "
        "You have access to two skills: "
        "write_sql and review_legal_doc. "
        "Use load_skill to access them."
    ),
)
```

## Skill Middleware Pattern

```python
from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
from langchain.messages import SystemMessage
from typing import Callable

class SkillMiddleware(AgentMiddleware):
    """Middleware that injects skill descriptions into the system prompt."""

    tools = [load_skill]  # Register tools as class variable

    def __init__(self):
        # Build skills prompt from SKILLS list
        skills_list = []
        for skill in SKILLS:
            skills_list.append(
                f"- **{skill['name']}**: {skill['description']}"
            )
        self.skills_prompt = "\n".join(skills_list)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject skill descriptions into system prompt."""
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed information "
            "about handling a specific type of request."
        )

        # Append to system message
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        modified_request = request.override(system_message=new_system_message)
        return handler(modified_request)
```

## Extending the Pattern

### Dynamic Tool Registration
Combine progressive disclosure with state management to register new tools as skills load. For example, loading a "database_admin" skill could both add specialized context and register database-specific tools (backup, restore, migrate).

### Hierarchical Skills
Skills can define other skills in a tree structure, creating nested specializations. For instance, loading a "data_science" skill might make available sub-skills like "pandas_expert", "visualization", and "statistical_analysis".

## Implementation Variations

### Storage Backends
- **In-memory**: Fast access, no I/O overhead (requires redeployment for updates)
- **File system** (Claude Code): Skills as directories with files, discovered via file operations
- **Remote storage**: S3, databases, Notion, or APIs, fetched on-demand

### Skill Discovery
- **System prompt listing**: Descriptions in system prompt
- **File-based**: Scan directories (Claude Code approach)
- **Registry-based**: Query a skill registry service
- **Dynamic lookup**: List available skills via a tool call

### Progressive Disclosure Strategies
- **Single load**: Load entire skill content in one tool call
- **Paginated**: Load skill content in multiple pages/chunks
- **Search-based**: Search within skill content for relevant sections
- **Hierarchical**: Load overview first, then drill into subsections

### Size Considerations
- **Small skills** (< 1K tokens): Can be included directly in system prompt
- **Medium skills** (1-10K tokens): Benefit from on-demand loading
- **Large skills** (> 10K tokens): Should use progressive disclosure techniques

## Advanced: Constraints with Custom State

Track loaded skills and enforce tool constraints - certain tools only available after specific skills have been loaded.

```python
from langchain.agents.middleware import AgentState

class CustomState(AgentState):
    skills_loaded: NotRequired[list[str]]  # Track loaded skills

@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> Command:
    """Load skill and update state."""
    for skill in SKILLS:
        if skill["name"] == skill_name:
            return Command(
                update={
                    "messages": [ToolMessage(content=skill['content'], ...)],
                    "skills_loaded": [skill_name],
                }
            )

@tool
def write_sql_query(query: str, vertical: str, runtime: ToolRuntime) -> str:
    """Tool only usable after skill is loaded."""
    skills_loaded = runtime.state.get("skills_loaded", [])

    if vertical not in skills_loaded:
        return (
            f"Error: You must load the '{vertical}' skill first. "
            f"Use load_skill('{vertical}') to load the schema."
        )

    # Proceed with query...
```

## Combining with Few-Shot Prompting

Progressive disclosure is fundamentally a **context engineering technique**. You can combine it with dynamic few-shot prompting:

1. User asks: "Find customers who haven't ordered in 6 months"
2. Agent loads `sales_analytics` schema
3. Agent also loads 2-3 relevant example queries (via semantic search or tag-based lookup)
4. Agent writes query using both schema knowledge AND example patterns

## Relevant to Executive Assistant

For Executive Assistant's use case (too many tools, not proactive enough):

1. **Progressive disclosure** - Instead of exposing all 40+ tools upfront, group them into skills:
   - `timesheet_skill`: Exposes only DB tools needed for timesheet tracking
   - `file_management_skill`: Exposes file operations
   - `data_analysis_skill`: Exposes VS, DB, and Python tools

2. **Proactive behavior** - Skills should include instructions that guide the agent to:
   - Recognize user intent ("track my time" → load timesheet_skill)
   - Take initiative without waiting for explicit tool calls
   - Chain multiple tools to achieve the goal

3. **Skill definitions should be task-oriented** rather than tool-oriented:
   - Instead of: "Here are the DB tools you can use..."
   - Use: "For timesheet tracking: 1) Create timesheet table, 2) Add time entries, 3) Query for reports"

---

## Revised Analysis (Post-Documentation Review)

**Date:** 2025-01-18
**Reviewed:** Official LangChain Skills Documentation

After reviewing the official LangChain documentation (saved in `./doc/kb/`), my original analysis remains accurate with some important refinements:

### Confirmed Concepts

1. **TypedDict Skill Structure** - The official docs use `TypedDict` for type safety:
   ```python
   class Skill(TypedDict):
       name: str        # Unique identifier
       description: str  # 1-2 sentence description for system prompt
       content: str     # Full detailed instructions (loaded on-demand)
   ```

2. **content_blocks Approach** - The middleware uses `request.system_message.content_blocks` to append skills rather than modifying the system prompt string directly. This is the LangChain-recommended approach for structured message content.

3. **Middleware Tool Registration** - Tools are registered as class variables (`tools = [load_skill]`) on the middleware class, not passed separately. This is cleaner than the pattern I initially suggested.

### New Insights from Official Docs

4. **Size Considerations are More Specific**:
   - Small (< 1K tokens): Include in system prompt with caching
   - Medium (1-10K tokens): Use progressive disclosure
   - Large (> 10K tokens): Must use pagination/search/hierarchical loading

5. **Dynamic Tool Registration is Official Pattern** - The docs explicitly mention loading a skill could "register database-specific tools (backup, restore, migrate)" - confirming this is a valid extension, not just my idea.

6. **Hierarchical Skills are Explicitly Supported** - Skills can define sub-skills in a tree structure. This could be useful for Executive Assistant's complex tool ecosystem.

7. **Progressive Disclosure + Few-Shot Combination** - The docs show a concrete example of loading both schema AND example queries. This suggests Executive Assistant could load both tool instructions AND usage examples together.

### Minor Corrections

8. **content_blocks vs content** - The middleware uses `request.system_message.content_blocks` (a list), not `request.system_message.content` (a string). This is the LangChain structured content approach.

9. **request.override() Pattern** - The docs show using `request.override(system_message=new_system_message)` rather than modifying the request directly. This is the immutability-safe pattern.

### Implementation Recommendations for Executive Assistant

Based on the official docs, here's the refined implementation approach:

```python
from typing import TypedDict

class Skill(TypedDict):
    name: str
    description: str
    content: str

EXECUTIVE_ASSISTANT_SKILLS: list[Skill] = [
    {
        "name": "timesheet_tracking",
        "description": "Track work hours, manage timesheet entries, and generate time reports.",
        "content": """# Timesheet Tracking Skill

## When to Use
User wants to: track time, log hours, view timesheet reports, calculate billable hours.

## Available Tools
- db_create_table: Create timesheet table
- db_insert: Add time entries
- db_query: Generate reports

## Workflow
1. Check if timesheet table exists
2. If not, create with schema: date, project, hours, description
3. Insert entry
4. Confirm to user
""",
    },
    {
        "name": "knowledge_management",
        "description": "Search, store, and manage information in vector store and databases.",
        "content": """# Knowledge Management Skill

## When to Use
User wants to: save information, search knowledge base, retrieve documents.

## Available Tools
- vs_add: Store documents
- vs_query: Semantic search
- db_create_table: Create knowledge tables
- db_insert/query: CRUD operations

## Workflow
1. Determine if info is for VS (semantic) or DB (structured)
2. For VS: create collection, add documents
3. For DB: design schema, create table, insert data
4. Confirm storage location and retrieval method
""",
    },
]
```

The key difference from my original suggestion: skills are **task-oriented** with explicit workflows, not just tool groupings. This aligns with making Executive Assistant more proactive - the skill content tells the agent **what to do**, not just **what tools are available**.
