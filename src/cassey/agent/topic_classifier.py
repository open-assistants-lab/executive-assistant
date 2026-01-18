"""Topic classifier for conversation summarization.

Implements rule-based topic classification with LLM fallback.
Topics are hierarchical (e.g., "compliance/aml/settlor") to enable semantic operations.
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from cassey.config import settings

# Topic classification result
TopicIntent = Literal["factual", "conversational", "hybrid"]


class TopicClassifier:
    """
    Classify conversation messages into topics for structured summarization.

    Uses rule-based classification first (fast, deterministic) with LLM fallback
    for ambiguous cases.
    """

    # Domain keyword mappings for rule-based classification
    DOMAIN_KEYWORDS = {
        "compliance": ["compliance", "regulation", "aml", "kyc", "settlor", "trustee",
                      "clause", "section", "act", "law", "legal", "regulatory"],
        "finance": ["revenue", "cost", "budget", "financial", "expense", "profit",
                    "investment", "portfolio", "asset", "liability"],
        "travel": ["flight", "hotel", "booking", "trip", "travel", "airport",
                  "reservation", "itinerary", "vacation", "visa", "passport"],
        "technical": ["code", "function", "api", "debug", "error", "bug",
                     "deploy", "server", "database", "query", "schema"],
        "general": ["help", "how to", "what is", "explain", "tell me"],
    }

    # Action keywords for sub-topic classification
    ACTION_KEYWORDS = {
        "search": ["find", "search", "look for", "locate", "get", "retrieve"],
        "store": ["save", "store", "keep", "remember", "archive"],
        "analyze": ["analyze", "check", "review", "examine", "assess"],
        "create": ["create", "make", "build", "generate", "new"],
        "update": ["update", "change", "modify", "edit", "revise"],
    }

    # Action verbs to skip when extracting topic "specific" component
    # These are common verbs that shouldn't become the topic identifier
    SKIP_VERBS = {
        "find", "get", "search", "show", "list", "look", "locate", "retrieve",
        "tell", "give", "make", "create", "update", "change", "check",
        "help", "need", "want", "know", "see", "use"
    }

    # Stopwords to filter out
    STOPWORDS = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
        "her", "was", "one", "our", "out", "with", "has", "have", "been",
        "is", "of", "to", "in", "that", "it", "as", "be", "this", "from",
        "or", "by", "an", "will", "at", "on", "do", "if", "my", "me"
    }

    # Factual query indicators
    FACTUAL_PATTERNS = [
        r"\bfind\b",
        r"\bsearch\b",
        r"\blocate\b",
        r"\bwhat\s+(is|are|does)\b",
        r"\blist\b",
        r"\bshow\b",
        r"\bget\b",
        r"\bwhich\b",
        r"\bclause\b",
        r"\bsection\b",
    ]

    @classmethod
    def classify_intent(cls, query: str) -> TopicIntent:
        """
        Classify query intent for routing (factual vs conversational).

        Args:
            query: User's query text

        Returns:
            "factual" for lookup/search queries
            "conversational" for discussion/chat
            "hybrid" for both
        """
        query_lower = query.lower()

        # Check for factual patterns
        for pattern in cls.FACTUAL_PATTERNS:
            if re.search(pattern, query_lower):
                # Check if it has conversational elements too
                if any(word in query_lower for word in ["think", "opinion", "feel", "believe"]):
                    return "hybrid"
                return "factual"

        # Check for conversational patterns
        conversational_words = [
            "think", "opinion", "feel", "believe", "maybe", "could be",
            "what do you", "how about", "tell me about"
        ]
        if any(word in query_lower for word in conversational_words):
            return "conversational"

        # Default to hybrid for ambiguous queries
        return "hybrid"

    @classmethod
    def generate_topic_id(cls, query: str, model: BaseChatModel | None = None) -> str:
        """
        Generate a hierarchical topic ID from the query.

        Format: {domain}/{action}/{specific}

        Examples:
            - "compliance/search/settlor"
            - "travel/book/flight"
            - "technical/debug/error"

        Args:
            query: User's query text
            model: Optional LLM for ambiguous cases

        Returns:
            Hierarchical topic ID string
        """
        query_lower = query.lower()

        # Find domain
        domain = "general"
        for d, keywords in cls.DOMAIN_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                domain = d
                break

        # Find action
        action = "query"
        for a, keywords in cls.ACTION_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                action = a
                break

        # Extract specific terms (skip action verbs and stopwords)
        words = re.findall(r"\b\w+\b", query_lower)
        specific_words = [
            w for w in words
            if len(w) > 2
            and w not in cls.SKIP_VERBS
            and w not in cls.STOPWORDS
        ]

        if specific_words:
            # Use the most specific noun/term (first non-verb word)
            specific = specific_words[0][:20]  # Limit to 20 chars
        else:
            specific = "misc"

        return f"{domain}/{action}/{specific}"

    @classmethod
    async def classify_with_llm(
        cls,
        query: str,
        model: BaseChatModel,
    ) -> tuple[TopicIntent, str]:
        """
        Classify using LLM for ambiguous cases.

        Args:
            query: User's query text
            model: LLM for classification

        Returns:
            Tuple of (intent, topic_id)
        """
        classifier_prompt = """Classify the user's query into:
1. Intent: "factual" (lookup/search), "conversational" (chat), or "hybrid" (both)
2. Topic ID: hierarchical format like {domain}/{action}/{specific}

Respond ONLY with JSON: {"intent": "...", "topic_id": "..."}"

Query: {query}"""

        try:
            logger.debug("🤖 TOPIC_CLASSIFIER: Starting LLM call...")
            start = time.time()
            response = await model.ainvoke([
                SystemMessage(content="You are a query classifier. Respond only with valid JSON."),
                HumanMessage(content=classifier_prompt.format(query=query))
            ])
            elapsed = time.time() - start
            logger.debug(f"🤖 TOPIC_CLASSIFIER: Done in {elapsed:.2f}s")

            result = json.loads(response.content.strip())
            intent = result.get("intent", "hybrid")
            topic_id = result.get("topic_id", cls.generate_topic_id(query))

            # Validate intent
            if intent not in ("factual", "conversational", "hybrid"):
                intent = "hybrid"

            return intent, topic_id

        except (json.JSONDecodeError, KeyError, Exception):
            # Fallback to rule-based
            return cls.classify_intent(query), cls.generate_topic_id(query)


def get_topic_id_from_summary(
    structured_summary: dict[str, Any] | None,
) -> str | None:
    """
    Extract the active topic ID from a structured summary.

    Args:
        structured_summary: The structured summary dict

    Returns:
        The active topic_id or None
    """
    if not structured_summary:
        return None

    active_request = structured_summary.get("active_request", {})
    if isinstance(active_request, dict):
        return active_request.get("topic_id")

    return None


def topic_similarity_score(query: str, topic_id: str) -> float:
    """
    Calculate similarity between a query and a topic_id.

    Returns a score from 0.0 (no similarity) to 1.0 (identical).

    Args:
        query: The new query
        topic_id: Existing topic ID (format: domain/action/specific)

    Returns:
        Similarity score
    """
    query_lower = query.lower()

    # Extract domain/action/specific from topic_id
    parts = topic_id.split("/")
    if len(parts) < 3:
        return 0.0

    domain, action, specific = parts[0], parts[1], parts[2]

    # Check domain match
    domain_keywords = TopicClassifier.DOMAIN_KEYWORDS.get(domain, [])
    domain_match = any(kw in query_lower for kw in domain_keywords)

    # Check if query mentions the specific topic term
    specific_match = specific in query_lower

    # Calculate score
    score = 0.0
    if domain_match:
        score += 0.4  # Domain match contributes 40%
    if specific_match:
        score += 0.6  # Specific term match contributes 60%

    return score


def should_create_new_topic(
    query: str,
    current_topic_id: str | None,
    model: BaseChatModel | None = None,
    similarity_threshold: float = 0.4,
) -> bool:
    """
    Determine if a new topic should be created based on the query.

    Uses two heuristics:
    1. Domain change (always creates new topic)
    2. Low similarity within same domain (prevents contamination)

    Args:
        query: New user query
        current_topic_id: Current active topic_id
        model: Optional LLM for classification
        similarity_threshold: Minimum similarity to keep same topic (default 0.4)

    Returns:
        True if new topic should be created
    """
    if not current_topic_id:
        return True

    # Extract current domain
    current_domain = current_topic_id.split("/")[0] if "/" in current_topic_id else "general"

    # Generate new topic id
    new_topic_id = TopicClassifier.generate_topic_id(query)
    new_domain = new_topic_id.split("/")[0] if "/" in new_topic_id else "general"

    # Always create new topic if domain changes
    if current_domain != new_domain:
        return True

    # Within same domain, check similarity
    similarity = topic_similarity_score(query, current_topic_id)

    # If similarity is below threshold, create new topic even in same domain
    # This prevents "Kris's flights" from bleeding into "AML settlor" queries
    return similarity < similarity_threshold


class StructuredSummaryBuilder:
    """
    Build and update structured summaries following the schema.

    Schema:
    {
        "active_request": {"text": str, "topic_id": str, "message_ids": [str]},
        "topics": [
            {
                "topic_id": str,
                "status": "active" | "inactive",
                "last_updated": str (ISO timestamp),
                "facts": [{"text": str, "message_ids": [str]}],
                "decisions": [{"text": str, "message_ids": [str]}],
                "tasks": [{"text": str, "message_ids": [str]}],
                "open_questions": [{"text": str, "message_ids": [str]}],
                "constraints": [{"text": str, "message_ids": [str]}],
                "sources": [str]
            }
        ],
        "inactive_topics": [{"topic_id": str, "reason": str}]
    }
    """

    @staticmethod
    def create_empty() -> dict[str, Any]:
        """Create an empty structured summary."""
        return {
            "active_request": {},
            "topics": [],
            "inactive_topics": [],
        }

    @staticmethod
    def get_or_create_topic(
        summary: dict[str, Any],
        topic_id: str,
    ) -> dict[str, Any]:
        """
        Get existing topic or create new one.

        Args:
            summary: The structured summary dict
            topic_id: Topic ID to find/create

        Returns:
            The topic dict (created if not exists)
        """
        for topic in summary.get("topics", []):
            if topic.get("topic_id") == topic_id:
                return topic

        # Create new topic
        new_topic: dict[str, Any] = {
            "topic_id": topic_id,
            "status": "active",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "facts": [],
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "constraints": [],
            "sources": [],
        }

        if "topics" not in summary:
            summary["topics"] = []
        summary["topics"].append(new_topic)

        return new_topic

    @staticmethod
    def mark_topic_inactive(
        summary: dict[str, Any],
        topic_id: str,
        reason: str = "superseded_by_new_topic",
    ) -> None:
        """
        Mark a topic as inactive and move to inactive_topics list.

        Args:
            summary: The structured summary dict
            topic_id: Topic ID to mark inactive
            reason: Reason for inactivation
        """
        topics = summary.get("topics", [])
        for i, topic in enumerate(topics):
            if topic.get("topic_id") == topic_id:
                topic["status"] = "inactive"
                # Move to inactive_topics
                if "inactive_topics" not in summary:
                    summary["inactive_topics"] = []
                summary["inactive_topics"].append({
                    "topic_id": topic_id,
                    "reason": reason,
                })
                # Remove from active topics
                topics.pop(i)
                return

    @staticmethod
    def add_fact(
        summary: dict[str, Any],
        topic_id: str,
        text: str,
        message_ids: list[str],
    ) -> None:
        """Add a fact to a topic."""
        topic = StructuredSummaryBuilder.get_or_create_topic(summary, topic_id)
        topic["facts"].append({"text": text, "message_ids": message_ids})
        topic["sources"].extend(message_ids)
        topic["last_updated"] = datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def add_open_question(
        summary: dict[str, Any],
        topic_id: str,
        text: str,
        message_ids: list[str],
    ) -> None:
        """Add an open question to a topic."""
        topic = StructuredSummaryBuilder.get_or_create_topic(summary, topic_id)
        topic["open_questions"].append({"text": text, "message_ids": message_ids})
        topic["sources"].extend(message_ids)
        topic["last_updated"] = datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def set_active_request(
        summary: dict[str, Any],
        text: str,
        topic_id: str,
        message_ids: list[str],
    ) -> None:
        """
        Set the active request (always the latest user message).

        Args:
            summary: The structured summary dict
            text: The user's request text
            topic_id: The topic ID for this request
            message_ids: Message IDs to reference
        """
        summary["active_request"] = {
            "text": text,
            "topic_id": topic_id,
            "message_ids": message_ids,
        }

    @staticmethod
    def render_for_prompt(summary: dict[str, Any] | None) -> str:
        """
        Render structured summary as text for the prompt.

        Format:
        [Current Request]
        {active_request.text}

        [Active Topic: {topic_id}]
        Facts:
        - {fact}
        Decisions:
        - {decision}
        Tasks:
        - {task}
        Open Questions:
        - {question}
        Constraints:
        - {constraint}

        Note: Inactive topics are NOT rendered (they're archived, not context)
        """
        if not summary:
            return ""

        parts = []

        # Active request (most important - intent-first)
        active_request = summary.get("active_request", {})
        if isinstance(active_request, dict) and active_request.get("text"):
            parts.append(f"[Current Request]\n{active_request['text']}")

        # Active topics only
        active_topics = [
            t for t in summary.get("topics", [])
            if t.get("status") == "active"
        ]

        for topic in active_topics:
            topic_id = topic.get("topic_id", "unknown")
            parts.append(f"\n[Active Topic: {topic_id}]")

            # Facts
            facts = topic.get("facts", [])
            if facts:
                parts.append("Facts:")
                for fact in facts[:5]:  # Limit to 5 most recent
                    parts.append(f"- {fact.get('text', '')}")

            # Decisions
            decisions = topic.get("decisions", [])
            if decisions:
                parts.append("Decisions:")
                for decision in decisions[:3]:
                    parts.append(f"- {decision.get('text', '')}")

            # Tasks (only incomplete tasks)
            tasks = topic.get("tasks", [])
            incomplete_tasks = [t for t in tasks if not t.get("completed", False)]
            if incomplete_tasks:
                parts.append("Pending Tasks:")
                for task in incomplete_tasks[:3]:
                    parts.append(f"- {task.get('text', '')}")

            # Open questions
            open_questions = topic.get("open_questions", [])
            if open_questions:
                parts.append("Open Questions:")
                for q in open_questions[:3]:  # Limit to 3
                    parts.append(f"- {q.get('text', '')}")

            # Constraints
            constraints = topic.get("constraints", [])
            if constraints:
                parts.append("Constraints:")
                for constraint in constraints[:3]:
                    parts.append(f"- {constraint.get('text', '')}")

        return "\n".join(parts) if parts else ""
