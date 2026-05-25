"""Tests for research tools."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.sdk.research import ExperimentResult


class TestResearchTools:
    def test_research_list_empty(self):
        """research_list returns 'not found' when no experiments exist."""
        from src.sdk.tools_core.research import research_list

        result = research_list.invoke({
            "user_id": "test_user",
            "workspace_id": "personal",
        })

        assert "No research experiments found" in result

    def test_research_list_with_results(self):
        """research_list reads from existing results.tsv."""
        from src.sdk.tools_core.research import research_list

        base = Path("data") / "private" / "research" / "t_user" / "t_ws"
        base.mkdir(parents=True, exist_ok=True)
        tsv = base / "results.tsv"
        tsv.write_text(
            "commit\tdirty\tval_metric\tmemory_gb\tstatus\tdescription\n"
            "abc1234\t0\t0.950000\t0.5\tkeep\tBetter prompt\n"
        )

        try:
            result = research_list.invoke({
                "user_id": "t_user",
                "workspace_id": "t_ws",
            })
            assert "abc1234" in result
            assert "0.950000" in result
            assert "Better prompt" in result
            assert "keep" in result
        finally:
            import shutil
            shutil.rmtree(base.parent, ignore_errors=True)

    def test_format_result(self):
        """_format_result produces expected string."""
        from src.sdk.tools_core.research import _format_result

        r = ExperimentResult(
            target_name="test",
            metric_value=0.85,
            improved=True,
            commit_hash="def5678",
            description="Improved specificity",
            status="keep",
        )
        formatted = _format_result(r)
        assert "Improved specificity" in formatted
        assert "0.8500" in formatted
        assert "def5678" in formatted
        assert "improved" in formatted
