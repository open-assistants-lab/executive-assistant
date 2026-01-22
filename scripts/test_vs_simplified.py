#!/usr/bin/env python
"""Test simplified VS tools interface.

This validates that the new simplified parameters work correctly:
- create_vs_collection with content parameter (single document)
- create_vs_collection with documents parameter (JSON array)
- create_vs_collection empty, then add_vs_documents with content
- search_vs for semantic search
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from contextvars import ContextVar
from executive_assistant.storage.vs_tools import (
    create_vs_collection,
    add_vs_documents,
    search_vs,
    vs_list,
    drop_vs_collection,
)
from executive_assistant.storage.file_sandbox import set_thread_id


def test_simplified_vs_interface():
    """Test the simplified VS tools with content parameter."""

    storage_id = "telegram:999000"  # thread_id format expected by FileSandbox
    collection_name = "test_collection"

    # Set context
    set_thread_id(storage_id)

    print("=" * 60)
    print("VS Tools Simplified Interface Test")
    print("=" * 60)

    # Test 1: Create collection with single content (simple method)
    print("\n[1/5] Creating collection with single content (simple method)...")
    result = create_vs_collection.invoke({
        "collection_name": collection_name,
        "content": "Executive Assistant is an AI assistant built with LangGraph for task automation."
    })
    print(f"   Result: {result}")
    assert "Created VS collection" in result and "chunks from 1 document" in result, result
    print("   ✅ Single content method works")

    # Test 2: Add another single document
    print("\n[2/5] Adding another single document...")
    result = add_vs_documents.invoke({
        "collection_name": collection_name,
        "content": "LanceDB is an embedded vector database for semantic search."
    })
    print(f"   Result: {result}")
    assert "Added" in result and "chunks" in result and "document" in result, result
    print("   ✅ Add single content works")

    # Test 3: Search for semantically similar content
    print("\n[3/5] Searching for 'AI assistant'...")
    result = search_vs.invoke({
        "query": "AI assistant",
        "collection_name": collection_name,
        "limit": 5
    })
    print(f"   Result preview:")
    assert "Search results" in result or "From" in result, result
    # Show first few lines
    for line in result.split('\n')[:5]:
        print(f"      {line}")
    print("   ✅ Semantic search works")

    # Test 4: List collections
    print("\n[4/5] Listing VS collections...")
    result = vs_list.invoke({})
    print(f"   Result: {result}")
    assert collection_name in result, f"Collection not found in list: {result}"
    print("   ✅ Collection listed correctly")

    # Test 5: Test JSON array method (backward compatibility)
    print("\n[5/5] Testing JSON array method (backward compatibility)...")
    result = create_vs_collection.invoke({
        "collection_name": f"{collection_name}_json",
        "documents": '[{"content": "Test document 1"}, {"content": "Test document 2"}]'
    })
    print(f"   Result: {result}")
    assert "Created VS collection" in result and "2 document" in result, result
    print("   ✅ JSON array method still works (backward compatible)")

    # Cleanup
    print("\n[Cleanup] Removing test collections...")
    drop_vs_collection.invoke({"collection_name": collection_name})
    drop_vs_collection.invoke({"collection_name": f"{collection_name}_json"})
    print("   ✅ Test collections removed")

    print("\n" + "=" * 60)
    print("✅ All VS simplified interface tests passed!")
    print("=" * 60)


def test_empty_collection_workflow():
    """Test creating empty collection then adding documents."""

    storage_id = "telegram:999001"  # thread_id format expected by FileSandbox
    collection_name = "test_workflow"

    # Set context
    set_thread_id(storage_id)

    print("\n" + "=" * 60)
    print("VS Empty Collection Workflow Test")
    print("=" * 60)

    # Create empty collection
    print("\n[1/3] Creating empty collection...")
    result = create_vs_collection.invoke({
        "collection_name": collection_name
    })
    print(f"   Result: {result}")
    assert "empty, ready for documents" in result, result
    print("   ✅ Empty collection created")

    # Add documents
    print("\n[2/3] Adding documents to empty collection...")
    result = add_vs_documents.invoke({
        "collection_name": collection_name,
        "content": "This is a test document added to empty collection."
    })
    print(f"   Result: {result}")
    assert "Added" in result, result
    print("   ✅ Documents added to empty collection")

    # Search
    print("\n[3/3] Searching the collection...")
    result = search_vs.invoke({
        "query": "test document",
        "collection_name": collection_name
    })
    print(f"   Result preview: {result[:100]}...")
    assert "Search results" in result or "From" in result, result
    print("   ✅ Search works on populated collection")

    # Cleanup
    print("\n[Cleanup] Removing test collection...")
    drop_vs_collection.invoke({"collection_name": collection_name})
    print("   ✅ Test collection removed")

    print("\n" + "=" * 60)
    print("✅ Empty collection workflow test passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_simplified_vs_interface()
        test_empty_collection_workflow()
    except AssertionError as exc:
        print(f"\n❌ Test failed: {exc}")
        sys.exit(1)
    else:
        print("\n✅ All tests passed.")
        sys.exit(0)
