"""Tests for memory tools — memory_profile and memory_reflection."""

from unittest.mock import MagicMock, patch

TEST_USER = "test_memory_user"


class TestMemoryProfile:
    def test_memory_profile_no_observations(self):
        from src.sdk.tools_core.memory import memory_profile

        with patch("src.storage.memory.get_memory_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_recent_observations.return_value = []
            mock_store_fn.return_value = mock_store

            result = memory_profile.invoke({"user_id": TEST_USER})

        assert "No observations available" in result

    def test_memory_profile_with_observations(self):
        from src.sdk.tools_core.memory import memory_profile

        with patch("src.storage.memory.get_memory_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_recent_observations.return_value = [
                {"id": "obs_1", "content": "Name is Alice",
                 "priority": "🔴", "observation_ts": "2026-05-27T12:00:00"},
                {"id": "obs_2", "content": "Works at TechCorp",
                 "priority": "🟡", "observation_ts": "2026-05-27T13:00:00"},
            ]
            mock_store_fn.return_value = mock_store

            result = memory_profile.invoke({"user_id": TEST_USER})

        assert "Name is Alice" in result
        assert "Works at TechCorp" in result
        assert "Working Memory" in result


class TestMemoryReflection:
    def test_memory_reflection_no_results(self):
        from src.sdk.tools_core.memory import memory_reflection

        with patch("src.storage.memory.get_memory_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.search_reflections.return_value = []
            mock_store_fn.return_value = mock_store

            result = memory_reflection.invoke(
                {"query": "career", "user_id": TEST_USER}
            )

        assert "No reflections found" in result

    def test_memory_reflection_with_results(self):
        from src.sdk.tools_core.memory import memory_reflection

        with patch("src.storage.memory.get_memory_store") as mock_store_fn:
            mock_store = MagicMock()
            mock_store.search_reflections.return_value = [
                {"id": "refl_1", "content": "Has strong career growth trajectory",
                 "domain": "career", "confidence": 0.85},
            ]
            mock_store_fn.return_value = mock_store

            result = memory_reflection.invoke(
                {"query": "career", "user_id": TEST_USER}
            )

        assert "career" in result
        assert "growth trajectory" in result
        mock_store.boost_reflection.assert_called_once_with("refl_1")
