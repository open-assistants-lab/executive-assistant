"""Memory context middleware for injecting relevant memories into prompts.

Uses progressive disclosure to minimize token usage:
- Searches memory index (Layer 1) for relevant memories
- Formats compact context for injection
- Full details fetched by agent via memory_get when needed
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import SystemMessage

from src.memory import MemoryStore, MemorySearchParams

if TYPE_CHECKING:
    from langchain.agents.middleware import ModelRequest, ModelResponse

logger = logging.getLogger(__name__)


class MemoryContextMiddleware(AgentMiddleware):
    """Inject relevant user memories into the system prompt.

    Uses progressive disclosure: searches memory index and injects compact
    context. Agent can use memory_get for full details if needed.

    Usage:
        from src.memory import MemoryStore
        from src.middleware import MemoryContextMiddleware

        store = MemoryStore(user_id="user-123", data_path=user_path)
        agent = create_deep_agent(
            model="gpt-4o",
            middleware=[MemoryContextMiddleware(store)],
        )
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        max_memories: int = 5,
        min_confidence: float = 0.7,
        include_types: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.memory_store = memory_store
        self.max_memories = max_memories
        self.min_confidence = min_confidence
        self.include_types = include_types

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        if not self.memory_store:
            return handler(request)

        query = self._extract_query(request)
        if not query:
            return handler(request)

        memories = self._search_memories(query)

        if not memories:
            return handler(request)

        memory_context = self._format_memories(memories)
        new_system = self._inject_context(request.system_message, memory_context)

        return handler(request.override(system_message=new_system))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async version of memory context injection."""
        logger.info(
            f"[MemoryContext] Called - memory_store={self.memory_store is not None}, enabled={self.max_memories} memories"
        )

        if not self.memory_store:
            return await handler(request)

        query = self._extract_query(request)
        logger.info(f"[MemoryContext] Query extracted: '{query}'")
        if not query:
            logger.debug("[MemoryContext] No query extracted")
            return await handler(request)

        memories = self._search_memories(query)
        logger.info(f"[MemoryContext] Search returned {len(memories)} memories")

        if not memories:
            logger.info(f"[MemoryContext] No memories found (min_confidence={self.min_confidence})")
            return await handler(request)

        logger.info(f"[MemoryContext] Injecting {len(memories)} memories")
        for memory in memories:
            logger.info(f"   - {memory.type}: {memory.title} (confidence: {memory.confidence:.2f})")

        memory_context = self._format_memories(memories)
        new_system = self._inject_context(request.system_message, memory_context)

        return await handler(request.override(system_message=new_system))

    def _extract_query(self, request: ModelRequest) -> str:
        """Extract search query from the last user message."""
        for msg in reversed(request.messages):
            if msg.type == "human":
                content = msg.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")
        return ""

    def _search_memories(self, query: str) -> list[Any]:
        """Search memory store for relevant memories (Layer 1 - index only)."""
        logger.info(f"[MemoryContext] Searching for: '{query}'")
        try:
            params = MemorySearchParams(
                query=query,
                limit=self.max_memories,
            )
            if self.include_types:
                pass

            results = self.memory_store.search(params)
            logger.info(f"[MemoryContext] Raw search results: {len(results)}")
            filtered = [r for r in results if r.confidence >= self.min_confidence]
            logger.info(
                f"[MemoryContext] Filtered by confidence >= {self.min_confidence}: {len(filtered)}"
            )
            return filtered
        except Exception as e:
            logger.info(f"[MemoryContext] Search error: {e}")
            return []

    def _format_memories(self, memories: list[Any]) -> str:
        """Format memories into compact context string.

        Uses progressive disclosure: only includes ID, type, and title.
        Agent can use memory_get for full details.
        """
        if not memories:
            return ""

        lines = ["## Relevant Context (from memory)", ""]
        lines.append("Use `memory_get` with IDs to fetch full details.")
        lines.append("")

        type_labels = {
            "profile": "Profile",
            "contact": "Contact",
            "preference": "Preference",
            "schedule": "Schedule",
            "task": "Task",
            "decision": "Decision",
            "insight": "Insight",
            "context": "Context",
            "goal": "Goal",
            "chat": "Chat",
            "feedback": "Feedback",
            "personal": "Personal",
        }

        for memory in memories:
            type_label = type_labels.get(memory.type, memory.type.title())
            lines.append(f"- **{type_label}**: {memory.title} `[{memory.id}]`")

        lines.append("")
        return "\n".join(lines)

    def _inject_context(
        self,
        system_message: SystemMessage,
        memory_context: str,
    ) -> SystemMessage:
        """Inject memory context into system message."""
        existing_content = system_message.content

        if isinstance(existing_content, str):
            new_content = existing_content + "\n\n" + memory_context
        elif isinstance(existing_content, list):
            new_content = list(existing_content) + [
                {"type": "text", "text": "\n\n" + memory_context}
            ]
        else:
            new_content = str(existing_content) + "\n\n" + memory_context

        return SystemMessage(content=new_content)
