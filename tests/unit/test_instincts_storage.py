"""Tests for instincts storage."""

import pytest
import shutil

from src.storage.instincts import InstinctsStore, get_instincts_store


class TestInstinctsStore:
    """Tests for InstinctsStore."""

    @pytest.fixture
    def store(self):
        """Create a test store."""
        user_id = "test_instincts_user"
        store = InstinctsStore(user_id)
        yield store
        shutil.rmtree(f"data/users/{user_id}", ignore_errors=True)

    def test_add_instinct(self, store):
        """Test adding an instinct."""
        instinct = store.add_instinct(
            trigger="when writing Python",
            action="use type hints",
            confidence=0.5,
            domain="preference",
        )

        assert instinct is not None
        assert instinct.trigger == "when writing Python"
        assert instinct.action == "use type hints"
        assert instinct.confidence == 0.5
        assert instinct.domain == "preference"

    def test_add_duplicate_instinct(self, store):
        """Test adding duplicate instinct increases confidence."""
        store.add_instinct(trigger="test trigger", action="test action")
        store.add_instinct(trigger="test trigger", action="test action")

        instinct = store.get_instinct(store._generate_id("test trigger", "test action"))
        assert instinct is not None
        assert instinct.observations == 2

    def test_list_instincts(self, store):
        """Test listing instincts."""
        store.add_instinct("trigger1", "action1", confidence=0.5)
        store.add_instinct("trigger2", "action2", confidence=0.8)
        store.add_instinct("trigger3", "action3", confidence=0.3)

        instincts = store.list_instincts()

        assert len(instincts) == 3
        assert instincts[0].confidence == 0.8

    def test_list_instincts_filter_domain(self, store):
        """Test listing instincts with domain filter."""
        store.add_instinct("trigger1", "action1", domain="preference")
        store.add_instinct("trigger2", "action2", domain="correction")

        prefs = store.list_instincts(domain="preference")
        assert len(prefs) == 1
        assert prefs[0].domain == "preference"

    def test_list_instincts_filter_confidence(self, store):
        """Test listing instincts with confidence filter."""
        store.add_instinct("trigger1", "action1", confidence=0.8)
        store.add_instinct("trigger2", "action2", confidence=0.3)

        high_conf = store.list_instincts(min_confidence=0.5)
        assert len(high_conf) == 1

    def test_remove_instinct(self, store):
        """Test removing an instinct."""
        instinct = store.add_instinct("test trigger", "test action")
        removed = store.remove_instinct(instinct.id)

        assert removed is True
        assert store.get_instinct(instinct.id) is None

    def test_search_fts(self, store):
        """Test FTS search."""
        store.add_instinct("when writing functions", "use functional style")
        store.add_instinct("when writing classes", "use OOP patterns")

        results = store.search_fts("functions")
        assert len(results) >= 1

    def test_search_semantic(self, store):
        """Test semantic search."""
        store.add_instinct("when coding in Python", "use type hints")
        store.add_instinct("when testing", "write unit tests first")

        results = store.search_semantic("programming language syntax", limit=5)
        assert isinstance(results, list)

    def test_search_hybrid(self, store):
        """Test hybrid search."""
        store.add_instinct("python coding", "use type hints")
        store.add_instinct("testing code", "write tests first")

        results = store.search_hybrid("python programming", limit=5)
        assert isinstance(results, list)

    def test_instinct_id_generation(self, store):
        """Test instinct ID generation."""
        id1 = store._generate_id("trigger1", "action1")
        id2 = store._generate_id("trigger1", "action1")
        id3 = store._generate_id("trigger2", "action1")

        assert id1 == id2
        assert id1 != id3
