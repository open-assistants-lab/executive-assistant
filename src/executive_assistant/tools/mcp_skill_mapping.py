"""Mapping of MCP servers to associated skills for auto-loading.

This module defines which skills should be suggested when specific MCP servers
are added, providing the agent with contextual knowledge about how to use those tools.
"""

from typing import Dict, List

# Mapping of MCP server names to their associated skills
MCP_SERVER_SKILLS: Dict[str, Dict] = {
    "fetch": {
        "skills": ["web_scraping", "fetch_content"],
        "reason": "The fetch tool requires knowledge of web scraping best practices, content extraction patterns, and handling pagination.",
        "auto": True,
    },
    "mcp-server-fetch": {
        "skills": ["web_scraping", "fetch_content"],
        "reason": "The fetch tool requires knowledge of web scraping best practices, content extraction patterns, and handling pagination.",
        "auto": True,
    },
    "github": {
        "skills": ["github_api", "code_search", "git_operations"],
        "reason": "GitHub tools require understanding of API patterns, effective code search queries, and repository operations.",
        "auto": True,
    },
    "@modelcontextprotocol/server-github": {
        "skills": ["github_api", "code_search", "git_operations"],
        "reason": "GitHub tools require understanding of API patterns, effective code search queries, and repository operations.",
        "auto": True,
    },
    "clickhouse": {
        "skills": ["clickhouse_sql", "database_queries"],
        "reason": "ClickHouse tools require knowledge of SQL syntax, ClickHouse-specific optimizations, and query patterns.",
        "auto": True,
    },
    "mcp-clickhouse": {
        "skills": ["clickhouse_sql", "database_queries"],
        "reason": "ClickHouse tools require knowledge of SQL syntax, ClickHouse-specific optimizations, and query patterns.",
        "auto": True,
    },
    "filesystem": {
        "skills": ["file_operations", "file_security"],
        "reason": "Filesystem tools require understanding of path manipulation, security considerations, and efficient file operations.",
        "auto": False,  # Requires path argument, so ask user first
    },
    "@modelcontextprotocol/server-filesystem": {
        "skills": ["file_operations", "file_security"],
        "reason": "Filesystem tools require understanding of path manipulation, security considerations, and efficient file operations.",
        "auto": False,
    },
    "brave-search": {
        "skills": ["web_search", "search_strategies"],
        "reason": "Search tools benefit from knowledge of query formulation, result evaluation, and search strategies.",
        "auto": True,
    },
    "mcp-server-brave-search": {
        "skills": ["web_search", "search_strategies"],
        "reason": "Search tools benefit from knowledge of query formulation, result evaluation, and search strategies.",
        "auto": True,
    },
    "puppeteer": {
        "skills": ["browser_automation", "web_scraping_advanced"],
        "reason": "Browser automation requires knowledge of DOM manipulation, waiting strategies, and scraping techniques.",
        "auto": True,
    },
    "@modelcontextprotocol/server-puppeteer": {
        "skills": ["browser_automation", "web_scraping_advanced"],
        "reason": "Browser automation requires knowledge of DOM manipulation, waiting strategies, and scraping techniques.",
        "auto": True,
    },
}


def get_skills_for_server(server_name: str, command: str = None) -> List[str]:
    """Get recommended skills for an MCP server.

    Args:
        server_name: Name of the MCP server
        command: Command used to start the server (for detection)

    Returns:
        List of skill names that would help with this server
    """
    # Try exact match first
    if server_name in MCP_SERVER_SKILLS:
        skill_info = MCP_SERVER_SKILLS[server_name]
        if skill_info.get("auto", True):
            return skill_info["skills"]

    # Try to detect from command
    if command:
        if "fetch" in command.lower():
            return MCP_SERVER_SKILLS["fetch"]["skills"]
        elif "github" in command.lower():
            return MCP_SERVER_SKILLS["github"]["skills"]
        elif "clickhouse" in command.lower():
            return MCP_SERVER_SKILLS["clickhouse"]["skills"]
        elif "filesystem" in command.lower():
            # Don't auto-load filesystem (requires paths)
            return []

    return []


def get_skill_recommendation_reason(server_name: str) -> str:
    """Get explanation of why skills are recommended for a server."""
    if server_name in MCP_SERVER_SKILLS:
        return MCP_SERVER_SKILLS[server_name]["reason"]
    return "Skills help the agent use this tool more effectively."


def is_server_auto_load(server_name: str) -> bool:
    """Check if skills should be auto-loaded for this server."""
    if server_name in MCP_SERVER_SKILLS:
        return MCP_SERVER_SKILLS[server_name].get("auto", True)
    return False
