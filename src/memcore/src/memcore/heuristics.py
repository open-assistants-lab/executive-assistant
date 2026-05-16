"""Deterministic post-retrieval heuristics — shared by all backends.

All heuristics are zero-LLM, purely pattern-based.
"""

import re


class SearchHeuristics:
    """Post-retrieval scoring heuristics based on MemPalace's proven patterns.

    Each heuristic applies a deterministic multiplier to results from
    the backend's raw search. Heuristics are additive — they boost or
    penalize scores without replacing the embedding ranking.
    """

    KEYWORD_OVERLAP_WEIGHT = 1.0
    TEMPORAL_BOOST_FACTOR = 0.15
    PERSON_NAME_BOOST = 0.40
    QUOTED_PHRASE_BOOST = 0.60
    COUNTING_QUESTION_SNIPPET_LENGTH = 3000
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "and", "or", "but", "not", "so", "if", "as", "than", "that",
        "this", "these", "those", "it", "its", "i", "me", "my", "we",
        "our", "you", "your", "he", "she", "they", "them", "their",
    }

    @classmethod
    def keyword_overlap(cls, query: str, content: str, score: float) -> float:
        """Boost score when query keywords appear in content.

        fused = score * (1 + weight * keyword_overlap_ratio)
        """
        q_words = {w.lower() for w in re.findall(r"\w+", query) if len(w) > 2}
        q_words -= cls.STOP_WORDS
        if not q_words:
            return score

        c_words = set(re.findall(r"\w+", content.lower()))
        overlap = len(q_words & c_words) / len(q_words)
        return score * (1 + cls.KEYWORD_OVERLAP_WEIGHT * overlap)

    @classmethod
    def temporal_boost(cls, query: str, content_ts: str | None, score: float) -> float:
        """Boost recent memories when query contains temporal cues.

        Detects patterns like 'current', 'latest', 'now', 'this year',
        'recently', 'these days' and boosts newer content.
        """
        temporal_cues = {
            "current", "latest", "now", "recently", "recent",
            "lately", "new", "newest", "these days", "this year",
            "nowadays", "updated", "today",
        }
        q_lower = query.lower()
        if not any(cue in q_lower for cue in temporal_cues):
            return score

        if not content_ts:
            return score

        try:
            from datetime import datetime
            ts = datetime.fromisoformat(content_ts)
            age_days = (datetime.now() - ts).days
            if age_days < 30:
                return score * (1 + cls.TEMPORAL_BOOST_FACTOR)
        except (ValueError, TypeError):
            pass
        return score

    @classmethod
    def person_name_boost(cls, content: str, score: float) -> float:
        """Boost content containing proper names (capitalized multi-word)."""
        names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", content)
        if names:
            return score * (1 + cls.PERSON_NAME_BOOST)
        return score

    @classmethod
    def quoted_phrase_boost(cls, query: str, content: str, score: float) -> float:
        """Boost when a quoted phrase from the query appears verbatim in content."""
        quoted = re.findall(r'"([^"]+)"', query)
        if not quoted:
            return score
        for phrase in quoted:
            if phrase.lower() in content.lower():
                return score * (1 + cls.QUOTED_PHRASE_BOOST)
        return score

    @classmethod
    def is_counting_question(cls, query: str) -> bool:
        """Detect 'how many' / 'how much total' questions."""
        q = query.lower()
        return q.startswith("how many") or "how much total" in q

    @classmethod
    def extract_date_cues(cls, query: str) -> str | None:
        """Extract a date reference from the query for temporal scoping."""
        year_match = re.search(r"\b(20\d{2})\b", query)
        if year_match:
            return year_match.group(1)

        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|"
            r"august|september|october|november|december)\b",
            query, re.IGNORECASE,
        )
        if month_match:
            return month_match.group(1)

        return None

    @classmethod
    def apply_all(cls, query: str, content: str, score: float, ts: str | None = None) -> float:
        """Apply all applicable heuristics to a single result."""
        s = cls.keyword_overlap(query, content, score)
        s = cls.temporal_boost(query, ts, s)
        s = cls.person_name_boost(content, s)
        s = cls.quoted_phrase_boost(query, content, s)
        return s
