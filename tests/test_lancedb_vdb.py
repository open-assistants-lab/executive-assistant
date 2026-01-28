"""Tests for LanceDB Vector Database operations."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from executive_assistant.storage.chunking import (
    Chunk,
    chunk_by_paragraph,
    chunk_by_size,
    prepare_documents_for_vdb,
)


# =============================================================================
# Chunking Tests (shared with DuckDB)
# =============================================================================

class TestChunking:
    """Test document chunking functionality."""

    def test_chunk_by_paragraph_single(self):
        """Test chunking a single short paragraph."""
        content = "This is a short paragraph."
        chunks = chunk_by_paragraph(content, filename="test.txt")

        assert len(chunks) == 1
        assert chunks[0].content == content
        assert chunks[0].metadata["filename"] == "test.txt"
        assert "chunk_index" in chunks[0].metadata

    def test_chunk_by_paragraph_multiple(self):
        """Test chunking multiple paragraphs."""
        content = """First paragraph.

Second paragraph.

Third paragraph."""
        # Use small chunk size (size of first paragraph) to force separate chunks
        # "First paragraph." is 17 chars, so using 17 ensures each paragraph is separate
        chunks = chunk_by_paragraph(content, filename="test.txt", chunk_size_chars=17)

        assert len(chunks) == 3
        assert "First paragraph." in chunks[0].content
        assert "Second paragraph." in chunks[1].content
        assert "Third paragraph." in chunks[2].content

    def test_chunk_by_paragraph_with_metadata(self):
        """Test that metadata is preserved."""
        chunks = chunk_by_paragraph(
            "Test content",
            filename="test.txt",
            source="test_source",
            author="test_author"
        )

        assert chunks[0].metadata["filename"] == "test.txt"
        assert chunks[0].metadata["source"] == "test_source"
        assert chunks[0].metadata["author"] == "test_author"

    def test_chunk_by_size(self):
        """Test chunking by character size."""
        content = "a" * 5000
        chunks = chunk_by_size(content, filename="large.txt", chunk_size=1000)

        assert len(chunks) == 5
        assert all(len(c.content) <= 1000 for c in chunks)
        assert all(c.metadata["chunk_index"] == i for i, c in enumerate(chunks))

    def test_chunk_by_empty_content(self):
        """Test chunking empty content."""
        chunks = chunk_by_paragraph("", filename="empty.txt")
        assert len(chunks) == 0

        chunks = chunk_by_size("", filename="empty.txt")
        assert len(chunks) == 0

    def test_chunk_preserves_metadata(self):
        """Test that chunking preserves file metadata."""
        from executive_assistant.storage.chunking import chunk_by_paragraph

        content = "Paragraph 1\n\nParagraph 2"
        chunks = chunk_by_paragraph(content, filename="test.txt", source="test")

        assert all(c.metadata.get("filename") == "test.txt" for c in chunks)
        assert all(c.metadata.get("source") == "test" for c in chunks)

    def test_prepare_documents_for_vdb(self):
        """Test preparing documents for VDB ingestion."""
        documents = [
            {"content": "First document", "metadata": {"title": "Doc1"}},
            {"content": "Second document", "metadata": {"title": "Doc2"}},
        ]

        chunks = prepare_documents_for_vdb(documents, auto_chunk=True)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.content for c in chunks)


# =============================================================================
# LanceDB Collection Tests
# =============================================================================

class TestLanceDBCollection:
    """Test LanceDB collection operations."""

    @pytest.fixture
    def temp_vdb_root(self, tmp_path):
        """Create a temporary VDB root."""
        root = tmp_path / "users" / "test_thread" / "vs"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def collection(self, temp_vdb_root):
        """Create a LanceDBCollection for testing."""
        from executive_assistant.storage.lancedb_storage import LanceDBCollection
        import lancedb
        import pyarrow as pa

        db_path = temp_vdb_root / ".lancedb"
        db = lancedb.connect(str(db_path))

        # Define schema
        dimension = 384
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("metadata", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dimension)),
        ])

        # Create table
        table = db.create_table(
            "test_collection",
            schema=schema,
            mode="overwrite"
        )

        collection = LanceDBCollection(
            name="test_collection",
            thread_id="test_thread",
            db=db,
            table=table,
            dimension=384,
            path=temp_vdb_root
        )

        return collection

    def test_collection_init(self, collection):
        """Test collection initialization."""
        assert collection.name == "test_collection"
        assert collection.thread_id == "test_thread"
        assert collection.dimension == 384

    def test_collection_count_empty(self, collection):
        """Test counting documents in empty collection."""
        assert collection.count() == 0

    def test_collection_documents_empty(self, collection):
        """Test getting documents from empty collection."""
        assert collection.documents == {}

    def test_add_documents(self, collection):
        """Test adding documents to collection."""
        # Mock get_embeddings to avoid real embedding generation
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            # Return fake 384-dim embeddings
            mock_embed.return_value = [[0.0] * 384, [0.0] * 384]

            documents = [
                {"content": "First document content", "metadata": {"title": "Doc1"}},
                {"content": "Second document content", "metadata": {"title": "Doc2"}},
            ]

            count = collection.add_documents(documents)

            assert count >= 2  # May be chunked
            assert collection.count() >= 2

    def test_search(self, collection):
        """Test searching collection."""
        # Add documents first
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.0] * 384]
            mock_embed.side_effect = [
                [[0.0] * 384, [0.0] * 384],  # For add_documents
                [[1.0] * 384],  # For search query
            ]

            collection.add_documents([
                {"content": "Python programming tutorial", "metadata": {"topic": "python"}},
                {"content": "Java introduction", "metadata": {"topic": "java"}},
            ])

            # Search
            results = collection.search("Python", limit=2, search_type="vector")
            assert isinstance(results, list)


# =============================================================================
# VDB Storage Tests
# =============================================================================

class TestVDBStorage:
    """Test VDB storage functions."""

    @pytest.fixture
    def temp_vdb_root(self, tmp_path):
        """Create a temporary VDB root."""
        root = tmp_path / "users"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_get_vdb_storage_dir(self, temp_vdb_root):
        """Test getting VDB storage directory."""
        from executive_assistant.storage.lancedb_storage import get_vdb_storage_dir

        with patch("executive_assistant.storage.lancedb_storage.get_thread_path") as get_root:
            get_root.return_value = temp_vdb_root / "test_thread"
            path = get_vdb_storage_dir(storage_id="test_thread")
            assert "test_thread" in str(path)
            assert "vdb" in str(path)

    def test_get_vdb_storage_dir_from_context(self, temp_vdb_root):
        """Test getting VDB storage dir from context."""
        from executive_assistant.storage.lancedb_storage import get_vdb_storage_dir, _get_storage_id
        from executive_assistant.storage.thread_storage import set_thread_id

        with patch("executive_assistant.storage.lancedb_storage.get_thread_path") as get_root:
            get_root.return_value = temp_vdb_root / "test_thread"
            set_thread_id("test_thread")
            path = get_vdb_storage_dir()
            assert "test_thread" in str(path)
            set_thread_id("")  # Clear


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.postgres
class TestVDBIntegration:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    async def test_create_lancedb_collection(self, db_conn, clean_test_data):
        """Test creating and using LanceDB collection."""
        from executive_assistant.storage.lancedb_storage import create_lancedb_collection

        # Create a test collection
        collection = create_lancedb_collection(
            storage_id="test_thread",
            collection_name="test_collection"
        )

        # Add documents with mocked embeddings
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.0] * 384, [0.0] * 384]

            docs = [
                {"content": "Test document 1", "metadata": {"id": "1"}},
                {"content": "Test document 2", "metadata": {"id": "2"}},
            ]

            count = collection.add_documents(docs)
            assert count >= 2

        # Clean up
        from executive_assistant.storage.lancedb_storage import drop_lancedb_collection
        drop_lancedb_collection(storage_id="test_thread", collection_name="test_collection")

    @pytest.mark.asyncio
    async def test_list_lancedb_collections(self, db_conn, clean_test_data):
        """Test listing collections."""
        from executive_assistant.storage.lancedb_storage import list_lancedb_collections

        # Should return empty list or available collections
        collections = list_lancedb_collections(storage_id="test_thread")
        assert isinstance(collections, list)

    @pytest.mark.asyncio
    async def test_drop_lancedb_collections(self, db_conn, clean_test_data):
        """Test dropping collections."""
        from executive_assistant.storage.lancedb_storage import drop_all_lancedb_collections

        # Should not raise
        count = drop_all_lancedb_collections(storage_id="test_thread")
        assert isinstance(count, int)


# =============================================================================
# Search Tests
# =============================================================================

class TestSearchTypes:
    """Test different search types."""

    @pytest.fixture
    def temp_vdb_root(self, tmp_path):
        """Create a temporary VDB root."""
        root = tmp_path / "users" / "test_thread" / "vs"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def populated_collection(self, temp_vdb_root):
        """Create a collection with test data."""
        from executive_assistant.storage.lancedb_storage import LanceDBCollection
        import lancedb
        import pyarrow as pa

        db_path = temp_vdb_root / ".lancedb"
        db = lancedb.connect(str(db_path))

        # Define schema
        dimension = 384
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("metadata", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dimension)),
        ])

        # Create table
        table = db.create_table(
            "test_collection",
            schema=schema,
            mode="overwrite"
        )

        collection = LanceDBCollection(
            name="test_collection",
            thread_id="test_thread",
            db=db,
            table=table,
            dimension=384,
            path=temp_vdb_root
        )

        # Add documents with mocked embeddings
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            # Return different embeddings for variety
            mock_embed.side_effect = [
                [[0.1] * 384, [0.2] * 384],  # For add_documents
                [[0.3] * 384],  # For search queries
            ]

            collection.add_documents([
                {"content": "Python programming tutorial for beginners", "metadata": {"topic": "python"}},
                {"content": "Introduction to machine learning", "metadata": {"topic": "ml"}},
            ])

        return collection

    def test_vector_search(self, populated_collection):
        """Test vector-only search."""
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.3] * 384]

            results = populated_collection.search(
                "Python",
                limit=5,
                search_type="vector"
            )
            assert isinstance(results, list)

    def test_fulltext_search(self, populated_collection):
        """Test fulltext-only search (LanceDB falls back to vector search).

        Note: LanceDB doesn't have native full-text search. The fulltext search
        type will fall back to vector search, which is the expected behavior.
        """
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.3] * 384]

            results = populated_collection.search(
                "Python",
                limit=5,
                search_type="fulltext"
            )
            assert isinstance(results, list)

    def test_hybrid_search(self, populated_collection):
        """Test hybrid search (LanceDB falls back to vector)."""
        with patch("executive_assistant.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.3] * 384]

            results = populated_collection.search(
                "Python",
                limit=5,
                search_type="hybrid"
            )
            assert isinstance(results, list)


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in VDB operations."""

    def test_search_empty_collection(self, tmp_path):
        """Test searching an empty collection."""
        from executive_assistant.storage.lancedb_storage import create_lancedb_collection

        collection = create_lancedb_collection(
            storage_id="test_thread",
            collection_name="empty_collection",
        )

        # Should not error, just return empty results
        results = collection.search("test query", limit=5)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_add_empty_documents(self, tmp_path):
        """Test adding empty document list."""
        from executive_assistant.storage.lancedb_storage import create_lancedb_collection

        collection = create_lancedb_collection(
            storage_id="test_thread",
            collection_name="test_collection",
        )

        count = collection.add_documents([])
        assert count == 0
