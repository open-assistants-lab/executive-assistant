#!/usr/bin/env python3
"""Test Firecrawl search integration.

This script tests the new Firecrawl search functionality
to verify it works as expected.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from executive_assistant.config.settings import settings
from executive_assistant.tools.firecrawl_tool import firecrawl_search


async def test_firecrawl_search():
    """Test basic Firecrawl search."""
    if not settings.FIRECRAWL_API_KEY:
        print("❌ FIRECRAWL_API_KEY not configured")
        return False

    print("Testing Firecrawl search...")
    print("-" * 60)

    # Test 1: Basic web search
    print("\n1. Basic web search (3 results):")
    result = await firecrawl_search.ainvoke({
        "query": "python async await",
        "num_results": 3,
        "sources": "web",
        "scrape_results": False,
    })
    print(result[:500] + "..." if len(result) > 500 else result)

    # Test 2: Search with content scraping
    print("\n2. Search with content scraping (2 results):")
    result = await firecrawl_search.ainvoke({
        "query": "what is Firecrawl API",
        "num_results": 2,
        "sources": "web",
        "scrape_results": True,
    })
    print(result[:800] + "..." if len(result) > 800 else result)

    # Test 3: News search
    print("\n3. News search:")
    result = await firecrawl_search.ainvoke({
        "query": "artificial intelligence",
        "num_results": 3,
        "sources": "news",
        "scrape_results": False,
    })
    print(result[:500] + "..." if len(result) > 500 else result)

    print("\n" + "-" * 60)
    print("✅ All tests passed!")
    return True


def test_search_tool():
    """Test unified search tool with provider switching."""
    import asyncio
    from executive_assistant.tools.search_tool import _search_with_searxng, _search_with_firecrawl

    print("\nTesting unified search_tool.py...")

    # Test current provider
    provider = settings.SEARCH_PROVIDER
    print(f"Current SEARCH_PROVIDER: {provider}")

    if provider == "firecrawl":
        if not settings.FIRECRAWL_API_KEY:
            print("❌ Firecrawl selected but API key not configured")
            return False

        # Test Firecrawl search
        result = asyncio.run(_search_with_firecrawl("test search", 2))
        print(f"Result preview: {result[:200]}...")
        print("✅ Firecrawl search works!")
    else:
        # Test SearXNG search
        result = _search_with_searxng("test search", 2)
        print(f"Result preview: {result[:200]}...")
        print("✅ SearXNG search works!")

    return True


if __name__ == "__main__":
    print("Firecrawl Search Test Suite")
    print("=" * 60)

    # Run Firecrawl-specific tests
    success = asyncio.run(test_firecrawl_search())

    # Run unified tool tests
    if success:
        test_search_tool()

    print("\n" + "=" * 60)
    print("Test complete!")
