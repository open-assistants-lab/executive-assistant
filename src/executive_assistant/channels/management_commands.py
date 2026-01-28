"""Management slash commands for /mem, /vdb, /tdb, /adb, /file, /meta.

These commands provide direct access to storage systems without needing
to go through the agent's tool calling mechanism.
"""

import json
import logging
import html
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from executive_assistant.config import settings

logger = logging.getLogger(__name__)
from executive_assistant.storage.thread_storage import (
    set_thread_id,
    clear_thread_id,
    set_channel,
    set_chat_type,
)
from executive_assistant.storage.mem_storage import get_mem_storage
from executive_assistant.storage.sqlite_db_storage import get_sqlite_db
from executive_assistant.storage.shared_tdb_storage import get_shared_tdb_storage
from executive_assistant.storage.adb_tools import list_adb_tables, query_adb
from executive_assistant.storage.adb_storage import get_adb
from executive_assistant.storage.db_storage import validate_identifier
from executive_assistant.storage.meta_registry import load_meta, refresh_meta, format_meta
from executive_assistant.storage.user_allowlist import (
    add_user,
    remove_user,
    list_users,
    is_admin,
    is_admin_entry,
    is_authorized,
    normalize_entry,
)
from executive_assistant.tools.reminder_tools import (
    reminder_set,
    reminder_list,
    reminder_cancel,
    reminder_edit,
)

from executive_assistant.tools.flow_tools import (
    create_flow,
    list_flows,
    run_flow,
    cancel_flow,
    delete_flow,
)
from executive_assistant.agent.flow_mode import (
    enable_flow_mode,
    disable_flow_mode,
    is_flow_mode_enabled,
)

ALLOWED_MEMORY_TYPES = {"profile", "preference", "fact", "constraint", "style", "context"}
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

_LAST_MEM_LIST: dict[str, list[dict]] = {}

def _get_thread_id(update: Update) -> str:
    """Get thread_id from Telegram update."""
    return f"telegram:{update.effective_chat.id}"

def _get_chat_type(update: Update) -> str | None:
    if update.effective_chat:
        return update.effective_chat.type
    return None

async def _set_context(thread_id: str, chat_type: str | None = None) -> None:
    """Set thread context for storage operations."""
    set_thread_id(thread_id)
    set_channel("telegram")
    set_chat_type("private")

def _clear_context() -> None:
    """Clear thread_id context."""
    clear_thread_id()

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
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /mem {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []

    if not args:
        await _mem_overview(update, thread_id, chat_type)
        return

    action = args[0].lower()

    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /mem action={action} args={args[1:]}")

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
            await update.message.reply_text("Usage: /mem forget <index|key|id>")
        else:
            await _mem_forget(update, thread_id, target, chat_type)
    elif action == "update":
        # /mem update <id> <content>
        if len(args) < 3:
            await update.message.reply_text("Usage: /mem update <index|id> <new content>")
        else:
            memory_id = args[1]
            content = " ".join(args[2:])
            await _mem_update(update, thread_id, memory_id, content, chat_type)
    else:
        await _mem_help(update)

async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /user admin commands."""
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /user {update.message.text or ''}")
    if not is_admin(thread_id):
        await update.message.reply_text("Only admins can manage users.")
        return

    args = context.args if context.args else []
    if not args or args[0].lower() in {"help", "?"}:
        await update.message.reply_text(
            "Usage:\n"
            "/user list\n"
            "/user add <channel:id>\n"
            "/user remove <channel:id>"
        )
        return

    action = args[0].lower()
    if action == "list":
        users = list_users()
        if not users:
            await update.message.reply_text("No users in allowlist.")
        else:
            await update.message.reply_text("Allowlist:\n" + "\n".join(users))
        return

    if action in {"add", "remove"}:
        if len(args) < 2:
            await update.message.reply_text(f"Usage: /user {action} <channel:id>")
            return
        entry_raw = " ".join(args[1:]).strip()
        try:
            entry = normalize_entry(entry_raw)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        if action == "add":
            try:
                added = add_user(entry)
            except PermissionError:
                await update.message.reply_text(
                    f"Allowlist is not writable. Check permissions for {settings.ADMINS_ROOT} (host) or {settings.ADMINS_ROOT} (container)."
                )
                return
            await update.message.reply_text("Added." if added else "Already present.")
            return
        if is_admin_entry(entry):
            await update.message.reply_text("Admins must be managed in docker/config.yaml.")
            return
        try:
            removed = remove_user(entry)
        except PermissionError:
            await update.message.reply_text(
                f"Allowlist is not writable. Check permissions for {settings.ADMINS_ROOT} (host) or {settings.ADMINS_ROOT} (container)."
            )
            return
        await update.message.reply_text("Removed." if removed else "Not found.")
        return

    await update.message.reply_text("Unknown action. Use /user help")

# ==================== /reminder COMMAND ====================

async def _ensure_authorized(update: Update, thread_id: str) -> bool:
    if is_authorized(thread_id):
        return True
    await update.message.reply_text(
        "Access restricted. Ask an admin to add you using /user add <channel:id>. "
        "Use /start to get your ID."
    )
    return False


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
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /reminder {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []

    if not args:
        await _reminder_help(update)
        return

    action = args[0].lower()

    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /reminder action={action} args={args[1:]}")

    await _set_context(thread_id, chat_type)
    try:
        if action == "status":
            enabled = is_flow_mode_enabled(str(update.effective_chat.id))
            status_text = "on" if enabled else "off"
            await update.message.reply_text(f"Flow mode is {status_text}.")
            return
        if action == "on":
            enable_flow_mode(str(update.effective_chat.id))
            await update.message.reply_text("🧐 I will build and test the agents + flow now.")
            return
        if action == "off":
            disable_flow_mode(str(update.effective_chat.id))
            await update.message.reply_text("Flow mode off.")
            return
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
                "message": message or '',
                "time": time_str or '',
                "recurrence": recurrence or '',
            })
            await update.message.reply_text(result)
        else:
            await _reminder_help(update)
    finally:
        _clear_context()

async def _reminder_help(update: Update) -> None:
    """Show /reminder help."""
    help_text = (
        "⏰ <b>Reminders</b>\n\n"
        "Commands:\n"
        "• <code>/reminder list</code>\n"
        "• <code>/reminder add &lt;time&gt; &lt;message&gt;</code>\n"
        "• <code>/reminder edit &lt;id&gt; &lt;time&gt; &lt;message&gt;</code>\n"
        "• <code>/reminder cancel &lt;id&gt;</code>\n"
        "• <code>/reminder help</code>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def _mem_add(update: Update, thread_id: str, content: str, mem_type: str | None = None, key: str | None = None, chat_type: str | None = None) -> None:
    """Add a memory."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()

        # If key is provided, check if it already exists
        if key:
            existing = storage.get_memory_by_key(key)
            if existing:
                existing_content = (existing.get("content") or "").strip()
                if existing_content == content.strip():
                    await update.message.reply_text(f"✅ Memory already exists [{key}]: {content[:60]}...")
                    return
                storage.update_memory(existing["id"], content=content)
                await update.message.reply_text(f"✅ Updated memory '{key}': {content[:60]}...")
                return

        # Avoid duplicates by content when no key is provided
        existing = storage.get_memory_by_content(content)
        if existing:
            await update.message.reply_text(f"✅ Memory already exists: {content[:60]}...")
            return

        # Create new memory
        memory_id = storage.create_memory(
            content=content,
            memory_type=mem_type or "fact",
            key=key,
            confidence=1.0
        )

        key_note = f" [{key}]" if key else ""
        type_note = f" ({mem_type or 'fact'})"
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
            msg = "💾 <b>No memories found</b>\n\nUse <code>/remember &lt;content&gt;</code> to save memories."
            await update.message.reply_text(msg, parse_mode="HTML")
            return

        lines = [f"💾 <b>Your Memories</b> ({len(memories)} total)\n"]

        # Thread by type
        by_type: dict[str, list[dict]] = {}
        for m in memories:
            by_type.setdefault(m["memory_type"], []).append(m)

        index = 1
        ordered: list[dict] = []
        for mtype, items in by_type.items():
            lines.append(f"\n<b>{html.escape(mtype.capitalize())}</b> ({len(items)}):")
            for m in items[:5]:  # Max 5 per type
                content = html.escape(m["content"][:60])
                suffix = "..." if len(m["content"]) > 60 else ""
                key_val = html.escape(m.get("key") or "-")
                lines.append(f"  • [{index}] {content}{suffix} (key: {key_val})")
                ordered.append(m)
                index += 1

        _LAST_MEM_LIST[thread_id] = ordered
        try:
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        except Exception as e:
            logger.exception(f"/mem list send failed: {e}")
            raise
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

        safe_query = html.escape(query)
        lines = [f"💾 <b>Memories matching '{safe_query}'</b> ({len(memories)} found)\n"]
        for m in memories:
            key_val = html.escape(m.get("key") or "-")
            key_note = f" (key: {key_val})"
            content = html.escape(m["content"][:80])
            suffix = "..." if len(m["content"]) > 80 else ""
            lines.append(f"  • {content}{suffix}{key_note}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error searching memories: {e}")
    finally:
        _clear_context()

async def _mem_forget(update: Update, thread_id: str, target: str, chat_type: str | None) -> None:
    """Forget a memory by ID or key."""
    await _set_context(thread_id, chat_type)
    try:
        storage = get_mem_storage()

        # Try as index from last /mem list
        if target.isdigit():
            idx = int(target)
            entries = _LAST_MEM_LIST.get(thread_id, [])
            if 1 <= idx <= len(entries):
                memory = entries[idx - 1]
                success = storage.delete_memory(memory["id"])
                if success:
                    await update.message.reply_text(f"✅ Forgot memory [{idx}]: {memory['content'][:50]}...")
                    return

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
        target_id = memory_id
        if memory_id.isdigit():
            idx = int(memory_id)
            entries = _LAST_MEM_LIST.get(thread_id, [])
            if 1 <= idx <= len(entries):
                target_id = entries[idx - 1]["id"]
        success = storage.update_memory(target_id, content=content)
        if success:
            await update.message.reply_text(f"✅ Memory updated: {target_id[:8]}...\nNew content: {content[:60]}")
        else:
            await update.message.reply_text(f"❌ Memory not found: {memory_id}")
    except Exception as e:
        await update.message.reply_text(f"Error updating memory: {e}")
    finally:
        _clear_context()

# ==================== /vdb COMMAND ====================

async def vdb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /vdb command for Vector Database management.

    Usage:
        /vdb                        - List all VDB tables
        /vdb store <table> <json>   - Store documents
        /vdb search <query> [table] - Search VDB
        /vdb describe <table>       - Describe a table
        /vdb delete <table>         - Delete a table
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /vdb {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
    chat_type = _get_chat_type(update)
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _vdb_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /vdb action={action} args={args[1:]}")

    if action == "list":
        await _vdb_list(update, thread_id, scope)
    elif action == "store":
        # /vdb store <table_name> <json_documents>
        if len(args) < 3:
            await update.message.reply_text("Usage: /vdb store <table_name> <json_documents>")
        else:
            table_name = args[1]
            documents = " ".join(args[2:])
            await _vdb_store(update, thread_id, table_name, documents, scope)
    elif action == "search":
        # /vdb search <query> [table_name]
        query = args[1] if len(args) > 1 else ""
        table_name = args[2] if len(args) > 2 else ""
        if not query:
            await update.message.reply_text("Usage: /vdb search <query> [table_name]")
        else:
            await _vdb_search(update, thread_id, query, table_name, scope)
    elif action == "describe":
        # /vdb describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /vdb describe <table_name>")
        else:
            await _vdb_describe(update, thread_id, args[1], scope)
    elif action == "delete":
        # /vdb delete <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /vdb delete <table_name>")
        else:
            await _vdb_delete(update, thread_id, args[1], scope)
    else:
        await _vdb_help(update)

async def _vdb_help(update: Update) -> None:
    """Show /vdb help."""
    help_text = (
        "🧠 <b>Vector Database</b>\n\n"
        "Commands:\n"
        "• <code>/vdb list</code>\n"
        "• <code>/vdb create &lt;name&gt;</code>\n"
        "• <code>/vdb add &lt;name&gt; &lt;text&gt;</code>\n"
        "• <code>/vdb add_file &lt;name&gt; &lt;path&gt;</code>\n"
        "• <code>/vdb search &lt;name&gt; &lt;query&gt;</code>\n"
        "• <code>/vdb describe &lt;name&gt;</code>\n"
        "• <code>/vdb delete &lt;name&gt;</code>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def _vdb_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show VDB summary and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import vdb_list

        tables_text = vdb_list.invoke({"scope": scope})
        total = 0
        if isinstance(tables_text, str) and tables_text.startswith("Vector Database collections:"):
            total = len([line for line in tables_text.splitlines() if line.strip().startswith("-")])

        help_text = (
            "🧠 <b>Vector Database (VDB)</b>\n\n"
            f"Collections: {total}\n\n"
            "Commands:\n"
            "• <code>/vdb list</code>\n"
            "• <code>/vdb store &lt;name&gt; &lt;json&gt;</code>\n"
            "• <code>/vdb search &lt;query&gt; [name]</code>\n"
            "• <code>/vdb describe &lt;name&gt;</code>\n"
            "• <code>/vdb delete &lt;name&gt;</code>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error loading VDB overview: {e}")
    finally:
        _clear_context()


async def _vdb_list(update: Update, thread_id: str, scope: str) -> None:
    """List VDB tables."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import vdb_list

        result = vdb_list.invoke({"scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error listing VDB: {e}")
    finally:
        _clear_context()

async def _vdb_store(update: Update, thread_id: str, table_name: str, documents: str, scope: str) -> None:
    """Store documents in VDB."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import create_vdb_collection

        result = create_vdb_collection.invoke({"collection_name": table_name, "documents": documents, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error storing documents: {e}")
    finally:
        _clear_context()

async def _vdb_search(update: Update, thread_id: str, query: str, table_name: str, scope: str) -> None:
    """Search VDB."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import search_vdb

        result = search_vdb.invoke({"query": query, "collection_name": table_name, "limit": 5, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error searching VDB: {e}")
    finally:
        _clear_context()

async def _vdb_describe(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Describe VDB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import describe_vdb_collection

        result = describe_vdb_collection.invoke({"collection_name": table_name, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error describing table: {e}")
    finally:
        _clear_context()

async def _vdb_delete(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Delete VDB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        from executive_assistant.storage.vs_tools import drop_vdb_collection

        result = drop_vdb_collection.invoke({"collection_name": table_name, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error deleting table: {e}")
    finally:
        _clear_context()

# ==================== /tdb COMMAND ====================

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
        return get_shared_tdb_storage()
    return get_sqlite_db()

def _get_thread_files_path(thread_id: str) -> Path:
    return settings.get_thread_files_path(thread_id)

def _get_files_path_for_scope(thread_id: str, scope: str) -> Path:
    if scope == "shared":
        return settings.get_shared_files_path()
    return _get_thread_files_path(thread_id)

async def _adb_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show ADB counts and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        tables_text = list_adb_tables.invoke({"scope": scope})
        total = 0
        if tables_text.startswith("Tables:"):
            total = len([line for line in tables_text.splitlines() if line.strip().startswith("-")])

        help_text = (
            "📈 <b>Analytics DB (ADB)</b>\n\n"
            f"Tables: {total}\n\n"
            "Commands:\n"
            "• <code>/adb list</code>\n"
            "• <code>/adb create &lt;table&gt; &lt;json&gt;</code>\n"
            "• <code>/adb insert &lt;table&gt; &lt;json&gt;</code>\n"
            "• <code>/adb query &lt;sql&gt;</code>\n"
            "• <code>/adb describe &lt;table&gt;</code>\n"
            "• <code>/adb drop &lt;table&gt;</code>\n"
            "• <code>/adb export &lt;table&gt; &lt;filename&gt; [csv|parquet|json]</code>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error reading ADB: {e}")
    finally:
        _clear_context()


def _normalize_json_rows(raw_json: str) -> list[dict]:
    parsed = json.loads(raw_json)
    if isinstance(parsed, dict):
        rows = [parsed]
    elif isinstance(parsed, list):
        rows = parsed
    else:
        raise ValueError("JSON must be an object or an array of objects.")

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON must be an object or an array of objects.")
    return rows


def _infer_duckdb_type(values: list[object]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "VARCHAR"
    if all(isinstance(v, bool) for v in non_null):
        return "BOOLEAN"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "BIGINT"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "DOUBLE"
    return "VARCHAR"


def _infer_schema(rows: list[dict]) -> tuple[list[str], dict[str, str]]:
    columns: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    if not columns:
        raise ValueError("No columns found in JSON payload.")

    for col in columns:
        validate_identifier(col)

    types = {
        col: _infer_duckdb_type([row.get(col) for row in rows])
        for col in columns
    }
    return columns, types


def _safe_filename(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Filename is required.")
    if Path(cleaned).name != cleaned:
        raise ValueError("Filename must not include directories.")
    return cleaned


def _resolve_export_format(filename: str, format_arg: str | None) -> tuple[str, str]:
    allowed = {"csv": ".csv", "parquet": ".parquet", "json": ".json"}
    if format_arg:
        fmt = format_arg.lower().lstrip(".")
        if fmt not in allowed:
            raise ValueError("Format must be csv, parquet, or json.")
        ext = Path(filename).suffix.lower()
        if ext != allowed[fmt]:
            filename = f"{Path(filename).stem}{allowed[fmt]}" if ext else f"{filename}{allowed[fmt]}"
        return filename, fmt

    ext = Path(filename).suffix.lower()
    if ext in allowed.values():
        fmt = {v: k for k, v in allowed.items()}[ext]
        return filename, fmt

    return f"{filename}.csv", "csv"


async def _adb_list(update: Update, thread_id: str, scope: str) -> None:
    """List ADB tables."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        result = list_adb_tables.invoke({"scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error listing ADB tables: {e}")
    finally:
        _clear_context()


async def _adb_query(update: Update, thread_id: str, sql: str, scope: str) -> None:
    """Run SQL query (ADB)."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        result = query_adb.invoke({"sql": sql, "scope": scope})
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error running ADB query: {e}")
    finally:
        _clear_context()


async def _adb_create(update: Update, thread_id: str, table_name: str, data: str, scope: str) -> None:
    """Create ADB table from JSON rows."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        validate_identifier(table_name)
        rows = _normalize_json_rows(data)
        columns, types = _infer_schema(rows)
        conn = get_adb(scope)
        col_defs = ", ".join(f"{col} {types[col]}" for col in columns)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})")

        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = [[row.get(col) for col in columns] for row in rows]
        if values:
            conn.executemany(
                f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                values,
            )
        await update.message.reply_text(
            f"✅ Table '{table_name}' created with {len(values)} row(s)"
        )
    except Exception as e:
        await update.message.reply_text(f"Error creating ADB table: {e}")
    finally:
        _clear_context()


async def _adb_insert(update: Update, thread_id: str, table_name: str, data: str, scope: str) -> None:
    """Insert JSON rows into ADB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        validate_identifier(table_name)
        rows = _normalize_json_rows(data)
        if not rows:
            await update.message.reply_text("No rows to insert.")
            return
        columns = list(rows[0].keys())
        for col in columns:
            validate_identifier(col)

        conn = get_adb(scope)
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = [[row.get(col) for col in columns] for row in rows]
        conn.executemany(
            f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
            values,
        )
        await update.message.reply_text(
            f"✅ Inserted {len(values)} row(s) into '{table_name}'"
        )
    except Exception as e:
        await update.message.reply_text(f"Error inserting into ADB: {e}")
    finally:
        _clear_context()


async def _adb_describe(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Describe ADB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        validate_identifier(table_name)
        conn = get_adb(scope)
        rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        if not rows:
            await update.message.reply_text(f"❌ Table '{table_name}' not found.")
            return
        safe_name = html.escape(table_name)
        lines = [f"📈 <b>Table '{safe_name}'</b>\n"]
        for row in rows:
            name = html.escape(str(row[1]))
            col_type = html.escape(str(row[2]))
            notnull = "NOT NULL" if row[3] else "NULL"
            dflt = html.escape(str(row[4])) if row[4] is not None else "NULL"
            pk = " PK" if row[5] else ""
            lines.append(f"• {name} — {col_type} {notnull} DEFAULT {dflt}{pk}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error describing ADB table: {e}")
    finally:
        _clear_context()


async def _adb_drop(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Drop ADB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        validate_identifier(table_name)
        conn = get_adb(scope)
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        await update.message.reply_text(f"✅ Dropped table '{table_name}'")
    except Exception as e:
        await update.message.reply_text(f"Error dropping ADB table: {e}")
    finally:
        _clear_context()


async def _adb_export(
    update: Update,
    thread_id: str,
    table_name: str,
    filename: str,
    format_arg: str | None,
    scope: str,
) -> None:
    """Export ADB table to a file in thread files."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        validate_identifier(table_name)
        final_name, fmt = _resolve_export_format(filename, format_arg)
        safe_name = _safe_filename(final_name)
        output_dir = _get_thread_files_path(thread_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / safe_name

        conn = get_adb(scope)
        if fmt == "parquet":
            conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT 'parquet')")
        elif fmt == "json":
            conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT 'json')")
        else:
            conn.execute(f"COPY {table_name} TO '{output_path}' (HEADER, DELIMITER ',')")
        await update.message.reply_text(f"✅ Exported to {output_path}")
    except Exception as e:
        await update.message.reply_text(f"Error exporting ADB table: {e}")
    finally:
        _clear_context()


async def adb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /adb command for analytics DB management.

    Usage:
        /adb               - Show counts and commands
        /adb list          - List tables
        /adb create <table> <json> - Create table from JSON rows
        /adb insert <table> <json> - Insert JSON rows
        /adb query <sql>   - Run SQL query
        /adb describe <table> - Describe table
        /adb drop <table> - Drop table
        /adb export <table> <filename> [format] - Export to file
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /adb {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return

    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if scope != "context":
        await update.message.reply_text("ADB currently supports context scope only.")
        return

    if not args:
        await _adb_overview(update, thread_id, scope)
        return

    action = args[0].lower()
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /adb action={action} args={args[1:]}")

    if action in {"list", "tables"}:
        await _adb_list(update, thread_id, scope)
        return

    if action == "create":
        if len(args) < 3:
            await update.message.reply_text("Usage: /adb create <table> <json>")
            return
        table_name = args[1]
        data = " ".join(args[2:])
        await _adb_create(update, thread_id, table_name, data, scope)
        return

    if action == "insert":
        if len(args) < 3:
            await update.message.reply_text("Usage: /adb insert <table> <json>")
            return
        table_name = args[1]
        data = " ".join(args[2:])
        await _adb_insert(update, thread_id, table_name, data, scope)
        return

    if action == "query":
        sql = " ".join(args[1:])
        if not sql.strip():
            await update.message.reply_text("Usage: /adb query <sql>")
            return
        await _adb_query(update, thread_id, sql, scope)
        return

    if action == "describe":
        if len(args) < 2:
            await update.message.reply_text("Usage: /adb describe <table>")
            return
        await _adb_describe(update, thread_id, args[1], scope)
        return

    if action == "drop":
        if len(args) < 2:
            await update.message.reply_text("Usage: /adb drop <table>")
            return
        await _adb_drop(update, thread_id, args[1], scope)
        return

    if action == "export":
        if len(args) < 3:
            await update.message.reply_text("Usage: /adb export <table> <filename> [csv|parquet|json]")
            return
        format_arg = args[3] if len(args) > 3 else None
        await _adb_export(update, thread_id, args[1], args[2], format_arg, scope)
        return

    await update.message.reply_text(
        "Usage: /adb list | /adb create <table> <json> | /adb insert <table> <json> | "
        "/adb query <sql> | /adb describe <table> | /adb drop <table> | "
        "/adb export <table> <filename> [csv|parquet|json]"
    )


async def tdb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tdb command for database management.

    Usage:
        /tdb                          - List all tables
        /tdb create <table> <json>    - Create table
        /tdb insert <table> <json>    - Insert data
        /tdb query <sql>              - Run SQL query
        /tdb describe <table>         - Describe table
        /tdb drop <table>             - Drop table
        /tdb export <table> <file>    - Export table
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /tdb {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _db_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /tdb action={action} args={args[1:]}")

    if action == "list":
        await _db_list(update, thread_id, scope)
    elif action == "create":
        # /tdb create <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /tdb create <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_create(update, thread_id, table_name, data, scope)
    elif action == "insert":
        # /tdb insert <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /tdb insert <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_insert(update, thread_id, table_name, data, scope)
    elif action == "query":
        # /tdb query <sql>
        sql = " ".join(args[1:])
        if not sql:
            await update.message.reply_text("Usage: /tdb query <sql>")
        else:
            await _db_query(update, thread_id, sql, scope)
    elif action == "describe":
        # /tdb describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /tdb describe <table_name>")
        else:
            await _db_describe(update, thread_id, args[1], scope)
    elif action == "drop":
        # /tdb drop <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /tdb drop <table_name>")
        else:
            await _db_drop(update, thread_id, args[1], scope)
    elif action == "export":
        # /tdb export <table_name> <filename>
        if len(args) < 3:
            await update.message.reply_text("Usage: /tdb export <table> <filename>")
        else:
            await _db_export(update, thread_id, args[1], args[2], scope)
    else:
        await _db_help(update)

async def _db_help(update: Update) -> None:
    """Show /tdb help."""
    help_text = (
        "🗄️ <b>Transactional Database (TDB)</b>\n\n"
        "Commands:\n"
        "• <code>/tdb list</code>\n"
        "• <code>/tdb create &lt;table&gt; &lt;json&gt;</code>\n"
        "• <code>/tdb insert &lt;table&gt; &lt;json&gt;</code>\n"
        "• <code>/tdb query &lt;sql&gt;</code>\n"
        "• <code>/tdb describe &lt;table&gt;</code>\n"
        "• <code>/tdb drop &lt;table&gt;</code>\n"
        "• <code>/tdb export &lt;table&gt; &lt;filename&gt;</code>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def _db_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show TDB summary and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        tables = storage.list_tables()
        total = len(tables)
        help_text = (
            "🗄️ <b>Transactional Database (TDB)</b>\n\n"
            f"Tables: {total}\n\n"
            "Commands:\n"
            "• <code>/tdb list</code>\n"
            "• <code>/tdb create &lt;table&gt; &lt;json&gt;</code>\n"
            "• <code>/tdb insert &lt;table&gt; &lt;json&gt;</code>\n"
            "• <code>/tdb query &lt;sql&gt;</code>\n"
            "• <code>/tdb describe &lt;table&gt;</code>\n"
            "• <code>/tdb drop &lt;table&gt;</code>\n"
            "• <code>/tdb export &lt;table&gt; &lt;filename&gt;</code>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error loading TDB overview: {e}")
    finally:
        _clear_context()


async def _db_list(update: Update, thread_id: str, scope: str) -> None:
    """List TDB tables."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        tables = storage.list_tables()

        if not tables:
            await update.message.reply_text("🗄️ No tables. Use /tdb create <table> <json> to create one.")
            return

        lines = ["🗄️ TDB Tables\n"]
        for table in tables:
            lines.append(f"• {table}")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error listing tables: {e}")
    finally:
        _clear_context()

async def _db_create(update: Update, thread_id: str, table_name: str, data: str, scope: str) -> None:
    """Create TDB table."""
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
    """Insert into TDB table."""
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
    """Run SQL query (TDB)."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        results = _db_execute(storage, sql)

        if not results:
            await update.message.reply_text("🗄️ No results")
            return

        lines = [f"🗄️ <b>Query Results</b> ({len(results)} rows)\n"]
        for row in results[:20]:  # Max 20 rows
            values = [
                html.escape(str(v)) if v is not None else "NULL"
                for v in row
            ]
            lines.append("  " + "\t".join(values))

        if len(results) > 20:
            lines.append(f"\n... ({len(results) - 20} more rows)")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error running query: {e}")
    finally:
        _clear_context()


async def _db_describe(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Describe TDB table."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        storage = _get_db_storage_for_scope(scope)
        columns = storage.get_table_info(table_name)
        safe_name = html.escape(table_name)
        lines = [f"🗄️ <b>Table '{safe_name}'</b>\n"]
        for col in columns:
            nullable = "NULL" if not col["notnull"] else "NOT NULL"
            pk = " PK" if col["pk"] > 0 else ""
            safe_col = html.escape(str(col["name"]))
            safe_type = html.escape(str(col["type"]))
            lines.append(f"  • {safe_col}: {safe_type} {nullable}{pk}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error describing table: {e}")
    finally:
        _clear_context()

async def _db_drop(update: Update, thread_id: str, table_name: str, scope: str) -> None:
    """Drop TDB table."""
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
    """Export TDB table."""
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
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /file {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
    args = context.args if context.args else []
    scope, args = _parse_scope(args)

    if not args:
        await _file_overview(update, thread_id, scope)
        return

    action = args[0].lower()

    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /file action={action} args={args[1:]}" )

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
        "📁 <b>Files</b>\n\n"
        "Commands:\n"
        "• <code>/file list</code>\n"
        "• <code>/file read &lt;path&gt;</code>\n"
        "• <code>/file write &lt;path&gt; &lt;text&gt;</code>\n"
        "• <code>/file delete &lt;path&gt;</code>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def _file_overview(update: Update, thread_id: str, scope: str) -> None:
    """Show file scope summary and commands."""
    await _set_context(thread_id, _get_chat_type(update))
    try:
        base_path = _get_files_path_for_scope(thread_id, scope)
        help_text = (
            "📂 <b>Files</b>\n\n"
            f"Scope: {scope}\n"
            f"Base path: <code>{base_path}</code>\n\n"
            "Commands:\n"
            "• <code>/file list</code>\n"
            "• <code>/file read &lt;path&gt;</code>\n"
            "• <code>/file write &lt;path&gt; &lt;text&gt;</code>\n"
            "• <code>/file delete &lt;path&gt;</code>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error loading file overview: {e}")
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

        safe_path = html.escape(filepath)
        safe_result = html.escape(result)
        await update.message.reply_text(
            f"📄 <b>{safe_path}</b>\n\n<pre><code>{safe_result}</code></pre>",
            parse_mode="HTML",
        )
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
    chat_type = _get_chat_type(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /meta {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return
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
            text = html.escape(json.dumps(meta, indent=2))
            await update.message.reply_text(f"<pre><code>{text}</code></pre>", parse_mode="HTML")
        else:
            text = html.escape(format_meta(meta, markdown=False))
            await update.message.reply_text(f"<pre>{text}</pre>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error reading meta: {e}")
    finally:
        _clear_context()


# ==================== /flow COMMAND ====================

async def flow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /flow command for flow management.

    Usage:
        /flow list [status]
        /flow run <id>
        /flow cancel <id>
        /flow delete <id>
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command recv /flow {update.message.text or ''}")
    if not await _ensure_authorized(update, thread_id):
        return

    chat_type = _get_chat_type(update)
    args = context.args if context.args else []

    if not args:
        await update.message.reply_text(
            "Usage: /flow status | /flow on | /flow off | /flow list [status] | /flow run <id> | /flow cancel <id> | /flow delete <id>"
        )
        return

    action = args[0].lower()
    logger.info(f"CH=telegram CONV={update.effective_chat.id} USER={thread_id} | command /flow action={action} args={args[1:]}")

    await _set_context(thread_id, chat_type)
    try:
        if action == "status":
            enabled = is_flow_mode_enabled(str(update.effective_chat.id))
            status_text = "on" if enabled else "off"
            await update.message.reply_text(f"Flow mode is {status_text}.")
            return
        if action == "on":
            enable_flow_mode(str(update.effective_chat.id))
            await update.message.reply_text("I will build and test the agents + flow now.")
            return
        if action == "off":
            disable_flow_mode(str(update.effective_chat.id))
            await update.message.reply_text("Flow mode off.")
            return
        if action == "list":
            status = args[1].lower() if len(args) > 1 else None
            result = await list_flows.ainvoke({"status": status})
            await update.message.reply_text(result)
        elif action == "run":
            if len(args) < 2:
                await update.message.reply_text("Usage: /flow run <id>")
                return
            result = await run_flow.ainvoke({"flow_id": int(args[1])})
            await update.message.reply_text(result)
        elif action == "cancel":
            if len(args) < 2:
                await update.message.reply_text("Usage: /flow cancel <id>")
                return
            result = await cancel_flow.ainvoke({"flow_id": int(args[1])})
            await update.message.reply_text(result)
        elif action == "delete":
            if len(args) < 2:
                await update.message.reply_text("Usage: /flow delete <id>")
                return
            result = await delete_flow.ainvoke({"flow_id": int(args[1])})
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("Unknown action. Use /flow list|run|cancel|delete")
    finally:
        _clear_context()
