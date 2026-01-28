# Synthesis

Description: Learn how to combine multiple information sources, extract patterns, and create coherent summaries and insights.

Tags: core, infrastructure, synthesis, integration, summarization, insights

## Overview

This skill teaches **information synthesis**: combining multiple sources to create new understanding.

**The Synthesis Process:**
1. **Gather** - Collect information from multiple sources
2. **Extract** - Identify key points and patterns
3. **Integrate** - Combine and organize information
4. **Output** - Create coherent summary or insight

**Key Principle:** The whole is greater than the sum of parts. Synthesis creates new understanding.

---

## The Synthesis Framework

```
┌─────────────────────────────────────────────────────────────┐
│                    Synthesis Process                         │
│                                                               │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐ │
│  │ Gather  │───▶│ Extract  │───▶│ Integrate│───▶│Output│ │
│  └─────────┘    └──────────┘    └──────────┘    └──────┘ │
│       │              │               │            │      │
│       ▼              ▼               ▼            ▼      │
│  Multiple       Key Points      Organize      Summary   │
│  Sources        Patterns        Structure     Insight   │
│  TDB/VDB/Files    Themes          Connect       Report    │
│  Search/Read    Commonalities   Prioritize    Action    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Gather Multiple Sources

**Gather information from diverse sources.**

### Source Types

**Structured Data (TDB):**
```python
# Query structured data
timesheets = query_tdb("SELECT * FROM timesheets WHERE date >= '2025-01-01'")
expenses = query_tdb("SELECT * FROM expenses WHERE date >= '2025-01-01'")
tasks = query_tdb("SELECT * FROM tasks WHERE status = 'complete'")
```

**Qualitative Knowledge (VDB):**
```python
# Search for related information
meeting_notes = search_vdb("project planning milestones", "meetings")
documentation = search_vdb("technical architecture design", "docs")
decisions = search_vdb("roadmap priorities strategy", "strategy")
```

**Files and References:**
```python
# Read files
reports = [read_file(f) for f in list_files("reports/weekly")]
documentation = read_file("docs/project_plan.md")
```

**External Sources:**
```python
# Search web
research = search_web("industry best practices project tracking")
```

---

## Phase 2: Extract Key Points

**Identify the most important information from each source.**

### Extraction Techniques

**Structured Extraction:**
```python
# Extract patterns from TDB
query_tdb("""
    SELECT
        project,
        SUM(hours) as total_hours,
        COUNT(*) as entries,
        MAX(date) as last_worked
    FROM timesheets
    GROUP BY project
""")
# → Summary: Which projects consumed most time
```

**Keyword Extraction:**
```python
# Search VDB for key themes
search_vdb("challenges blockers obstacles", "meetings")
search_vdb("successes achievements wins", "journal")
search_vdb("decisions choices commitments", "strategy")
```

**Pattern Extraction:**
```python
# Use Python to extract patterns
execute_python("""
import pandas as pd
import re

# Find common themes in text
texts = [meeting['content'] for meeting in meetings]
# Extract dates, names, action items
patterns = {
    'dates': re.findall(r'\\d{4}-\\d{2}-\\d{2}', text),
    'action_items': re.findall(r'Action:\\s*(.+)', text),
    'decisions': re.findall(r'Decided:\\s*(.+)', text)
}
""")
```

---

## Phase 3: Integrate and Organize

**Combine extracted points into a coherent structure.**

### Organization Strategies

**Chronological:**
```python
# Organize by timeline
events = query_tdb("""
    SELECT date, type, description
    FROM project_events
    ORDER BY date ASC
""")
# → Timeline of project events
```

**Thematic:**
```python
# Group by themes
search_vdb("technical architecture", "meetings")  # Technical discussions
search_vdb("budget costs financial", "meetings")   # Financial discussions
search_vdb("timeline schedule planning", "meetings")  # Planning discussions
```

**Priority-Based:**
```python
# Organize by importance
query_tdb("""
    SELECT *
    FROM tasks
    ORDER BY priority DESC, due_date ASC
""")
```

**Hierarchical:**
```python
# Organize by category
query_tdb("""
    SELECT
        category,
        subcategory,
        COUNT(*) as count,
        SUM(amount) as total
    FROM expenses
    GROUP BY category, subcategory
    ORDER BY category, total DESC
""")
```

---

## Phase 4: Output and Insights

**Create coherent summaries and actionable insights.**

### Output Formats

**Executive Summary:**
```python
# Create high-level overview
summary = f"""
# Executive Summary: {project_name}

## Key Achievements
- {achievements}

## Challenges
- {challenges}

## Next Steps
- {next_steps}
"""
write_file(f"reports/{project_name}_summary.md", summary)
```

**Detailed Report:**
```python
# Comprehensive synthesis
report = f"""
# {report_title}

## Overview
{overview}

## Data Analysis
{data_analysis}

## Key Findings
{findings}

## Recommendations
{recommendations}

## Appendices
{appendices}
"""
```

**Action Items:**
```python
# Extract next steps
action_items = execute_python("""
# Extract action items from multiple sources
actions = []

# From meeting notes
for meeting in meetings:
    actions.extend(extract_actions(meeting))

# From tasks TDB
tasks = query_tdb("SELECT * FROM tasks WHERE status = 'pending'")

# Prioritize and deduplicate
unique_actions = prioritize_actions(actions)
""")
```

---

## Common Synthesis Scenarios

### Scenario 1: Weekly Project Status

**Gather:**
```python
timesheets = query_tdb("SELECT project, SUM(hours) FROM timesheets GROUP BY project")
tasks = query_tdb("SELECT * FROM tasks WHERE status = 'pending'")
meetings = search_vdb("project progress update", "meetings")
```

**Extract:**
```python
# Top time consumers
top_projects = sorted(timesheets, key=lambda x: x['total'], reverse=True)[:3]

# Critical tasks
critical_tasks = [t for t in tasks if t['priority'] == 'high']

# Recent decisions
decisions = search_vdb("decisions commitments", "meetings")
```

**Integrate:**
```python
status_report = f"""
# Weekly Status Report

## Time Distribution
{format_timesheets(top_projects)}

## Critical Tasks
{format_tasks(critical_tasks)}

## Recent Decisions
{format_decisions(decisions)}
"""
```

**Output:**
```python
write_file(f"reports/weekly_status_{date.today()}.md", status_report)
```

---

### Scenario 2: Research Synthesis

**Gather:**
```python
# Multiple research sources
web_research = search_web("best practices agile project management")
internal_docs = search_vdb("project management methodology", "docs")
team_notes = search_vdb("lessons learned retrospectives", "meetings")
```

**Extract:**
```python
# Common themes
themes = extract_common_themes([web_research, internal_docs, team_notes])

# Best practices
practices = extract_best_practices(web_research)

# Team insights
insights = extract_insights(team_notes)
```

**Integrate:**
```python
synthesis = f"""
# Research Synthesis: Agile Project Management

## Best Practices from Industry
{practices}

## Team Insights & Lessons Learned
{insights}

## Recommended Approach
{synthesize_approach(practices, insights)}
"""
```

---

### Scenario 3: Performance Review

**Gather:**
```python
# Quantitative metrics
performance = query_tdb("SELECT * FROM kpis WHERE period = 'Q1'")
productivity = query_tdb("SELECT * FROM productivity WHERE date >= '2025-01-01'")

# Qualitative feedback
feedback = search_vdb("performance feedback review", "meetings")
achievements = search_vdb("successes wins accomplishments", "journal")
```

**Extract:**
```python
# Top achievements
top_achievements = extract_top(achievements, limit=5)

# Areas for improvement
improvements = extract_improvements(feedback)

# Metrics trend
trends = calculate_trends(performance)
```

**Integrate:**
```python
review = f"""
# Q1 Performance Review

## Key Achievements
{top_achievements}

## Metrics Summary
{trends}

## Areas for Improvement
{improvements}

## Development Plan
{create_development_plan(improvements)}
"""
```

---

## Best Practices

### ✅ DO

- **Start with clear purpose** - Know what you're synthesizing for
- **Use multiple sources** - Diverse perspectives create better synthesis
- **Extract key points first** - Don't get lost in details
- **Organize logically** - Theme, chronology, priority
- **Cite sources** - Know where information came from
- **Look for patterns** - Common themes across sources
- **Identify gaps** - What's missing or unclear?
- **Create actionable output** - Summary should drive decisions

### ❌ DON'T

- **Don't include everything** - Synthesis requires selection
- **Don't ignore contradictions** - Resolve conflicting information
- **Don't lose context** - Maintain source attribution
- **Don't rush extraction** - Take time to find key points
- **Don't over-organize** - Simple structure beats complex hierarchy
- **Don't forget audience** - Tailor synthesis to who will read it
- **Don't miss insights** - Synthesis should reveal new understanding
- **Don't ignore gaps** - Acknowledge what's unknown

---

## Synthesis Techniques

### Technique 1: Compare and Contrast

```python
# Compare different sources
source_a = search_vdb("technical approach architecture", "docs")
source_b = search_vdb("business strategy roadmap", "strategy")

comparison = f"""
# Technical vs Strategic Approach

## Technical View
{summarize(source_a)}

## Strategic View
{summarize(source_b)}

## Alignment
{find_alignment(source_a, source_b)}

## Gaps
{find_gaps(source_a, source_b)}
"""
```

### Technique 2: Timeline Synthesis

```python
# Build chronological narrative
events = []

# From TDB
events.extend(query_tdb("SELECT date, event FROM milestones ORDER BY date"))

# From VDB
events.extend(search_vdb("important dates deadlines", "meetings"))

# From files
events.extend(extract_dates(read_file("project_timeline.md")))

# Organize chronologically
chronological = sorted(events, key=lambda x: x['date'])
timeline = format_timeline(chronological)
```

### Technique 3: Theme Extraction

```python
# Find common themes across sources
sources = [
    search_vdb("challenges problems", "meetings"),
    search_vdb("blockers obstacles", "journal"),
    query_tdb("SELECT * FROM issues WHERE status = 'open'")
]

# Extract themes
themes = {
    'technical': extract_technical_themes(sources),
    'process': extract_process_themes(sources),
    'people': extract_people_themes(sources),
    'resource': extract_resource_themes(sources)
}

# Organize by theme
synthesis = organize_by_theme(themes)
```

---

## Quick Reference

**Synthesis Workflows:**
- **Status Report:** Gather data → Extract metrics → Integrate → Report
- **Research:** Search sources → Extract themes → Compare → Recommendations
- **Performance:** Metrics + Feedback → Extract patterns → Insights → Plan
- **Planning:** Past data + Future goals → Extract constraints → Strategy → Actions

**Source Combinations:**
- **TDB + VDB:** Quantitative + Qualitative = Complete picture
- **Multiple VDB searches:** Different topics = Thematic synthesis
- **Files + TDB:** Context + Data = Evidence-based analysis
- **External + Internal:** Research + Experience = Practical recommendations

---

## Summary

**Synthesis Process:**
1. **Gather** - Multiple sources (TDB, VDB, Files, Search)
2. **Extract** - Key points, patterns, themes
3. **Integrate** - Organize and connect information
4. **Output** - Coherent summary, insights, actions

**Key Principles:**
- Start with clear purpose
- Use multiple diverse sources
- Extract key points, not everything
- Organize logically (theme/time/priority)
- Create actionable output
- Identify gaps and contradictions

**Synthesis Creates Value:**
- Combines quantitative + qualitative
- Reveals patterns across sources
- Generates new insights
- Drives informed decisions
- Saves time for readers

Good synthesis transforms information into understanding.
