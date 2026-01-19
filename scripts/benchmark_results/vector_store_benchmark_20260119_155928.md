# Vector Store Performance Benchmark: DuckDB vs LanceDB

**Benchmark Date:** 2026-01-19 15:59:28

---


## 100 Documents

### Performance Comparison

| Metric | DuckDB | LanceDB | Winner |
|--------|--------|---------|--------|
| Insert Throughput | 8.74 docs/sec | 725.55 docs/sec | **LanceDB** |
| Vector Search (avg) | 19.421 ms | 29.568 ms | **DuckDB** |
| Storage Size | 3.26 MB | 0.20 MB | **LanceDB** |
| Peak Memory | 134.51 MB | 1.35 MB | **LanceDB** |

### Detailed Results

#### DuckDB

- **Insert Time:** 11.444 sec
- **Throughput:** 8.74 docs/sec
- **Vector Search:** 19.421 ms (average)
- **Hybrid Search:** 13.760 ms (average)
- **Storage:** 3.26 MB
- **Peak Memory:** 134.51 MB

#### LanceDB

- **Insert Time:** 0.138 sec
- **Throughput:** 725.55 docs/sec
- **Vector Search:** 29.568 ms (average)
- **Storage:** 0.20 MB
- **Peak Memory:** 1.35 MB

---

## Summary

- **DuckDB Wins:** 1 metrics
- **LanceDB Wins:** 1 metrics

### Key Findings


#### 100 Documents:

- DuckDB is **1.52x faster** on vector search
- LanceDB has **83.0%** higher insert throughput
- LanceDB uses **93.8%** less storage