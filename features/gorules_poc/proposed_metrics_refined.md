# Proposed Metric Structure: Refined

## User's Proposed Metrics (Refined)

```python
{
  "storage_intent": "memory" | "database" | "vector" | "file",
  "retrieval_intent": "read" | "query" | "search" | "filter",
  "analytic_intent": true | false,
  "data_type": "structured" | "numeric" | "text" | "binary"
}
```

### Key Refinement: retrieval_intent = "search"

**"search" includes**:
- ✅ Keyword search ("find user named John")
- ✅ Similarity search ("find documents like this one")
- ✅ Semantic search ("search by meaning")
- ✅ Fuzzy matching ("find similar emails")

**This is much better!**

## Complete Intent Mapping

### storage_intent × retrieval_intent Matrix

| storage_intent | retrieval_intent | Result | Example |
|----------------|-----------------|--------|---------|
| **memory** | read | Memory | "Remember my preferences" |
| **memory** | query | Memory | "What did I say about X?" |
| **memory** | search | Memory | "Find my saved settings" |
| **database** | read | TDB | "Get my todo list" |
| **database** | query | ADB | "Join sales and expenses" |
| **database** | search | TDB or TDB+VDB | "Find transactions from Amazon" |
| **database** | filter | ADB | "Show expenses > $100" |
| **vector** | read | VDB | "Get document by ID" |
| **vector** | search | VDB | "Find similar documents" |
| **vector** | filter | VDB | "Filter by relevance score" |
| **file** | read | Files | "Read my report" |
| **file** | query | Files+ADB | "Analyze my CSV export" |
| **file** | search | Files+VDB | "Search my reports" |

## How "search" Intent Works

### Examples Showing Search = Keywords + Similarity

```python
# Example 1: Keyword search
Request: "Find user named John"
Metrics:
{
  "storage_intent": "database",
  "retrieval_intent": "search",
  "analytic_intent": false,
  "data_type": "structured"
}
Result: TDB (keyword search on users table)

# Example 2: Similarity search
Request: "Find similar notes about Python"
Metrics:
{
  "storage_intent": "vector",
  "retrieval_intent": "search",
  "analytic_intent": false,
  "data_type": "text"
}
Result: VDB (semantic/similarity search)

# Example 3: Hybrid search
Request: "Search for transactions like this one"
Metrics:
{
  "storage_intent": "database",  # Transaction data
  "retrieval_intent": "search",   # Similarity search
  "analytic_intent": false,
  "data_type": "structured"
}
Result: TDB + VDB (track in TDB, find similar in VDB)
```

## Multi-Storage Examples

### 1. "Track expenses and analyze trends"

```python
{
  "storage_intent": "database",
  "retrieval_intent": "read",      # CRUD operations
  "analytic_intent": true,          # Will analyze later
  "data_type": "structured"
}

Decision Flow:
1. storage_intent = "database" → TDB or ADB
2. retrieval_intent = "read" → Default to TDB
3. analytic_intent = true → Also use ADB
4. Result: ["tdb", "adb"]
```

### 2. "Track data but also search it semantically"

```python
{
  "storage_intent": "database",    # Structured data
  "retrieval_intent": "search",     # Keyword/similarity search
  "analytic_intent": false,
  "data_type": "structured"
}

Decision Flow:
1. storage_intent = "database" → TDB or ADB
2. retrieval_intent = "search" → Add VDB
3. Result: ["tdb", "vdb"]
```

### 3. "Generate report from search results"

```python
{
  "storage_intent": "file",        # Report generation
  "retrieval_intent": "search",     # First search, then report
  "analytic_intent": false,
  "data_type": "text"
}

Decision Flow:
1. storage_intent = "file" → Files for report
2. retrieval_intent = "search" → Also need VDB for search
3. Result: ["vdb", "files"]  # Note order: search first, then generate
```

### 4. "Export report and analyze it"

```python
{
  "storage_intent": "file",        # File export
  "retrieval_intent": "query",     # Analyze later
  "analytic_intent": true,          # Explicit analytics
  "data_type": "structured"
}

Decision Flow:
1. storage_intent = "file" → Files for export
2. analytic_intent = true → Also ADB for analysis
3. Result: ["files", "adb"]
```

## retrieval_intent Semantics

### "read" - Simple CRUD

```
Operations: create, read, update, delete
Examples: "Get my todos", "Add task", "Update expense"
Storage: TDB for structured, Memory for preferences
```

### "query" - Complex Operations

```
Operations: joins, aggregations, window functions, pivot tables
Examples: "Join tables", "Show running total", "Calculate rank"
Storage: ADB for analytics, TDB for simple queries
```

### "search" - Finding Content (Keywords + Similarity) ⭐

```
Operations:
  - Keyword search: "find user named John"
  - Similarity search: "find similar notes"
  - Semantic search: "search by meaning"
  - Fuzzy matching: "find transactions like this"

Examples:
  - "Find transactions from Amazon"
  - "Search for similar documents"
  - "Find emails about project X"

Storage:
  - TDB (keyword search on structured data)
  - VDB (similarity/semantic search on content)
  - TDB + VDB (hybrid: structured + semantic)
```

### "filter" - Filtering and Sorting

```
Operations: Where, having, order by, top N
Examples: "Show expenses > $100", "Top 10 items", "Filter by date"
Storage: ADB (aggregates), TDB (simple filters)
```

## Multi-Intent Detection

### Multiple retrieval_intents

```python
# Request: "Search for expenses and show monthly totals"
{
  "storage_intent": "database",
  "retrieval_intent": "search",     # First part
  "analytic_intent": true,          # Second part
  "data_type": "structured"
}

# Or as multiple intents:
{
  "storage_intent": "database",
  "retrieval_intents": ["search", "filter"],  # Multiple!
  "analytic_intent": true,
  "data_type": "structured"
}
```

**Question**: Should we allow multiple retrieval_intents or just pick the dominant one?

## Updated Decision Tree

```python
def select_storage_refined(storage_intent, retrieval_intent, analytic_intent, data_type):
    """Refined decision logic with search = keywords + similarity."""

    # 1. Memory is straightforward
    if storage_intent == "memory":
        return ["memory"]

    # 2. Vector for search intent (includes similarity)
    if storage_intent == "vector":
        if retrieval_intent == "search":
            # May also use database if structured data
            if data_type == "structured":
                return ["tdb", "vdb"]  # Store in TDB, search in VDB
            return ["vdb"]
        return ["vdb"]

    # 3. Database with different retrieval patterns
    if storage_intent == "database":
        if retrieval_intent == "query":
            # Complex operations (joins, aggregations, windows)
            return ["adb"]
        elif retrieval_intent == "search":
            # Search can use TDB (keywords) or VDB (similarity)
            if data_type == "text":
                return ["vdb"]  # Content is text → VDB
            return ["tdb"]   # Structured data → TDB search
        elif retrieval_intent == "filter":
            # Filtering operations
            return ["adb"]
        elif retrieval_intent == "read":
            # Simple CRUD
            return ["tdb"]

    # 4. Files with analytics
    if storage_intent == "file":
        if analytic_intent:
            return ["files", "adb"]
        # If search intent on files, might need VDB too
        if retrieval_intent == "search":
            return ["files", "vdb"]
        return ["files"]

    # Default
    return ["files"]
```

## Token Comparison

### Current System (6 metrics)

```
Total prompt: ~3,520 tokens
```

### Your Proposal (4 metrics, refined "search")

```
- Instructions: ~800 tokens (clearer structure)
- Metric definitions: ~400 tokens (4 simple concepts)
- Few-shot examples: ~500 tokens (fewer needed, clearer logic)
- User request: ~20 tokens
- Total: ~1,720 tokens (51% reduction!)
```

## Advantages of Your Refinement

### 1. "search" is More Intuitive ✅

Users naturally say "search" for both:
- "Search my files" (could be keyword or semantic)
- "Find similar documents" (similarity)
- "Search by meaning" (semantic)

### 2. Reduces Metric Redundancy ✅

**Current**: semanticSearch (90% overlaps with searchByMeaning)
**Yours**: Single "search" intent covers all cases

### 3. Simplifies Decision Logic ✅

**Current**: Complex rules to distinguish semanticSearch vs searchByMeaning
**Yours**: "search" intent → Use appropriate search engine

### 4. Better Multi-Storage Support ✅

```python
# "Track data and search it"
storage_intent: "database"
retrieval_intent: "search"
Result: TDB + VDB (clear and correct)
```

## Proposed Next Steps

### Phase 1: Implement Test Parser

Create parser with your refined metrics and test on 50 cases.

### Phase 2: Validate Decision Logic

Test if the refined decision tree handles all edge cases correctly.

### Phase 3: Compare Results

- Your proposal (4 metrics)
- Current system (6 metrics)
- Baseline (direct LLM, 98%)

Expected outcome: Your proposal achieves **95%+ accuracy** with **51% token reduction**.

Should I implement this experiment?
