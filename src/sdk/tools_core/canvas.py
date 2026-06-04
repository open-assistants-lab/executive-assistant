import logging

from src.sdk.tools import tool, ToolAnnotations

logger = logging.getLogger(__name__)


@tool
def canvas_paint(
    html: str,
    surface_type: str = "canvas",
    user_id: str = "default_user",
    workspace_id: str = "personal",
) -> str:
    """Paint HTML content onto the Canvas tab.

    Call this tool to render a form, card, result, or any visual output
    in the user's Canvas tab. Include all CSS inline or in a style block.

    surface_type helps the backend validate:
      - 'canvas' — free-form content (default)
      - 'skill-form' — skill creation/editing form
      - 'subagent-form' — subagent creation/editing form

    Args:
        html: Full HTML content with inline CSS
        surface_type: Type of surface being painted
        user_id: User identifier
        workspace_id: Workspace identifier

    Returns:
        The HTML content (routed to Canvas tab by the backend)
    """
    html_bytes = len(html.encode("utf-8"))
    if html_bytes > 10240:
        return f"Canvas content too large ({html_bytes} bytes, max 10240). Simplify and try again."

    logger.info(
        "canvas.paint",
        {"surface_type": surface_type, "html_size": html_bytes},
        user_id=user_id,
    )

    return html


canvas_paint.annotations = ToolAnnotations(
    title="Paint Canvas",
    read_only=False,
    destructive=False,
    idempotent=False,
)
