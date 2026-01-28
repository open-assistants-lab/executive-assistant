# Build a SQL assistant with on-demand skills - LangChain Tutorial

**Source:** https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant

## Overview

This tutorial shows how to use **progressive disclosure** - a context management technique where the agent loads information on-demand rather than upfront - to implement **skills** (specialized prompt-based instructions). The agent loads skills via tool calls, rather than dynamically changing the system prompt, discovering and loading only the skills it needs for each task.

**Use case:** Imagine building an agent to help write SQL queries across different business verticals in a large enterprise. Your organization might have separate datastores for each vertical, or a single monolithic transactional database with thousands of tables. Either way, loading all schemas upfront would overwhelm the context window. Progressive disclosure solves this by loading only the relevant schema when needed. This architecture also enables different product owners and stakeholders to independently contribute and maintain skills for their specific business verticals.

**What you'll build:** A SQL query assistant with two skills (sales analytics and inventory management). The agent sees lightweight skill descriptions in its system prompt, then loads full transactional database schemas and business logic through tool calls only when relevant to the user's query.

## How it works

Here's the flow when a user asks for a SQL query:

### Why progressive disclosure:

- **Reduces context usage** - load only the 2-3 skills needed for a task, not all available skills
- **Scales efficiently** - add dozens or hundreds of skills without overwhelming context
- **Simplifies conversation history** - single agent with one conversation thread

### What are skills:

Skills, as popularized by Claude Code, are primarily prompt-based: self-contained units of specialized instructions for specific business tasks. In Claude Code, skills are exposed as directories with files on the file system, discovered through file operations. Skills guide behavior through prompts and can provide information about tool usage or include sample code for a coding agent to execute.

Skills with progressive disclosure can be viewed as a form of [RAG (Retrieval-Augmented Generation)](https://docs.langchain.com/oss/python/langchain/rag), where each skill is a retrieval unit—though not necessarily backed by embeddings or keyword search, but by tools for browsing content (like file operations or, in this tutorial, direct lookup).

### Trade-offs:

- **Latency**: Loading skills on-demand requires additional tool calls, which adds latency to the first request that needs each skill
- **Workflow control**: Basic implementations rely on prompting to guide skill usage - you cannot enforce hard constraints like "always try skill A before skill B" without custom logic

### Implementing your own skills system

When building your own skills implementation (as we do in this tutorial), the core concept is progressive disclosure - loading information on-demand. Beyond that, you have full flexibility in implementation:

- **Storage**: databases, S3, in-memory data structures, or any backend
- **Discovery**: direct lookup (this tutorial), RAG for large skill collections, file system scanning, or API calls
- **Loading logic**: customize latency characteristics and add logic to search through skill content or rank relevance
- **Side effects**: define what happens when a skill loads, such as exposing tools associated with that skill (covered in section 8)

This flexibility lets you optimize for your specific requirements around performance, storage, and workflow control.

## Setup

### Installation

This tutorial requires the `langchain` package:

```bash
pip install langchain
```

### LangSmith

Set up [LangSmith](https://smith.langchain.com/) to inspect what is happening inside your agent. Then set the following environment variables:

```bash
export LANGSMITH_TRACING="true"
export LANGSMITH_API_KEY="..."
```

### Select an LLM

Select a chat model from LangChain's suite of integrations: OpenAI, Anthropic, Azure, Google Gemini, AWS Bedrock, or HuggingFace.

## 1. Define skills

First, define the structure for skills. Each skill has a name, a brief description (shown in the system prompt), and full content (loaded on-demand):

```python
from typing import TypedDict

class Skill(TypedDict):
    """A skill that can be progressively disclosed to the agent."""
    name: str  # Unique identifier for the skill
    description: str  # 1-2 sentence description to show in system prompt
    content: str  # Full skill content with detailed instructions
```

Now define example skills for a SQL query assistant. The skills are designed to be **lightweight in description** (shown to the agent upfront) but **detailed in content** (loaded only when needed):

```python
SKILLS: list[Skill] = [
    {
        "name": "sales_analytics",
        "description": "Transactional Database schema and business logic for sales data analysis including customers, orders, and revenue.",
        "content": """# Sales Analytics Schema

## Tables

### customers
- customer_id (PRIMARY KEY)
- name
- email
- signup_date
- status (active/inactive)
- customer_tier (bronze/silver/gold/platinum)

### orders
- order_id (PRIMARY KEY)
- customer_id (FOREIGN KEY -> customers)
- order_date
- status (pending/completed/cancelled/refunded)
- total_amount
- sales_region (north/south/east/west)

### order_items
- item_id (PRIMARY KEY)
- order_id (FOREIGN KEY -> orders)
- product_id
- quantity
- unit_price
- discount_percent

## Business Logic

**Active customers**: status = 'active' AND signup_date <= CURRENT_DATE - INTERVAL '90 days'

**Revenue calculation**: Only count orders with status = 'completed'. Use total_amount from orders table, which already accounts for discounts.

**Customer lifetime value (CLV)**: Sum of all completed order amounts for a customer.

**High-value orders**: Orders with total_amount > 1000

## Example Query

-- Get top 10 customers by revenue in the last quarter
SELECT
    c.customer_id,
    c.name,
    c.customer_tier,
    SUM(o.total_amount) as total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status = 'completed'
  AND o.order_date >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY c.customer_id, c.name, c.customer_tier
ORDER BY total_revenue DESC
LIMIT 10;
""",
    },
    {
        "name": "inventory_management",
        "description": "Transactional Database schema and business logic for inventory tracking including products, warehouses, and stock levels.",
        "content": """# Inventory Management Schema

## Tables

### products
- product_id (PRIMARY KEY)
- product_name
- sku
- category
- unit_cost
- reorder_point (minimum stock level before reordering)
- discontinued (boolean)

### warehouses
- warehouse_id (PRIMARY KEY)
- warehouse_name
- location
- capacity

### inventory
- inventory_id (PRIMARY KEY)
- product_id (FOREIGN KEY -> products)
- warehouse_id (FOREIGN KEY -> warehouses)
- quantity_on_hand
- last_updated

### stock_movements
- movement_id (PRIMARY KEY)
- product_id (FOREIGN KEY -> products)
- warehouse_id (FOREIGN KEY -> warehouses)
- movement_type (inbound/outbound/transfer/adjustment)
- quantity (positive for inbound, negative for outbound)
- movement_date
- reference_number

## Business Logic

**Available stock**: quantity_on_hand from inventory table where quantity_on_hand > 0

**Products needing reorder**: Products where total quantity_on_hand across all warehouses is less than or equal to the product's reorder_point

**Active products only**: Exclude products where discontinued = true unless specifically analyzing discontinued items

**Stock valuation**: quantity_on_hand * unit_cost for each product

## Example Query

-- Find products below reorder point across all warehouses
SELECT
    p.product_id,
    p.product_name,
    p.reorder_point,
    SUM(i.quantity_on_hand) as total_stock,
    p.unit_cost,
    (p.reorder_point - SUM(i.quantity_on_hand)) as units_to_reorder
FROM products p
JOIN inventory i ON p.product_id = i.product_id
WHERE p.discontinued = false
GROUP BY p.product_id, p.product_name, p.reorder_point, p.unit_cost
HAVING SUM(i.quantity_on_hand) <= p.reorder_point
ORDER BY units_to_reorder DESC;
""",
    },
]
```

## 2. Create skill loading tool

Create a tool to load full skill content on-demand:

```python
from langchain.tools import tool

@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "expense_reporting", "travel_booking")
    """
    # Find and return the requested skill
    for skill in SKILLS:
        if skill["name"] == skill_name:
            return f"Loaded skill: {skill_name}\n\n{skill['content']}"

    # Skill not found
    available = ", ".join(s["name"] for s in SKILLS)
    return f"Skill '{skill_name}' not found. Available skills: {available}"
```

## 3. Build skill middleware

Create custom middleware that injects skill descriptions into the system prompt. This middleware makes skills discoverable without loading their full content upfront.

```python
from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
from langchain.messages import SystemMessage
from typing import Callable

class SkillMiddleware(AgentMiddleware):
    """Middleware that injects skill descriptions into the system prompt."""

    # Register the load_skill tool as a class variable
    tools = [load_skill]

    def __init__(self):
        """Initialize and generate the skills prompt from SKILLS."""
        # Build skills prompt from the SKILLS list
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
        """Sync: Inject skill descriptions into system prompt."""
        # Build the skills addendum
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed information "
            "about handling a specific type of request."
        )

        # Append to system message content blocks
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        modified_request = request.override(system_message=new_system_message)
        return handler(modified_request)
```

## 4. Create the agent with skill support

Now create the agent with the skill middleware and a checkpointer for state persistence:

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

# Create the agent with skill support
agent = create_agent(
    model,
    system_prompt=(
        "You are a SQL query assistant that helps users "
        "write queries against business databases."
    ),
    middleware=[SkillMiddleware()],
    checkpointer=InMemorySaver(),
)
```

## 5. Test progressive disclosure

Test the agent with a question that requires skill-specific knowledge:

```python
import uuid

# Configuration for this conversation thread
thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}

# Ask for a SQL query
result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Write a SQL query to find all customers "
                    "who made orders over $1000 in the last month"
                ),
            }
        ]
    },
    config
)

# Print the conversation
for message in result["messages"]:
    if hasattr(message, 'pretty_print'):
        message.pretty_print()
    else:
        print(f"{message.type}: {message.content}")
```

Expected output:

```
================================ Human Message =================================

Write a SQL query to find all customers who made orders over $1000 in the last month
================================= Ai Message ==================================
Tool Calls:
  load_skill (call_abc123)
 Call ID: call_abc123
  Args:
    skill_name: sales_analytics
================================ Tool Message ================================
Name: load_skill

Loaded skill: sales_analytics

# Sales Analytics Schema

## Tables

### customers
- customer_id (PRIMARY KEY)
- name
- email
- signup_date
- status (active/inactive)
- customer_tier (bronze/silver/gold/platinum)

### orders
- order_id (PRIMARY KEY)
- customer_id (FOREIGN KEY -> customers)
- order_date
- status (pending/completed/cancelled/refunded)
- total_amount
- sales_region (north/south/east/west)

[... rest of schema ...]

## Business Logic

**High-value orders**: Orders with `total_amount > 1000`
**Revenue calculation**: Only count orders with `status = 'completed'`

================================= Ai Message ==================================

Here's a SQL query to find all customers who made orders over $1000 in the last month:

```sql
SELECT DISTINCT
    c.customer_id,
    c.name,
    c.email,
    c.customer_tier
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.total_amount > 1000
  AND o.status = 'completed'
  AND o.order_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY c.customer_id;
```

This query:
- Joins customers with their orders
- Filters for high-value orders (>$1000) using the total_amount field
- Only includes completed orders (as per the business logic)
- Restricts to orders from the last month
- Returns distinct customers to avoid duplicates if they made multiple qualifying orders
```

## 6. Advanced: Add constraints with custom state

Optional: Track loaded skills and enforce tool constraints

You can add constraints to enforce that certain tools are only available after specific skills have been loaded. This requires tracking which skills have been loaded in custom agent state.

### Define custom state

First, extend the agent state to track loaded skills:

```python
from langchain.agents.middleware import AgentState

class CustomState(AgentState):
    skills_loaded: NotRequired[list[str]]  # Track which skills have been loaded
```

### Update load_skill to modify state

Modify the `load_skill` tool to update state when a skill is loaded:

```python
from langgraph.types import Command
from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage

@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> Command:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load
    """
    # Find and return the requested skill
    for skill in SKILLS:
        if skill["name"] == skill_name:
            skill_content = f"Loaded skill: {skill_name}\n\n{skill['content']}"

            # Update state to track loaded skill
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=skill_content,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                    "skills_loaded": [skill_name],
                }
            )

    # Skill not found
    available = ", ".join(s["name"] for s in SKILLS)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Skill '{skill_name}' not found. Available skills: {available}",
                    tool_call_id=runtime.tool_call_id,
                )
            ]
        }
    )
```

### Create constrained tool

Create a tool that's only usable after a specific skill has been loaded:

```python
@tool
def write_sql_query(
    query: str,
    vertical: str,
    runtime: ToolRuntime,
) -> str:
    """Write and validate a SQL query for a specific business vertical.

    This tool helps format and validate SQL queries. You must load the
    appropriate skill first to understand the transactional database schema.

    Args:
        query: The SQL query to write
        vertical: The business vertical (sales_analytics or inventory_management)
    """
    # Check if the required skill has been loaded
    skills_loaded = runtime.state.get("skills_loaded", [])

    if vertical not in skills_loaded:
        return (
            f"Error: You must load the '{vertical}' skill first "
            f"to understand the transactional database schema before writing queries. "
            f"Use load_skill('{vertical}') to load the schema."
        )

    # Validate and format the query
    return (
        f"SQL Query for {vertical}:\n\n"
        f"```sql\n{query}\n```\n\n"
        f"✓ Query validated against {vertical} schema\n"
        f"Ready to execute against the transactional database."
    )
```

### Update middleware and agent

Update the middleware to use the custom state schema:

```python
class SkillMiddleware(AgentMiddleware[CustomState]):
    """Middleware that injects skill descriptions into the system prompt."""

    state_schema = CustomState
    tools = [load_skill, write_sql_query]

    # ... rest of the middleware implementation stays the same
```

Create the agent with the middleware that registers the constrained tool:

```python
agent = create_agent(
    model,
    system_prompt=(
        "You are a SQL query assistant that helps users "
        "write queries against business databases."
    ),
    middleware=[SkillMiddleware()],
    checkpointer=InMemorySaver(),
)
```

## Implementation variations

This tutorial implemented skills as in-memory Python dictionaries loaded through tool calls. However, there are several ways to implement progressive disclosure with skills:

**Storage backends:**

- **In-memory** (this tutorial): Skills defined as Python data structures, fast access, no I/O overhead
- **File system** (Claude Code approach): Skills as directories with files, discovered via file operations like `read_file`
- **Remote storage**: Skills in S3, databases, Notion, or APIs, fetched on-demand

**Skill discovery** (how the agent learns which skills exist):

- **System prompt listing**: Skill descriptions in system prompt (used in this tutorial)
- **File-based**: Discover skills by scanning directories (Claude Code approach)
- **Registry-based**: Query a skill registry service or API for available skills
- **Dynamic lookup**: List available skills via a tool call

**Progressive disclosure strategies** (how skill content is loaded):

- **Single load**: Load entire skill content in one tool call (used in this tutorial)
- **Paginated**: Load skill content in multiple pages/chunks for large skills
- **Search-based**: Search within a specific skill's content for relevant sections (e.g., using grep/read operations on skill files)
- **Hierarchical**: Load skill overview first, then drill into specific subsections

**Size considerations** (uncalibrated mental model - optimize for your system):

- **Small skills** (< 1K tokens / ~750 words): Can be included directly in system prompt and cached with prompt caching for cost savings and faster responses
- **Medium skills** (1-10K tokens / ~750-7.5K words): Benefit from on-demand loading to avoid context overhead (this tutorial)
- **Large skills** (> 10K tokens / ~7.5K words, or > 5-10% of context window): Should use progressive disclosure techniques like pagination, search-based loading, or hierarchical exploration to avoid consuming excessive context

## Progressive disclosure and context engineering

### Combining with few-shot prompting

For the SQL query use case, you could extend progressive disclosure to dynamically load **few-shot examples** that match the user's query:

**Example approach:**

1. User asks: "Find customers who haven't ordered in 6 months"
2. Agent loads `sales_analytics` schema (as shown in this tutorial)
3. Agent also loads 2-3 relevant example queries (via semantic search or tag-based lookup):
   - Query for finding inactive customers
   - Query with date-based filtering
   - Query joining customers and orders tables
4. Agent writes query using both schema knowledge AND example patterns

This combination of progressive disclosure (loading schemas on-demand) and dynamic few-shot prompting (loading relevant examples) creates a powerful context engineering pattern that scales to large knowledge bases while providing high-quality, grounded outputs.

## Next steps

- Learn about [middleware](https://docs.langchain.com/oss/python/langchain/middleware) for more dynamic agent behaviors
- Explore [context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) techniques for managing agent context
- Explore the [handoffs pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support) for sequential workflows
- Read the [subagents pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant) for parallel task routing
- See [multi-agent patterns](https://docs.langchain.com/oss/python/langchain/multi-agent) for other approaches to specialized agents
- Use [LangSmith](https://smith.langchain.com/) to debug and monitor skill loading
