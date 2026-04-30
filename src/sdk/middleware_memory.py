"""Memory middleware for extracting and injecting learned behavioral patterns.

SDK-native implementation: replaces src/middleware/memory.py.
Uses SDK Middleware base class instead of LangChain AgentMiddleware.
"""

import json
import os
import threading
from typing import Any

from src.app_logging import get_logger
from src.sdk.memory_planner import is_memory_query, plan_memory_query
from src.sdk.messages import Message
from src.sdk.middleware import Middleware
from src.sdk.state import AgentState
from src.storage.memory import (
    DEFAULT_CONFIDENCE,
    MAX_CONFIDENCE,
    MEMORY_DETAIL_SUMMARY,
    MEMORY_TYPE_CORRECTION,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_WORKFLOW,
    SOURCE_LEARNED,
    get_memory_store,
)

logger = get_logger()

EXTRACTION_TURN_INTERVAL = 3

CORRECTION_KEYWORDS = [
    "no ",
    "don't ",
    "don't do",
    "not like",
    "wrong",
    "actually",
    "instead",
    "please don't",
    "never",
    "avoid",
    "not that",
    "i meant",
    "not what",
    "that's not",
    "stop",
    "dislike",
    "correction",
    "update:",
    "actually no",
    "wait ",
    "hold on",
]

PREFERENCE_KEYWORDS = [
    "i prefer",
    "i like",
    "i want",
    "i love",
    "i hate",
    "i don't like",
    "always",
    "never",
    "usually",
    "i'm used to",
    "i'm comfortable with",
    "my favorite",
    "i'm a fan of",
    "better with",
    "instead of",
]

NEW_INFO_KEYWORDS = [
    "i am ",
    "i'm ",
    "i was",
    "my name is",
    "i live in",
    "i work at",
    "i'm from",
    "i've been",
    "i do",
    "i'm a",
    "i'm an",
    "i speak",
    "speak ",
    "speaks ",
]

EXTRACTION_PROMPT = """You are a user information extraction system. Extract factual information about the user that should be remembered for future conversations.

## EXTRACTION RULES:
1. Extract CONCRETE FACTS: names, locations, dates, numbers, preferences, changes, corrections
2. Each memory trigger should be a specific fact query (e.g., "user's name" not "when user asks about name")
3. Each memory action should be the EXACT factual answer (e.g., "Jordan Mitchell" not "respond with stored info")
4. Do NOT extract meta-observations about the conversation itself
5. Prioritize FACTS and CORRECTIONS over workflow patterns

## MEMORY TYPES (pick one):

| Type | When to use |
|------|-------------|
| **fact** | Factual info about user (name, location, job, family, pets, etc) |
| **preference** | User expresses what they want/prefer (likes, dislikes, wants) |
| **correction** | User corrects previous info ("I moved to...", "actually it's...") |
| **workflow** | User's working patterns or habits (less common) |

## DOMAINS (for categorization):

| Domain | What to extract |
|--------|-----------------|
| personal | Name, age, family, bio |
| work | Role, company, team, seniority |
| location | City, country, timezone |
| interests | Topics, hobbies, passions |
| skills | Experience, expertise, tech stack |
| goals | Objectives, targets, ambitions |
| constraints | Limitations, requirements |
| communication | Style preferences (concise, bullet points, etc) |
| tools | Preferred tools, software |
| languages | Spoken/programming languages |
| correction | Corrections to AI responses |
| workflow | Habits, processes |
| lesson | Things taught to AI |
| dislikes | Explicitly unwanted |

## STRUCTURED DATA:

For **fact** type memories, include structured fields:
```json
{{"entity": "user", "attribute": "property name", "value": "the exact value", "previous_value": "optional old value", "effective_at": "optional date/time"}}
```

Examples:
- User says "My name is Jordan Mitchell" → trigger="user's name", action="Jordan Mitchell", structured_data={{"entity":"user","attribute":"name","value":"Jordan Mitchell"}}
- User says "I moved to Denver" → trigger="user's location", action="Denver", structured_data={{"entity":"user","attribute":"location","value":"Denver"}}
- User says "My new manager is Tom, not Karen" → trigger="user's manager", action="Tom", structured_data={{"entity":"user","attribute":"manager","value":"Tom","previous_value":"Karen"}}

For **workflow** type memories, include steps:
```json
{{"steps": ["step 1", "step 2"]}}
```

For **correction** type memories, include old and new:
```json
{{"old_value": "what was wrong", "new_value": "what is correct"}}
```

## OUTPUT (JSON array):

```json
[
  {{"trigger": "when [situation]", "action": "what the user wants", "domain": "domain_name", "memory_type": "preference|fact|workflow|correction", "confidence": 0.0-1.0, "structured_data": {{}}}}
]
```

Only return valid JSON with patterns that are WORTH remembering. Less is more.

Conversation:
{conversation}

Extracted patterns (JSON):"""

EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "trigger": {"type": "string"},
            "action": {"type": "string"},
            "domain": {"type": "string"},
            "memory_type": {
                "type": "string",
                "enum": [
                    MEMORY_TYPE_PREFERENCE,
                    MEMORY_TYPE_FACT,
                    MEMORY_TYPE_WORKFLOW,
                    MEMORY_TYPE_CORRECTION,
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "structured_data": {"type": "object"},
        },
        "required": ["trigger", "action", "domain", "memory_type", "confidence"],
    },
}


class MemoryMiddleware(Middleware):
    """Middleware that extracts and injects learned memories.

    Uses turn-based extraction (every N turns) instead of keyword detection,
    with keyword detection as a correction signal amplifier.

    SDK-native: extends Middleware instead of LangChain AgentMiddleware.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id or "default_user"
        self.memory_store = get_memory_store(self.user_id)
        self._model: Any = None
        self._turn_count = 0

    def _get_model(self) -> Any | None:
        if self._model is None:
            try:
                from src.sdk.providers.factory import create_model_from_config

                settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
                model_str = getattr(settings.agent, "model", "ollama:minimax-m2.5")
                self._model = create_model_from_config(model_str)
            except Exception as e:
                logger.warning(
                    "memory.model_unavailable",
                    {"error": str(e)},
                    user_id=self.user_id,
                )
                return None
        return self._model

    def _get_message_content(self, msg: Message) -> str:
        content = msg.content
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
        return str(content)

    def _latest_user_query(self, messages: list[Message]) -> str:
        for msg in reversed(messages):
            if msg.role == "user":
                return self._get_message_content(msg).strip()
        return ""

    def _get_relevant_memory_context(self, query: str) -> str:
        if os.environ.get("MEMORY_QUERY_PLANNER_ENABLED", "false").lower() not in {
            "1",
            "true",
            "yes",
        }:
            return self._get_baseline_memory_context(query)

        plan = plan_memory_query(query)
        if plan.intent == "unknown":
            return ""

        sections: list[str] = []
        fact_memories = []

        try:
            fact_memories = (
                self.memory_store.find_facts_for_query(query, limit=plan.max_facts)
                if plan.needs_current_facts
                else []
            )
            if fact_memories:
                sections.append("### Exact Structured Facts")
                for memory in fact_memories:
                    sd = memory.structured_data
                    previous = sd.get("previous_value")
                    previous_text = f" (previous: {previous})" if previous else ""
                    sections.append(
                        f"- {sd.get('entity', 'user')}.{sd.get('attribute', memory.trigger)} = "
                        f"{sd.get('value', memory.action)}{previous_text}"
                    )

            if plan.needs_fact_history:
                temporal_facts = self.memory_store.find_fact_history_for_query(
                    query, limit=plan.max_history
                )
                if temporal_facts:
                    sections.append("### Temporal / Update History")
                    for memory in temporal_facts:
                        sd = memory.structured_data
                        status = "current" if not memory.is_superseded else "superseded"
                        effective_at = sd.get("effective_at") or memory.updated_at.date().isoformat()
                        previous = sd.get("previous_value")
                        previous_text = f"; previous={previous}" if previous else ""
                        sections.append(
                            f"- {effective_at} [{status}] "
                            f"{sd.get('entity', 'user')}.{sd.get('attribute', memory.trigger)} = "
                            f"{sd.get('value', memory.action)}{previous_text}"
                        )

            fact_ids = {memory.id for memory in fact_memories}
            memories = [m for m in self.memory_store.search_hybrid(query, limit=8) if m.id not in fact_ids]
            if memories:
                sections.append("### Learned Memories")
                for memory in memories[:6]:
                    sections.append(f"- [{memory.domain}] {memory.trigger}: {memory.action}")
        except Exception as e:
            logger.debug(
                "memory.query_memories_failed",
                {"error": str(e), "query": query[:100]},
                user_id=self.user_id,
            )

        needs_message_fallback = plan.intent == "current_fact" and not fact_memories
        if plan.needs_messages or needs_message_fallback:
            try:
                from src.sdk.tools_core.memory import _expand_queries
                from src.storage.messages import get_message_store

                conversation = get_message_store(self.user_id)
                seen_ids: set[int] = set()
                message_results = []
                recency_keywords = [
                    "current",
                    "latest",
                    "now",
                    "after",
                    "updated",
                    "new",
                    "recently",
                    "last",
                    "today",
                ]
                recency_weight = (
                    0.7 if any(kw in query.lower() for kw in recency_keywords) else 0.3
                )

                for expanded_query in _expand_queries(query):
                    for result in conversation.search_hybrid(
                        expanded_query,
                        limit=plan.max_messages or 5,
                        recency_weight=recency_weight,
                    ):
                        if result.id in seen_ids:
                            continue
                        seen_ids.add(result.id)
                        message_results.append(result)

                message_results.sort(key=lambda r: r.score, reverse=True)
                if message_results:
                    sections.append("### Relevant Conversation History")
                    for result in message_results[: (plan.max_messages or 5)]:
                        content = result.content.replace("\n", " ")
                        sections.append(
                            f"- {result.role} ({result.ts.date()}): {content} "
                            f"(score: {result.score:.2f})"
                        )
            except Exception as e:
                logger.debug(
                    "memory.query_messages_failed",
                    {"error": str(e), "query": query[:100]},
                    user_id=self.user_id,
                )

        if not sections:
            return ""

        logger.info(
            "memory.query_context_injected",
            {
                "query": query[:100],
                "intent": plan.intent,
                "sections": len(sections),
                "needs_history": plan.needs_fact_history,
                "needs_messages": plan.needs_messages or needs_message_fallback,
            },
            user_id=self.user_id,
        )
        return "## Relevant Memory Search Results\n" + "\n".join(sections)

    def _get_baseline_memory_context(self, query: str) -> str:
        """Best validated retrieval path: facts + learned memories + message evidence."""
        if not is_memory_query(query):
            return ""

        sections: list[str] = []

        try:
            fact_memories = self.memory_store.find_facts_for_query(query, limit=6)
            if fact_memories:
                sections.append("### Exact Structured Facts")
                for memory in fact_memories:
                    sd = memory.structured_data
                    previous = sd.get("previous_value")
                    previous_text = f" (previous: {previous})" if previous else ""
                    sections.append(
                        f"- {sd.get('entity', 'user')}.{sd.get('attribute', memory.trigger)} = "
                        f"{sd.get('value', memory.action)}{previous_text}"
                    )

            fact_ids = {memory.id for memory in fact_memories}
            memories = [m for m in self.memory_store.search_hybrid(query, limit=8) if m.id not in fact_ids]
            if memories:
                sections.append("### Learned Memories")
                for memory in memories[:6]:
                    sections.append(f"- [{memory.domain}] {memory.trigger}: {memory.action}")
        except Exception as e:
            logger.debug(
                "memory.query_memories_failed",
                {"error": str(e), "query": query[:100]},
                user_id=self.user_id,
            )

        try:
            from src.sdk.tools_core.memory import _expand_queries
            from src.storage.messages import get_message_store

            conversation = get_message_store(self.user_id)
            seen_ids: set[int] = set()
            message_results = []
            recency_keywords = [
                "current",
                "latest",
                "now",
                "after",
                "updated",
                "new",
                "recently",
                "last",
                "today",
            ]
            recency_weight = 0.7 if any(kw in query.lower() for kw in recency_keywords) else 0.3

            for expanded_query in _expand_queries(query):
                for result in conversation.search_hybrid(
                    expanded_query,
                    limit=8,
                    recency_weight=recency_weight,
                ):
                    if result.id in seen_ids:
                        continue
                    seen_ids.add(result.id)
                    message_results.append(result)

            message_results.sort(key=lambda r: r.score, reverse=True)
            if message_results:
                sections.append("### Relevant Conversation History")
                for result in message_results[:8]:
                    content = result.content.replace("\n", " ")
                    sections.append(
                        f"- {result.role} ({result.ts.date()}): {content} "
                        f"(score: {result.score:.2f})"
                    )
        except Exception as e:
            logger.debug(
                "memory.query_messages_failed",
                {"error": str(e), "query": query[:100]},
                user_id=self.user_id,
            )

        if not sections:
            return ""

        logger.info(
            "memory.query_context_injected",
            {
                "query": query[:100],
                "intent": "baseline",
                "sections": len(sections),
                "needs_history": False,
                "needs_messages": True,
            },
            user_id=self.user_id,
        )
        return "## Relevant Memory Search Results\n" + "\n".join(sections)

    def _should_extract(self, messages: list[Message]) -> bool:
        self._turn_count += 1

        if self._turn_count % EXTRACTION_TURN_INTERVAL == 0:
            return True

        if not messages:
            return False

        user_messages = [m for m in messages[-4:] if m.role == "user"]
        user_text = " ".join(self._get_message_content(m) for m in user_messages).lower()
        conversation_lower = " ".join(self._get_message_content(m) for m in messages[-6:]).lower()

        correction_count = sum(1 for kw in CORRECTION_KEYWORDS if kw in conversation_lower)
        if correction_count >= 1:
            return True

        new_info_count = sum(1 for kw in NEW_INFO_KEYWORDS if kw in user_text)
        if new_info_count >= 1:
            return True

        return False

    def before_agent(self, state: AgentState) -> dict[str, Any] | None:
        memory_context = self.memory_store.get_memory_context(detail_level=MEMORY_DETAIL_SUMMARY)
        query = self._latest_user_query(state.messages)
        query_context = self._get_relevant_memory_context(query)

        contexts = [context for context in (memory_context, query_context) if context]
        if not contexts:
            return None

        combined_context = "\n\n".join(contexts)

        current_messages = state.messages

        system_idx = None
        for i, msg in enumerate(current_messages):
            if msg.role == "system":
                system_idx = i
                break

        if system_idx is not None:
            sys_msg = current_messages[system_idx]
            content = self._get_message_content(sys_msg)
            if combined_context not in content:
                updated_content = content + "\n\n" + combined_context
                current_messages[system_idx] = Message.system(updated_content)
        else:
            current_messages.insert(0, Message.system(combined_context))

        logger.debug(
            "memory.injected",
            {"context_length": len(combined_context), "query_context": bool(query_context)},
            user_id=self.user_id,
        )

        return {"messages": current_messages}

    def after_agent(self, state: AgentState) -> dict[str, Any] | None:
        messages = state.messages
        if not messages:
            return None

        if not self._should_extract(messages):
            return None

        recent_messages = []
        for msg in messages[-8:]:
            role = msg.role
            content = self._get_message_content(msg)
            if content:
                recent_messages.append(f"{role}: {content[:500]}")

        if len(recent_messages) < 2:
            return None

        threading.Thread(
            target=self._extract_with_llm,
            args=(recent_messages,),
            daemon=True,
        ).start()

        self._check_and_trigger_consolidation()

        return None

    def _check_and_trigger_consolidation(self) -> None:
        try:
            from src.config import get_settings
            from src.storage.consolidation import on_conversation_end

            settings = get_settings()
            threshold = settings.memory.consolidate_after_messages

            if threshold <= 0:
                return

            if not hasattr(self, "_message_count"):
                self._message_count = 0
            self._message_count += 1

            if self._message_count >= threshold and self._message_count % threshold == 0:
                on_conversation_end(self.user_id, threshold)
        except Exception:
            pass

    def _extract_with_llm(self, messages: list[str]) -> None:
        try:
            model = self._get_model()
            if model is None:
                return

            conversation = "\n\n".join(messages)
            prompt = EXTRACTION_PROMPT.format(conversation=conversation)

            extraction_messages = [
                Message.system("You are a user pattern extraction system. Return only valid JSON."),
                Message.user(prompt),
            ]

            import asyncio

            from src.sdk.loop import AgentLoop

            loop = AgentLoop(provider=model)

            # Run in a background thread — create a persistent event loop
            # that stays alive for subsequent HybridDB operations (ChromaDB
            # needs an active loop for embedding generation and vector ops).
            try:
                asyncio.get_running_loop()
                raise RuntimeError("Already in event loop, use _extract_in_executor")
            except RuntimeError:
                pass

            extraction_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(extraction_loop)
            result = extraction_loop.run_until_complete(
                loop.run_single(extraction_messages)
            )

            if result is None:
                return

            content = result.content if isinstance(result.content, str) else str(result.content)
            if not isinstance(content, str):
                content = str(content)

            patterns = self._parse_json_response(content)

            is_correction = self._detect_correction_in_messages(messages)

            seen_triggers = set()
            for pattern in patterns:
                trigger = pattern.get("trigger", "")
                action = pattern.get("action", "")
                domain = pattern.get("domain", "preference")
                memory_type = pattern.get("memory_type", MEMORY_TYPE_PREFERENCE)
                confidence = pattern.get("confidence", DEFAULT_CONFIDENCE)
                structured_data = pattern.get("structured_data", {})

                if not trigger or not action:
                    continue

                trigger_key = (trigger.lower().strip(), domain.lower().strip())
                if trigger_key in seen_triggers:
                    continue
                seen_triggers.add(trigger_key)

                if memory_type == MEMORY_TYPE_FACT and isinstance(structured_data, dict):
                    entity = str(structured_data.get("entity") or "user").strip()
                    attribute = str(structured_data.get("attribute") or "").strip()
                    value = str(structured_data.get("value") or action).strip()
                    if attribute and value:
                        extra = {
                            k: v
                            for k, v in structured_data.items()
                            if k
                            not in {
                                "entity",
                                "attribute",
                                "value",
                                "previous_value",
                                "effective_at",
                            }
                        }
                        mem = self.memory_store.upsert_fact_memory(
                            entity=entity,
                            attribute=attribute,
                            value=value,
                            domain=domain,
                            confidence=min(confidence, MAX_CONFIDENCE),
                            source=SOURCE_LEARNED,
                            trigger=trigger,
                            previous_value=structured_data.get("previous_value"),
                            effective_at=structured_data.get("effective_at"),
                            extra=extra or None,
                        )
                        logger.info(
                            "memory.fact_upserted",
                            {
                                "id": mem.id,
                                "entity": entity,
                                "attribute": attribute,
                                "value": value,
                                "domain": domain,
                                "confidence": confidence,
                            },
                            user_id=self.user_id,
                        )
                        continue

                existing = self.memory_store.search_hybrid(trigger, limit=3)
                similar = [m for m in existing if m.domain == domain and not m.is_superseded]

                if not similar and memory_type == MEMORY_TYPE_FACT:
                    domain_memories = self.memory_store.list_memories(
                        domain=domain,
                        memory_type=memory_type,
                        min_confidence=0.5,
                        limit=10,
                    )
                    existing_same = [m for m in domain_memories if not m.is_superseded]
                    if existing_same:
                        similar = [existing_same[0]]

                if is_correction and similar:
                    old_mem = similar[0]
                    new_mem = self.memory_store.update_memory(
                        old_mem.id,
                        new_trigger=trigger,
                        new_action=action,
                        new_domain=domain,
                        new_structured_data=structured_data if structured_data else None,
                    )
                    if new_mem:
                        self.memory_store.supersede_memory(old_mem.id, new_mem.id)
                        self.memory_store.add_connection(
                            new_mem.id, old_mem.id, relationship="corrects"
                        )
                        logger.info(
                            "memory.corrected",
                            {
                                "old_trigger": old_mem.trigger,
                                "new_trigger": trigger,
                                "old_action": old_mem.action,
                                "new_action": action,
                            },
                            user_id=self.user_id,
                        )
                else:
                    self.memory_store.add_memory(
                        trigger=trigger,
                        action=action,
                        confidence=min(confidence, MAX_CONFIDENCE),
                        domain=domain,
                        source=SOURCE_LEARNED,
                        memory_type=memory_type,
                        structured_data=structured_data if structured_data else None,
                    )

                    logger.info(
                        "memory.extracted",
                        {
                            "trigger": trigger,
                            "action": action,
                            "domain": domain,
                            "memory_type": memory_type,
                            "confidence": confidence,
                        },
                        user_id=self.user_id,
                    )

        except Exception as e:
            logger.warning(
                "memory.extraction_failed",
                {"error": str(e)},
                user_id=self.user_id,
            )

    def _detect_correction_in_messages(self, messages: list[str]) -> bool:
        conversation_text = " ".join(m[-500:] for m in messages if m.strip()).lower()
        return any(kw in conversation_text for kw in CORRECTION_KEYWORDS)

    def _parse_json_response(self, content: str) -> list[dict[str, Any]]:
        content = content.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        content = content.strip()

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(content[start:end])
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    pass

        return []

    def retrieve_longterm_memories(self, query: str, limit: int = 10) -> list[Any]:
        return self.memory_store.search_hybrid(query, limit=limit)

    def trigger_consolidation(self) -> None:
        try:
            from src.storage.consolidation import trigger_consolidation

            trigger_consolidation(self.user_id)
        except Exception:
            pass


__all__ = ["MemoryMiddleware", "EXTRACTION_TURN_INTERVAL"]
