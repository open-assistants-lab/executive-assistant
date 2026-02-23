"""Firecrawl tools for web scraping, search, map and crawl."""

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


def _get_firecrawl_client():
    """Get Firecrawl client with config."""

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
def scrape_url(url: str, formats: list[str] | None = None) -> str:
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
                                + "\n".join(f"- {link}" for link in links)
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
def search_web(query: str, limit: int | None = None) -> str:
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
def map_url(url: str, search: str | None = None) -> str:
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


@tool
def crawl_url(
    url: str,
    limit: int | None = None,
    max_depth: int | None = None,
    crawl_entire_domain: bool = False,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> str:
    """Crawl a URL and all its pages recursively.

    Crawl a website starting from a URL, following links to discover and scrape
    multiple pages. Use this when you need to extract content from an entire
    website or multiple pages.

    Args:
        url: Starting URL to crawl (e.g., 'https://example.com')
        limit: Maximum number of pages to crawl (default: 10, max: 1000)
        max_depth: Maximum link depth to follow (default: 2)
        crawl_entire_domain: If True, crawl all pages on the domain (default: False)
        include_paths: List of path patterns to include (e.g., ['/blog/*', '/docs/**'])
        exclude_paths: List of path patterns to exclude (e.g., ['/admin/*', '/api/*'])

    Returns:
        Crawled content from multiple pages
    """
    if limit is None:
        limit = 10
    limit = min(limit, 1000)  # Cap at 1000

    if max_depth is None:
        max_depth = 2

    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info(
            "firecrawl.crawl",
            {"url": url, "limit": limit, "max_depth": max_depth},
            channel="agent",
        )

        result = client.crawl(
            url=url,
            limit=limit,
            max_discovery_depth=max_depth,
            crawl_entire_domain=crawl_entire_domain,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
        )

        if hasattr(result, "data"):
            data = result.data
            if isinstance(data, list) and data:
                output = f"## Crawl Results for: {url}\n"
                output += f"Pages crawled: {len(data)}\n\n"

                for i, page in enumerate(data[:20], 1):
                    if isinstance(page, dict):
                        markdown = page.get("markdown", "")
                        url_found = page.get("url", "")
                        title = page.get("title", "")

                        if markdown:
                            # Truncate each page
                            truncated = markdown[:2000] if len(markdown) > 2000 else markdown
                            output += f"### {i}. {title or url_found}\n"
                            output += f"URL: {url_found}\n\n"
                            output += f"{truncated}\n\n"
                            output += "---\n\n"

                if len(data) > 20:
                    output += f"\n... and {len(data) - 20} more pages (limit: {limit})"

                return output
            return f"No content crawled from: {url}"
        elif hasattr(result, "markdown"):
            return result.markdown[:10000]
        else:
            return str(result)[:5000]

    except Exception as e:
        logger.error("firecrawl.crawl_error", {"url": url, "error": str(e)}, channel="agent")
        return f"Error crawling {url}: {str(e)}"


@tool
def get_crawl_status(job_id: str) -> str:
    """Get the status of a crawl job.

    Check the progress of a crawl operation started with crawl_url.
    Returns the current status and any data that has been collected so far.

    Args:
        job_id: The job ID returned from a crawl operation

    Returns:
        Status information about the crawl job
    """
    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info("firecrawl.get_crawl_status", {"job_id": job_id}, channel="agent")

        result = client.get_crawl_status(job_id=job_id)

        if hasattr(result, "status"):
            output = "## Crawl Job Status\n\n"
            output += f"Job ID: {job_id}\n"
            output += f"Status: {result.status}\n"

            if hasattr(result, "data") and result.data:
                data = result.data
                if isinstance(data, list):
                    output += f"Pages completed: {len(data)}\n"
                elif isinstance(data, dict):
                    output += f"Data: {str(data)[:500]}\n"

            if hasattr(result, "total"):
                output += f"Total pages: {result.total}"

            return output
        else:
            return str(result)[:1000]

    except Exception as e:
        logger.error(
            "firecrawl.get_crawl_status_error", {"job_id": job_id, "error": str(e)}, channel="agent"
        )
        return f"Error getting crawl status: {str(e)}"


@tool
def cancel_crawl(crawl_id: str) -> str:
    """Cancel a running crawl job.

    Stop a crawl operation that is in progress.

    Args:
        crawl_id: The crawl ID to cancel

    Returns:
        Confirmation of cancellation
    """
    client, error = _get_firecrawl_client()
    if error:
        return f"Error: {error}"

    try:
        logger.info("firecrawl.cancel_crawl", {"crawl_id": crawl_id}, channel="agent")

        result = client.cancel_crawl(crawl_id=crawl_id)

        if result:
            return f"Crawl {crawl_id} has been cancelled."
        else:
            return f"Failed to cancel crawl {crawl_id}"

    except Exception as e:
        logger.error(
            "firecrawl.cancel_crawl_error", {"crawl_id": crawl_id, "error": str(e)}, channel="agent"
        )
        return f"Error cancelling crawl: {str(e)}"
