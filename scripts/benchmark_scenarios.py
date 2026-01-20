"""Realistic test scenarios based on actual Executive Assistant usage."""

from executive_assistant.agent.prompts import get_system_prompt


TELEGRAM_SYSTEM_PROMPT = get_system_prompt("telegram")

# Token count estimate: ~4 chars per token
TELEGRAM_SYSTEM_TOKENS = len(TELEGRAM_SYSTEM_PROMPT) // 4


SCENARIOS = [
    # ============================================================================
    # Simple Q&A (Low Token Count)
    # ============================================================================

    {
        "name": "simple_qa",
        "description": "Simple factual question",
        "complexity": "simple",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "What's the current time in Tokyo?",
        "expected_tools": [],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 15,
    },

    {
        "name": "simple_explanation",
        "description": "Explain a concept briefly",
        "complexity": "simple",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "What is vector store and how does it work?",
        "expected_tools": [],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 15,
    },

    # ============================================================================
    # Tool-Using (Medium Token Count)
    # ============================================================================

    {
        "name": "web_search_single",
        "description": "Single web search with summary",
        "complexity": "medium",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "Search for the latest Python 3.13 features and summarize them briefly.",
        "expected_tools": ["search_web"],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 20,
    },

    {
        "name": "db_operation",
        "description": "Create table and insert data",
        "complexity": "medium",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "Create a timesheet table with columns: date, activity, duration. Then add an entry for today: 2025-01-18, Executive Assistant development, 2.5 hours.",
        "expected_tools": ["create_db_table", "insert_db_table"],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 50,
    },

    # ============================================================================
    # Complex Multi-Tool (High Token Count)
    # ============================================================================

    {
        "name": "research_and_store",
        "description": "Web search → DB → summary",
        "complexity": "complex",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "Search for 'top 5 Python web frameworks 2025', create a database table with the results (name, description, url), and save a summary to a file.",
        "expected_tools": ["search_web", "create_db_table", "insert_db_table", "write_file"],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 35,
    },

    {
        "name": "time_tracking_workflow",
        "description": "Real user message: Track time",
        "complexity": "medium",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "Track my time spent on Executive Assistant development today. Create a timesheet table with columns: date, activity, duration_hours. Log these entries: 2h coding, 30min documentation, 1h testing, 45min benchmarking.",
        "expected_tools": ["create_db_table", "insert_db_table"],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 65,
    },

    # ============================================================================
    # Context-Heavy (High Token Count)
    # ============================================================================

    {
        "name": "long_context",
        "description": "Long reasoning task",
        "complexity": "complex",
        "system_prompt": TELEGRAM_SYSTEM_PROMPT,
        "user_message": "I want to implement a progressive disclosure system for LangChain agents. Explain: 1) What is progressive disclosure? 2) How does it apply to agent tools? 3) What are the implementation steps? 4) What are common pitfalls? Provide detailed explanation with examples.",
        "expected_tools": [],
        "estimated_input_tokens": TELEGRAM_SYSTEM_TOKENS + 50,
    },
]


def get_scenario(name: str) -> dict | None:
    """Get a scenario by name."""
    for scenario in SCENARIOS:
        if scenario["name"] == name:
            return scenario
    return None


def get_all_scenarios() -> list[dict]:
    """Get all scenarios."""
    return SCENARIOS


def get_scenarios_by_complexity(complexity: str) -> list[dict]:
    """Get scenarios filtered by complexity."""
    return [s for s in SCENARIOS if s["complexity"] == complexity]
