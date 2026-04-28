# HybridDB: SQLite + FTS5 + ChromaDB with Self-Healing Journal

> A reusable hybrid-search database engine for Python applications.
> TEXT columns get keyword search. LONGTEXT columns get keyword + semantic search.
> All backed by an operation journal that guarantees consistency across SQLite, FTS5, and ChromaDB.

---

## Table of Contents

1. [Why HybridDB Exists](#1-why-hybriddb-exists)
2. [Architecture](#2-architecture)
3. [Column Types & Search Behavior](#3-column-types--search-behavior)
4. [ChromaDB Metadata Strategy](#4-chromadb-metadata-strategy)
5. [The Journal: Self-Healing Consistency](#5-the-journal-self-healing-consistency)
6. [Schema Management](#6-schema-management)
7. [Search API](#7-search-api)
8. [Fitness Check: MemoryStore](#8-fitness-check-memorystore)
9. [Fitness Check: MessageStore](#9-fitness-check-conversationstore)
10. [File Layout](#10-file-layout)
11. [Public API Reference](#11-public-api-reference)
12. [In Scope / Out of Scope](#12-in-scope--out-of-scope)
13. [Design Decisions & Rationale](#13-design-decisions--rationale)
14. [Known Risks & Mitigations](#14-known-risks--mitigations)
15. [Benchmark Context](#15-benchmark-context)

---

## 1. Why HybridDB Exists

### The problem

Applications that need both keyword and semantic search currently face three bad options:

1. **ChromaDB alone** — no keyword search, no SQL queries, no complex filtering
2. **SQLite + FTS5 alone** — no semantic/vector search, can't find "morning meetings" when the text says "9am standup"
3. **SQLite + FTS5 + ChromaDB (custom wiring)** — two databases to keep in sync, ghosts on crash, schema changes break things, every project reinvents this

The third option is what every serious project ends up building. HybridDB is that wiring, done once and done right.

### Why not just use ChromaDB?

ChromaDB is a vector database, not a general-purpose database. It can't:
- Run SQL queries (`SELECT * FROM contacts WHERE clv > 2000 AND status = 'active'`)
- Do keyword search (FTS5 BM25 ranking)
- Handle complex schemas (foreign keys, indexes, constraints)
- Survive without an embedding model (it's vector-only)

### Why not just use SQLite + sqlite-vec?

sqlite-vec (v0.1.6) is brute-force only — no HNSW index. Our benchmark showed it's **78x slower** than ChromaDB at 100k rows for vector search, and **105x slower** for hybrid search. At 1M rows it's unusable for interactive applications. See [Section 15](#15-benchmark-context) for details.

### The hybrid answer

HybridDB combines three systems, each doing what it's best at:

| System | Role | Why |
|--------|------|-----|
| **SQLite** | Source of truth, CRUD queries, structured filtering | Battle-tested, single-file, ACID transactions |
| **FTS5** | Keyword/full-text search with BM25 scoring | Built into SQLite, content-external, auto-synced via triggers |
| **ChromaDB** | Semantic/vector search with HNSW indexing | Only option with ANN for fast O(log n) search at scale |

The challenge is keeping them all consistent. That's what the journal solves.

---

## 2. Architecture

```
┌──────────────────────────────────────────────┐
│              HybridDB (Python)               │
│                                              │
│  ┌─────────────┐  ┌───────────────────────┐ │
│  │  Schema      │  │  Search Engine        │ │
│  │  Engine      │  │  - FTS5 (BM25)        │ │
│  │  - TEXT      │  │  - ChromaDB (HNSW)    │ │
│  │  - LONGTEXT  │  │  - Hybrid RRF fusion  │ │
│  │  - INTEGER   │  │  - Recency scoring    │ │
│  │  - REAL      │  │  - Metadata filtering │ │
│  │  - BOOLEAN   │  │                       │ │
│  │  - JSON      │  │                       │ │
│  └──────┬───────┘  └───────────┬───────────┘ │
│         │                      │             │
│  ┌──────┴──────────────────────┴───────────┐ │
│  │          Operation Journal              │ │
│  │  (SQLite table: _journal)               │ │
│  │  - Queues all ChromaDB mutations        │ │
│  │  - Processed after SQLite commit        │ │
│  │  - Self-heals on crash                  │ │
│  └──────────────────────────────────────────┘ │
│         │                      │             │
└─────────┼──────────────────────┼─────────────┘
          │                      │
    ┌─────▼──────┐        ┌─────▼──────┐
    │   SQLite    │        │  ChromaDB  │
    │  + FTS5     │        │  (HNSW)    │
    │  (WAL)      │        │            │
    │             │        │            │
    │  Source of   │        │  Derived   │
    │  truth       │        │  index     │
    └─────────────┘        └────────────┘
```

### Key principle

**SQLite is the single source of truth. ChromaDB is a derived index.**

If ChromaDB is wiped, it can be fully reconstructed from SQLite. If SQLite is corrupted, nothing can save you. The journal ensures ChromaDB eventually matches SQLite, even after crashes.

---

## 3. Column Types & Search Behavior

### Type hierarchy

| HybridDB Type | SQLite Storage | FTS5 Keyword | ChromaDB Vector | ChromaDB Metadata | Use For |
|---------------|---------------|---------------|-----------------|-------------------|---------|
| `TEXT` | `TEXT` | ✅ Yes | ❌ No | ✅ Yes | Names, emails, phone, status |
| `LONGTEXT` | `TEXT` | ✅ Yes | ✅ Yes | ❌ No (it IS the document) | Notes, descriptions, content |
| `INTEGER` | `INTEGER` | ❌ No | ❌ No | ✅ Yes | Counts, ages, priorities |
| `REAL` | `REAL` | ❌ No | ❌ No | ✅ Yes | Prices, scores, weights |
| `BOOLEAN` | `INTEGER` (0/1) | ❌ No | ❌ No | ✅ Yes | Active flags, toggles |
| `JSON` | `TEXT` | ❌ No | ❌ No | ❌ No | Structured blobs, metadata |

### How TEXT vs LONGTEXT was chosen (design rationale)

We considered three approaches for telling HybridDB which columns get semantic search:

1. **`search=hybrid/keyword/semantic` flag** — Descriptive but adds cognitive load. What does `search=semantic` mean? Is keyword absent? Three modes to explain.
2. **Smart detection** (LONGTEXT for `*notes*`, `*description*`) — Magic heuristics break in surprising ways. A column named `bio` gets LONGTEXT but `biography` doesn't?
3. **Type-based: `TEXT` vs `LONGTEXT`** — The column type IS the search mode. Zero magic, zero config. MySQL uses TEXT/MEDIUMTEXT/LONGTEXT for size differentiation, so the concept is familiar.

We chose option 3. The `search=` flag was rejected because:
- Three modes (`hybrid`/`keyword`/`semantic`) is more than needed — `semantic`-only (vector without keyword) has no real use case
- `search=hybrid` can be misread as "only hybrid search, no keyword?" 
- A type is harder to forget than a flag — you always specify a type, you might forget a flag

`LONGTEXT` was chosen over alternatives like `TEXT search=hybrid` because it's a **single concept** — "this field is long, free-form text" — and the search behavior follows naturally from that.

### FTS5 behavior per type

Each `TEXT` and `LONGTEXT` column gets its own FTS5 virtual table:

```sql
-- For a contacts table with: first_name TEXT, company LONGTEXT, notes LONGTEXT
CREATE VIRTUAL TABLE contacts_fts_first_name USING fts5(
    first_name, content='contacts', content_rowid='id'
);
CREATE VIRTUAL TABLE contacts_fts_company USING fts5(
    company, content='contacts', content_rowid='id'
);
CREATE VIRTUAL TABLE contacts_fts_notes USING fts5(
    notes, content='contacts', content_rowid='id'
);
```

Each FTS5 table has DELETE/INSERT/UPDATE triggers that auto-sync from the main table (standard content-external FTS5 pattern).

### ChromaDB behavior per LONGTEXT column

Each `LONGTEXT` column gets its own ChromaDB collection:

```python
# Collection naming: {table}_{column}
collections = {
    "contacts_company": chroma.get_or_create_collection("contacts_company"),
    "contacts_notes":   chroma.get_or_create_collection("contacts_notes"),
}
```

Each row becomes one document in the collection:

```python
collection.upsert(
    ids=["42"],                           # SQLite row ID as string
    embeddings=[[0.1, 0.2, ...]],          # 384-dim embedding from sentence-transformers
    documents=["Acme Corp"],               # the LONGTEXT value
    metadatas=[{...}],                     # see Section 4
)
```

### Why separate FTS5 tables and ChromaDB collections per column

Alternative: one FTS5 table and one ChromaDB collection per table, containing all columns.

| Approach | FTS5 scoring | ChromaDB search | Implementation |
|----------|-------------|-----------------|---------------|
| Per-column | BM25 per column — precise | Top-k per column — clean results | More tables, but each is simple |
| Per-table | BM25 blended — mixed quality | One embedding per row — loses column-level precision | Fewer tables, but scoring is muddy |

Per-column is strictly better because:
- **FTS5 BM25**: A match in `notes` should score differently than a match in `company`. Per-column FTS5 gives independent BM25 scores that can be weighted in fusion.
- **ChromaDB**: Embedding `"Acme Corp"` (company) produces a different vector than `"VIP client, key decision maker"` (notes). Searching the `notes` collection for "key decision maker" finds it directly. Searching a combined doc requires the company text to not dilute the notes embedding.
- **Where filtering**: Per-column collections allow metadata filtering scoped to that column's context.

---

## 4. ChromaDB Metadata Strategy

### Rule: All scalar columns become metadata in every LONGTEXT collection

Non-LONGTEXT, non-JSON columns are automatically added as ChromaDB metadata:

| Column Type | In Metadata? | Why |
|-------------|-------------|-----|
| `TEXT` | ✅ Yes | Enables exact-match and `$ne` filtering (e.g., `where={"status": "active"}`) |
| `INTEGER` | ✅ Yes | Enables numeric range filtering (e.g., `where={"clv": {"$gt": 2000}}`) |
| `REAL` | ✅ Yes | Enables numeric range filtering (e.g., `where={"price": {"$lte": 100}}`) |
| `BOOLEAN` | ✅ Yes | Enables boolean filtering (e.g., `where={"is_active": True}`) |
| `LONGTEXT` | ❌ No | This IS the document being embedded — not metadata |
| `JSON` | ❌ No | Not a scalar value, can't be stored in ChromaDB metadata |

### Why this rule (design rationale)

We evaluated four options:

| Option | Config | Text filter | Numeric filter | Boolean filter | Storage cost |
|--------|--------|-------------|----------------|-----------------|-------------|
| A: TEXT only | Zero | ✅ | ❌ (post-filter) | ❌ (post-filter) | Small |
| B: User specifies `meta=true` | Required | On marked cols | On marked cols | On marked cols | User-controlled |
| C: TEXT + INTEGER + REAL + BOOLEAN | Zero | ✅ | ✅ | ✅ | Moderate |
| D: User specifies per column | Required | On marked cols | On marked cols | On marked cols | User-controlled |

**Option A** fails the CLV > 2000 test. Numeric range queries require Python post-filtering, which means fetching extra results and hoping enough match. ChromaDB's native `where` filter is much more efficient because it applies during the ANN search phase.

**Option B** requires configuration. If a user forgets to mark `clv` as metadata, they can't filter by it later without a full backfill.

**Option C** (chosen) gives you everything with zero config. The cost is metadata duplication across k ChromaDB collections:

```
Example: contacts table with 2 LONGTEXT, 5 TEXT, 3 REAL, 2 BOOLEAN columns
Per document: 10 metadata key-value pairs (5+3+2)
Per table: 2 collections × 10 keys = 20 metadata entries per row (excluding LONGTEXT)
For 10,000 rows: 200,000 tiny key-value pairs — negligible
```

### NULL handling

ChromaDB metadata does not support `None`/`null` values. When a column is NULL in SQLite, the key is **omitted** from metadata:

```python
# Row: {first_name: "Alice", clv: NULL, status: "active"}
metadatas=[{"first_name": "Alice", "status": "active"}]  # "clv" key absent

# Filtering:
where={"clv": {"$gt": 2000}}  # rows without "clv" are excluded (not an error)
```

This is ChromaDB's built-in behavior — missing keys simply don't match.

### ChromaDB where filter operators (reference)

Supported by ChromaDB natively:

| Operator | Works on | Example |
|----------|---------|---------|
| Exact match | string, number, bool | `{"status": "active"}` |
| `$ne` | string, number, bool | `{"status": {"$ne": "churned"}}` |
| `$gt`, `$gte` | number | `{"clv": {"$gt": 2000}}` |
| `$lt`, `$lte` | number | `{"price": {"$lte": 100}}` |
| `$and` | any | `{"$and": [{"status": "active"}, {"clv": {"$gt": 2000}}]}` |
| `$or` | any | `{"$or": [{"status": "lead"}, {"status": "prospect"}]}` |

### Metadata duplication problem

Each LONGTEXT collection stores a **full copy** of all scalar metadata. There is no way to share metadata references across ChromaDB collections — each collection is fully isolated.

This means:
- Update row 42's `status` → must update metadata in `contacts_company` AND `contacts_notes`
- Schema change adding `region` → must add `region` key to metadata in every collection

Cost per mutation: O(k) ChromaDB update calls, where k = number of LONGTEXT columns.

This is the primary motivation for the journal (Section 5).

---

## 5. The Journal: Self-Healing Consistency

### The fundamental problem

SQLite + FTS5 are in the same transaction — FTS5 triggers fire within the SQLite commit, so they're always consistent. ChromaDB is external — it **cannot** participate in SQLite transactions. Any multi-step operation can partially fail:

```
INSERT into SQLite ✅ → FTS5 trigger fires ✅ → ChromaDB upsert ❌ (crash)
Result: SQLite + FTS5 are consistent, ChromaDB is stale
```

Without a journal, you need a full `reconcile()` to fix this — scanning every row and comparing SQLite vs ChromaDB. O(n × k) every time, even for a single failed write.

### The journal design

The `_journal` table lives in the same SQLite database as the application data. It acts as a durable queue of pending ChromaDB operations:

```sql
CREATE TABLE IF NOT EXISTS _journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_table TEXT NOT NULL,
    row_id INTEGER,                -- NULL for table-level ops (add_column, etc.)
    column_name TEXT,              -- which LONGTEXT column (NULL for table-level)
    op TEXT NOT NULL,             -- "add", "update", "delete", "meta_update",
                                  -- "create_collection", "drop_collection", "reindex"
    data TEXT,                    -- the LONGTEXT value to embed (NULL for deletes/meta_updates)
    metadata TEXT,                -- JSON metadata to attach (NULL for deletes)
    status TEXT DEFAULT 'pending', -- "pending", "done", "failed"
    error TEXT,                   -- error message if failed
    created_at TEXT NOT NULL,
    retries INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_journal_pending ON _journal(status, app_table);
```

### Operation flow

Every write operation follows this pattern:

```
1. SQLite write (transaction) ──→ includes FTS5 trigger (same txn)
2. Journal entry (same txn)   ──→ queues ChromaDB work durably
3. SQLite commit              ──→ now durable
4. Process journal (after)    ──→ best-effort ChromaDB sync
                                  if crash here, journal entries survive
                                  and are processed on next operation
```

### INSERT

```python
def insert(self, table: str, data: dict) -> int:
    with self._connect() as conn:
        cur = conn.cursor()
        
        # 1. SQLite INSERT (FTS5 triggers fire automatically)
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        cur.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", 
                    list(data.values()))
        row_id = cur.lastrowid
        
        # 2. Re-read full row (for metadata computation)
        row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())
        
        # 3. Journal ChromaDB work (in same transaction)
        metadata = self._row_to_metadata(table, row)
        for col in self._get_longtext_columns(table):
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                "VALUES (?, ?, ?, 'add', ?, ?, ?)",
                (table, row_id, col, row.get(col, ""), json.dumps(metadata), now_iso())
            )
        
        conn.commit()
    
    # 4. Process journal (best-effort, after commit)
    self._process_journal()
    return row_id
```

### UPDATE

```python
def update(self, table: str, row_id: int, data: dict) -> bool:
    with self._connect() as conn:
        cur = conn.cursor()
        
        # 1. SQLite UPDATE (FTS5 triggers fire automatically)
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        cur.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", 
                    list(data.values()) + [row_id])
        
        if cur.rowcount == 0:
            return False
        
        # 2. Re-read full row (for metadata computation)
        row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())
        
        # 3. Journal metadata update (ALL collections get new metadata)
        metadata = self._row_to_metadata(table, row)
        for col in self._get_longtext_columns(table):
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                "VALUES (?, ?, ?, 'update', ?, ?, ?)",
                (table, row_id, col, row.get(col, ""), json.dumps(metadata), now_iso())
            )
        
        conn.commit()
    
    # 4. Process journal
    self._process_journal()
    return True
```

### DELETE

```python
def delete(self, table: str, row_id: int) -> bool:
    with self._connect() as conn:
        cur = conn.cursor()
        
        # 1. SQLite DELETE (FTS5 triggers fire automatically)
        cur.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        if cur.rowcount == 0:
            return False
        
        # 2. Journal ChromaDB deletes (no data/metadata needed)
        for col in self._get_longtext_columns(table):
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, column_name, op, created_at) "
                "VALUES (?, ?, ?, 'delete', ?)",
                (table, row_id, col, now_iso())
            )
        
        conn.commit()
    
    # 3. Process journal
    self._process_journal()
    return True
```

### Batch operations

For bulk inserts/updates, journal entries are created per-row but processed in batch:

```python
def insert_batch(self, table: str, rows: list[dict]) -> list[int]:
    with self._connect() as conn:
        cur = conn.cursor()
        ids = []
        for data in rows:
            cur.execute(f"INSERT INTO {table} ...", ...)
            row_id = cur.lastrowid
            ids.append(row_id)
            
            # Journal each row
            for col in self._get_longtext_columns(table):
                cur.execute("INSERT INTO _journal (...) VALUES (...)", ...)
        
        conn.commit()
    
    # Process all pending at once (batched ChromaDB upserts)
    self._process_journal()
    return ids
```

### The _process_journal method

```python
def _process_journal(self, batch_limit: int = 5000):
    """Process pending journal entries. Called after every mutation + before search."""
    
    # Cap check: if journal is overflowing, disable hybrid and warn
    pending_count = self._journal_count()
    if pending_count > 50_000:
        logger.warning("journal.overflow", {"pending": pending_count})
        self._disable_hybrid_temporarily()
        return
    
    with self._connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM _journal WHERE status = 'pending' ORDER BY id LIMIT ?",
            (batch_limit,),
        )
        entries = [dict(r) for r in cur.fetchall()]
    
    if not entries:
        return
    
    # Group by operation type for batch processing
    adds = [e for e in entries if e["op"] == "add"]
    updates = [e for e in entries if e["op"] == "update"]
    deletes = [e for e in entries if e["op"] == "delete"]
    
    # Process in batches per collection
    CHROMA_BATCH = 5000
    
    # Process adds: batch upsert
    by_collection = defaultdict(lambda: {"ids": [], "embeddings": [], "documents": [], "metadatas": []})
    for entry in adds:
        collection_name = f"{entry['app_table']}_{entry['column_name']}"
        collection = self._get_collection(collection_name)
        doc = entry["data"] or ""
        embedding = self._get_embedding(doc)
        metadata = json.loads(entry["metadata"]) if entry["metadata"] else {}
        
        by_collection[collection_name]["ids"].append(str(entry["row_id"]))
        by_collection[collection_name]["embeddings"].append(embedding)
        by_collection[collection_name]["documents"].append(doc)
        by_collection[collection_name]["metadatas"].append(metadata)
    
    for coll_name, batch in by_collection.items():
        collection = self._get_collection(coll_name)
        for i in range(0, len(batch["ids"]), CHROMA_BATCH):
            collection.upsert(
                ids=batch["ids"][i:i+CHROMA_BATCH],
                embeddings=batch["embeddings"][i:i+CHROMA_BATCH],
                documents=batch["documents"][i:i+CHROMA_BATCH],
                metadatas=batch["metadatas"][i:i+CHROMA_BATCH],
            )
    
    # Process deletes: batch delete
    by_collection_del = defaultdict(list)
    for entry in deletes:
        collection_name = f"{entry['app_table']}_{entry['column_name']}"
        by_collection_del[collection_name].append(str(entry["row_id"]))
    
    for coll_name, ids in by_collection_del.items():
        collection = self._get_collection(coll_name)
        for i in range(0, len(ids), CHROMA_BATCH):
            collection.delete(ids=ids[i:i+CHROMA_BATCH])
    
    # Process updates: combine metadata + embedding update
    for entry in updates:
        collection_name = f"{entry['app_table']}_{entry['column_name']}"
        collection = self._get_collection(collection_name)
        metadata = json.loads(entry["metadata"]) if entry["metadata"] else {}
        doc = entry["data"] or ""
        embedding = self._get_embedding(doc)
        
        collection.update(
            ids=[str(entry["row_id"])],
            embeddings=[embedding],
            documents=[doc],
            metadatas=[metadata],
        )
    
    # Mark entries as done (delete from journal)
    done_ids = [e["id"] for e in entries]
    with self._connect() as conn:
        placeholders = ",".join("?" * len(done_ids))
        conn.execute(f"DELETE FROM _journal WHERE id IN ({placeholders})", done_ids)
        conn.commit()
    
    # Retry failed entries
    failed = [e for e in entries if e["id"] not in done_ids]
    with self._connect() as conn:
        for entry in failed:
            conn.execute(
                "UPDATE _journal SET status = 'failed', error = ?, retries = retries + 1 WHERE id = ?",
                (str(e), entry["id"])
            )
        conn.commit()
```

### Search auto-processes journal

```python
def search(self, table, column, query, where=None, limit=10):
    # Auto-process pending entries before searching
    pending = self._journal_count(table)
    if pending > 0:
        self._process_journal()
    
    # Now ChromaDB is consistent with SQLite
    ...
```

### Recovery scenarios

| Scenario | SQLite state | FTS5 state | ChromaDB state | Journal | Recovery |
|----------|-------------|------------|----------------|---------|----------|
| Normal write | ✅ committed | ✅ synced (trigger) | ✅ synced (journal processed) | empty | None needed |
| Crash after SQLite commit, before journal process | ✅ committed | ✅ synced | ❌ stale | entries pending | Auto-recovered on next search |
| Crash during SQLite commit | ❌ rolled back | ❌ rolled back | ✅ no entry (journal in same txn) | empty | None needed — ACID |
| ChromaDB down for extended period | ✅ current | ✅ current | ❌ stale | entries piling up | Journal caps at 50k, temporarily disables hybrid |
| ChromaDB permanently corrupted | ✅ current | ✅ current | ❌ broken | entries piling up | Call `reconcile()` to rebuild ChromaDB from SQLite |

### Why this is better than reconcile-only (Option B)

| Aspect | B: Reconcile | D: Operation Journal |
|--------|-------------|---------------------|
| Recovery granularity | Full table scan every time | Only affected rows |
| Recovery cost | O(n × k) always | O(m) where m = pending entries |
| Insert crash recovery | Full scan to find missing rows | Journal entry tells exactly which rows |
| Update crash recovery | Can't detect metadata drift without comparing | Journal entry tells exactly which rows |
| Delete crash recovery | Can't detect ghosts without comparing | Journal entry tells exactly which rows |
| Open-source story | "Call reconcile() if things seem wrong" | "It self-heals on every operation" |
| Journal growth | N/A | Auto-pruned on success, capped at 50k |

---

## 6. Schema Management

### Supported operations

| Operation | SQLite | FTS5 | ChromaDB | Journal entries |
|-----------|--------|------|----------|-----------------|
| `create_table(table, columns)` | CREATE TABLE + indexes | CREATE VIRTUAL TABLE per TEXT/LONGTEXT + triggers | get_or_create_collection per LONGTEXT | None |
| `add_column(table, col, type)` | ALTER TABLE ADD COLUMN | If TEXT/LONGTEXT: add FTS5 table + triggers | If LONGTEXT: create collection | If LONGTEXT: `create_collection` entry |
| `drop_column(table, col)` | Rebuild table (SQLite limitation) | Rebuild FTS5 tables | If LONGTEXT: drop collection + remove from metadata of other collections | `drop_collection` + `meta_update` entries |
| `rename_column(table, old, new)` | ALTER TABLE RENAME COLUMN | Drop old FTS5, create new FTS5 with new name | Rename metadata key in all collections | `meta_update` entries per collection |
| `change_column_type(table, col, new_type)` | Rebuild table | Rebuild FTS5 | If TEXT→LONGTEXT: create collection + backfill embeddings; If LONGTEXT→TEXT: drop collection + add to metadata | `reindex` or `drop_collection` entries |

### SQLite's ALTER TABLE limitations

SQLite only supports `ADD COLUMN` and `RENAME COLUMN`. Everything else (drop column, change type) requires a table rebuild:

```python
def _rebuild_table(self, table, new_columns):
    """Rebuild table with new schema. SQLite limitation workaround."""
    old_table = f"_{table}_old"
    
    # 1. Rename current table
    cur.execute(f"ALTER TABLE {table} RENAME TO {old_table}")
    
    # 2. Create new table with updated schema
    cur.execute(f"CREATE TABLE {table} ({self._columns_to_sql(new_columns)})")
    
    # 3. Copy data (only columns that exist in both)
    shared_cols = [c.name for c in new_columns if c.name in old_column_names]
    col_list = ", ".join(shared_cols)
    cur.execute(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {old_table}")
    
    # 4. Drop old table
    cur.execute(f"DROP TABLE {old_table}")
    
    # 5. Recreate indexes
    for idx in self._indexes_for(table):
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx}")
    
    # 6. Rebuild all FTS5 tables
    self._rebuild_all_fts5(table)
    
    # 7. Journal ChromaDB work (lazy sync)
    for col in self._get_longtext_columns(table):
        cur.execute("INSERT INTO _journal (...) VALUES (...)", 
                    (table, None, col, "reindex", ...))
```

### Schema change + ChromaDB sync cost

Schema changes that affect ChromaDB (type changes, column renames) mark the table as needing a re-sync. The actual work happens on the next `_process_journal()` call:

| Change | ChromaDB work | Cost at 10k rows | Cost at 100k rows |
|--------|-------------|-----------------|------------------|
| Add column | Nothing (new rows get new metadata key automatically) | 0 | 0 |
| Rename column | Update metadata key in all documents, all collections | ~1s (batched) | ~10s (batched) |
| Drop column | Remove stale metadata key from all documents, all collections | ~1s | ~10s |
| TEXT → LONGTEXT | Create collection + embed all values + add to collection | ~5s | ~50s |
| LONGTEXT → TEXT | Drop collection + add column to metadata in all other collections | ~5s | ~50s |
| REAL → TEXT | Re-type metadata values (numeric → string) — warning: breaks numeric `where` | ~1s | ~10s |

These costs are incurred on the **first search** after the schema change, not on the `add_column`/`rename_column` call itself (which returns instantly).

### Schema version tracking

Store schema in SQLite's `_schema` table:

```sql
CREATE TABLE IF NOT EXISTS _schema (
    table_name TEXT PRIMARY KEY,
    columns_json TEXT NOT NULL,     -- JSON of ColumnDef[]
    version INTEGER DEFAULT 1,       -- incremented on schema changes
    is_dirty BOOLEAN DEFAULT 0,      -- needs ChromaDB re-sync
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 7. Search API

### search() — Single column search

```python
def search(
    self,
    table: str,
    column: str,
    query: str,
    mode: SearchMode = SearchMode.HYBRID,   # HYBRID, KEYWORD, SEMANTIC
    where: dict | None = None,               # ChromaDB metadata filter
    limit: int = 10,
    fts_weight: float = 0.5,                 # 0.0 = vector-only, 1.0 = keyword-only
    recency_weight: float = 0.0,            # 0.0 = ignore recency
    recency_column: str | None = None,      # column name for time-decay (e.g., "ts")
) -> list[dict]:
```

### search_all() — Multi-column search (RRF fusion)

```python
def search_all(
    self,
    table: str,
    query: str,
    where: dict | None = None,
    limit: int = 10,
    fts_weight: float = 0.5,
    recency_weight: float = 0.0,
    recency_column: str | None = None,
) -> list[dict]:
    """Search all LONGTEXT columns, fuse results with Reciprocal Rank Fusion."""
```

### FTS5 keyword search: BM25 scoring

FTS5 keyword search uses SQLite's built-in `bm25()` function, not rank-based scoring:

```sql
SELECT m.*, bm25(contacts_fts_notes) as fts_score
FROM contacts_fts_notes fts
JOIN contacts m ON m.id = fts.rowid
WHERE contacts_fts_notes MATCH ?
ORDER BY fts_score
LIMIT ?
```

BM25 produces negative scores (closer to 0 = better match). These are normalized for hybrid fusion:

```python
def _normalize_bm25(self, raw_scores: list[float]) -> list[float]:
    """Normalize BM25 scores to [0, 1] range using min-max."""
    if not raw_scores:
        return []
    min_s = min(raw_scores)
    max_s = max(raw_scores)
    if max_s == min_s:
        return [1.0] * len(raw_scores)
    # BM25 is negative, so invert: closer to 0 = higher normalized score
    return [(s - min_s) / (max_s - min_s) for s in raw_scores]
```

### Vector search: ChromaDB HNSW

```python
embedding = self._get_embedding(query)
results = collection.query(
    query_embeddings=[embedding],
    n_results=limit * 2,       # overfetch for post-filtering
    where=where,               # metadata filtering (if provided)
    include=["documents", "metadatas", "distances"]
)
# distances → cosine distance → normalized to similarity: 1 - distance
```

### Hybrid fusion: Reciprocal Rank Fusion (RRF)

```python
def _fuse_hybrid(
    self,
    fts_results: list[tuple[int, float]],    # (row_id, bm25_score)
    vec_results: list[tuple[int, float]],    # (row_id, cosine_similarity)
    fts_weight: float = 0.5,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion of keyword and vector results."""
    
    # RRF: score = 1/(k + rank) where k is a constant (typically 60)
    K = 60
    
    scores = {}
    
    for rank, (row_id, _) in enumerate(fts_results):
        rrf_score = fts_weight / (K + rank + 1)
        scores[row_id] = scores.get(row_id, 0) + rrf_score
    
    for rank, (row_id, _) in enumerate(vec_results):
        rrf_score = (1 - fts_weight) / (K + rank + 1)
        scores[row_id] = scores.get(row_id, 0) + rrf_score
    
    # Sort by fused score descending
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### Recency scoring

Optional time-decay scoring for tables with a timestamp column:

```python
def _compute_recency(self, row: dict, column: str) -> float:
    """Compute recency score: 1/(1 + days_ago/30)."""
    ts_str = row.get(column)
    if not ts_str:
        return 0.0
    ts = datetime.fromisoformat(ts_str)
    days_ago = max((datetime.now(UTC) - ts).days, 0)
    return 1.0 / (1 + days_ago / 30)

# In hybrid fusion:
# final_score = relevance * (1 - recency_weight) + recency * recency_weight
```

---

## 8. Fitness Check: MemoryStore

### MemoryStore schema mapped to HybridDB

```python
# Two tables: memories and insights
memories = {
    "id":              "TEXT PRIMARY KEY",     # hash-based ID
    "trigger":         "LONGTEXT",             # FTS5 + ChromaDB
    "action":          "LONGTEXT",             # FTS5 + ChromaDB
    "confidence":      "REAL",                 # metadata
    "domain":          "TEXT",                 # FTS5 + metadata
    "source":          "TEXT",                 # FTS5 + metadata
    "memory_type":     "TEXT",                 # FTS5 + metadata
    "importance":      "REAL",                 # metadata
    "observations":    "INTEGER",             # metadata
    "created_at":      "TEXT",                 # FTS5 + metadata
    "updated_at":      "TEXT",                 # FTS5 + metadata
    "is_superseded":   "BOOLEAN",              # metadata
    "structured_data": "LONGTEXT",             # FTS5 + ChromaDB
    "scope":           "TEXT",                 # FTS5 + metadata
    "project_id":      "TEXT",                 # FTS5 + metadata
    "access_count":    "INTEGER",              # metadata
    "last_accessed_at":"TEXT",                 # FTS5 + metadata
    "linked_to":       "JSON",                 # not indexed
}

insights = {
    "id":              "TEXT PRIMARY KEY",
    "summary":         "LONGTEXT",             # FTS5 + ChromaDB
    "domain":          "TEXT",                 # FTS5 + metadata
    "linked_memories": "JSON",                 # not indexed
    "confidence":      "REAL",                 # metadata
    "is_superseded":   "BOOLEAN",              # metadata
    "superseded_by":   "TEXT",                 # FTS5 + metadata
    "created_at":      "TEXT",                 # FTS5 + metadata
    "updated_at":      "TEXT",                 # FTS5 + metadata
}
```

### ChromaDB collections produced

```
memories_trigger         # embeddings of trigger values, metadata: {domain, source, memory_type, ...}
memories_action          # embeddings of action values, same metadata
memories_structured_data # embeddings of structured_data text, same metadata
insights_summary         # embeddings of summary values, metadata: {domain, confidence, ...}
```

### MemoryStore current ChromaDB → HybridDB mapping

| Current MemoryStore collection | HybridDB equivalent | Difference |
|-------------------------------|---------------------|-----------|
| `memories` (full doc: `"{trigger}: {action}"`) | **Not natively produced** | HybridDB embeds per-column, not combined. See gap below. |
| `memories_fields` (per-field: trigger, action, data with `memory_id` metadata) | `memories_trigger`, `memories_action`, `memories_structured_data` | HybridDB produces these automatically. Metadata includes all scalar columns (domain, source, memory_type, etc.) which covers the `memory_id` metadata's filtering purpose. |
| `insights` | `insights_summary` | Direct mapping. |

### Gap: Composite doc embedding

MemoryStore embeds `"{trigger}: {action}"` as a single document. This captures cross-field semantics — searching "morning meetings" matches when "morning" is in the trigger and "meetings" is in the action. HybridDB embeds per-column, so this cross-field match is weaker.

**Solution**: MemoryStore (the domain layer on top of HybridDB) can add a composite embedding manually:

```python
class MemoryStore:
    def __init__(self, hybrid_db):
        self.db = hybrid_db
        # Add a virtual composite collection
        self.composite_collection = self.db.chroma.get_or_create_collection("memories_composite")
    
    def insert(self, trigger, action, ...):
        row_id = self.db.insert("memories", {...})
        
        # Also embed the composite doc
        composite = f"{trigger}: {action}"
        self.composite_collection.upsert(
            ids=[str(row_id)],
            embeddings=[get_embedding(composite)],
            documents=[composite],
            metadatas=[self.db._row_to_metadata("memories", row)]
        )
    
    def search_hybrid(self, query, limit=10):
        # 1. FTS5: search all TEXT/LONGTEXT columns
        fts = self.db.search_all("memories", query, mode=KEYWORD, limit=limit*2)
        
        # 2. Per-column vector: trigger + action + structured_data
        vec_trigger = self.db.search("memories", "trigger", query, mode=SEMANTIC, limit=limit*2)
        vec_action = self.db.search("memories", "action", query, mode=SEMANTIC, limit=limit*2)
        
        # 3. Composite vector: "{trigger}: {action}"
        composite_results = self.composite_collection.query(
            query_embeddings=[get_embedding(query)],
            n_results=limit*2,
        )
        
        # 4. RRF fuse all sources with production weights:
        # 0.5 * fts + 0.35 * composite_vec + 0.15 * field_vec
        return self._rrf_fuse(fts, composite_results, vec_trigger, vec_action, ...)
```

This is a **domain-layer addition**, not a HybridDB feature. HybridDB stays generic.

### MemoryStore features that stay in MemoryStore (not HybridDB)

| Feature | Why it stays in MemoryStore |
|---------|---------------------------|
| Confidence boost on access (`_boost_access`) | Domain logic — only memories have confidence |
| Confidence decay (`maybe_decay_confidence`) | Domain logic — only memories forget |
| Supersession (`supersede_memory`) | Domain logic — only memories supersede |
| Connections graph (`add_connection`, `remove_connection`) | Domain logic — only memories have relationships |
| Vector reconciliation (`reconcile_vectors`) | Replaced by journal — but MemoryStore may add domain-specific reconciliation |
| Working/long-term memory tiers | Domain logic — hybrid search returns all, MemoryStore layers the tiers |
| Progressive disclosure (`get_compact_context`) | Domain logic — presentation concern |

### Verdict: MemoryStore fits on HybridDB ✅

- Schema maps cleanly — 3 LONGTEXT columns produce 3 ChromaDB collections
- Search maps with one gap (composite embedding) — solved at domain layer
- All domain-specific logic stays in MemoryStore
- Journal replaces explicit `reconcile_vectors()` calls

---

## 9. Fitness Check: MessageStore

### MessageStore schema mapped to HybridDB

```python
messages = {
    "id":       "INTEGER PRIMARY KEY AUTOINCREMENT",
    "ts":       "TEXT NOT NULL",      # metadata + recency scoring
    "role":     "TEXT NOT NULL",      # FTS5 + metadata
    "content":  "LONGTEXT",            # FTS5 + ChromaDB
    "metadata": "JSON",               # not indexed
}
```

### ChromaDB collections produced

```
messages_content    # embeddings of content, metadata: {role, ts}
```

Just **one** LONGTEXT column → **one** ChromaDB collection. Simplest possible mapping.

### MessageStore current features → HybridDB mapping

| Feature | How MessageStore does it | How HybridDB does it |
|---------|------------------------------|---------------------|
| FTS5 keyword search | Custom `search_keyword()` with BM25 | `search("messages", "content", query, mode=KEYWORD)` — same BM25 |
| Vector search | Custom `search_vector()` with cosine similarity | `search("messages", "content", query, mode=SEMANTIC)` — same ChromaDB query |
| Hybrid search | Custom `search_hybrid()` with 3-way fusion | `search("messages", "content", query, mode=HYBRID)` — same RRF fusion |
| Recency scoring | Inline: `1/(1+days_ago/30)`, weight=0.3 | `search(..., recency_weight=0.3, recency_column="ts")` — built-in |
| Metadata filtering | Stored `{"role": "user", "ts": "..."}` | Automatic — TEXT columns `role`, `ts` become metadata |
| Ghost filtering | `[m for m in results if m is not None]` | Automatic — batch fetch from SQL filters missing IDs |
| Summary messages | `role='summary'` + special retrieval | Same — just rows with a particular TEXT value |
| `add_message_with_embedding()` | Skip computing embedding | `insert()` with pre-computed embedding — same pattern |
| `reconcile_vectors()` | Not implemented (just silently drops ghosts) | Replaced by journal — never needed |

### MessageStore features that stay in MessageStore

| Feature | Why |
|---------|-----|
| `get_messages_with_summary()` | Domain logic — conversation windowing |
| `add_summary_message()` | Domain logic — conversation compression |
| `has_summary()` | Domain logic — checks for compression marker |

### Verdict: MessageStore fits on HybridDB perfectly ✅

- Single LONGTEXT column → single ChromaDB collection
- No gaps, no composite embeddings needed
- Recency scoring is built into HybridDB
- Metadata filtering is built into HybridDB (role, ts auto-included)
- Ghost filtering is built into HybridDB (batch SQL fetch)

---

## 10. File Layout

### Per-app isolation (recommended)

```
data/private/apps/
├── crm/
│   ├── app.db                 # SQLite + FTS5 + journal + schema
│   └── vectors/               # ChromaDB PersistentClient
│       ├── chroma.sqlite3     # ChromaDB metadata
│       └── {uuid}/           # HNSW index files
├── inventory/
│   ├── app.db
│   └── vectors/
├── todo/
│   └── app.db                 # No vectors/ (no LONGTEXT columns)
└── library/
    ├── app.db
    └── vectors/
```

### System stores

```
data/private/
├── conversation/
│   ├── messages.db            # → HybridDB: messages table
│   └── vectors/
├── memory/
│   ├── memory.db              # → HybridDB: memories + insights tables
│   └── vectors/
```

### Shared apps (multi-user deployment only)

```
data/shared/apps/
├── team_crm/
│   ├── app.db
│   └── vectors/
└── project_tracker/
    ├── app.db
    └── vectors/
```

### SQLite database internals

Each `app.db` contains:
- Application tables (user-defined)
- FTS5 virtual tables (auto-generated per TEXT/LONGTEXT column)
- FTS5 triggers (auto-generated)
- `_journal` table (operation queue)
- `_schema` table (schema metadata)

---

## 11. Public API Reference

```python
class HybridDB:
    """Hybrid search database: SQLite + FTS5 + ChromaDB with self-healing journal."""
    
    def __init__(self, path: str, embedding_fn: Callable[[str], list[float]] | None = None):
        """
        Args:
            path: Directory path for the database. SQLite + ChromaDB stored here.
            embedding_fn: Custom embedding function. Default: sentence-transformers all-MiniLM-L6-v2.
        """
    
    # ── Schema ──────────────────────────────────────────────
    
    def create_table(self, table: str, columns: dict[str, str]) -> None:
        """
        Create a table with columns.
        
        Args:
            table: Table name (e.g., "contacts")
            columns: Column definitions. Keys = column names, values = types.
                     Types: "TEXT", "LONGTEXT", "INTEGER", "REAL", "BOOLEAN", "JSON"
                     Column names ending with " NOT NULL" or " PRIMARY KEY" are supported.
                     
        Example:
            db.create_table("contacts", {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "first_name": "TEXT",
                "company": "LONGTEXT",
                "notes": "LONGTEXT",
                "clv": "REAL",
                "is_active": "BOOLEAN",
            })
        """
    
    def add_column(self, table: str, column: str, col_type: str) -> None:
        """Add a column to an existing table."""
    
    def drop_column(self, table: str, column: str) -> None:
        """Remove a column. Requires table rebuild (SQLite limitation)."""
    
    def rename_column(self, table: str, old_name: str, new_name: str) -> None:
        """Rename a column."""
    
    def list_tables(self) -> list[str]:
        """List all user tables (excludes _journal, _schema, FTS5 tables)."""
    
    def get_schema(self, table: str) -> dict:
        """Get column definitions for a table."""
    
    # ── CRUD ────────────────────────────────────────────────
    
    def insert(self, table: str, data: dict, sync: bool = True) -> int:
        """Insert a row. Returns the row ID. Auto-syncs FTS5 + journals ChromaDB.
        
        Args:
            sync: If True (default), process journal after commit. 
                  If False, journal is processed lazily on next search.
        """
    
    def insert_batch(self, table: str, rows: list[dict]) -> list[int]:
        """Insert multiple rows. Batch-embeds LONGTEXT columns."""
    
    def update(self, table: str, row_id: int, data: dict) -> bool:
        """Update a row. Auto-syncs FTS5 + journals ChromaDB metadata + embeddings."""
    
    def delete(self, table: str, row_id: int) -> bool:
        """Delete a row. Auto-syncs FTS5 + journals ChromaDB delete."""
    
    def get(self, table: str, row_id: int) -> dict | None:
        """Get a single row by ID."""
    
    def query(self, table: str, where: str = "", params: tuple = (), 
              order_by: str = "", limit: int = 100) -> list[dict]:
        """Raw SQL query. Returns list of dicts."""
    
    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        """Count rows matching condition."""
    
    # ── Search ──────────────────────────────────────────────
    
    def search(
        self,
        table: str,
        column: str,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        where: dict | None = None,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.0,
        recency_column: str | None = None,
    ) -> list[dict]:
        """
        Search a specific column.
        
        Args:
            table: Table name
            column: Column name (must be TEXT or LONGTEXT)
            query: Search query string
            mode: KEYWORD (FTS5 only), SEMANTIC (ChromaDB only), HYBRID (both)
            where: ChromaDB metadata filter, e.g., {"clv": {"$gt": 2000}, "status": "active"}
            limit: Max results
            fts_weight: 0.0 = vector-only, 1.0 = keyword-only, 0.5 = balanced
            recency_weight: 0.0 = ignore recency, 0.3 = moderate decay
            recency_column: Column with timestamps for recency scoring
        
        Returns:
            List of row dicts with added "_score" and "_search_mode" keys.
        """
    
    def search_all(
        self,
        table: str,
        query: str,
        where: dict | None = None,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.0,
        recency_column: str | None = None,
    ) -> list[dict]:
        """Search all LONGTEXT columns with RRF fusion."""
    
    # ── Maintenance ─────────────────────────────────────────
    
    def reconcile(self, table: str) -> dict:
        """
        Full re-sync of ChromaDB from SQLite. 
        Removes ghosts, backfills missing docs, updates stale metadata.
        Returns {"ghosts_deleted": N, "missing_added": N, "metadata_updated": N}.
        """
    
    def health(self, table: str) -> dict:
        """
        Lightweight health check — compares row counts without full reconciliation.
        Returns {"sqlite_rows": N, "chroma_docs": {collection: count}, "status": "ok"|"drift"|"broken"}.
        """
    
    def journal_status(self, table: str | None = None) -> dict:
        """Check pending journal entries. Returns {"pending": N, "failed": N}."""
    
    def process_journal(self, limit: int = 5000) -> int:
        """Manually process pending journal entries. Returns count processed."""
    
    def close(self) -> None:
        """Close all connections."""

class SearchMode(Enum):
    KEYWORD = "keyword"     # FTS5 BM25 only
    SEMANTIC = "semantic"   # ChromaDB vector only
    HYBRID = "hybrid"       # FTS5 + ChromaDB with RRF fusion
```

---

## 12. In Scope / Out of Scope

### In Scope

- ✅ SQLite storage with WAL mode
- ✅ FTS5 keyword search with BM25 scoring (per-column)
- ✅ ChromaDB vector search with HNSW (per-LONGTEXT-column)
- ✅ Hybrid search with Reciprocal Rank Fusion
- ✅ Recency scoring (time-decay)
- ✅ ChromaDB metadata filtering (where)
- ✅ Operation journal (self-healing consistency)
- ✅ Schema management (create table, add/drop/rename columns)
- ✅ Batch operations (insert_batch, process_journal in batches)
- ✅ NULL handling (omit missing keys from ChromaDB metadata)
- ✅ Ghost detection (batch SQL fetch naturally filters dead IDs)
- ✅ SQLite AUTOINCREMENT (prevents row ID reuse after delete)
- ✅ Per-app isolation (separate .db + vectors per app)

### Out of Scope

- ❌ Embedding model management (HybridDB accepts an `embedding_fn`, doesn't manage models)
- ❌ Composite/cross-column embeddings (domain layer responsibility, see MemoryStore gap)
- ❌ Authentication / authorization (HybridDB is per-user, auth is the app's job)
- ❌ Multi-user concurrency (single-writer per database, WAL allows concurrent readers)
- ❌ Replication / sync (single-machine, no distributed features)
- ❌ ChromaDB server mode (uses PersistentClient, not HttpClient)
- ❌ Foreign keys / relationships between tables (HybridDB doesn't enforce, you can add manually)
- ❌ Migration from AppStorage (migration script is a separate task)
- ❌ sqlite-vec backend (currently brute-force only — HNSW is required for production use)
- ❌ Custom HNSW SQLite extension (future consideration, see Section 15)

---

## 13. Design Decisions & Rationale

### Why per-column FTS5 tables, not one per table

One FTS5 table per table (containing all TEXT/LONGTEXT columns) would blend BM25 scores across columns. A match in `notes` (long, dense, many terms) scores very differently from a match in `first_name` (short, exact). Per-column FTS5 gives independent BM25 scores that can be weighted independently in fusion.

**Considered and rejected**: Single FTS5 table with all columns. Simpler but produces lower-quality hybrid fusion because BM25 can't distinguish which column matched.

### Why per-column ChromaDB collections, not one per table

Same reasoning. An embedding of `"Acme Corp"` captures the company's semantics cleanly. An embedding of `"Acme Corp VIP client key decision maker prefers email"` is noisier — the company's vector is diluted by the notes text.

**Considered and rejected**: Single ChromaDB collection with all LONGTEXT values concatenated. Loses column-level search precision and where-filtering granularity.

### Why LONGTEXT instead of a `search=` flag

Three approaches were evaluated:

1. **`search=hybrid/keyword/semantic`** (3 modes) — Too much cognitive load. `semantic`-only has no real use case. `search=hybrid` can be misread as "only hybrid, no keyword?"
2. **Smart detection** (LONGTEXT for `*notes*`, `*description*`) — Heuristics break in surprising ways. A column named `bio` gets detection but `biography` doesn't? No magic.
3. **`TEXT` vs `LONGTEXT`** — The type IS the search behavior. Zero config, zero magic. MySQL's TEXT/LONGTEXT pattern is well-known.

### Why Option D (operation journal) instead of Option B (reconcile)

| Aspect | Reconcile | Journal |
|--------|-----------|---------|
| Recovery granularity | Full table scan | Only affected rows |
| Detects insert failures | Must compare all IDs | Journal entry tells exactly |
| Detects metadata drift | Must compare all metadata | Journal entry tells exactly |
| Open-source UX | "Call reconcile() if broken" | "Self-heals on every search" |

### Why all scalar columns as metadata (not just TEXT)

Without numeric metadata, `clv > 2000` requires Python post-filtering (fetch 100 results, filter in Python, hope enough match). With REAL/INTEGER in metadata, ChromaDB's native `where` filter handles it during the ANN search phase — much more efficient.

### Why recency_weight is optional, not always-on

MessageStore uses recency (messages get stale). MemoryStore doesn't (memories are permanent). CRM probably doesn't. Making it optional prevents unnecessary computation for tables where recency doesn't matter.

### Why SQLite AUTOINCREMENT is mandatory

Without `AUTOINCREMENT`, SQLite can reuse the max rowid after deletion. This would create phantom ChromaDB entries where a new row inherits an old row's vector data. `AUTOINCREMENT` guarantees monotonic IDs that are never reused.

---

## 14. Known Risks & Mitigations

### Risk: Journal overflow during ChromaDB outage

If ChromaDB is unavailable for extended time, `_journal` grows unbounded.

**Mitigation**: Per-table cap at 50,000 entries. When exceeded, temporarily disable hybrid search for that table (fall back to keyword-only). Log warning. User can call `reconcile()` later to rebuild. The cap is per-table, not global, so one overflowing table doesn't disable hybrid for others.

### Risk: Column type change silently breaks metadata filtering

Changing `clv REAL` → `clv TEXT` converts metadata values from numbers to strings. `{"clv": {"$gt": 2000}}` would do string comparison, not numeric.

**Mitigation**: Log a warning on type changes involving REAL/INTEGER → TEXT. Suggest using `rename_column` strategy instead (add new column, migrate, drop old).

### Risk: ChromaDB PersistentClient single-writer

ChromaDB's PersistentClient uses SQLite internally with WAL. Two HybridDB instances writing to the same `vectors/` directory will conflict.

**Mitigation**: Document that one `vectors/` directory = one HybridDB instance. For multi-process, use ChromaDB server mode (not supported in v1). For shared apps in multi-user deployment, each container runs its own HybridDB instance; the shared volume must use a directory-per-app isolation pattern where only one container writes to a given app's `vectors/` directory.

### Risk: Embedding model mismatch

If the embedding model changes (e.g., all-MiniLM-L6-v2 → all-MiniLM-L12-v2), all existing vectors become invalid. Dimension mismatch causes crashes; same dimension but different model produces garbage results.

**Mitigation**: Store embedding model name + dimension in `_schema`. On init, verify model matches. If mismatch, **raise an error** by default — require explicit `force=True` to override. Silent garbage vectors are worse than a startup failure. When overridden, log a warning and suggest `reconcile()` with the new model (full re-embed).

### Risk: FTS5 rebuild cost on schema change

Adding/dropping TEXT/LONGTEXT columns requires rebuilding FTS5 virtual tables. For a table with 100k rows, this takes ~5 seconds.

**Mitigation**: Lazy rebuild — defer to next `_process_journal()` call, same as ChromaDB sync.

---

## 15. Migration Impact: MessageStore & MemoryStore

### Current state

Both stores manually wire the same SQLite+FTS5+ChromaDB pattern that HybridDB extracts:

| Store | Lines | SQLite | FTS5 | ChromaDB | Journal | Schema management |
|-------|-------|--------|------|----------|---------|-------------------|
| MessageStore | ~516 | ✅ | ✅ (1 table) | ✅ (1 collection) | ❌ reconcile-only | ❌ hardcoded |
| MemoryStore | ~1708 | ✅ | ✅ (3 fields) | ✅ (4 collections) | ❌ reconcile-only | ❌ hardcoded |
| AppStorage | ~791 | ✅ | ✅ (per-table) | ✅ (per-column) | ❌ reconcile-only | ✅ dynamic |

### After HybridDB

| Store | Lines (est.) | What remains |
|-------|-------------|-------------|
| MessageStore | ~50 | `get_messages_with_summary()`, `add_summary_message()`, `has_summary()` — domain logic only |
| MemoryStore | ~150 | Confidence decay, supersession, connections graph, working/long-term tiers — domain logic only |
| AppStorage | ~30 | App-level concerns (`_app_meta`, `_app_shares`) — domain logic only |

**Net reduction: ~2,200 lines of duplicated wiring replaced by one HybridDB class (~400 lines).**

### Migration path

1. Implement `HybridDB` as a standalone class in `src/sdk/hybrid_db.py`
2. Create thin domain wrappers:
   - `MessageStore` delegates CRUD+search to `HybridDB`, adds compression logic
   - `MemoryStore` delegates CRUD+search to `HybridDB`, adds confidence/connections logic
   - `AppStorage` delegates schema+CRUD+search to `HybridDB`, adds app metadata
3. Existing databases are backward-compatible — same SQLite schema, same ChromaDB collections. The `_journal` and `_schema` tables are added on first open.
4. Remove the duplicated FTS5, ChromaDB, and embedding code from each store.

### What stays in the domain layer

| Feature | Store | Why it stays |
|---------|-------|---------------|
| Conversation compression | MessageStore | Domain logic — when/how to summarize |
| Working vs long-term memory | MemoryStore | Domain logic — tier selection |
| Confidence boost on access | MemoryStore | Domain logic — only memories have confidence |
| Supersession | MemoryStore | Domain logic — only memories supersede |
| Connections graph | MemoryStore | Domain logic — only memories have relationships |
| App sharing (`_app_shares`) | AppStorage | Domain logic — access control |
| Composite embedding | MemoryStore | Domain layer addition — HybridDB is per-column only |

---

## 16. Benchmark Context

### v2 Benchmark results (corrected from v1)

These results use production MemoryStore schema, real embeddings (all-MiniLM-L6-v2, 384d), actual FTS5 MATCH queries, and fair timing (including vector writes for both engines):

| Metric (ms) | sqlite-vec @10k | ChromaDB @10k | sqlite-vec @100k | ChromaDB @100k |
|-------------|-----------------|---------------|-------------------|----------------|
| Bulk insert | 7,600 | 12,600 | 84,000 | 144,000 |
| Single insert | 68 | 36 | 66 | 38 |
| FTS5 keyword | 7.8 | 0.9 | 9.1 | 2.2 |
| Vector search | 92 | 10 | 807 | 10 |
| Hybrid search | 268 | 21 | 2,430 | 23 |

**Conclusion**: sqlite-vec's brute-force vector search is 9-79x slower than ChromaDB's HNSW, making hybrid search 12-105x slower. This gap grows linearly with row count.

### Why ChromaDB (HNSW) is required

sqlite-vec (v0.1.6) is brute-force only — no ANN index. From sqlite-vec GitHub issue #25:

> "sqlite-vec as of v0.1.0 will be brute-force search only, which slows down on large datasets (>1M w/ large dimensions)"

For an interactive assistant where search must return in <50ms, ChromaDB's HNSW is essential at any meaningful scale.

### Future: Native SQLite HNSW extension

If sqlite-vec or a new extension adds HNSW support to SQLite, HybridDB could eliminate the ChromaDB dependency. This would:
- Remove the journal complexity (single database, ACID transactions)
- Reduce deployment footprint (one .db file instead of .db + vectors/ directory)
- Enable true atomic schema changes (no lazy sync needed)

**This is the long-term goal**. HybridDB's `LONGTEXT` type abstraction is designed so that the backend can be swapped without changing the API — `LONGTEXT` today means "ChromaDB collection", tomorrow it could mean "sqlite-vec HNSW virtual table".

The benchmark file is at: `docs/benchmarks/test_memory_benchmark_v2.py`