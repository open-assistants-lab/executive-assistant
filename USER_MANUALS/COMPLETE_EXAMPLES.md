# Complete Real-World Examples

This guide shows you complete workflows using Ken Executive Assistant. These examples demonstrate how to accomplish real tasks.

---

## Example 1: Daily Work Tracking & Timesheets

### Scenario: You're a developer who needs to track time for billing

**Step 1: Log your work throughout the day**
```
You: I worked on the user authentication feature for 3 hours
Ken: ✅ Logged: "Worked on user authentication feature" (3 hours)

You: Fixed 2 bugs in the API, took 1.5 hours
Ken: ✅ Logged: "Fixed 2 API bugs" (1.5 hours)

You: Database optimization for 2 hours
Ken: ✅ Logged: "Database optimization" (2 hours)
```

**Step 2: Generate weekly timesheet**
```
You: Create a timesheet for this week
Ken: ✅ Weekly Timesheet (Jan 15-19):
     ┌────────────────────────────────┬───────┐
     │ Day                            │ Hours │
     ├────────────────────────────────┼───────┤
     │ Mon: User auth, bugfixes       │ 4.5h  │
     │ Tue: API integration           │ 6.0h  │
     │ Wed: Database optimization     │ 5.5h  │
     │ Thu: Code review, testing      │ 7.0h  │
     │ Fri: Documentation, deployment │ 5.0h  │
     ├────────────────────────────────┼───────┤
     │ Total                          │ 28.0h │
     └────────────────────────────────┴───────┘

     💾 Saved to: timesheets/week_2024-01-15.csv
```

**Step 3: Query specific periods**
```
You: How many hours did I spend on the authentication feature?
Ken: Authentication feature: 12.5 hours total
     • Mon: 3h (initial implementation)
     • Tue: 4h (OAuth integration)
     • Wed: 2.5h (testing, bugfixes)
     • Thu: 3h (documentation)
```

---

## Example 2: Sales Analytics from CSV

### Scenario: You have a large sales CSV and need insights

**Step 1: Upload the file**
```
You: I have sales_data.csv with 500K rows. Upload it
Ken: ✅ Analyzing file...
     Detected: 500,234 rows, 15 columns
     Columns: date, product, category, quantity, revenue, customer, region

     Importing to Analytics Database...
     ✅ Imported 500,234 rows in 2.3 seconds
```

**Step 2: Get top-level insights**
```
You: Show me key metrics for this quarter
Ken: 📊 Q1 Sales Summary:
     • Total Revenue: $2,345,678 (+15% vs Q4)
     • Total Orders: 45,234
     • Avg Order Value: $51.82
     • Top Product: Widget Pro ($234,567)
     • Best Region: West Coast ($890,123)
```

**Step 3: Drill down with specific questions**
```
You: What are the top 10 products by revenue?
Ken: Top 10 Products by Revenue:
     ┌────────────────────┬──────────────┬──────────┐
     │ Product            │ Revenue      │ Growth   │
     ├────────────────────┼──────────────┼──────────┤
     │ 1. Widget Pro      │ $234,567     │ +23%     │
     │ 2. Premium Pack    │ $198,234     │ +18%     │
     │ 3. Enterprise Suite│ $176,543     │ +31%     │
     │ 4. Basic Widget    │ $154,321     │ -5%      │
     │ 5. Custom Bundle   │ $143,210     │ +12%     │
     └────────────────────┴──────────────┴──────────┘

     💡 Insight: Premium products driving growth
```

**Step 4: Create visualizations**
```
You: Create a monthly trend chart and save to reports/
Ken: ✅ Running analytics...
     Generated 3 visualizations:
     • monthly_trend.png (line chart)
     • category_breakdown.png (pie chart)
     • regional_comparison.png (bar chart)

     📁 Saved to: reports/q1_sales_analysis/
```

---

## Example 3: Knowledge Base for Team Decisions

### Scenario: Your team makes decisions and needs to reference them later

**Step 1: Store a decision with context**
```
You: Save this to knowledge base:

    **Date:** January 15, 2024
    **Attendees:** John, Sarah, Mike
    **Topic:** Database migration strategy

    **Decision:** Migrate from MySQL to PostgreSQL in Q2
    **Reasoning:**
    - Better JSON support for our document storage needs
    - Superior performance for complex joins
    - Team already has PostgreSQL experience
    - Migration tools are mature

    **Timeline:**
    - Feb: Set up PostgreSQL replica
    - Mar: Dual-write to both databases
    - Apr: Cutover to PostgreSQL
    - May: Decommission MySQL

    **Risks:** Data migration complexity, downtime during cutover

Ken: ✅ Added to knowledge base (collection: decisions)
     Document ID: decision_001
     You can search this with: /vdb search decisions "database migration"
```

**Step 2: Search for related decisions**
```
You: What did we decide about the database?
Ken: Found 2 relevant decisions:

     1. "Database Migration Strategy" (Jan 15)
        "Decision: Migrate from MySQL to PostgreSQL in Q2"
        Reasoning: "Better JSON support, superior performance..."
        Similarity: 0.96

     2. "Database Backup Strategy" (Jan 10)
        "Decision: Keep MySQL backup for 30 days post-migration"
        Similarity: 0.89

     📊 Timeline from decision:
     Feb: Set up PostgreSQL replica
     Mar: Dual-write phase
     Apr: Cutover
```

**Step 3: Update a decision**
```
You: Update the database migration decision:
    Add: "Budget approved: $10,000 for migration tools"

Ken: ✅ Updated document: decision_001
     Added: "Budget approved: $10,000 for migration tools"
     Previous version archived
```

---

## Example 4: Automated Daily Report

### Scenario: You need a daily summary of work activities

**Step 1: Ask for today's summary**
```
You: What did I work on today?
Ken: Today's Activity (3 entries):
     • 9:00 AM - Created sales dashboard schema (2h)
     • 11:30 AM - API integration testing (1.5h)
     • 2:00 PM - Bugfix: authentication timeout (2.5h)

     Total: 6 hours
```

**Step 2: Create a formatted report**
```
You: Generate a daily report in markdown format
Ken: ✅ Daily Report - January 15, 2024

     ## Work Completed
     - Created sales dashboard schema (2h)
     - API integration testing (1.5h)
     - Fixed authentication timeout bug (2.5h)

     ## Key Achievements
     - Dashboard schema supports real-time updates
     - API tests passing: 45/47 (96%)
     - Authentication bug resolved (root cause: token expiry)

     ## Tomorrow's Plan
     - Complete remaining 2 API tests
     - Start dashboard frontend
     - Code review for authentication fix

     💾 Saved to: reports/daily/2024-01-15.md
```

**Step 3: Email the report**
```
You: Email this report to manager@example.com
Ken: ✅ Draft email created:
     To: manager@example.com
     Subject: Daily Report - January 15, 2024
     Body: [Report content attached]

     📧 Saved to: drafts/email_manager_2024-01-15.eml
     (Send via your email client)
```

---

## Example 5: Project Planning & Goal Tracking

### Scenario: You're managing a project with milestones

**Step 1: Create a goal**
```
You: Create a goal: Launch sales dashboard by March 1st
Ken: ✅ Created goal: "Launch sales dashboard"
     Details:
     • Target date: March 1, 2024
     • Duration: 6 weeks
     • Category: medium_term

     Set priority (1-10) and importance (1-10)?
```

**Step 2: Define sub-goals**
```
You: Create sub-goals:
    1. Complete backend API by Feb 1
    2. Finish frontend by Feb 15
    3. Testing and bugfixes by Feb 25

Ken: ✅ Created 3 sub-goals:
     • "Complete backend API" (due: Feb 1)
     • "Finish frontend" (due: Feb 15)
     • "Testing and bugfixes" (due: Feb 25)

     All linked to parent: "Launch sales dashboard"
```

**Step 3: Track progress**
```
You: Update: Backend API is 50% complete
Ken: ✅ Progress updated: "Complete backend API" → 50%

     📊 Goal Status:
     ├─ Launch sales dashboard (0%)
     │  ├─ Complete backend API (50%) ✅ on track
     │  ├─ Finish frontend (0%) ⚠️ should start soon
     │  └─ Testing and bugfixes (0%)
```

**Step 4: Get progress alerts**
```
You: Check which goals need attention
Ken: ⚠️ Goals needing attention:

     1. "Finish frontend" - Due in 5 days
        Status: Not started
        Action: Start frontend development this week

     2. "Testing and bugfixes" - Due in 12 days
        Status: Blocked (frontend not complete)
        Action: Complete frontend first
```

---

## Example 6: Data Pipeline Automation

### Scenario: Build a daily data processing workflow

**Step 1: Define the workflow**
```
You: Create a daily workflow that:
    1. Fetches sales data from PostgreSQL
    2. Joins with customer data from CSV
    3. Calculates customer lifetime value
    4. Identifies high-value customers (LTV > $10,000)
    5. Stores results for easy access

Ken: ✅ Created scheduled flow: "daily_customer_ltv"
     Schedule: Daily at 6:00 AM
     Workflow:
     1. [PostgreSQL] Fetch yesterday's transactions
     2. [CSV] Load customer profiles
     3. [Python] Calculate LTV for each customer
     4. [Filter] Identify high-value (LTV > $10K)
     5. [TDB] Store to high_value_customers table

     📊 Next run: Tomorrow 6:00 AM
```

**Step 2: Test the workflow**
```
You: Run the daily_customer_ltv workflow now
Ken: 🔄 Running workflow: daily_customer_ltv

     Step 1: [PostgreSQL] Retrieved 1,234 transactions
     Step 2: [CSV] Loaded 856 customer profiles
     Step 3: [Python] Calculated LTV...
             → High-value customers: 127 (LTV > $10K)
             → Mid-tier customers: 342 ($5K-$10K)
             → Standard customers: 387 (< $5K)
     Step 4: [TDB] Stored to: high_value_customers (127 rows)

     ✅ Workflow complete (12.3 seconds)
```

**Step 3: Query the results**
```
You: Show me top 10 high-value customers
Ken: Top 10 High-Value Customers:
     ┌──────────────────┬─────────────┬────────┐
     │ Customer         │ LTV         │ Orders │
     ├──────────────────┼─────────────┼────────┤
     │ Acme Corp        │ $45,234     │ 234    │
     │ TechStart Inc    │ $38,912     │ 189    │
     │ GlobalTrade Ltd  │ $34,567     │ 156    │
     │ ...              │ ...         │ ...    │
     └──────────────────┴─────────────┴────────┘

     💡 Total high-value customers: 127
     💰 Combined LTV: $2,345,678
```

---

## Example 7: Meeting Assistant

### Scenario: Prepare for and summarize meetings

**Step 1: Pre-meeting research**
```
You: I have a meeting about the sales dashboard in 1 hour.
    Find all related decisions and progress.

Ken: 🔍 Found relevant information:

     **Decisions:**
     • "Dashboard Requirements" (Jan 10)
       "Must show real-time sales data, support drill-down"

     • "Dashboard Tech Stack" (Jan 12)
       "Frontend: React, Backend: FastAPI, Database: ClickHouse"

     **Progress:**
     • Created dashboard schema (Jan 15)
     • API integration: 96% complete (Jan 16)
     • Authentication bug fixed (Jan 17)

     **Current Status:**
     Backend: 50% complete
     Frontend: Not started
     Due: March 1, 2024 (6 weeks remaining)

     ⚠️ Risks: Frontend not started, need to begin soon
```

**Step 2: During the meeting (take notes)**
```
You: Take notes:

    **Sales Dashboard Meeting - Jan 18**
    Attendees: John, Sarah, Mike, Lisa

    **Discussion:**
    - Real-time updates using WebSockets
    - Drill-down feature needs more filters
    - Mobile responsive design required

    **Decisions:**
    1. Use WebSocket for real-time updates
    2. Add 5 more filters to drill-down
    3. Mobile-first design approach

    **Action Items:**
    - John: Implement WebSocket (due: Jan 25)
    - Sarah: Design mobile layouts (due: Jan 22)
    - Mike: Add filter options (due: Jan 24)

Ken: ✅ Meeting notes saved
     Document ID: meeting_2024-01-18
     Action items tracked in goals
```

**Step 3: Post-meeting summary**
```
You: Email meeting summary to all attendees
Ken: ✅ Draft email created:

     To: john@example.com, sarah@example.com, mike@example.com, lisa@example.com
     Subject: Meeting Summary: Sales Dashboard (Jan 18)

     **Decisions Made:**
     • Use WebSocket for real-time updates
     • Add 5 more filters to drill-down feature
     • Mobile-first design approach

     **Action Items:**
     • John: Implement WebSocket (due: Jan 25)
     • Sarah: Design mobile layouts (due: Jan 22)
     • Mike: Add filter options (due: Jan 24)

     **Next Meeting:** Jan 25, 2024

     📧 Saved to: drafts/meeting_summary_2024-01-18.eml
```

---

## Example 8: Research Helper

### Scenario: Research a topic and compile findings

**Step 1: Start research**
```
You: I need to research the best database for time-series data.
    Create a research document.

Ken: ✅ Created research document: time_series_database_research
     Outline:
     1. Requirements
     2. Options being considered
     3. Comparison criteria
     4. Recommendations
```

**Step 2: Add findings**
```
You: Add to research document:

    **Requirements:**
    - Handle 1M+ writes per second
    - Sub-second query response
    - Automatic data retention (drop old data)
    - Time-series specific functions (aggregations, downsampling)

    **Options:**
    1. TimescaleDB (PostgreSQL extension)
    2. InfluxDB (purpose-built)
    3. ClickHouse (analytics-focused)

Ken: ✅ Updated research document
     Added: Requirements section, Options section
```

**Step 3: Web search for more info**
```
You: Search the web for "TimescaleDB vs InfluxDB performance benchmark 2024"
Ken: 🔍 Searching web...

     Found 3 relevant articles:

     1. "TimescaleDB vs InfluxDB 2024 Benchmark"
        • TimescaleDB: Better for complex queries
        • InfluxDB: Faster for simple time-series writes
        • Source: timescale.com/blog

     2. "ClickHouse for Time-Series: When to Use"
        • Excellent for analytics workloads
        • Not ideal for high-frequency writes
        • Source: clickhouse.com/blog

     3. "Real-world Time-Series Database Comparison"
        • TimescaleDB wins on SQL compatibility
        • InfluxDB wins on write performance
        • Source: db-engines.com

     💾 Saved search results to research document
```

**Step 4: Compile final recommendation**
```
You: Generate a recommendation document
Ken: ✅ Recommendation Document: Time-Series Database Choice

     **Executive Summary:**
     Recommendation: TimescaleDB for our use case

     **Why TimescaleDB:**
     ✅ SQL compatibility (team already knows PostgreSQL)
     ✅ Handles our write volume (1M/sec benchmark: 1.2M/sec)
     ✅ Complex query support (joins with relational data)
     ✅ Automatic retention policies (drop old data)

     **Trade-offs:**
     ⚠️ Slightly slower writes than InfluxDB (but sufficient)
     ⚠️ More storage overhead (acceptable)

     **Implementation Plan:**
     1. Install TimescaleDB extension
     2. Migrate existing PostgreSQL data
     3. Set up retention policies (keep 90 days raw, 1 year aggregated)
     4. Benchmark with production load

     💾 Saved to: research/time_series_database_recommendation.md
```

---

## 💡 Key Patterns from These Examples

### Pattern 1: Progressive Refinement
Start simple, add complexity as needed:
```
1. Simple: "Show me sales data"
2. Add filter: "Show me sales from January"
3. Add calculation: "Calculate month-over-month growth"
4. Add visualization: "Create a chart showing the trend"
```

### Pattern 2: Knowledge Accumulation
Build knowledge over time:
```
Day 1: Store decision
Day 7: Update with new info
Day 30: Search for related decisions
Day 90: Have comprehensive knowledge base
```

### Pattern 3: Automation
Repeat tasks become automated:
```
Week 1: Manual daily report (ask Ken to generate)
Week 2: Ken learns the format
Week 3: Create scheduled workflow
Week 4+: Reports arrive automatically at 9 AM
```

### Pattern 4: Context Awareness
Ken uses all context sources:
```
• Journal: What you did (activity log)
• Memory: What you said (facts, decisions)
• Instincts: How you like it (preferences)
• Goals: What you're working toward (objectives)
```

---

## 🎓 Tips for Your Own Workflows

1. **Start with natural language** - Don't worry about commands initially
2. **Store important decisions** - Build a knowledge base over time
3. **Let Ken learn your preferences** - Patterns become skills
4. **Use structured data for analytics** - TDB for structured, VDB for semantic
5. **Automate repetitive tasks** - Scheduled workflows save time
6. **Review progress regularly** - Goals and journal keep you on track

---

**Need more?**
- See [GETTING_STARTED.md](GETTING_STARTED.md) for introduction
- See [ESSENTIAL_COMMANDS.md](ESSENTIAL_COMMANDS.md) for command reference
- See [MEMORY_AND_KNOWLEDGE.md](MEMORY_AND_KNOWLEDGE.md) for memory system details
