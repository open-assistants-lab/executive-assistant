# Ken Executive Assistant - Comprehensive Test Plan

**Total Tests:** 237 (212 + 10 check-in tests + 15 learning patterns)
**Last Updated:** 2025-02-06
**Status:** Ready for Execution

---

## Table of Contents

1. [Feature Implementation Status](#feature-implementation-status)
2. [Test Overview](#test-overview)
3. [Phase 1: Cross-Persona Tests](#phase-1-cross-persona-tests-same-task-different-personas)
4. [Phase 2: Persona-Specific Deep Dives](#phase-2-persona-specific-deep-dives)
5. [Phase 3: Adhoc App Build-Off](#phase-3-adhoc-app-build-off)
6. [Phase 4: Learning & Adaptation](#phase-4-learning--adaptation)
7. [Phase 5: Web Scraping Intelligence](#phase-5-web-scraping-intelligence)
8. [Phase 6: Middleware Testing](#phase-6-middleware-testing)
9. [Phase 7: Streaming Responses](#phase-7-streaming-responses)
10. [Phase 8: Error Handling](#phase-8-error-handling--edge-cases)
11. [Phase 9: Multi-Turn Conversations](#phase-9-multi-turn-conversations)
12. [Phase 10: Channel Differences](#phase-10-channel-differences)
13. [Phase 11: Checkpointer/State Management](#phase-11-checkpointerstate-management)
14. [Phase 12: Shared Scope](#phase-12-shared-scope)
15. [Phase 13: Security Testing](#phase-13-security-testing)
16. [Phase 14: Concurrent Access](#phase-14-concurrent-access)
17. [Phase 15: Performance Benchmarks](#phase-15-performance-benchmarks)
18. [Phase 16: Check-in Monitoring](#phase-16-check-in-monitoring)
19. [Phase 17: Learning Patterns](#phase-17-learning-patterns)
20. [Test Execution Guide](#test-execution-guide)
21. [Scoring Matrix](#scoring-matrix)

---

## Feature Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Onboarding | ✅ Implemented | Skill-based + channel-level |
| Memory (4 pillars) | ✅ Implemented | profile, preference, fact, constraint |
| TDB (Transactional DB) | ✅ Implemented | SQLite per user |
| ADB (Analytics DB) | ✅ Implemented | DuckDB per user |
| VDB (Vector DB) | ✅ Implemented | SQLite+FTS5 per user |
| File Storage | ✅ Implemented | Per-user file system |
| Reminders | ✅ Implemented | Scheduler-based |
| Adhoc Apps | ✅ Implemented | Built via TDB/ADB/VDB |
| Web Search | ✅ Implemented | Firecrawl integration |
| Web Scraping (3 tools) | ✅ Implemented | firecrawl_scrape, firecrawl_crawl, playwright_scrape |
| MCP Integration | ✅ Implemented | ClickHouse example |
| Export/Import | ✅ Implemented | CSV, JSON, Parquet |
| TodoListMiddleware | ✅ Implemented | Agent execution planning |
| ThreadContextMiddleware | ✅ Implemented | ContextVar propagation |
| StatusUpdateMiddleware | ✅ Implemented | "Thinking..." indicators |
| ToolRetryMiddleware | ✅ Implemented | Retry failed tools |
| ModelRetryMiddleware | ✅ Implemented | Retry failed LLM calls |
| ModelCallLimitMiddleware | ✅ Implemented | Cap at 50 calls |
| ToolCallLimitMiddleware | ✅ Implemented | Cap at 100 calls |
| ContextEditingMiddleware | ❌ Disabled | Token management (can enable) |
| HITLMiddleware | ❌ Disabled | Human-in-the-loop (can enable) |
| Conversation → Instincts | ✅ Implemented | Pattern learning |
| Conversation → Skills | ✅ Implemented | load_skill() tool |
| **Check-in (Journal + Goals)** | ✅ Implemented | Proactive monitoring |
| **Scheduled Flows** | ❌ NOT IMPLEMENTED | Planned for future |
| **Image/Multimodal** | ⚠️ PARTIAL | OCR only, no LLM vision |
| **Email/SMS Notifications** | ❌ NOT IMPLEMENTED | Telegram/HTTP only |
| **Webhooks** | ❌ NOT IMPLEMENTED | Not available |
| **API Rate Limiting** | ❌ NOT IMPLEMENTED | No per-user/global limits |
| **Audit Logging** | ✅ PARTIAL | User registry logs, no comprehensive audit |
| **GDPR Export** | ❌ NOT IMPLEMENTED | No all-user-data export |
| **GDPR Deletion** | ⚠️ PARTIAL | `/reset` command, not full GDPR |

---

## Test Overview

### Test Methodology

**All tests via HTTP API** (production-real testing):

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_{persona}_{test_number}",
    "content": "test query",
    "stream": false
  }'
```

### Helper Functions

```bash
# Test agent via HTTP
test_agent() {
  local user_id=$1
  local content=$2
  curl -s -X POST http://localhost:8000/message \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$user_id\",\"content\":\"$content\",\"stream\":false}" \
    | jq -r '.[0].content'
}

# Extract tool calls from response
get_tools() {
  grep -oP '<invoke name="\K[^"]+' || echo "No tools called"
}
```

---

## Phase 1: Cross-Persona Tests (Same Task, Different Personas)

**Goal:** Test agent adaptability to different user personas with the same core task.

**Tests:** 12

### Personas Defined:

| Persona | Technical Skill | Goals | Communication Style |
|---------|-----------------|-------|---------------------|
| **Executive** | Low | Quick insights, decisions | Brief, no jargon |
| **Analyst** | Medium | Deep data exploration, trends | Some technical terms |
| **Developer** | High | Automation, APIs, code | Technical, concise |
| **Gong Cha Expert** | Mixed | Domain-specific queries | Industry terms |

---

### Test Suite 1: Onboarding & Memory Formation

| Test | Persona | Query | Expected |
|------|---------|-------|----------|
| 1.1 | Executive | "I'm a busy CEO, always give me brief summaries" | Creates profile: role=executive, preference=brief |
| 1.2 | Analyst | "I'm a data analyst, I love detailed numbers and trends" | Creates profile: role=analyst, preference=detailed |
| 1.3 | Developer | "I'm a developer, be direct, no fluff, show me code" | Creates profile: role=developer, style=concise |
| 1.4 | Gong Cha | "yesterday's sales" | **NO onboarding**, direct query |

**Verify:**
- [ ] Onboarding triggers for 1.1-1.3 (new users)
- [ ] No onboarding for 1.4 (admin skills present)
- [ ] `create_user_profile` called with correct params
- [ ] Memories stored: profile (role), preference (style), communication_style

---

### Test Suite 2: Memory Retrieval & Application

| Test | Persona | Query | Expected |
|------|---------|-------|----------|
| 2.1 | Executive | "What's my sales summary?" | Brief response (respects preference) |
| 2.2 | Analyst | "What's my sales summary?" | Detailed breakdown (respects preference) |
| 2.3 | Developer | "What's my sales summary?" | Direct + maybe SQL (respects style) |

**Verify:**
- [ ] Agent recalls communication preferences from memory
- [ ] Response style matches persona
- [ ] Different answers for same query based on stored preferences

---

### Test Suite 3: Conversation → Instincts

| Test | Persona | Query (Round 1) | Query (Round 2) |
|------|---------|-----------------|-----------------|
| 3.1 | Executive | "Track my strategic initiatives" | "Track my quarterly goals" |
| 3.2 | Analyst | "Compare YOY sales by region" | "Compare YOY revenue by territory" |
| 3.3 | Developer | "Create a REST API" | "Build a GraphQL API" |

**Verify:**
- [ ] Round 2: Agent applies learned pattern from Round 1
- [ ] Instinct system creates new instinct from conversation
- [ ] Same tool usage pattern applied to new query

---

### Test Suite 4: Conversation → Skill

| Test | Query | Expected |
|------|-------|----------|
| 4.1 | "I need to do advanced analytics with DuckDB" | Agent calls `load_skill("analytics_with_duckdb")` |
| 4.2 | "Help me plan a complex project" | Agent calls `load_skill("planning")` |
| 4.3 | "I need to organize my calendar" | Agent calls `load_skill("organization")` |

**Verify:**
- [ ] Agent recognizes need for specialized skill
- [ ] `load_skill` called with correct skill name
- [ ] Follow-up queries use loaded skill's guidance

---

## Phase 2: Persona-Specific Deep Dives

**Goal:** Test each persona's complete feature interaction.

**Tests:** 46

---

### 👔 Executive Suite (Low technical, high-level)

| # | Feature | Test Query | Expected Behavior |
|---|---------|------------|-------------------|
| E1 | **Onboarding** | "I'm a CEO, help me manage my business" | Brief, business-focused onboarding |
| E2 | **Memory** | "Remember I prefer executive summaries" | Stored as `preference` memory |
| E3 | **TDB** | "Track my key initiatives and status" | Creates TDB table: initiatives (name, status, priority) |
| E4 | **ADB** | "What are my top 3 priorities this week?" | ADB query with aggregation, brief summary |
| E5 | **VDB** | "Save notes from board meeting" | VDB collection for semantic search |
| E6 | **File** | "Save strategy document as markdown" | Writes `.md` file |
| E7 | **Reminder** | "Remind me about budget review tomorrow 9am" | Reminder created |
| E8 | **Adhoc CRM** | "Track my key contacts and company interactions" | TDB: contacts (name, company, last_contact) |
| E9 | **Web Search** | "What are competitors doing in AI?" | Web search, brief summary |
| E10 | **Export** | "Export my initiatives to Excel" | CSV export via `export_adb_table` |

---

### 📊 Analyst Deep Dive (Medium technical, data-focused)

| # | Feature | Test Query | Expected Behavior |
|---|---------|------------|-------------------|
| A1 | **Onboarding** | "I'm a data analyst, help me explore data" | Data-focused onboarding |
| A2 | **Memory** | "I care about YOY trends and seasonality" | Stored as `preference` |
| A3 | **TDB** | "Log my daily analysis tasks" | TDB: analysis_log (date, task, findings) |
| A4 | **ADB** | "Show monthly sales trends with YoY comparison" | Complex ADB query with window functions |
| A5 | **VDB** | "Find that analysis I did about Q3 seasonality" | Semantic search across past analyses |
| A6 | **File** | "Save detailed report with tables" | Markdown with data tables |
| A7 | **Reminder** | "Remind me every Monday to review weekly metrics" | Recurring reminder |
| A8 | **Adhoc Knowledge Base** | "Save market research for future reference" | VDB: research (content, tags, date) |
| A9 | **→ Skill** | "Help me with advanced DuckDB analytics" | `load_skill("analytics_with_duckdb")` |
| A10 | **Export** | "Export customer segments to CSV" | CSV export with segmentation |
| A11 | **→ Instincts** | "Analyze regional sales" → Repeat for "territory" | Pattern learned, same query structure |

---

### 💻 Developer Power User (High technical, automation)

| # | Feature | Test Query | Expected Behavior |
|---|---------|------------|-------------------|
| D1 | **Onboarding** | "Create a project management API" | **SKIP** onboarding, direct build |
| D2 | **Memory** | "I use PostgreSQL schema naming conventions" | Stored as `preference` |
| D3 | **TDB** | "Create relational schema: users, projects, tasks" | Multi-table TDB with implied FKs |
| D4 | **ADB** | "Show raw SQL for complex analytics query" | Returns SQL for verification |
| D5 | **VDB** | "Build semantic search over API docs" | VDB: api_docs (endpoint, description, code) |
| D6 | **File** | "Save API spec as JSON" | JSON file output |
| D7 | **Reminder** | "Remind me about code review in 2 hours" | Simple reminder |
| D8 | **Adhoc CRM** | "Build full CRM: contacts, deals, activities" | TDB: 3 tables with relationships |
| D9 | **→ Skill** | "I need system patterns for agent improvement" | `load_skill("system_patterns_(agent_self-improvement)")` |
| D10 | **Export/Import** | "Export all tables, then import to new workspace" | Bulk operations |
| D11 | **→ Instincts** | "Create REST API" → "Create GraphQL API" | Pattern recognized, same approach |
| D12 | **Todo Planning** | "Set up multi-region deployment: 1) backup, 2) migrate, 3) verify, 4) switch DNS" | `write_todos` with 4 steps |

---

### 🧱 Gong Cha Domain Expert (Specialized business)

| # | Feature | Test Query | Expected Behavior |
|---|---------|------------|-------------------|
| G1 | **Onboarding** | "yesterday's sales" | **NO onboarding**, immediate query |
| G2 | **Memory** | "I care about store performance metrics" | Stored as domain `preference` |
| G3 | **MCP ClickHouse** | "yesterday's sales by store" | Uses `run_select_query` on `gong_cha_redcat_db` |
| G4 | **ADB** | "top 5 products this week" | Pre-approved SQL query |
| G5 | **File** | "Save product rankings as CSV" | Export via `export_adb_table` |
| G6 | **→ Instincts** | "store performance CBD" → "store performance Melbourne" | Domain pattern applied |
| G7 | **Export** | "Export yesterday's sales to CSV" | Direct CSV export |
| G8 | **Adhoc Dashboard** | "Track daily sales by store" | TDB: daily_sales (date, store, amount) |

---

## Phase 3: Adhoc App Build-Off

**Goal:** Build complete applications from scratch.

**Tests:** 18 (6 apps × 3 queries each)

| # | App | Storage | Features | Test Queries |
|---|-----|---------|----------|--------------|
| APP1 | **CRM** | TDB + VDB | Contacts, deals, search notes | "Create CRM", "Add contact", "Find contacts in healthcare" |
| APP2 | **Todo App** | TDB + Reminder | Tasks, priorities, deadlines | "Track my todos", "Add high-priority task", "Remind me tomorrow" |
| APP3 | **Knowledge Base** | VDB + File | Semantic search, categories | "Build knowledge base", "Save article", "Find articles about pricing" |
| APP4 | **Inventory** | TDB + Reminder | Products, stock, low-stock alerts | "Track inventory", "Add product", "Alert when stock < 10" |
| APP5 | **Expense Tracker** | TDB + ADB | Daily entry + monthly analysis | "Track expenses", "Log $50 lunch", "Show monthly spending by category" |
| APP6 | **Sales Dashboard** | ADB + MCP | Metrics, trends, rankings | "Show sales dashboard", "Compare this week vs last week" |

---

## Phase 4: Learning & Adaptation

**Goal:** Test agent learning systems.

**Tests:** 15

---

### Test Suite: Conversation → Instincts

| Test | Round 1 (Train) | Round 2 (Test) | Expected Pattern Learned |
|------|-----------------|----------------|-------------------------|
| I1 | "Create TDB table for users" | "Create TDB table for customers" | Same table structure pattern |
| I2 | "Query sales grouped by store" | "Query revenue grouped by region" | Same aggregation pattern |
| I3 | "Export query results to CSV" | "Save query results to Excel" | Export workflow pattern |
| I4 | "Search past conversations about pricing" | "Find previous discussions about costs" | Semantic search pattern |

**Verify:**
- [ ] Instincts created after Round 1
- [ ] Round 2 applies learned instinct
- [ ] Pattern recognition works across domains

---

### Test Suite: Conversation → Skill

| Test | Trigger Query | Expected Skill Load | Verification Query |
|------|--------------|---------------------|-------------------|
| S1 | "I need advanced DuckDB analytics" | `load_skill("analytics_with_duckdb")` | "Calculate moving average" |
| S2 | "Help me break down a complex project" | `load_skill("planning")` | "Estimate effort for X" |
| S3 | "Organize my calendar and reminders" | `load_skill("organization")` | "Set up recurring meeting" |
| S4 | "Combine multiple data sources" | `load_skill("synthesis")` | "Merge sales + traffic data" |

**Verify:**
- [ ] Skill loaded on-demand
- [ ] Follow-up queries use skill guidance
- [ ] Skill content affects tool choices

---

## Phase 5: Web Scraping Intelligence

**Goal:** Test web scraping tool selection.

**Tests:** 15

### Tool Selection Matrix

| Tool | Best For | When to Use | Example |
|------|----------|-------------|---------|
| **firecrawl_scrape** | Simple pages, blogs, articles | Single page, mostly static | "Summarize this blog post" |
| **firecrawl_crawl** | Multi-page discovery | Entire site, multiple URLs | "Crawl all product pages" |
| **playwright_scrape** | Dynamic/JS content | SPAs, interactive, auth needed | "Scrape data from React app" |

---

### Test Suite: Web Scraping Tool Selection

| # | Test Case | Query | Expected Tool | Reasoning |
|---|-----------|-------|---------------|-----------|
| W1 | **Simple blog** | "Summarize https://blog.example.com/post" | `firecrawl_scrape` | Static content, single page |
| W2 | **Article scraping** | "Extract key points from this article" | `firecrawl_scrape` | Text extraction focused |
| W3 | **Site crawl** | "Get all blog posts from this site" | `firecrawl_crawl` | Multi-page discovery |
| W4 | **Product catalog** | "Scrape all products from https://store.com" | `firecrawl_crawl` | Multiple product pages |
| W5 | **Dynamic SPA** | "Scrape data from React dashboard" | `playwright_scrape` | JavaScript rendering |
| W6 | **Interactive site** | "Extract data requiring login/interaction" | `playwright_scrape` | Browser automation |
| W7 | **E-commerce** | "Get prices from https://shop.com (JS-heavy)" | `playwright_scrape` | Dynamic pricing |
| W8 | **Documentation** | "Scrape API docs from https://docs.example.com" | `firecrawl_crawl` | Structured multi-page |
| W9 | **News site** | "Extract article from news site (paywall)" | `playwright_scrape` | May need browser interaction |
| W10 | **Comparison shopping** | "Compare prices across 3 sites" | Mix based on site type | Adaptive selection |

---

### Advanced Switching Scenarios

| # | Scenario | Expected Flow |
|---|----------|---------------|
| WS1 | **Try Firecrawl → Fails → Switch to Playwright** | Firecrawl returns empty → Retry with Playwright |
| WS2 | **Single URL → Discover More Pages** | Start with `firecrawl_scrape` → Agent suggests `firecrawl_crawl` |
| WS3 | **Static vs Dynamic Detection** | Agent analyzes URL/site → Picks appropriate tool |
| WS4 | **Cost/Performance Optimization** | Simple sites → Firecrawl (faster/cheaper), Complex → Playwright |
| WS5 | **Content Type Detection** | Blog/article → Firecrawl, Dashboard/SPA → Playwright |

---

## Phase 6: Middleware Testing

**Goal:** Test all middleware components.

**Tests:** 40

### Middleware Overview

| Middleware | Purpose | Status | Test Coverage |
|------------|---------|--------|---------------|
| **ThreadContextMiddleware** | Propagates ContextVars to tools | ✅ Always on | M1 (4 tests) |
| **StatusUpdateMiddleware** | "Thinking..." status to channels | ✅ Optional | M2 (4 tests) |
| **TodoListMiddleware** | Agent execution planning | ✅ Optional | M3 (4 tests) |
| **ToolRetryMiddleware** | Retry failed tool calls | ✅ Enabled | M4 (4 tests) |
| **ModelRetryMiddleware** | Retry failed LLM calls | ✅ Enabled | M5 (4 tests) |
| **ModelCallLimitMiddleware** | Cap model calls | ✅ Enabled | M6 (4 tests) |
| **ToolCallLimitMiddleware** | Cap tool calls | ✅ Enabled | M7 (4 tests) |
| **ContextEditingMiddleware** | Token limit management | ❌ Disabled | M8 (4 tests, if enabled) |
| **HITLMiddleware** | Human-in-the-loop approval | ❌ Disabled | M9 (4 tests, if enabled) |

---

### Test Suite M1: ThreadContextMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|------|-------|-------------------|--------------|
| M1-1 | **Basic propagation** | "Create a TDB table" | TDB created in correct user directory | Check file path: `data/users/{user_id}/...` |
| M1-2 | **Multi-tool flow** | "Create table, insert data, query it" | All operations use same thread_id | All data in same user directory |
| M1-3 | **Concurrent requests** | Simultaneous requests from different users | No cross-contamination | User A data ≠ User B data |
| M1-4 | **ThreadPoolExecutor** | Complex query (agent uses parallel tools) | Context preserved across threads | Tools access correct user data |

---

### Test Suite M2: StatusUpdateMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| M2-1 | **Quick response** | "What's 2+2?" | No status update (too fast) | Response immediate |
| M2-2 | **Slow operation** | "Analyze last 6 months of sales" | Status: "Thinking..." | Status sent before response |
| M2-3 | **Multi-step** | "Research AI trends, write report, save to file" | Status updates per step | Multiple status updates |
| M2-4 | **Long-running query** | Complex ADB aggregation | Status during execution | User sees progress |

---

### Test Suite M3: TodoListMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|------|-------|-------------------|--------------|
| M3-1 | **Simple task** | "What's 2+2?" | No `write_todos` (too simple) | Direct answer |
| M3-2 | **Multi-step** | "Research, analyze, report, save" | `write_todos` called | 4 todos created |
| M3-3 | **User todos** | "Track my personal todos" | Uses TDB, not `write_todos` | `create_tdb_table` called |
| M3-4 | **Agent execution** | "Complex multi-tool operation" | `write_todos` for tracking | Execution steps shown |

---

### Test Suite M4: ToolRetryMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|------|-------|-------------------|--------------|
| M4-1 | **Network timeout** | Query external API that times out | Automatic retry (up to limit) | Success or clear error |
| M4-2 | **Transient error** | Web search with temporary failure | Retry succeeds | Eventual success |
| M4-3 | **Permanent error** | Invalid operation | Retries exhausted, proper error | Clear error message |
| M4-4 | **Retry limit** | Failing operation (3+ attempts) | Stops after configured limit | Doesn't loop forever |

---

### Test Suite M5: ModelRetryMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|------|-------|-------------------|--------------|
| M5-1 | **API timeout** | Long-running agent task | Retry on timeout | Success after retry |
| M5-2 | **Rate limit** | Quick successive requests | Backoff and retry | All requests complete |
| M5-3 | **Invalid response** | Malformed LLM output | Retry generation | Valid response |
| M5-4 | **Retry exhausted** | Persistent failure | Graceful error | User sees error, not crash |

---

### Test Suite M6: ModelCallLimitMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| M6-1 | **Under limit** | Simple query | Completes normally | No limit hit |
| M6-2 | **At limit** | Task requiring ~50 calls | Completes at limit | Stops at boundary |
| M6-3 | **Over limit** | Complex multi-step task | Stops at limit | Clear message |
| M6-4 | **Count tracking** | "Show me execution steps" | Agent aware of limit | Plans efficiently |

---

### Test Suite M7: ToolCallLimitMiddleware

| # | Test | Query | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| M7-1 | **Under limit** | Simple task | Completes normally | < 100 tools |
| M7-2 | **At limit** | Multi-step task | Completes at limit | ~100 tools |
| M7-3 | **Over limit** | Complex automation | Stops at limit | Graceful stop |
| M7-4 | **Tool efficiency** | Large data analysis | Agent uses fewer tools | Batches operations |

---

### Test Suite M8: ContextEditingMiddleware (DISABLED)

| # | Test | Query | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| M8-1 | **Current status** | N/A | Should be disabled | Check logs/settings |
| M8-2 | **Enable & test** | Enable middleware | Context edits when over limit | Tokens reduced |
| M8-3 | **Preserve recent** | Long conversation | Old messages edited | Recent context kept |
| M8-4 | **Preserve system** | Long chat + queries | System prompt preserved | Skills intact |

**Note:** This middleware is disabled by default. Tests only run if enabled.

---

### Test Suite M9: HITLMiddleware (DISABLED)

| # | Test | Query | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| M9-1 | **Current status** | N/A | Should be disabled | Check settings |
| M9-2 | **Enable & test** | "Delete all data" | Asks for approval | Approval prompt |
| M9-3 | **Approve** | User approves | Action executes | Operation completes |
| M9-4 | **Deny** | User denies | Action cancelled | Graceful denial |

**Note:** This middleware is disabled by default. Tests only run if enabled.

---

## Phase 7: Streaming Responses

**Goal:** Test SSE streaming functionality.

**Tests:** 5

| # | Test | Query | Expected |
|---|------|-------|----------|
| SR1 | **Basic streaming** | Simple query with `stream: true` | Multiple chunks |
| SR2 | **Long response** | Complex explanation | Many chunks |
| SR3 | **Tool calls in stream** | Query that uses tools | Status updates in stream |
| SR4 | **Error in stream** | Invalid operation | Error in chunk |
| SR5 | **Chunk ordering** | Fast streaming | Correct order |

---

## Phase 8: Error Handling & Edge Cases

**Goal:** Test graceful error handling.

**Tests:** 8

| # | Test | Query | Expected |
|---|------|-------|----------|
| EH1 | **Invalid table** | Query non-existent TDB table | Clear error |
| EH2 | **Invalid SQL** | Malformed ADB query | SQL error message |
| EH3 | **File not found** | Read non-existent file | "File not found" |
| EH4 | **Invalid memory key** | Get memory with wrong key | Graceful handle |
| EH5 | **Tool timeout** | Operation that times out | Retry or timeout error |
| EH6 | **Permission denied** | Access another user's data | Permission error |
| EH7 | **Invalid parameters** | Tool with bad params | Parameter error |
| EH8 | **Network failure** | Web search with network down | Retry or fail gracefully |

---

## Phase 9: Multi-Turn Conversations

**Goal:** Test conversation state management.

**Tests:** 5

| # | Test | Flow | Expected |
|---|------|------|----------|
| MT1 | **Context retention** | Q1: "My name is X" → Q2: "What's my name?" | Remembers |
| MT2 | **State persistence** | Create table → Query in next message | Table exists |
| MT3 | **Long conversation** | 50+ message conversation | Works |
| MT4 | **Memory editing** | Exceed context, check old memory | Old memories preserved |
| MT5 | **Conversation search** | "What did we discuss about X?" | Searches history |

---

## Phase 10: Channel Differences

**Goal:** Test HTTP vs Telegram behavior.

**Tests:** 4

| # | Test | HTTP | Telegram | Expected |
|---|----------|------|----------|----------|
| CD1 | **Formatting** | Markdown | Telegram markdown | Appropriate for channel |
| CD2 | **Streaming** | SSE | Typing indicator | Channel-appropriate |
| CD3 | **Files** | JSON output | File upload | Both work |
| CD4 | **Buttons** | None | Inline keyboards | Telegram has buttons |

---

## Phase 11: Checkpointer/State Management

**Goal:** Test conversation persistence.

**Tests:** 4

| # | Test | Query | Expected |
|---|------|-------|----------|
| CP1 | **State save** | Create data, restart, query | Data persists |
| CP2 | **Thread isolation** | Two conversations same user | Separate states |
| CP3 | **Checkpoint blob** | Check saved state in DB | Blob exists |
| CP4 | **Resume** | Long break, return to chat | Context restored |

---

## Phase 12: Shared Scope

**Goal:** Test organization-wide data.

**Tests:** 4

| # | Test | Query | Expected |
|---|------|-------|----------|
| SH1 | **Create shared** | `scope="shared"` in create_adb_table | All users see it |
| SH2 | **Shared vs private** | Create both, check isolation | Correct separation |
| SH3 | **Cross-user query** | User A queries shared table | Access works |
| SH4 | **Update shared** | User B updates shared table | User A sees changes |

---

## Phase 13: Security Testing

**Goal:** Test security boundaries.

**Tests:** 6

| # | Test | Query | Expected |
|---|------|-------|----------|
| SEC1 | **SQL injection** | `"; DROP TABLE--` in query | Sanitized/blocked |
| SEC2 | **Path traversal** | `"../../../etc/passwd"` in file path | Blocked |
| SEC3 | **XSS in content** | Save `<script>alert(1)</script>` | Escaped or sanitized |
| SEC4 | **Prompt injection** | "Ignore previous instructions" | Ignored |
| SEC5 | **User isolation** | User A queries User B's data | Permission denied |
| SEC6 | **Allowlist** | Unauthorized user tries to use | Blocked |

---

## Phase 14: Concurrent Access

**Goal:** test concurrent user access.

**Tests:** 3

| # | Test | Scenario | Expected |
|---|------|----------|----------|
| CONC1 | **Same resource** | Two users update same shared table | Both succeed or last write wins |
| CONC2 | **Same user concurrent** | Parallel requests from same user | No data corruption |
| CONC3 | **Locking** | Long operation + query | Query waits or gets snapshot |

---

## Phase 15: Performance Benchmarks

**Goal:** Establish performance baselines.

**Tests:** 5

| # | Metric | Test | Target |
|---|------|------|--------|
| PERF1 | **Simple query** | "What's 2+2?" | < 2s |
| PERF2 | **Complex query** | ADB aggregation | < 10s |
| PERF3 | **Tool latency** | Single tool call | < 1s |
| PERF4 | **Streaming first chunk** | Time to first chunk | < 1s |
| PERF5 | **Memory usage** | Long conversation | No leak |

---

## Test Execution Guide

### Prerequisites

1. **Agent Running:**
   ```bash
   cd /Users/eddy/Developer/Langgraph/ken
   uv run executive_assistant
   ```

2. **HTTP Endpoint Available:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status":"healthy",...}
   ```

3. **Test Database Clean:**
   ```bash
   # Optional: Start with fresh state
   rm -rf data/users/test_*
   ```

---

### Execution Options

#### Option A: Tiered Approach ⭐ RECOMMENDED

**Tier 1: Critical** (108 tests, 3-4 hours)
- Core features (30)
- Middlewares (40)
- Error handling (8)
- Security (6)
- Multi-turn (5)
- Streaming (5)
- Persona basics (14 - one per persona)

**Tier 2: Important** (62 tests, 2 hours)
- Learning & Skills (15)
- Adhoc Apps (18)
- Web Scraping (15)
- Checkpointer (4)
- Shared Scope (4)
- Channel differences (4)
- Performance (2)

**Tier 3: Nice-to-Have** (42 tests, 1-2 hours)
- Persona advanced (32 - deep dives per persona)
- Concurrent access (3)
- Performance (3)
- Advanced edge cases (6)

---

#### Option B: Feature-Based

Run all tests for a specific feature category:

```bash
# Example: Run all middleware tests (40 tests)
# Execute M1-M9 test suites
```

---

#### Option C: Smoke Test

Quick validation (top 20 tests, 30 min):

1. Onboarding (4 tests - 1.1-1.4)
2. Memory (3 tests - 2.1-2.3)
3. TDB (1 test - E3)
4. ADB (1 test - E4)
5. Tool selection (1 test - W1)
6. ThreadContext (1 test - M1-1)
7. Error handling (2 tests - EH1, EH2)
8. Security (2 tests - SEC1, SEC5)
9. Multi-turn (1 test - MT1)
10. Streaming (1 test - SR1)
11. Performance (3 tests - PERF1-PERF3)

---

### Test Reporting Format

For each test, document:

```markdown
## [Test ID] Test Name

**Date:** YYYY-MM-DD
**Tester:** [Name]
**User ID:** test_persona_number

### Query
```
[Actual query sent]
```

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happened]

### Tool Calls
- [ ] Tool1: expected
- [ ] Tool2: not called (BUG)

### Verification
- [ ] Pass
- [ ] Fail

### Issues
[Description of any issues]

### Screenshots/Logs
[Attach evidence]
```

---

## Scoring Matrix

### Overall Scoring

| Tier | Tests | Pass Threshold | Status |
|------|-------|---------------|--------|
| **Tier 1: Critical** | 108 | 100% | BLOCKER if failed |
| **Tier 2: Important** | 62 | 90% | WARN if < 90% |
| **Tier 3: Nice-to-Have** | 42 | 80% | INFO if < 80% |
| **TOTAL** | 212 | 95% | Production readiness |

---

### Feature Category Scores

| Category | Tests | Weight | Pass % | Status |
|----------|-------|--------|--------|--------|
| Core Features | 30 | 15% | ___ | ___ |
| Middlewares | 40 | 20% | ___ | ___ |
| Error Handling | 8 | 5% | ___ | ___ |
| Security | 6 | 10% | ___ | ___ |
| Multi-turn | 5 | 3% | ___ | ___ |
| Streaming | 5 | 3% | ___ | ___ |
| Learning & Skills | 15 | 5% | ___ | ___ |
| Adhoc Apps | 18 | 8% | ___ | ___ |
| Web Scraping | 15 | 8% | ___ | ___ |
| Checkpointer | 4 | 2% | ___ | ___ |
| Shared Scope | 4 | 2% | ___ | ___ |
| Channel Differences | 4 | 2% | ___ | ___ |
| Concurrent Access | 3 | 1% | ___ | ___ |
| Performance | 5 | 2% | ___ | ___ |
| Persona Deep Dives | 46 | 14% | ___ | ___ |

---

### Persona Scores

| Persona | Tests | Pass % | Notes |
|---------|-------|--------|-------|
| Executive | 14 | ___ | |
| Analyst | 15 | ___ | |
| Developer | 16 | ___ | |
| Gong Cha | 8 | ___ | |

---

## Phase 16: Check-in Monitoring

**Feature:** Proactive journal and goals monitoring with intelligent insights

**What it does:**
- Periodically analyzes journal entries and goals
- Detects patterns, inactivity, and misalignment
- Messages user only when something needs attention
- Stays silent if everything is on track

**Tools tested:**
- `checkin_enable()` - Enable check-in
- `checkin_disable()` - Disable check-in
- `checkin_show()` - Show configuration
- `checkin_schedule()` - Set frequency
- `checkin_hours()` - Set active hours
- `checkin_test()` - Run test check-in

### Test Cases

| # | Test | Expected | Pass/Fail |
|---|------|----------|-----------|
| 1 | Enable check-in with defaults | Check-in enabled, 30m/24h | ___ |
| 2 | Enable check-in with custom settings | Custom settings saved | ___ |
| 3 | Show check-in configuration | Current config displayed | ___ |
| 4 | Change frequency to 1h | Schedule updated | ___ |
| 5 | Set active hours to 9-18 | Hours updated | ___ |
| 6 | Disable check-in | Check-in disabled | ___ |
| 7 | Run test check-in (no journal) | Returns CHECKIN_OK | ___ |
| 8 | Run test check-in (with journal) | Analyzes entries | ___ |
| 9 | Run test check-in (with goals) | Analyzes goals | ___ |
| 10 | Run test check-in (both) | Combined analysis | ___ |

### Success Criteria

- **Enable/Disable:** Config persists across restarts
- **Configuration:** All settings saved and retrieved correctly
- **Analysis:** Correctly identifies patterns and issues
- **Filtering:** Returns CHECKIN_OK when nothing important
- **Integration:** Works with existing journal and goals systems

### Test Script

```bash
#!/bin/bash
# Phase 16: Check-in Monitoring Tests

USER_ID="test_checkin_01"
PASS=0
FAIL=0

test_count=0

run_test() {
  local test_name=$1
  local expected=$2
  local test_command=$3

  test_count=$((test_count + 1))
  echo "Test $test_count: $test_name"

  response=$(eval $test_command)

  if echo "$response" | grep -q "$expected"; then
    echo "  ✅ PASS"
    PASS=$((PASS + 1))
  else
    echo "  ❌ FAIL"
    echo "  Expected: $expected"
    echo "  Got: $response"
    FAIL=$((FAIL + 1))
  fi
}

# Test 1: Enable check-in
run_test \
  "Enable check-in" \
  "Check-in enabled" \
  "test_agent '$USER_ID' 'checkin_enable()'"

# Test 2: Show configuration
run_test \
  "Show configuration" \
  "every 30m" \
  "test_agent '$USER_ID' 'checkin_show()'"

# Test 3: Test check-in (no data)
run_test \
  "Test check-in (no data)" \
  "CHECKIN_OK" \
  "test_agent '$USER_ID' 'checkin_test()'"

# Test 4: Create journal entries and test
test_agent '$USER_ID' 'Journal: Working on API feature'
test_agent '$USER_ID' 'Journal: Fixed authentication bug'

run_test \
  "Test check-in (with data)" \
  "." \
  "test_agent '$USER_ID' 'checkin_test()'"

# Test 5: Disable check-in
run_test \
  "Disable check-in" \
  "Check-in disabled" \
  "test_agent '$USER_ID' 'checkin_disable()'"

echo ""
echo "Phase 16 Results: $PASS passed, $FAIL failed"
```

---

## Phase 17: Learning Patterns

**Feature:** Progressive intelligence through three learning patterns

**What it does:**
- **Teach → Verify**: Two-way learning where Ken confirms understanding before saving patterns
- **Reflect → Improve**: Self-reflection after tasks to learn from mistakes and improve
- **Predict → Prepare**: Anticipatory assistance based on behavioral patterns

**Tools tested:**
- `learning_stats()` - Show comprehensive learning statistics
- `verify_preferences()` - Show pending verifications
- `confirm_learning()` - Confirm a learning verification
- `show_reflections()` - Show recent reflections and improvements
- `create_learning_reflection()` - Create a learning reflection after a task
- `show_patterns()` - Show learned patterns for proactive assistance
- `learn_pattern()` - Manually teach Ken a pattern

### Test Cases

#### Pattern 1: Teach → Verify (4 tests)

| # | Test | Query | Expected | Pass/Fail |
|---|------|-------|----------|-----------|
| 1 | Show learning stats | `learning_stats()` | Shows TEACH → VERIFY stats | ___ |
| 2 | Check pending verifications | `verify_preferences()` | Shows pending items or "No pending" | ___ |
| 3 | Confirm learning | `confirm_learning(id, "yes")` | Verification confirmed | ___ |
| 4 | Reject learning | `confirm_learning(id, "no")` | Verification rejected | ___ |

**Success Criteria:**
- Learning stats display all three patterns
- Verifications created and stored in learning.db
- Confirmation/rejection updates status correctly
- Acceptance rate calculated accurately

#### Pattern 2: Reflect → Improve (5 tests)

| # | Test | Query | Expected | Pass/Fail |
|---|------|-------|----------|-----------|
| 5 | Show reflections | `show_reflections()` | Shows recent reflections | ___ |
| 6 | Create reflection (task success) | `create_learning_reflection("analysis", "Quick processing", "")` | Reflection created | ___ |
| 7 | Create reflection (with improvement) | `create_learning_reflection("coding", "Good progress", "Add more tests")` | Suggestions generated | ___ |
| 8 | Create reflection (with corrections) | Manual correction input | Correction pattern learned | ___ |
| 9 | Implement improvement | `implement_improvement(suggestion_id)` | Improvement marked implemented | ___ |

**Success Criteria:**
- Reflections stored in reflections.db
- Improvement suggestions generated automatically
- User corrections captured and analyzed
- Implementation tracking works correctly

#### Pattern 3: Predict → Prepare (4 tests)

| # | Test | Query | Expected | Pass/Fail |
|---|------|-------|----------|-----------|
| 10 | Show patterns | `show_patterns()` | Shows detected patterns | ___ |
| 11 | Learn pattern manually | `learn_pattern("time", "Monday 9am sales review", "Monday 9am")` | Pattern stored | ___ |
| 12 | Learn task pattern | `learn_pattern("task", "Sales report query", "sales report")` | Pattern stored | ___ |
| 13 | Show prepared data | `show_prepared_data()` | Shows prepared items or "No prepared data" | ___ |

**Success Criteria:**
- Patterns detected and stored in predictions.db
- Confidence scoring works correctly
- Context matching identifies triggers
- Preparation offers made at high confidence

#### Integration Tests (2 tests)

| # | Test | Scenario | Expected | Pass/Fail |
|---|------|----------|----------|-----------|
| 14 | Multi-pattern workflow | Complete task → Reflect → Verify | All patterns engaged | ___ |
| 15 | Stats aggregation | All three patterns active | Comprehensive stats | ___ |

**Success Criteria:**
- All three patterns work together
- Stats aggregate across all patterns
- No conflicts between patterns
- Learning databases isolated correctly

### Test Script

```bash
#!/bin/bash
# Phase 17: Learning Patterns Tests

USER_ID="test_learning_01"
PASS=0
FAIL=0

test_count=0

run_test() {
  local test_name=$1
  local expected=$2
  local test_command=$3

  test_count=$((test_count + 1))
  echo "Test $test_count: $test_name"

  response=$(eval $test_command)

  if echo "$response" | grep -q "$expected"; then
    echo "  ✅ PASS"
    PASS=$((PASS + 1))
  else
    echo "  ❌ FAIL"
    echo "  Expected: $expected"
    echo "  Got: $response"
    FAIL=$((FAIL + 1))
  fi
}

# Test 1: Show learning stats
run_test \
  "Show learning stats" \
  "TEACH → VERIFY" \
  "test_agent '$USER_ID' 'learning_stats()'"

# Test 2: Check pending verifications
run_test \
  "Check pending verifications" \
  "Pending Verifications" \
  "test_agent '$USER_ID' 'verify_preferences()'"

# Test 3: Show reflections
run_test \
  "Show reflections" \
  "Learning Progress" \
  "test_agent '$USER_ID' 'show_reflections()'"

# Test 4: Create learning reflection
run_test \
  "Create learning reflection" \
  "Reflection saved" \
  "test_agent '$USER_ID' 'create_learning_reflection(\"analysis\", \"Quick data processing\", \"Would be faster with caching\")'"

# Test 5: Show patterns
run_test \
  "Show patterns" \
  "Learned Patterns" \
  "test_agent '$USER_ID' 'show_patterns()'"

# Test 6: Learn pattern manually
run_test \
  "Learn pattern manually" \
  "Pattern learned" \
  "test_agent '$USER_ID' 'learn_pattern(\"time\", \"Monday 9am sales review\", \"Monday 9am\", 0.8)'"

# Test 7: Check learning stats again
run_test \
  "Check learning stats updated" \
  "Patterns Detected: 1" \
  "test_agent '$USER_ID' 'learning_stats()'"

echo ""
echo "Phase 17 Results: $PASS passed, $FAIL failed"
```

### Success Criteria

**Teach → Verify:**
- [ ] Verifications created for learning events
- [ ] User can confirm/reject learning
- [ ] Acceptance rate tracked
- [ ] Bad instincts prevented

**Reflect → Improve:**
- [ ] Reflections created after tasks
- [ ] Improvement suggestions generated
- [ ] Corrections captured and analyzed
- [ ] Implementation tracking works

**Predict → Prepare:**
- [ ] Patterns detected from behavior
- [ ] Confidence scoring accurate
- [ ] Context matching works
- [ ] Proactive offers made appropriately

**Integration:**
- [ ] All three patterns coexist
- [ ] Stats aggregate correctly
- [ ] Databases isolated per user
- [ ] Tools registered and accessible

---

## Test Execution Checklist

### Pre-Test Setup
- [ ] Agent running on port 8000
- [ ] Health check passing
- [ ] Test database clean (optional)
- [ ] Log monitoring configured
- [ ] Test results document ready

### During Testing
- [ ] Document each test result
- [ ] Capture logs for failures
- [ ] Note unexpected behaviors
- [ ] Record response times

### Post-Test
- [ ] Calculate pass rates
- [ ] Document bugs/issues
- [ ] Generate summary report
- [ ] Create bug tickets for failures
- [ ] Update test plan if needed

---

## Known Limitations

### Not Implemented (Test Skipped)
1. **Scheduled Flows** - Not implemented, tests skipped
2. **Email/SMS Notifications** - Not implemented, tests skipped
3. **Webhooks** - Not implemented, tests skipped
4. **API Rate Limiting** - Not implemented, tests skipped

### Partially Implemented
1. **Image/Multimodal** - OCR only, no LLM vision
2. **Audit Logging** - Basic logging, no comprehensive audit trail
3. **GDPR Export** - Table export only, no all-user-data export
4. **GDPR Deletion** - `/reset` command, not full GDPR compliance

---

## Appendix

### A. Tool Reference

**Storage Tools:**
- `create_tdb_table`, `query_tdb`, `insert_tdb_table`, `update_tdb_table`
- `query_adb`, `import_adb_csv`, `export_adb_table`
- `create_vdb_collection`, `search_vdb`
- `write_file`, `read_file`
- `create_memory`, `get_memory_by_key`, `update_memory`

**Web Tools:**
- `firecrawl_scrape`, `firecrawl_crawl`, `playwright_scrape`
- `search_web`

**System Tools:**
- `load_skill`, `write_todos`
- `create_user_profile`, `mark_onboarding_complete`

**MCP Tools:**
- `run_select_query`, `list_databases`, `list_tables` (ClickHouse)

---

### B. Memory Types (4 Pillars)

1. **Profile** - User identity (role, name)
2. **Preference** - User preferences (style, format)
3. **Fact** - Objective information
4. **Constraint** - Limitations/rules

---

### C. Middleware Configuration

Edit `docker/config.yaml` to enable/disable middlewares:

```yaml
MIDDLEWARE_TODO_LIST_ENABLED: true
MIDDLEWARE_STATUS_UPDATE_ENABLED: true
MIDDLEWARE_CONTEXT_EDITING_ENABLED: false
MIDDLEWARE_HITL_ENABLED: false
MIDDLEWARE_MODEL_CALL_LIMIT: 50
MIDDLEWARE_TOOL_CALL_LIMIT: 100
MIDDLEWARE_TOOL_RETRY_ENABLED: true
MIDDLEWARE_MODEL_RETRY_ENABLED: true
```

---

**Document Version:** 1.0
**Last Modified:** 2025-02-05
**Maintained By:** QA Team
