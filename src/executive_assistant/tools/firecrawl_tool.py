"""Firecrawl web scraping tools.

Provides tools for scraping web pages using the Firecrawl API.
Firecrawl handles JavaScript rendering, anti-bot protections, and content extraction.
"""

from typing import Literal

from langchain_core.tools import tool
import httpx

from executive_assistant.config.settings import settings


def _is_firecrawl_configured() -> bool:
    """Check if Firecrawl API key is configured."""
    return bool(settings.FIRECRAWL_API_KEY)


async def _firecrawl_request(
    endpoint: str,
    payload: dict,
    timeout: int = 30,
) -> dict:
    """
    Make a request to the Firecrawl API.

    Args:
        endpoint: API endpoint (e.g., "/scrape")
        payload: Request payload
        timeout: Request timeout in seconds

    Returns:
        API response as dict

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If the request fails
    """
    if not settings.FIRECRAWL_API_KEY:
        raise ValueError("Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable.")

    url = f"{settings.FIRECRAWL_API_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


@tool
async def firecrawl_scrape(
    url: str,
    formats: str | None = None,
) -> str:
    """
    Scrape a web page using Firecrawl API.

    Firecrawl handles:
    - JavaScript rendering (SPA, React, Vue, etc.)
    - Anti-bot protections
    - Clean content extraction
    - Screenshot capture

    Args:
        url: The URL of the web page to scrape.
        formats: Output format(s) - comma-separated list.
                Options: "markdown", "html", "rawHtml", "links", "screenshot".
                Default: "markdown" for clean text extraction.

    Returns:
        Scraped content in the requested format(s).

    Raises:
        ValueError: If Firecrawl API key is not configured.

    Examples:
        >>> firecrawl_scrape("https://example.com")
        "Scraped content from https://example.com:\\n\\n# Example Domain\\n..."
    """
    if not _is_firecrawl_configured():
        return "Error: Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable."

    try:
        # Parse formats
        if formats:
            format_list = [f.strip() for f in formats.split(",")]
        else:
            format_list = ["markdown"]

        # Validate formats
        valid_formats = {"markdown", "html", "rawHtml", "links", "screenshot"}
        for fmt in format_list:
            if fmt not in valid_formats:
                return f"Invalid format: '{fmt}'. Valid options: {', '.join(valid_formats)}"

        payload = {
            "url": url,
            "formats": format_list,
        }

        result = await _firecrawl_request("/v1/scrape", payload)

        # Check for errors
        if result.get("error"):
            return f"Firecrawl error: {result['error']}"

        if not result.get("success"):
            return f"Scraping failed: {result.get('message', 'Unknown error')}"

        # Extract and format content
        data = result.get("data", {})
        output = [f"Scraped content from {url}:\n"]

        if "markdown" in data:
            output.append(f"## Markdown\n{data['markdown']}\n")

        if "html" in data:
            output.append(f"## HTML\n{data['html']}\n")

        if "rawHtml" in data:
            output.append(f"## Raw HTML\n{data['rawHtml']}\n")

        if "links" in data:
            links = data["links"]
            output.append(f"## Links ({len(links)} found)\n")
            for link in links[:20]:  # Limit to 20 links
                output.append(f"- {link}")
            if len(links) > 20:
                output.append(f"... and {len(links) - 20} more links")

        return "\n".join(output)

    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Request error: {e}"
    except Exception as e:
        return f"Error scraping URL: {e}"


@tool
async def firecrawl_crawl(
    url: str,
    limit: int = 10,
    formats: str | None = None,
) -> str:
    """
    Crawl a website starting from the given URL.

    Firecrawl will:
    - Start from the given URL
    - Follow internal links
    - Scrape multiple pages
    - Return structured content

    Args:
        url: Starting URL for the crawl.
        limit: Maximum number of pages to crawl (default: 10).
        formats: Output format(s) - comma-separated list.
                Options: "markdown", "html", "rawHtml", "links".
                Default: "markdown".

    Returns:
        Crawled content summary with page URLs and extracted content.

    Raises:
        ValueError: If Firecrawl API key is not configured.

    Examples:
        >>> firecrawl_crawl("https://example.com", limit=5)
        "Crawl started for https://example.com (max 5 pages)\\n\\n jobId: abc-123..."
    """
    if not _is_firecrawl_configured():
        return "Error: Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable."

    try:
        # Parse formats
        if formats:
            format_list = [f.strip() for f in formats.split(",")]
        else:
            format_list = ["markdown"]

        payload = {
            "url": url,
            "formats": format_list,
            "limit": limit,
            "scrapeOptions": {
                "onlyMainContent": True,
            }
        }

        # Start the crawl (asynchronous)
        result = await _firecrawl_request("/v1/crawl", payload)

        # Check for errors
        if result.get("error"):
            return f"Firecrawl error: {result['error']}"

        if not result.get("success"):
            return f"Crawl failed: {result.get('message', 'Unknown error')}"

        job_id = result.get("id")
        return f"Crawl started for {url} (max {limit} pages)\n\nJob ID: {job_id}\nNote: This is an asynchronous operation. Use firecrawl_check_status to check progress."

    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Request error: {e}"
    except Exception as e:
        return f"Error starting crawl: {e}"


@tool
async def firecrawl_check_status(job_id: str) -> str:
    """
    Check the status of an asynchronous Firecrawl crawl job.

    Args:
        job_id: The job ID returned by firecrawl_crawl.

    Returns:
        Current status of the crawl job and results if completed.

    Examples:
        >>> firecrawl_check_status("abc-123-def")
        "Crawl job abc-123-def status: completed\\n\\nTotal pages: 5\\n..."
    """
    if not _is_firecrawl_configured():
        return "Error: Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable."

    try:
        url = f"{settings.FIRECRAWL_API_URL}/v1/crawl/{job_id}"

        headers = {
            "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()

        # Check for errors
        if result.get("error"):
            return f"Firecrawl error: {result['error']}"

        status = result.get("status", "unknown")
        output = [f"Crawl job {job_id} status: {status}"]

        if status == "completed":
            data = result.get("data", {})
            total = data.get("total", 0)
            output.append(f"\nTotal pages: {total}")

            # Show results summary
            if "results" in data and data["results"]:
                output.append("\nCrawled pages:")
                for page_result in data["results"][:10]:
                    page_url = page_result.get("url", "unknown")
                    output.append(f"- {page_url}")

                if len(data["results"]) > 10:
                    output.append(f"... and {len(data['results']) - 10} more pages")

        elif status == "processing":
            output.append("\nCrawl is still in progress. Check again in a few moments.")

        elif status == "failed":
            output.append(f"\nError: {result.get('error', 'Unknown error')}")

        return "\n".join(output)

    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        return f"Request error: {e}"
    except Exception as e:
        return f"Error checking job status: {e}"


def get_firecrawl_tools() -> list:
    """
    Get all Firecrawl tools if API is configured.

    Returns empty list if FIRECRAWL_API_KEY is not set.
    """
    if not _is_firecrawl_configured():
        return []
    return [firecrawl_scrape, firecrawl_crawl, firecrawl_check_status]
