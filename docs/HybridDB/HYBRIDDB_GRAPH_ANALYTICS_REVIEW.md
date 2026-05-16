# HybridDB Graph + Analytics — Implementation Review

> Reviewed: `src/sdk/hybrid_db.py` (2,143 lines), `tests/sdk/test_graph_analytics.py` (661 lines, 53 tests + 12 new)
> Date: May 2026 — **UPDATED with implementation status**

---

## Verdict

**All P0-P2 items addressed. 126 tests pass, lint clean.** Native DuckDB journal sync deferred as agreed.

---

## 1. Items Addressed (since original review)

| Item | Original Priority | Status | Note |
|---|---|---|---|
| Test coverage (graph/duckdb) | P0 | ✅ DONE | 53 tests existed, 12 new added: TestGraphSync (5), TestEdgeDecay (4), TestNxCache (3). Total: 65 graph/analytics + 61 original = 126. |
| Decay floor mismatch | P2 | ✅ DONE | Floor changed from 0.01 → 0.05, now matches reconcile delete threshold |
| to_networkx directed cache | P1 | ✅ DONE | Cache now stores `directed` flag. `to_networkx(directed=False)` rebuilds if cache was built for directed. |
| search_graph hardcoded tables | P1 | ✅ DONE | Now scans `_graph_sync` registry instead of hardcoding "memories" + "messages". |
| DuckDB full table rebuild | P3 | ⚠️ DEFERRED | Correctness-first design. Full refresh per affected table is correct and fast at journal batch sizes (<5K rows). Incremental per-row upserts are an optimization for when this becomes a bottleneck. |

## 2. Items Deferred (with reasoning)

| Item | Original Priority | Reasoning |
|---|---|---|
| Native DuckDB materialized views | P3 | Thin adapter (ATTACH per query) was slower than SQLite at 100K rows. Current approach uses persistent `analytics.duckdb` with full table refresh per journal batch — correct, fast enough, no per-query overhead. Materialized views add 200+ lines for a marginal gain. |
| `query()` auto-routing to DuckDB | P3 | Explicit routing (`analytics()` method) is safer. Different NULL semantics, type coercion between engines. Callers decide when they want DuckDB. |
| Incremental per-row DuckDB upserts | P3 | Current full refresh per table is ~5-15ms for journal batches. Not a bottleneck. Can add incremental when a table hits 1M+ rows and sync latency matters. |

## 3. Store Integration Status

| Store | DuckDB | Graph |
|---|---|---|
| `MessageStore` | ✅ `register_duckdb_table("messages")` on init. All inserts auto-sync via journal. | N/A |
| `MemoryStore` | ❌ Deferred — no analytics use case strong enough yet | ✅ `register_entity_node("memories")`. `add_connection` dual-writes JSON + graph edges. `get_connections` queries `neighbors()`. New: `traverse_memories`, `search_graph`, `get_central_memories`, `detect_memory_communities`. |

---

## 4. Remaining Recommendations

- **Edge auto-sync only on reconcile()**: `_auto_sync_graph_nodes()` and `_auto_sync_graph_edges()` are called from `reconcile()`, not automatically on insert. This is intentional — auto-sync is a maintenance operation, not a hot path. Could add a `sync_on_write` flag to `add_connection()` later if needed.
- **`linked_to` JSON stays**: Dual-write preserves backward compatibility. Can drop the column once all consumers use graph APIs.
