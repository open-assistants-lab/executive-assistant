"""Storage selector using GoRules Zen decision engine."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import zen
from executive_assistant.storage.thread_storage import get_thread_id
from executive_assistant.storage.user_storage import UserPaths

logger = logging.getLogger(__name__)


class StorageSelector:
    """Storage selection decision engine using GoRules Zen.

    This class uses the GoRules Zen engine to deterministically select
    appropriate storage (TDB/ADB/VDB/Memory/Files) based on structured
    decision criteria.

    The engine supports user customization through per-thread rule overrides.
    """

    def __init__(self):
        """Initialize the storage selector with GoRules engine."""
        # Initialize engine with file-system loader
        self.engine = zen.ZenEngine({
            "loader": self._load_decision
        })

        # Cache for compiled decisions (ZenDecisionContent)
        self._cache: Dict[str, zen.ZenDecisionContent] = {}

    def _load_decision(self, key: str) -> zen.ZenDecisionContent:
        """
        Load decision JSON from file system with user customization support.

        Priority:
        1. User-specific rules (data/users/{thread_id}/rules/{key}.json)
        2. Global default rules (data/rules/{key}.json)

        Args:
            key: Decision name (e.g., "storage-selection")

        Returns:
            ZenDecisionContent: Compiled decision content

        Raises:
            FileNotFoundError: If decision file not found
        """
        thread_id = get_thread_id()

        # Check cache first
        cache_key = f"{thread_id}:{key}" if thread_id else f"global:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try user-specific rules first
        if thread_id:
            user_rules_path = UserPaths.get_user_root(thread_id) / "rules" / f"{key}.json"
            if user_rules_path.exists():
                logger.debug(f"Loading user decision: {user_rules_path}")
                with open(user_rules_path) as f:
                    content = zen.ZenDecisionContent(f.read())
                    self._cache[cache_key] = content
                    return content

        # Fallback to global rules
        # Go up 4 levels from: src/executive_assistant/decisions/
        global_rules_path = Path(__file__).parent.parent.parent.parent / "data" / "rules" / f"{key}.json"
        if not global_rules_path.exists():
            raise FileNotFoundError(
                f"Decision not found: {key}\n"
                f"Looked in: {global_rules_path}"
            )

        logger.debug(f"Loading global decision: {global_rules_path}")
        with open(global_rules_path) as f:
            content = zen.ZenDecisionContent(f.read())
            self._cache[cache_key] = content
            return content

    async def select_storage(
        self,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Select appropriate storage based on structured criteria.

        Args:
            criteria: Structured decision criteria with keys:
                - dataType: "preference" | "structured" | "document" | "numeric" | "unstructured"
                - complexAnalytics: bool (needs joins, window functions)
                - needsJoins: bool (needs to join multiple tables)
                - windowFunctions: bool (needs window functions)
                - semanticSearch: bool (search by meaning)
                - searchByMeaning: bool (find similar content)

        Returns:
            Dict with:
                - storage: List[str] of storage types
                - tools: List[str] of recommended tools
                - reasoning: str explanation of the decision
                - trace: Dict of execution trace (if enabled)

        Example:
            >>> criteria = {
            ...     "dataType": "structured",
            ...     "complexAnalytics": False,
            ...     "semanticSearch": False
            ... }
            >>> result = await selector.select_storage(criteria)
            >>> print(result["storage"])
            ["tdb"]
        """
        try:
            # Evaluate decision
            response = await self.engine.async_evaluate(
                "storage-selection",
                {"input": criteria}
            )

            result = response.get("result", {})

            return {
                "storage": result.get("storage", []),
                "tools": result.get("tools", []),
                "reasoning": result.get("reasoning", ""),
                "trace": response.get("trace", {})
            }

        except Exception as e:
            logger.error(f"Storage decision failed: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear the decision cache (useful for testing or rule updates)."""
        self._cache.clear()
        logger.debug("Decision cache cleared")
