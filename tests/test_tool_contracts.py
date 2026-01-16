"""Contract tests for tool registry."""

import pytest

from cassey.tools.registry import get_all_tools


@pytest.mark.asyncio
async def test_tool_registry_contract():
    """Ensure tools are loadable and have basic metadata."""
    tools = await get_all_tools()
    assert tools, "Tool registry returned no tools"

    names = [tool.name for tool in tools]
    assert len(names) == len(set(names)), "Tool names must be unique"

    for tool in tools:
        assert isinstance(tool.name, str) and tool.name.strip()
        description = getattr(tool, "description", None)
        assert isinstance(description, str) and description.strip()
        assert callable(getattr(tool, "invoke", None)) or callable(getattr(tool, "ainvoke", None))
        args_schema = getattr(tool, "args_schema", None)
        args = getattr(tool, "args", None)
        assert args_schema is not None or args is not None
