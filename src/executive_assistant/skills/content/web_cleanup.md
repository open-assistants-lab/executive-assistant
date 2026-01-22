# Web Cleanup

Description: Clean scraped web content into readable, structured text before summarizing or storing.

Tags: web, cleanup, scraping, text, normalization

## Overview
This skill provides a lightweight pipeline for turning raw scraped HTML into concise, readable text.

## When to use
- After `search_web`, `firecrawl_scrape`, or `playwright_scrape` returns messy HTML or boilerplate.
- Before summarization, storage, or document export.

## Recommended pipeline
1) **Structural cleanup (deterministic)**
   - Strip scripts/styles, nav/headers/footers, cookie banners.
   - Keep headings, paragraphs, lists.
   - Prefer `readability-lxml` (if available) to isolate main content.

2) **Semantic cleanup (LLM)**
   - Summarize cleaned text into a concise outline.
   - Preserve sources/links when relevant.

## Python helper (example)
```python
from bs4 import BeautifulSoup
from readability import Document

def extract_main_text(html: str) -> str:
    # Try readability first
    try:
        doc = Document(html)
        html = doc.summary()
    except Exception:
        pass
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "aside"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return text
```

## Output guidance
- Prefer bullet summaries for Telegram.
- Keep a short "sources" section if URLs are present.
