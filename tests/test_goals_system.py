"""Test goals system implementation (TDD approach).

This test suite follows TDD methodology:
1. Write tests first (define expectations)
2. Create SQLite schema
3. Implement goals storage
4. Implement progress tracking
5. Implement change detection (5 mechanisms)
6. Implement version history
7. Verify all tests pass

Week 4 Implementation: Goal tracking with change detection
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from executive_assistant.storage.goals_storage import GoalsStorage


class TestGoalsSchema:
    """Test SQLite schema for goals."""

    @pytest.fixture
    def goals_db(self, tmp_path):
        """Create a temporary goals database."""
        db_path = tmp_path / "goals.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, db_path

    def test_create_goals_table(self, goals_db):
        """Test creating goals table."""
        conn, db_path = goals_db

        # Create schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                target_date TEXT,
                status TEXT DEFAULT 'planned',
                progress REAL DEFAULT 0.0,
                priority INTEGER NOT NULL,
                importance INTEGER NOT NULL,
                parent_goal_id TEXT,
                related_projects JSON,
                depends_on JSON,
                tags JSON,
                notes JSON,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_thread ON goals(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_category ON goals(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_target_date ON goals(target_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id)")

        conn.commit()

        # Verify table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='goals'"
        ).fetchall()

        assert len(tables) == 1

    def test_create_goal_progress_table(self, goals_db):
        """Test creating goal_progress table."""
        conn, db_path = goals_db

        # Create goals table first
        conn.execute("""
            CREATE TABLE goals (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL
            )
        """)

        # Create goal_progress table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goal_progress (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                progress REAL NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_goal ON goal_progress(goal_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_timestamp ON goal_progress(timestamp)")

        conn.commit()

        # Verify table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='goal_progress'"
        ).fetchall()

        assert len(tables) == 1

    def test_create_goal_versions_table(self, goals_db):
        """Test creating goal_versions table."""
        conn, db_path = goals_db

        # Create goals table first
        conn.execute("""
            CREATE TABLE goals (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL
            )
        """)

        # Create goal_versions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goal_versions (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot JSON NOT NULL,
                change_type TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_goal ON goal_versions(goal_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_version ON goal_versions(version)")

        conn.commit()

        # Verify table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='goal_versions'"
        ).fetchall()

        assert len(tables) == 1

    def test_insert_and_retrieve_goal(self, goals_db):
        """Test inserting and retrieving a goal."""
        conn, db_path = goals_db

        # Create schema
        conn.execute("""
            CREATE TABLE goals (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                target_date TEXT,
                status TEXT DEFAULT 'planned',
                progress REAL DEFAULT 0.0,
                priority INTEGER NOT NULL,
                importance INTEGER NOT NULL,
                parent_goal_id TEXT,
                related_projects JSON,
                depends_on JSON,
                tags JSON,
                notes JSON,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Insert goal
        goal_id = "goal-123"
        now = datetime.now(timezone.utc).isoformat()

        conn.execute("""
            INSERT INTO goals (
                id, thread_id, title, description, category, target_date,
                status, progress, priority, importance,
                related_projects, depends_on, tags, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            goal_id, "test_thread", "Launch sales dashboard",
            "Build and deploy sales analytics dashboard",
            "medium_term", (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "planned", 0.0, 8, 9,
            '["sales_analytics"]', '[]', '["dashboard", "sales"]', '[]',
            now, now
        ))

        conn.commit()

        # Retrieve
        row = conn.execute(
            "SELECT * FROM goals WHERE id = ?",
            (goal_id,)
        ).fetchone()

        assert row is not None
        assert row["title"] == "Launch sales dashboard"
        assert row["category"] == "medium_term"
        assert row["status"] == "planned"
        assert row["progress"] == 0.0
        assert row["priority"] == 8


class TestGoalsStorageAPI:
    """Test goals storage API."""

    @pytest.fixture
    def goals_storage(self, tmp_path):
        """Create goals storage for testing."""
        from executive_assistant.storage.goals_storage import GoalsStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_goals"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)

        storage = GoalsStorage()
        storage._get_goals_dir = lambda tid=None: goals_dir

        return storage, thread_id

    def test_create_goal(self, goals_storage):
        """Test creating a goal."""
        storage, thread_id = goals_storage

        goal_id = storage.create_goal(
            title="Launch sales dashboard",
            description="Build and deploy sales analytics dashboard",
            category="medium_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            priority=8,
            importance=9,
            thread_id=thread_id,
            tags=["dashboard", "sales"],
        )

        assert goal_id is not None

        # Verify retrieval
        goal = storage.get_goal(goal_id, thread_id)
        assert goal is not None
        assert goal["title"] == "Launch sales dashboard"
        assert goal["category"] == "medium_term"
        assert goal["status"] == "planned"
        assert goal["progress"] == 0.0

    def test_list_goals_by_status(self, goals_storage):
        """Test listing goals by status."""
        storage, thread_id = goals_storage

        # Create goals with different statuses
        storage.create_goal(
            title="Active goal 1",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )

        storage.create_goal(
            title="Active goal 2",
            category="short_term",
            priority=6,
            importance=8,
            thread_id=thread_id,
        )

        storage.create_goal(
            title="Completed goal",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )

        # Mark one as completed
        goals = storage.list_goals(thread_id=thread_id)
        storage.update_goal(
            goals[2]["id"],
            thread_id=thread_id,
            status="completed",
            progress=100.0,
        )

        # Get active goals
        active_goals = storage.list_goals(
            thread_id=thread_id,
            status="planned",
        )

        assert len(active_goals) >= 2
        assert all(g["status"] == "planned" for g in active_goals)

    def test_update_goal_progress(self, goals_storage):
        """Test updating goal progress."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Learn Python",
            category="medium_term",
            priority=7,
            importance=8,
            thread_id=thread_id,
        )

        # Update progress
        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=25.0,
            source="manual",
            notes="Completed basic syntax tutorial",
        )

        # Verify progress updated
        goal = storage.get_goal(goal_id, thread_id)
        assert goal["progress"] == 25.0

        # Verify progress entry created
        progress_history = storage.get_progress_history(goal_id, thread_id)
        assert len(progress_history) == 1
        assert progress_history[0]["progress"] == 25.0


class TestProgressTracking:
    """Test progress tracking functionality."""

    @pytest.fixture
    def goals_storage(self, tmp_path):
        """Create goals storage for testing."""
        from executive_assistant.storage.goals_storage import GoalsStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_progress"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)

        storage = GoalsStorage()
        storage._get_goals_dir = lambda tid=None: goals_dir

        return storage, thread_id

    def test_track_multiple_progress_updates(self, goals_storage):
        """Test tracking multiple progress updates."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Complete API integration",
            category="short_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Add multiple progress updates
        now = datetime.now(timezone.utc)

        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=10.0,
            source="manual",
            notes="Started API design",
        )

        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=35.0,
            source="manual",
            notes="Completed endpoints",
        )

        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=60.0,
            source="manual",
            notes="Integrated with frontend",
        )

        # Verify progress history
        progress_history = storage.get_progress_history(goal_id, thread_id)
        assert len(progress_history) == 3

        # Verify latest progress
        goal = storage.get_goal(goal_id, thread_id)
        assert goal["progress"] == 60.0

    def test_get_goals_by_progress_range(self, goals_storage):
        """Test filtering goals by progress range."""
        storage, thread_id = goals_storage

        # Create goals
        goal1 = storage.create_goal(
            title="Goal 1",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )
        storage.update_goal_progress(goal1, thread_id, progress=20.0, source="test")

        goal2 = storage.create_goal(
            title="Goal 2",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )
        storage.update_goal_progress(goal2, thread_id, progress=50.0, source="test")

        goal3 = storage.create_goal(
            title="Goal 3",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )
        storage.update_goal_progress(goal3, thread_id, progress=80.0, source="test")

        # Get goals with progress < 50%
        low_progress = storage.list_goals(
            thread_id=thread_id,
            min_progress=0.0,
            max_progress=50.0,
        )

        assert len(low_progress) >= 2


class TestChangeDetection:
    """Test change detection mechanisms."""

    @pytest.fixture
    def goals_storage(self, tmp_path):
        """Create goals storage for testing."""
        from executive_assistant.storage.goals_storage import GoalsStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_changes"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)

        storage = GoalsStorage()
        storage._get_goals_dir = lambda tid=None: goals_dir

        return storage, thread_id

    def test_detect_explicit_change(self, goals_storage):
        """Test detecting explicit goal changes."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Launch dashboard",
            description="Original description",
            category="medium_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Update with explicit change
        storage.update_goal(
            goal_id=goal_id,
            thread_id=thread_id,
            description="Updated description with new requirements",
            change_type="modification",
            change_reason="User explicitly changed requirements",
        )

        # Verify version history
        versions = storage.get_version_history(goal_id, thread_id)
        assert len(versions) >= 1
        assert versions[0]["change_type"] == "modification"

    def test_detect_journal_stagnation(self, goals_storage):
        """Test detecting stagnation from lack of progress."""
        storage, thread_id = goals_storage

        # Create old goal with no progress
        goal_id = storage.create_goal(
            title="Old stagnant goal",
            category="long_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )

        # Manually set created_at to 3 weeks ago
        three_weeks_ago = (datetime.now(timezone.utc) - timedelta(weeks=3)).isoformat()
        conn = storage.get_connection(thread_id)
        conn.execute(
            "UPDATE goals SET created_at = ?, updated_at = ? WHERE id = ?",
            (three_weeks_ago, three_weeks_ago, goal_id)
        )
        conn.commit()
        conn.close()

        # Detect stagnation
        stagnant_goals = storage.detect_stagnant_goals(thread_id, weeks=2)
        assert len(stagnant_goals) >= 1
        assert stagnant_goals[0]["id"] == goal_id

    def test_detect_progress_stall(self, goals_storage):
        """Test detecting stalled progress."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Stalled goal",
            category="medium_term",
            priority=7,
            importance=8,
            thread_id=thread_id,
        )

        # Add initial progress
        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=40.0,
            source="manual",
            notes="Made good progress",
        )

        # Manually set progress timestamp to 2 weeks ago
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(weeks=2)).isoformat()
        conn = storage.get_connection(thread_id)
        conn.execute(
            "UPDATE goal_progress SET timestamp = ? WHERE goal_id = ?",
            (two_weeks_ago, goal_id)
        )
        conn.commit()
        conn.close()

        # Detect stalled goals
        stalled_goals = storage.detect_stalled_progress(thread_id, weeks=1)
        assert len(stalled_goals) >= 1

    def test_detect_approaching_deadline(self, goals_storage):
        """Test detecting goals approaching deadline with low progress."""
        storage, thread_id = goals_storage

        # Create goal with deadline in 3 days
        three_days_from_now = datetime.now(timezone.utc) + timedelta(days=3)

        goal_id = storage.create_goal(
            title="Urgent goal",
            category="short_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
            target_date=three_days_from_now.isoformat(),
        )

        # Set low progress
        storage.update_goal_progress(
            goal_id=goal_id,
            thread_id=thread_id,
            progress=15.0,
            source="test",
        )

        # Detect urgent goals
        urgent_goals = storage.detect_urgent_goals(thread_id, days_threshold=5, progress_threshold=30.0)
        assert len(urgent_goals) >= 1
        assert urgent_goals[0]["id"] == goal_id


class TestVersionHistory:
    """Test version history and audit trail."""

    @pytest.fixture
    def goals_storage(self, tmp_path):
        """Create goals storage for testing."""
        from executive_assistant.storage.goals_storage import GoalsStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_versions"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)

        storage = GoalsStorage()
        storage._get_goals_dir = lambda tid=None: goals_dir

        return storage, thread_id

    def test_create_version_on_goal_update(self, goals_storage):
        """Test that version is created when goal is updated."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Original title",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )

        # Update goal
        storage.update_goal(
            goal_id=goal_id,
            thread_id=thread_id,
            title="Updated title",
            change_type="modification",
            change_reason="User requested title change",
        )

        # Verify version created
        versions = storage.get_version_history(goal_id, thread_id)
        assert len(versions) >= 1

        # Verify snapshot contains old data
        snapshot = versions[0]["snapshot"]
        assert snapshot["title"] == "Original title"

    def test_restore_from_version(self, goals_storage):
        """Test restoring goal from previous version."""
        storage, thread_id = goals_storage

        # Create and update goal
        goal_id = storage.create_goal(
            title="Original title",
            description="Original description",
            category="short_term",
            priority=5,
            importance=7,
            thread_id=thread_id,
        )

        storage.update_goal(
            goal_id=goal_id,
            thread_id=thread_id,
            title="New title",
            description="New description",
            change_type="modification",
            change_reason="User changed everything",
        )

        # Get version 1 (original)
        versions = storage.get_version_history(goal_id, thread_id)
        original_version = versions[0]

        # Restore from version
        storage.restore_from_version(
            goal_id=goal_id,
            thread_id=thread_id,
            version_id=original_version["id"],
            change_reason="Restoring original version by user request",
        )

        # Verify restoration
        goal = storage.get_goal(goal_id, thread_id)
        assert goal["title"] == "Original title"
        assert goal["description"] == "Original description"


class TestGoalsIntegration:
    """Test goals integration with journal and memory."""

    @pytest.fixture
    def goals_storage(self, tmp_path):
        """Create goals storage for testing."""
        from executive_assistant.storage.goals_storage import GoalsStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_integration"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)

        storage = GoalsStorage()
        storage._get_goals_dir = lambda tid=None: goals_dir

        return storage, thread_id

    def test_update_progress_from_journal(self, goals_storage):
        """Test updating goal progress based on journal entries."""
        storage, thread_id = goals_storage

        # Create goal
        goal_id = storage.create_goal(
            title="Complete sales dashboard",
            category="medium_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Simulate journal entry indicating progress
        # TODO: Implement journal → goals integration
        # Expected:
        # - Detect goal-related activity in journal
        # - Update progress automatically
        # - Verify progress updated
        pass

    def test_inform_goals_from_memory(self, goals_storage):
        """Test creating goals informed by memory facts."""
        storage, thread_id = goals_storage

        # TODO: Implement memory → goals integration
        # Expected:
        # - User states objective in conversation
        # - Memory extracts fact: "User wants to launch dashboard by EOM"
        # - Goals system creates goal from memory
        # - Verify goal created with correct target_date
        pass
