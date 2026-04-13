"""Tests for LongMemEval benchmark harness."""

import pytest

from tests.benchmarks.longmemeval import (
    LongMemEvalAdapter,
    LongMemEvalDataset,
    LongMemEvalRunner,
)


class TestDatasetLoader:
    """Tests for the dataset loader."""

    @pytest.mark.asyncio
    async def test_download_and_load_small(self):
        """Test downloading and loading the small dataset."""
        dataset = LongMemEvalDataset()

        path = dataset.download("small")
        assert path.exists()

        instances = dataset.load("small")
        assert len(instances) > 0

    def test_dataset_stats(self):
        """Test dataset statistics."""
        dataset = LongMemEvalDataset()
        instances = dataset.load("small")

        stats = dataset.get_stats(instances)
        assert stats["total_instances"] == 500
        assert "single-session-user" in stats["type_counts"]
        assert "temporal-reasoning" in stats["type_counts"]


class TestAdapter:
    """Tests for the LongMemEval adapter."""

    def test_inject_and_retrieve(self):
        """Test injecting sessions and retrieving them."""
        adapter = LongMemEvalAdapter(user_id="test_inject")

        sessions = [
            [
                {"role": "user", "content": "Hello, my name is John."},
                {"role": "assistant", "content": "Hi John! Nice to meet you."},
            ],
            [
                {"role": "user", "content": "I live in New York."},
                {"role": "assistant", "content": "New York is a great city!"},
            ],
        ]
        dates = ["2024-01-01T10:00:00Z", "2024-01-02T14:30:00Z"]

        adapter.inject_sessions(sessions, dates)

        verification = adapter.verify_injection()
        assert verification["total_messages"] == 4
        assert verification["user_messages"] == 2
        assert verification["assistant_messages"] == 2

    def test_format_sessions(self):
        """Test session formatting."""
        from tests.benchmarks.longmemeval import format_sessions_as_context

        sessions = [
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        ]
        dates = ["2024-01-01T10:00:00Z"]

        context = format_sessions_as_context(sessions, dates, format_type="natural")
        assert "2024-01-01" in context
        assert "Hello" in context
        assert "Hi there!" in context


class TestRunner:
    """Tests for the evaluation runner."""

    @pytest.mark.asyncio
    async def test_runner_creation(self):
        """Test that runner can be created."""
        runner = LongMemEvalRunner(user_id="test_runner", skip_abstention=True)
        assert runner is not None
        assert runner.skip_abstention is True
