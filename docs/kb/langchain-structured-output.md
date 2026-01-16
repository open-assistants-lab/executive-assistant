# LangGraph Structured Output - Knowledge Base

## Overview

Structured output allows you to constrain LLM responses to specific JSON schemas, Pydantic models, or other structured formats. This is essential for building reliable agents that need consistent, parseable outputs.

## Methods for Structured Output

### 1. ToolStrategy (Universal)

Works with any model that supports tool calling (OpenAI, Anthropic, etc.):

```python
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

class QueryResponse(BaseModel):
    """Structured response from the agent."""
    answer: str
    confidence: float
    sources: list[str]

agent = create_agent(
    model="gpt-4o-mini",
    tools=[search_tool],
    response_format=ToolStrategy(QueryResponse)
)

result = agent.invoke({"messages": [{"role": "user", "content": "What is X?"}]})
# Returns: QueryResponse(answer="...", confidence=0.9, sources=[...])
```

**Pros**: Works with any tool-calling model
**Cons**: Slightly slower than native methods

### 2. ProviderStrategy (Native)

Uses provider-native structured output (more reliable):

```python
from langchain.agents.structured_output import ProviderStrategy

agent = create_agent(
    model="gpt-4o",  # OpenAI supports native structured output
    response_format=ProviderStrategy(QueryResponse)
)
```

**Supported Providers**:
- OpenAI: `response_format={"type": "json_schema"}`
- Anthropic: `tool_choice` with constrained tool

### 3. with_structured_output() (LangChain Core)

Direct model binding:

```python
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

class Sentiment(BaseModel):
    sentiment: str  # "positive", "negative", "neutral"
    confidence: float
    reasoning: str

model = ChatOpenAI(model="gpt-4o")
structured_model = model.with_structured_output(Sentiment)

result = structured_model.invoke("Analyze: I love this product!")
# Returns: Sentiment(sentiment="positive", confidence=0.95, reasoning="...")
```

## Pydantic Models

### Defining Schemas

```python
from pydantic import BaseModel, Field
from typing import List, Literal

class ResearchFindings(BaseModel):
    """Structured research output."""
    topic: str = Field(description="The main research topic")
    summary: str = Field(description="Brief summary of findings")
    key_points: List[str] = Field(description="3-5 key points")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level in the findings"
    )
    sources: List[str] = Field(description="List of source URLs")
```

### Nested Models

```python
class Citation(BaseModel):
    url: str
    title: str
    snippet: str

class AnalysisResult(BaseModel):
    """Nested structured output."""
    conclusion: str
    citations: List[Citation]
    metadata: dict
```

## In LangGraph Graphs

### State with Structured Output

```python
from langgraph.graph import StateGraph, MessagesState
from typing import TypedDict

class AnalysisState(TypedDict):
    messages: list  # Chat history
    analysis: dict  # Structured analysis output
    status: str

def analyze_node(state: AnalysisState):
    """Node that produces structured output."""
    # Use structured model
    structured_model = model.with_structured_output(AnalysisResult)

    # Extract question from messages
    question = state["messages"][-1].content

    # Get structured output
    result = structured_model.invoke(f"Analyze: {question}")

    # Return state update
    return {
        "analysis": result.dict(),
        "status": "complete"
    }
```

### Conditional Routing Based on Output

```python
def route_based_on_result(state: AnalysisState) -> str:
    """Route to different nodes based on structured output."""
    confidence = state["analysis"].get("confidence", "low")

    if confidence == "high":
        return "finalize"
    elif confidence == "medium":
        return "verify"
    else:
        return "research_more"

workflow.add_conditional_edges(
    "analyze",
    route_based_on_result,
    {
        "finalize": "final_node",
        "verify": "verify_node",
        "research_more": "research_node"
    }
)
```

## Error Handling

### Validation Errors

```python
from pydantic import ValidationError

try:
    result = structured_model.invoke(user_input)
except ValidationError as e:
    print(f"Validation failed: {e}")
    # Fallback to retry or different approach
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(ValidationError)
)
async def get_structured_output(model, prompt: str):
    """Retry structured output on validation failure."""
    return await model.ainvoke(prompt)
```

## Structured Output for Tools

### Defining Tool Output Schema

```python
from langchain.tools import tool
from pydantic import BaseModel

class WeatherResult(BaseModel):
    """Weather tool output schema."""
    temperature: float
    conditions: str
    humidity: int
    location: str

@tool
def get_weather(location: str) -> WeatherResult:
    """Get weather information for a location."""
    # Simulated weather data
    return WeatherResult(
        temperature=72.5,
        conditions="Sunny",
        humidity=45,
        location=location
    )
```

### Structured Tool Output in Agents

```python
agent = create_agent(
    model="gpt-4o",
    tools=[get_weather],
    # The agent can now parse structured tool outputs
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What's the weather in Tokyo?"}]
})
# Tool returns WeatherResult that agent can reason about
```

## Advanced Patterns

### Multiple Structured Outputs

```python
from typing import Union

class PositiveResponse(BaseModel):
    type: Literal["positive"]
    feedback: str

class NegativeResponse(BaseModel):
    type: Literal["negative"]
    reason: str

class NeutralResponse(BaseModel):
    type: Literal["neutral"]
    notes: str

Response = Union[PositiveResponse, NegativeResponse, NeutralResponse]

model = ChatOpenAI(model="gpt-4o")
structured_model = model.with_structured_output(Response)
```

### Streaming Structured Output

```python
async def stream_structured(model, prompt: str):
    """Stream with structured output parsing."""
    async for chunk in model.astream(prompt):
        # Partial streaming may not be available for all providers
        # Consider using callbacks for partial results
        pass

    # Final structured result
    result = await model.ainvoke(prompt)
    return result
```

## Best Practices

1. **Be explicit in field descriptions**: Help the model understand what each field should contain
2. **Use enums for constrained values**: Better than open-ended strings
3. **Validate on your side too**: Don't trust model output 100%
4. **Provide examples in prompts**: For complex schemas, show example outputs
5. **Handle errors gracefully**: Have fallbacks when structured parsing fails

## References

- [Structured Output Documentation](https://docs.langchain.com/oss/python/langchain/structured_outputs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
