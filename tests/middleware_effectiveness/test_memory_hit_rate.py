"""Effectiveness tests for memory retrieval accuracy.

Measure memory hit rate.
Target: 90%+ of queries retrieve relevant information.

Hit rate = (queries that found relevant memories) / (total queries)
"""

from __future__ import annotations

import pytest
from src.memory import MemoryCreate, MemoryType, MemorySource


class TestMemoryHitRate:
    """Test memory retrieval hit rate accuracy.

    Target: 90%+ hit rate for relevant queries.
    """

    def test_hit_rate_for_profile_queries(self, mock_memory_store):
        """Test hit rate for profile information queries."""
        # Add profile information
        profile_memories = [
            MemoryCreate(
                title="VP Engineering based in SF",
                type=MemoryType.PROFILE,
                narrative="User is VP of Engineering based in San Francisco, PST timezone",
                facts=["VP Engineering", "San Francisco", "PST"],
                confidence=0.95,
                source=MemorySource.EXPLICIT,
            ),
            MemoryCreate(
                title="Reports to CTO",
                type=MemoryType.PROFILE,
                narrative="User reports directly to the CTO",
                facts=["Reports to CTO", "Executive team"],
                confidence=0.9,
                source=MemorySource.EXPLICIT,
            ),
            MemoryCreate(
                title="10 years experience",
                type=MemoryType.PROFILE,
                narrative="User has 10 years of engineering experience",
                facts=["10 years experience", "Engineering background"],
                confidence=0.85,
                source=MemorySource.EXPLICIT,
            ),
        ]

        for memory in profile_memories:
            mock_memory_store.add(memory)

        # Test queries
        queries = [
            ("What's my role?", ["VP", "Engineering"]),
            ("Where am I based?", ["San Francisco", "SF"]),
            ("Who do I report to?", ["CTO"]),
            ("How much experience do I have?", ["10 years"]),
        ]

        hits = 0
        for query, expected_keywords in queries:
            from src.memory import MemorySearchParams
            results = mock_memory_store.search(
                MemorySearchParams(query=query, limit=5)
            )

            # Check if any result contains expected keywords
            if results:
                result_text = " ".join(
                    f"{r.title} {r.narrative or ''}" for r in results
                ).lower()

                if any(kw.lower() in result_text for kw in expected_keywords):
                    hits += 1

        hit_rate = hits / len(queries)
        assert hit_rate >= 0.90, (
            f"Profile query hit rate is {hit_rate:.1%}, target is 90%+"
        )

        print(f"\nProfile Hit Rate: {hit_rate:.1%} ({hits}/{len(queries)} queries)")

    def test_hit_rate_for_preference_queries(self, mock_memory_store):
        """Test hit rate for preference queries."""
        # Add preference information
        preferences = [
            MemoryCreate(
                title="Prefers async communication",
                type=MemoryType.PREFERENCE,
                narrative="User prefers asynchronous communication over real-time meetings",
                facts=["Async", "Slack over Zoom"],
                confidence=0.9,
                source=MemorySource.EXPLICIT,
            ),
            MemoryCreate(
                title="Likes Python",
                type=MemoryType.PREFERENCE,
                narrative="User prefers Python for backend development",
                facts=["Python", "Backend"],
                confidence=0.85,
                source=MemorySource.EXPLICIT,
            ),
            MemoryCreate(
                title="Prefers code reviews",
                type=MemoryType.PREFERENCE,
                narrative="User values thorough code reviews",
                facts=["Code reviews", "Quality"],
                confidence=0.8,
                source=MemorySource.EXPLICIT,
            ),
        ]

        for pref in preferences:
            mock_memory_store.add(pref)

        # Test queries
        queries = [
            ("What are my communication preferences?", ["async", "slack"]),
            ("What programming language do I like?", ["python"]),
            ("Do I like code reviews?", ["reviews"]),
        ]

        hits = 0
        for query, expected_keywords in queries:
            from src.memory import MemorySearchParams
            results = mock_memory_store.search(
                MemorySearchParams(query=query, limit=5)
            )

            if results:
                result_text = " ".join(
                    f"{r.title} {r.narrative or ''}" for r in results
                ).lower()

                if any(kw.lower() in result_text for kw in expected_keywords):
                    hits += 1

        hit_rate = hits / len(queries)
        assert hit_rate >= 0.90, (
            f"Preference query hit rate is {hit_rate:.1%}, target is 90%+"
        )

    def test_hit_rate_for_task_queries(self, mock_memory_store):
        """Test hit rate for task queries."""
        # Add tasks
        tasks = [
            MemoryCreate(
                title="Submit budget by Friday",
                type=MemoryType.TASK,
                narrative="User needs to submit budget proposal by Friday 5 PM",
                facts=["Budget", "Friday", "Deadline"],
                confidence=0.9,
                source=MemorySource.EXPLICIT,
            ),
            MemoryCreate(
                title="Review project X",
                type=MemoryType.TASK,
                narrative="Review and approve Project X documentation",
                facts=["Project X", "Review", "Approval"],
                confidence=0.85,
                source=MemorySource.EXPLICIT,
            ),
        ]

        for task in tasks:
            mock_memory_store.add(task)

        # Test queries
        queries = [
            ("What deadlines do I have?", ["friday", "deadline"]),
            ("What tasks need approval?", ["review", "approve"]),
        ]

        hits = 0
        for query, expected_keywords in queries:
            from src.memory import MemorySearchParams
            results = mock_memory_store.search(
                MemorySearchParams(query=query, limit=5)
            )

            if results:
                result_text = " ".join(
                    f"{r.title} {r.narrative or ''}" for r in results
                ).lower()

                if any(kw.lower() in result_text for kw in expected_keywords):
                    hits += 1

        hit_rate = hits / len(queries)
        # Allow slightly lower for tasks (less structured)
        assert hit_rate >= 0.85, (
            f"Task query hit rate is {hit_rate:.1%}, target is 85%+"
        )

    def test_hit_rate_with_varied_query_phrasing(self, mock_memory_store):
        """Test hit rate with different ways of asking the same question."""
        # Add a memory
        mock_memory_store.add(
            MemoryCreate(
                title="Prefers async communication",
                type=MemoryType.PREFERENCE,
                narrative="User prefers async communication over meetings",
                confidence=0.9,
                source=MemorySource.EXPLICIT,
            )
        )

        # Different ways to ask
        query_variations = [
            "What are my communication preferences?",
            "Do I prefer async or sync communication?",
            "How do I like to communicate?",
            "Async or real-time meetings?",
            "What's my preference for meetings?",
        ]

        hits = 0
        for query in query_variations:
            from src.memory import MemorySearchParams
            results = mock_memory_store.search(
                MemorySearchParams(query=query, limit=5)
            )

            if results:
                result_text = " ".join(
                    f"{r.title} {r.narrative or ''}" for r in results
                ).lower()

                if "async" in result_text:
                    hits += 1

        hit_rate = hits / len(query_variations)
        assert hit_rate >= 0.80, (
            f"Varied query hit rate is {hit_rate:.1%}, target is 80%+"
        )

    def test_hit_rate_false_positive_rate(self, mock_memory_store):
        """Test that irrelevant queries don't return memories (low false positive rate)."""
        # Add specific memories
        mock_memory_store.add(
            MemoryCreate(
                title="Python preference",
                type=MemoryType.PREFERENCE,
                narrative="User prefers Python for development",
                confidence=0.9,
                source=MemorySource.EXPLICIT,
            )
        )

        # Irrelevant queries (should return empty or unrelated)
        irrelevant_queries = [
            "What's the weather?",
            "Tell me about cooking",
            "Who won the game?",
            "What's for dinner?",
        ]

        false_positives = 0
        for query in irrelevant_queries:
            from src.memory import MemorySearchParams
            results = mock_memory_store.search(
                MemorySearchParams(query=query, limit=5)
            )

            # Should return empty or results not matching Python
            if results:
                result_text = " ".join(
                    f"{r.title} {r.narrative or ''}" for r in results
                ).lower()

                if "python" in result_text:
                    false_positives += 1

        false_positive_rate = false_positives / len(irrelevant_queries)

        # Target: <10% false positive rate
        assert false_positive_rate < 0.10, (
            f"False positive rate is {false_positive_rate:.1%}, target is <10%"
        )


class TestMemoryRetrievalLatency:
    """Test memory retrieval performance."""

    def test_search_latency(self, mock_memory_store):
        """Test that search completes quickly."""
        import time

        # Add some memories
        for i in range(20):
            mock_memory_store.add(
                MemoryCreate(
                    title=f"Memory {i}",
                    type=MemoryType.INSIGHT,
                    narrative=f"Test memory content {i}",
                    confidence=0.8,
                    source=MemorySource.LEARNED,
                )
            )

        # Measure search latency
        from src.memory import MemorySearchParams

        start = time.time()
        results = mock_memory_store.search(
            MemorySearchParams(query="test", limit=10)
        )
        duration = time.time() - start

        # Should complete in <1 second
        assert duration < 1.0, f"Search took {duration:.3f}s, target is <1s"

    def test_get_latency(self, mock_memory_store):
        """Test that get_many completes quickly."""
        import time

        # Add memories
        ids = []
        for i in range(10):
            memory = mock_memory_store.add(
                MemoryCreate(
                    title=f"Memory {i}",
                    type=MemoryType.INSIGHT,
                    narrative=f"Content {i}",
                    confidence=0.8,
                    source=MemorySource.LEARNED,
                )
            )
            ids.append(memory)

        # Measure get latency
        start = time.time()
        memories = mock_memory_store.get_many(ids)
        duration = time.time() - start

        # Should complete in <0.5 seconds
        assert duration < 0.5, f"Get took {duration:.3f}s, target is <0.5s"
