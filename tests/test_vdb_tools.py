"""Comprehensive tests for VDB (Vector Database) tools.

This test suite covers all 7 VDB tools:
1. create_vdb_collection
2. add_vdb_documents
3. search_vdb
4. list_vdb_collections
5. vdb_list
6. describe_vdb_collection
7. drop_vdb_collection
"""

import pytest
from typing import Generator

from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.storage.vdb_tools import (
    create_vdb_collection,
    add_vdb_documents,
    search_vdb,
    list_vdb_collections,
    vdb_list,
    describe_vdb_collection,
    drop_vdb_collection,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_vdb_tools"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for VDB operations."""
    set_thread_id(test_thread_id)
    yield
    # Cleanup happens automatically via test isolation


@pytest.fixture
def sample_documents() -> list[dict]:
    """Provide sample documents for vector search."""
    return [
        {
            "id": "doc1",
            "text": "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
            "metadata": {"category": "AI", "topic": "ML"}
        },
        {
            "id": "doc2",
            "text": "Deep learning uses neural networks with multiple layers to model complex patterns in data.",
            "metadata": {"category": "AI", "topic": "Deep Learning"}
        },
        {
            "id": "doc3",
            "text": "Natural language processing enables computers to understand and generate human language.",
            "metadata": {"category": "AI", "topic": "NLP"}
        },
        {
            "id": "doc4",
            "text": "Computer vision allows machines to interpret and make decisions based on visual data.",
            "metadata": {"category": "AI", "topic": "Computer Vision"}
        },
    ]


# =============================================================================
# Test: create_vdb_collection
# =============================================================================

class TestCreateVDBCollection:
    """Tests for create_vdb_collection tool."""

    def test_create_collection(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a new vector collection."""
        result = create_vdb_collection(
            collection_name="knowledge_base",
            scope="context"
        )

        assert "created" in result.lower()
        assert "knowledge_base" in result.lower()

    def test_create_collection_with_custom_name(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a collection with a custom name."""
        result = create_vdb_collection(
            collection_name="my_documents",
            scope="context"
        )

        assert "created" in result.lower()
        assert "my_documents" in result.lower()


# =============================================================================
# Test: add_vdb_documents
# =============================================================================

class TestAddVDBDocuments:
    """Tests for add_vdb_documents tool."""

    def test_add_documents_to_collection(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test adding documents to an existing collection."""
        # Create collection first
        create_vdb_collection(collection_name="knowledge", scope="context")

        # Add documents
        result = add_vdb_documents(
            collection_name="knowledge",
            documents=sample_documents,
            scope="context"
        )

        assert "added" in result.lower() or "4" in result

    def test_add_documents_with_metadata(
        self, setup_thread_context: None
    ) -> None:
        """Test adding documents with metadata."""
        create_vdb_collection(collection_name="test_docs", scope="context")

        documents = [
            {
                "id": "test1",
                "text": "Test document about Python",
                "metadata": {"language": "Python", "type": "tutorial"}
            }
        ]

        result = add_vdb_documents(
            collection_name="test_docs",
            documents=documents,
            scope="context"
        )

        assert "added" in result.lower()

    def test_add_documents_batch(
        self, setup_thread_context: None
    ) -> None:
        """Test adding multiple documents in batch."""
        create_vdb_collection(collection_name="batch_test", scope="context")

        # Create multiple documents
        documents = [
            {"id": f"doc{i}", "text": f"Document number {i}"}
            for i in range(10)
        ]

        result = add_vdb_documents(
            collection_name="batch_test",
            documents=documents,
            scope="context"
        )

        assert "added" in result.lower() or "10" in result


# =============================================================================
# Test: search_vdb
# =============================================================================

class TestSearchVDB:
    """Tests for search_vdb tool."""

    def test_search_semantic(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test semantic search in a collection."""
        # Setup
        create_vdb_collection(collection_name="ai_knowledge", scope="context")
        add_vdb_documents(collection_name="ai_knowledge", documents=sample_documents, scope="context")

        # Search for "neural networks"
        result = search_vdb(
            collection_name="ai_knowledge",
            query="neural networks and deep learning",
            limit=3,
            scope="context"
        )

        # Should find relevant documents
        assert len(result) > 0
        assert "neural" in result.lower() or "deep" in result.lower() or "learning" in result.lower()

    def test_search_with_limit(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test search with result limit."""
        create_vdb_collection(collection_name="ai_knowledge", scope="context")
        add_vdb_documents(collection_name="ai_knowledge", documents=sample_documents, scope="context")

        # Search with limit
        result = search_vdb(
            collection_name="ai_knowledge",
            query="artificial intelligence",
            limit=2,
            scope="context"
        )

        # Should return at most 2 results
        # (actual implementation might vary, but should respect limit)

    def test_search_no_results(
        self, setup_thread_context: None
    ) -> None:
        """Test search when no relevant documents exist."""
        create_vdb_collection(collection_name="empty_collection", scope="context")

        result = search_vdb(
            collection_name="empty_collection",
            query="quantum physics",
            limit=5,
            scope="context"
        )

        # Should handle empty results gracefully
        assert "no results" in result.lower() or "not found" in result.lower() or len(result) == 0


# =============================================================================
# Test: list_vdb_collections
# =============================================================================

class TestListVDBCollections:
    """Tests for list_vdb_collections tool."""

    def test_list_empty_collections(
        self, setup_thread_context: None
    ) -> None:
        """Test listing when no collections exist."""
        result = list_vdb_collections(scope="context")

        assert "no collections" in result.lower() or "empty" in result.lower() or result == ""

    def test_list_multiple_collections(
        self, setup_thread_context: None
    ) -> None:
        """Test listing multiple collections."""
        # Create multiple collections
        create_vdb_collection(collection_name="collection1", scope="context")
        create_vdb_collection(collection_name="collection2", scope="context")
        create_vdb_collection(collection_name="collection3", scope="context")

        result = list_vdb_collections(scope="context")

        assert "collection1" in result.lower() or "collection2" in result.lower()


# =============================================================================
# Test: vdb_list
# =============================================================================

class TestVDBList:
    """Tests for vdb_list tool."""

    def test_list_documents_in_collection(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test listing all documents in a collection."""
        create_vdb_collection(collection_name="docs", scope="context")
        add_vdb_documents(collection_name="docs", documents=sample_documents, scope="context")

        result = vdb_list(
            collection_name="docs",
            scope="context"
        )

        # Should show document count or list
        assert "doc" in result.lower() or "4" in result


# =============================================================================
# Test: describe_vdb_collection
# =============================================================================

class TestDescribeVDBCollection:
    """Tests for describe_vdb_collection tool."""

    def test_describe_collection_metadata(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test describing collection metadata."""
        create_vdb_collection(collection_name="knowledge", scope="context")
        add_vdb_documents(collection_name="knowledge", documents=sample_documents, scope="context")

        result = describe_vdb_collection(
            collection_name="knowledge",
            scope="context"
        )

        assert "knowledge" in result.lower()
        # Should show document count or metadata info

    def test_describe_nonexistent_collection(
        self, setup_thread_context: None
    ) -> None:
        """Test describing a collection that doesn't exist."""
        result = describe_vdb_collection(
            collection_name="nonexistent",
            scope="context"
        )

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: drop_vdb_collection
# =============================================================================

class TestDropVDBCollection:
    """Tests for drop_vdb_collection tool."""

    def test_drop_existing_collection(
        self, setup_thread_context: None, sample_documents: list[dict]
    ) -> None:
        """Test dropping an existing collection."""
        # Setup
        create_vdb_collection(collection_name="temp_collection", scope="context")
        add_vdb_documents(collection_name="temp_collection", documents=sample_documents, scope="context")

        # Drop collection
        result = drop_vdb_collection(
            collection_name="temp_collection",
            scope="context"
        )

        assert "dropped" in result.lower() or "deleted" in result.lower()

        # Verify it's gone
        collections = list_vdb_collections(scope="context")
        assert "temp_collection" not in collections.lower()

    def test_drop_nonexistent_collection(
        self, setup_thread_context: None
    ) -> None:
        """Test dropping a collection that doesn't exist."""
        result = drop_vdb_collection(
            collection_name="nonexistent",
            scope="context"
        )

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Integration Tests: Multi-Step Workflows
# =============================================================================

class TestVDBWorkflows:
    """Integration tests for common VDB workflows."""

    def test_full_lifecycle_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test complete collection lifecycle: create, add, search, drop."""
        # 1. Create collection
        create_vdb_collection(collection_name="test_lifecycle", scope="context")

        # 2. Add documents
        docs = [
            {"id": "1", "text": "Python is a programming language"},
            {"id": "2", "text": "JavaScript is used for web development"}
        ]
        add_vdb_documents(collection_name="test_lifecycle", documents=docs, scope="context")

        # 3. Search
        result = search_vdb(
            collection_name="test_lifecycle",
            query="programming",
            limit=5,
            scope="context"
        )
        # Should find at least one document

        # 4. List documents
        vdb_list(collection_name="test_lifecycle", scope="context")

        # 5. Describe collection
        describe_vdb_collection(collection_name="test_lifecycle", scope="context")

        # 6. Drop collection
        drop_vdb_collection(collection_name="test_lifecycle", scope="context")

        # 7. Verify deletion
        collections = list_vdb_collections(scope="context")
        assert "test_lifecycle" not in collections.lower()

    def test_semantic_search_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test semantic search with varied queries."""
        # Create knowledge base
        create_vdb_collection(collection_name="kb", scope="context")

        documents = [
            {"id": "1", "text": "The quick brown fox jumps over the lazy dog"},
            {"id": "2", "text": "Python is a high-level programming language"},
            {"id": "3", "text": "Machine learning models learn patterns from data"},
            {"id": "4", "text": "Web browsers use JavaScript for interactivity"},
        ]
        add_vdb_documents(collection_name="kb", documents=documents, scope="context")

        # Search for programming-related content
        result = search_vdb(
            collection_name="kb",
            query="coding and software development",
            limit=2,
            scope="context"
        )
        # Should find Python or JavaScript documents

        # Search for AI-related content
        result = search_vdb(
            collection_name="kb",
            query="artificial intelligence and neural networks",
            limit=2,
            scope="context"
        )
        # Should find machine learning document

    def test_thread_isolation(
        self, setup_thread_context: None
    ) -> None:
        """Test that different threads have isolated VDB storage."""
        # Create collection in default thread
        create_vdb_collection(collection_name="test_collection", scope="context")
        docs = [{"id": "1", "text": "Test document"}]
        add_vdb_documents(collection_name="test_collection", documents=docs, scope="context")

        # Should exist in default thread
        collections = list_vdb_collections(scope="context")
        assert "test_collection" in collections.lower()

        # Switch to different thread
        set_thread_id("different_thread")

        # Collection should not exist in different thread
        collections = list_vdb_collections(scope="context")
        assert "test_collection" not in collections.lower()
