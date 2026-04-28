"""Browser tools — Agent-Browser CLI implementation.

Uses Agent-Browser (https://agent-browser.dev) by Vercel Labs.
Pure Rust CLI with daemon architecture, ~50ms command latency.
Ref-based element selection for deterministic AI interaction.

Key difference from Browser-Use CLI:
- Uses refs (@e1, @e2) instead of indices — deterministic across snapshots
- Compact text output (~200-400 tokens vs ~3000-5000 for full DOM)
- Pure Rust binary — no Python/Node.js runtime needed
- 50+ commands including network, clipboard, diff, device emulation

Commands wrapped:
  browser_open        → agent-browser open <url>
  browser_snapshot    → agent-browser snapshot -i
  browser_click       → agent-browser click @<ref>
  browser_fill        → agent-browser fill @<ref> "<text>"
  browser_type        → agent-browser type "<text>"
  browser_press       → agent-browser press <key>
  browser_scroll      → agent-browser scroll [up|down]
  browser_hover       → agent-browser hover @<ref>
  browser_screenshot  → agent-browser screenshot [path]
  browser_eval        → agent-browser eval "<js>"
  browser_get_title   → agent-browser get title
  browser_get_text    → agent-browser get text
  browser_get_html    → agent-browser get html
  browser_get_url     → agent-browser get url
  browser_tab_new     → agent-browser tab new [<url>]
  browser_tab_close   → agent-browser tab close
  browser_back        → agent-browser back
  browser_forward     → agent-browser forward
  browser_wait_text   → agent-browser wait --text "<text>"
  browser_sessions    → agent-browser session list
  browser_close_all   → agent-browser close --all
  browser_status      → check CLI is installed + available
"""

from __future__ import annotations

from src.app_logging import get_logger
from src.sdk.tools import ToolAnnotations, tool
from src.sdk.tools_core.cli_adapter import CLIToolAdapter

logger = get_logger()


class AgentBrowserCLI(CLIToolAdapter):
    cli_name = "agent-browser"
    install_hint = "brew install agent-browser  OR  npm install -g agent-browser"


_ab = AgentBrowserCLI()

_DEFAULT_SESSION = "default_session"
_DEFAULT_TIMEOUT = 60


def _session_flag(session: str | None) -> list[str]:
    if session:
        return ["--session", session]
    return []


def _check_available() -> str | None:
    err = _ab.require()
    if err:
        return err
    return None


@tool
def browser_open(url: str, session: str | None = None) -> str:
    """Open a URL in the browser.

    Navigates the browser to the specified URL. Creates or reuses a session.
    After opening, use browser_snapshot to see the page elements.

    Args:
        url: The URL to open (e.g., 'https://example.com')
        session: Optional session name to reuse (default: 'default_session')

    Returns:
        Confirmation of navigation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["open", url, "--session", sess]

    logger.info("browser.open", {"url": url, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=_DEFAULT_TIMEOUT)
    return output.strip() if rc == 0 else f"Error opening {url}: {output}"


browser_open.annotations = ToolAnnotations(title="Open URL in Browser", open_world=True)


@tool
def browser_snapshot(session: str | None = None) -> str:
    """Get the current page snapshot — interactive elements with refs.

    Returns a compact accessibility tree with element refs (@e1, @e2, etc.)
    that you can use with browser_click, browser_fill, etc.

    This is more token-efficient than getting full HTML. Typically 200-400 tokens
    vs 3000-5000 for full DOM.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Accessibility tree with refs for each interactive element
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["snapshot", "-i", "--session", sess]

    logger.info("browser.snapshot", {"session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=30)
    if rc == 0:
        if len(output) > 8000:
            output = output[:8000] + "\n\n... [truncated]"
        return output
    return f"Error getting snapshot: {output}"


browser_snapshot.annotations = ToolAnnotations(
    title="Get Browser Snapshot", read_only=True, idempotent=True
)


@tool
def browser_click(ref: str, session: str | None = None) -> str:
    """Click on an element by its ref from the browser snapshot.

    Use browser_snapshot first to get element refs, then click by ref.
    Refs look like @e1, @e2, etc.

    Args:
        ref: Element ref from browser_snapshot (e.g., '@e5')
        session: Optional session name (default: 'default_session')

    Returns:
        Result of the click action
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["click", ref, "--session", sess]

    logger.info("browser.click", {"ref": ref, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=_DEFAULT_TIMEOUT)
    return output.strip() if rc == 0 else f"Error clicking {ref}: {output}"


browser_click.annotations = ToolAnnotations(title="Click Browser Element")


@tool
def browser_fill(ref: str, text: str, session: str | None = None) -> str:
    """Fill text into a form field identified by its ref.

    Clears the field first, then types the text.

    Args:
        ref: Element ref from browser_snapshot (e.g., '@e3')
        text: Text to fill into the field
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["fill", ref, text, "--session", sess]

    logger.info("browser.fill", {"ref": ref, "text": text[:50], "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=_DEFAULT_TIMEOUT)
    return output.strip() if rc == 0 else f"Error filling {ref}: {output}"


browser_fill.annotations = ToolAnnotations(title="Fill Browser Field")


@tool
def browser_type(text: str, submit_key: str | None = None, session: str | None = None) -> str:
    """Type text using the keyboard into the currently focused element.

    Optionally press a key after typing (e.g., 'Enter', 'Tab').

    Args:
        text: Text to type
        submit_key: Optional key to press after typing (e.g., 'Enter', 'Tab')
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["keyboard", "type", text, "--session", sess]

    logger.info("browser.type", {"text": text[:50], "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=_DEFAULT_TIMEOUT)
    result = output.strip() if rc == 0 else f"Error typing text: {output}"

    if submit_key and rc == 0:
        key_args = ["press", submit_key, "--session", sess]
        krc, kout = _ab.run(key_args, timeout=10)
        if krc != 0:
            result += f"\nWarning: key press '{submit_key}' failed: {kout}"

    return result


browser_type.annotations = ToolAnnotations(title="Type Text in Browser")


@tool
def browser_press(key: str, session: str | None = None) -> str:
    """Press a keyboard key or key combination.

    Supports special keys like Enter, Tab, Escape, and combinations
    like Control+a, Control+Shift+R.

    Args:
        key: Key or key combination (e.g., 'Enter', 'Control+a', 'Escape')
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["press", key, "--session", sess]

    logger.info("browser.press", {"key": key, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error pressing key '{key}': {output}"


browser_press.annotations = ToolAnnotations(title="Press Browser Key")


@tool
def browser_scroll(direction: str = "down", amount: int = 500, session: str | None = None) -> str:
    """Scroll the current page.

    Args:
        direction: Scroll direction: 'up' or 'down' (default: 'down')
        amount: Pixels to scroll (default: 500)
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    if direction not in ("up", "down"):
        return "Error: direction must be 'up' or 'down'"

    sess = session or _DEFAULT_SESSION
    args = ["scroll", direction, str(amount), "--session", sess]

    logger.info("browser.scroll", {"direction": direction, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error scrolling {direction}: {output}"


browser_scroll.annotations = ToolAnnotations(title="Scroll Browser Page")


@tool
def browser_hover(ref: str, session: str | None = None) -> str:
    """Hover over an element by its ref.

    Args:
        ref: Element ref from browser_snapshot (e.g., '@e2')
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["hover", ref, "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error hovering {ref}: {output}"


browser_hover.annotations = ToolAnnotations(title="Hover Browser Element")


@tool
def browser_screenshot(path: str | None = None, session: str | None = None) -> str:
    """Take a screenshot of the current browser page.

    Args:
        path: Optional file path to save screenshot (e.g., 'page.png')
        session: Optional session name (default: 'default_session')

    Returns:
        Path to saved screenshot or confirmation message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["screenshot", "--session", sess]
    if path:
        args.append(path)

    logger.info("browser.screenshot", {"session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=15)
    return output.strip() if rc == 0 else f"Error taking screenshot: {output}"


browser_screenshot.annotations = ToolAnnotations(title="Take Browser Screenshot", read_only=True)


@tool
def browser_eval(script: str, session: str | None = None) -> str:
    """Execute JavaScript in the current browser page.

    Args:
        script: JavaScript code to execute (e.g., 'document.title')
        session: Optional session name (default: 'default_session')

    Returns:
        JavaScript execution result
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["eval", script, "--session", sess]

    logger.info("browser.eval", {"session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=15)
    return output.strip() if rc == 0 else f"Error executing JavaScript: {output}"


browser_eval.annotations = ToolAnnotations(title="Execute Browser JavaScript", open_world=True)


@tool
def browser_get_title(session: str | None = None) -> str:
    """Get the title of the current browser page.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Page title
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["get", "title", "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error getting page title: {output}"


browser_get_title.annotations = ToolAnnotations(
    title="Get Browser Title", read_only=True, idempotent=True
)


@tool
def browser_get_text(ref: str | None = None, session: str | None = None) -> str:
    """Get the text content of the current page or a specific element.

    Args:
        ref: Optional element ref (e.g., '@e1') to get text from. If omitted, gets all page text.
        session: Optional session name (default: 'default_session')

    Returns:
        Page or element text content
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["get", "text", "--session", sess]
    if ref:
        args.append(ref)

    logger.info("browser.get_text", {"ref": ref, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=15)
    if rc == 0:
        if len(output) > 10000:
            output = output[:10000] + "\n\n... [truncated]"
        return output
    return f"Error getting text: {output}"


browser_get_text.annotations = ToolAnnotations(
    title="Get Browser Page Text", read_only=True, idempotent=True
)


@tool
def browser_get_html(session: str | None = None) -> str:
    """Get the HTML source of the current browser page.

    Returns raw HTML. Use browser_get_text for readable content instead.
    Use browser_snapshot for the most token-efficient page representation.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        HTML source (truncated if very long)
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["get", "html", "--session", sess]

    rc, output = _ab.run(args, timeout=15)
    if rc == 0:
        if len(output) > 15000:
            output = output[:15000] + "\n\n... [truncated]"
        return output
    return f"Error getting page HTML: {output}"


browser_get_html.annotations = ToolAnnotations(
    title="Get Browser HTML", read_only=True, idempotent=True
)


@tool
def browser_get_url(session: str | None = None) -> str:
    """Get the current URL of the browser page.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Current page URL
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["get", "url", "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error getting URL: {output}"


browser_get_url.annotations = ToolAnnotations(
    title="Get Browser URL", read_only=True, idempotent=True
)


@tool
def browser_tab_new(url: str | None = None, session: str | None = None) -> str:
    """Open a new browser tab, optionally with a URL.

    Args:
        url: Optional URL to open in the new tab
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation of new tab
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["tab", "new", "--session", sess]
    if url:
        args.append(url)

    logger.info("browser.tab_new", {"url": url, "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=_DEFAULT_TIMEOUT)
    return output.strip() if rc == 0 else f"Error opening new tab: {output}"


browser_tab_new.annotations = ToolAnnotations(title="Open New Browser Tab")


@tool
def browser_tab_close(session: str | None = None) -> str:
    """Close the current browser tab.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation of tab closure
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["tab", "close", "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error closing tab: {output}"


browser_tab_close.annotations = ToolAnnotations(title="Close Browser Tab", destructive=True)


@tool
def browser_back(session: str | None = None) -> str:
    """Navigate back to the previous page.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["back", "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error navigating back: {output}"


browser_back.annotations = ToolAnnotations(title="Browser Back", read_only=True)


@tool
def browser_forward(session: str | None = None) -> str:
    """Navigate forward to the next page.

    Args:
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation or error message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["forward", "--session", sess]

    rc, output = _ab.run(args, timeout=10)
    return output.strip() if rc == 0 else f"Error navigating forward: {output}"


browser_forward.annotations = ToolAnnotations(title="Browser Forward", read_only=True)


@tool
def browser_wait_text(text: str, timeout_ms: int = 5000, session: str | None = None) -> str:
    """Wait for specific text to appear on the current page.

    Args:
        text: Text to wait for
        timeout_ms: Maximum wait time in milliseconds (default: 5000)
        session: Optional session name (default: 'default_session')

    Returns:
        Confirmation that text appeared or timeout message
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    sess = session or _DEFAULT_SESSION
    args = ["wait", "--text", text, "--session", sess]

    timeout_s = max(10, timeout_ms // 1000 + 5)

    logger.info("browser.wait_text", {"text": text[:50], "session": sess}, channel="agent")

    rc, output = _ab.run(args, timeout=timeout_s)
    return output.strip() if rc == 0 else f"Text '{text}' not found within timeout: {output}"


browser_wait_text.annotations = ToolAnnotations(title="Wait for Browser Text", read_only=True)


@tool
def browser_sessions() -> str:
    """List all active browser sessions.

    Returns:
        List of active browser sessions
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["session", "list"]

    rc, output = _ab.run(args, timeout=10)
    return output if rc == 0 else f"Error listing sessions: {output}"


browser_sessions.annotations = ToolAnnotations(
    title="List Browser Sessions", read_only=True, idempotent=True
)


@tool
def browser_close_all() -> str:
    """Close all browser sessions and clean up.

    Returns:
        Confirmation of cleanup
    """
    err = _check_available()
    if err:
        return f"Error: {err}"

    args = ["close", "--all"]

    logger.info("browser.close_all", {}, channel="agent")

    rc, output = _ab.run(args, timeout=15)
    return output.strip() if rc == 0 else f"Error closing sessions: {output}"


browser_close_all.annotations = ToolAnnotations(
    title="Close All Browser Sessions", destructive=True
)


@tool
def browser_status() -> str:
    """Check if Agent-Browser CLI is installed and available.

    Returns:
        Status information about Agent-Browser CLI availability
    """
    err = _ab.require()
    if err:
        return err

    rc, output = _ab.run(["--version"], timeout=10)
    version = output.strip() if rc == 0 else "unknown"

    sessions_rc, sessions_out = _ab.run(["session", "list"], timeout=10)
    session_count = "unknown"
    if sessions_rc == 0:
        lines = [ln for ln in sessions_out.strip().split("\n") if ln.strip()]
        session_count = str(max(0, len(lines) - 1)) if lines else "0"

    return f"Agent-Browser CLI: available\nVersion: {version}\nActive sessions: {session_count}"


browser_status.annotations = ToolAnnotations(
    title="Agent-Browser Status", read_only=True, idempotent=True
)
