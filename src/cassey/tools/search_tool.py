"""Web search tool using SearXNG.

Integrates with SearXNG metasearch engine for web search functionality.
"""

from langchain_core.tools import tool

from cassey.config.settings import settings


def _get_searxng_params():
    """Get SearXNG connection parameters from settings."""
    searxng_url = settings.SEARXNG_HOST
    if not searxng_url:
        raise ValueError(
            "SearXNG host not configured. Please set SEARXNG_HOST in .env file."
        )
    return {"searx_host": searxng_url}


@tool
def search_web(query: str, num_results: int = 5) -> str:
    """Search the web using SearXNG metasearch engine.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5, max: 20)

    Returns:
        Search results as formatted text with titles, URLs, and snippets.

    Examples:
        >>> web_search("python async await tutorial")
        "Found 5 results:\\n1. Python Async Await - Real Python..."

        >>> web_search("latest AI news", num_results=3)
        "Found 3 results:\\n1. ..."
    """
    try:
        params = _get_searxng_params()
    except ValueError as e:
        return f"Configuration error: {e}"

    # Import here to avoid errors if not installed
    try:
        from langchain_community.utilities import SearxSearchWrapper
    except ImportError:
        return "Error: langchain-community not installed. Run: uv add langchain-community"

    # Limit num_results
    num_results = max(1, min(20, int(num_results)))

    try:
        # Create SearXNG wrapper
        search = SearxSearchWrapper(**params)

        # Perform search
        results = search.results(query, num_results)

        if not results:
            return f"No results found for: {query}"

        # Format results
        output_lines = [f"Found {len(results)} result(s) for: {query}\\n"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("link", result.get("url", "No URL"))
            snippet = result.get("snippet", result.get("body", ""))

            # Truncate snippet if too long
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."

            output_lines.append(f"{i}. {title}")
            output_lines.append(f"   URL: {url}")
            if snippet:
                output_lines.append(f"   {snippet}")
            output_lines.append("")

        return "\\n".join(output_lines).strip()

    except Exception as e:
        return f"Search error: {type(e).__name__}: {e}"


def get_search_tools() -> list:
    """Get web search tools."""
    return [search_web]
