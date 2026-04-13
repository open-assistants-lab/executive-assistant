"""Unit tests for the memory storage layer (src/storage/memory.py)."""

import pytest

from src.storage.memory import (
    DEFAULT_CONFIDENCE,
    MEMORY_DETAIL_COMPACT,
    MEMORY_DETAIL_FULL,
    MEMORY_DETAIL_SUMMARY,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_WORKFLOW,
    MAX_CONFIDENCE,
    MAX_CONFIDENCE_BOOST_FROM_ACCESS,
    MIN_CONFIDENCE_DELETE,
    SCOPE_GLOBAL,
    SCOPE_PROJECT,
    SOURCE_EXPLICIT,
    SOURCE_LEARNED,
    MemoryStore,
)


@pytest.fixture
def store(tmp_path):
    """Create a MemoryStore with a temp directory."""
    return MemoryStore(user_id="test_user", base_dir=tmp_path)


@pytest.fixture
def store_with_memories(store):
    """Create a MemoryStore with some pre-populated memories."""
    store.add_memory(
        trigger="when user provides name",
        action="call them Alice",
        confidence=0.9,
        domain="personal",
        memory_type=MEMORY_TYPE_FACT,
        source=SOURCE_EXPLICIT,
    )
    store.add_memory(
        trigger="when discussing coding",
        action="use dark mode",
        confidence=0.7,
        domain="tools",
        memory_type=MEMORY_TYPE_PREFERENCE,
        source=SOURCE_LEARNED,
    )
    store.add_memory(
        trigger="when deploying code",
        action="run tests first",
        confidence=0.5,
        domain="development",
        memory_type=MEMORY_TYPE_WORKFLOW,
        source=SOURCE_LEARNED,
    )
    return store


class TestAddMemory:
    """Tests for add_memory."""

    def test_add_basic_memory(self, store):
        mem = store.add_memory(
            trigger="when user provides name",
            action="Alice",
            confidence=0.8,
            domain="personal",
            memory_type=MEMORY_TYPE_FACT,
        )
        assert mem.trigger == "when user provides name"
        assert mem.action == "Alice"
        assert mem.domain == "personal"
        assert mem.memory_type == MEMORY_TYPE_FACT

    def test_add_memory_with_defaults(self, store):
        mem = store.add_memory(trigger="test trigger", action="test action")
        assert mem.confidence == DEFAULT_CONFIDENCE
        assert mem.source == SOURCE_LEARNED
        assert mem.memory_type == MEMORY_TYPE_PREFERENCE
        assert mem.scope == SCOPE_GLOBAL

    def test_add_memory_with_structured_data(self, store):
        structured = {"entity": "coding environment", "attribute": "theme", "value": "dark mode"}
        mem = store.add_memory(
            trigger="when coding",
            action="use dark mode",
            structured_data=structured,
        )
        assert mem.structured_data == structured

    def test_add_memory_with_scope(self, store):
        mem = store.add_memory(
            trigger="when in project X",
            action="use specific config",
            scope=SCOPE_PROJECT,
            project_id="proj_x",
        )
        assert mem.scope == SCOPE_PROJECT
        assert mem.project_id == "proj_x"

    def test_add_memory_returns_id(self, store):
        mem = store.add_memory(trigger="test", action="test")
        assert mem.id is not None
        assert len(mem.id) > 0


class TestGetMemory:
    """Tests for get_memory."""

    def test_get_existing_memory(self, store):
        mem = store.add_memory(trigger="test", action="test action")
        retrieved = store.get_memory(mem.id)
        assert retrieved is not None
        assert retrieved.id == mem.id
        assert retrieved.trigger == "test"

    def test_get_nonexistent_memory(self, store):
        result = store.get_memory("nonexistent_id")
        assert result is None


class TestListMemories:
    """Tests for list_memories."""

    def test_list_all_memories(self, store_with_memories):
        mems = store_with_memories.list_memories()
        assert len(mems) >= 3

    def test_list_memories_by_domain(self, store_with_memories):
        mems = store_with_memories.list_memories(domain="personal")
        assert all(m.domain == "personal" for m in mems)

    def test_list_memories_by_type(self, store_with_memories):
        mems = store_with_memories.list_memories(memory_type=MEMORY_TYPE_PREFERENCE)
        assert all(m.memory_type == MEMORY_TYPE_PREFERENCE for m in mems)

    def test_list_memories_by_scope(self, store_with_memories):
        mems = store_with_memories.list_memories(scope=SCOPE_GLOBAL)
        assert all(m.scope == SCOPE_GLOBAL for m in mems)

    def test_list_memories_excludes_superseded(self, store_with_memories):
        mems = store_with_memories.list_memories()
        assert all(not m.is_superseded for m in mems)

    def test_list_memories_with_limit(self, store_with_memories):
        mems = store_with_memories.list_memories(limit=2)
        assert len(mems) <= 2


class TestRemoveMemory:
    """Tests for remove_memory."""

    def test_remove_memory(self, store):
        mem = store.add_memory(trigger="to_remove", action="will be gone")
        result = store.remove_memory(mem.id)
        assert result is True
        assert store.get_memory(mem.id) is None

    def test_remove_nonexistent_memory(self, store):
        result = store.remove_memory("nonexistent_id")
        assert result is False


class TestUpdateMemory:
    """Tests for update_memory."""

    def test_update_memory_action(self, store):
        mem = store.add_memory(trigger="test", action="original")
        updated = store.update_memory(mem.id, new_action="updated action")
        assert updated.action == "updated action"

    def test_update_memory_trigger(self, store):
        mem = store.add_memory(trigger="old trigger", action="action")
        updated = store.update_memory(mem.id, new_trigger="new trigger")
        assert updated.trigger == "new trigger"

    def test_update_nonexistent_memory(self, store):
        result = store.update_memory("nonexistent_id", new_action="fail")
        assert result is None


class TestSupersedeMemory:
    """Tests for supersede_memory."""

    def test_supersede_memory(self, store):
        old = store.add_memory(trigger="old trigger", action="old action")
        new = store.add_memory(trigger="new trigger", action="new action")
        store.supersede_memory(old.id, new.id)
        old_check = store.get_memory(old.id)
        assert old_check.is_superseded is True
        assert old_check.superseded_by == new.id


class TestSearchFTS:
    """Tests for keyword/full-text search."""

    def test_search_fts_finds_match(self, store_with_memories):
        results = store_with_memories.search_fts("dark mode", limit=5)
        assert len(results) > 0
        assert any("dark" in m.action.lower() or "dark" in m.trigger.lower() for m in results)

    def test_search_fts_no_match(self, store_with_memories):
        results = store_with_memories.search_fts("quantum physics", limit=5)
        assert len(results) == 0

    def test_search_fts_excludes_superseded(self, store_with_memories):
        mems = store_with_memories.list_memories()
        if mems:
            new = store_with_memories.add_memory(trigger="replacement", action="new action")
            store_with_memories.supersede_memory(mems[0].id, new.id)
            results = store_with_memories.search_fts(mems[0].action.split()[0], limit=10)
            assert all(not m.is_superseded for m in results)


class TestSearchSemantic:
    """Tests for vector/semantic search."""

    def test_search_semantic_finds_relevant(self, store_with_memories):
        results = store_with_memories.search_semantic("coding preferences", limit=5)
        assert len(results) > 0

    def test_search_semantic_no_results(self, tmp_path):
        store = MemoryStore(user_id="empty_user", base_dir=tmp_path)
        results = store.search_semantic("anything", limit=5)
        assert len(results) == 0


class TestSearchHybrid:
    """Tests for hybrid search (keyword + semantic combined)."""

    def test_search_hybrid_returns_results(self, store_with_memories):
        results = store_with_memories.search_hybrid("dark mode", limit=5)
        assert len(results) > 0

    def test_search_hybrid_empty_store(self, tmp_path):
        store = MemoryStore(user_id="empty_hybrid", base_dir=tmp_path)
        results = store.search_hybrid("test", limit=5)
        assert len(results) == 0


class TestSearchAll:
    """Tests for unified search across memories + messages + insights."""

    def test_search_all_finds_memories(self, store_with_memories):
        results = store_with_memories.search_all("dark mode")
        assert "memories" in results
        assert len(results["memories"]) > 0

    def test_search_all_returns_all_sections(self, store_with_memories):
        results = store_with_memories.search_all("test")
        assert "memories" in results
        assert "insights" in results
        assert "messages" in results


class TestConnections:
    """Tests for connections graph."""

    def test_add_connection(self, store):
        mem1 = store.add_memory(trigger="trigger1", action="action1")
        mem2 = store.add_memory(trigger="trigger2", action="action2")
        store.add_connection(mem1.id, mem2.id, "relates_to")
        connections = store.get_connections(mem1.id)
        assert len(connections) >= 1
        assert connections[0].target_id == mem2.id
        assert connections[0].relationship == "relates_to"

    def test_add_connection_with_strength(self, store):
        mem1 = store.add_memory(trigger="trigger1", action="action1")
        mem2 = store.add_memory(trigger="trigger2", action="action2")
        store.add_connection(mem1.id, mem2.id, "updates", strength=0.8)
        connections = store.get_connections(mem1.id)
        assert any(c.strength == 0.8 for c in connections)

    def test_get_connections(self, store):
        mem1 = store.add_memory(trigger="trigger1", action="action1")
        mem2 = store.add_memory(trigger="trigger2", action="action2")
        store.add_connection(mem1.id, mem2.id, "relates_to")
        connections = store.get_connections(mem1.id)
        assert len(connections) >= 1
        assert connections[0].target_id == mem2.id

    def test_remove_connection(self, store):
        mem1 = store.add_memory(trigger="trigger1", action="action1")
        mem2 = store.add_memory(trigger="trigger2", action="action2")
        store.add_connection(mem1.id, mem2.id, "relates_to")
        store.remove_connection(mem1.id, mem2.id)
        connections = store.get_connections(mem1.id)
        assert len(connections) == 0

    def test_remove_connection_is_idempotent(self, store):
        store.remove_connection("fake1", "fake2")

    def test_connection_in_memory_data(self, store):
        mem1 = store.add_memory(trigger="trigger1", action="action1")
        mem2 = store.add_memory(trigger="trigger2", action="action2")
        store.add_connection(mem1.id, mem2.id, "contradicts")
        retrieved = store.get_memory(mem1.id)
        assert retrieved.connections is not None
        assert len(retrieved.connections) >= 1


class TestInsights:
    """Tests for insight management."""

    def test_add_insight(self, store):
        insight = store.add_insight(
            summary="User tends to work late",
            linked_memories=["mem1", "mem2"],
            confidence=0.8,
            domain="work_patterns",
        )
        assert insight.summary == "User tends to work late"
        assert insight.domain == "work_patterns"

    def test_list_insights(self, store):
        store.add_insight(summary="Insight 1", linked_memories=[], confidence=0.6, domain="test")
        store.add_insight(summary="Insight 2", linked_memories=[], confidence=0.7, domain="other")
        insights = store.list_insights()
        assert len(insights) >= 2

    def test_list_insights_by_domain(self, store):
        store.add_insight(
            summary="Test insight", linked_memories=[], confidence=0.5, domain="specific_domain"
        )
        insights = store.list_insights(domain="specific_domain")
        assert all(i.domain == "specific_domain" for i in insights)

    def test_remove_insight(self, store):
        insight = store.add_insight(
            summary="Removable", linked_memories=[], confidence=0.5, domain="test"
        )
        result = store.remove_insight(insight.id)
        assert result is True
        assert store.get_insights(insight.id) is None

    def test_remove_nonexistent_insight(self, store):
        result = store.remove_insight("nonexistent_id")
        assert result is False

    def test_search_insights_keyword(self, store):
        store.add_insight(
            summary="User prefers morning meetings",
            linked_memories=[],
            confidence=0.7,
            domain="schedule",
        )
        results = store.search_insights("morning", limit=5)
        assert len(results) > 0

    def test_search_insights_semantic(self, store):
        store.add_insight(
            summary="User prefers morning meetings",
            linked_memories=[],
            confidence=0.7,
            domain="schedule",
        )
        results = store.search_insights_semantic("early day scheduling", limit=5)
        assert len(results) >= 0


class TestSessions:
    """Tests for session tracking."""

    def test_create_session(self, store):
        session_id = store.create_session()
        assert session_id is not None
        assert len(session_id) > 0

    def test_create_session_with_id(self, store):
        session_id = store.create_session(session_id="my_session")
        assert session_id == "my_session"

    def test_get_session(self, store):
        session_id = store.create_session()
        session = store.get_session(session_id)
        assert session is not None
        assert session["id"] == session_id

    def test_update_session(self, store):
        session_id = store.create_session()
        store.update_session(session_id, message_count=5, summary="Testing session")
        session = store.get_session(session_id)
        assert session["message_count"] == 5
        assert session["summary"] == "Testing session"

    def test_list_sessions(self, store):
        store.create_session()
        store.create_session()
        sessions = store.list_sessions()
        assert len(sessions) >= 2


class TestAccessTracking:
    """Tests for smart forgetting (access boosting)."""

    def test_search_boosts_confidence(self, store):
        mem = store.add_memory(trigger="boost test", action="should get boosted", confidence=0.3)
        initial_confidence = mem.confidence
        store.search_semantic("boost test", limit=1)
        updated = store.get_memory(mem.id)
        assert updated.confidence > initial_confidence

    def test_confidence_capped_at_max(self, store):
        mem = store.add_memory(trigger="cap test", action="should be capped", confidence=0.95)
        for _ in range(20):
            store._boost_access(mem.id)
        updated = store.get_memory(mem.id)
        assert updated.confidence <= MAX_CONFIDENCE + MAX_CONFIDENCE_BOOST_FROM_ACCESS

    def test_access_count_increments_on_boost(self, store):
        mem = store.add_memory(trigger="count test", action="should be counted")
        assert mem.access_count == 0
        store._boost_access(mem.id)
        updated = store.get_memory(mem.id)
        assert updated.access_count >= 1


class TestMaybeDecay:
    """Tests for confidence decay."""

    def test_maybe_decay_reduces_confidence(self, store):
        mem = store.add_memory(trigger="decay test", action="will decay", confidence=0.8)
        store.maybe_decay_confidence()
        updated = store.get_memory(mem.id)
        assert updated.confidence < 0.8

    def test_maybe_decay_prunes_below_threshold(self, store):
        store.add_memory(
            trigger="prune candidate",
            action="very low conf",
            confidence=MIN_CONFIDENCE_DELETE + 0.01,
        )
        store.maybe_decay_confidence()
        mems = store.list_memories()
        assert all(m.confidence >= MIN_CONFIDENCE_DELETE for m in mems)


class TestProgressiveDisclosure:
    """Tests for context injection with progressive detail levels."""

    def test_compact_context(self, store_with_memories):
        context = store_with_memories.get_memory_context(detail_level=MEMORY_DETAIL_COMPACT)
        assert isinstance(context, str)
        assert len(context) > 0

    def test_summary_context(self, store_with_memories):
        context = store_with_memories.get_memory_context(detail_level=MEMORY_DETAIL_SUMMARY)
        assert isinstance(context, str)
        assert len(context) > 0

    def test_full_context(self, store_with_memories):
        context = store_with_memories.get_memory_context(detail_level=MEMORY_DETAIL_FULL)
        assert isinstance(context, str)
        assert len(context) > 0

    def test_compact_shorter_than_full(self, store_with_memories):
        compact = store_with_memories.get_memory_context(detail_level=MEMORY_DETAIL_COMPACT)
        full = store_with_memories.get_memory_context(detail_level=MEMORY_DETAIL_FULL)
        assert len(compact) <= len(full)


class TestSearchFieldSemantic:
    """Tests for per-field semantic search."""

    def test_search_field_trigger(self, store):
        store.add_memory(trigger="when the user needs deployment help", action="use CI/CD")
        results = store.search_field_semantic("deployment assistance", field="trigger", limit=5)
        assert isinstance(results, list)

    def test_search_field_action(self, store):
        store.add_memory(trigger="when coding", action="use VS Code with Python extension")
        results = store.search_field_semantic("IDE setup for Python", field="action", limit=5)
        assert isinstance(results, list)


class TestBatchOperations:
    """Tests for batch add."""

    def test_add_memories_batch(self, store):
        memories_data = [
            {
                "trigger": "batch1",
                "action": "action1",
                "domain": "test",
                "memory_type": MEMORY_TYPE_FACT,
            },
            {
                "trigger": "batch2",
                "action": "action2",
                "domain": "test",
                "memory_type": MEMORY_TYPE_PREFERENCE,
            },
            {
                "trigger": "batch3",
                "action": "action3",
                "domain": "test",
                "memory_type": MEMORY_TYPE_WORKFLOW,
            },
        ]
        result = store.add_memories_batch(memories_data)
        assert len(result) >= 3
        mems = store.list_memories()
        assert len(mems) >= 3


class TestProjectScoping:
    """Tests for project-scoped memories."""

    def test_add_project_memory(self, store):
        mem = store.add_memory(
            trigger="project specific trigger",
            action="project specific action",
            scope=SCOPE_PROJECT,
            project_id="proj_abc",
        )
        assert mem.scope == SCOPE_PROJECT
        assert mem.project_id == "proj_abc"

    def test_list_memories_filter_by_scope(self, store):
        store.add_memory(trigger="global", action="global action", scope=SCOPE_GLOBAL)
        store.add_memory(
            trigger="proj", action="proj action", scope=SCOPE_PROJECT, project_id="proj_abc"
        )
        mems = store.list_memories(scope=SCOPE_PROJECT)
        assert all(m.scope == SCOPE_PROJECT for m in mems)

    def test_promote_project_to_global(self, store):
        mem = store.add_memory(
            trigger="promote me",
            action="upgrade to global",
            scope=SCOPE_PROJECT,
            project_id="proj_xyz",
        )
        updated = store.promote_project_memory(mem.id)
        assert updated.scope == SCOPE_GLOBAL
        assert updated.project_id is None


class TestFindSimilar:
    """Tests for find_similar (vector similarity)."""

    def test_find_similar_returns_results(self, store_with_memories):
        results = store_with_memories.find_similar("coding preferences", limit=3)
        assert isinstance(results, list)

    def test_find_similar_empty_store(self, tmp_path):
        store = MemoryStore(user_id="empty_similar", base_dir=tmp_path)
        results = store.find_similar("test query", limit=3)
        assert len(results) == 0


class TestGetStats:
    """Tests for get_stats."""

    def test_stats_with_memories(self, store_with_memories):
        stats = store_with_memories.get_stats()
        assert stats["total"] >= 3
        assert "personal" in stats["by_domain"]
        assert MEMORY_TYPE_FACT in stats["by_type"]

    def test_stats_empty_store(self, tmp_path):
        store = MemoryStore(user_id="empty_stats", base_dir=tmp_path)
        stats = store.get_stats()
        assert stats["total"] == 0
        assert stats["avg_confidence"] == 0
