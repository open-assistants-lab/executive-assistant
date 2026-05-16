"""Tests for Observational Memory pipeline.

Covers: ObservationStore CRUD, Observer output parsing, observation injection,
token counting, middleware hooks, memory_get_profile tool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.sdk.messages import Message
from src.sdk.middleware_observation import ObservationMiddleware
from src.sdk.state import AgentState
from src.sdk.tools_core.observation import (
    OBSERVER_PROMPT,
    REFLECTOR_PROMPT,
    _parse_observer_json,
    _parse_reflector_json,
)
from src.storage.observation import (
    ObservationStore,
    _observation_store_cache,
    get_observation_store,
)


@pytest.fixture(autouse=True)
def clear_obs_cache() -> None:
    _observation_store_cache.clear()
    yield
    _observation_store_cache.clear()


@pytest.fixture
def temp_dir(tmp_path: Path) -> str:
    return str(tmp_path)


@pytest.fixture
def obs_store(tmp_path: Path) -> ObservationStore:
    import uuid
    uid = f"test_{uuid.uuid4().hex[:8]}"
    store_dir = tmp_path / "obs_test"
    store_dir.mkdir(exist_ok=True)
    return ObservationStore(uid, base_dir=str(store_dir))


class TestObservationStore:
    def test_create_store(self, obs_store: ObservationStore) -> None:
        assert obs_store.db is not None

    def test_insert_and_get_observations(self, obs_store: ObservationStore) -> None:
        obs_store.insert_observations(
            [
                {
                    "content": "user moved to Denver",
                    "priority": "🔴",
                    "observation_ts": "2026-05-01T00:00:00+00:00",
                }
            ]
        )
        recent = obs_store.get_recent_observations(days=30, limit=10)
        assert len(recent) == 1
        assert recent[0]["content"] == "user moved to Denver"
        assert recent[0]["priority"] == "🔴"

    def test_insert_batch_observations(self, obs_store: ObservationStore) -> None:
        obs_store.insert_observations(
            [
                {"content": "fact 1", "priority": "🟢"},
                {"content": "fact 2", "priority": "🟡"},
                {"content": "fact 3", "priority": "🔴"},
            ]
        )
        recent = obs_store.get_recent_observations(days=30, limit=10)
        assert len(recent) == 3

    def test_recent_observations_respects_days(self, obs_store: ObservationStore) -> None:
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        new = datetime.now(UTC).isoformat()
        obs_store.insert_observations(
            [
                {"content": "old event", "observation_ts": old},
                {"content": "new event", "observation_ts": new},
            ]
        )
        recent = obs_store.get_recent_observations(days=7, limit=10)
        assert len(recent) == 1
        assert recent[0]["content"] == "new event"

    def test_insert_and_get_reflection(self, obs_store: ObservationStore) -> None:
        obs_store.insert_reflection(
            {
                "reflection_text": "condensed summary of user activity",
                "observation_count": 10,
                "token_count": 42,
            }
        )
        refl = obs_store.get_latest_reflection()
        assert refl is not None
        assert "condensed summary" in refl["content"]

    def test_search_observations(self, obs_store: ObservationStore) -> None:
        obs_store.insert_observations(
            [
                {"content": "user discussed hiking in Colorado"},
                {"content": "user discussed cooking Italian food"},
            ]
        )
        results = obs_store.search_observations("hiking", limit=5)
        assert len(results) >= 1

    def test_search_reflections(self, obs_store: ObservationStore) -> None:
        obs_store.insert_reflection({"reflection_text": "summary mentioning kayaking"})
        results = obs_store.search_reflections("kayaking", limit=5)
        assert len(results) >= 1

    def test_get_all_observations(self, obs_store: ObservationStore) -> None:
        obs_store.insert_observations(
            [
                {"content": "a", "observation_ts": "2026-01-01T00:00:00+00:00"},
                {"content": "b", "observation_ts": "2026-06-01T00:00:00+00:00"},
            ]
        )
        all_obs = obs_store.get_all_observations()
        assert len(all_obs) == 2
        assert all_obs[0]["observation_ts"] < all_obs[1]["observation_ts"]

    def test_empty_store_returns_none(self, obs_store: ObservationStore) -> None:
        assert obs_store.get_latest_reflection() is None
        assert obs_store.get_recent_observations() == []


class TestObserverParsing:
    def test_parse_valid_json_array(self) -> None:
        text = '[{"content": "user moved", "priority": "🔴"}]'
        result = _parse_observer_json(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "user moved"

    def test_parse_json_in_code_block(self) -> None:
        text = '```json\n[{"content": "test", "priority": "🟢"}]\n```'
        result = _parse_observer_json(text)
        assert result is not None
        assert len(result) == 1

    def test_parse_adds_observation_ts(self) -> None:
        text = '[{"content": "test", "priority": "🟡"}]'
        result = _parse_observer_json(text)
        assert result is not None
        assert "observation_ts" in result[0]

    def test_parse_invalid_json_returns_none(self) -> None:
        result = _parse_observer_json("not json at all")
        assert result is None

    def test_parse_json_with_regex_fallback(self) -> None:
        text = 'Some text [{"content": "nested", "priority": "🟢"}] more text'
        result = _parse_observer_json(text)
        assert result is not None
        assert result[0]["content"] == "nested"

    def test_parse_reflector_valid_json(self) -> None:
        text = (
            '{"id": "refl_1", "reflection_text": "summary", '
            '"dropped_observation_ids": ["obs_1"]}'
        )
        result = _parse_reflector_json(text)
        assert result is not None
        assert result["reflection_text"] == "summary"

    def test_parse_reflector_in_markdown_block(self) -> None:
        text = '```json\n{"reflection_text": "summary", "id": "refl_x"}\n```'
        result = _parse_reflector_json(text)
        assert result is not None
        assert result["reflection_text"] == "summary"


class TestObserverPrompt:
    def test_prompt_contains_format_keys(self) -> None:
        assert "conversation" in OBSERVER_PROMPT

    def test_prompt_formats_correctly(self) -> None:
        formatted = OBSERVER_PROMPT.format(conversation="hello")
        assert "hello" in formatted

    def test_reflector_prompt_contains_format_keys(self) -> None:
        assert "observations" in REFLECTOR_PROMPT

    def test_reflector_prompt_formats_correctly(self) -> None:
        formatted = REFLECTOR_PROMPT.format(observations="[test]")
        assert "[test]" in formatted


class TestObservationMiddleware:
    @pytest.fixture
    def mw(self, tmp_path: Path) -> ObservationMiddleware:
        import uuid
        store_dir = tmp_path / "mw_test"
        store_dir.mkdir(exist_ok=True)
        return ObservationMiddleware(
            f"mw_{uuid.uuid4().hex[:8]}",
            base_dir=str(store_dir),
        )

    def test_init(self, mw: ObservationMiddleware) -> None:
        assert mw._turns_since_observer == 0
        assert mw._observer_running is False
        assert mw._observation_store is not None

    def test_before_agent_no_observations(self, mw: ObservationMiddleware) -> None:
        state = AgentState()
        result = mw.before_agent(state)
        assert result is None

    def test_before_agent_with_observations(self, mw: ObservationMiddleware) -> None:
        mw._observation_store.insert_observations(
            [
                {
                    "content": "user discussed hiking",
                    "priority": "🟡",
                    "observation_ts": datetime.now(UTC).isoformat(),
                }
            ]
        )
        state = AgentState(messages=[Message.user("hello")])
        result = mw.before_agent(state)
        assert result is not None
        assert "messages" in result
        system_msgs = [m for m in result["messages"] if m.role == "system"]
        assert len(system_msgs) == 1
        assert "hiking" in str(system_msgs[0].content)

    def test_after_agent_increments_turn(self, mw: ObservationMiddleware) -> None:
        state = AgentState()
        mw.after_agent(state)
        assert mw._turns_since_observer == 1

    def test_token_estimation(self, mw: ObservationMiddleware) -> None:
        tokens = mw._estimate_tokens("hello world")
        assert tokens > 0

    def test_truncate_text(self, mw: ObservationMiddleware) -> None:
        long_text = "word " * 1000
        truncated = mw._truncate_text(long_text, max_tokens=50)
        assert len(truncated) < len(long_text)
        assert "truncated" in truncated

    def test_count_unobserved_tokens(self, mw: ObservationMiddleware) -> None:
        tokens = mw._count_unobserved_tokens()
        assert tokens >= 0

    def test_format_working_memory_block(self, mw: ObservationMiddleware) -> None:
        wm = {"block_text": "sample memory", "total_tokens": 10, "sections": []}
        block = mw._format_working_memory_block(wm)
        assert "Working Memory" in block
        assert "sample memory" in block


class TestMemoryGetProfile:
    def test_get_profile_returns_string(self) -> None:
        import uuid

        from src.sdk.tools_core.memory import memory_get_profile
        from src.storage.observation import ObservationStore

        uid = f"prof_{uuid.uuid4().hex[:8]}"
        store = ObservationStore(uid, workspace_id="test_ws")
        store.insert_observations(
            [
                {
                    "content": "user prefers dark mode",
                    "priority": "🟡",
                    "observation_ts": datetime.now(UTC).isoformat(),
                }
            ]
        )
        result = memory_get_profile.function(user_id=uid)
        assert isinstance(result, str)
        assert "dark mode" in result

    def test_get_profile_empty(self) -> None:
        import uuid

        from src.sdk.tools_core.memory import memory_get_profile

        result = memory_get_profile.function(user_id=f"empty_{uuid.uuid4().hex[:8]}")
        assert isinstance(result, str)


class TestGetObservationStore:
    def test_singleton_cache(self) -> None:
        import uuid
        uid = f"cache_{uuid.uuid4().hex[:8]}"
        store1 = get_observation_store(uid)
        store2 = get_observation_store(uid)
        assert store1 is store2

    def test_different_users(self) -> None:
        import uuid
        store1 = get_observation_store(f"user_a_{uuid.uuid4().hex[:8]}")
        store2 = get_observation_store(f"user_b_{uuid.uuid4().hex[:8]}")
        assert store1 is not store2
