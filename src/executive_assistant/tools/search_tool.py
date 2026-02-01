"""Web search tool using Firecrawl API.

Firecrawl provides:
- High-quality web search results
- Optional content extraction from search results
- Advanced filtering (location, time, categories)
- Multiple source types: web, news, images
"""

import asyncio
from langchain_core.tools import tool

from executive_assistant.config.settings import settings


@tool
def search_web(query: str, num_results: int = 5, scrape_results: bool = False) -> str:
    """Search the web using Firecrawl API.

    Firecrawl provides high-quality search results with optional content extraction.
    Can search web, news, and images with advanced filters.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5, max: 20)
        scrape_results: If True, scrape full content from search results (uses more credits)

    Returns:
        Search results as formatted text with titles, URLs, and snippets.
        If scrape_results=True, includes full content from each result.

    Examples:
        >>> search_web("python async await tutorial")
        "Found 5 results:\\n1. Python Async Await - Real Python..."

        >>> search_web("latest AI news", num_results=3, scrape_results=True)
        "Found 3 results with content:\\n1. ..."
    """
    if not settings.FIRECRAWL_API_KEY:
        return "Error: FIRECRAWL_API_KEY not configured. Please set FIRECRAWL_API_KEY in .env file."

    # Import here to avoid circular dependency
    from executive_assistant.tools.firecrawl_tool import firecrawl_search

    # Limit num_results
    num_results = max(1, min(20, int(num_results)))

    try:
        # Firecrawl search is async, run it in event loop
        result = asyncio.run(firecrawl_search.ainvoke({
            "query": query,
            "num_results": num_results,
            "sources": "web",
            "scrape_results": scrape_results,
        }))
        return result
    except Exception as e:
        return f"Search error: {type(e).__name__}: {e}"


def get_search_tools() -> list:
    """Get web search tools."""
    return [search_web]
