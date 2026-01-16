# Review: "Continue" After Max Iterations

## Issue Summary
The max-iterations guard is intended as a soft stop to prevent runaway tool loops; it emits a brief “summary” and asks the user to say “continue” to resume. However, when the user replies “continue”, the agent resets the counter but never invokes the model, so the conversation stalls. This contradicts the design intent for the max-iteration/summarization flow.

## Evidence
- `src/cassey/agent/nodes.py:42` `src/cassey/agent/nodes.py:57` returns only `{"iterations": 0}` when "continue" is detected.
- The node returns no `messages`, so the graph ends without a new model call.

## Expected vs Actual
- Expected (per design intent): "continue" should resume the agent and immediately produce a new response from the model.
- Actual: iterations reset but no response is generated; the graph ends and the user can loop on the max-iteration warning.

## Impact
- Users see "continue" do nothing or repeatedly hit the max-iteration warning.
- Breaks the intended recovery path for long tool-driven tasks.

## Recommendation (Minimal Fix)
When "continue" is detected:
1) Reset the iteration counter, **and**
2) Continue the normal call flow so the model runs immediately (do not early-return with no messages).

One way to do this is to remove the early return and let the function proceed, or to return both a response and `iterations: 0`. If you want to treat “continue” as a meta command, you can also drop the last HumanMessage before invoking the model so it continues with the prior task context.

```python
# Pseudocode
if iterations >= MAX_ITERATIONS and user_said_continue:
    iterations = 0  # or return {"iterations": 0, "messages": [response]}
    # proceed to model_with_tools.ainvoke(...)
```

This keeps the UX promise: user says "continue" and gets a fresh response.

## Verdict
Not expected. This should be fixed to align the max-iteration “summary + continue” pattern with its intended behavior.
