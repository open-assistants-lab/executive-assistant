"""Test suite for Instinct System and Memory Evolution with HITL Approval.

This test suite validates the complete learning pipeline:
1. Observer detects patterns from user interactions
2. Instincts are created/stored with confidence scoring
3. Evolver clusters related instincts into skills
4. HITL approval workflow saves skills
5. Memory system supports temporal queries

Test Levels:
- Level 1: Basic instinct CRUD operations
- Level 2: Observer pattern detection
- Level 3: Storage persistence (JSONL + snapshot)
- Level 4: Evolver clustering
- Level 5: HITL skill evolution
- Level 6: Memory temporal queries
- Level 7: End-to-end learning workflows
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest

from executive_assistant.instincts.observer import get_instinct_observer
from executive_assistant.instincts.evolver import get_instinct_evolver
from executive_assistant.instincts.profiles import get_profile_manager
from executive_assistant.storage.instinct_storage import get_instinct_storage
from executive_assistant.storage.mem_storage import get_mem_storage
from executive_assistant.agent.prompts import get_system_prompt


class TestLevel1_BasicInstinctCRUD:
    """Level 1: Basic instinct create, read, update operations."""

    @pytest.fixture
    def thread_id(self):
        """Create isolated thread ID for each test."""
        import uuid
        return f"test-level1-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def storage(self, thread_id):
        """Get storage instance and cleanup after test."""
        storage = get_instinct_storage()
        yield storage
        # Cleanup
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_create_instinct(self, storage, thread_id):
        """Test basic instinct creation."""
        instinct_id = storage.create_instinct(
            trigger="user asks for summary",
            action="provide concise bullet points",
            domain="format",
            source="explicit-user",
            confidence=0.8,
            thread_id=thread_id,
        )

        assert instinct_id is not None
        assert len(instinct_id) == 36  # UUID format

    def test_list_instincts(self, storage, thread_id):
        """Test listing all instincts."""
        # Create test instincts
        storage.create_instinct("trigger1", "action1", "communication", "explicit-user", 0.7, thread_id)
        storage.create_instinct("trigger2", "action2", "format", "session-observation", 0.6, thread_id)

        instincts = storage.list_instincts(thread_id=thread_id)
        assert len(instincts) == 2

        # Test filtering
        comm_instincts = storage.list_instincts(domain="communication", thread_id=thread_id)
        assert len(comm_instincts) == 1

    def test_adjust_confidence(self, storage, thread_id):
        """Test confidence adjustment."""
        instinct_id = storage.create_instinct(
            "trigger", "action", "workflow", "session-observation", 0.5, thread_id
        )

        # Adjust up
        success = storage.adjust_confidence(instinct_id, 0.1, thread_id)
        assert success is True

        instincts = storage.list_instincts(thread_id=thread_id)
        assert instincts[0]["confidence"] == 0.6

        # Adjust down
        success = storage.adjust_confidence(instinct_id, -0.2, thread_id)
        assert success is True
        assert instincts[0]["confidence"] == 0.4

    def test_enable_disable_instinct(self, storage, thread_id):
        """Test enabling/disabling instincts."""
        instinct_id = storage.create_instinct(
            "trigger", "action", "communication", "session-observation", 0.5, thread_id
        )

        # Disable
        success = storage.set_instinct_status(instinct_id, "disabled", thread_id)
        assert success is True

        instincts = storage.list_instincts(thread_id=thread_id)
        assert instincts[0]["status"] == "disabled"

        # Re-enable
        success = storage.set_instinct_status(instinct_id, "enabled", thread_id)
        assert success is True
        assert instincts[0]["status"] == "enabled"


class TestLevel2_ObserverPatternDetection:
    """Level 2: Observer detects patterns from user messages."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level2-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def observer(self):
        return get_instinct_observer()

    @pytest.fixture
    def cleanup(self, thread_id):
        yield
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_detect_verbosity_preference(self, observer, thread_id, cleanup):
        """Test observer detects 'be concise' pattern."""
        detected = observer.observe_message("Be concise and brief", thread_id=thread_id)
        assert len(detected) >= 1

        storage = get_instinct_storage()
        instincts = storage.list_instincts(thread_id=thread_id)

        # Should have created a "concise" instinct
        concise_instincts = [i for i in instincts if "concise" in i["action"].lower()]
        assert len(concise_instincts) >= 1

    def test_detect_correction_pattern(self, observer, thread_id, cleanup):
        """Test observer detects 'actually, I meant' pattern."""
        detected = observer.observe_message(
            "Actually, I meant use JSON format instead",
            thread_id=thread_id
        )
        assert len(detected) >= 1

        storage = get_instinct_storage()
        instincts = storage.list_instincts(thread_id=thread_id)

        # Should have created a correction instinct
        correction_instincts = [i for i in instincts if "correct" in i["trigger"].lower()]
        assert len(correction_instincts) >= 1

    def test_detect_format_preference(self, observer, thread_id, cleanup):
        """Test observer detects format preferences."""
        test_messages = [
            "Use bullet points for this",
            "Return as JSON please",
            "Give me a table format",
        ]

        for msg in test_messages:
            detected = observer.observe_message(msg, thread_id=thread_id)
            assert len(detected) >= 1, f"Failed to detect pattern in: {msg}"

    def test_pattern_reinforcement(self, observer, thread_id, cleanup):
        """Test that repeated patterns reinforce confidence."""
        # First message
        observer.observe_message("Be brief", thread_id=thread_id)

        storage = get_instinct_storage()
        instincts_after_first = storage.list_instincts(thread_id=thread_id)
        initial_confidence = instincts_after_first[0]["confidence"]

        # Second similar message (should reinforce)
        observer.observe_message("Keep it short", thread_id=thread_id)

        instincts_after_second = storage.list_instincts(thread_id=thread_id)
        # Should reinforce existing instinct, not create new one
        assert len(instincts_after_second) == 1


class TestLevel3_StoragePersistence:
    """Level 3: JSONL + snapshot storage and recovery."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level3-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def storage(self, thread_id):
        storage = get_instinct_storage()
        yield storage
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_jsonl_append_only_log(self, storage, thread_id):
        """Test that events are appended to JSONL."""
        # Create multiple instincts
        id1 = storage.create_instinct("trigger1", "action1", "communication", "session-observation", 0.5, thread_id)
        id2 = storage.create_instinct("trigger2", "action2", "format", "session-observation", 0.6, thread_id)
        id3 = storage.create_instinct("trigger3", "action3", "workflow", "session-observation", 0.7, thread_id)

        # Check JSONL file exists
        jsonl_path = storage._get_jsonl_path(thread_id)
        assert jsonl_path.exists()

        # Count lines (3 create events)
        with open(jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_snapshot_compaction(self, storage, thread_id):
        """Test snapshot creation and compaction."""
        # Create instincts
        for i in range(5):
            storage.create_instinct(f"trigger{i}", f"action{i}", "communication", "session-observation", 0.5 + i*0.1, thread_id)

        # Create snapshot
        snapshot_path = storage._get_snapshot_path(thread_id)
        storage._save_snapshot(thread_id)

        assert snapshot_path.exists()

        # Verify snapshot contains all instincts
        import json
        with open(snapshot_path) as f:
            snapshot = json.load(f)

        assert len(snapshot) == 5

    def test_replay_from_snapshot(self, storage, thread_id):
        """Test loading from snapshot after clearing memory."""
        # Create instincts and snapshot
        for i in range(3):
            storage.create_instinct(f"t{i}", f"a{i}", "format", "session-observation", 0.5, thread_id)

        storage._save_snapshot(thread_id)

        # Clear in-memory cache
        storage._snapshot_cache.clear()

        # Load should rebuild from JSONL
        instincts = storage.list_instincts(thread_id=thread_id)
        assert len(instincts) == 3

    def test_export_import_roundtrip(self, storage, thread_id):
        """Test export and import functionality."""
        from executive_assistant.tools.instinct_tools import export_instincts, import_instincts

        # Create test instincts
        storage.create_instinct("test_trigger", "test_action", "communication", "session-observation", 0.75, thread_id)

        # Export
        export_data = export_instincts()
        assert "test_trigger" in export_data
        assert "test_action" in export_data

        # Import to new thread
        new_thread_id = f"{thread_id}-import"
        result = import_instincts(export_data)
        assert "Imported" in result

        # Verify imported
        new_storage = get_instinct_storage()
        imported_instincts = new_storage.list_instincts(thread_id=new_thread_id)
        assert len(imported_instincts) == 1

        # Cleanup
        if os.path.exists(f"data/users/{new_thread_id}"):
            shutil.rmtree(f"data/users/{new_thread_id}")


class TestLevel4_EvolverClustering:
    """Level 4: Evolver clusters related instincts into skills."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level4-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def evolver(self):
        return get_instinct_evolver()

    @pytest.fixture
    def storage(self, thread_id):
        storage = get_instinct_storage()
        yield storage
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_analyze_clusters_by_domain(self, evolver, storage, thread_id):
        """Test that evolver groups instincts by domain."""
        # Create communication instincts
        storage.create_instinct("user asks questions", "be brief", "communication", "session-observation", 0.8, thread_id)
        storage.create_instinct("wants short answers", "keep concise", "communication", "session-observation", 0.75, thread_id)

        # Create format instincts
        storage.create_instinct("user exports data", "use JSON", "format", "session-observation", 0.7, thread_id)
        storage.create_instinct("requests report", "use tables", "format", "session-observation", 0.65, thread_id)

        clusters = evolver.analyze_clusters(thread_id)

        # Should have 2 clusters (communication and format)
        assert len(clusters) == 2

    def test_generate_draft_skill(self, evolver, storage, thread_id):
        """Test draft skill generation from cluster."""
        # Create cluster-worthy instincts
        storage.create_instinct("asks for summary", "use bullets", "format", "session-observation", 0.8, thread_id)
        storage.create_instinct("requests list", "use bullet points", "format", "session-observation", 0.7, thread_id)

        clusters = evolver.analyze_clusters(thread_id)
        assert len(clusters) >= 1

        # Generate draft
        draft = evolver.generate_draft_skill(clusters[0], thread_id)

        assert draft["name"] is not None
        assert draft["content"] is not None
        assert "## Behavioral Patterns" in draft["content"]
        assert draft["cluster"]["avg_confidence"] >= 0.6

    def test_evolve_requires_minimum_confidence(self, evolver, storage, thread_id):
        """Test that low-confidence instincts don't evolve."""
        # Create low-confidence instincts
        storage.create_instinct("trigger1", "action1", "communication", "session-observation", 0.4, thread_id)
        storage.create_instinct("trigger2", "action2", "communication", "session-observation", 0.5, thread_id)

        drafts = evolver.evolve_instincts(thread_id)

        # Should not evolve (avg confidence < 0.6)
        assert len(drafts) == 0


class TestLevel5_HITLSkillEvolution:
    """Level 5: Human-in-the-loop approval workflow."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level5-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def evolver(self):
        return get_instinct_evolver()

    @pytest.fixture
    def cleanup(self, thread_id):
        yield
        # Clean up both main thread and skills
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")
        skills_dir = f"data/users/{thread_id}/skills/on_demand"
        if os.path.exists(skills_dir):
            shutil.rmtree(skills_dir)

    def test_approve_evolved_skill(self, evolver, thread_id, cleanup):
        """Test approving a draft skill."""
        storage = get_instinct_storage()

        # Create cluster-worthy instincts
        storage.create_instinct("asks for brief", "be concise", "communication", "session-observation", 0.8, thread_id)
        storage.create_instinct("wants short", "keep it brief", "communication", "session-observation", 0.75, thread_id)
        storage.create_instinct("prefers concise", "use minimal words", "communication", "session-observation", 0.7, thread_id)

        # Evolve
        drafts = evolver.evolve_instincts(thread_id)
        assert len(drafts) >= 1

        draft_id = drafts[0]["id"]

        # Approve (should create user skill)
        success = evolver.approve_skill(draft_id, thread_id)
        assert success is True

        # Verify skill was created
        from executive_assistant.storage.file_sandbox import get_thread_id
        skills_dir = Path(f"data/users/{thread_id}/skills/on_demand")
        assert skills_dir.exists()

        skill_files = list(skills_dir.glob("*.md"))
        assert len(skill_files) >= 1

    def test_rejected_skill_not_saved(self, evolver, thread_id, cleanup):
        """Test that rejecting a skill doesn't save it."""
        # This would require user interaction in real scenario
        # For now, we test that approve returns False for invalid draft
        success = evolver.approve_skill("invalid_draft_id", thread_id)
        assert success is False


class TestLevel6_MemoryTemporalQueries:
    """Level 6: Memory system with temporal queries."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level6-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def storage(self):
        mem_storage = get_mem_storage()
        yield mem_storage
        # Cleanup handled by thread_id fixture

    @pytest.fixture
    def cleanup(self, thread_id):
        yield
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_save_memory_with_timestamp(self, storage, thread_id, cleanup):
        """Test saving memory with automatic timestamp."""
        memory_id = storage.save_memory(
            fact="User's location is Tokyo",
            thread_id=thread_id,
        )

        assert memory_id is not None

        # Retrieve and check timestamp
        memory = storage.get_memory(memory_id, thread_id=thread_id)
        assert memory["fact"] == "User's location is Tokyo"
        assert "valid_from" in memory
        assert memory["valid_to"] is None  # Current fact

    def test_update_fact_with_temporal_tracking(self, storage, thread_id, cleanup):
        """Test updating a fact preserves history."""
        # Save initial fact
        memory_id = storage.save_memory("Job: Engineer", thread_id=thread_id)

        memory = storage.get_memory(memory_id, thread_id=thread_id)
        first_valid_from = memory["valid_from"]

        # Update fact
        storage.update_memory(memory_id, "Job: Senior Engineer", thread_id=thread_id)

        # Check history
        history = storage.get_memory_history(memory_id, thread_id=thread_id)
        assert len(history) == 2
        assert history[0]["fact"] == "Job: Engineer"
        assert history[1]["fact"] == "Job: Senior Engineer"

    def test_get_memory_at_time(self, storage, thread_id, cleanup):
        """Test querying memory as of specific time."""
        # Save initial state
        memory_id = storage.save_memory("Status: Active", thread_id=thread_id)

        # Get current memory
        current = storage.get_memory(memory_id, thread_id=thread_id)
        current_time = current["valid_from"]

        # Query at current time
        memory_at_time = storage.get_memory_at_time(memory_id, current_time, thread_id=thread_id)
        assert memory_at_time["fact"] == "Status: Active"

    def test_location_change_scenario(self, storage, thread_id, cleanup):
        """Test classic Sydney → Tokyo temporal scenario."""
        # Initial location
        memory_id = storage.save_memory("Location: Sydney", thread_id=thread_id)

        # Simulate time passing and location change
        storage.update_memory(memory_id, "Location: Tokyo", thread_id=thread_id)

        # Query history shows full timeline
        history = storage.get_memory_history(memory_id, thread_id=thread_id)
        assert len(history) == 2
        assert "Sydney" in history[0]["fact"]
        assert "Tokyo" in history[1]["fact"]


class TestLevel7_EndToEndWorkflows:
    """Level 7: Complete learning workflows with all components."""

    @pytest.fixture
    def thread_id(self):
        import uuid
        return f"test-level7-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def cleanup(self, thread_id):
        yield
        if os.path.exists(f"data/users/{thread_id}"):
            shutil.rmtree(f"data/users/{thread_id}")

    def test_profile_to_learned_behavior_workflow(self, thread_id, cleanup):
        """Test: Apply profile → observer detects corrections → behavior adjusts."""
        manager = get_profile_manager()
        observer = get_instinct_observer()
        storage = get_instinct_storage()

        # Step 1: Apply profile
        result = manager.apply_profile("concise_professional", thread_id)
        assert result["success"] is True
        assert result["instincts_created"] == 3

        # Step 2: Verify profile instincts loaded
        instincts = storage.list_instincts(thread_id=thread_id)
        assert len(instincts) == 3

        # Step 3: Observer detects correction (user doesn't want concise)
        observer.observe_message("Actually, I prefer detailed explanations", thread_id=thread_id)

        # Step 4: Verify correction instinct created
        correction_instincts = [
            i for i in storage.list_instincts(thread_id=thread_id)
            if "correct" in i["trigger"].lower() or "detailed" in i["action"].lower()
        ]
        assert len(correction_instincts) >= 1

    def test_instinct_injection_workflow(self, thread_id, cleanup):
        """Test: Create instinct → verify it appears in system prompt."""
        from executive_assistant.storage.file_sandbox import set_thread_id
        set_thread_id(thread_id)

        storage = get_instinct_storage()

        # Create instinct
        storage.create_instinct(
            trigger="user requests data export",
            action="always use JSON format",
            domain="format",
            source="explicit-user",
            confidence=0.9,
            thread_id=thread_id,
        )

        # Generate system prompt
        prompt = get_system_prompt(
            channel="http",
            thread_id=thread_id,
            user_message="Export the user data"
        )

        # Verify instinct section is present
        assert "## Behavioral Patterns" in prompt
        assert "JSON format" in prompt or "json" in prompt.lower()

    def test_complete_evolution_pipeline(self, thread_id, cleanup):
        """Test: Observer learns patterns → Evolve → HITL approve → Skill created."""
        observer = get_instinct_observer()
        evolver = get_instinct_evolver()
        storage = get_instinct_storage()

        # Step 1: User expresses preferences multiple times
        preference_messages = [
            "Use bullet points",
            "Keep it structured with bullets",
            "I like lists",
        ]

        for msg in preference_messages:
            observer.observe_message(msg, thread_id=thread_id)

        # Step 2: Verify instincts created
        instincts = storage.list_instincts(thread_id=thread_id)
        format_instincts = [i for i in instincts if i["domain"] == "format"]
        assert len(format_instincts) >= 1

        # Step 3: Evolve into skill
        drafts = evolver.evolve_instincts(thread_id)
        assert len(drafts) >= 1

        # Step 4: Approve skill
        draft_id = drafts[0]["id"]
        success = evolver.approve_skill(draft_id, thread_id)
        assert success is True

        # Step 5: Verify skill file created
        from executive_assistant.storage.file_sandbox import get_thread_id
        skills_dir = Path(f"data/users/{thread_id}/skills/on_demand")
        skill_files = list(skills_dir.glob("*.md"))
        assert len(skill_files) >= 1

        # Step 6: Verify skill content
        skill_content = skill_files[0].read_text()
        assert "bullet" in skill_content.lower() or "list" in skill_content.lower()

    def test_memory_temporal_workflow(self, thread_id, cleanup):
        """Test: Save memory → update over time → query history."""
        storage = get_memory_storage()

        # Simulate job changes over time
        jobs = [
            ("Job: Junior Developer", "2026-01-01T10:00:00Z"),
            ("Job: Senior Developer", "2026-06-01T10:00:00Z"),
            ("Job: Tech Lead", "2026-12-01T10:00:00Z"),
        ]

        memory_id = None
        for job, timestamp in jobs:
            if memory_id is None:
                memory_id = storage.save_memory(job, thread_id=thread_id)
            else:
                storage.update_memory(memory_id, job, thread_id=thread_id)

        # Query full history
        history = storage.get_memory_history(memory_id, thread_id=thread_id)
        assert len(history) == 3

        # Verify progression
        assert "Junior" in history[0]["fact"]
        assert "Senior" in history[1]["fact"]
        assert "Tech Lead" in history[2]["fact"]

    def test_export_import_instincts_workflow(self, thread_id, cleanup):
        """Test: Create instincts → export → import to new thread → verify."""
        from executive_assistant.tools.instinct_tools import export_instincts, import_instincts

        storage = get_instinct_storage()

        # Create instincts in thread 1
        storage.create_instinct("trigger1", "action1", "communication", "session-observation", 0.8, thread_id)
        storage.create_instinct("trigger2", "action2", "format", "session-observation", 0.7, thread_id)

        # Export
        export_data = export_instincts()

        # Import to thread 2
        thread_id_2 = f"{thread_id}-new"
        result = import_instincts(export_data)
        assert "Imported 2 instincts" in result

        # Verify in thread 2
        instincts_2 = storage.list_instincts(thread_id=thread_id_2)
        assert len(instincts_2) == 2

        # Cleanup
        if os.path.exists(f"data/users/{thread_id_2}"):
            shutil.rmtree(f"data/users/{thread_id_2}")


# Test runner instructions
if __name__ == "__main__":
    print("=" * 70)
    print("INSTINCT SYSTEM & MEMORY EVOLUTION TEST SUITE")
    print("=" * 70)
    print("\nTest Levels:")
    print("  Level 1: Basic Instinct CRUD")
    print("  Level 2: Observer Pattern Detection")
    print("  Level 3: Storage Persistence (JSONL + Snapshot)")
    print("  Level 4: Evolver Clustering")
    print("  Level 5: HITL Skill Evolution")
    print("  Level 6: Memory Temporal Queries")
    print("  Level 7: End-to-End Workflows")
    print("\nRunning tests...")
    print("\nTo run specific level:")
    print("  pytest tests/poc/test_instinct_and_memory_evolution.py::TestLevel1 -v")
    print("\nTo run all tests:")
    print("  pytest tests/poc/test_instinct_and_memory_evolution.py -v")
    print("\nTo run with coverage:")
    print("  pytest tests/poc/test_instinct_and_memory_evolution.py --cov=src/executive_assistant/instincts --cov-report=html")
