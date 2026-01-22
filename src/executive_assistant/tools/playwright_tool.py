"""Playwright-based web scraper for JS-rendered pages."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
async def playwright_scrape(
    url: str,
    wait_for_selector: str | None = None,
    timeout_ms: int = 30000,
    max_chars: int = 12000,
) -> str:
    """Scrape a JS-rendered page using Playwright. [WEB]

    Args:
        url: The page URL to load.
        wait_for_selector: Optional CSS selector to wait for.
        timeout_ms: Page load timeout in milliseconds.
        max_chars: Max characters to return from page text.

    Returns:
        Extracted visible text (truncated).
    """
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return (
            "Playwright is not available. Install with 'uv add playwright' and run "
            "'playwright install' to download browser binaries."
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
            title = await page.title()
            text = await page.inner_text("body")
        finally:
            await browser.close()

    if not text:
        return f"No visible text found for {url}"

    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[truncated]"

    return f"Title: {title}\nURL: {url}\n\n{text}"

