"""Memory learning middleware for extracting and saving memories from conversations.

Supports two modes:
- Rule-based: Simple pattern matching (no LLM required)
- LLM-based: Uses LLM for intelligent extraction

Memory types: profile, contact, preference, schedule, task, decision,
              insight, context, goal, chat, feedback, personal
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone as dt_timezone
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware

from src.memory import MemoryStore, MemoryCreate, MemoryType, MemorySource

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentState
    from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class MemoryLearningMiddleware(AgentMiddleware):
    """Automatically extract and save memories from conversations.

    This middleware runs after the agent completes and extracts
    structured memories using the 12 memory types.

    Usage:
        from src.memory import MemoryStore
        from src.middleware import MemoryLearningMiddleware

        store = MemoryStore(user_id="user-123", data_path=user_path)
        agent = create_deep_agent(
            model="gpt-4o",
            middleware=[MemoryLearningMiddleware(store, extraction_model=llm)],
        )
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        extraction_model: Any | None = None,
        auto_learn: bool = True,
        min_confidence: float = 0.6,
    ) -> None:
        super().__init__()
        self.memory_store = memory_store
        self.extraction_model = extraction_model
        self.auto_learn = auto_learn
        self.min_confidence = min_confidence

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Extract memories after conversation completes."""
        if not self.auto_learn or not self.memory_store:
            return None

        messages = state.get("messages", [])
        if len(messages) < 2:
            return None

        try:
            memories = self._extract_memories(messages)

            for memory_data in memories:
                if memory_data.get("confidence", 0) >= self.min_confidence:
                    self._save_memory(memory_data)

        except Exception:
            pass

        return None

    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Async version of memory extraction after agent completes."""
        if not self.auto_learn or not self.memory_store:
            logger.debug("[MemoryLearning] Skipped (auto_learn=%s, memory_store=%s)", self.auto_learn, self.memory_store is not None)
            return None

        messages = state.get("messages", [])
        if len(messages) < 2:
            logger.debug("[MemoryLearning] Skipped (not enough messages)")
            return None

        try:
            logger.debug("[MemoryLearning] Extracting memories from conversation...")
            memories = self._extract_memories(messages)
            logger.debug(f"[MemoryLearning] Found {len(memories)} candidate memories")

            saved_count = 0
            for memory_data in memories:
                if memory_data.get("confidence", 0) >= self.min_confidence:
                    memory_id = self._save_memory(memory_data)
                    if memory_id:
                        saved_count += 1
                        logger.debug(f"   ✓ Saved: {memory_data.get('type', 'unknown')} - {memory_data.get('title', 'no title')} (confidence: {memory_data.get('confidence', 0):.2f})")
                    else:
                        logger.debug(f"   ✗ Failed to save: {memory_data.get('type', 'unknown')} - {memory_data.get('title', 'no title')}")
                else:
                    logger.debug(f"   ⊘ Skipping low-confidence memory: {memory_data.get('type', 'unknown')} - {memory_data.get('title', 'no title')} (confidence: {memory_data.get('confidence', 0):.2f} < {self.min_confidence})")

            if saved_count == 0:
                logger.debug("[MemoryLearning] No memories met confidence threshold")
            else:
                logger.debug(f"[MemoryLearning] Saved {saved_count} memories")

        except Exception as e:
            logger.error(f"[MemoryLearning] Error: {e}")

        return None

    def _extract_memories(self, messages: list) -> list[dict]:
        """Extract memories from conversation messages."""
        conversation_text = self._format_conversation(messages)

        if self.extraction_model:
            return self._llm_extraction(conversation_text)

        return self._rule_extraction(messages)

    def _format_conversation(self, messages: list) -> str:
        """Format messages into a single string."""
        lines = []
        for msg in messages:
            role = msg.type if hasattr(msg, "type") else "unknown"
            content = msg.content if hasattr(msg, "content") else str(msg)

            if role == "human":
                lines.append(f"User: {content}")
            elif role == "ai":
                lines.append(f"Assistant: {content}")

        return "\n".join(lines)

    def _llm_extraction(self, conversation: str) -> list[dict]:
        """Use LLM to extract structured memories from conversation."""
        from langchain.messages import HumanMessage, SystemMessage

        prompt = f"""Analyze this conversation and extract important information about the user.

For each piece of information, provide:
1. title: Short summary (~10 words)
2. type: One of: profile, contact, preference, schedule, task, decision, insight, context, goal, chat, feedback, personal
3. narrative: Full description (~100 words)
4. facts: Array of key facts
5. concepts: Array of tags/keywords
6. confidence: 0.0-1.0

Types explained:
- profile: About the user themselves (name, role, company, timezone)
- contact: About other people (relationships, who they know)
- preference: User preferences (how they like things)
- schedule: Time commitments (meetings, events, recurring items)
- task: Todos, deadlines, deliverables
- decision: Decisions made with rationale
- insight: Patterns observed about the user
- context: Background info, project context
- goal: Goals and aspirations
- chat: Casual sharing, venting, personal updates
- feedback: User's feelings about the assistant
- personal: Family, health, hobbies, non-work life

Conversation:
{conversation[:4000]}

Return JSON array. Example:
[
  {{
    "title": "Prefers async communication",
    "type": "preference",
    "narrative": "User prefers asynchronous communication over real-time meetings for non-urgent matters.",
    "facts": ["Prefers Slack over Zoom", "Responds faster to written messages"],
    "concepts": ["communication", "productivity", "async"],
    "confidence": 0.9
  }}
]

Only extract meaningful, non-obvious information. Return empty array if nothing significant."""

        try:
            response = self.extraction_model.invoke(
                [SystemMessage(content=prompt), HumanMessage(content="Extract memories now.")]
            )

            content = response.content
            if isinstance(content, str):
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
        except Exception:
            pass

        return []

    def _rule_extraction(self, messages: list) -> list[dict]:
        """Extract memories using simple rules (no LLM)."""
        memories = []

        for msg in messages:
            content = msg.content if hasattr(msg, "content") else ""
            if not isinstance(content, str):
                continue

            content_lower = content.lower()

            preferences = self._extract_preferences(content, content_lower)
            memories.extend(preferences)

            facts = self._extract_profile_facts(content, content_lower)
            memories.extend(facts)

            tasks = self._extract_tasks(content, content_lower)
            memories.extend(tasks)

            contacts = self._extract_contacts(content, content_lower)
            memories.extend(contacts)

        return memories

    def _extract_preferences(self, text: str, text_lower: str) -> list[dict]:
        """Extract preference-type memories."""
        memories = []
        indicators = [
            ("i prefer", "prefers"),
            ("i like", "likes"),
            ("i'd rather", "would rather"),
            ("my preference", "preference is"),
            ("always use", "always wants"),
            ("never use", "never wants"),
            ("please use", "requests using"),
            ("i want", "wants"),
            ("i need", "needs"),
        ]

        for indicator, prefix in indicators:
            if indicator in text_lower:
                idx = text_lower.find(indicator)
                rest = text[idx + len(indicator) :].strip()
                rest = re.split(r"[.!?,]", rest)[0].strip()

                if len(rest) > 5 and len(rest) < 100:
                    memories.append(
                        {
                            "title": f"{prefix.title()} {rest[:50]}",
                            "type": "preference",
                            "narrative": f"User {prefix} {rest}.",
                            "facts": [f"{prefix.title()} {rest}"],
                            "concepts": ["preference"],
                            "confidence": 0.7,
                            "source": "explicit",
                        }
                    )

        return memories[:2]

    def _extract_profile_facts(self, text: str, text_lower: str) -> list[dict]:
        """Extract profile-type memories."""
        memories = []
        indicators = [
            ("i am a", "is a"),
            ("i work at", "works at"),
            ("i work for", "works for"),
            ("my role is", "role is"),
            ("i'm a", "is a"),
            ("my name is", "name is"),
            ("i'm based in", "is based in"),
            ("i live in", "lives in"),
        ]

        for indicator, prefix in indicators:
            if indicator in text_lower:
                idx = text_lower.find(indicator)
                rest = text[idx + len(indicator) :].strip()
                rest = re.split(r"[.!?,]", rest)[0].strip()

                if len(rest) > 3 and len(rest) < 100:
                    memories.append(
                        {
                            "title": f"User {prefix} {rest[:50]}",
                            "type": "profile",
                            "narrative": f"User {prefix} {rest}.",
                            "facts": [f"{prefix.title()} {rest}"],
                            "concepts": ["profile"],
                            "confidence": 0.85,
                            "source": "explicit",
                        }
                    )

        return memories[:2]

    def _extract_tasks(self, text: str, text_lower: str) -> list[dict]:
        """Extract task-type memories."""
        memories = []
        patterns = [
            r"i need to (.+?)(?:by|before|on)\s+(\w+\s+\d+)",
            r"don't forget (?:to\s+)?(.+)",
            r"remind me to (.+)",
            r"deadline (?:for\s+)?(.+?)\s+is\s+(.+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if isinstance(match, tuple):
                    task_desc = match[0].strip()
                else:
                    task_desc = match.strip()

                if len(task_desc) > 5 and len(task_desc) < 100:
                    memories.append(
                        {
                            "title": f"Task: {task_desc[:50].title()}",
                            "type": "task",
                            "narrative": f"User needs to {task_desc}.",
                            "facts": [f"Task: {task_desc}"],
                            "concepts": ["task", "todo"],
                            "confidence": 0.75,
                            "source": "explicit",
                        }
                    )

        return memories[:2]

    def _extract_contacts(self, text: str, text_lower: str) -> list[dict]:
        """Extract contact-type memories."""
        memories = []

        patterns = [
            r"my (boss|manager|colleague|friend|partner) (?:is|name is) (\w+)",
            r"(\w+) (?:is my|from) (boss|manager|colleague|friend|partner)",
            r"(?:talked to|met with|spoke with) (\w+)(?:\s+about\s+(.+))?",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if len(match) >= 2:
                    name = (
                        match[1]
                        if match[0] in ["boss", "manager", "colleague", "friend", "partner"]
                        else match[0]
                    )
                    context = match[2] if len(match) > 2 else match[0]

                    if name and len(name) > 1:
                        memories.append(
                            {
                                "title": f"Contact: {name.title()}",
                                "type": "contact",
                                "narrative": f"User mentioned {name} - their {context}.",
                                "facts": [f"{name.title()} - {context}"],
                                "concepts": ["contact", "relationship"],
                                "confidence": 0.7,
                                "source": "learned",
                            }
                        )

        return memories[:2]

    def _save_memory(self, memory_data: dict) -> None:
        """Save a memory to the store."""
        try:
            memory_type = MemoryType(memory_data.get("type", "insight"))
        except ValueError:
            memory_type = MemoryType.INSIGHT

        try:
            source = MemorySource(memory_data.get("source", "learned"))
        except ValueError:
            source = MemorySource.LEARNED

        try:
            data = MemoryCreate(
                title=memory_data.get("title", "Untitled"),
                type=memory_type,
                narrative=memory_data.get("narrative"),
                facts=memory_data.get("facts", []),
                concepts=memory_data.get("concepts", []),
                entities=memory_data.get("entities", []),
                project=memory_data.get("project"),
                confidence=memory_data.get("confidence", 0.7),
                source=source,
            )

            self.memory_store.add(data)
        except Exception:
            pass
