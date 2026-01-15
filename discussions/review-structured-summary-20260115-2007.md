# Review: Structured Summary Implementation (2026-01-15 20:07)

## Findings
- High: Source binding is effectively broken. Each extracted element is assigned the full list of message IDs (not per-item), and IDs fall back to ephemeral `msg_{i}` values. This also tags items with IDs for messages that never made it into the truncated input. `src/cassey/agent/summary_extractor.py:45` `src/cassey/agent/summary_extractor.py:90` `src/cassey/agent/summary_extractor.py:95`
- Medium: Topic deactivation only triggers when the domain changes, so different topics within the same domain remain active and can reintroduce multi-topic contamination. `src/cassey/agent/summary_extractor.py:175` `src/cassey/agent/topic_classifier.py:216`
- Medium: Prompt rendering omits tasks and constraints, so pending actions and limitations never reach the model. This undermines the schema’s usefulness. `src/cassey/agent/topic_classifier.py:397`
- Medium: `sources` is defined in the schema but never populated because the updater bypasses builder helpers that append sources. Any downstream audit/filters will see empty `sources`. `src/cassey/agent/summary_extractor.py:211` `src/cassey/agent/topic_classifier.py:348`
- Low: Topic IDs are noisy because `generate_topic_id` uses the first non-stopword, which often captures verbs like “find” instead of the entity. This increases topic sprawl. `src/cassey/agent/topic_classifier.py:100`
- Low: `intent` and `new_topic_created` are computed but unused, suggesting intended behavior isn’t wired. `src/cassey/agent/summary_extractor.py:167`

## Open Questions / Assumptions
- Should prompt rendering include only the active request’s topic (single-topic view) or multiple active topics?
- Do you want tasks/constraints visible to the model, or intentionally hidden?
- Are message IDs stable in your message objects, or should you generate/persist them?

## Change Summary
- Structured summaries are now extracted and persisted, but traceability, topic lifecycle, and prompt rendering don’t fully match the intent-first, source-bound design.

## Tests
- Not run (review only).
