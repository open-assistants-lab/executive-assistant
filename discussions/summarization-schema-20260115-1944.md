# Executive Assistant Summarization Schema + Update Rules (v1)

## Goals
- Prevent summary-driven confusion by making the latest user intent explicit and dominant.
- Keep summaries faithful (no new tasks or assumptions) and traceable to source messages.
- Scale to long threads without losing rare-but-critical details.

## Design Principles
- Intent-first: the first line must state the current user request in plain language.
- Topic separation: summarize by topic, not by time alone.
- Recency bias: latest user messages override earlier summaries.
- Fidelity: do not carry assistant boilerplate or suggestions unless the user accepted them.
- Traceability: each summary bullet is tied to one or more message IDs.

## Summary Schema (stored in DB as JSON, rendered as text for prompt)

### Structured record (storage)
```json
{
  "thread_id": "...",
  "active_request": {
    "text": "Find relevant AML clause about settlor",
    "topic_id": "compliance/aml/settlor",
    "message_ids": ["m_123"]
  },
  "topics": [
    {
      "topic_id": "compliance/aml/settlor",
      "status": "active",
      "last_updated": "2026-01-15T19:42:00Z",
      "facts": [
        {"text": "User asks for specific clause related to settlor", "message_ids": ["m_123"]}
      ],
      "decisions": [],
      "tasks": [],
      "open_questions": [
        {"text": "Which jurisdiction's AML law?", "message_ids": ["m_124"]}
      ],
      "constraints": [],
      "sources": ["m_123", "m_124"]
    }
  ],
  "inactive_topics": [
    {"topic_id": "travel/flights", "reason": "superseded by new topic"}
  ]
}
```

### Prompt rendering (textual)
```
[Current Request]
Find relevant AML clause about settlor.

[Active Topic: compliance/aml/settlor]
Facts:
- User wants a specific clause about settlor.
Open Questions:
- Which jurisdiction's AML law applies?

[Inactive Topics]
- travel/flights (inactive)
```

## Update Rules (thread_id-first)
1) **Topic classification**
   - Assign each new message to a topic via embedding similarity + recency.
   - If similarity is below threshold, create a new topic.

2) **Active request update**
   - Always set `active_request.text` from the latest user message.
   - Never include assistant suggestions or boilerplate unless user explicitly accepted.

3) **Fact/decision/task extraction**
   - Extract facts, decisions, tasks, constraints, and open questions.
   - Require explicit acceptance for assistant-proposed tasks.

4) **Source binding**
   - Attach `message_ids` to each summary bullet.
   - Reject bullets without sources.

5) **Topic status**
   - Mark old topics inactive when a new topic becomes dominant and no unresolved tasks remain.

6) **Merge behavior (later)**
   - When threads are merged to a user, merge summaries by topic_id with dedupe on text hash.

## Summarization Techniques Used (and why)
- **Level 2 (Prompt templates)**: Consistent extraction of facts/decisions/tasks across chunks.
- **Level 3 (Map-Reduce)**: Summarize long histories by chunking, then reducing summaries.
- **Detail-controlled chunking**: A `detail` parameter scales the chunk count and depth, so summaries can be short or comprehensive.
- **Recursive summarization**: Use prior chunk summaries as context to reduce contradictions.
- **Representative chunk selection (coverage-aware)**: Use MMR or max-coverage to avoid missing rare details that k-means centroids can skip.
- **Agentic retrieval (Level 5)**: Only when topic is unknown; enforce budget and strict relevance filters.

## Guardrails to Avoid Confusion (like the AML case)
- **Exclude assistant templates**: do not store assistant “example responses” in summaries.
- **Single open question**: if missing jurisdiction, ask only that one question.
- **Topic boundary**: travel planning and AML compliance must never be in the same active topic.

## Implementation Notes (fits current code)
- Current summarizer lives in `src/executive_assistant/agent/nodes.py` and stores a plain text `summary`.
- Suggested incremental change:
  1) Store structured JSON summary in Postgres (`conversations.summary` as JSONB).
  2) Render a compact text view for the prompt.
  3) Keep last N raw messages for nuance.

## Example Update Flow
1) New user message arrives.
2) Classify topic and set `active_request`.
3) Extract facts/open questions and attach message IDs.
4) Persist structured summary + render prompt summary.
5) Use prompt summary + last N messages when calling the model.
