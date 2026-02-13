"""Tests for tool description prompt optimization."""

from langchain_core.tools import tool

from executive_assistant.tools import registry


def test_compact_tool_description_removes_sections_and_caps_length():
    description = (
        "Create a table from JSON input.\n\n"
        "Args:\n"
        "  table_name: Name of table.\n"
        "  data: Payload.\n\n"
        "Examples:\n"
        "  create_table(...)\n"
    )
    compact = registry._compact_tool_description(description, max_chars=50)

    assert "Args:" not in compact
    assert "Examples:" not in compact
    assert len(compact) <= 50
    assert compact == "Create a table from JSON input."


def test_optimize_tools_for_prompt_updates_base_tool_description():
    @tool
    def sample_tool(name: str) -> str:
        """Create a sample record with safe defaults.

        Args:
            name: The user-visible label for the record.

        Returns:
            Success text.
        """
        return name

    before = sample_tool.description
    registry._optimize_tools_for_prompt(
        [sample_tool],
        enabled=True,
        max_chars=80,
    )
    after = sample_tool.description

    assert "Args:" in before
    assert "Args:" not in after
    assert len(after) <= 80
