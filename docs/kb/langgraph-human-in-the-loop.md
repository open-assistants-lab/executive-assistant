# LangGraph Human-in-the-Loop - Knowledge Base

## Overview

Human-in-the-loop (HITL) allows agents to pause execution and request human approval, input, or guidance before continuing. This is essential for high-stakes operations, compliance workflows, and iterative agent improvement.

## LangGraph Interrupt Mechanism

LangGraph supports HITL through the **interrupt** mechanism, which pauses graph execution at a specific point and waits for human intervention.

### Basic Interrupt

```python
from langgraph.graph import StateGraph, MessagesState
from langgraph.checkpoint import MemorySaver

# Setup checkpointer (required for interrupts)
checkpointer = MemorySaver()

def approval_required_node(state: MessagesState):
    """Node that requests human approval."""
    # Check if we have approval
    if state.get("approved", False):
        return {"messages": "Continuing with approved action"}

    # Request approval
    return {
        "messages": [{
            "role": "assistant",
            "content": "I need approval before proceeding",
            "tool_calls": [{
                "id": "approval_request",
                "name": "human_approval",
                "args": {"action": "send_email", "recipient": "user@example.com"}
            }]
        }]
    }

# Add interrupt point
workflow = StateGraph(MessagesState)
workflow.add_node("approval_node", approval_required_node)

# This edge will have an interrupt
workflow.add_edge("approval_node", "__interrupt__")
```

## HumanInTheLoopMiddleware (LangChain)

Using the middleware approach with `create_agent`:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import MemorySaver

agent = create_agent(
    model="gpt-4o",
    tools=[send_email, delete_file, transfer_money],
    checkpointer=MemorySaver(),  # Required
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
                "delete_file": True,  # Interrupt on this tool
                "transfer_money": {
                    "allowed_decisions": ["approve", "reject"],
                },
            }
        )
    ]
)
```

## Handling Interrupts with LangGraph API

### Server-Side Setup

```python
# Agent Server automatically supports interrupts
from langgraph_api import add_routes
from fastapi import FastAPI

app = FastAPI()
add_routes(app, agent)

# The endpoint now supports:
# - POST /threads/{thread_id}/state - to update state and resume
# - GET /threads/{thread_id}/state - to check for interrupts
```

### Client-Side Resume

```python
from langgraph_sdk import get_client

client = get_client(url="http://localhost:2024")

async def handle_human_approval(thread_id: str, approve: bool):
    """Resume an interrupted thread."""
    if not approve:
        # Reject the action and end
        await client.threads.update_state(
            thread_id=thread_id,
            values={"approved": False}
        )
        return

    # Approve and continue
    await client.threads.update_state(
        thread_id=thread_id,
        values={"approved": True}
    )

    # The graph will resume execution
```

## Custom Interrupt Conditions

### Conditional Interrupt

```python
from langgraph.graph import StateGraph

def should_interrupt(state) -> bool:
    """Determine if interrupt is needed."""
    # Interrupt if amount > threshold
    amount = state.get("amount", 0)
    return amount > 1000

def payment_node(state):
    """Process payment."""
    if should_interrupt(state):
        # Signal interrupt needed
        return {
            "needs_approval": True,
            "approval_reason": f"High value: ${state['amount']}"
        }

    # Process payment
    return process_payment(state)

# Route based on approval need
def route_after_payment(state):
    if state.get("needs_approval"):
        return "interrupt_node"
    return "complete"

workflow.add_conditional_edges(
    "payment",
    route_after_payment,
    {
        "interrupt_node": "interrupt_node",
        "complete": END
    }
)
```

## Approval Workflow Patterns

### Pattern 1: Tool-Level Approval

```python
from langchain.tools import tool
from typing import Literal

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email (requires approval)."""
    # This will be intercepted by middleware
    return f"Email sent to {to}"

# Configure middleware
HumanInTheLoopMiddleware(
    interrupt_on={
        "send_email": {
            "allowed_decisions": ["approve", "edit", "reject"],
        }
    }
)
```

### Pattern 2: State-Based Approval

```python
class ApprovalState(TypedDict):
    messages: list
    pending_action: dict | None
    approval_status: Literal["pending", "approved", "rejected"]
    approval_feedback: str

def request_approval(state: ApprovalState):
    """Request approval for an action."""
    return {
        "pending_action": {
            "type": "delete_file",
            "path": "/important/file.txt"
        },
        "approval_status": "pending"
    }

def check_approval(state: ApprovalState) -> str:
    """Route based on approval status."""
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "execute"
    elif status == "rejected":
        return "cancel"
    return "wait"

def execute_action(state: ApprovalState):
    """Execute the approved action."""
    action = state["pending_action"]
    return {"messages": f"Executed: {action['type']}"}

# Wait node that creates interrupt
def wait_for_approval(state: ApprovalState):
    """This node will be interrupted."""
    # In production, use __interrupt__ mechanism
    return state
```

### Pattern 3: Multi-Step Approval

```python
class MultiApprovalState(TypedDict):
    messages: list
    level1_approved: bool
    level2_approved: bool
    amount: float

def level1_approval(state: MultiApprovalState):
    """First level approval (manager)."""
    if state["amount"] < 1000:
        return {"level1_approved": True, "level2_approved": True}
    return {"level1_approved": False}

def level2_approval(state: MultiApprovalState):
    """Second level approval (director) for high amounts."""
    if state["amount"] >= 1000 and state["level1_approved"]:
        # Request director approval
        return {}
    return {}

def route_after_level1(state: MultiApprovalState) -> str:
    if state["amount"] < 1000:
        return "execute"
    return "level2_approval"
```

## Editing Interrupted Actions

Allow humans to modify the action before approval:

```python
HumanInTheLoopMiddleware(
    interrupt_on={
        "send_email": {
            "allowed_decisions": ["approve", "edit", "reject"],
        }
    }
)

# Client-side edit
async def edit_and_approve(thread_id: str, new_subject: str):
    """Edit the pending action before approval."""
    await client.threads.update_state(
        thread_id=thread_id,
        values={
            "edit_mode": "modify",
            "modifications": {
                "subject": new_subject
            },
            "approved": True
        }
    )
```

## Time Travel with Human Approval

Revert to a previous checkpoint and make different decisions:

```python
async def revert_and_retry(thread_id: str, checkpoint_id: str):
    """Revert to a previous checkpoint."""
    # Get state at checkpoint
    state = await client.threads.get_state(
        thread_id=thread_id,
        checkpoint_id=checkpoint_id
    )

    # Revert to that point
    await client.threads.update_state(
        thread_id=thread_id,
        state=state.values
    )

    # Now make a different decision
    await client.threads.update_state(
        thread_id=thread_id,
        values={"approved": True}  # Different decision
    )
```

## Best Practices

1. **Always use a checkpointer**: Required for interrupt functionality
2. **Clear approval requests**: Tell the human exactly what they're approving
3. **Provide context**: Include relevant information in approval prompts
4. **Timeout mechanisms**: Don't wait forever for approval
5. **Audit trail**: Log all approval decisions

## References

- [LangGraph Human-in-the-Loop](https://docs.langchain.com/oss/python/langgraph/human_in_the_loop)
- [LangSmith HITL API](https://docs.langchain.com/langsmith/add-human-in-the-loop)
