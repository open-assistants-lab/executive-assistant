# DuckDB + Hybrid KB Implementation Plan

## Overview
Replace SeekDB (Linux-only) with DuckDB + Hybrid (FTS + VSS) for cross-platform knowledge base storage.

## Data Model

```
Workspace
└── Collections (e.g., "Tax Documents", "Company Policies")
    └── Documents (e.g., "ITAA 1997.txt", "Employee Handbook.pdf")
        └── Chunks (automatically created, transparent to user)
```

### DuckDB Schema

```sql
-- One table per workspace/collection
{workspace_id}__{collection_name}_docs (
    id VARCHAR PRIMARY KEY,           -- Unique chunk ID
    document_id VARCHAR,              -- Groups chunks from same file
    content TEXT,                     -- Chunk content
    metadata JSON,                    -- filename, page, chunk_index
    created_at TIMESTAMP
)

{workspace_id}__{collection_name}_vectors (
    id VARCHAR PRIMARY KEY,           -- Links to docs.id
    embedding FLOAT[384]               -- Vector embedding
)

-- FTS index for fulltext search
PRAGMA create_fts_index("{table}", "id", "content")

-- HNSW index for vector search
CREATE INDEX vss_idx ON {table}_vectors USING HNSW (embedding)
```

## Chunking Strategy

| File Type | Chunking Method | Metadata |
|-----------|----------------|----------|
| **PDF** | By page + paragraph (3000 chars) | filename, page_num |
| **TXT/MD** | By paragraph (blank line separator) | filename, chunk_index |
| **DOCX** | By paragraph | filename, paragraph_num |
| **Other** | Fixed size (3000 chars) | filename, chunk_index |

### Chunking Implementation

```python
def chunk_document(content: str, filename: str, file_type: str) -> list[Chunk]:
    """Auto-chunk based on file type."""
    if file_type == "pdf":
        return chunk_pdf_by_page(content, filename)
    elif file_type in ("txt", "md"):
        return chunk_by_paragraph(content, filename)
    else:
        return chunk_by_size(content, filename, chunk_size=3000)
```

## Files to Create/Modify

### New Files
1. `src/cassey/storage/duckdb_storage.py` - DuckDB storage layer
2. `src/cassey/storage/chunking.py` - Document chunking utilities
3. `tests/test_duckdb_kb.py` - DuckDB KB tests

### Modified Files
1. `src/cassey/storage/kb_tools.py` - Update to use DuckDB
2. `src/cassey/storage/__init__.py` - Update imports
3. `src/cassey/config/settings.py` - Replace SeekDB settings with DuckDB
4. `pyproject.toml` - Replace `pyseekdb` with `duckdb>=1.1.0`
5. `.env.example` - Update KB environment variables

### Files to Delete
1. `src/cassey/storage/seekdb_storage.py` - Remove after migration
2. `tests/test_kb.py` - Replace with DuckDB tests

## Implementation Steps

### Phase 1: Test Cases (TDD)
- [ ] Write chunking tests
- [ ] Write DuckDB storage tests
- [ ] Write KB tools tests
- [ ] Write integration tests

### Phase 2: Core Implementation
- [ ] Implement chunking utilities
- [ ] Implement DuckDB storage layer
- [ ] Implement embedding generation (sentence-transformers)
- [ ] Implement hybrid search (FTS filter + VSS rank)

### Phase 3: KB Tools
- [ ] Update `create_kb_collection` - support documents + chunks
- [ ] Update `search_kb` - hybrid search
- [ ] Update `kb_list` - list collections
- [ ] Update `describe_kb_collection` - show collection info
- [ ] Update `drop_kb_collection` - delete collection
- [ ] Update `add_kb_documents` - add with auto-chunking
- [ ] Update `delete_kb_documents` - delete by ID

### Phase 4: Configuration
- [ ] Update settings.py
- [ ] Update pyproject.toml
- [ ] Update .env.example
- [ ] Update tool registry

### Phase 5: Migration
- [ ] Remove SeekDB imports
- [ ] Delete seekdb_storage.py
- [ ] Update documentation

## API Compatibility

**Tool signatures remain unchanged** for backward compatibility:

```python
@tool
def create_kb_collection(collection_name: str, documents: str = "") -> str

@tool
def search_kb(query: str, collection_name: str = "", limit: int = 5) -> str

@tool
def kb_list() -> str

@tool
def describe_kb_collection(collection_name: str) -> str

@tool
def drop_kb_collection(collection_name: str) -> str

@tool
def add_kb_documents(collection_name: str, documents: str) -> str

@tool
def delete_kb_documents(collection_name: str, ids: str) -> str
```

## Dependencies

```toml
# Remove
"pyseekdb>=0.1.0"

# Add
"duckdb>=1.1.0",
"sentence-transformers>=3.0.0",
"huggingface-hub>=0.34.0,<1.0",
```

## Performance Expectations

| Operation | Expected Time |
|-----------|---------------|
| Ingest 9MB document | ~17 seconds |
| Search (hybrid) | ~2-3ms |
| Create collection | <100ms |
| List collections | <50ms |

## Cross-Platform Support

- ✅ macOS (ARM64, x86_64)
- ✅ Linux (x86_64, ARM64)
- ✅ Windows (x86_64)
