# Memory Time-Tiers Plan (SQLite)

## Goal
Keep SQLite as the canonical memory store while adding time-based rollups (4h → daily → weekly → monthly) to improve relevance, reduce noise, and control retrieval cost.

## Why This Helps the LLM
- **Higher signal**: rollups summarize repeated preferences and stable facts.
- **Lower token cost**: inject fewer, higher-confidence memories instead of many raw entries.
- **Temporal relevance**: recent changes are surfaced from 4h/daily buckets, while older habits come from weekly/monthly.
- **Conflict resolution**: newer buckets can override older summaries when contradictions appear.

## Data Model
### A) Existing table (unchanged)
- `memories` (raw entries)

### B) New table: `memory_rollups`
Columns:
- `id` (uuid)
- `bucket_type` TEXT CHECK IN ('4h','daily','weekly','monthly')
- `bucket_start` TEXT (ISO8601)
- `bucket_end` TEXT (ISO8601)
- `memory_type` TEXT
- `summary` TEXT
- `confidence` REAL
- `source_count` INTEGER
- `status` TEXT DEFAULT 'active'
- `created_at` TEXT
- `updated_at` TEXT

Indexes:
- `(bucket_type, bucket_start)`
- `(memory_type)`

Optional:
- `memory_rollups_fts` (FTS5 on summary)

## Rollup Policy
- **4h buckets**: aggregate raw memories into summaries every 4 hours.
- **Daily**: aggregate 4h buckets into daily summaries.
- **Weekly**: aggregate daily into weekly.
- **Monthly**: aggregate weekly into monthly.

## Retention Policy
- Keep raw memories for `N` days (e.g., 14–30).
- After rollup, mark raw entries as `compacted` or reduce confidence weight.
- Rollups are the long-term durable memory surface.

## Query Strategy (for LLM)
- **Recent preference** (last day): search raw + 4h + daily.
- **Stable preference**: search weekly + monthly.
- **Ranking**: prefer higher confidence and more recent bucket.
- **Conflict handling**: if a newer bucket contradicts an older summary, prefer newer.

## Rollup Job Steps
1) Determine bucket window (e.g., last 4 hours for raw → 4h rollup).
2) Group by `memory_type` and optional `key`.
3) Summarize entries:
   - Prefer latest value when keys collide.
   - Increase confidence when repeated or consistent.
4) Write to `memory_rollups`.
5) Mark raw entries as compacted (optional).
6) Repeat for daily, weekly, monthly windows.

## LLM Usage Integration
- Update memory retrieval to:
  - Check for explicit recency intent ("recent", "this week").
  - Pull from tiered sources accordingly.
- Inject rollup summaries instead of raw text where possible.
- Limit total injected tokens by prioritizing:
  1) Newest bucket type
  2) Highest confidence
  3) Matching memory_type (preference/constraint/style)

## Implementation Checklist
1) Migration: add `memory_rollups` table + indexes
2) Add rollup worker (cron or scheduled job)
3) Add FTS5 for rollups (optional)
4) Extend memory retrieval to include rollups
5) Add `/mem rollup` command (manual trigger)
6) Add `/mem tier` command (inspect tiers)
7) Add tests for rollup correctness + retrieval ordering

## Success Criteria
- Lower token usage in memory injection
- Better preference stability with fewer contradictions
- Raw memory DB size bounded and predictable

## References
- Time-based tiering inspired by Time Machine-style retention (conceptual model).
- SQLite FTS5 (already used for raw memories in this project).
- Moltbot/Clawdbot memory docs (daily vs durable, pre-compaction flush): https://docs.clawd.bot/concepts/memory
