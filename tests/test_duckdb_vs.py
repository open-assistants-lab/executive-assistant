"""Tests for DuckDB Vector Store operations."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cassey.storage.chunking import (
    Chunk,
    chunk_by_paragraph,
    chunk_by_size,
    prepare_documents_for_vs,
)


# =============================================================================
# Chunking Tests
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
        from cassey.storage.chunking import chunk_by_paragraph

        content = "Paragraph 1\n\nParagraph 2"
        chunks = chunk_by_paragraph(content, filename="test.txt", source="test")

        assert all(c.metadata.get("filename") == "test.txt" for c in chunks)
        assert all(c.metadata.get("source") == "test" for c in chunks)

    def test_prepare_documents_for_vs(self):
        """Test preparing documents for VS ingestion."""
        documents = [
            {"content": "First document", "metadata": {"title": "Doc1"}},
            {"content": "Second document", "metadata": {"title": "Doc2"}},
        ]

        chunks = prepare_documents_for_vs(documents, auto_chunk=True)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.content for c in chunks)


# =============================================================================
# DuckDB Collection Tests
# =============================================================================

class TestDuckDBCollection:
    """Test DuckDB collection operations."""

    @pytest.fixture
    def temp_vs_root(self, tmp_path):
        """Create a temporary VS root."""
        root = tmp_path / "groups" / "test_group" / "vs"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def collection(self, temp_vs_root):
        """Create a DuckDBCollection for testing."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="test_collection",
            workspace_id="test_group",
            conn=conn,
            dimension=384,
            path=temp_vs_root
        )

        # Initialize tables (normally done by create_duckdb_collection)
        docs_table = collection._table_name()
        vectors_table = collection._vector_table_name()

        # Create documents table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {docs_table} (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create vectors table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {vectors_table} (
                id VARCHAR PRIMARY KEY,
                embedding FLOAT[384],
                FOREIGN KEY (id) REFERENCES {docs_table}(id)
            );
        """)

        return collection

    def test_collection_init(self, collection):
        """Test collection initialization."""
        assert collection.name == "test_collection"
        assert collection.workspace_id == "test_group"
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
        with patch("cassey.storage.chunking.get_embeddings") as mock_embed:
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
        with patch("cassey.storage.chunking.get_embeddings") as mock_embed:
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
# VS Storage Tests
# =============================================================================

class TestVSStorage:
    """Test VS storage functions."""

    @pytest.fixture
    def temp_vs_root(self, tmp_path):
        """Create a temporary VS root."""
        root = tmp_path / "groups"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_get_vs_storage_dir(self, temp_vs_root):
        """Test getting VS storage directory."""
        from cassey.storage.duckdb_storage import get_vs_storage_dir

        with patch("cassey.storage.duckdb_storage.settings.GROUPS_ROOT", temp_vs_root):
            path = get_vs_storage_dir(storage_id="test_group")
            assert "test_group" in str(path)
            assert "vs" in str(path)

    def test_get_vs_storage_dir_from_context(self, temp_vs_root):
        """Test getting VS storage dir from context."""
        from cassey.storage.duckdb_storage import get_vs_storage_dir, _get_storage_id
        from cassey.storage.group_storage import set_group_id

        with patch("cassey.storage.duckdb_storage.settings.GROUPS_ROOT", temp_vs_root):
            set_group_id("test_group")
            path = get_vs_storage_dir()
            assert "test_group" in str(path)
            set_group_id("")  # Clear


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.postgres
class TestVSIntegration:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    async def test_create_duckdb_collection(self, db_conn, clean_test_data):
        """Test creating and using DuckDB collection."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        # Create in-memory collection for testing
        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="test_collection",
            workspace_id="test_group",
            conn=conn
        )

        # Initialize tables
        docs_table = collection._table_name()
        vectors_table = collection._vector_table_name()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {docs_table} (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {vectors_table} (
                id VARCHAR PRIMARY KEY,
                embedding FLOAT[384],
                FOREIGN KEY (id) REFERENCES {docs_table}(id)
            );
        """)

        # Add documents with mocked embeddings
        with patch("cassey.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.0] * 384, [0.0] * 384]

            docs = [
                {"content": "Test document 1", "metadata": {"id": "1"}},
                {"content": "Test document 2", "metadata": {"id": "2"}},
            ]

            count = collection.add_documents(docs)
            assert count >= 2

    @pytest.mark.asyncio
    async def test_list_duckdb_collections(self, db_conn, clean_test_data):
        """Test listing collections."""
        from cassey.storage.duckdb_storage import list_duckdb_collections

        # Should return empty list or available collections
        collections = list_duckdb_collections(storage_id="test_group")
        assert isinstance(collections, list)

    @pytest.mark.asyncio
    async def test_drop_duckdb_collections(self, db_conn, clean_test_data):
        """Test dropping collections."""
        from cassey.storage.duckdb_storage import drop_all_duckdb_collections

        # Should not raise
        count = drop_all_duckdb_collections(storage_id="test_group")
        assert isinstance(count, int)


# =============================================================================
# Search Tests
# =============================================================================

class TestSearchTypes:
    """Test different search types."""

    @pytest.fixture
    def temp_vs_root(self, tmp_path):
        """Create a temporary VS root."""
        root = tmp_path / "groups" / "test_group" / "vs"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def populated_collection(self, temp_vs_root):
        """Create a collection with test data."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="test_collection",
            workspace_id="test_group",
            conn=conn,
            dimension=384,
            path=temp_vs_root
        )

        # Initialize tables (normally done by create_duckdb_collection)
        docs_table = collection._table_name()
        vectors_table = collection._vector_table_name()

        # Create documents table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {docs_table} (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create vectors table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {vectors_table} (
                id VARCHAR PRIMARY KEY,
                embedding FLOAT[384],
                FOREIGN KEY (id) REFERENCES {docs_table}(id)
            );
        """)

        # Add documents with mocked embeddings
        with patch("cassey.storage.chunking.get_embeddings") as mock_embed:
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

    def test_hybrid_search(self, populated_collection):
        """Test hybrid search (vector + fulltext)."""
        results = populated_collection.search(
            "Python",
            limit=5,
            search_type="hybrid"
        )
        assert isinstance(results, list)

    def test_vector_search(self, populated_collection):
        """Test vector-only search."""
        with patch("cassey.storage.chunking.get_embeddings") as mock_embed:
            mock_embed.return_value = [[0.3] * 384]

            results = populated_collection.search(
                "Python",
                limit=5,
                search_type="vector"
            )
            assert isinstance(results, list)

    def test_fulltext_search(self, populated_collection):
        """Test fulltext-only search."""
        results = populated_collection.search(
            "Python",
            limit=5,
            search_type="fulltext"
        )
        assert isinstance(results, list)


# =============================================================================
# Schema Tests
# =============================================================================

class TestSchema:
    """Test database schema creation."""

    @pytest.fixture
    def temp_vs_root(self, tmp_path):
        """Create a temporary VS root."""
        root = tmp_path / "groups" / "test_group" / "vs"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def collection(self, temp_vs_root):
        """Create a DuckDBCollection for testing."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="test_collection",
            workspace_id="test_group",
            conn=conn,
            dimension=384,
            path=temp_vs_root
        )

        # Initialize tables (normally done by create_duckdb_collection)
        docs_table = collection._table_name()
        vectors_table = collection._vector_table_name()

        # Create documents table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {docs_table} (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create vectors table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {vectors_table} (
                id VARCHAR PRIMARY KEY,
                embedding FLOAT[384],
                FOREIGN KEY (id) REFERENCES {docs_table}(id)
            );
        """)

        return collection

    def test_table_names(self, collection):
        """Test that table names are generated correctly."""
        # Table names include the workspace_id prefix
        assert "test_collection_docs" in collection._table_name()
        assert "test_collection_vectors" in collection._vector_table_name()

    def test_fts_table_name(self, collection):
        """Test FTS table name generation."""
        fts_name = collection._fts_table_name()
        assert "fts_main" in fts_name
        assert "test_collection" in fts_name


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in VS operations."""

    def test_search_empty_collection(self, tmp_path):
        """Test searching an empty collection."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="empty_collection",
            workspace_id="test_group",
            conn=conn
        )

        # Initialize tables
        docs_table = collection._table_name()
        vectors_table = collection._vector_table_name()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {docs_table} (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                content TEXT,
                metadata JSON DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {vectors_table} (
                id VARCHAR PRIMARY KEY,
                embedding FLOAT[384],
                FOREIGN KEY (id) REFERENCES {docs_table}(id)
            );
        """)

        # Should not error, just return empty results
        results = collection.search("test query", limit=5)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_add_empty_documents(self, tmp_path):
        """Test adding empty document list."""
        from cassey.storage.duckdb_storage import DuckDBCollection
        import duckdb

        conn = duckdb.connect(":memory:")
        collection = DuckDBCollection(
            name="test_collection",
            workspace_id="test_group",
            conn=conn
        )

        count = collection.add_documents([])
        assert count == 0
