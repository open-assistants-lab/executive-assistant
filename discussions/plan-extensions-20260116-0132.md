# Plan: Dateparser + RapidFuzz + Logging + Firecrawl (2026-01-16 01:32)

## Feasibility
- **Dateparser replacement:** High. Current reminder parsing is in one file and can be swapped with minimal ripple.
- **RapidFuzz for KB + file search:** High. Can be introduced as a fallback layer without breaking FTS or glob/grep flows.
- **Logging library:** Medium. Straightforward to add, but needs early initialization and a small logging shim.
- **Firecrawl API integration:** Medium. Depends on official API/SDK details; should be easy once the exact endpoints/params are confirmed.

## Assumptions / Open Questions
- Firecrawl docs confirm env names and endpoints. Proposed env keys: `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL` (aligns with `.mcp.json`).
- No strict timezone handling is currently required for reminders (naive datetimes are accepted).

## Implementation Plan

### 1) Dependencies
- Add to `pyproject.toml`:
  - `dateparser`
  - `rapidfuzz`
  - logging library pick (see section 4)
  - HTTP client for Firecrawl (e.g., `httpx`) **if** not using the official Firecrawl SDK

### 2) Replace Reminder Date Parser (dateutil -> dateparser)
- File: `src/executive_assistant/tools/reminder_tools.py`
- Replace `_parse_time_expression` logic with `dateparser.parse` using settings:
  - `PREFER_DATES_FROM = "future"` (keeps reminders forward-looking)
  - `RELATIVE_BASE = datetime.now()`
  - `STRICT_PARSING = False`
- Keep a small pre-parse for edge formats if dateparser fails (e.g., `1130hr`) to avoid regressions.
- Update help text in `set_reminder` docstring to mention dateparser-supported expressions.

### 3) Add RapidFuzz for KB Search
- File: `src/executive_assistant/storage/kb_tools.py`
- Behavior change (no new tool required):
  - After BM25 returns **no results**, run a fuzzy fallback over candidate docs.
  - Use `rapidfuzz.process.extract` with `fuzz.token_set_ratio` (or `WRatio`).
  - Limit scan size (e.g., max 1,000 docs/table; use `content[:500]` + metadata) to avoid large-KB overhead.
  - Only include results above a cutoff (e.g., score >= 70) and label as “fuzzy match”.
- If a `table_name` is provided and not found, return fuzzy table name suggestions.

### 4) Add RapidFuzz for File Search
- File: `src/executive_assistant/storage/file_sandbox.py`
- Add a new tool (verb-first), e.g. `find_files_fuzzy(query, directory="", recursive=True, limit=10, score_cutoff=70)`:
  - Collect file paths (relative to sandbox root).
  - Use RapidFuzz to rank closest matches by filename/path.
  - Return ranked list with scores.
- Register the new tool in `src/executive_assistant/tools/registry.py` so it becomes available to the agent.

### 5) Pick and Integrate a Logging Library
- Recommendation: **Loguru** (minimal config, readable output).
- Add `loguru` dependency.
- Create `src/executive_assistant/logging.py`:
  - Configure Loguru sink/format.
  - Bridge stdlib logging via an intercept handler so existing `logging.getLogger` calls still work.
- Call `configure_logging()` early in `src/executive_assistant/main.py`.
- Optional: add `LOG_LEVEL` to `src/executive_assistant/config/settings.py` and `.env.example`.

### 6) Firecrawl API Integration
- Add settings to `src/executive_assistant/config/settings.py`:
  - `FIRECRAWL_API_KEY: str | None`
  - `FIRECRAWL_API_URL: str | None` (default to official base URL)
- Add to `.env.example` and `README.md`.
- Create `src/executive_assistant/tools/firecrawl_tool.py` with tools aligned to official docs:
  - `firecrawl_scrape(url, format="markdown", ...)`
  - Optional `firecrawl_crawl(url, limit=..., ...)` if supported
- Use the official Firecrawl Python SDK if recommended by docs; otherwise implement via `httpx`:
  - Build request with API key auth header
  - Handle response normalization (text/markdown)
  - Timeouts + error mapping
- Register tools in `src/executive_assistant/tools/registry.py` when API key is set.

## Risks / Mitigations
- **Dateparser behavior changes**: Add a small set of regression checks (manual or lightweight tests) for existing reminder formats.
- **RapidFuzz scan cost**: Apply caps and short text extraction to keep worst-case latency bounded.
- **Firecrawl API variance**: Confirm endpoints/params before coding; keep tool signature minimal and add clear error messages when not configured.

## Deliverables
- Updated deps in `pyproject.toml`
- Dateparser-based reminders
- Fuzzy KB + file search
- Logging library configured
- Firecrawl tool + envs + docs update
