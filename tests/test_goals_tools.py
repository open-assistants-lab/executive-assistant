"""Tests for minimal goals tools."""

from __future__ import annotations

from typing import Generator
from uuid import uuid4

import pytest

from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.tools.goals_tools import create_goal, list_goals, update_goal


def _extract_goal_id(result: str) -> str:
    marker = "Goal created: "
    assert marker in result, f"Goal creation result missing ID marker: {result}"
    return result.split(marker, 1)[1].strip()


@pytest.fixture
def test_thread_id() -> str:
    return f"test_goals_tools_{uuid4().hex[:10]}"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    set_thread_id(test_thread_id)
    yield


class TestGoalsTools:
    def test_create_and_list_goal(self, setup_thread_context: None) -> None:
        created = create_goal.invoke(
            {
                "title": "Ship weekly report",
                "category": "short_term",
                "priority": 7,
                "importance": 8,
            }
        )
        goal_id = _extract_goal_id(created)
        assert len(goal_id) >= 8

        listed = list_goals.invoke({"limit": 10})
        assert "ship weekly report" in listed.lower()

    def test_update_goal_by_prefix_with_progress(self, setup_thread_context: None) -> None:
        created = create_goal.invoke(
            {
                "title": "Build onboarding checklist",
                "category": "medium_term",
                "priority": 6,
                "importance": 9,
            }
        )
        goal_id = _extract_goal_id(created)

        updated = update_goal.invoke(
            {
                "goal_id": goal_id[:8],
                "status": "in_progress",
                "progress": 35.0,
            }
        )
        assert "goal updated" in updated.lower()
        assert "in_progress" in updated.lower()
        assert "35.0%" in updated.lower()

    def test_update_goal_not_found(self, setup_thread_context: None) -> None:
        result = update_goal.invoke({"goal_id": "missing_goal", "status": "completed"})
        assert "not found" in result.lower()

    def test_thread_isolation(self, setup_thread_context: None) -> None:
        create_goal.invoke(
            {
                "title": "Thread one goal",
                "category": "short_term",
                "priority": 5,
                "importance": 5,
            }
        )
        listed_current = list_goals.invoke({"limit": 10})
        assert "thread one goal" in listed_current.lower()

        set_thread_id(f"test_goals_tools_other_{uuid4().hex[:8]}")
        listed_other = list_goals.invoke({"limit": 10})
        assert "thread one goal" not in listed_other.lower()

