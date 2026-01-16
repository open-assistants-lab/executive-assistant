# LangGraph Guardrails - Knowledge Base

## Overview

Guardrails are safety mechanisms that constrain agent behavior, ensuring outputs remain within acceptable boundaries. LangGraph supports guardrails through state validation, middleware, and conditional routing.

## Guardrail Patterns

### 1. Input Validation Guardrails

Validate user inputs before processing:

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class GuardState(TypedDict):
    messages: list
    passed_guards: bool
    guard_reason: str

def input_validation_node(state: GuardState):
    """Validate input content."""
    user_message = state["messages"][-1].content

    # Example guardrails
    forbidden_keywords = ["hack", "exploit", "bypass"]
    contains_forbidden = any(kw in user_message.lower() for kw in forbidden_keywords)

    if contains_forbidden:
        return {
            "passed_guards": False,
            "guard_reason": "Input contains prohibited content"
        }

    return {"passed_guards": True}

workflow = StateGraph(GuardState)
workflow.add_node("validate_input", input_validation_node)

def route_after_validation(state: GuardState) -> str:
    """Route based on validation result."""
    if state.get("passed_guards"):
        return "process"
    return "reject"

workflow.add_conditional_edges(
    "validate_input",
    route_after_validation,
    {"process": "agent_node", "reject": END}
)
```

### 2. Output Sanitization Guardrails

```python
import re

def sanitize_output_node(state: GuardState):
    """Sanitize agent output before returning to user."""
    ai_message = state["messages"][-1]

    if ai_message.type != "ai":
        return state

    content = ai_message.content

    # Remove potential code injection
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE)

    # Redact potential PII patterns
    content = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED-SSN]', content)

    # Update message with sanitized content
    ai_message.content = content

    return {"messages": [ai_message]}
```

### 3. Topic Guardrails

Constrain agent to specific topics:

```python
from pydantic import BaseModel
from typing import Literal

class TopicCheck(BaseModel):
    """Topic validation result."""
    allowed: bool
    topic: str
    redirect_message: str | None = None

ALLOWED_TOPICS = ["weather", "sports", "news", "entertainment"]

def topic_guard_node(state: GuardState):
    """Check if query is about allowed topics."""
    user_message = state["messages"][-1].content

    # Use LLM to classify topic
    classifier = model.with_structured_output(TopicCheck)

    result = classifier.invoke(f"""
    Classify this query: "{user_message}"

    Allowed topics: {ALLOWED_TOPICS}
    """)

    if not result.allowed:
        return {
            "messages": [{
                "role": "assistant",
                "content": result.redirect_message or "I can only help with weather, sports, news, and entertainment topics."
            }]
        }

    # Proceed to agent
    return state  # Pass through unchanged
```

### 4. Tool Usage Guardrails

```python
def tool_guard_node(state: GuardState):
    """Validate tool calls before execution."""
    for msg in state["messages"]:
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get("name", "")

                # Guardrail: Block certain tools
                if tool_name in ["delete_database", "send_money"]:
                    # Replace with error message
                    msg.tool_calls.remove(tool_call)

                # Guardrail: Require approval for sensitive tools
                if tool_name in ["send_email", "update_record"]:
                    # Add approval step
                    tool_call["approval_required"] = True

    return state
```

## Middleware Guardrails

Using LangChain middleware for guardrails:

```python
from langchain.agents.middleware import PIIMiddleware, AgentMiddleware

class ContentFilterMiddleware(AgentMiddleware):
    """Custom middleware for content filtering."""

    def before_model(self, state, runtime) -> dict | None:
        """Filter input before model sees it."""
        messages = state.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and "content" in msg:
                # Remove profanity
                msg["content"] = self.filter_profanity(msg["content"])
        return None  # State modified in place

    def after_model(self, state, runtime, result) -> dict | None:
        """Filter output after model generates."""
        if hasattr(result, "content"):
            result.content = self.filter_profanity(result.content)
        return None

agent = create_agent(
    model="gpt-4o",
    tools=[...],
    middleware=[
        PIIMiddleware("email", strategy="redact", apply_to_input=True),
        PIIMiddleware("ssn", strategy="mask", apply_to_output=True),
        ContentFilterMiddleware()
    ]
)
```

## State Schema Validation

Use Pydantic for runtime state validation:

```python
from pydantic import BaseModel, field_validator
from typing import List

class ValidatedState(BaseModel):
    """State with built-in validation."""
    messages: List[dict]
    user_id: str
    max_tokens: int = 4000

    @field_validator("messages")
    def validate_message_length(cls, v):
        """Ensure message list doesn't exceed token limit."""
        total = sum(len(m.get("content", "")) for m in v)
        if total > 100000:  # Approximate token limit
            raise ValueError("Message history too long")
        return v

    @field_validator("user_id")
    def validate_user_id(cls, v):
        """Ensure user_id is valid format."""
        if not v or not isinstance(v, str):
            raise ValueError("Invalid user_id")
        return v
```

## LLM-Based Guardrails

Use an LLM to evaluate safety:

```python
from pydantic import BaseModel

class SafetyCheck(BaseModel):
    """Safety evaluation result."""
    is_safe: bool
    risk_level: Literal["low", "medium", "high"]
    reason: str

def safety_guard_node(state: GuardState):
    """LLM-based safety check."""
    user_message = state["messages"][-1].content

    safety_model = model.with_structured_output(SafetyCheck)

    check = safety_model.invoke(f"""
    Evaluate the safety of this user message:
    "{user_message}"

    Check for:
    - Harmful content
    - PII exposure
    - Inappropriate requests
    """)

    if not check.is_safe or check.risk_level == "high":
        return {
            "messages": [{
                "role": "assistant",
                "content": f"I cannot process that request. Reason: {check.reason}"
            }]
        }

    return state  # Safe to proceed
```

## Guardrail Composition

Combine multiple guardrails in sequence:

```python
# Define guardrail nodes
workflow.add_node("input_guard", input_validation_node)
workflow.add_node("topic_guard", topic_guard_node)
workflow.add_node("safety_guard", safety_guard_node)
workflow.add_node("tool_guard", tool_guard_node)
workflow.add_node("sanitize", sanitize_output_node)

# Chain guardrails before agent
workflow.add_edge(START, "input_guard")
workflow.add_edge("input_guard", "topic_guard")
workflow.add_edge("topic_guard", "safety_guard")
workflow.add_edge("safety_guard", "agent_node")

# Tool guard before tool execution
workflow.add_edge("agent_node", "tool_guard")
workflow.add_conditional_edges(
    "tool_guard",
    lambda s: "tools" if s.get("tool_calls") else END,
    {"tools": "tools", END: "sanitize"}
)

# Sanitize before output
workflow.add_edge("tools", "sanitize")
workflow.add_edge("sanitize", END)
```

## Best Practices

1. **Fail closed**: Default to blocking unknown inputs
2. **Explain rejections**: Tell users why content was blocked
3. **Log guardrail triggers**: Monitor for abuse patterns
4. **Layer defenses**: Use multiple guardrail types
5. **Test adversarially**: Try to break your own guardrails

## Guardrail Libraries

Consider these specialized libraries:

- **Guardrails AI**: Configurable validation rails
- **NeMo Guardrails**: Programmable guardrails for LLMs
- **Microsoft Guidance**: Structured generation with constraints

## References

- [LangGraph State Validation](https://docs.langchain.com/oss/python/langgraph/graph-api#state)
- [Guardrails Best Practices](https://www.anthropic.com/engineering/building-effective-agents)
