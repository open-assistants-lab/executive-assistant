# Vector Store Performance Benchmark: DuckDB vs LanceDB

**Benchmark Date:** 2026-01-19 15:07:59

---


## 100 Documents

### Performance Comparison

| Metric | DuckDB | LanceDB | Winner |
|--------|--------|---------|--------|
| Insert Throughput | 5.17 docs/sec | 654.86 docs/sec | **LanceDB** |
| Vector Search (avg) | 535.692 ms | 16.835 ms | **LanceDB** |
| Storage Size | 3.26 MB | 0.20 MB | **LanceDB** |
| Peak Memory | 134.57 MB | 1.35 MB | **LanceDB** |

### Detailed Results

#### DuckDB

- **Insert Time:** 19.339 sec
- **Throughput:** 5.17 docs/sec
- **Vector Search:** 535.692 ms (average)
- **Hybrid Search:** 14.542 ms (average)
- **Storage:** 3.26 MB
- **Peak Memory:** 134.57 MB

#### LanceDB

- **Insert Time:** 0.153 sec
- **Throughput:** 654.86 docs/sec
- **Vector Search:** 16.835 ms (average)
- **Storage:** 0.20 MB
- **Peak Memory:** 1.35 MB

---


## 500 Documents

### Performance Comparison

| Metric | DuckDB | LanceDB | Winner |
|--------|--------|---------|--------|
| Insert Throughput | 292.82 docs/sec | 991.23 docs/sec | **LanceDB** |
| Vector Search (avg) | 18.405 ms | 13.244 ms | **LanceDB** |
| Storage Size | 4.51 MB | 0.89 MB | **LanceDB** |
| Peak Memory | 6.66 MB | 6.66 MB | **DuckDB** |

### Detailed Results

#### DuckDB

- **Insert Time:** 1.708 sec
- **Throughput:** 292.82 docs/sec
- **Vector Search:** 18.405 ms (average)
- **Hybrid Search:** 13.759 ms (average)
- **Storage:** 4.51 MB
- **Peak Memory:** 6.66 MB

#### LanceDB

- **Insert Time:** 0.504 sec
- **Throughput:** 991.23 docs/sec
- **Vector Search:** 13.244 ms (average)
- **Storage:** 0.89 MB
- **Peak Memory:** 6.66 MB

---


## 1000 Documents

### Performance Comparison

| Metric | DuckDB | LanceDB | Winner |
|--------|--------|---------|--------|
| Insert Throughput | 300.20 docs/sec | 1000.61 docs/sec | **LanceDB** |
| Vector Search (avg) | 17.898 ms | 15.906 ms | **LanceDB** |
| Storage Size | 6.01 MB | 1.75 MB | **LanceDB** |
| Peak Memory | 13.30 MB | 13.30 MB | **LanceDB** |

### Detailed Results

#### DuckDB

- **Insert Time:** 3.331 sec
- **Throughput:** 300.20 docs/sec
- **Vector Search:** 17.898 ms (average)
- **Hybrid Search:** 14.485 ms (average)
- **Storage:** 6.01 MB
- **Peak Memory:** 13.30 MB

#### LanceDB

- **Insert Time:** 0.999 sec
- **Throughput:** 1000.61 docs/sec
- **Vector Search:** 15.906 ms (average)
- **Storage:** 1.75 MB
- **Peak Memory:** 13.30 MB

---

## Summary

- **DuckDB Wins:** 0 metrics
- **LanceDB Wins:** 6 metrics

### Key Findings


#### 100 Documents:

- LanceDB is **31.82x faster** on vector search
- LanceDB has **126.6%** higher insert throughput
- LanceDB uses **93.8%** less storage

#### 500 Documents:

- LanceDB is **1.39x faster** on vector search
- LanceDB has **3.4%** higher insert throughput
- LanceDB uses **80.2%** less storage

#### 1000 Documents:

- LanceDB is **1.13x faster** on vector search
- LanceDB has **3.3%** higher insert throughput
- LanceDB uses **70.9%** less storage