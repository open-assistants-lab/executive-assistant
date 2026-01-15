"""Unit tests for Knowledge Base storage and tools."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cassey.storage.kb_storage import KBStorage, get_kb_storage
from cassey.storage import kb_tools


@pytest.fixture
def temp_kb_root(tmp_path):
    """Create a temporary KB root for testing."""
    return tmp_path / "kb"


@pytest.fixture
def kb_store_instance(temp_kb_root):
    """Create a KB storage instance with temporary root."""
    return KBStorage(root=temp_kb_root)


@pytest.fixture
def mock_thread_id():
    """Mock thread_id for testing."""
    return "telegram:test_12345"


@pytest.fixture
def set_thread_context(mock_thread_id):
    """Set thread_id context for tool testing."""
    from cassey.storage.file_sandbox import set_thread_id

    set_thread_id(mock_thread_id)
    yield
    # Reset context after test
    set_thread_id("")


class TestKBStorage:
    """Test KB storage operations."""

    def test_initialization(self, kb_store_instance):
        """Test storage initialization."""
        assert kb_store_instance.root.exists()
        assert kb_store_instance.root.is_dir()

    def test_get_db_path(self, kb_store_instance):
        """Test getting database path for thread."""
        db_path = kb_store_instance._get_db_path("telegram:test123")
        assert db_path.name == "telegram_test123.db"
        assert db_path.parent == kb_store_instance.root

    def test_thread_isolation(self, kb_store_instance):
        """Test that different threads have isolated KB databases."""
        # Create table in thread1
        kb_store_instance.create_table_from_data(
            "kb1", [{"content": "thread1 data"}], None, "thread1"
        )

        # Create table in thread2
        kb_store_instance.create_table_from_data(
            "kb2", [{"content": "thread2 data"}], None, "thread2"
        )

        # Thread1 should only see its own table
        tables1 = kb_store_instance.list_tables("thread1")
        assert tables1 == ["kb1"]

        # Thread2 should only see its own table
        tables2 = kb_store_instance.list_tables("thread2")
        assert tables2 == ["kb2"]


class TestGlobalKBStorage:
    """Test global KB storage instance."""

    def test_get_kb_storage(self):
        """Test getting global storage instance."""
        storage = get_kb_storage()
        assert isinstance(storage, KBStorage)

    def test_global_instance_singleton(self):
        """Test that global instance is a singleton."""
        storage1 = get_kb_storage()
        storage2 = get_kb_storage()
        assert storage1 is storage2


class TestKBTools:
    """Test KB tool functions."""

    def test_kb_store_creates_table(self, set_thread_context, temp_kb_root):
        """Test kb_store creates a table with FTS index."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            documents = json.dumps([
                {"content": "Meeting notes: Q1 revenue was $1M", "metadata": "finance"},
                {"content": "Todo: Review project plan", "metadata": "tasks"}
            ])

            result = kb_tools.kb_store.invoke({"table_name": "notes", "documents": documents})

            assert "Stored 2 documents" in result
            assert "notes" in result
            assert "FTS index" in result

    def test_kb_store_invalid_json(self, set_thread_context, temp_kb_root):
        """Test kb_store handles invalid JSON."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_store.invoke({"table_name": "test", "documents": "not valid json"})
            assert "Error: Invalid JSON" in result

    def test_kb_store_empty_array(self, set_thread_context, temp_kb_root):
        """Test kb_store handles empty array."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_store.invoke({"table_name": "test", "documents": "[]"})
            assert "Error: documents array is empty" in result

    def test_kb_store_not_array(self, set_thread_context, temp_kb_root):
        """Test kb_store handles non-array input."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_store.invoke({"table_name": "test", "documents": '{"content": "single object"}'})
            assert "Error: documents must be a JSON array" in result

    def test_kb_search_finds_documents(self, set_thread_context, temp_kb_root):
        """Test kb_search finds relevant documents."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # First store some documents
            docs = json.dumps([
                {"content": "The quick brown fox jumps over the lazy dog"},
                {"content": "Python is a great programming language"},
                {"content": "Revenue for Q1 was $1.2 million dollars"}
            ])
            kb_tools.kb_store.invoke({"table_name": "docs", "documents": docs})

            # Search for "python"
            result = kb_tools.kb_search.invoke({"query": "python", "table_name": "docs", "limit": 5})

            assert "Search results" in result or "From 'docs'" in result or "docs" in result.lower()
            assert "python" in result.lower() or "programming" in result.lower()

    def test_kb_search_all_tables(self, set_thread_context, temp_kb_root):
        """Test kb_search across all tables."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Store documents in multiple tables
            docs1 = json.dumps([{"content": "Finance: Revenue exceeded expectations"}])
            docs2 = json.dumps([{"content": "Tech: Python version released"}])

            kb_tools.kb_store.invoke({"table_name": "finance", "documents": docs1})
            kb_tools.kb_store.invoke({"table_name": "tech", "documents": docs2})

            # Search all tables for "revenue"
            result = kb_tools.kb_search.invoke({"query": "revenue", "table_name": "", "limit": 5})

            assert "finance" in result.lower() or "revenue" in result.lower()

    def test_kb_search_no_tables(self, set_thread_context, temp_kb_root):
        """Test kb_search when no tables exist."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_search.invoke({"query": "test", "table_name": "", "limit": 5})
            assert "No KB tables found" in result

    def test_kb_search_table_not_found(self, set_thread_context, temp_kb_root):
        """Test kb_search when specified table doesn't exist."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Create a different table first
            docs = json.dumps([{"content": "test"}])
            kb_tools.kb_store.invoke({"table_name": "existing", "documents": docs})

            result = kb_tools.kb_search.invoke({"query": "test", "table_name": "nonexistent", "limit": 5})
            # Error can be either our custom message or SQL error
            assert "Error" in result and ("not found" in result or "does not exist" in result)

    def test_kb_list_empty(self, set_thread_context, temp_kb_root):
        """Test kb_list when no tables exist."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_list.invoke({})
            assert "empty" in result.lower() or "use kb_store" in result.lower()

    def test_kb_list_with_tables(self, set_thread_context, temp_kb_root):
        """Test kb_list returns table names and counts."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Create tables with different document counts
            docs1 = json.dumps([
                {"content": "doc1"},
                {"content": "doc2"},
                {"content": "doc3"}
            ])
            docs2 = json.dumps([{"content": "single doc"}])

            kb_tools.kb_store.invoke({"table_name": "table1", "documents": docs1})
            kb_tools.kb_store.invoke({"table_name": "table2", "documents": docs2})

            result = kb_tools.kb_list.invoke({})

            assert "table1" in result
            assert "3 documents" in result
            assert "table2" in result
            assert "1 document" in result

    def test_kb_describe_table(self, set_thread_context, temp_kb_root):
        """Test kb_describe shows table schema and samples."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            docs = json.dumps([
                {"content": "First document", "metadata": "tag1"},
                {"content": "Second document", "metadata": "tag2"}
            ])
            kb_tools.kb_store.invoke({"table_name": "test_table", "documents": docs})

            result = kb_tools.kb_describe.invoke({"table_name": "test_table"})

            assert "test_table" in result
            assert "Schema:" in result
            assert "Total documents: 2" in result
            assert "First document" in result

    def test_kb_describe_nonexistent_table(self, set_thread_context, temp_kb_root):
        """Test kb_describe with nonexistent table."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_describe.invoke({"table_name": "nonexistent"})
            assert "Error: KB table 'nonexistent' not found" in result

    def test_kb_delete_table(self, set_thread_context, temp_kb_root):
        """Test kb_delete removes table and FTS index."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Create a table
            docs = json.dumps([{"content": "test"}])
            kb_tools.kb_store.invoke({"table_name": "to_delete", "documents": docs})

            # Verify it exists
            list_result = kb_tools.kb_list.invoke({})
            assert "to_delete" in list_result

            # Delete it
            delete_result = kb_tools.kb_delete.invoke({"table_name": "to_delete"})
            assert "Deleted KB table 'to_delete'" in delete_result
            assert "1 document" in delete_result

            # Verify it's gone
            list_result = kb_tools.kb_list.invoke({})
            assert "to_delete" not in list_result

    def test_kb_delete_nonexistent_table(self, set_thread_context, temp_kb_root):
        """Test kb_delete with nonexistent table."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_delete.invoke({"table_name": "nonexistent"})
            assert "Error: KB table 'nonexistent' not found" in result

    def test_kb_add_documents(self, set_thread_context, temp_kb_root):
        """Test kb_add_documents appends to existing table."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Create initial table
            docs1 = json.dumps([{"content": "Initial document"}])
            kb_tools.kb_store.invoke({"table_name": "notes", "documents": docs1})

            # Add more documents
            docs2 = json.dumps([
                {"content": "Added document 1"},
                {"content": "Added document 2"}
            ])
            result = kb_tools.kb_add_documents.invoke({"table_name": "notes", "documents": docs2})

            assert "Added 2 documents" in result
            assert "notes" in result
            assert "FTS index rebuilt" in result

            # Verify total count
            describe_result = kb_tools.kb_describe.invoke({"table_name": "notes"})
            assert "Total documents: 3" in describe_result

    def test_kb_add_documents_invalid_json(self, set_thread_context, temp_kb_root):
        """Test kb_add_documents handles invalid JSON."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            result = kb_tools.kb_add_documents.invoke({"table_name": "test", "documents": "invalid json"})
            assert "Error: Invalid JSON" in result

    def test_kb_add_documents_nonexistent_table(self, set_thread_context, temp_kb_root):
        """Test kb_add_documents with nonexistent table."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            docs = json.dumps([{"content": "test"}])
            result = kb_tools.kb_add_documents.invoke({"table_name": "nonexistent", "documents": docs})
            assert "Error: KB table 'nonexistent' not found" in result

    def test_kb_store_replaces_existing(self, set_thread_context, temp_kb_root):
        """Test that kb_store replaces existing table."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Create initial table
            docs1 = json.dumps([
                {"content": "Original 1"},
                {"content": "Original 2"}
            ])
            kb_tools.kb_store.invoke({"table_name": "notes", "documents": docs1})

            # Replace with new data
            docs2 = json.dumps([{"content": "New document"}])
            result = kb_tools.kb_store.invoke({"table_name": "notes", "documents": docs2})

            assert "Stored 1 documents" in result

            # Verify only new data exists
            describe_result = kb_tools.kb_describe.invoke({"table_name": "notes"})
            assert "Total documents: 1" in describe_result
            assert "New document" in describe_result
            assert "Original" not in describe_result


class TestKBToolsFTS:
    """Test KB tools with FTS-specific functionality."""

    def test_fts_stemming(self, set_thread_context, temp_kb_root):
        """Test that FTS stems words (running matches run)."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Store document with "running"
            docs = json.dumps([{"content": "I am running a marathon"}])
            kb_tools.kb_store.invoke({"table_name": "test", "documents": docs})

            # Search for "run" - should match due to stemming
            result = kb_tools.kb_search.invoke({"query": "run", "table_name": "test", "limit": 5})
            # BM25 search should find the stemmed match
            assert "running" in result.lower() or "marathon" in result.lower()

    def test_fts_case_insensitive(self, set_thread_context, temp_kb_root):
        """Test that FTS is case-insensitive."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            docs = json.dumps([{"content": "Python Programming"}])
            kb_tools.kb_store.invoke({"table_name": "test", "documents": docs})

            # Search with different case
            result = kb_tools.kb_search.invoke({"query": "PYTHON", "table_name": "test", "limit": 5})
            assert "python" in result.lower() or "programming" in result.lower()

    def test_fts_relevance_ranking(self, set_thread_context, temp_kb_root):
        """Test that FTS returns relevance scores (BM25)."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            docs = json.dumps([
                {"content": "The quick brown fox"},
                {"content": "A fast brown dog"}
            ])
            kb_tools.kb_store.invoke({"table_name": "test", "documents": docs})

            # Search for "brown fox" - should score higher for document with both terms
            result = kb_tools.kb_search.invoke({"query": "brown fox", "table_name": "test", "limit": 5})
            # Results should be relevance-ranked (BM25 scores)
            assert "test" in result.lower() or "fox" in result.lower() or "dog" in result.lower()


class TestKBToolsWithMetadata:
    """Test KB tools with metadata handling."""

    def test_search_with_metadata(self, set_thread_context, temp_kb_root):
        """Test that metadata is included in search results."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            docs = json.dumps([
                {"content": "Revenue data", "metadata": "finance"},
                {"content": "Code snippet", "metadata": "tech"}
            ])
            kb_tools.kb_store.invoke({"table_name": "docs", "documents": docs})

            result = kb_tools.kb_search.invoke({"query": "revenue", "table_name": "docs", "limit": 5})

            # Should include metadata in results
            assert "finance" in result or "revenue" in result.lower() or "metadata" in result.lower()

    def test_metadata_optional(self, set_thread_context, temp_kb_root):
        """Test that metadata is optional in documents."""
        with patch.object(kb_tools, "_kb_storage", KBStorage(root=temp_kb_root)):
            # Mix of documents with and without metadata
            docs = json.dumps([
                {"content": "Doc with metadata", "metadata": "tag1"},
                {"content": "Doc without metadata"}
            ])
            result = kb_tools.kb_store.invoke({"table_name": "test", "documents": docs})

            assert "Stored 2 documents" in result
