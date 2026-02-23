"""Firecrawl tools for web scraping, search, map and crawl."""

from typing import Any, Optional

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


def _get_firecrawl_client():
    """Get Firecrawl client with config."""
    from src.config import get_settings

    settings = get_settings()
    config = settings.tools

    api_key = config.firecrawl_api_key
    base_url = config.firecrawl_base_url or None

    if not api_key:
        return None, "Firecrawl API key not configured. Set FIRECRAWL_API_KEY env var."

    try:
        from firecrawl import Firecrawl

        client = Firecrawl(api_key=api_key, api_url=base_url if base_url else None)
        return client, None
    except ImportError:
        return None, "Firecrawl SDK not installed. Run: uv pip install firecrawl"
    except Exception as e:
        return None, f"Failed to initialize Firecrawl: {e}"


@tool
def scrape_url(url: str, formats: Optional[list[str]] = None) -> str:
    """Scrape a URL and return its content.

    Extract content from any URL in markdown, HTML, or structured JSON.
    Use this when you need to get content from a specific webpage.

    Args:
        url: The URL to scrape (e.g., 'https://example.com')
        formats: Output formats to return. Options: ['markdown', 'html', 'json', 'screenshot', 'links']
                 Default: ['markdown']

    Returns:
        Scraped content in requested format(s)
    """
    if formats is None:
        formats = ["markdown"]

    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info("firecrawl.scrape", {"url": url, "formats": formats}, channel="agent")

        result = client.scrape(url, formats=formats)

        if hasattr(result, "data"):
            data = result.data
            if isinstance(data, dict):
                outputs = []
                for fmt in formats:
                    if fmt in data:
                        content = data[fmt]
                        if fmt == "markdown" and content:
                            # Truncate very long content
                            if len(content) > 10000:
                                content = content[:10000] + "\n\n... [truncated]"
                            outputs.append(f"## {fmt.upper()}\n\n{content}")
                        elif fmt == "links" and content:
                            links = content[:20]  # Limit links
                            outputs.append(
                                f"## Links ({len(content)} total)\n\n"
                                + "\n".join(f"- {l}" for l in links)
                            )
                        else:
                            outputs.append(f"## {fmt}\n\n{str(content)[:2000]}")
                    elif fmt == "json" and data.get("json"):
                        outputs.append(f"## JSON\n\n{str(data['json'])[:2000]}")

                if outputs:
                    return "\n\n---\n\n".join(outputs)
                return f"No content returned for formats: {formats}"
            return str(data)[:5000]
        elif hasattr(result, "markdown"):
            return result.markdown[:10000]
        else:
            return str(result)[:5000]

    except Exception as e:
        logger.error("firecrawl.scrape_error", {"url": url, "error": str(e)}, channel="agent")
        return f"Error scraping {url}: {str(e)}"


@tool
def search_web(query: str, limit: Optional[int] = None) -> str:
    """Search the web and get results with full page content.

    Search the web and optionally scrape the results in one operation.
    Use this when you need to find information from multiple sources.

    Args:
        query: Search query (e.g., 'latest AI news', 'python tutorial')
        limit: Number of results to return (default: 5, max: 20)

    Returns:
        Search results with titles, URLs, and descriptions
    """
    if limit is None:
        limit = 5
    limit = min(limit, 20)  # Cap at 20

    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info("firecrawl.search", {"query": query, "limit": limit}, channel="agent")

        results = client.search(query=query, limit=limit)

        if hasattr(results, "data") and results.data:
            data = results.data
            web_results = data.get("web", [])

            if not web_results:
                return f"No results found for: {query}"

            output = f"## Search Results for: {query}\n\n"
            for i, r in enumerate(web_results[:limit], 1):
                title = r.get("title", "No title")
                url = r.get("url", "")
                desc = r.get("description", "No description")
                output += f"### {i}. {title}\n"
                output += f"   URL: {url}\n"
                if desc:
                    output += f"   {desc}\n"
                output += "\n"

            return output
        else:
            return f"No results found for: {query}"

    except Exception as e:
        logger.error("firecrawl.search_error", {"query": query, "error": str(e)}, channel="agent")
        return f"Error searching for '{query}': {str(e)}"


@tool
def map_url(url: str, search: Optional[str] = None) -> str:
    """Map a Website to discover all indexed URLs.

    Discover URLs on a Website. Optionally search for specific content.
    Use this to find all pages on a site before scraping.

    Args:
        url: Base URL to map (e.g., 'https://example.com')
        search: Optional search term to filter results

    Returns:
        List of discovered URLs
    """
    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info("firecrawl.map", {"url": url, "search": search}, channel="agent")

        result = client.map(url=url, search=search)

        if hasattr(result, "links"):
            links = result.links
            if not links:
                return f"No links found for: {url}"

            output = f"## URLs found on: {url}\n"
            if search:
                output += f"(filtered by: {search})\n"
            output += f"\nTotal: {len(links)} URLs\n\n"

            # Show first 30 links
            for link in links[:30]:
                output += f"- {link}\n"

            if len(links) > 30:
                output += f"\n... and {len(links) - 30} more"

            return output
        else:
            return f"No links found for: {url}"

    except Exception as e:
        logger.error("firecrawl.map_error", {"url": url, "error": str(e)}, channel="agent")
        return f"Error mapping {url}: {str(e)}"
