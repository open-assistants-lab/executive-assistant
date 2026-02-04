"""Integration tests for the complete unified context system (4 pillars).

Tests all four pillars working together:
1. Memory (Semantic) - "Who you are"
2. Journal (Episodic) - "What you did"
3. Instincts (Procedural) - "How you behave"
4. Goals (Intentions) - "Why/Where"
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from executive_assistant.storage.mem_storage import MemoryStorage
from executive_assistant.storage.journal_storage import JournalStorage
from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite
from executive_assistant.storage.goals_storage import GoalsStorage


class TestFourPillarIntegration:
    """Integration tests for all four pillars working together."""

    @pytest.fixture
    def context_systems(self, tmp_path):
        """Create all four storage systems for testing."""
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_integration"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Memory (Semantic)
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        # Journal (Episodic)
        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        # Instincts (Procedural)
        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        # Goals (Intentions)
        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        return {
            "memory": memory,
            "journal": journal,
            "instincts": instincts,
            "goals": goals,
            "thread_id": thread_id,
        }

    def test_all_four_pillars_work_together(self, context_systems):
        """Test that all four pillars can be used together."""
        memory = context_systems["memory"]
        journal = context_systems["journal"]
        instincts = context_systems["instincts"]
        goals = context_systems["goals"]
        thread_id = context_systems["thread_id"]

        # 1. Memory: Store user facts
        memory.create_memory(
            content="Name: Alice, Role: Product Manager at Acme",
            memory_type="declarative",
            thread_id=thread_id,
        )
        memory.create_memory(
            content="Prefers brief responses with bullet points",
            memory_type="preference",
            thread_id=thread_id,
        )

        # 2. Journal: Log activities
        journal.add_entry(
            content="Built sales dashboard with Python and Streamlit",
            entry_type="raw",
            thread_id=thread_id,
        )
        journal.add_entry(
            content="Created API endpoints for customer data",
            entry_type="raw",
            thread_id=thread_id,
        )
        journal.add_entry(
            content="Fixed authentication bug in login flow",
            entry_type="raw",
            thread_id=thread_id,
        )

        # 3. Instincts: Learn behavioral patterns
        instincts.create_instinct(
            trigger="user asks for report",
            action="use bullet points",
            domain="format",
            confidence=0.9,
            thread_id=thread_id,
        )
        instincts.create_instinct(
            trigger="morning interaction",
            action="be detailed and thorough",
            domain="timing",
            confidence=0.8,
            thread_id=thread_id,
        )

        # 4. Goals: Set objectives
        goals.create_goal(
            title="Launch sales dashboard",
            description="Complete and deploy sales analytics dashboard",
            category="short_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Verify all four systems have data
        # Memory
        memories = memory.list_memories(thread_id=thread_id)
        assert len(memories) >= 2

        # Journal
        entries = journal.list_entries(thread_id=thread_id)
        assert len(entries) >= 3

        # Instincts
        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(learned) >= 2

        # Goals
        user_goals = goals.list_goals(thread_id=thread_id)
        assert len(user_goals) >= 1

    def test_cross_pillar_search(self, context_systems):
        """Test searching across all pillars for relevant context."""
        memory = context_systems["memory"]
        journal = context_systems["journal"]
        thread_id = context_systems["thread_id"]

        # Add diverse data
        memory.create_memory(
            content="Project: Sales Analytics Dashboard",
            memory_type="work",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Built sales dashboard with revenue charts",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Created customer segmentation analysis",
            entry_type="raw",
            thread_id=thread_id,
        )

        # Search for "sales dashboard"
        results = journal.search(
            query="sales dashboard",
            thread_id=thread_id,
            limit=5,
        )

        assert len(results) >= 1
        assert any("sales" in r["content"].lower() for r in results)

    def test_comprehensive_context_retrieval(self, context_systems):
        """Test retrieving complete context from all pillars."""
        memory = context_systems["memory"]
        journal = context_systems["journal"]
        instincts = context_systems["instincts"]
        goals = context_systems["goals"]
        thread_id = context_systems["thread_id"]

        # Populate all pillars
        # Memory
        memory.create_memory(
            content="Name: Bob, Role: Data Analyst",
            memory_type="identity",
            thread_id=thread_id,
        )

        # Journal
        journal.add_entry(
            content="Analyzed customer churn data",
            entry_type="raw",
            thread_id=thread_id,
        )

        # Instincts
        instincts.create_instinct(
            trigger="analysis task",
            action="provide visualizations",
            domain="content",
            confidence=0.8,
            thread_id=thread_id,
        )

        # Goals
        goals.create_goal(
            title="Complete churn analysis",
            category="short_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Retrieve complete context
        context = {
            "memory": memory.list_memories(thread_id=thread_id),
            "journal": journal.list_entries(thread_id=thread_id, limit=5),
            "instincts": instincts.list_instincts(thread_id=thread_id, apply_decay=False),
            "goals": goals.list_goals(thread_id=thread_id, status="planned"),
        }

        # Verify all pillars have data
        assert len(context["memory"]) >= 1
        assert len(context["journal"]) >= 1
        assert len(context["instincts"]) >= 1
        assert len(context["goals"]) >= 1


class TestPerformanceWithLargeDataset:
    """Performance tests with realistic data volumes."""

    @pytest.fixture
    def large_dataset(self, tmp_path):
        """Create systems with large dataset."""
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_performance"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        return {"journal": journal, "thread_id": thread_id}

    def test_search_performance_with_100_entries(self, large_dataset):
        """Test search performance with 100 journal entries."""
        journal = large_dataset["journal"]
        thread_id = large_dataset["thread_id"]

        # Add 100 entries
        for i in range(100):
            journal.add_entry(
                content=f"Activity {i}: {['built', 'fixed', 'created', 'analyzed'][i % 4]} "
                       f"{['dashboard', 'API', 'database', 'report'][i % 4]}",
                entry_type="raw",
                thread_id=thread_id,
            )

        # Search should be fast
        import time
        start = time.time()
        results = journal.search(query="dashboard analytics", thread_id=thread_id, limit=10)
        elapsed = time.time() - start

        assert len(results) >= 1
        assert elapsed < 1.0  # Should complete in < 1 second

    def test_list_performance_with_1000_entries(self, large_dataset):
        """Test listing performance with 1000 entries."""
        journal = large_dataset["journal"]
        thread_id = large_dataset["thread_id"]

        # Add 1000 entries
        for i in range(1000):
            journal.add_entry(
                content=f"Activity {i}: Work on project",
                entry_type="raw",
                thread_id=thread_id,
            )

        # List should be fast
        import time
        start = time.time()
        entries = journal.list_entries(thread_id=thread_id, limit=100)
        elapsed = time.time() - start

        assert len(entries) == 100
        assert elapsed < 0.5  # Should complete in < 500ms

