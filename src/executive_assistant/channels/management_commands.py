"""Management slash commands for /mem, /vs, /db, /file, /meta.

These commands provide direct access to storage systems without needing
to go through the agent's tool calling mechanism.
"""

import json
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from executive_assistant.config import settings
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id
from executive_assistant.storage.group_storage import (
    ensure_thread_group,
    set_group_id as set_workspace_context,
    set_user_id as set_workspace_user_id,
    clear_group_id as clear_workspace_context,
    clear_user_id as clear_workspace_user_id,
)
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
from executive_assistant.storage.mem_storage import get_mem_storage
from executive_assistant.storage.sqlite_db_storage import get_sqlite_db
from executive_assistant.storage.shared_db_storage import get_shared_db_storage
from executive_assistant.storage.meta_registry import load_meta, refresh_meta, format_meta
from executive_assistant.tools.reminder_tools import (
    reminder_set,
    reminder_list,
    reminder_cancel,
    reminder_edit,
)

ALLOWED_MEMORY_TYPES = {"profile", "preference", "fact", "task", "note"}
COMMON_MEMORY_KEYS = {
    "timezone",
    "language",
    "name",
    "role",
    "job",
    "company",
    "location",
    "email",
    "phone",
    "pronouns",
}


def _get_thread_id(update: Update) -> str:
    """Get thread_id from Telegram update."""
    return f"telegram:{update.effective_chat.id}"


def _get_chat_type(update: Update) -> str | None:
    if update.effective_chat:
        return update.effective_chat.type
    return None


async def _set_context(thread_id: str, chat_type: str | None = None) -> None:
    """Set thread, group, and user context for storage operations."""
    set_thread_id(thread_id)
    user_id_for_storage = sanitize_thread_id_to_user_id(thread_id)
    is_group_chat = chat_type in {"group", "supergroup"}
    if is_group_chat:
        group_id = await ensure_thread_group(thread_id, user_id_for_storage)
        set_workspace_context(group_id)
    else:
        clear_workspace_context()
    set_workspace_user_id(user_id_for_storage)


def _clear_context() -> None:
    """Clear thread_id context."""
    clear_thread_id()
    clear_workspace_context()
    clear_workspace_user_id()


# ==================== /mem COMMAND ====================

async def mem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mem command for memory management.

    Usage:
        /mem                    - List all memories
        /mem list [type]        - List memories by type
        /mem add <content>       - Add a new memory
        /mem search <query>     - Search memories
        /mem forget <id|key>    - Forget a memory
        /mem update <id> <text> - Update a memory
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []

    if not args:
        await _mem_overview(update, thread_id, chat_type)
        return

    action = args[0].lower()

    if action == "list":
        # /mem list [type]
        mem_type = args[1] if len(args) > 1 else None
        await _mem_list(update, thread_id, mem_type, chat_type)
    elif action == "add":
        # /mem add <content> [type] [key]
        content, mem_type, key = _parse_mem_add_args(args)
        if not content:
            await update.message.reply_text(
                "Usage: /mem add <content> [type] [key]\n"
                "Tip: use type=<type> and key=<key> for clarity."
            )
        else:
            await _mem_add(update, thread_id, content, mem_type, key, chat_type)
    elif action == "search":
        # /mem search <query>
        query = " ".join(args[1:]) if len(args) > 1 else ""
        if not query:
            await update.message.reply_text("Usage: /mem search <query>")
        else:
            await _mem_search(update, thread_id, query, chat_type)
    elif action == "forget":
        # /mem forget <id|key>
        target = " ".join(args[1:]) if len(args) > 1 else ""
        if not target:
            await update.message.reply_text("Usage: /mem forget <memory_id or key>")
        else:
            await _mem_forget(update, thread_id, target, chat_type)
    elif action == "update":
        # /mem update <id> <content>
        if len(args) < 3:
            await update.message.reply_text("Usage: /mem update <memory_id> <new content>")
        else:
            memory_id = args[1]
            content = " ".join(args[2:])
            await _mem_update(update, thread_id, memory_id, content, chat_type)
    else:
        await _mem_help(update)


# ==================== /reminder COMMAND ====================

def _parse_reminder_set_args(args: list[str]) -> tuple[str | None, str | None, str]:
    """Parse reminder set args into time, message, recurrence."""
    if not args:
        return None, None, ""

    text = " ".join(args)
    recurrence = ""

    tokens = text.split()
    remaining_tokens: list[str] = []
    for token in tokens:
        if token.startswith("recurrence="):
            recurrence = token.split("=", 1)[1]
        else:
            remaining_tokens.append(token)
    text = " ".join(remaining_tokens)

    for sep in (" | ", " -- "):
        if sep in text:
            time_str, message = text.split(sep, 1)
            return time_str.strip() or None, message.strip() or None, recurrence

    parts = text.split()
    if len(parts) < 2:
        return None, None, recurrence
    time_str = parts[0]
    message = " ".join(parts[1:])
    return time_str, message, recurrence


def _parse_reminder_edit_args(args: list[str]) -> tuple[int | None, str | None, str | None, str]:
    """Parse reminder edit args into id, time, message, recurrence."""
    if len(args) < 2:
        return None, None, None, ""
    try:
        reminder_id = int(args[1])
    except ValueError:
        return None, None, None, ""

    text = " ".join(args[2:])
    recurrence = ""
    message: str | None = None
    time_str: str | None = None

    tokens = text.split()
    remaining_tokens: list[str] = []
    for token in tokens:
        if token.startswith("recurrence="):
            recurrence = token.split("=", 1)[1]
        elif token.startswith("time="):
            time_str = token.split("=", 1)[1]
        elif token.startswith("message="):
            message = token.split("=", 1)[1]
        else:
            remaining_tokens.append(token)

    if message is None and time_str is None and remaining_tokens:
        text = " ".join(remaining_tokens)
        for sep in (" | ", " -- "):
            if sep in text:
                time_str, message = text.split(sep, 1)
                return reminder_id, time_str.strip() or None, message.strip() or None, recurrence

        parts = text.split()
        if len(parts) >= 2:
            time_str = parts[0]
            message = " ".join(parts[1:])

    return reminder_id, time_str, message, recurrence


async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminder command for reminders."""
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []

    if not args:
        await _reminder_help(update)
        return

    action = args[0].lower()

    await _set_context(thread_id, chat_type)
    try:
        if action == "list":
            status = args[1].lower() if len(args) > 1 else ""
            result = await reminder_list.ainvoke({"status": status})
            await update.message.reply_text(result)
        elif action == "set":
            time_str, message, recurrence = _parse_reminder_set_args(args[1:])
            if not time_str or not message:
                await update.message.reply_text(
                    "Usage: /reminder set <time> <message>\n"
                    "Tip: use ' | ' for multi-word time, e.g. /reminder set tomorrow 9am | standup\n"
                    "Optional: recurrence=<daily|weekly|...>"
                )
                return
            result = await reminder_set.ainvoke({"message": message, "time": time_str, "recurrence": recurrence})
            await update.message.reply_text(result)
        elif action == "cancel":
            if len(args) < 2:
                await update.message.reply_text("Usage: /reminder cancel <id>")
                return
            try:
                reminder_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Reminder ID must be a number.")
                return
            result = await reminder_cancel.ainvoke({"reminder_id": reminder_id})
            await update.message.reply_text(result)
        elif action == "edit":
            reminder_id, time_str, message, recurrence = _parse_reminder_edit_args(args)
            if reminder_id is None:
                await update.message.reply_text(
                    "Usage: /reminder edit <id> <time> <message>\n"
                    "Tip: use time=<...> message=<...> recurrence=<...> for clarity."
                )
                return
            result = await reminder_edit.ainvoke({
                "reminder_id": reminder_id,
                "message": message or "",
                "time": time_str or "",
                "recurrence": recurrence or "",
            })
            await update.message.reply_text(result)
        else:
            await _reminder_help(update)
    finally:
        _clear_context()


async def _reminder_help(update: Update) -> None:
    """Show /reminder help."""
    help_text = (
        "⏰ Reminders\n\n"
        "Usage:\n"
        "• /reminder list [status]\n"
        "• /reminder set <time> <message>\n"
        "• /reminder cancel <id>\n"
        "• /reminder edit <id> <time> <message>\n\n"
        "Tips:\n"
        "- Use ' | ' to separate time and message when time has spaces\n"
        "- Add recurrence=<daily|weekly|...> when setting/editing\n\n"
        "Examples:\n"
        "/reminder set tomorrow 9am | standup\n"
        "/reminder list pending\n"
        "/reminder cancel 12"
    )
    await update.message.reply_text(help_text)


async def _mem_help(update: Update) -> None:
    """Show /mem help."""
    help_text = (
        "💾 *Memory Management*\n\n"
        "Usage:\n"
        "• `/mem` - Show counts and commands\n"
        "• `/mem list [type]` - List by type (profile|preference|fact|task|note)\n"
        "• `/mem add <content> [type] [key]` - Add a memory (or use type= / key=)\n"
        "• `/mem search <query>` - Search memories\n"
        "• `/mem forget <id|key>` - Forget a memory\n"
        "• `/mem update <id> <text>` - Update a memory\n\n"
        "Examples:\n"
        "• `/mem add I prefer tea over coffee type=preference`\n"
        "• `/mem add My office timezone is EST key=timezone`\n"
        "• `/mem list preference`\n"
        "• `/mem search timezone`\n"
        "• `/mem forget abc123`\n"
        "• `/mem update abc123 New content here`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _mem_overview(update: Update, thread_id: str, chat_type: str | None) -> None:
    """Show memory counts and commands."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()
        memories = storage.list_memories(memory_type=None, status="active")
        total = len(memories)

        by_type: dict[str, int] = {}
        for m in memories:
            by_type[m["memory_type"]] = by_type.get(m["memory_type"], 0) + 1

        type_summary = ", ".join(
            f"{mtype}:{count}" for mtype, count in sorted(by_type.items())
        ) or "none"

        help_text = (
            "💾 *Memory Management*\n\n"
            f"Memories: {total}\n"
            f"By type: {type_summary}\n\n"
            "Commands:\n"
            "• `/mem list [type]`\n"
            "• `/mem add <content> [type] [key]`\n"
            "• `/mem search <query>`\n"
            "• `/mem forget <id|key>`\n"
            "• `/mem update <id> <text>`\n\n"
            "Example:\n"
            "`/mem add I prefer tea over coffee type=preference`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading memories: {e}")
    finally:
        _clear_context()


def _parse_mem_add_args(args: list[str]) -> tuple[str, str | None, str | None]:
    """Parse /mem add arguments into content, memory_type, and key."""
    if len(args) < 2:
        return "", None, None

    tokens = args[1:]
    content_tokens: list[str] = []
    mem_type: str | None = None
    key: str | None = None
    explicit_type = False

    def _extract_prefixed(token: str, prefix: str) -> str | None:
        if token.startswith(prefix + "="):
            return token[len(prefix) + 1 :]
        if token.startswith(prefix + ":"):
            return token[len(prefix) + 1 :]
        if token.startswith("--" + prefix + "="):
            return token[len(prefix) + 3 :]
        if token.startswith("--" + prefix + ":"):
            return token[len(prefix) + 3 :]
        return None

    for token in tokens:
        key_val = _extract_prefixed(token, "key")
        if key_val:
            key = key_val
            continue
        type_val = _extract_prefixed(token, "type")
        if type_val:
            mem_type = type_val.lower()
            explicit_type = True
            continue
        content_tokens.append(token)

    if not explicit_type:
        if content_tokens:
            last = content_tokens[-1].lower()
            if last in ALLOWED_MEMORY_TYPES:
                mem_type = content_tokens.pop().lower()
            elif len(content_tokens) >= 2 and content_tokens[-2].lower() in ALLOWED_MEMORY_TYPES:
                mem_type = content_tokens.pop(-2).lower()
                key = content_tokens.pop(-1)
            elif last in COMMON_MEMORY_KEYS:
                key = content_tokens.pop(-1)

    content = " ".join(content_tokens).strip()
    return content, mem_type, key


async def _mem_add(update: Update, thread_id: str, content: str, mem_type: str | None = None, key: str | None = None, chat_type: str | None = None) -> None:
    """Add a memory."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()

        # If key is provided, check if it already exists
        if key:
            existing = storage.get_memory_by_key(key)
            if existing:
                # Update existing memory
                storage.update_memory(existing["id"], content=content)
                await update.message.reply_text(f"✅ Updated memory '{key}': {content[:60]}...")
                return

        # Create new memory
        memory_id = storage.create_memory(
            content=content,
            memory_type=mem_type or "note",
            key=key,
            confidence=1.0
        )

        key_note = f" [{key}]" if key else ""
        type_note = f" ({mem_type or 'note'})"
        await update.message.reply_text(f"✅ Memory saved{key_note}{type_note}: {content[:60]}...")
    except Exception as e:
        await update.message.reply_text(f"Error adding memory: {e}")
    finally:
        _clear_context()


async def _mem_list(update: Update, thread_id: str, mem_type: str | None = None, chat_type: str | None = None) -> None:
    """List memories."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()
        memories = storage.list_memories(memory_type=mem_type, status="active")

        if not memories:
            msg = "💾 *No memories found*\n\nUse `/remember <content>` to save memories."
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        lines = [f"💾 *Your Memories* ({len(memories)} total)\n"]

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for m in memories:
            by_type.setdefault(m["memory_type"], []).append(m)

        for mtype, items in by_type.items():
            lines.append(f"\n*{mtype.capitalize()}* ({len(items)}):")
            for m in items[:5]:  # Max 5 per type
                key_note = f" [{m['key']}]" if m.get("key") else ""
                lines.append(f"  • {m['content'][:60]}{'...' if len(m['content']) > 60 else ''}{key_note}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing memories: {e}")
    finally:
        _clear_context()


async def _mem_search(update: Update, thread_id: str, query: str, chat_type: str | None) -> None:
    """Search memories."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()
        memories = storage.search_memories(query, limit=10)

        if not memories:
            await update.message.reply_text(f"💾 No memories found matching: {query}")
            return

        lines = [f"💾 *Memories matching '{query}'* ({len(memories)} found)\n"]
        for m in memories:
            key_note = f" [{m['key']}]" if m.get("key") else ""
            lines.append(f"  • {m['content'][:80]}{'...' if len(m['content']) > 80 else ''}{key_note}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error searching memories: {e}")
    finally:
        _clear_context()


async def _mem_forget(update: Update, thread_id: str, target: str, chat_type: str | None) -> None:
    """Forget a memory by ID or key."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()

        # Try as key first
        memory = storage.get_memory_by_key(target)
        if memory:
            success = storage.delete_memory(memory["id"])
            if success:
                await update.message.reply_text(f"✅ Forgot memory: {memory['content'][:50]}...")
                return

        # Try as ID
        success = storage.delete_memory(target)
        if success:
            await update.message.reply_text(f"✅ Forgot memory: {target[:8]}...")
        else:
            await update.message.reply_text(f"❌ Memory not found: {target}")
    except Exception as e:
        await update.message.reply_text(f"Error forgetting memory: {e}")
    finally:
        _clear_context()


async def _mem_update(update: Update, thread_id: str, memory_id: str, content: str, chat_type: str | None) -> None:
    """Update a memory."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()
        success = storage.update_memory(memory_id, content=content)
        if success:
            await update.message.reply_text(f"✅ Memory updated: {memory_id[:8]}...\nNew content: {content[:60]}")
        else:
            await update.message.reply_text(f"❌ Memory not found: {memory_id}")
    except Exception as e:
        await update.message.reply_text(f"Error updating memory: {e}")
    finally:
        _clear_context()


# ==================== /vs COMMAND ====================

async def vs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /vs command for Vector Store management.

    Usage:
        /vs                        - List all VS tables
        /vs store <table> <json>   - Store documents
        /vs search <query> [table] - Search VS
        /vs describe <table>       - Describe a table
        /vs delete <table>         - Delete a table
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _vs_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    if action == "list":
        await _vs_list(update, thread_id, scope)
    elif action == "store":
        # /vs store <table_name> <json_documents>
        if len(args) < 3:
            await update.message.reply_text("Usage: /vs store <table_name> <json_documents>")
        else:
            table_name = args[1]
            documents = " ".join(args[2:])
            await _vs_store(update, thread_id, table_name, documents, scope)
    elif action == "search":
        # /vs search <query> [table_name]
        query = args[1] if len(args) > 1 else ""
        table_name = args[2] if len(args) > 2 else ""
        if not query:
            await update.message.reply_text("Usage: /vs search <query> [table_name]")
        else:
            await _vs_search(update, thread_id, query, table_name, scope)
    elif action == "describe":
        # /vs describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /vs describe <table_name>")
        else:
            await _vs_describe(update, thread_id, args[1], scope)
    elif action == "delete":
        # /vs delete <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /vs delete <table_name>")
        else:
            await _vs_delete(update, thread_id, args[1], scope)
    else:
        await _vs_help(update)


async def _vs_help(update: Update) -> None:
    """Show /vs help."""
    help_text = (
        "🔍 *Vector Store Management*\n\n"
        "Usage:\n"
        "• `/vs` - Show counts and commands\n"
        "• `/vs store <table> <json>` - Store documents\n"
        "• `/vs search <query> [table]` - Search\n"
        "• `/vs describe <table>` - Describe table\n"
        "• `/vs delete <table>` - Delete table\n"
        "• Add `scope=shared` to use shared VS\n\n"
        "Example:\n"
        "`/vs store notes [{\"content\": \"Meeting notes\"}]`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _vs_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show VS counts and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.lancedb_storage import list_lancedb_collections

        collections = list_lancedb_collections() if scope == "context" else list_lancedb_collections("shared")
        total = len(collections)

        help_text = (
            "🔍 *Vector Store Management*\n\n"
            f"Collections: {total}\n\n"
            "Commands:\n"
            "• `/vs list`\n"
            "• `/vs store <table> <json>`\n"
            "• `/vs search <query> [table]`\n"
            "• `/vs describe <table>`\n"
            "• `/vs delete <table>`\n"
            "• Add `scope=shared` to use shared VS\n\n"
            "Example:\n"
            "`/vs store notes [{\"content\": \"Meeting notes\"}]`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing VS: {e}")
    finally:
        _clear_context()


async def _vs_list(update: Update, thread_id: str, scope: str) -> None:
    """List VS tables."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import vs_list

        result = vs_list.invoke({"scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error listing VS: {e}")
    finally:
        _clear_context()


async def _vs_store(update: Update, thread_id: str, table_name: str, documents: str, scope: str) -> None:
    """Store documents in VS."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import create_vs_collection

        result = create_vs_collection.invoke({"collection_name": table_name, "documents": documents, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error storing documents: {e}")
    finally:
        _clear_context()


async def _vs_search(update: Update, thread_id: str, query: str, table_name: str, scope: str) -> None:
    """Search VS."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import search_vs

        result = search_vs.invoke({"query": query, "collection_name": table_name, "limit": 5, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error searching VS: {e}")
    finally:
        _clear_context()


async def _vs_describe(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Describe VS table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import describe_vs_collection

        result = describe_vs_collection.invoke({"collection_name": table_name, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error describing table: {e}")
    finally:
        _clear_context()


async def _vs_delete(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Delete VS table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import drop_vs_collection

        result = drop_vs_collection.invoke({"collection_name": table_name, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error deleting table: {e}")
    finally:
        _clear_context()


# ==================== /db COMMAND ====================

def _db_execute(storage, sql: str) -> list[tuple]:
    cursor = storage.conn.execute(sql)
    if cursor.description is None:
        storage.commit()
        return []
    return cursor.fetchall()


def _parse_scope(args: list[str]) -> tuple[str, list[str]]:
    scope = "context"
    cleaned: list[str] = []
    for arg in args:
        lowered = arg.lower()
        if lowered.startswith("scope=") or lowered.startswith("--scope="):
            _, value = lowered.split("=", 1)
            if value in {"context", "shared"}:
                scope = value
                continue
        cleaned.append(arg)
    return scope, cleaned


def _get_db_storage_for_scope(scope: str):
    if scope == "shared":
        return get_shared_db_storage()
    return get_sqlite_db()


def _get_user_files_path(thread_id: str) -> Path:
    from executive_assistant.storage.group_storage import get_user_id

    user_id = get_user_id()
    if user_id:
        return settings.get_user_files_path(user_id)

    user_id = sanitize_thread_id_to_user_id(thread_id)
    return settings.get_user_files_path(user_id)


def _get_files_path_for_scope(thread_id: str, scope: str) -> Path:
    if scope == "shared":
        return settings.get_shared_files_path()
    return _get_user_files_path(thread_id)


async def db_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /db command for database management.

    Usage:
        /db                          - List all tables
        /db create <table> <json>    - Create table
        /db insert <table> <json>    - Insert data
        /db query <sql>              - Run SQL query
        /db describe <table>         - Describe table
        /db drop <table>             - Drop table
        /db export <table> <file>    - Export table
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _db_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    if action == "list":
        await _db_list(update, thread_id, scope)
    elif action == "create":
        # /db create <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db create <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_create(update, thread_id, table_name, data, scope)
    elif action == "insert":
        # /db insert <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db insert <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_insert(update, thread_id, table_name, data, scope)
    elif action == "query":
        # /db query <sql>
        sql = " ".join(args[1:])
        if not sql:
            await update.message.reply_text("Usage: /db query <sql>")
        else:
            await _db_query(update, thread_id, sql, scope)
    elif action == "describe":
        # /db describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /db describe <table_name>")
        else:
            await _db_describe(update, thread_id, args[1], scope)
    elif action == "drop":
        # /db drop <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /db drop <table_name>")
        else:
            await _db_drop(update, thread_id, args[1], scope)
    elif action == "export":
        # /db export <table_name> <filename>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db export <table> <filename>")
        else:
            await _db_export(update, thread_id, args[1], args[2], scope)
    else:
        await _db_help(update)


async def _db_help(update: Update) -> None:
    """Show /db help."""
    help_text = (
        "🗄️ *Database Management*\n\n"
        "Usage:\n"
        "• `/db` - Show counts and commands\n"
        "• `/db create <table> <json>` - Create table\n"
        "• `/db insert <table> <json>` - Insert data\n"
        "• `/db query <sql>` - Run query\n"
        "• `/db describe <table>` - Describe table\n"
        "• `/db drop <table>` - Drop table\n"
        "• `/db export <table> <file>` - Export to CSV\n"
        "• Add `scope=shared` to use shared DB\n\n"
        "Example:\n"
        "`/db create users [{\"name\": \"Alice\", \"age\": 30}]`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _db_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show DB counts and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        tables = storage.list_tables()
        total = len(tables)

        help_text = (
            "🗄️ *Database Management*\n\n"
            f"Tables: {total}\n\n"
            "Commands:\n"
            "• `/db list`\n"
            "• `/db create <table> <json>`\n"
            "• `/db insert <table> <json>`\n"
            "• `/db query <sql>`\n"
            "• `/db describe <table>`\n"
            "• `/db drop <table>`\n"
            "• `/db export <table> <file>`\n"
            "• Add `scope=shared` to use shared DB\n\n"
            "Example:\n"
            "`/db create users [{\"name\": \"Alice\", \"age\": 30}]`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing tables: {e}")
    finally:
        _clear_context()


async def _db_list(update: Update, thread_id: str, scope: str) -> None:
    """List DB tables."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        tables = storage.list_tables()

        if not tables:
            await update.message.reply_text("🗄️ No tables. Use /db create <table> <json> to create one.")
            return

        lines = ["🗄️ Database Tables\n"]
        for table in tables:
            lines.append(f"• {table}")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error listing tables: {e}")
    finally:
        _clear_context()


async def _db_create(update: Update, thread_id: str, table_name: str, data: str, scope: str) -> None:
    """Create DB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"❌ Invalid JSON: {e}")
            return

        storage = _get_db_storage_for_scope(scope)
        storage.create_table_from_data(table_name, parsed, None)
        await update.message.reply_text(f"✅ Table '{table_name}' created with {len(parsed)} rows")
    except Exception as e:
        await update.message.reply_text(f"Error creating table: {e}")
    finally:
        _clear_context()


async def _db_insert(update: Update, thread_id: str, table_name: str, data: str, scope: str) -> None:
    """Insert into DB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"❌ Invalid JSON: {e}")
            return

        storage = _get_db_storage_for_scope(scope)
        storage.append_to_table(table_name, parsed)
        await update.message.reply_text(f"✅ Inserted {len(parsed)} row(s) into '{table_name}'")
    except Exception as e:
        await update.message.reply_text(f"Error inserting data: {e}")
    finally:
        _clear_context()


async def _db_query(update: Update, thread_id: str, sql: str, scope: str) -> None:
    """Run SQL query."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        results = _db_execute(storage, sql)

        if not results:
            await update.message.reply_text(f"🗄️ No results")
            return

        lines = [f"🗄️ *Query Results* ({len(results)} rows)\n"]
        for row in results[:20]:  # Max 20 rows
            lines.append("  " + "\t".join(str(v) if v is not None else "NULL" for v in row))

        if len(results) > 20:
            lines.append(f"\n... ({len(results) - 20} more rows)")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error running query: {e}")
    finally:
        _clear_context()


async def _db_describe(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Describe DB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        columns = storage.get_table_info(table_name)

        lines = [f"🗄️ *Table '{table_name}'*\n"]
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PK" if col["pk"] > 0 else ""
            lines.append(f"  • {col['name']}: {col['type']} {nullable}{pk}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error describing table: {e}")
    finally:
        _clear_context()


async def _db_drop(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Drop DB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        storage.drop_table(table_name)
        await update.message.reply_text(f"✅ Dropped table '{table_name}'")
    except Exception as e:
        await update.message.reply_text(f"Error dropping table: {e}")
    finally:
        _clear_context()


async def _db_export(update: Update, thread_id: str, table_name: str, filename: str, scope: str) -> None:
    """Export DB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)

        files_dir = _get_files_path_for_scope(thread_id, scope)
        files_dir.mkdir(parents=True, exist_ok=True)

        if not filename.endswith(".csv"):
            filename = f"{filename}.csv"

        output_path = files_dir / filename

        storage.export_table(table_name, output_path, "csv")
        await update.message.reply_text(f"✅ Exported '{table_name}' to {filename}")
    except Exception as e:
        await update.message.reply_text(f"Error exporting table: {e}")
    finally:
        _clear_context()


# ==================== /file COMMAND ====================

async def file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /file command for file management.

    Usage:
        /file                    - List files
        /file list [pattern]      - List files with pattern
        /file read <filepath>     - Read file
        /file write <path> <text> - Write to file
        /file create <folder>     - Create folder
        /file delete <path>       - Delete file/folder
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _file_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    if action == "list":
        pattern = args[1] if len(args) > 1 else None
        await _file_list(update, thread_id, pattern, scope)
    elif action == "read":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file read <filepath>")
        else:
            await _file_read(update, thread_id, args[1], scope)
    elif action == "write":
        if len(args) < 3:
            await update.message.reply_text("Usage: /file write <filepath> <content>")
        else:
            filepath = args[1]
            content = " ".join(args[2:])
            await _file_write(update, thread_id, filepath, content, scope)
    elif action == "create":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file create <folder_name>")
        else:
            await _file_create_folder(update, thread_id, args[1], scope)
    elif action == "delete":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file delete <path>")
        else:
            await _file_delete(update, thread_id, args[1], scope)
    else:
        await _file_help(update)


async def _file_help(update: Update) -> None:
    """Show /file help."""
    help_text = (
        "📁 *File Management*\n\n"
        "Usage:\n"
        "• `/file` - Show counts and commands\n"
        "• `/file list [pattern]` - List with pattern\n"
        "• `/file read <path>` - Read file\n"
        "• `/file write <path> <text>` - Write file\n"
        "• `/file create <folder>` - Create folder\n"
        "• `/file delete <path>` - Delete file/folder\n"
        "• Add `scope=shared` to use shared files\n\n"
        "Examples:\n"
        "• `/file list *.txt`\n"
        "• `/file read notes.txt`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _file_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show file counts and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        import os
        from executive_assistant.storage.file_sandbox import get_sandbox, get_shared_sandbox

        sandbox = get_shared_sandbox() if scope == "shared" else get_sandbox()
        total_files = 0
        for _, _, files in os.walk(sandbox.root):
            total_files += len(files)

        help_text = (
            "📁 *File Management*\n\n"
            f"Files: {total_files}\n\n"
            "Commands:\n"
            "• `/file list [pattern]`\n"
            "• `/file read <path>`\n"
            "• `/file write <path> <text>`\n"
            "• `/file create <folder>`\n"
            "• `/file delete <path>`\n"
            "• Add `scope=shared` to use shared files\n\n"
            "Examples:\n"
            "• `/file list *.txt`\n"
            "• `/file read notes.txt`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing files: {e}")
    finally:
        _clear_context()


async def _file_list(update: Update, thread_id: str, pattern: str | None = None, scope: str = "context") -> None:
    """List files."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.file_sandbox import list_files

        if pattern:
            from executive_assistant.storage.file_sandbox import glob_files
            result = glob_files.invoke({"pattern": pattern, "scope": scope})
        else:
            result = list_files.invoke({"scope": scope})

        # Send plain text to avoid Telegram markdown parsing issues
        if "files:" in result.lower() or "found" in result.lower():
            await update.message.reply_text(f"📁 Files\n\n{result}")
        else:
            await update.message.reply_text(f"📁 Files\n\n{result or 'No files found'}")
    except Exception as e:
        await update.message.reply_text(f"Error listing files: {e}")
    finally:
        _clear_context()


async def _file_read(update: Update, thread_id: str, filepath: str, scope: str) -> None:
    """Read file."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.file_sandbox import read_file

        result = read_file.invoke({"file_path": filepath, "scope": scope})

        # Truncate if too long
        if len(result) > 3000:
            result = result[:3000] + "\n\n... (truncated, file too large)"

        await update.message.reply_text(f"📄 *{filepath}*\n\n```\n{result}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading file: {e}")
    finally:
        _clear_context()


async def _file_write(update: Update, thread_id: str, filepath: str, content: str, scope: str) -> None:
    """Write file."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.file_sandbox import write_file

        write_file.invoke({"file_path": filepath, "content": content, "scope": scope})
        await update.message.reply_text(f"✅ Wrote to {filepath}")
    except Exception as e:
        await update.message.reply_text(f"Error writing file: {e}")
    finally:
        _clear_context()


async def _file_create_folder(update: Update, thread_id: str, folder_name: str, scope: str) -> None:
    """Create folder."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.file_sandbox import create_folder

        create_folder.invoke({"path": folder_name, "scope": scope})
        await update.message.reply_text(f"✅ Created folder: {folder_name}")
    except Exception as e:
        await update.message.reply_text(f"Error creating folder: {e}")
    finally:
        _clear_context()


async def _file_delete(update: Update, thread_id: str, path: str, scope: str) -> None:
    """Delete file or folder."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.file_sandbox import delete_folder

        delete_folder.invoke({"path": path, "scope": scope})
        await update.message.reply_text(f"✅ Deleted: {path}")
    except Exception as e:
        await update.message.reply_text(f"Error deleting: {e}")
    finally:
        _clear_context()


# ==================== /meta COMMAND ====================

async def meta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /meta command for system inventory.

    Usage:
        /meta                 - Show current inventory
        /meta refresh         - Rebuild inventory from disk/DB
        /meta json            - Show raw JSON
        /meta refresh json    - Refresh and show JSON
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    args = context.args if context.args else []
    refresh = False
    as_json = False

    for arg in args:
        lower = arg.lower()
        if lower in {"refresh", "rebuild"}:
            refresh = True
        if lower in {"json", "raw"}:
            as_json = True

    if as_json:
        refresh = True

    try:
        await _set_context(thread_id, chat_type)
        meta = await refresh_meta(thread_id) if refresh else load_meta(thread_id)
        if as_json:
            text = json.dumps(meta, indent=2)
            await update.message.reply_text(f"```json\n{text}\n```", parse_mode="Markdown")
        else:
            text = format_meta(meta, markdown=True)
            await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading meta: {e}")
    finally:
        _clear_context()
