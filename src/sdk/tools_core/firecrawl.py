"""Firecrawl tools — CLI-backed implementation.

Uses the Firecrawl CLI (https://docs.firecrawl.dev/sdks/cli) instead of the
Python SDK. This removes the `firecrawl` pip dependency and replaces it with
a subprocess call to `firecrawl` CLI, which supports:
  - Self-hosted instances via --api-url
  - Authentication via FIRECRAWL_API_KEY env or `firecrawl login`
  - JSON output via --json flag
  - All scrape, search, map, crawl, and agent commands
"""

from __future__ import annotations

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.tools import ToolAnnotations, tool
from src.sdk.tools_core.cli_adapter import CLIToolAdapter

logger = get_logger()


class FirecrawlCLI(CLIToolAdapter):
    cli_name = "firecrawl"
    install_hint = "npm install -g firecrawl-cli"


_fc = FirecrawlCLI()


def _api_url_args() -> list[str]:
    """Build --api-url args if Firecrawl is configured for self-hosted."""
    settings = get_settings()
    config = settings.tools
    base_url = getattr(config, "firecrawl_base_url", None)
    if base_url:
        return ["--api-url", base_url]
    return []


def _check_available() -> str | None:
    """Check if Firecrawl CLI is available and configured. Returns error or None."""
    err = _fc.require()
    if err:
        return err
    settings = get_settings()
    config = settings.tools
    api_key = getattr(config, "firecrawl_api_key", None)
    base_url = getattr(config, "firecrawl_base_url", None)
    if not base_url and not api_key:
        return "Firecrawl not configured. Set FIRECRAWL_BASE_URL (self-hosted) or FIRECRAWL_API_KEY (cloud), or run: firecrawl login"
    return None


@tool
def scrape_url(url: str, formats: str = "markdown", only_main_content: bool = True) -> str:
    """Scrape a URL and return its content.

    Extract content from any URL. Defaults to markdown output.
    Use --only-main-content for clean output without navigation, footers, and ads.

    Args:
        url: The URL to scrape (e.g., 'https://example.com')
        formats: Output format(s): 'markdown', 'html', 'links', 'screenshot', 'json', 'summary'.
                 Comma-separated for multiple (e.g., 'markdown,links'). Default: markdown
        only_main_content: Extract only main content, removing nav/footer (default: True)

    Returns:
        Scraped content in requested format
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["scrape", url, "--format", formats]
    args.extend(_api_url_args())
    if only_main_content:
        args.append("--only-main-content")

    logger.info("firecrawl.scrape", {"url": url, "formats": formats}, channel="agent")

    if formats != "markdown" or "," in formats:
        result = _fc.run_json(args)
        if result is None:
            rc, output = _fc.run(args, json_output=False)
            return output if rc == 0 else f"Error scraping {url}: {output}"
        if isinstance(result, dict):
            parts = []
            for fmt in formats.split(","):
                fmt = fmt.strip()
                if fmt in result:
                    content = str(result[fmt])
                    if fmt == "markdown" and len(content) > 10000:
                        content = content[:10000] + "\n\n... [truncated]"
                    parts.append(f"## {fmt.upper()}\n\n{content}")
                elif fmt == "links" and "links" in result:
                    links = result["links"][:20]
                    parts.append(
                        f"## Links ({len(result['links'])} total)\n\n"
                        + "\n".join(f"- {link}" for link in links)
                    )
            return (
                "\n\n---\n\n".join(parts)
                if parts
                else f"No content returned for formats: {formats}"
            )
        return str(result)[:5000]

    rc, output = _fc.run(args, json_output=False)
    if rc != 0:
        return f"Error scraping {url}: {output}"
    if len(output) > 10000:
        output = output[:10000] + "\n\n... [truncated]"
    return output


scrape_url.annotations = ToolAnnotations(
    title="Scrape URL", read_only=True, idempotent=True, open_world=True
)


@tool
def search_web(query: str, limit: int = 5) -> str:
    """Search the web and return results.

    Search the web using Firecrawl. Returns titles, URLs, and descriptions.
    Optionally scrape results for full content.

    Args:
        query: Search query (e.g., 'latest AI news')
        limit: Number of results to return (default: 5, max: 20)

    Returns:
        Search results with titles, URLs, and descriptions
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    limit = min(limit, 20)

    args = ["search", query, "--limit", str(limit), "--json"]
    args.extend(_api_url_args())

    logger.info("firecrawl.search", {"query": query, "limit": limit}, channel="agent")

    result = _fc.run_json(args)
    if result is None:
        rc, output = _fc.run(args, json_output=False)
        return output if rc == 0 else f"Error searching for '{query}': {output}"

    web_results = []
    if isinstance(result, dict):
        if "data" in result and isinstance(result["data"], dict):
            web_results = result["data"].get("web", [])
        elif "data" in result and isinstance(result["data"], list):
            web_results = result["data"]
        else:
            for key in ("web", "results", "data"):
                if key in result and isinstance(result[key], list):
                    web_results = result[key]
                    break

    if not web_results:
        return f"No results found for: {query}"

    output = f"## Search Results for: {query}\n\n"
    for i, r in enumerate(web_results[:limit], 1):
        if isinstance(r, dict):
            title = r.get("title", "No title")
            url = r.get("url", "")
            desc = r.get("description", r.get("snippet", ""))
        else:
            title = str(r)
            url = ""
            desc = ""
        output += f"### {i}. {title}\n"
        output += f"   URL: {url}\n"
        if desc:
            output += f"   {desc}\n"
        output += "\n"

    return output


search_web.annotations = ToolAnnotations(title="Search Web", read_only=True, open_world=True)


@tool
def map_url(url: str, search: str | None = None, limit: int | None = None) -> str:
    """Map a website to discover all indexed URLs.

    Discover URLs on a website. Optionally filter by search query.

    Args:
        url: Base URL to map (e.g., 'https://example.com')
        search: Optional search term to filter results
        limit: Maximum number of URLs to return (default: unlimited)

    Returns:
        List of discovered URLs
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["map", url, "--json"]
    args.extend(_api_url_args())
    if search:
        args.extend(["--search", search])
    if limit:
        args.extend(["--limit", str(limit)])

    logger.info("firecrawl.map", {"url": url, "search": search}, channel="agent")

    result = _fc.run_json(args)
    if result is None:
        rc, output = _fc.run(args, json_output=False)
        return output if rc == 0 else f"Error mapping {url}: {output}"

    links = []
    if isinstance(result, dict):
        if "links" in result:
            links = result["links"]
        elif "data" in result and isinstance(result["data"], list):
            links = result["data"]
    elif isinstance(result, list):
        links = result

    if not links:
        return f"No links found for: {url}"

    output = f"## URLs found on: {url}\n"
    if search:
        output += f"(filtered by: {search})\n"
    output += f"\nTotal: {len(links)} URLs\n\n"

    for link in links[:30]:
        if isinstance(link, dict):
            link = link.get("url", str(link))
        output += f"- {link}\n"

    if len(links) > 30:
        output += f"\n... and {len(links) - 30} more"

    return output


map_url.annotations = ToolAnnotations(
    title="Map Website URLs", read_only=True, idempotent=True, open_world=True
)


@tool
def crawl_url(
    url: str,
    limit: int = 10,
    max_depth: int = 2,
    crawl_entire_domain: bool = False,
    include_paths: str | None = None,
    exclude_paths: str | None = None,
) -> str:
    """Crawl a website starting from a URL.

    Crawl a website, following links to discover and scrape multiple pages.
    Returns results when complete (uses --wait flag).

    Args:
        url: Starting URL to crawl (e.g., 'https://example.com')
        limit: Maximum number of pages to crawl (default: 10, max: 1000)
        max_depth: Maximum link depth to follow (default: 2)
        crawl_entire_domain: If True, crawl all pages on the domain (default: False)
        include_paths: Comma-separated path patterns to include (e.g., '/blog,/docs')
        exclude_paths: Comma-separated path patterns to exclude (e.g., '/admin,/api')

    Returns:
        Crawled content from multiple pages
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    limit = min(limit, 1000)

    args = ["crawl", url, "--wait", "--limit", str(limit), "--max-depth", str(max_depth)]
    args.extend(_api_url_args())

    if crawl_entire_domain:
        args.append("--crawl-entire-domain")
    if include_paths:
        args.extend(["--include-paths", include_paths])
    if exclude_paths:
        args.extend(["--exclude-paths", exclude_paths])

    logger.info(
        "firecrawl.crawl",
        {"url": url, "limit": limit, "max_depth": max_depth},
        channel="agent",
    )

    result = _fc.run_json(args, timeout=300)
    if result is None:
        rc, output = _fc.run(args, json_output=False, timeout=300)
        return output if rc == 0 else f"Error crawling {url}: {output}"

    if isinstance(result, dict):
        data = result.get("data", [])
        if isinstance(data, list) and data:
            output = f"## Crawl Results for: {url}\n"
            output += f"Pages crawled: {len(data)}\n\n"

            for i, page in enumerate(data[:20], 1):
                if isinstance(page, dict):
                    markdown = page.get("markdown", "")
                    url_found = page.get("url", "")
                    title = page.get("title", "")

                    if markdown:
                        truncated = markdown[:2000] if len(markdown) > 2000 else markdown
                        output += f"### {i}. {title or url_found}\n"
                        output += f"URL: {url_found}\n\n"
                        output += f"{truncated}\n\n"
                        output += "---\n\n"

            if len(data) > 20:
                output += f"\n... and {len(data) - 20} more pages (limit: {limit})"

            return output
        return f"No content crawled from: {url}"

    return str(result)[:5000]


crawl_url.annotations = ToolAnnotations(title="Crawl Website", open_world=True)


@tool
def get_crawl_status(job_id: str) -> str:
    """Check the status of a crawl job.

    Args:
        job_id: The crawl job ID returned from crawl_url

    Returns:
        Crawl job status information
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["crawl", job_id, "--json"]
    args.extend(_api_url_args())

    logger.info("firecrawl.crawl_status", {"job_id": job_id}, channel="agent")

    result = _fc.run_json(args)
    if result is None:
        rc, output = _fc.run(args, json_output=False)
        return output if rc == 0 else f"Error getting crawl status: {output}"

    if isinstance(result, dict):
        status = result.get("status", "unknown")
        output = "## Crawl Job Status\n\n"
        output += f"Job ID: {job_id}\n"
        output += f"Status: {status}\n"

        if "data" in result:
            data = result["data"]
            if isinstance(data, list):
                output += f"Pages completed: {len(data)}\n"
            elif isinstance(data, dict):
                output += f"Data: {str(data)[:500]}\n"

        if "total" in result:
            output += f"Total pages: {result['total']}"

        return output

    return str(result)[:1000]


get_crawl_status.annotations = ToolAnnotations(
    title="Get Crawl Status", read_only=True, idempotent=True
)


@tool
def cancel_crawl(crawl_id: str) -> str:
    """Cancel a running crawl job.

    Note: The Firecrawl CLI doesn't have a direct cancel command.
    This tool attempts to check the crawl status. Use the Firecrawl
    dashboard or API to cancel running crawls.

    Args:
        crawl_id: The crawl ID to cancel

    Returns:
        Status or guidance message
    """
    return (
        f"Crawl cancellation for {crawl_id} is not supported via CLI. "
        f"Use the Firecrawl dashboard at https://firecrawl.dev/app "
        f"or the REST API (DELETE /v1/crawl/{crawl_id}) to cancel."
    )


cancel_crawl.annotations = ToolAnnotations(title="Cancel Crawl", destructive=True)


@tool
def firecrawl_status() -> str:
    """Check Firecrawl CLI status, authentication, and credits.

    Returns:
        Status information including version, auth, and credits
    """
    err = _fc.require()
    if err:
        return err

    args = ["--status"]
    args.extend(_api_url_args())

    rc, output = _fc.run(args, timeout=10)
    return output if rc == 0 else f"Error checking status: {output}"


firecrawl_status.annotations = ToolAnnotations(
    title="Firecrawl Status", read_only=True, idempotent=True
)


@tool
def firecrawl_agent(
    prompt: str,
    urls: str | None = None,
    schema: str | None = None,
) -> str:
    """Use Firecrawl's AI agent to research and extract data from the web.

    The agent autonomously browses websites to answer your query.
    Much more powerful than search for complex research tasks.

    Args:
        prompt: Natural language query (e.g., 'Find the top 5 AI startups and their funding')
        urls: Optional comma-separated URLs to focus the agent on
        schema: Optional JSON schema for structured output (e.g., '{"name":"string","funding":"number"}')

    Returns:
        Agent research results
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["agent", prompt, "--wait"]
    args.extend(_api_url_args())

    if urls:
        args.extend(["--urls", urls])
    if schema:
        args.extend(["--schema", schema])

    logger.info("firecrawl.agent", {"prompt": prompt[:100]}, channel="agent")

    rc, output = _fc.run(args, timeout=300, json_output=False)
    if rc != 0:
        return f"Error from Firecrawl agent: {output}"

    if len(output) > 10000:
        output = output[:10000] + "\n\n... [truncated]"

    return output


firecrawl_agent.annotations = ToolAnnotations(
    title="Firecrawl Agent Research", read_only=True, open_world=True
)
