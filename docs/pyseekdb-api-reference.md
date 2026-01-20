# pyseekdb API Reference

**Source:** [oceanbase/pyseekdb](https://github.com/oceanbase/pyseekdb)

**License:** Apache-2.0

**Description:** pyseekdb aims to provide developers with simple and easy-to-use APIs for accessing seekdb and OceanBase's AI-related features. It provides efficient and easy-to-use APIs with a fixed data model and schema-free interfaces.

---

## Installation

```shell
pip install -U pyseekdb
```

---

## 1. Client Connection

The `Client` class provides a unified interface for connecting to seekdb in different modes. It automatically selects the appropriate connection mode based on the parameters provided.

### 1.1 Embedded seekdb Client

Connect to a local embedded seekdb instance:

```python
import pyseekdb

# Create embedded client with explicit path
client = pyseekdb.Client(
    path="./seekdb",      # Path to seekdb data directory (DIRECTORY, not file)
    database="demo"        # Database name
)

# Create embedded client with default path (current working directory)
# If path is not provided, uses seekdb.db in the current process working directory
client = pyseekdb.Client(
    database="demo"        # Database name (path defaults to current working directory/seekdb.db)
)
```

**IMPORTANT:** In embedded mode, `path` is a **DIRECTORY** where SeekDB creates `seekdb.db`, `seekdb.db-wal`, and `seekdb.db-shm` files.

### 1.2 Remote Server Client

Connect to a remote server (supports both seekdb Server and OceanBase Server):

```python
import pyseekdb

# Create remote server client (seekdb Server)
client = pyseekdb.Client(
    host="127.0.0.1",      # Server host
    port=2881,              # Server port (default: 2881)
    database="demo",        # Database name
    user="root",            # Username (default: "root")
    password=""             # Password (can be retrieved from SEEKDB_PASSWORD environment variable)
)

# Create remote server client (OceanBase Server)
client = pyseekdb.Client(
    host="127.0.0.1",      # Server host
    port=2881,              # Server port (default: 2881)
    tenant="sys",          # Tenant name (default: sys)
    database="demo",       # Database name
    user="root",           # Username (default: "root")
    password=""             # Password (can be retrieved from SEEKDB_PASSWORD environment variable)
)
```

### 1.3 Client Methods and Properties

| Method / Property | Description |
| --- | --- |
| `create_collection()` | Create a new collection (see Collection Management) |
| `get_collection()` | Get an existing collection object |
| `delete_collection()` | Delete a collection |
| `list_collections()` | List all collections in the current database |
| `has_collection()` | Check if a collection exists |
| `get_or_create_collection()` | Get an existing collection or create it if it doesn't exist |
| `count_collection()` | Count the number of collections in the current database |

---

## 2. AdminClient Connection and Database Management

The `AdminClient` class provides database management operations. It uses the same connection modes as `Client` but only exposes database management methods.

### 2.1 AdminClient Methods

| Method | Description |
| --- | --- |
| `create_database(name, tenant=DEFAULT_TENANT)` | Create a new database |
| `get_database(name, tenant=DEFAULT_TENANT)` | Get database object with metadata |
| `delete_database(name, tenant=DEFAULT_TENANT)` | Delete a database |
| `list_databases(limit=None, offset=None, tenant=DEFAULT_TENANT)` | List all databases with optional pagination |

---

## 3. Collection (Table) Management

Collections are the primary data structures in pyseekdb, similar to tables in traditional databases. Each collection stores documents with vector embeddings, metadata, and full-text search capabilities.

### 3.1 Creating a Collection

```python
import pyseekdb
from pyseekdb import (
    DefaultEmbeddingFunction,
    HNSWConfiguration,
    Configuration,
    FulltextParserConfig
)

# Create a client
client = pyseekdb.Client(host="127.0.0.1", port=2881, database="test")

# Create a collection with default configuration
collection = client.create_collection(
    name="my_collection"
    # embedding_function defaults to DefaultEmbeddingFunction() (384 dimensions)
)

# Create a collection with custom embedding function
ef = UserDefinedEmbeddingFunction(model_name='all-MiniLM-L6-v2')
collection = client.create_collection(
    name="my_collection",
    embedding_function=ef
)

# Recommended: Create a collection with Configuration wrapper
# Using IK parser (default for Chinese text)
config = Configuration(
    hnsw=HNSWConfiguration(dimension=384, distance='cosine'),
    fulltext_config=FulltextParserConfig(parser='ik')
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=ef
)

# Recommended: Create a collection with Configuration (only HNSW config, uses default parser)
config = Configuration(
    hnsw=HNSWConfiguration(dimension=384, distance='cosine')
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=ef
)

# Create a collection with Space parser (for space-separated languages)
config = Configuration(
    hnsw=HNSWConfiguration(dimension=384, distance='cosine'),
    fulltext_config=FulltextParserConfig(parser='space')
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=ef
)

# Create a collection with Ngram parser and custom parameters
config = Configuration(
    hnsw=HNSWConfiguration(dimension=384, distance='cosine'),
    fulltext_config=FulltextParserConfig(parser='ngram', params={'ngram_token_size': 3})
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=ef
)

# Create a collection without embedding function (embeddings must be provided manually)
config = Configuration(
    hnsw=HNSWConfiguration(dimension=128, distance='cosine')
)
collection = client.create_collection(
    name="my_collection",
    configuration=config,
    embedding_function=None  # Explicitly disable embedding function
)

# Get or create collection (creates if doesn't exist)
collection = client.get_or_create_collection(
    name="my_collection",
)
```

**Parameters:**

*   `name` (str): Collection name (required). Must be non-empty, use only letters/digits/underscore (`[a-zA-Z0-9_]`), and be at most 512 characters.
*   `configuration` (Configuration, HNSWConfiguration, or None, optional): Index configuration
    *   **Recommended:** `Configuration` - Wrapper class that can include both `HNSWConfiguration` and `FulltextParserConfig`
    *   `HNSWConfiguration`: Vector index configuration with `dimension` and `distance` metric (backward compatibility)
    *   If not provided, uses default (dimension=384, distance='cosine', parser='ik')
    *   If set to `None`, dimension will be calculated from `embedding_function`
*   `embedding_function` (EmbeddingFunction, optional): Function to convert documents to embeddings
    *   If not provided, uses `DefaultEmbeddingFunction()` (384 dimensions)
    *   If set to `None`, collection will not have an embedding function
    *   If provided, the dimension will be automatically calculated and validated against `configuration.dimension`

**Fulltext Parser Options:**

*   `'ik'` (default): IK parser for Chinese text segmentation
*   `'space'`: Space-separated tokenizer for languages like English
*   `'ngram'`: N-gram tokenizer
*   `'ngram2'`: 2-gram tokenizer
*   `'beng'`: Bengali text parser

### 3.2 Getting a Collection

```python
# Get an existing collection (uses default embedding function if collection doesn't have one)
collection = client.get_collection("my_collection")

# Get collection with specific embedding function
ef = DefaultEmbeddingFunction(model_name='all-MiniLM-L6-v2')
collection = client.get_collection("my_collection", embedding_function=ef)

# Get collection without embedding function
collection = client.get_collection("my_collection", embedding_function=None)

# Check if collection exists
if client.has_collection("my_collection"):
    collection = client.get_collection("my_collection")
```

### 3.3 Listing Collections

```python
# List all collections
collections = client.list_collections()
for coll in collections:
    print(f"Collection: {coll.name}, Dimension: {coll.dimension}")

# Count collections in database
collection_count = client.count_collection()
print(f"Database has {collection_count} collections")
```

### 3.4 Deleting a Collection

```python
# Delete a collection
client.delete_collection("my_collection")
```

### 3.5 Collection Properties

Each `Collection` object has the following properties:

*   `name` (str): Collection name
*   `id` (str, optional): Collection unique identifier
*   `dimension` (int, optional): Vector dimension
*   `embedding_function` (EmbeddingFunction, optional): Embedding function associated with this collection
*   `distance` (str): Distance metric used by the index (e.g., 'l2', 'cosine', 'inner_product')
*   `metadata` (dict): Collection metadata

---

## 4. DML Operations

DML (Data Manipulation Language) operations allow you to insert, update, and delete data in collections.

### 4.1 Add Data

**IMPORTANT:** All parameter names are **PLURAL** - `ids`, `documents`, `metadatas`, `embeddings`

```python
# Add single item with embeddings (embedding_function not used)
collection.add(
    ids="item1",
    embeddings=[0.1, 0.2, 0.3],
    documents="This is a document",
    metadatas={"category": "AI", "score": 95}
)

# Add multiple items with embeddings (embedding_function not used)
collection.add(
    ids=["item1", "item2", "item3"],
    embeddings=[
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9]
    ],
    documents=[
        "Document 1",
        "Document 2",
        "Document 3"
    ],
    metadatas=[
        {"category": "AI", "score": 95},
        {"category": "ML", "score": 88},
        {"category": "DL", "score": 92}
    ]
)

# Add with only embeddings (no documents)
collection.add(
    ids=["vec1", "vec2"],
    embeddings=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
)

# Add with only documents - embeddings auto-generated by embedding_function
# Requires: collection must have embedding_function set
collection.add(
    ids=["doc1", "doc2"],
    documents=["Text document 1", "Text document 2"],
    metadatas=[{"tag": "A"}, {"tag": "B"}]
)
# The collection's embedding_function will automatically convert documents to embeddings
```

**Parameters:**

*   `ids` (str or List[str]): Single ID or list of IDs (required)
*   `embeddings` (List[float] or List[List[float]], optional): Single embedding or list of embeddings
*   `documents` (str or List[str], optional): Single document or list of documents
*   `metadatas` (dict or List[dict], optional): Single metadata dict or list of metadata dicts

### 4.2 Update Data

```python
# Update single item - metadata only (embedding_function not used)
collection.update(
    ids="item1",
    metadatas={"category": "AI", "score": 98}  # Update metadata only
)

# Update multiple items with embeddings (embedding_function not used)
collection.update(
    ids=["item1", "item2"],
    embeddings=[[0.9, 0.8, 0.7], [0.6, 0.5, 0.4]],  # Update embeddings
    documents=["Updated document 1", "Updated document 2"]  # Update documents
)

# Update with documents only - embeddings auto-generated by embedding_function
collection.update(
    ids="item1",
    documents="New document text",  # Embeddings will be auto-generated
    metadatas={"category": "AI"}
)
```

### 4.3 Upsert Data

```python
# Upsert single item with embeddings (embedding_function not used)
collection.upsert(
    ids="item1",
    embeddings=[0.1, 0.2, 0.3],
    documents="Document text",
    metadatas={"category": "AI", "score": 95}
)

# Upsert multiple items with embeddings (embedding_function not used)
collection.upsert(
    ids=["item1", "item2", "item3"],
    embeddings=[
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9]
    ],
    documents=["Doc 1", "Doc 2", "Doc 3"],
    metadatas=[
        {"category": "AI"},
        {"category": "ML"},
        {"category": "DL"}
    ]
)

# Upsert with documents only - embeddings auto-generated by embedding_function
collection.upsert(
    ids=["item1", "item2"],
    documents=["Document 1", "Document 2"],
    metadatas=[{"category": "AI"}, {"category": "ML"}]
)
```

### 4.4 Delete Data

```python
# Delete by IDs
collection.delete(ids=["item1", "item2", "item3"])

# Delete by single ID
collection.delete(ids="item1")

# Delete by metadata filter
collection.delete(where={"category": {"$eq": "AI"}})

# Delete by comparison operator
collection.delete(where={"score": {"$lt": 50}})

# Delete by document filter
collection.delete(where_document={"$contains": "obsolete"})

# Delete with combined filters
collection.delete(
    where={"category": {"$eq": "AI"}},
    where_document={"$contains": "deprecated"}
)
```

---

## 5. DQL Operations

DQL (Data Query Language) operations allow you to retrieve data from collections using various query methods.

### 5.1 Query (Vector Similarity Search)

```python
# Basic vector similarity query (embedding_function not used)
results = collection.query(
    query_embeddings=[1.0, 2.0, 3.0],
    n_results=3
)

# Iterate over results
for i in range(len(results["ids"][0])):
    print(f"ID: {results['ids'][0][i]}, Distance: {results['distances'][0][i]}")
    if results.get("documents"):
        print(f"Document: {results['documents'][0][i]}")
    if results.get("metadatas"):
        print(f"Metadata: {results['metadatas'][0][i]}")

# Query by texts - embeddings auto-generated by embedding_function
results = collection.query(
    query_texts=["my query text"],
    n_results=10
)

# Query by multiple texts (batch query)
results = collection.query(
    query_texts=["query text 1", "query text 2"],
    n_results=5
)

# Query with metadata filter (using query_texts)
results = collection.query(
    query_texts=["AI research"],
    where={"category": {"$eq": "AI"}},
    n_results=5
)

# Query with comparison operator (using query_texts)
results = collection.query(
    query_texts=["machine learning"],
    where={"score": {"$gte": 90}},
    n_results=5
)

# Query with document filter (using query_texts)
results = collection.query(
    query_texts=["neural networks"],
    where_document={"$contains": "machine learning"},
    n_results=5
)

# Query with combined filters (using query_texts)
results = collection.query(
    query_texts=["AI research"],
    where={"category": {"$eq": "AI"}, "score": {"$gte": 90}},
    where_document={"$contains": "machine"},
    n_results=5
)
```

**Returns:** Dict with keys (chromadb-compatible format):

*   `ids`: `List[List[str]]` - List of ID lists, one list per query
*   `documents`: `Optional[List[List[str]]]` - List of document lists, one list per query (if included)
*   `metadatas`: `Optional[List[List[Dict]]]` - List of metadata lists, one list per query (if included)
*   `embeddings`: `Optional[List[List[List[float]]]]` - List of embedding lists, one list per query (if included)
*   `distances`: `Optional[List[List[float]]]` - List of distance lists, one list per query

### 5.2 Get (Retrieve by IDs or Filters)

```python
# Get by single ID
results = collection.get(ids="123")

# Get by multiple IDs
results = collection.get(ids=["1", "2", "3"])

# Get by metadata filter (simplified equality - both forms are supported)
results = collection.get(
    where={"category": "AI"},
    limit=10
)

# Get by comparison operator
results = collection.get(
    where={"score": {"$gte": 90}},
    limit=10
)

# Get by $in operator
results = collection.get(
    where={"tag": {"$in": ["ml", "python"]}},
    limit=10
)

# Get by logical operators ($or)
results = collection.get(
    where={
        "$or": [
            {"category": "AI"},
            {"tag": "python"}
        ]
    },
    limit=10
)

# Get by document content filter
results = collection.get(
    where_document={"$contains": "machine learning"},
    limit=10
)

# Get with combined filters
results = collection.get(
    where={"category": {"$eq": "AI"}},
    where_document={"$contains": "machine"},
    limit=10
)

# Get with pagination
results = collection.get(limit=2, offset=1)

# Get with specific fields
results = collection.get(
    ids=["1", "2"],
    include=["documents", "metadatas", "embeddings"]
)

# Get all data (up to limit)
results = collection.get(limit=100)
```

**Returns:** Dict with keys (chromadb-compatible format):

*   `ids`: `List[str]` - List of IDs
*   `documents`: `Optional[List[str]]` - List of documents (if included)
*   `metadatas`: `Optional[List[Dict]]` - List of metadata dictionaries (if included)
*   `embeddings`: `Optional[List[List[float]]]` - List of embeddings (if included)

### 5.3 Hybrid Search

`collection.hybrid_search()` runs full-text/scalar queries and vector KNN search in parallel, then fuses the results (RRF is supported).

```python
# Full-text + vector with rank fusion (dict style)
results = collection.hybrid_search(
    query={
        "where_document": {"$contains": "machine learning"},
        "where": {"category": {"$eq": "science"}},
        "boost": 0.5,
    },
    knn={
        "query_texts": ["AI research"],  # auto-embedded via collection.embedding_function
        "where": {"year": {"$gte": 2020}},
        "n_results": 10,  # k per vector route
        "boost": 0.8,
    },
    rank={"rrf": {"rank_window_size": 60, "rank_constant": 60}},
    n_results=5,
    include=["documents", "metadatas", "embeddings"],
)

# Vector-only search using explicit embeddings (dimension is validated)
results = collection.hybrid_search(
    knn={"query_embeddings": [[0.1, 0.2, 0.3]], "n_results": 8},
    n_results=5,
    include=["documents", "metadatas"],
)

# Pass a HybridSearch builder (takes precedence over other args)
from pyseekdb import (
    HybridSearch,
    DOCUMENT,
    TEXT,
    EMBEDDINGS,
    K,
    DOCUMENTS,
    METADATAS,
)

search = (
    HybridSearch()
    .query(DOCUMENT.contains("machine learning"), K("category") == "AI", boost=0.6)
    .knn(TEXT("AI research"), K("year") >= 2020, n_results=10, boost=0.8)
    .limit(5)
    .select(DOCUMENTS, METADATAS, EMBEDDINGS)
    .rank({"rrf": {}})
)
results = collection.hybrid_search(search)
```

### 5.4 Filter Operators

#### Metadata Filters (`where` parameter)

*   `$eq` (or direct equality) / `$ne` / `$gt` / `$gte` / `$lt` / `$lte`
*   `$in` / `$nin` for membership checks
*   `$or` / `$and` for logical composition
*   `$not` for negation
*   `#id` to filter by primary key (e.g., `{"#id": {"$in": ["id1", "id2"]}}`)

#### Document Filters (`where_document` parameter)

*   `$contains`: full-text match
*   `$not_contains`: exclude matches
*   `$or` / `$and` combining multiple `$contains` clauses

### 5.5 Collection Information Methods

```python
# Get item count
count = collection.count()
print(f"Collection has {count} items")

# Preview first few items in collection
preview = collection.peek(limit=5)
for i in range(len(preview["ids"])):
    print(f"ID: {preview['ids'][i]}, Document: {preview['documents'][i]}")
    print(f"Metadata: {preview['metadatas'][i]}, Embedding: {preview['embeddings'][i]}")

# Count collections in database
collection_count = client.count_collection()
print(f"Database has {collection_count} collections")
```

---

## 6. Embedding Functions

Embedding functions convert text documents into vector embeddings for similarity search. pyseekdb supports both built-in and custom embedding functions.

### 6.1 Default Embedding Function

The `DefaultEmbeddingFunction` uses all-MiniLM-L6-v2' and is the default embedding function if none is specified.

```python
from pyseekdb import DefaultEmbeddingFunction

# Use default model (all-MiniLM-L6-v2, 384 dimensions)
ef = DefaultEmbeddingFunction()

# Use custom model
ef = DefaultEmbeddingFunction(model_name='all-MiniLM-L6-v2')

# Get embedding dimension
print(f"Dimension: {ef.dimension}")  # 384

# Generate embeddings
embeddings = ef(["Hello world", "How are you?"])
print(f"Generated {len(embeddings)} embeddings, each with {len(embeddings[0])} dimensions")
```

### 6.2 Creating Custom Embedding Functions

You can create custom embedding functions by implementing the `EmbeddingFunction` protocol. The function must:

1.  Implement `__call__` method that accepts `Documents` (str or List[str]) and returns `Embeddings` (List[List[float]])
2.  Optionally implement a `dimension` property to return the vector dimension

**Example: Sentence-Transformer Custom Embedding Function**

```python
from typing import List, Union
from pyseekdb import EmbeddingFunction

Documents = Union[str, List[str]]
Embeddings = List[List[float]]

class SentenceTransformerCustomEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    A custom embedding function using sentence-transformers with a specific model.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dimension = None

    def _ensure_model_loaded(self):
        """Lazy load the embedding model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                test_embedding = self._model.encode(["test"], convert_to_numpy=True)
                self._dimension = len(test_embedding[0])
            except ImportError:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Please install it with: pip install sentence-transformers"
                )

    @property
    def dimension(self) -> int:
        """Get the dimension of embeddings produced by this function"""
        self._ensure_model_loaded()
        return self._dimension

    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for the given documents."""
        self._ensure_model_loaded()

        # Handle single string input
        if isinstance(input, str):
            input = [input]

        # Handle empty input
        if not input:
            return []

        # Generate embeddings
        embeddings = self._model.encode(
            input,
            convert_to_numpy=True,
            show_progress_bar=False
        )

        # Convert numpy arrays to lists
        return [embedding.tolist() for embedding in embeddings]
```

### 6.3 Embedding Function Requirements

When creating a custom embedding function, ensure:

1.  **Implement `__call__` method:**
    *   Accepts: `str` or `List[str]` (single document or list of documents)
    *   Returns: `List[List[float]]` (list of embeddings)
    *   Each vector must have the same dimension
2.  **Implement `dimension` property (recommended):**
    *   Returns: `int` (the dimension of embeddings produced by this function)
3.  **Handle edge cases:**
    *   Single string input should be converted to list
    *   Empty input should return empty list
    *   All embeddings in the output must have the same dimension

---

## 7. RAG Demo

pyseekdb provides a complete RAG (Retrieval-Augmented Generation) demo application that demonstrates how to build a hybrid search knowledge base. The demo includes:

*   **Document Import**: Import Markdown files or directory into seekdb
*   **Vector Search**: Semantic search over imported documents
*   **RAG Interface**: Interactive Streamlit web interface for querying

The demo supports three embedding modes:

*   **`default`**: Uses pyseekdb's built-in `DefaultEmbeddingFunction` (ONNX-based, 384 dimensions). No API key required, automatically downloads models on first use.
*   **`local`**: Uses sentence-transformers models (e.g., all-mpnet-base-v2, 768 dimensions). Requires installing sentence-transformers library.
*   **`api`**: Uses OpenAI-compatible Embedding API services (e.g., DashScope, OpenAI). Requires API key configuration.

For detailed instructions, see [demo/rag/README.md](https://github.com/oceanbase/pyseekdb/blob/develop/demo/rag/README.md).

---

## 8. Testing

```shell
# Run all tests (unit + integration)
python3 -m pytest -v

# Run tests with log output
python3 -m pytest -v -s

# Run unit tests only
python3 -m pytest tests/unit_tests/ -v

# Run integration tests only
python3 -m pytest tests/integration_tests/ -v

# Run integration tests for specific mode
python3 -m pytest tests/integration_tests/ -v -k "embedded"   # embedded mode
python3 -m pytest tests/integration_tests/ -v -k "server"     # server mode (requires seekdb server)
python3 -m pytest tests/integration_tests/ -v -k "oceanbase"  # oceanbase mode (requires OceanBase)

# Run specific test file
python3 -m pytest tests/integration_tests/test_collection_query.py -v

# Run specific test function
python3 -m pytest tests/integration_tests/test_collection_query.py::TestCollectionQuery::test_collection_query -v
```

---

## Executive Assistant Integration Notes

- **Persistence path:** `data/users/{thread_id}/kb/` (directory). SeekDB writes `seekdb.db`, `seekdb.db-wal`, and `seekdb.db-shm` inside this directory.
- **Embedded mode requirement:** pyseekdb embedded uses `pylibseekdb`, which is **Linux-only**. On macOS/Windows you must run a SeekDB server and use remote mode.
- **Embedding defaults:** Executive Assistant defaults to `SEEKDB_EMBEDDING_MODE=default` to enable local embeddings.
- **Full-text parser:** configurable via `SEEKDB_FULLTEXT_PARSER` (default `space`).
- **Distance metric:** configurable via `SEEKDB_DISTANCE_METRIC` (default `cosine`).

## Executive Assistant Implementation Details (2026-01-16)
- Removed DuckDB KB storage/tools and replaced with SeekDB-backed KB tools (same tool signatures).
- Added per-thread SeekDB storage helpers in `src/executive_assistant/storage/seekdb_storage.py`.
- KB persistence now uses `data/users/{thread_id}/kb/` (directory) for embedded SeekDB.
- `SEEKDB_EMBEDDING_MODE` default set to `default` (local embeddings enabled).
- Management `/kb` commands now call SeekDB-backed KB tools.
- Tests updated to skip KB tool tests when SeekDB embedded is unavailable.

**Test run:** `uv run pytest tests/test_kb.py` → 3 skipped (SeekDB embedded not available on this macOS host).

---

## Sources

- [pyseekdb GitHub](https://github.com/oceanbase/pyseekdb)
- [SeekDB Release Announcement](https://www.marktechpost.com/2025/11/26/oceanbase-releases-seekdb-an-open-source-ai-native-hybrid-search-database)
- [pyseekdb API Documentation](https://github.com/oceanbase/pyseekdb/blob/develop/README.md)
- [OceanBase AI Blog - SeekDB Tutorials](https://open.oceanbase.com/blog)
