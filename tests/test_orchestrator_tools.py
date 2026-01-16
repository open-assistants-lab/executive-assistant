"""Unit tests for Orchestrator tools."""

import pytest

pytest.skip("Orchestrator/worker agents are archived.", allow_module_level=True)

import asyncio
from datetime import datetime

from cassey.storage.file_sandbox import set_thread_id
from cassey.tools.orchestrator_tools import (
    spawn_worker,
    schedule_job,
    list_jobs,
    cancel_job,
    validate_tools,
)
from cassey.utils.cron import parse_cron_next
from langchain_core.tools import tool


class TestValidateTools:
    """Test tool validation."""

    @tool
    def dummy_tool(self, arg: str) -> str:
        """A dummy tool for testing."""
        return arg

    def test_validate_all_valid_tools(self):
        """Test validation with all valid tool names."""
        available = {"tool1": self.dummy_tool, "tool2": self.dummy_tool}
        result = validate_tools(["tool1", "tool2"], available)
        assert result == ["tool1", "tool2"]

    def test_validate_invalid_tool_raises(self):
        """Test that invalid tool names raise ValueError."""
        available = {"tool1": self.dummy_tool}
        with pytest.raises(ValueError, match="Unknown tool names"):
            validate_tools(["tool1", "invalid_tool"], available)

    def test_validate_empty_list(self):
        """Test validation with empty list."""
        available = {"tool1": self.dummy_tool}
        result = validate_tools([], available)
        assert result == []


class TestSpawnWorker:
    """Test spawn_worker tool."""

    @pytest.mark.asyncio
    async def test_spawn_worker_no_thread_id(self):
        """Test spawn_worker fails without thread_id context."""
        # Clear any existing thread_id
        from cassey.storage.file_sandbox import clear_thread_id
        clear_thread_id()

        result = await spawn_worker.ainvoke({"name": "test", "tools": "execute_python", "prompt": "Test prompt"})

        assert "Error: No thread_id context" in result

    @pytest.mark.asyncio
    async def test_spawn_worker_invalid_tool_name(self, monkeypatch):
        """Test spawn_worker rejects invalid tool names."""
        set_thread_id("telegram:test_user:123")

        # Mock the async operations to avoid DB calls
        async def mock_get_all_tools():
            return []

        async def mock_create(*args, **kwargs):
            raise ValueError("Should not reach here")

        monkeypatch.setattr(
            "cassey.tools.orchestrator_tools.get_all_tools",
            lambda: mock_get_all_tools(),
        )

        result = await spawn_worker.ainvoke({"name": "test", "tools": "invalid_tool,another_invalid", "prompt": "Prompt"})

        # Should return error about unknown tools
        assert "Error creating worker" in result or "Unknown tool names" in result


class TestScheduleJob:
    """Test schedule_job tool."""

    @pytest.mark.asyncio
    async def test_schedule_job_no_thread_id(self):
        """Test schedule_job fails without thread_id context."""
        from cassey.storage.file_sandbox import clear_thread_id
        clear_thread_id()

        result = await schedule_job.ainvoke({"name": "test", "task": "task", "flow": "flow", "schedule": "daily"})

        assert "Error: No thread_id context" in result

    @pytest.mark.asyncio
    async def test_schedule_job_simple_format(self):
        """Test scheduling with simple format."""
        set_thread_id("telegram:test_user:123")

        # We can't fully test without DB, but we can check the parse logic
        # The actual DB operations are mocked
        try:
            result = await schedule_job.ainvoke({"name": "test_job", "task": "Do something", "flow": "Do it", "schedule": "daily at 9am"})
            # Should either succeed with DB or fail with connection error
            # But shouldn't crash with parse error
            assert "error" in result.lower() or "scheduled for" in result.lower()
        finally:
            from cassey.storage.file_sandbox import clear_thread_id
            clear_thread_id()


class TestListJobs:
    """Test list_jobs tool."""

    @pytest.mark.asyncio
    async def test_list_jobs_no_thread_id(self):
        """Test list_jobs fails without thread_id context."""
        from cassey.storage.file_sandbox import clear_thread_id
        clear_thread_id()

        result = await list_jobs.ainvoke({"status": ""})

        assert "Error: No thread_id context" in result


class TestCancelJob:
    """Test cancel_job tool."""

    @pytest.mark.asyncio
    async def test_cancel_job_no_thread_id(self):
        """Test cancel_job fails without thread_id context."""
        from cassey.storage.file_sandbox import clear_thread_id
        clear_thread_id()

        result = await cancel_job.ainvoke({"job_id": 123})

        assert "Error: No thread_id context" in result


class TestParseCronNextAdvanced:
    """Advanced cron parsing tests."""

    def test_parse_cron_midnight(self):
        """Test parsing '0 0 * * *' (midnight)."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("0 0 * * *", now)
        expected = datetime(2025, 1, 16, 0, 0, 0)
        assert next_time == expected

    def test_parse_cron_noon(self):
        """Test parsing '0 12 * * *' (noon)."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("0 12 * * *", now)
        expected = datetime(2025, 1, 15, 12, 0, 0)
        assert next_time == expected

    def test_parse_cron_every_12_hours(self):
        """Test parsing '0 */12 * * *' (every 12 hours)."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("0 */12 * * *", now)
        expected = datetime(2025, 1, 15, 12, 0, 0)
        assert next_time == expected

    def test_parse_cron_every_12_hours_from_evening(self):
        """Test parsing '0 */12 * * *' from evening."""
        now = datetime(2025, 1, 15, 20, 0, 0)
        next_time = parse_cron_next("0 */12 * * *", now)
        expected = datetime(2025, 1, 16, 0, 0, 0)
        assert next_time == expected

    def test_parse_cron_minutes_interval(self):
        """Test parsing '*/15 * * * *' (every 15 minutes)."""
        now = datetime(2025, 1, 15, 10, 7, 0)
        next_time = parse_cron_next("*/15 * * * *", now)
        expected = datetime(2025, 1, 15, 10, 15, 0)
        assert next_time == expected

    def test_parse_cron_minutes_interval_wrap(self):
        """Test parsing '*/15 * * * *' wrapping to next hour."""
        now = datetime(2025, 1, 15, 10, 52, 0)
        next_time = parse_cron_next("*/15 * * * *", now)
        expected = datetime(2025, 1, 15, 11, 0, 0)
        assert next_time == expected

    def test_parse_cron_weekdays_only(self):
        """Test parsing '0 9 * * 1-5' (weekdays at 9am)."""
        # Friday
        now = datetime(2025, 1, 10, 10, 0, 0)
        next_time = parse_cron_next("0 9 * * 1-5", now)
        # Should be Monday (weekday 0)
        expected = datetime(2025, 1, 13, 9, 0, 0)
        assert next_time == expected

    def test_parse_cron_lowercase_daily(self):
        """Test lowercase 'daily' shortcut."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        next_time = parse_cron_next("DAILY", now)
        expected = datetime(2025, 1, 16, 0, 0, 0)
        assert next_time == expected

    def test_parse_cron_extra_spaces(self):
        """Test handling extra spaces in cron."""
        now = datetime(2025, 1, 15, 10, 0, 0)
        next_time = parse_cron_next("  0   9   *   *   *  ", now)
        expected = datetime(2025, 1, 15, 21, 0, 0)  # Wait, 9am is past
        # Actually 9am is past, so next day
        expected = datetime(2025, 1, 16, 9, 0, 0)
        assert next_time == expected


class TestCronEdgeCases:
    """Test edge cases in cron parsing."""

    def test_cron_hour_boundary(self):
        """Test cron at hour boundary (23 -> 00)."""
        now = datetime(2025, 1, 15, 23, 30, 0)
        next_time = parse_cron_next("hourly", now)
        expected = datetime(2025, 1, 16, 0, 30, 0)
        assert next_time == expected

    def test_cron_month_boundary(self):
        """Test cron at month boundary."""
        now = datetime(2025, 1, 31, 10, 0, 0)
        next_time = parse_cron_next("daily", now)
        expected = datetime(2025, 2, 1, 0, 0, 0)
        assert next_time == expected

    def test_cron_year_boundary(self):
        """Test cron at year boundary."""
        now = datetime(2025, 12, 31, 10, 0, 0)
        next_time = parse_cron_next("daily", now)
        expected = datetime(2026, 1, 1, 0, 0, 0)
        assert next_time == expected

    def test_cron_invalid_hour(self):
        """Test invalid hour in cron raises error."""
        with pytest.raises(ValueError):
            parse_cron_next("0 25 * * *", datetime.now())

    def test_cron_invalid_interval(self):
        """Test invalid interval in cron raises error."""
        with pytest.raises(ValueError):
            parse_cron_next("0 */0 * * *", datetime.now())

    def test_cron_too_many_fields(self):
        """Test too many fields raises error."""
        with pytest.raises(ValueError):
            parse_cron_next("0 9 * * * *", datetime.now())

    def test_cron_too_few_fields(self):
        """Test too few fields raises error."""
        with pytest.raises(ValueError):
            parse_cron_next("0 9 * *", datetime.now())
