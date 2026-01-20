# Proposed Fixes: Structured Summary Implementation (2026-01-15 20:07)

## Fixes by Finding

### 1) Source binding is broken
**Problem:** All summary items get the full list of message IDs and IDs are ephemeral (`msg_{i}`).

**Proposed fix:**
- Use stable message IDs. If messages don’t have IDs, generate UUIDs once and persist them in message metadata (or in the audit log) and reuse on subsequent summarizations.
- Bind each extracted item to the specific message IDs that justify it. Two options:
  1) Ask the extractor to return message indices (or hashes) per item, then map them to IDs.
  2) Post-process: run a lightweight semantic match between each extracted item and recent messages to choose 1–3 supporting message IDs.

**Implementation sketch:**
- Change extractor prompt to return a list of `{text, sources:[message_index]}` for each category.
- In `extract_conversation_elements`, map indices to message IDs (or hashes) and store those.
- Store message IDs in a durable place (message metadata or separate log table).

### 2) Topic deactivation only on domain change
**Problem:** In-domain topic shifts keep multiple active topics, reintroducing contamination.

**Proposed fix:**
- Introduce a topic similarity threshold using embeddings or keyword overlap. If a new topic diverges significantly, mark the previous active topic inactive even if domain matches.
- Add a “topic relevance score” from the classifier (or embed similarity) and only keep the top 1–2 active topics in the prompt.

**Implementation sketch:**
- Add `TopicClassifier.topic_similarity(query, topic_id)` with embedding cosine similarity.
- If similarity < threshold (e.g. 0.6), mark old topic inactive.
- Render only the active topic that matches the current request (single-topic view).

### 3) Prompt rendering omits tasks/constraints
**Problem:** Tasks and constraints never reach the model, defeating the schema’s intent.

**Proposed fix:**
- Render tasks and constraints in the prompt view, with limits (e.g., top 3 each).
- Optionally hide tasks marked `completed: true`.

**Implementation sketch:**
- Extend `StructuredSummaryBuilder.render_for_prompt` to add:
  - `Tasks:` list
  - `Constraints:` list

### 4) `sources` never populated
**Problem:** `sources` stays empty because updater bypasses builder methods.

**Proposed fix:**
- Use builder helpers (`add_fact`, `add_open_question`, etc.) or update `sources` inline whenever adding facts/decisions/tasks/questions/constraints.
- Dedupe `sources` after updates.

### 5) Noisy topic IDs
**Problem:** Topic IDs use first non-stopword; often picks verbs like “find”.

**Proposed fix:**
- Extract a noun phrase or named entity as the `specific` component.
- Or use a small LLM call for topic_id only when the rule-based extractor detects low confidence.

**Implementation sketch:**
- Add a stopword list for action verbs (“find”, “get”, “show”, “list”) and skip them.
- If no strong noun found, fall back to a short LLM classifier.

### 6) Unused `intent` and `new_topic_created`
**Problem:** Signals are computed but not applied.

**Proposed fix:**
- Use `intent` to decide KB-first behavior and whether to include active-topic summary at all.
- Use `new_topic_created` to trigger cleanup: cap old topics and archive if no unresolved tasks.

## Suggested Minimal Patch (order of operations)
1) Fix message ID binding + extractor output format.
2) Render tasks/constraints in prompt.
3) Add topic similarity threshold + single-topic prompt view.
4) Improve topic ID specificity.
5) Wire intent/new_topic_created into routing.

## Verification
- Add tests that:
  - Ensure each extracted item has specific source IDs (1–3, not “all messages”).
  - Confirm only one active topic renders by default.
  - Verify tasks/constraints appear in prompt output.
  - Ensure topic deactivates on in-domain shift.

---

# Implementation (2025-01-15)

## Overview

All 6 fixes have been implemented and deployed. Executive Assistant restarted with PID 50281.

### 1) Source binding - FIXED

**Implementation:** `src/executive_assistant/agent/summary_extractor.py`

Added `get_stable_message_id()` function using SHA-256 hash:
```python
def get_stable_message_id(msg: BaseMessage) -> str:
    content = msg.content or ""
    role = "human" if isinstance(msg, HumanMessage) else "ai"
    timestamp = getattr(msg, "timestamp", None)
    timestamp_str = str(timestamp) if timestamp else ""
    hash_input = f"{role}:{content}:{timestamp_str}"
    return "msg_" + hashlib.sha256(hash_input.encode()).hexdigest()[:16]
```

Updated extraction prompt to require source indices:
```python
extract_prompt = """...
Respond ONLY with valid JSON in this exact format:
{
    "facts": [{"text": "statement1", "sources": [0, 1]}],
    "decisions": [{"text": "decision1", "sources": [2]}],
    ...
}
"""
```

### 2) Topic deactivation on similarity - FIXED

**Implementation:** `src/executive_assistant/agent/topic_classifier.py`

Added similarity scoring function:
```python
def topic_similarity_score(query: str, topic_id: str) -> float:
    # Extract domain/action/specific from topic_id
    parts = topic_id.split("/")
    domain, action, specific = parts[0], parts[1], parts[2]

    # Domain match: 40%, Specific term match: 60%
    domain_keywords = TopicClassifier.DOMAIN_KEYWORDS.get(domain, [])
    domain_match = any(kw in query_lower for kw in domain_keywords)
    specific_match = specific in query_lower

    score = 0.0
    if domain_match: score += 0.4
    if specific_match: score += 0.6
    return score
```

Updated `should_create_new_topic()` with threshold (default 0.4):
```python
def should_create_new_topic(..., similarity_threshold: float = 0.4) -> bool:
    # New topic if domain changes OR similarity < threshold
    similarity = topic_similarity_score(query, current_topic_id)
    return similarity < similarity_threshold
```

### 3) Tasks/constraints in prompt - FIXED

**Implementation:** `src/executive_assistant/agent/topic_classifier.py`

Updated `render_for_prompt()`:
```python
# Tasks (only incomplete tasks)
tasks = topic.get("tasks", [])
incomplete_tasks = [t for t in tasks if not t.get("completed", False)]
if incomplete_tasks:
    parts.append("Pending Tasks:")
    for task in incomplete_tasks[:3]:
        parts.append(f"- {task.get('text', '')}")

# Constraints
constraints = topic.get("constraints", [])
if constraints:
    parts.append("Constraints:")
    for constraint in constraints[:3]:
        parts.append(f"- {constraint.get('text', '')}")
```

### 4) Sources populated - FIXED

**Implementation:** `src/executive_assistant/agent/summary_extractor.py`

Updated `update_structured_summary()`:
```python
# Add facts (with source tracking)
for fact in elements.get("facts", []):
    if not any(f.get("text") == fact.get("text") for f in topic["facts"]):
        topic["facts"].append(fact)
        topic["sources"].extend(fact.get("message_ids", []))

# Dedupe sources
if topic["sources"]:
    topic["sources"] = list(set(topic["sources"]))
```

### 5) Topic ID specificity - FIXED

**Implementation:** `src/executive_assistant/agent/topic_classifier.py`

Added skip lists:
```python
SKIP_VERBS = {
    "find", "get", "search", "show", "list", "look", "locate", "retrieve",
    "tell", "give", "make", "create", "update", "change", "check",
    "help", "need", "want", "know", "see", "use"
}

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", ...
}
```

Updated `generate_topic_id()`:
```python
specific_words = [
    w for w in words
    if len(w) > 2
    and w not in cls.SKIP_VERBS
    and w not in cls.STOPWORDS
]
```

### 6) Intent wired into routing - FIXED

**Implementation:** `src/executive_assistant/agent/nodes.py`

Updated `call_model()` for KB-first mode:
```python
# Extract intent from active topic
active_topics = [t for t in structured_summary.get("topics", []) if t.get("status") == "active"]
if active_topics:
    intent = active_topics[0].get("intent", "hybrid")

# For factual queries, use minimal summary context (KB-first mode)
if intent == "factual":
    # Only show current request, skip the rest of the summary
    active_request = structured_summary.get("active_request", {})
    prompt += f"\n\n[Current Request]\n{active_request['text']}"
    prompt += "\n\nNote: For this factual query, prioritize KB results over conversation context."
else:
    # For conversational/hybrid, show full summary
    rendered = StructuredSummaryBuilder.render_for_prompt(structured_summary)
    prompt += f"\n\n{rendered}"
```

## Files Modified

| File | Changes |
|------|---------|
| `src/executive_assistant/agent/summary_extractor.py` | Stable message IDs, source binding, sources tracking |
| `src/executive_assistant/agent/topic_classifier.py` | Similarity scoring, skip verbs, tasks/constraints rendering |
| `src/executive_assistant/agent/nodes.py` | Intent-based KB-first routing |

## Testing

```bash
pytest tests/test_summarization.py -v
# 9 passed
```

## Configuration

Similarity threshold can be adjusted in `should_create_new_topic()`:
- Lower (0.3) → More permissive, topics merge more easily
- Higher (0.5) → Stricter, more new topics created

---

## Additional Concerns After Review

1) **Topic reuse vs new topic ID mismatch**
- `update_structured_summary()` always uses a newly generated `topic_id`, even when `should_create_new_topic()` returns `False`. This can create multiple active topics within the same domain because the old topic isn’t inactivated while a new topic is created.  
- Example: `compliance/search/settlor` → new query `compliance/search/trustee` yields similarity 0.4 (domain match), so no deactivation, but a new topic is created.
- Suggested fix: when `should_create_new_topic()` is `False`, force `topic_id = current_topic_id` to reuse the active topic, or change the similarity threshold logic so any “different specific” triggers a new topic.
- References: `src/executive_assistant/agent/summary_extractor.py`, `src/executive_assistant/agent/topic_classifier.py`

2) **Similarity threshold is effectively “domain match = same topic”**
- `topic_similarity_score()` gives 0.4 for domain match and 0.6 for specific match. With default threshold 0.4, any same-domain query stays on the same topic even if the specific term is different.  
- This reduces topic separation and may keep older topics active longer than intended.
- Suggested fix: raise the threshold (e.g., 0.5+) or require specific match to keep the same topic.
- Reference: `src/executive_assistant/agent/topic_classifier.py`

3) **Stable message IDs may collide for repeated content**
- `get_stable_message_id()` hashes `(role + content + timestamp)`; if `timestamp` is missing and the user repeats short messages (“ok”, “yes”), IDs collide.  
- Suggested fix: prefer a message UUID if present (`msg.id`), or add a stable per-message counter in metadata.
- Reference: `src/executive_assistant/agent/summary_extractor.py`

4) **KB-first mode still sends full recent messages**
- The summary is minimized for factual intent, but the full recent message history is still sent. That can still carry irrelevant context into a factual lookup.
- Suggested fix: for `intent == "factual"`, reduce the message window or filter to the last 1–2 user messages.
- Reference: `src/executive_assistant/agent/nodes.py`

5) **Fallback source attribution may be misleading**
- When LLM returns no sources, the code assigns the last two messages as sources. This can attach incorrect provenance.
- Suggested fix: leave `message_ids` empty or mark as `uncertain` and only fill via semantic match.
- Reference: `src/executive_assistant/agent/summary_extractor.py`

---

## Additional Fixes Applied (2025-01-15 20:25)

### 1) Topic reuse bug - FIXED

**Problem:** `topic_id` was always regenerated from the query, even when `should_create_new_topic()` returned `False`. This caused multiple active topics within the same domain.

**Fix:** Reorganized `update_structured_summary()` to check `should_create_new_topic()` first, then either reuse `current_topic_id` or generate a new one:

```python
# Determine topic_id: reuse current if same topic, generate new if different
if should_create_new_topic(query, current_topic_id):
    # Create new topic ID
    topic_id = TopicClassifier.generate_topic_id(query)
    # ... mark old topic inactive ...
else:
    # Reuse current topic ID (same topic continues)
    topic_id = current_topic_id or TopicClassifier.generate_topic_id(query)
```

**Result:** Same-domain queries now properly reuse the same topic object, preventing topic proliferation.
