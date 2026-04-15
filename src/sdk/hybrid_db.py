"""HybridDB: SQLite + FTS5 + ChromaDB with self-healing journal.

TEXT columns get keyword search. LONGTEXT columns get keyword + semantic search.
All backed by an operation journal that guarantees consistency across SQLite, FTS5, and ChromaDB.

See docs/HYBRIDDB_SPEC.md for full design rationale.
"""

import json
import sqlite3
import threading
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.app_logging import get_logger

logger = get_logger()

EMBEDDING_DIM = 384
JOURNAL_CAP = 50_000
CHROMA_BATCH = 5000
RRF_K = 60

_SYSTEM_TABLES = {"_journal", "_schema"}


class SearchMode(Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class EmbeddingModelError(Exception):
    pass


def _default_embedding_fn(text: str) -> list[float]:
    if not text:
        return [0.0] * EMBEDDING_DIM
    try:
        from src.sdk.tools_core.apps_storage import get_embedding

        return get_embedding(text)
    except Exception:
        return _hash_embedding(text)


def _hash_embedding(text: str) -> list[float]:
    import hashlib

    if not text:
        return [0.0] * EMBEDDING_DIM
    words = str(text).lower().split()
    dim = EMBEDDING_DIM
    embedding = [0.0] * dim
    for word in words:
        h = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
        embedding[h] += 1.0
    mag = sum(x**2 for x in embedding) ** 0.5
    if mag > 0:
        embedding = [x / mag for x in embedding]
    return embedding


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sanitize_fts_query(query: str) -> str:
    import re

    q = re.sub(r"[^\w\s]", " ", query.strip())
    q = " ".join(q.split())
    if not q:
        return ""
    return " OR ".join(q.split())


_EMBEDDING_MODEL_NAME: str | None = None


def _get_stored_model_name() -> str:
    global _EMBEDDING_MODEL_NAME
    if _EMBEDDING_MODEL_NAME is not None:
        return _EMBEDDING_MODEL_NAME
    try:
        from src.sdk.tools_core.apps_storage import EMBEDDING_MODEL

        _EMBEDDING_MODEL_NAME = EMBEDDING_MODEL
    except ImportError:
        _EMBEDDING_MODEL_NAME = "unknown"
    return _EMBEDDING_MODEL_NAME


class HybridDB:
    """Hybrid search database: SQLite + FTS5 + ChromaDB with self-healing journal."""

    def __init__(
        self,
        path: str,
        embedding_fn: Any | None = None,
        embedding_model_name: str | None = None,
        force_model: bool = False,
    ):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

        self._db_path = str((self.path / "app.db").resolve())
        self._vector_path = str((self.path / "vectors").resolve())
        Path(self._vector_path).mkdir(parents=True, exist_ok=True)

        self._embedding_fn = embedding_fn or _default_embedding_fn
        self._embedding_model_name = embedding_model_name or "unknown"
        self._db_lock = threading.RLock()
        self._hybrid_disabled: dict[str, bool] = {}

        self._init_system_tables()
        self._init_chroma(force_model)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Cursor, None, None]:
        with self._db_lock:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_system_tables(self) -> None:
        with self._connect() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_table TEXT NOT NULL,
                    row_id INTEGER,
                    column_name TEXT,
                    op TEXT NOT NULL,
                    data TEXT,
                    metadata TEXT,
                    status TEXT DEFAULT 'pending',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    retries INTEGER DEFAULT 0
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_pending ON _journal(status, app_table)"
            )

            cur.execute("""
                CREATE TABLE IF NOT EXISTS _schema (
                    table_name TEXT PRIMARY KEY,
                    columns_json TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    is_dirty INTEGER DEFAULT 0,
                    embedding_model TEXT,
                    embedding_dim INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _init_chroma(self, force: bool = False) -> None:
        self._chroma = chromadb.PersistentClient(
            path=self._vector_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        with self._connect() as cur:
            cur.execute("SELECT table_name, embedding_model, embedding_dim FROM _schema")
            rows = cur.fetchall()

        for row in rows:
            if row["embedding_model"] and row["embedding_model"] != "unknown":
                if row["embedding_model"] != self._embedding_model_name and not force:
                    raise EmbeddingModelError(
                        f"Embedding model mismatch for table '{row['table_name']}': "
                        f"stored='{row['embedding_model']}', current='{self._embedding_model_name}'. "
                        f"Pass force=True to override, then call reconcile()."
                    )

    def _get_embedding(self, text: str) -> list[float]:
        if not text:
            return [0.0] * EMBEDDING_DIM
        return self._embedding_fn(text)

    def _get_collection(self, name: str):
        return self._chroma.get_or_create_collection(name=name)

    def _table_meta(self, table: str) -> dict[str, Any] | None:
        with self._connect() as cur:
            cur.execute("SELECT * FROM _schema WHERE table_name = ?", (table,))
            row = cur.fetchone()
        if not row:
            return None
        return {
            "table_name": row["table_name"],
            "columns": json.loads(row["columns_json"]),
            "version": row["version"],
            "is_dirty": bool(row["is_dirty"]),
        }

    def _save_table_meta(
        self, cur: sqlite3.Cursor, table: str, columns: dict[str, str], dirty: bool = False
    ) -> None:
        now = _now_iso()
        cur.execute(
            "INSERT OR REPLACE INTO _schema "
            "(table_name, columns_json, version, is_dirty, embedding_model, embedding_dim, created_at, updated_at) "
            "VALUES (?, ?, COALESCE((SELECT version FROM _schema WHERE table_name = ?), 0) + 1, ?, ?, ?, ?, ?)",
            (
                table,
                json.dumps(columns),
                table,
                int(dirty),
                self._embedding_model_name,
                EMBEDDING_DIM,
                now,
                now,
            ),
        )

    def _get_text_columns(self, table: str) -> list[str]:
        meta = self._table_meta(table)
        if not meta:
            return []
        return [col for col, ctype in meta["columns"].items() if ctype in ("TEXT", "LONGTEXT")]

    def _get_longtext_columns(self, table: str) -> list[str]:
        meta = self._table_meta(table)
        if not meta:
            return []
        return [col for col, ctype in meta["columns"].items() if ctype == "LONGTEXT"]

    def _row_to_metadata(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        meta = self._table_meta(table)
        if not meta:
            return {}
        result = {}
        for col, ctype in meta["columns"].items():
            if ctype in ("LONGTEXT", "JSON"):
                continue
            val = row.get(col)
            if val is None:
                continue
            base = ctype.replace("_PK", "")
            if base == "BOOLEAN":
                result[col] = bool(val)
            else:
                result[col] = val
        return result

    def _has_autoincrement_id(self, table: str) -> bool:
        with self._connect() as cur:
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,))
            row = cur.fetchone()
        if not row or not row["sql"]:
            return False
        return "INTEGER PRIMARY KEY AUTOINCREMENT" in row["sql"]

    def _create_fts5(self, cur: sqlite3.Cursor, table: str, col: str) -> None:
        fts_name = f"{table}_fts_{col}"
        use_id = self._has_autoincrement_id(table)
        rowid_ref = "new.id" if use_id else "new.rowid"
        old_rowid_ref = "old.id" if use_id else "old.rowid"
        content_rowid = "id" if use_id else "rowid"

        cur.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts_name} USING fts5("
            f"{col}, content='{table}', content_rowid='{content_rowid}')"
        )
        cur.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_ai_{col} AFTER INSERT ON {table} BEGIN "
            f"INSERT INTO {fts_name}(rowid, {col}) VALUES ({rowid_ref}, new.{col}); END"
        )
        cur.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_ad_{col} AFTER DELETE ON {table} BEGIN "
            f"INSERT INTO {fts_name}({fts_name}, rowid, {col}) "
            f"VALUES ('delete', {old_rowid_ref}, old.{col}); END"
        )
        cur.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_au_{col} AFTER UPDATE ON {table} BEGIN "
            f"INSERT INTO {fts_name}({fts_name}, rowid, {col}) "
            f"VALUES ('delete', {old_rowid_ref}, old.{col}); "
            f"INSERT INTO {fts_name}(rowid, {col}) VALUES ({rowid_ref}, new.{col}); END"
        )

    def _drop_fts5(self, cur: sqlite3.Cursor, table: str, col: str) -> None:
        fts_name = f"{table}_fts_{col}"
        cur.execute(f"DROP TABLE IF EXISTS {fts_name}")
        for suffix in ("ai", "ad", "au"):
            cur.execute(f"DROP TRIGGER IF EXISTS {table}_{suffix}_{col}")

    def _rebuild_all_fts5(self, cur: sqlite3.Cursor, table: str) -> None:
        meta = self._table_meta(table)
        if not meta:
            return
        for col in self._get_text_columns(table):
            self._drop_fts5(cur, table, col)
            self._create_fts5(cur, table, col)

    # ── Schema ──────────────────────────────────────────────

    def create_table(self, table: str, columns: dict[str, str]) -> None:
        col_defs: list[str] = []
        parsed: dict[str, str] = {}
        has_custom_pk = any(
            "PRIMARY KEY" in spec.upper() and name == "id" for name, spec in columns.items()
        )

        if not has_custom_pk:
            col_defs.append("id INTEGER PRIMARY KEY AUTOINCREMENT")

        for col_name, col_spec in columns.items():
            parts = col_spec.split()
            base_type = parts[0].upper()
            extras = " ".join(parts[1:]) if len(parts) > 1 else ""
            is_pk = "PRIMARY KEY" in extras.upper()

            if base_type == "TEXT":
                col_defs.append(f"{col_name} TEXT{' ' + extras if extras else ''}")
                parsed[col_name] = "TEXT" if not is_pk else "TEXT_PK"
            elif base_type == "LONGTEXT":
                col_defs.append(f"{col_name} TEXT{' ' + extras if extras else ''}")
                parsed[col_name] = "LONGTEXT"
            elif base_type == "INTEGER":
                col_defs.append(f"{col_name} INTEGER{' ' + extras if extras else ''}")
                parsed[col_name] = "INTEGER" if not is_pk else "INTEGER_PK"
            elif base_type == "REAL":
                col_defs.append(f"{col_name} REAL{' ' + extras if extras else ''}")
                parsed[col_name] = "REAL"
            elif base_type == "BOOLEAN":
                col_defs.append(f"{col_name} INTEGER{' ' + extras if extras else ''}")
                parsed[col_name] = "BOOLEAN"
            elif base_type == "JSON":
                col_defs.append(f"{col_name} TEXT{' ' + extras if extras else ''}")
                parsed[col_name] = "JSON"
            else:
                col_defs.append(f"{col_name} TEXT{' ' + extras if extras else ''}")
                parsed[col_name] = base_type

        with self._connect() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})")

            for col in self._get_text_columns(table) if self._table_meta(table) else []:
                pass

            text_cols = [c for c, t in parsed.items() if t in ("TEXT", "LONGTEXT")]
            for col in text_cols:
                self._create_fts5(cur, table, col)

            for col in self._get_longtext_columns_from_parsed(parsed):
                self._get_collection(f"{table}_{col}")

            self._save_table_meta(cur, table, parsed)

    def _get_longtext_columns_from_parsed(self, parsed: dict[str, str]) -> list[str]:
        return [col for col, ctype in parsed.items() if ctype == "LONGTEXT"]

    def add_column(self, table: str, column: str, col_type: str) -> None:
        meta = self._table_meta(table)
        if not meta:
            raise ValueError(f"Table '{table}' not found")

        base_type = col_type.split()[0].upper()
        sqlite_type = {
            "LONGTEXT": "TEXT",
            "BOOLEAN": "INTEGER",
            "JSON": "TEXT",
        }.get(base_type, base_type)

        extras = " ".join(col_type.split()[1:]) if len(col_type.split()) > 1 else ""
        col_def = f"{column} {sqlite_type}{' ' + extras if extras else ''}"

        with self._connect() as cur:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")

            new_columns = dict(meta["columns"])
            new_columns[column] = base_type

            if base_type in ("TEXT", "LONGTEXT"):
                self._create_fts5(cur, table, column)

            if base_type == "LONGTEXT":
                self._get_collection(f"{table}_{column}")

            self._save_table_meta(cur, table, new_columns, dirty=(base_type == "LONGTEXT"))

    def drop_column(self, table: str, column: str) -> None:
        meta = self._table_meta(table)
        if not meta or column not in meta["columns"]:
            raise ValueError(f"Column '{column}' not found in table '{table}'")

        col_type = meta["columns"][column]
        old_columns = {k: v for k, v in meta["columns"].items() if k != column}

        with self._connect() as cur:
            old_table = f"_{table}_old"
            cur.execute(f"ALTER TABLE {table} RENAME TO {old_table}")

            new_col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            for cname, ctype in old_columns.items():
                sqlite_type = {"LONGTEXT": "TEXT", "BOOLEAN": "INTEGER", "JSON": "TEXT"}.get(
                    ctype, ctype
                )
                new_col_defs.append(f"{cname} {sqlite_type}")

            cur.execute(f"CREATE TABLE {table} ({', '.join(new_col_defs)})")

            shared = [c for c in old_columns if c in meta["columns"]]
            col_list = ", ".join(shared)
            cur.execute(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {old_table}")
            cur.execute(f"DROP TABLE {old_table}")

            if col_type in ("TEXT", "LONGTEXT"):
                self._drop_fts5(cur, table, column)

            self._rebuild_all_fts5(cur, table)

            if col_type == "LONGTEXT":
                try:
                    self._chroma.delete_collection(f"{table}_{column}")
                except Exception:
                    pass

                for lt_col in self._get_longtext_columns_from_parsed(old_columns):
                    now = _now_iso()
                    cur.execute(
                        "INSERT INTO _journal (app_table, row_id, column_name, op, created_at) "
                        "VALUES (?, NULL, ?, 'meta_update', ?)",
                        (table, lt_col, now),
                    )

            self._save_table_meta(cur, table, old_columns, dirty=True)

    def rename_column(self, table: str, old_name: str, new_name: str) -> None:
        meta = self._table_meta(table)
        if not meta or old_name not in meta["columns"]:
            raise ValueError(f"Column '{old_name}' not found in table '{table}'")

        col_type = meta["columns"][old_name]
        new_columns = {}
        for k, v in meta["columns"].items():
            new_columns[new_name if k == old_name else k] = v

        with self._connect() as cur:
            cur.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")

            if col_type in ("TEXT", "LONGTEXT"):
                self._drop_fts5(cur, table, old_name)
                self._create_fts5(cur, table, new_name)

            for lt_col in self._get_longtext_columns_from_parsed(new_columns):
                now = _now_iso()
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, created_at) "
                    "VALUES (?, NULL, ?, 'meta_update', ?)",
                    (table, lt_col, now),
                )

            self._save_table_meta(cur, table, new_columns, dirty=True)

    def list_tables(self) -> list[str]:
        with self._connect() as cur:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row["name"] for row in cur.fetchall()]
        return [
            t
            for t in tables
            if t not in _SYSTEM_TABLES and not t.endswith("_fts") and not t.startswith("_")
        ]

    def get_schema(self, table: str) -> dict[str, str]:
        meta = self._table_meta(table)
        if not meta:
            return {}
        return meta["columns"]

    # ── CRUD ────────────────────────────────────────────────

    def insert(self, table: str, data: dict, sync: bool = True) -> int:
        meta = self._table_meta(table)
        if not meta:
            raise ValueError(f"Table '{table}' not found")

        filtered = {k: v for k, v in data.items() if k in meta["columns"]}
        columns = list(filtered.keys())
        placeholders = ", ".join("?" * len(columns))
        values = list(filtered.values())

        with self._connect() as cur:
            cur.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            row_id = cur.lastrowid
            has_auto_id = self._has_autoincrement_id(table)

            if has_auto_id:
                row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())
            elif "id" in filtered:
                row_id = filtered["id"]
                row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())
            else:
                row = dict(
                    cur.execute(f"SELECT * FROM {table} WHERE rowid = ?", (row_id,)).fetchone()
                )

            metadata = self._row_to_metadata(table, row)
            for col in self._get_longtext_columns(table):
                now = _now_iso()
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                    "VALUES (?, ?, ?, 'add', ?, ?, ?)",
                    (table, row_id, col, row.get(col, ""), json.dumps(metadata), now),
                )

        if sync:
            self._process_journal()
        return row_id

    def insert_batch(self, table: str, rows: list[dict], sync: bool = True) -> list[int]:
        meta = self._table_meta(table)
        if not meta:
            raise ValueError(f"Table '{table}' not found")

        ids: list[int] = []
        with self._connect() as cur:
            for data in rows:
                filtered = {k: v for k, v in data.items() if k in meta["columns"]}
                columns = list(filtered.keys())
                placeholders = ", ".join("?" * len(columns))
                values = list(filtered.values())

                cur.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    values,
                )
                row_id = cur.lastrowid
                assert row_id is not None
                ids.append(row_id)

                row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())

                metadata = self._row_to_metadata(table, row)
                for col in self._get_longtext_columns(table):
                    now = _now_iso()
                    cur.execute(
                        "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                        "VALUES (?, ?, ?, 'add', ?, ?, ?)",
                        (table, row_id, col, row.get(col, ""), json.dumps(metadata), now),
                    )

        if sync:
            self._process_journal()
        return ids

    def update(self, table: str, row_id: int | str, data: dict, sync: bool = True) -> bool:
        meta = self._table_meta(table)
        if not meta:
            raise ValueError(f"Table '{table}' not found")

        filtered = {k: v for k, v in data.items() if k in meta["columns"]}
        if not filtered:
            return False

        with self._connect() as cur:
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            cur.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?",
                list(filtered.values()) + [row_id],
            )
            if cur.rowcount == 0:
                return False

            row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())

            metadata = self._row_to_metadata(table, row)
            for col in self._get_longtext_columns(table):
                now = _now_iso()
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                    "VALUES (?, ?, ?, 'update', ?, ?, ?)",
                    (table, row_id, col, row.get(col, ""), json.dumps(metadata), now),
                )

        if sync:
            self._process_journal()
        return True

    def delete(self, table: str, row_id: int | str, sync: bool = True) -> bool:
        with self._connect() as cur:
            cur.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            if cur.rowcount == 0:
                return False

            for col in self._get_longtext_columns(table):
                now = _now_iso()
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, created_at) "
                    "VALUES (?, ?, ?, 'delete', ?)",
                    (table, row_id, col, now),
                )

        if sync:
            self._process_journal()
        return True

    def get(self, table: str, row_id: int | str) -> dict | None:
        with self._connect() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
            row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def query(
        self,
        table: str,
        where: str = "",
        params: tuple = (),
        order_by: str = "",
        limit: int = 100,
    ) -> list[dict]:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {limit}"

        with self._connect() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def raw_query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        with self._connect() as cur:
            result = cur.execute(sql, params).fetchone()
        return result[0] if result else 0

    # ── Search ──────────────────────────────────────────────

    def search(
        self,
        table: str,
        column: str,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        where: dict | None = None,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.0,
        recency_column: str | None = None,
    ) -> list[dict]:
        pending = self._journal_count(table)
        if pending > 0:
            self._process_journal()

        if self._hybrid_disabled.get(table) and mode != SearchMode.KEYWORD:
            mode = SearchMode.KEYWORD

        fts_results: list[tuple[int, float]] = []
        vec_results: list[tuple[int, float]] = []

        meta = self._table_meta(table)
        col_type = meta["columns"].get(column, "") if meta else ""
        if col_type not in ("TEXT", "LONGTEXT"):
            return []

        if mode in (SearchMode.KEYWORD, SearchMode.HYBRID):
            fts_results = self._fts_search(table, column, query, limit * 2)

        if mode in (SearchMode.SEMANTIC, SearchMode.HYBRID) and col_type == "LONGTEXT":
            vec_results = self._vector_search(table, column, query, where, limit * 2)

        if mode == SearchMode.KEYWORD:
            ranked = fts_results
        elif mode == SearchMode.SEMANTIC:
            ranked = vec_results
        else:
            ranked = self._fuse_hybrid(fts_results, vec_results, fts_weight)

        if not ranked:
            return []

        row_ids = [r[0] for r in ranked]
        rows = self._fetch_rows_by_ids(table, row_ids)

        results = []
        for row_id, score in ranked:
            row = rows.get(row_id)
            if row is None:
                continue

            final_score = score
            if recency_weight > 0 and recency_column:
                ts_str = row.get(recency_column)
                recency = self._compute_recency(ts_str)
                final_score = score * (1 - recency_weight) + recency * recency_weight

            row["_score"] = final_score
            row["_search_mode"] = mode.value
            results.append(row)

        return results[:limit]

    def search_all(
        self,
        table: str,
        query: str,
        where: dict | None = None,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.0,
        recency_column: str | None = None,
    ) -> list[dict]:
        pending = self._journal_count(table)
        if pending > 0:
            self._process_journal()

        lt_cols = self._get_longtext_columns(table)
        all_text_cols = self._get_text_columns(table)

        all_fts: list[tuple[int, float]] = []
        for col in all_text_cols:
            col_fts = self._fts_search(table, col, query, limit * 2)
            all_fts.extend(col_fts)

        all_vec: list[tuple[int, float]] = []
        for col in lt_cols:
            col_vec = self._vector_search(table, col, query, where, limit * 2)
            all_vec.extend(col_vec)

        ranked = self._fuse_hybrid(all_fts, all_vec, fts_weight)

        if not ranked:
            return []

        row_ids = [r[0] for r in ranked]
        rows = self._fetch_rows_by_ids(table, row_ids)

        results = []
        for row_id, score in ranked:
            row = rows.get(row_id)
            if row is None:
                continue

            final_score = score
            if recency_weight > 0 and recency_column:
                ts_str = row.get(recency_column)
                recency = self._compute_recency(ts_str)
                final_score = score * (1 - recency_weight) + recency * recency_weight

            row["_score"] = final_score
            row["_search_mode"] = "hybrid"
            results.append(row)

        return results[:limit]

    def _fts_search(
        self, table: str, column: str, query: str, limit: int
    ) -> list[tuple[int, float]]:
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []

        fts_table = f"{table}_fts_{column}"
        use_id = self._has_autoincrement_id(table)
        join_col = "m.id" if use_id else "m.rowid"

        try:
            with self._connect() as cur:
                cur.execute(
                    f"SELECT {join_col} as id, bm25({fts_table}) as score "
                    f"FROM {fts_table} fts JOIN {table} m ON {join_col} = fts.rowid "
                    f"WHERE {fts_table} MATCH ? ORDER BY score LIMIT ?",
                    (fts_query, limit),
                )
                rows = cur.fetchall()
                return [(r["id"], r["score"]) for r in rows]
        except Exception:
            try:
                with self._connect() as cur:
                    cur.execute(
                        f"SELECT id, 0.0 as score FROM {table} WHERE {column} LIKE ? LIMIT ?",
                        (f"%{query}%", limit),
                    )
                    rows = cur.fetchall()
                    return [(r["id"], r["score"]) for r in rows]
            except Exception:
                return []

    def _vector_search(
        self,
        table: str,
        column: str,
        query: str,
        where: dict | None = None,
        limit: int = 10,
    ) -> list[tuple[int, float]]:
        collection_name = f"{table}_{column}"
        try:
            collection = self._get_collection(collection_name)
            embedding = self._get_embedding(query)
            kwargs: dict[str, Any] = {
                "query_embeddings": [embedding],
                "n_results": limit,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = collection.query(**kwargs)

            if not results["ids"] or not results["ids"][0]:
                return []

            out = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if "distances" in results else 0
                similarity = max(0.0, 1.0 - distance)
                out.append((int(doc_id), similarity))
            return out
        except Exception:
            return []

    def _fuse_hybrid(
        self,
        fts_results: list[tuple[int, float]],
        vec_results: list[tuple[int, float]],
        fts_weight: float = 0.5,
    ) -> list[tuple[int, float]]:
        scores: dict[int, float] = {}

        for rank, (row_id, _) in enumerate(fts_results):
            rrf = fts_weight / (RRF_K + rank + 1)
            scores[row_id] = scores.get(row_id, 0) + rrf

        for rank, (row_id, _) in enumerate(vec_results):
            rrf = (1 - fts_weight) / (RRF_K + rank + 1)
            scores[row_id] = scores.get(row_id, 0) + rrf

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _compute_recency(self, ts_str: str | None) -> float:
        if not ts_str:
            return 0.0
        try:
            ts = datetime.fromisoformat(ts_str)
            days_ago = max((datetime.now(UTC) - ts).days, 0)
            return 1.0 / (1 + days_ago / 30)
        except (ValueError, TypeError):
            return 0.0

    def _fetch_rows_by_ids(self, table: str, ids: list[int | str]) -> dict[int | str, dict]:
        if not ids:
            return {}
        has_auto_id = self._has_autoincrement_id(table)
        with self._connect() as cur:
            placeholders = ",".join("?" * len(ids))
            if has_auto_id:
                cur.execute(
                    f"SELECT *, id as _lookup_id FROM {table} WHERE id IN ({placeholders})",
                    ids,
                )
            else:
                cur.execute(
                    f"SELECT *, rowid as _lookup_id FROM {table} WHERE rowid IN ({placeholders})",
                    ids,
                )
            rows = cur.fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            lookup_id = d.pop("_lookup_id", None)
            result[lookup_id] = d
        return result

    # ── Journal ─────────────────────────────────────────────

    def _journal_count(self, table: str | None = None) -> int:
        with self._connect() as cur:
            if table:
                cur.execute(
                    "SELECT COUNT(*) FROM _journal WHERE status = 'pending' AND app_table = ?",
                    (table,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM _journal WHERE status = 'pending'")
            result = cur.fetchone()
        return result[0] if result else 0

    def _process_journal(self, batch_limit: int = 5000) -> int:
        table_caps: dict[str, int] = {}
        with self._connect() as cur:
            cur.execute(
                "SELECT app_table, COUNT(*) FROM _journal WHERE status = 'pending' GROUP BY app_table"
            )
            for row in cur.fetchall():
                table_caps[row[0]] = row[1]

        for tbl, count in table_caps.items():
            if count > JOURNAL_CAP:
                logger.warning("journal.overflow", {"table": tbl, "pending": count})
                self._hybrid_disabled[tbl] = True

        with self._connect() as cur:
            cur.execute(
                "SELECT * FROM _journal WHERE status = 'pending' ORDER BY id LIMIT ?",
                (batch_limit,),
            )
            entries = [dict(r) for r in cur.fetchall()]

        if not entries:
            return 0

        adds = [e for e in entries if e["op"] == "add"]
        updates = [e for e in entries if e["op"] == "update"]
        deletes = [e for e in entries if e["op"] == "delete"]
        meta_updates = [e for e in entries if e["op"] == "meta_update"]

        by_collection: dict[str, dict[str, list]] = defaultdict(
            lambda: {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        )
        for entry in adds:
            collection_name = f"{entry['app_table']}_{entry['column_name']}"
            doc = entry["data"] or ""
            embedding = self._get_embedding(doc)
            metadata = json.loads(entry["metadata"]) if entry["metadata"] else {}
            if not metadata:
                metadata = None

            by_collection[collection_name]["ids"].append(str(entry["row_id"]))
            by_collection[collection_name]["embeddings"].append(embedding)
            by_collection[collection_name]["documents"].append(doc)
            by_collection[collection_name]["metadatas"].append(metadata)

        for coll_name, batch in by_collection.items():
            collection = self._get_collection(coll_name)
            for i in range(0, len(batch["ids"]), CHROMA_BATCH):
                kwargs: dict[str, Any] = {
                    "ids": batch["ids"][i : i + CHROMA_BATCH],
                    "embeddings": batch["embeddings"][i : i + CHROMA_BATCH],
                    "documents": batch["documents"][i : i + CHROMA_BATCH],
                }
                metas = batch["metadatas"][i : i + CHROMA_BATCH]
                if any(m is not None for m in metas):
                    kwargs["metadatas"] = metas
                collection.upsert(**kwargs)

        by_collection_del: dict[str, list[str]] = defaultdict(list)
        for entry in deletes:
            collection_name = f"{entry['app_table']}_{entry['column_name']}"
            by_collection_del[collection_name].append(str(entry["row_id"]))

        for coll_name, ids in by_collection_del.items():
            collection = self._get_collection(coll_name)
            for i in range(0, len(ids), CHROMA_BATCH):
                collection.delete(ids=ids[i : i + CHROMA_BATCH])

        for entry in updates:
            collection_name = f"{entry['app_table']}_{entry['column_name']}"
            try:
                collection = self._get_collection(collection_name)
                metadata = json.loads(entry["metadata"]) if entry["metadata"] else {}
                doc = entry["data"] or ""
                embedding = self._get_embedding(doc)

                update_kwargs: dict[str, Any] = {
                    "ids": [str(entry["row_id"])],
                    "embeddings": [embedding],
                    "documents": [doc],
                }
                if metadata:
                    update_kwargs["metadatas"] = [metadata]
                collection.update(**update_kwargs)
            except Exception as e:
                logger.warning(
                    "journal.update_failed",
                    {"entry_id": entry["id"], "error": str(e)},
                    user_id="system",
                )

        for entry in meta_updates:
            try:
                self._process_meta_update(entry)
            except Exception as e:
                logger.warning(
                    "journal.meta_update_failed",
                    {"entry_id": entry["id"], "error": str(e)},
                    user_id="system",
                )

        done_ids = [e["id"] for e in entries]
        with self._connect() as cur:
            placeholders = ",".join("?" * len(done_ids))
            cur.execute(f"DELETE FROM _journal WHERE id IN ({placeholders})", done_ids)

        return len(done_ids)

    def _process_meta_update(self, entry: dict) -> None:
        pass

    # ── Maintenance ─────────────────────────────────────────

    def reconcile(self, table: str) -> dict:
        result = {"ghosts_deleted": 0, "missing_added": 0, "metadata_updated": 0}
        lt_cols = self._get_longtext_columns(table)

        for col in lt_cols:
            collection_name = f"{table}_{col}"
            try:
                collection = self._get_collection(collection_name)
                chroma_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()

                with self._connect() as cur:
                    cur.execute(f"SELECT id, {col} FROM {table}")
                    sql_rows = cur.fetchall()

                sql_ids = {str(r["id"]) for r in sql_rows}

                ghosts = chroma_ids - sql_ids
                if ghosts:
                    collection.delete(ids=list(ghosts))
                    result["ghosts_deleted"] += len(ghosts)

                missing = sql_ids - chroma_ids
                if missing:
                    id_to_row = {str(r["id"]): r for r in sql_rows if str(r["id"]) in missing}

                    ids_batch = []
                    embeddings_batch = []
                    docs_batch = []
                    metas_batch = []

                    for mid in missing:
                        row = id_to_row.get(mid)
                        if row:
                            doc = row[col] or ""
                            ids_batch.append(mid)
                            embeddings_batch.append(self._get_embedding(doc))
                            docs_batch.append(doc)

                            full_row = self.get(table, int(mid))
                            if full_row:
                                metas_batch.append(self._row_to_metadata(table, full_row))
                            else:
                                metas_batch.append({})

                            if len(ids_batch) >= CHROMA_BATCH:
                                collection.upsert(
                                    ids=ids_batch,
                                    embeddings=embeddings_batch,
                                    documents=docs_batch,
                                    metadatas=metas_batch,
                                )
                                result["missing_added"] += len(ids_batch)
                                ids_batch = []
                                embeddings_batch = []
                                docs_batch = []
                                metas_batch = []

                    if ids_batch:
                        collection.upsert(
                            ids=ids_batch,
                            embeddings=embeddings_batch,
                            documents=docs_batch,
                            metadatas=metas_batch,
                        )
                        result["missing_added"] += len(ids_batch)

                self._hybrid_disabled.pop(table, None)
            except Exception as e:
                logger.warning(
                    "hybrid_db.reconcile_failed",
                    {"table": table, "column": col, "error": str(e)},
                    user_id="system",
                )

        return result

    def health(self, table: str) -> dict:
        with self._connect() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            sql_count = cur.fetchone()[0]

        chroma_docs: dict[str, int] = {}
        status = "ok"

        for col in self._get_longtext_columns(table):
            collection_name = f"{table}_{col}"
            try:
                collection = self._get_collection(collection_name)
                chroma_docs[collection_name] = collection.count()
                if chroma_docs[collection_name] != sql_count:
                    status = "drift"
            except Exception:
                chroma_docs[collection_name] = -1
                status = "broken"

        pending = self._journal_count(table)
        if pending > 0 and status == "ok":
            status = "drift"

        return {
            "sqlite_rows": sql_count,
            "chroma_docs": chroma_docs,
            "pending_journal": pending,
            "status": status,
        }

    def journal_status(self, table: str | None = None) -> dict:
        with self._connect() as cur:
            if table:
                cur.execute(
                    "SELECT status, COUNT(*) FROM _journal WHERE app_table = ? GROUP BY status",
                    (table,),
                )
            else:
                cur.execute("SELECT status, COUNT(*) FROM _journal GROUP BY status")
            rows = cur.fetchall()

        result = {"pending": 0, "failed": 0, "done": 0}
        for row in rows:
            if row[0] in result:
                result[row[0]] = row[1]
        return result

    def process_journal(self, limit: int = 5000) -> int:
        return self._process_journal(batch_limit=limit)

    def close(self) -> None:
        pass
