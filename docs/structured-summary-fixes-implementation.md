# Structured Summary Fixes - Implementation Documentation

**Date:** 2025-01-15
**Reference:** `review-structured-summary-fixes-20260115-2007.md`

## Overview

This document describes the fixes applied to the structured summary implementation to address context contamination and improve topic isolation. The core issue was that conversation summaries from previous topics (e.g., "Kris's flights") were bleeding into unrelated queries (e.g., "AML settlor clauses"), causing incorrect responses.

## Issues Fixed

### 1. Source Binding Broken (HIGH)

**Problem:** All summary items were getting the full list of message IDs (`msg_{i}`), and IDs were ephemeral - regenerated on each summarization cycle. This made it impossible to trace which specific messages supported each extracted fact/decision/task.

**Solution:**

1. **Stable Message IDs** (`summary_extractor.py`):
   - Created `get_stable_message_id()` function using SHA-256 hash
   - Hash input: `{role}:{content}:{timestamp}`
   - Returns: `msg_{16_char_hash}` - persists across summarization cycles

```python
def get_stable_message_id(msg: BaseMessage) -> str:
    content = msg.content or ""
    role = "human" if isinstance(msg, HumanMessage) else "ai"
    timestamp = getattr(msg, "timestamp", None)
    timestamp_str = str(timestamp) if timestamp else ""
    hash_input = f"{role}:{content}:{timestamp_str}"
    return "msg_" + hashlib.sha256(hash_input.encode()).hexdigest()[:16]
```

2. **Source Binding in Extraction**:
   - Updated `extract_conversation_elements()` to ask LLM for message indices
   - LLM prompt now requires: `[{"text": "...", "sources": [0, 1]}]`
   - Indices mapped to stable message IDs
   - Fallback to last 2 messages if no sources specified

### 2. Tasks and Constraints Not Rendered in Prompt

**Problem:** The schema defined `tasks` and `constraints` fields, but `render_for_prompt()` never included them in the output sent to the model.

**Solution:**

Updated `StructuredSummaryBuilder.render_for_prompt()` in `topic_classifier.py`:

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

### 3. Topic Deactivation Only on Domain Change

**Problem:** In-domain topic shifts (e.g., from "Kris's flights" to "AML settlor" within compliance domain) kept multiple active topics, causing context contamination.

**Solution:**

Added topic similarity scoring and threshold-based deactivation:

```python
def topic_similarity_score(query: str, topic_id: str) -> float:
    """
    Calculate similarity between query and topic_id (0.0 to 1.0).
    - Domain match: 40%
    - Specific term match: 60%
    """
    parts = topic_id.split("/")
    domain, action, specific = parts[0], parts[1], parts[2]

    domain_keywords = TopicClassifier.DOMAIN_KEYWORDS.get(domain, [])
    domain_match = any(kw in query_lower for kw in domain_keywords)
    specific_match = specific in query_lower

    score = 0.0
    if domain_match:
        score += 0.4
    if specific_match:
        score += 0.6
    return score

def should_create_new_topic(..., similarity_threshold: float = 0.4) -> bool:
    # Creates new topic if:
    # 1. Domain changes, OR
    # 2. Similarity < threshold (prevents in-domain contamination)
    similarity = topic_similarity_score(query, current_topic_id)
    return similarity < similarity_threshold
```

### 4. Sources Never Populated

**Problem:** The `sources` field in each topic stayed empty because `update_structured_summary()` directly appended to lists instead of using builder methods that tracked sources.

**Solution:**

Updated `update_structured_summary()` to track sources when adding elements:

```python
# Add facts (with source tracking)
for fact in elements.get("facts", []):
    if not any(f.get("text") == fact.get("text") for f in topic["facts"]):
        topic["facts"].append(fact)
        topic["sources"].extend(fact.get("message_ids", []))

# ... same for decisions, tasks, open_questions, constraints

# Dedupe sources
if topic["sources"]:
    topic["sources"] = list(set(topic["sources"]))
```

### 5. Noisy Topic IDs

**Problem:** Topic IDs used the first significant word, which was often an action verb like "find" or "get" instead of the actual subject.

**Solution:**

Added skip lists for action verbs and stopwords in `topic_classifier.py`:

```python
SKIP_VERBS = {
    "find", "get", "search", "show", "list", "look", "locate", "retrieve",
    "tell", "give", "make", "create", "update", "change", "check",
    "help", "need", "want", "know", "see", "use"
}

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", ...
}

def generate_topic_id(cls, query: str) -> str:
    words = re.findall(r"\b\w+\b", query_lower)
    specific_words = [
        w for w in words
        if len(w) > 2
        and w not in cls.SKIP_VERBS
        and w not in cls.STOPWORDS
    ]
    specific = specific_words[0][:20] if specific_words else "misc"
    return f"{domain}/{action}/{specific}"
```

**Example:** `"find settlor clauses"` → `compliance/search/settlor` (not `compliance/search/find`)

### 6. Unused Intent Signal

**Problem:** The `intent` field was computed but never used to influence agent behavior.

**Solution:**

Wired intent into `call_model()` in `nodes.py` for KB-first routing:

```python
# Extract intent from active topic
active_topics = [t for t in structured_summary.get("topics", []) if t.get("status") == "active"]
if active_topics:
    intent = active_topics[0].get("intent", "hybrid")

# For factual queries, use minimal summary context (KB-first mode)
if intent == "factual":
    # Only show current request, skip the rest of the summary
    # This prevents context contamination for factual lookups
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
| `src/executive_assistant/agent/summary_extractor.py` | Added `get_stable_message_id()`, updated extraction to bind sources, updated `update_structured_summary()` to track sources |
| `src/executive_assistant/agent/topic_classifier.py` | Added `SKIP_VERBS`, `STOPWORDS`, `topic_similarity_score()`, updated `generate_topic_id()`, updated `should_create_new_topic()`, updated `render_for_prompt()` to include tasks/constraints |
| `src/executive_assistant/agent/nodes.py` | Updated `call_model()` to use intent for KB-first routing |

## Testing

All existing tests pass:
```bash
pytest tests/test_summarization.py -v
# 9 passed
```

## Expected Behavior Changes

1. **Factual queries** (e.g., "find settlor clauses"):
   - Only current request shown in prompt
   - KB results prioritized over conversation summary
   - Prevents contamination from unrelated topics

2. **Topic transitions**:
   - New topic created when similarity < 0.4
   - Old topic marked inactive if no unresolved tasks
   - Only ONE active topic shown in prompt at a time

3. **Source traceability**:
   - Each fact/decision/task has specific message IDs
   - Sources survive summarization cycles (stable IDs)

4. **Better topic IDs**:
   - `compliance/search/settlor` instead of `compliance/search/find`
   - More descriptive and useful for topic operations

## Configuration

The similarity threshold can be adjusted in `should_create_new_topic()`:

```python
def should_create_new_topic(
    query: str,
    current_topic_id: str | None,
    model: BaseChatModel | None = None,
    similarity_threshold: float = 0.4,  # Adjust this
) -> bool:
```

- Lower threshold (0.3) → More permissive, topics merge more easily
- Higher threshold (0.5) → Stricter, more new topics created

## Future Enhancements

1. **Embedding-based similarity**: Replace keyword-based similarity with vector embeddings for more accurate topic matching

2. **Topic archival**: Persist inactive topics to database for historical analysis

3. **Intent refinement**: Add more granular intent categories (e.g., "definition", "comparison", "procedural")

4. **Source verification**: Add validation that source message IDs actually exist in the conversation history
