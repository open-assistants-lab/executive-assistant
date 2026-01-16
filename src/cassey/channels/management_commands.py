"""Management slash commands for /mem, /kb, /db, /file.

These commands provide direct access to storage systems without needing
to go through the agent's tool calling mechanism.
"""

import json
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from cassey.config import settings
from cassey.storage.file_sandbox import set_thread_id, clear_thread_id
from cassey.storage.mem_storage import get_mem_storage
from cassey.storage.kb_storage import get_kb_storage
from cassey.storage.db_storage import get_db_storage


def _get_thread_id(update: Update) -> str:
    """Get thread_id from Telegram update."""
    return f"telegram:{update.effective_chat.id}"


def _set_context(thread_id: str) -> None:
    """Set thread_id context for storage operations."""
    set_thread_id(thread_id)


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
    args = context.args if context.args else []

    if not args:
        # List all memories
        await _mem_list(update, thread_id)
        return

    action = args[0].lower()

    if action == "list":
        # /mem list [type]
        mem_type = args[1] if len(args) > 1 else None
        await _mem_list(update, thread_id, mem_type)
    elif action == "add":
        # /mem add <content> [type] [key]
        content = args[1] if len(args) > 1 else ""
        if not content:
            await update.message.reply_text("Usage: /mem add <content> [type] [key]")
        else:
            mem_type = args[2] if len(args) > 2 else None
            key = args[3] if len(args) > 3 else None
            await _mem_add(update, thread_id, content, mem_type, key)
    elif action == "search":
        # /mem search <query>
        query = " ".join(args[1:]) if len(args) > 1 else ""
        if not query:
            await update.message.reply_text("Usage: /mem search <query>")
        else:
            await _mem_search(update, thread_id, query)
    elif action == "forget":
        # /mem forget <id|key>
        target = " ".join(args[1:]) if len(args) > 1 else ""
        if not target:
            await update.message.reply_text("Usage: /mem forget <memory_id or key>")
        else:
            await _mem_forget(update, thread_id, target)
    elif action == "update":
        # /mem update <id> <content>
        if len(args) < 3:
            await update.message.reply_text("Usage: /mem update <memory_id> <new content>")
        else:
            memory_id = args[1]
            content = " ".join(args[2:])
            await _mem_update(update, thread_id, memory_id, content)
    else:
        await _mem_help(update)


async def _mem_help(update: Update) -> None:
    """Show /mem help."""
    help_text = (
        "💾 *Memory Management*\n\n"
        "Usage:\n"
        "• `/mem` - List all memories\n"
        "• `/mem list [type]` - List by type (profile|preference|fact|task|note)\n"
        "• `/mem add <content> [type] [key]` - Add a memory\n"
        "• `/mem search <query>` - Search memories\n"
        "• `/mem forget <id|key>` - Forget a memory\n"
        "• `/mem update <id> <text>` - Update a memory\n\n"
        "Examples:\n"
        "• `/mem add I prefer tea over coffee preference`\n"
        "• `/mem add My office timezone is EST timezone`\n"
        "• `/mem list preference`\n"
        "• `/mem search timezone`\n"
        "• `/mem forget abc123`\n"
        "• `/mem update abc123 New content here`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _mem_add(update: Update, thread_id: str, content: str, mem_type: str | None = None, key: str | None = None) -> None:
    """Add a memory."""
    _set_context(thread_id)
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


async def _mem_list(update: Update, thread_id: str, mem_type: str | None = None) -> None:
    """List memories."""
    _set_context(thread_id)
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


async def _mem_search(update: Update, thread_id: str, query: str) -> None:
    """Search memories."""
    _set_context(thread_id)
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


async def _mem_forget(update: Update, thread_id: str, target: str) -> None:
    """Forget a memory by ID or key."""
    _set_context(thread_id)
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


async def _mem_update(update: Update, thread_id: str, memory_id: str, content: str) -> None:
    """Update a memory."""
    _set_context(thread_id)
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


# ==================== /kb COMMAND ====================

async def kb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /kb command for Knowledge Base management.

    Usage:
        /kb                        - List all KB tables
        /kb store <table> <json>   - Store documents
        /kb search <query> [table] - Search KB
        /kb describe <table>       - Describe a table
        /kb delete <table>         - Delete a table
    """
    if not update.message:
        return

    thread_id = _get_thread_id(update)
    args = context.args if context.args else []

    if not args:
        await _kb_list(update, thread_id)
        return

    action = args[0].lower()

    if action == "list":
        await _kb_list(update, thread_id)
    elif action == "store":
        # /kb store <table_name> <json_documents>
        if len(args) < 3:
            await update.message.reply_text("Usage: /kb store <table_name> <json_documents>")
        else:
            table_name = args[1]
            documents = " ".join(args[2:])
            await _kb_store(update, thread_id, table_name, documents)
    elif action == "search":
        # /kb search <query> [table_name]
        query = args[1] if len(args) > 1 else ""
        table_name = args[2] if len(args) > 2 else ""
        if not query:
            await update.message.reply_text("Usage: /kb search <query> [table_name]")
        else:
            await _kb_search(update, thread_id, query, table_name)
    elif action == "describe":
        # /kb describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /kb describe <table_name>")
        else:
            await _kb_describe(update, thread_id, args[1])
    elif action == "delete":
        # /kb delete <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /kb delete <table_name>")
        else:
            await _kb_delete(update, thread_id, args[1])
    else:
        await _kb_help(update)


async def _kb_help(update: Update) -> None:
    """Show /kb help."""
    help_text = (
        "📚 *Knowledge Base Management*\n\n"
        "Usage:\n"
        "• `/kb` - List all tables\n"
        "• `/kb store <table> <json>` - Store documents\n"
        "• `/kb search <query> [table]` - Search\n"
        "• `/kb describe <table>` - Describe table\n"
        "• `/kb delete <table>` - Delete table\n\n"
        "Example:\n"
        "`/kb store notes [{\"content\": \"Meeting notes\"}]`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _kb_list(update: Update, thread_id: str) -> None:
    """List KB tables."""
    _set_context(thread_id)
    try:
        from cassey.storage.kb_tools import _kb_storage

        conn = _kb_storage.get_connection()
        try:
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

            if not tables:
                await update.message.reply_text("📚 KB is empty. Use `/kb store <table> <json>` to create a table.")
                return

            lines = ["📚 *Knowledge Base Tables*\n"]
            for tbl in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                lines.append(f"• *{tbl}* - {count} documents (FTS indexed)")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        finally:
            conn.close()
    except Exception as e:
        await update.message.reply_text(f"Error listing KB: {e}")
    finally:
        _clear_context()


async def _kb_store(update: Update, thread_id: str, table_name: str, documents: str) -> None:
    """Store documents in KB."""
    _set_context(thread_id)
    try:
        from cassey.storage.kb_tools import _kb_storage, _ensure_fts_installed

        try:
            parsed = json.loads(documents)
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"❌ Invalid JSON: {e}")
            return

        if not isinstance(parsed, list):
            await update.message.reply_text("❌ Documents must be a JSON array")
            return

        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            try:
                conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            except Exception:
                pass

            conn.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for i, doc in enumerate(parsed):
                content = doc.get("content", "")
                metadata = doc.get("metadata", "")
                conn.execute(f"INSERT INTO {table_name} (id, content, metadata) VALUES (?, ?, ?)",
                           [i, content, metadata])

            conn.execute(f"PRAGMA create_fts_index('{table_name}', 'id', 'content', 'metadata')")

            await update.message.reply_text(f"✅ Stored {len(parsed)} documents in KB table '{table_name}'")
        finally:
            conn.close()
    except Exception as e:
        await update.message.reply_text(f"Error storing documents: {e}")
    finally:
        _clear_context()


async def _kb_search(update: Update, thread_id: str, query: str, table_name: str) -> None:
    """Search KB."""
    _set_context(thread_id)
    try:
        from cassey.storage.kb_tools import _kb_storage, _ensure_fts_installed

        conn = _kb_storage.get_connection()
        try:
            _ensure_fts_installed(conn)

            tables = [table_name] if table_name else [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

            if not tables:
                await update.message.reply_text("📚 KB is empty")
                return

            results = []
            for tbl in tables:
                try:
                    fts_query = f"""
                        SELECT content, metadata, fts_{tbl}.match_bm25(id, ?) AS score
                        FROM {tbl}
                        WHERE fts_{tbl}.match_bm25(id, ?) IS NOT NULL
                        ORDER BY score ASC
                        LIMIT 5
                    """
                    matches = conn.execute(fts_query, [query, query]).fetchall()

                    if matches:
                        results.append(f"\n*From '{tbl}':*")
                        for content, metadata, score in matches:
                            meta = f" [{metadata}]" if metadata else ""
                            results.append(f"  [{score:.2f}] {content[:60]}...{meta}")

                except Exception:
                    matches = conn.execute(f"""
                        SELECT content, metadata FROM {tbl}
                        WHERE content ILIKE ? LIMIT 5
                    """, [f"%{query}%"]).fetchall()

                    if matches:
                        results.append(f"\n*From '{tbl}':*")
                        for content, metadata in matches:
                            meta = f" [{metadata}]" if metadata else ""
                            results.append(f"  • {content[:60]}...{meta}")

            if not results:
                await update.message.reply_text(f"📚 No results for: {query}")
            else:
                await update.message.reply_text(f"📚 *Search results for '{query}':*\n" + "\n".join(results),
                                              parse_mode="Markdown")
        finally:
            conn.close()
    except Exception as e:
        await update.message.reply_text(f"Error searching KB: {e}")
    finally:
        _clear_context()


async def _kb_describe(update: Update, thread_id: str, table_name: str) -> None:
    """Describe KB table."""
    _set_context(thread_id)
    try:
        from cassey.storage.kb_tools import _kb_storage

        conn = _kb_storage.get_connection()
        try:
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                await update.message.reply_text(f"❌ KB table '{table_name}' not found")
                return

            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            samples = conn.execute(f"SELECT content, metadata FROM {table_name} LIMIT 3").fetchall()

            lines = [f"📚 *Table '{table_name}'*\n"]
            lines.append(f"Documents: {count}")
            lines.append("Has FTS index: Yes")

            if samples:
                lines.append("\n*Samples:*")
                for i, (content, metadata) in enumerate(samples, 1):
                    meta = f" [{metadata}]" if metadata else ""
                    lines.append(f"{i}. {content[:60]}...{meta}")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        finally:
            conn.close()
    except Exception as e:
        await update.message.reply_text(f"Error describing table: {e}")
    finally:
        _clear_context()


async def _kb_delete(update: Update, thread_id: str, table_name: str) -> None:
    """Delete KB table."""
    _set_context(thread_id)
    try:
        from cassey.storage.kb_tools import _kb_storage

        conn = _kb_storage.get_connection()
        try:
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                await update.message.reply_text(f"❌ KB table '{table_name}' not found")
                return

            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            try:
                conn.execute(f"PRAGMA drop_fts_index('{table_name}')")
            except Exception:
                pass

            conn.execute(f"DROP TABLE {table_name}")

            await update.message.reply_text(f"✅ Deleted KB table '{table_name}' ({count} documents)")
        finally:
            conn.close()
    except Exception as e:
        await update.message.reply_text(f"Error deleting table: {e}")
    finally:
        _clear_context()


# ==================== /db COMMAND ====================

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

    if not args:
        await _db_list(update, thread_id)
        return

    action = args[0].lower()

    if action == "list":
        await _db_list(update, thread_id)
    elif action == "create":
        # /db create <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db create <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_create(update, thread_id, table_name, data)
    elif action == "insert":
        # /db insert <table_name> <json_data>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db insert <table> <json_data>")
        else:
            table_name = args[1]
            data = " ".join(args[2:])
            await _db_insert(update, thread_id, table_name, data)
    elif action == "query":
        # /db query <sql>
        sql = " ".join(args[1:])
        if not sql:
            await update.message.reply_text("Usage: /db query <sql>")
        else:
            await _db_query(update, thread_id, sql)
    elif action == "describe":
        # /db describe <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /db describe <table_name>")
        else:
            await _db_describe(update, thread_id, args[1])
    elif action == "drop":
        # /db drop <table_name>
        if len(args) < 2:
            await update.message.reply_text("Usage: /db drop <table_name>")
        else:
            await _db_drop(update, thread_id, args[1])
    elif action == "export":
        # /db export <table_name> <filename>
        if len(args) < 3:
            await update.message.reply_text("Usage: /db export <table> <filename>")
        else:
            await _db_export(update, thread_id, args[1], args[2])
    else:
        await _db_help(update)


async def _db_help(update: Update) -> None:
    """Show /db help."""
    help_text = (
        "🗄️ *Database Management*\n\n"
        "Usage:\n"
        "• `/db` - List all tables\n"
        "• `/db create <table> <json>` - Create table\n"
        "• `/db insert <table> <json>` - Insert data\n"
        "• `/db query <sql>` - Run query\n"
        "• `/db describe <table>` - Describe table\n"
        "• `/db drop <table>` - Drop table\n"
        "• `/db export <table> <file>` - Export to CSV\n\n"
        "Example:\n"
        "`/db create users [{\"name\": \"Alice\", \"age\": 30}]`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _db_list(update: Update, thread_id: str) -> None:
    """List DB tables."""
    _set_context(thread_id)
    try:
        storage = get_db_storage()
        tables = storage.list_tables(thread_id)

        if not tables:
            await update.message.reply_text("🗄️ No tables. Use `/db create <table> <json>` to create one.")
            return

        lines = ["🗄️ *Database Tables*\n"]
        for table in tables:
            lines.append(f"• {table}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing tables: {e}")
    finally:
        _clear_context()


async def _db_create(update: Update, thread_id: str, table_name: str, data: str) -> None:
    """Create DB table."""
    _set_context(thread_id)
    try:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"❌ Invalid JSON: {e}")
            return

        storage = get_db_storage()
        storage.create_table_from_data(table_name, parsed, None, thread_id)
        await update.message.reply_text(f"✅ Table '{table_name}' created with {len(parsed)} rows")
    except Exception as e:
        await update.message.reply_text(f"Error creating table: {e}")
    finally:
        _clear_context()


async def _db_insert(update: Update, thread_id: str, table_name: str, data: str) -> None:
    """Insert into DB table."""
    _set_context(thread_id)
    try:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            await update.message.reply_text(f"❌ Invalid JSON: {e}")
            return

        storage = get_db_storage()
        storage.append_to_table(table_name, parsed, thread_id)
        await update.message.reply_text(f"✅ Inserted {len(parsed)} row(s) into '{table_name}'")
    except Exception as e:
        await update.message.reply_text(f"Error inserting data: {e}")
    finally:
        _clear_context()


async def _db_query(update: Update, thread_id: str, sql: str) -> None:
    """Run SQL query."""
    _set_context(thread_id)
    try:
        storage = get_db_storage()
        results = storage.execute(sql, thread_id)

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


async def _db_describe(update: Update, thread_id: str, table_name: str) -> None:
    """Describe DB table."""
    _set_context(thread_id)
    try:
        storage = get_db_storage()
        columns = storage.get_table_info(table_name, thread_id)

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


async def _db_drop(update: Update, thread_id: str, table_name: str) -> None:
    """Drop DB table."""
    _set_context(thread_id)
    try:
        storage = get_db_storage()
        storage.drop_table(table_name, thread_id)
        await update.message.reply_text(f"✅ Dropped table '{table_name}'")
    except Exception as e:
        await update.message.reply_text(f"Error dropping table: {e}")
    finally:
        _clear_context()


async def _db_export(update: Update, thread_id: str, table_name: str, filename: str) -> None:
    """Export DB table."""
    _set_context(thread_id)
    try:
        storage = get_db_storage()

        files_dir = settings.get_thread_files_path(thread_id)
        files_dir.mkdir(parents=True, exist_ok=True)

        if not filename.endswith(".csv"):
            filename = f"{filename}.csv"

        output_path = files_dir / filename

        storage.export_table(table_name, output_path, "csv", thread_id)
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

    if not args:
        await _file_list(update, thread_id)
        return

    action = args[0].lower()

    if action == "list":
        pattern = args[1] if len(args) > 1 else None
        await _file_list(update, thread_id, pattern)
    elif action == "read":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file read <filepath>")
        else:
            await _file_read(update, thread_id, args[1])
    elif action == "write":
        if len(args) < 3:
            await update.message.reply_text("Usage: /file write <filepath> <content>")
        else:
            filepath = args[1]
            content = " ".join(args[2:])
            await _file_write(update, thread_id, filepath, content)
    elif action == "create":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file create <folder_name>")
        else:
            await _file_create_folder(update, thread_id, args[1])
    elif action == "delete":
        if len(args) < 2:
            await update.message.reply_text("Usage: /file delete <path>")
        else:
            await _file_delete(update, thread_id, args[1])
    else:
        await _file_help(update)


async def _file_help(update: Update) -> None:
    """Show /file help."""
    help_text = (
        "📁 *File Management*\n\n"
        "Usage:\n"
        "• `/file` - List files\n"
        "• `/file list [pattern]` - List with pattern\n"
        "• `/file read <path>` - Read file\n"
        "• `/file write <path> <text>` - Write file\n"
        "• `/file create <folder>` - Create folder\n"
        "• `/file delete <path>` - Delete file/folder\n\n"
        "Examples:\n"
        "• `/file list *.txt`\n"
        "• `/file read notes.txt`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def _file_list(update: Update, thread_id: str, pattern: str | None = None) -> None:
    """List files."""
    _set_context(thread_id)
    try:
        from cassey.storage.file_sandbox import list_files

        if pattern:
            from cassey.storage.file_sandbox import glob_files
            result = glob_files.invoke({"pattern": pattern})
        else:
            result = list_files.invoke({})

        # Format result nicely
        if "files:" in result.lower() or "found" in result.lower():
            await update.message.reply_text(f"📁 *Files*\n\n{result}", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"📁 *Files*\n\n{result or 'No files found'}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing files: {e}")
    finally:
        _clear_context()


async def _file_read(update: Update, thread_id: str, filepath: str) -> None:
    """Read file."""
    _set_context(thread_id)
    try:
        from cassey.storage.file_sandbox import read_file

        result = read_file.invoke({"file_path": filepath})

        # Truncate if too long
        if len(result) > 3000:
            result = result[:3000] + "\n\n... (truncated, file too large)"

        await update.message.reply_text(f"📄 *{filepath}*\n\n```\n{result}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading file: {e}")
    finally:
        _clear_context()


async def _file_write(update: Update, thread_id: str, filepath: str, content: str) -> None:
    """Write file."""
    _set_context(thread_id)
    try:
        from cassey.storage.file_sandbox import write_file

        write_file.invoke({"file_path": filepath, "content": content})
        await update.message.reply_text(f"✅ Wrote to {filepath}")
    except Exception as e:
        await update.message.reply_text(f"Error writing file: {e}")
    finally:
        _clear_context()


async def _file_create_folder(update: Update, thread_id: str, folder_name: str) -> None:
    """Create folder."""
    _set_context(thread_id)
    try:
        from cassey.storage.file_sandbox import create_folder

        create_folder.invoke({"path": folder_name})
        await update.message.reply_text(f"✅ Created folder: {folder_name}")
    except Exception as e:
        await update.message.reply_text(f"Error creating folder: {e}")
    finally:
        _clear_context()


async def _file_delete(update: Update, thread_id: str, path: str) -> None:
    """Delete file or folder."""
    _set_context(thread_id)
    try:
        from cassey.storage.file_sandbox import delete_folder

        delete_folder.invoke({"path": path})
        await update.message.reply_text(f"✅ Deleted: {path}")
    except Exception as e:
        await update.message.reply_text(f"Error deleting: {e}")
    finally:
        _clear_context()
