"""User MCP (Model Context Protocol) management tools.

These tools allow users to add, remove, and manage their own MCP servers
per conversation, giving them control over their tool ecosystem.
"""

from typing import Any

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.user_mcp_storage import UserMCPStorage
from executive_assistant.storage.mcp_skill_storage import (
    MCPSkillProposal,
    save_pending_skill,
    load_pending_skill,
    list_pending_skills,
    approve_skill as approve_skill_storage,
    reject_skill as reject_skill_storage,
    get_approved_skills,
)
from executive_assistant.tools.mcp_skill_mapping import (
    get_skills_for_server,
    get_skill_recommendation_reason,
    is_server_auto_load,
)


def _format_server_list(local_servers: dict, remote_servers: dict) -> str:
    """Format server list for display.

    Args:
        local_servers: Local (stdio) MCP servers
        remote_servers: Remote (HTTP/SSE) MCP servers

    Returns:
        Formatted server list as markdown
    """
    lines = ["**Your MCP Servers:**\n"]

    if local_servers:
        lines.append("### Local (stdio) Servers")
        lines.append("| Name | Command | Args | Env Vars |")
        lines.append("|------|---------|------|----------|")

        for name, config in local_servers.items():
            command = config.get("command", "N/A")
            args = " ".join(config.get("args", []))
            env = f"{len(config.get('env', {}))} var(s)"
            cwd = config.get("cwd", "default")

            lines.append(f"| **{name}** | `{command}` | `{args}` | {env} |")

    if remote_servers:
        if local_servers:
            lines.append("")  # Blank line between sections
        lines.append("### Remote (HTTP/SSE) Servers")
        lines.append("| Name | URL | Headers |")
        lines.append("|------|-----|--------|")

        for name, config in remote_servers.items():
            url = config.get("url", "N/A")
            headers = config.get("headers", {})
            header_count = len(headers) if headers else 0

            lines.append(f"| **{name}** | `{url}` | {header_count} header(s) |")

    if not local_servers and not remote_servers:
        lines.append("No MCP servers configured.")
        lines.append("")
        lines.append("Add a server with:")
        lines.append("• Local: `mcp_add_server(name='...', command='...', args='...')`")
        lines.append("• Remote: `mcp_add_remote_server(name='...', url='...')`")

    return "\n".join(lines)


@tool
def mcp_list_servers() -> str:
    """List all configured MCP servers for the current conversation.

    Shows user MCP servers (per-thread) and admin MCP servers (if available).

    Returns:
        Formatted list of all configured MCP servers (local and remote)

    Examples:
        >>> mcp_list_servers()
        "Your MCP Servers:\\n\\n### Local (stdio) Servers\\n..."
    """
    from executive_assistant.storage.mcp_storage import load_mcp_config
    from executive_assistant.config import settings

    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        # Load user MCP servers
        storage = UserMCPStorage(thread_id)
        local = storage.load_local_config()["mcpServers"]
        remote = storage.load_remote_config()["mcpServers"]

        # Load admin MCP servers (if configured)
        admin_local = {}
        admin_remote = {}
        try:
            admin_config = load_mcp_config()
            # Check if admin MCP is enabled
            if admin_config.get("mcpEnabled", False):
                admin_servers = admin_config.get("mcpServers", {})
                # Split into local (stdio) and remote (HTTP/SSE)
                for name, config in admin_servers.items():
                    if "command" in config:
                        admin_local[name] = config
                    elif "url" in config:
                        admin_remote[name] = config
        except Exception:
            # Admin MCP not configured or error loading - skip
            pass

        # Build response
        parts = []

        # Admin servers (if any)
        if admin_local or admin_remote:
            parts.append("## 📋 Admin MCP Servers")
            parts.append("(Configured by system administrator)")
            parts.append(_format_server_list(admin_local, admin_remote))
            parts.append("")

        # User servers (if any)
        if local or remote:
            parts.append("## 👤 Your MCP Servers")
            parts.append("(Configured for this conversation)")
            parts.append(_format_server_list(local, remote))
            parts.append("")

        # No servers at all
        if not (local or remote or admin_local or admin_remote):
            return "I don't have any MCP servers configured right now. If you'd like to add a ClickHouse (or any other) server, let me know and I can walk you through the setup."

        return "\n".join(parts).strip()

    except Exception as e:
        return f"❌ Error loading MCP configuration: {e}"


@tool
def mcp_add_server(
    name: str,
    command: str,
    arguments: str = "",
    env: str = "{}",
    cwd: str = "",
) -> str:
    """Add a local MCP server (stdio).

    This adds a command-line tool that communicates via stdio.
    The server will be started automatically when tools are loaded.

    Args:
        name: Unique server name (letters, numbers, underscore, hyphen only)
        command: Command to run (e.g., "uvx mcp-server-fetch")
        arguments: Command arguments, comma-separated (optional)
        env: Environment variables as JSON string (optional)
        cwd: Working directory (optional)

    Returns:
        Confirmation message with next steps

    Examples:
        >>> mcp_add_server(
        ...     name="fetch",
        ...     command="uvx",
        ...     arguments="mcp-server-fetch,--port,3000"
        ... )
        "✅ Added server 'fetch'. Use /mcp reload to load tools."
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)
        config = storage.load_local_config()

        # Check if server already exists
        if name in config["mcpServers"]:
            return (
                f"❌ Server '{name}' already exists.\n"
                f"Use a different name or remove it first with `mcp_remove_server`."
            )

        # Parse arguments
        if arguments.strip():
            arg_list = [a.strip() for a in arguments.split(",")]
        else:
            arg_list = []

        # Parse env
        import json
        env_dict = {}
        if env.strip():
            try:
                env_dict = json.loads(env)
                if not isinstance(env_dict, dict):
                    return "❌ 'env' must be a JSON object (e.g., '{\"PATH\": \"/usr/bin\"}')"
            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON in 'env': {e}"

        # Build server config
        server_config = {
            "command": command,
            "args": arg_list,
            "env": env_dict,
        }

        # Add cwd if provided
        if cwd.strip():
            server_config["cwd"] = cwd

        # Save config
        config["mcpServers"][name] = server_config
        storage.save_local_config(config)

        # Check for associated skills and create proposals
        skill_proposals = get_skills_for_server(name, command)
        pending_skills = []

        for skill_name in skill_proposals:
            # Check if already approved or pending
            existing = load_pending_skill(skill_name)
            if existing and existing.status == "approved":
                continue  # Already approved

            reason = get_skill_recommendation_reason(name)

            # Create pending proposal
            proposal = MCPSkillProposal(
                skill_name=skill_name,
                source_server=name,
                reason=reason,
                content="",  # Will be loaded from skill file when needed
            )
            save_pending_skill(proposal)
            pending_skills.append(skill_name)

        # Build response message
        response_lines = [
            f"✅ Added MCP server '{name}'",
            "",
            f"**Command:** {command}",
            f"**Args:** {arg_list if arg_list else '(none)'}",
        ]

        if pending_skills:
            response_lines.extend([
                "",
                f"📚 **{len(pending_skills)} helper skill(s) proposed:**",
            ])
            for skill in pending_skills:
                response_lines.append(f"  • **{skill}**")
            response_lines.extend([
                "",
                f"These skills can help the agent use {name} tools more effectively.",
                "",
                "Next steps:",
                f"• Use `mcp_list_pending_skills` to see skill proposals",
                f"• Use `mcp_approve_skill('<name>')` to approve skills",
                f"• Use `mcp_reject_skill('<name>')` to reject skills",
                f"• Use `mcp_reload` to load tools from this server",
            ])
        else:
            response_lines.extend([
                "",
                "Next steps:",
                f"• Use `mcp_reload` to load tools from this server",
                f"• Use `mcp_show_server('{name}')` to see details",
                f"• Use `mcp_list_servers` to see all servers",
            ])

        return "\n".join(response_lines)

    except ValueError as e:
        return f"❌ Validation error: {e}"
    except Exception as e:
        return f"❌ Error adding server: {e}"


@tool
def mcp_add_remote_server(
    name: str,
    url: str,
    headers: str = "{}",
) -> str:
    """Add a remote MCP server (HTTP/SSE).

    This adds a network-accessible MCP server that communicates via HTTP or SSE.

    Args:
        name: Unique server name (letters, numbers, underscore, hyphen only)
        url: Server URL (HTTPS required, or http://localhost for testing)
        headers: HTTP headers as JSON string (optional)

    Returns:
        Confirmation message with next steps

    Examples:
        >>> mcp_add_remote_server(
        ...     name="github",
        ...     url="https://api.github.com/mcp",
        ...     headers='{"Authorization": "Bearer $GITHUB_TOKEN"}'
        ... )
        "✅ Added remote server 'github'"
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)
        config = storage.load_remote_config()

        # Check if server already exists
        if name in config["mcpServers"]:
            return (
                f"❌ Server '{name}' already exists.\n"
                f"Use a different name or remove it first with `mcp_remove_server`."
            )

        # Parse headers
        import json
        header_dict = {}
        if headers.strip():
            try:
                header_dict = json.loads(headers)
                if not isinstance(header_dict, dict):
                    return "❌ 'headers' must be a JSON object"
            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON in 'headers': {e}"

        # Build server config
        server_config = {
            "url": url,
            "headers": header_dict,
        }

        # Save config
        config["mcpServers"][name] = server_config
        storage.save_remote_config(config)

        return (
            f"✅ Added remote MCP server '{name}'\n\n"
            f"**URL:** {url}\n"
            f"**Headers:** {len(header_dict)} header(s)\n\n"
            f"Next steps:\n"
            f"• Use `mcp_reload` to load tools from this server\n"
            f"• Use `mcp_show_server('{name}')` to see details\n"
            f"• Use `mcp_list_servers` to see all servers"
        )

    except ValueError as e:
        return f"❌ Validation error: {e}"
    except Exception as e:
        return f"❌ Error adding remote server: {e}"


@tool
def mcp_remove_server(name: str) -> str:
    """Remove an MCP server (local or remote).

    This removes the server configuration. Tools from this server
    will no longer be available after reload.

    Args:
        name: Server name to remove

    Returns:
        Confirmation message

    Examples:
        >>> mcp_remove_server("fetch")
        "✅ Removed server 'fetch'"
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)

        # Check local config
        local_config = storage.load_local_config()
        if name in local_config["mcpServers"]:
            del local_config["mcpServers"][name]
            storage.save_local_config(local_config)
            return (
                f"✅ Removed server '{name}'\n\n"
                f"Use `mcp_reload` to update available tools."
            )

        # Check remote config
        remote_config = storage.load_remote_config()
        if name in remote_config["mcpServers"]:
            del remote_config["mcpServers"][name]
            storage.save_remote_config(remote_config)
            return (
                f"✅ Removed server '{name}'\n\n"
                f"Use `mcp_reload` to update available tools."
            )

        return (
            f"❌ Server '{name}' not found.\n\n"
            f"Use `mcp_list_servers` to see available servers."
        )

    except Exception as e:
        return f"❌ Error removing server: {e}"


@tool
def mcp_show_server(name: str) -> str:
    """Show detailed information about an MCP server.

    Args:
        name: Server name to show

    Returns:
        Detailed server configuration

    Examples:
        >>> mcp_show_server("fetch")
        "Server: fetch\\nCommand: uvx\\nArgs: ['--port', '3000']..."
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)

        # Check local config
        local_config = storage.load_local_config()
        if name in local_config["mcpServers"]:
            server = local_config["mcpServers"][name]
            return (
                f"**Server:** {name} (Local/stdio)\n\n"
                f"**Command:** `{server.get('command', 'N/A')}`\n"
                f"**Args:** `{server.get('args', [])}`\n"
                f"**Working Directory:** `{server.get('cwd', 'default')}`\n"
                f"**Environment Variables:** {len(server.get('env', {}))} var(s)\n\n"
                f"Configured at: {local_config.get('updated_at', 'N/A')}"
            )

        # Check remote config
        remote_config = storage.load_remote_config()
        if name in remote_config["mcpServers"]:
            server = remote_config["mcpServers"][name]
            headers = server.get("headers", {})
            header_list = [f"{k}: ***" for k in headers.keys()]  # Hide values

            return (
                f"**Server:** {name} (Remote HTTP/SSE)\n\n"
                f"**URL:** `{server.get('url', 'N/A')}`\n"
                f"**Headers:** {len(headers)} header(s)\n"
                f"{chr(10).join(header_list) if header_list else 'No headers'}\n\n"
                f"Configured at: {remote_config.get('updated_at', 'N/A')}"
            )

        return (
            f"❌ Server '{name}' not found.\n\n"
            f"Use `mcp_list_servers` to see available servers."
        )

    except Exception as e:
        return f"❌ Error showing server: {e}"


@tool
def mcp_export_config() -> str:
    """Export MCP configuration as JSON.

    This exports both local and remote MCP configurations as a JSON
    string that can be imported later or shared with others.

    Returns:
        JSON string of complete MCP configuration

    Examples:
        >>> mcp_export_config()
        '{"local": {...}, "remote": {...}, "exported_at": "..."}'
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)
        local = storage.load_local_config()
        remote = storage.load_remote_config()

        export = {
            "local": local,
            "remote": remote,
            "exported_at": _utc_now(),
        }

        return (
            f"✅ MCP configuration exported\n\n"
            f"```json\n{json.dumps(export, indent=2)}\n```\n\n"
            f"You can import this later with `mcp_import_config`."
        )

    except Exception as e:
        return f"❌ Error exporting config: {e}"


@tool
def mcp_import_config(config_json: str) -> str:
    """Import MCP configuration from JSON.

    This imports MCP server configurations from a JSON export.
    You can use this to restore from a backup or share configs between conversations.

    Args:
        config_json: JSON string containing MCP configuration

    Returns:
        Confirmation message

    Examples:
        >>> mcp_import_config('{"local": {...}, "remote": {...}}')
        "✅ Imported 2 local and 1 remote server(s)"
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        import json
        export = json.loads(config_json)

        # Validate structure
        if not isinstance(export, dict):
            return "❌ Config must be a JSON object"

        local = export.get("local", {})
        remote = export.get("remote", {})

        storage = UserMCPStorage(thread_id)

        imported_count = 0

        # Import local servers
        if "mcpServers" in local:
            local_config = storage.load_local_config()
            existing_names = set(local_config["mcpServers"].keys())

            for name, server in local["mcpServers"].items():
                if name in existing_names:
                    return f"❌ Server '{name}' already exists. Remove it first or rename in import."
                local_config["mcpServers"][name] = server
                imported_count += 1

            storage.save_local_config(local_config)

        # Import remote servers
        if "mcpServers" in remote:
            remote_config = storage.load_remote_config()
            existing_names = set(remote_config["mcpServers"].keys())

            for name, server in remote["mcpServers"].items():
                if name in existing_names:
                    return f"❌ Server '{name}' already exists. Remove it first or rename in import."
                remote_config["mcpServers"][name] = server
                imported_count += 1

            storage.save_remote_config(remote_config)

        return (
            f"✅ Imported {imported_count} server(s)\n\n"
            f"Use `mcp_list_servers` to see all servers.\n"
            f"Use `mcp_reload` to load tools from imported servers."
        )

    except json.JSONDecodeError as e:
        return f"❌ Invalid JSON: {e}"
    except Exception as e:
        return f"❌ Error importing config: {e}"


@tool
def mcp_list_backups() -> str:
    """List available MCP configuration backups.

    Backups are created automatically before making changes.
    Use this to see available restore points.

    Returns:
        List of backup files with timestamps

    Examples:
        >>> mcp_list_backups()
        "**Backups for mcp.json:**\\n\\n| Name | Size | Timestamp |..."
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        storage = UserMCPStorage(thread_id)

        # List backups for both config types
        local_backups = storage.list_backups("mcp.json")
        remote_backups = storage.list_backups("mcp_remote.json")

        lines = []

        if local_backups:
            lines.append("**Backups for mcp.json (Local):**")
            lines.append("| Name | Size | Modified |")
            lines.append("|------|------|----------|")
            for backup in local_backups[:5]:  # Show last 5
                size_kb = backup["size"] / 1024
                lines.append(
                    f"| {backup['name']} | {size_kb:.1f} KB | {backup['modified']} |"
                )

        if remote_backups:
            if local_backups:
                lines.append("")  # Blank line
            lines.append("**Backups for mcp_remote.json (Remote):**")
            lines.append("| Name | Size | Modified |")
            lines.append("|------|------|----------|")
            for backup in remote_backups[:5]:  # Show last 5
                size_kb = backup["size"] / 1024
                lines.append(
                    f"| {backup['name']} | {size_kb:.1f} KB | {backup['modified']} |"
                )

        if not local_backups and not remote_backups:
            return "No backups available yet."

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error listing backups: {e}"


@tool
def mcp_reload(load_skills: bool = True) -> str:
    """Reload MCP tools from configuration.

    This forces a reload of all MCP tools from the current thread's configuration.
    Use this after adding/removing servers to apply the changes.

    The reload clears any cached MCP connections and loads fresh tool lists.

    Args:
        load_skills: If True (default), also load approved skills

    Returns:
        Confirmation message with reload status

    Examples:
        >>> mcp_reload()
        "✅ MCP tools reloaded. 5 tools loaded from 2 servers."
    """
    thread_id = get_thread_id()
    if not thread_id:
        return "❌ No thread context available."

    try:
        # Import the reload function
        from executive_assistant.tools.registry import clear_mcp_cache
        from executive_assistant.skills.tool import load_skill

        # Clear the MCP tool cache
        cleared = clear_mcp_cache()

        # Count servers before reload
        storage = UserMCPStorage(thread_id)
        local_servers = storage.load_local_config()["mcpServers"]
        remote_servers = storage.load_remote_config()["mcpServers"]

        total_servers = len(local_servers) + len(remote_servers)

        # Load approved skills if requested
        skills_loaded = []
        skills_failed = []

        if load_skills:
            approved_skills = get_approved_skills()
            for skill_name in approved_skills:
                try:
                    result = load_skill(skill_name)
                    if "✅" in result or "#" in result:
                        skills_loaded.append(skill_name)
                    else:
                        skills_failed.append(skill_name)
                except Exception:
                    skills_failed.append(skill_name)

        # Build response
        if total_servers == 0 and not skills_loaded:
            return (
                "✅ MCP cache cleared.\n\n"
                "No MCP servers configured. Tools will load from admin config only."
            )

        lines = ["✅ MCP tools reloaded.", ""]

        if total_servers > 0:
            lines.append("**MCP Servers:**")
            lines.append(f"- {len(local_servers)} local server(s)")
            lines.append(f"- {len(remote_servers)} remote server(s)")
            lines.append(f"- **Total:** {total_servers} server(s)")
            lines.append("")

        if skills_loaded:
            lines.append(f"📚 **Skills Loaded:** {len(skills_loaded)}")
            for skill in skills_loaded:
                lines.append(f"  • {skill}")
            lines.append("")

        if skills_failed:
            lines.append(f"⚠️ **Skills Failed to Load:** {len(skills_failed)}")
            for skill in skills_failed:
                lines.append(f"  • {skill}")
            lines.append("")

        lines.append(
            "Tools from these servers will be available in your next message.\n"
            f"Use `mcp_list_servers` to see all configured servers."
        )

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error reloading MCP tools: {e}"


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@tool
def mcp_list_pending_skills() -> str:
    """List all pending skill proposals awaiting approval.

    When MCP servers are added, associated skills are proposed automatically.
    Use this tool to see which skills are waiting for your approval.

    Returns:
        List of pending skill proposals with details

    Examples:
        >>> mcp_list_pending_skills()
        "**Pending Skills:**\\n\\n### 1. web_scraping\\n**Source:** fetch server..."
    """
    from executive_assistant.storage.mcp_skill_storage import list_pending_skills

    try:
        proposals = list_pending_skills()

        if not proposals:
            return (
                "✅ No pending skill proposals.\n\n"
                "Skills are automatically proposed when you add MCP servers.\n"
                "Add an MCP server to see related skill proposals."
            )

        lines = ["**Pending Skill Proposals:**\n"]
        lines.append(f"Found {len(proposals)} proposal(s) awaiting your approval.\n")

        for idx, proposal in enumerate(proposals, 1):
            lines.append(f"### {idx}. {proposal.skill_name}")
            lines.append(f"**Source Server:** {proposal.source_server}")
            lines.append(f"**Created:** {proposal.created_at}")
            lines.append(f"**Why it's recommended:** {proposal.reason}")
            lines.append("")
            lines.append("**Actions:**")
            lines.append(f"• Approve: `mcp_approve_skill('{proposal.skill_name}')`")
            lines.append(f"• Reject: `mcp_reject_skill('{proposal.skill_name}')`")
            lines.append("")

        lines.append("**Summary:**")
        lines.append(
            "These skills teach the agent how to use MCP tools effectively. "
            "Approve skills that you want to load for this conversation."
        )

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error listing pending skills: {e}"


@tool
def mcp_approve_skill(skill_name: str) -> str:
    """Approve a pending skill proposal.

    Approved skills will be loaded into the agent's context on the next reload.
    Use this after reviewing a skill proposal with `mcp_list_pending_skills`.

    Args:
        skill_name: Name of the skill to approve

    Returns:
        Confirmation message

    Examples:
        >>> mcp_approve_skill("web_scraping")
        "✅ Approved skill 'web_scraping'\\n\\nUse mcp_reload to load it..."
    """
    try:
        # Load the proposal
        proposal = load_pending_skill(skill_name)

        if not proposal:
            return (
                f"❌ Pending skill '{skill_name}' not found.\n\n"
                f"Use `mcp_list_pending_skills` to see available proposals."
            )

        if proposal.status == "approved":
            return (
                f"✅ Skill '{skill_name}' is already approved.\n\n"
                f"Use `mcp_reload` to load approved skills."
            )

        if proposal.status == "rejected":
            return (
                f"❌ Skill '{skill_name}' was previously rejected.\n\n"
                f"You can approve it anyway, but you may want to review it first."
            )

        # Approve the skill
        approve_skill_storage(skill_name)

        return (
            f"✅ Approved skill '{skill_name}'\n\n"
            f"**Source:** {proposal.source_server} server\n"
            f"**Reason:** {proposal.reason}\n\n"
            f"Next steps:\n"
            f"• Use `mcp_reload` to load approved skills into context\n"
            f"• Use `mcp_list_pending_skills` to see remaining proposals"
        )

    except ValueError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        return f"❌ Error approving skill: {e}"


@tool
def mcp_reject_skill(skill_name: str) -> str:
    """Reject a pending skill proposal.

    Rejected skills will not be loaded. You can still approve them later
    if you change your mind.

    Args:
        skill_name: Name of the skill to reject

    Returns:
        Confirmation message

    Examples:
        >>> mcp_reject_skill("web_scraping")
        "✅ Rejected skill 'web_scraping'\\n\\nYou can approve it later..."
    """
    try:
        # Load the proposal
        proposal = load_pending_skill(skill_name)

        if not proposal:
            return (
                f"❌ Pending skill '{skill_name}' not found.\n\n"
                f"Use `mcp_list_pending_skills` to see available proposals."
            )

        if proposal.status == "rejected":
            return (
                f"✅ Skill '{skill_name}' is already rejected.\n\n"
                f"You can approve it later with `mcp_approve_skill('{skill_name}')`."
            )

        if proposal.status == "approved":
            return (
                f"⚠️ Skill '{skill_name}' was already approved.\n\n"
                f"Rejecting it now means it won't be loaded on next reload.\n"
                f"Use `mcp_approve_skill('{skill_name}')` to re-approve it."
            )

        # Reject the skill
        reject_skill_storage(skill_name)

        return (
            f"✅ Rejected skill '{skill_name}'\n\n"
            f"**Source:** {proposal.source_server} server\n\n"
            f"You can approve it later:\n"
            f"• `mcp_approve_skill('{skill_name}')`"
        )

    except ValueError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        return f"❌ Error rejecting skill: {e}"


@tool
def mcp_edit_skill(skill_name: str, content: str) -> str:
    """Edit a pending skill's content before approving.

    Use this to customize a skill's content to better fit your needs.
    The skill will remain pending until you approve it.

    Args:
        skill_name: Name of the skill to edit
        content: New content for the skill (markdown format)

    Returns:
        Confirmation message

    Examples:
        >>> mcp_edit_skill(
        ...     "web_scraping",
        ...     "# Custom Web Scraping Guide\\n\\nThis is my custom guide..."
        ... )
        "✅ Updated skill 'web_scraping'\\n\\nUse mcp_approve_skill to approve..."
    """
    try:
        # Load the proposal
        proposal = load_pending_skill(skill_name)

        if not proposal:
            return (
                f"❌ Pending skill '{skill_name}' not found.\n\n"
                f"Use `mcp_list_pending_skills` to see available proposals."
            )

        # Update content
        proposal.content = content
        save_pending_skill(proposal)

        return (
            f"✅ Updated skill '{skill_name}'\n\n"
            f"**Source:** {proposal.source_server} server\n"
            f"**Status:** {proposal.status}\n"
            f"**Content length:** {len(content)} characters\n\n"
            f"Next steps:\n"
            f"• Use `mcp_approve_skill('{skill_name}')` to approve the updated skill\n"
            f"• Use `mcp_reload` to load approved skills into context"
        )

    except Exception as e:
        return f"❌ Error editing skill: {e}"


@tool
def mcp_show_skill(skill_name: str) -> str:
    """Show detailed information about a skill proposal.

    Use this to review a skill's content before approving it.

    Args:
        skill_name: Name of the skill to show

    Returns:
        Detailed skill information

    Examples:
        >>> mcp_show_skill("web_scraping")
        "**Skill:** web_scraping\\n\\n**Source:** fetch server..."
    """
    try:
        # Load the proposal
        proposal = load_pending_skill(skill_name)

        if not proposal:
            return (
                f"❌ Skill '{skill_name}' not found.\n\n"
                f"Use `mcp_list_pending_skills` to see available proposals."
            )

        lines = [
            f"**Skill:** {proposal.skill_name}",
            "",
            f"**Source Server:** {proposal.source_server}",
            f"**Status:** {proposal.status}",
            f"**Created:** {proposal.created_at}",
            "",
            f"**Why it's recommended:**",
            f"{proposal.reason}",
            "",
        ]

        if proposal.content:
            lines.append("**Skill Content:**")
            lines.append("")
            lines.append("```markdown")
            lines.append(proposal.content)
            lines.append("```")
            lines.append("")
        else:
            lines.append("**Skill Content:** (will be loaded from skill file)")
            lines.append("")

        lines.append("**Actions:**")
        if proposal.status == "pending":
            lines.append(f"• Approve: `mcp_approve_skill('{skill_name}')`")
            lines.append(f"• Reject: `mcp_reject_skill('{skill_name}')`")
            lines.append(f"• Edit: `mcp_edit_skill('{skill_name}', '<content>')`")
        elif proposal.status == "approved":
            lines.append(f"• Load approved skills: `mcp_reload`")
        elif proposal.status == "rejected":
            lines.append(f"• Re-approve: `mcp_approve_skill('{skill_name}')`")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error showing skill: {e}"
