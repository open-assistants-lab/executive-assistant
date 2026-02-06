#!/usr/bin/env python3
"""Test MCP client caching to verify FastMCP doesn't restart on every call."""

import asyncio
import sys
import logging
import json
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, "src")

from executive_assistant.tools.registry import (
    _load_mcp_servers,
    clear_mcp_cache,
    get_mcp_cache_info,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def _load_demo_clickhouse_server() -> dict:
    """Load ClickHouse MCP server config, preferring admin config on disk.

    Falls back to the public ClickHouse demo endpoint if admin config is missing.
    """
    config_path = Path("data/admins/mcp/mcp.json")
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            server = (cfg.get("mcpServers") or {}).get("clickhouse")
            if server:
                return {"clickhouse": server}
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", config_path, exc)

    # Fallback: public demo ClickHouse endpoint.
    return {
        "clickhouse": {
            "command": "uvx",
            "args": ["mcp-clickhouse"],
            "env": {
                "CLICKHOUSE_HOST": "sql-clickhouse.clickhouse.com",
                "CLICKHOUSE_PORT": "8443",
                "CLICKHOUSE_USER": "demo",
                "CLICKHOUSE_PASSWORD": "",
                "CLICKHOUSE_SECURE": "true",
            },
        }
    }


def _extract_text_payload(result: Any) -> str:
    """Extract text payload from MCP tool results."""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        texts = []
        for item in result:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(str(item))
        return "\n".join(texts)
    return str(result)


async def test_mcp_caching():
    """Test that MCP client is cached and reused across calls."""

    print("\n" + "="*80)
    print("MCP CLIENT CACHING TEST")
    print("="*80)

    # Clear cache to start fresh
    clear_mcp_cache()
    print("\n✅ Cleared cache")

    # MCP server config tailored to the current ClickHouse demo setup.
    servers = _load_demo_clickhouse_server()
    print("\n🔧 Using ClickHouse MCP server config from:")
    print("   - data/admins/mcp/mcp.json (if present), else demo fallback")

    print("\n📊 Initial cache state:")
    cache_info = get_mcp_cache_info()
    print(f"   Cache size: {cache_info['size']}")
    print(f"   Cache keys: {cache_info['keys']}")

    # First call - should create new client
    print("\n🔄 Call 1: Loading MCP tools (should create new client)...")
    tools_1 = await _load_mcp_servers(servers, "test")
    print(f"   Loaded {len(tools_1)} tools")

    print("\n📊 Cache state after call 1:")
    cache_info = get_mcp_cache_info()
    print(f"   Cache size: {cache_info['size']}")
    print(f"   Cache keys: {cache_info['keys']}")

    # Second call - should reuse cached client
    print("\n🔄 Call 2: Loading MCP tools again (should reuse cached client)...")
    tools_2 = await _load_mcp_servers(servers, "test")
    print(f"   Loaded {len(tools_2)} tools")

    print("\n📊 Cache state after call 2:")
    cache_info = get_mcp_cache_info()
    print(f"   Cache size: {cache_info['size']}")
    print(f"   Cache keys: {cache_info['keys']}")

    # Third call - should still reuse cached client
    print("\n🔄 Call 3: Loading MCP tools once more (should reuse cached client)...")
    tools_3 = await _load_mcp_servers(servers, "test")
    print(f"   Loaded {len(tools_3)} tools")

    print("\n📊 Final cache state:")
    cache_info = get_mcp_cache_info()
    print(f"   Cache size: {cache_info['size']}")
    print(f"   Cache keys: {cache_info['keys']}")

    # Verify results
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    if cache_info['size'] == 1:
        print("\n✅ SUCCESS: MCP client was cached and reused!")
        print(f"   Only 1 client created for 3 calls (expected: 1)")
        print(f"   Cache hit rate: 2/3 = 66.7%")
    else:
        print(f"\n❌ FAILED: Expected 1 cached client, got {cache_info['size']}")
        print(f"   This means a new MCP client was created for each call!")
        return False

    if len(tools_1) > 0:
        print(f"\n✅ SUCCESS: Loaded {len(tools_1)} tools from MCP server")
        print(f"   Tool names: {[tool.name for tool in tools_1[:3]]}...")
    else:
        print("\n⚠️  WARNING: No tools loaded from MCP server")
        return False

    # Validate against demo ClickHouse instance shape.
    tool_map = {tool.name: tool for tool in tools_1}
    required = {"list_databases", "list_tables", "run_select_query"}
    missing = required - set(tool_map)
    if missing:
        print(f"\n❌ FAILED: Missing required ClickHouse tools: {sorted(missing)}")
        return False

    print("\n🔍 Verifying demo ClickHouse dataset visibility...")
    db_result = await tool_map["list_databases"].ainvoke({})
    db_text = _extract_text_payload(db_result)
    has_default_db = "\"default\"" in db_text or "\ndefault\n" in f"\n{db_text}\n"
    if not has_default_db:
        print("\n❌ FAILED: Expected demo database 'default' not found")
        print(f"   list_databases output: {db_text[:400]}")
        return False
    print("✅ Found database: default")

    tables_result = await tool_map["run_select_query"].ainvoke(
        {"query": "SHOW TABLES FROM default LIMIT 20"}
    )
    tables_text = _extract_text_payload(tables_result)
    has_queries = "queries" in tables_text
    has_results = "results" in tables_text
    if not (has_queries and has_results):
        print("\n❌ FAILED: Expected demo tables 'queries' and 'results' not both present")
        print(f"   SHOW TABLES output: {tables_text[:500]}")
        return False
    print("✅ Found demo tables: queries, results")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_caching())
    sys.exit(0 if success else 1)
