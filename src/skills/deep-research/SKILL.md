---
name: deep-research
description: Deep research, analyze and summarize content from the web. Use when user asks for comprehensive market research, competitive analysis, industry reports, or in-depth information gathering. This is for thorough research, not quick web searches.
---

# Deep Research Skill

## Overview

This skill provides a workflow for conducting **deep, comprehensive research** while managing context window limitations.

## The Problem

Web search results and scraped content can be very long, exceeding message limits and potentially the LLM's context window.

## The Solution

**Always save research to files first, then read from files to process.**

## Workflow

### Step 1: Search for Relevant Information

Use `search_web` to find relevant URLs:
```
search_web: "[topic] market size"
search_web: "[topic] industry analysis"
search_web: "[topic] competitors"
```

### Step 2: Scrape Key URLs

For each relevant URL found, use `scrape_url`:
```
scrape_url: "https://example.com/relevant-page"
```

### Step 3: Save Research to File

After gathering information, use `files_write` to save research:
```
files_write:
  path: "research/{topic}.md"
  content: |
    # [Topic] Research
    
    ## Key Findings
    [Summarize main findings]
    
    ## Market Size
    [What you found]
    
    ## Competitors
    [List competitors]
    
    ## Sources
    - https://example.com/source1
    - https://example.com/source2
```

### Step 4: Read and Summarize

Once saved, read from the file to summarize:
```
files_read: "research/{topic}.md"
```

## Research Framework

When conducting deep research, gather:

| Category | Data Points |
|----------|-------------|
| **Overview** | Industry, key players |
| **Market Size** | Value, volume, growth rate |
| **Market Share** | Key competitors, percentages |
| **Forecasts** | CAGR, trends, drivers |
| **Key Players** | Top companies, positioning |
| **Regulations** | Relevant laws, compliance |

## Best Practices

1. **Save First**: Always save research to files before summarizing
2. **Cite Sources**: Include URLs in your research document
3. **Structure**: Use headings and tables for readability
4. **Chunk Large Research**: If very long, save to multiple files
5. **Read from Files**: Don't try to read directly from search results

## Example Workflows

### Example 1: Market Research
```
User: "Research the EV battery market in 2025"

Agent:
1. search_web: "EV battery market size 2025"
2. search_web: "EV battery manufacturers competitors"
3. scrape_url: key URLs found
4. files_write: "research/ev-battery-market.md"
5. files_read: "research/ev-battery-market.md"
```

### Example 2: Competitor Analysis
```
User: "Analyze competitor X in the SaaS space"

Agent:
1. search_web: "competitor X company overview"
2. search_web: "competitor X market share"
3. scrape_url: competitor website, about page
4. files_write: "research/competitor-x.md"
5. files_read: "research/competitor-x.md"
```

### Example 3: Industry Report
```
User: "What's the outlook for AI in healthcare?"

Agent:
1. search_web: "AI healthcare market forecast 2025"
2. search_web: "AI healthcare companies"
3. scrape_url: industry reports, news articles
4. files_write: "research/ai-healthcare.md"
5. files_read: "research/ai-healthcare.md"
```

## File Location

Save research to:
```
research/{topic-slug}.md
```

This keeps research organized in the user's workspace for easy access.
