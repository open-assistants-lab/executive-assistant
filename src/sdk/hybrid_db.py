"""HybridDB: SQLite + FTS5 + ChromaDB + Graph + DuckDB with self-healing journal.

TEXT columns get keyword search. LONGTEXT columns get keyword + semantic search.
Graph capabilities: SQLite-backed nodes/edges, recursive CTE traversal, NetworkX algorithms.
Analytics: DuckDB columnar store synced via unified journal for fast OLAP queries.

All backed by an operation journal that guarantees consistency across all engines.
See docs/HYBRIDDB_SPEC.md and docs/HYBRIDDB_GRAPH_ANALYTICS.md for full design rationale.
"""

import json
import os
import shutil
import sqlite3
import struct
import tempfile
import threading
from collections import defaultdict
from collections.abc import Generator, Sequence
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

_CHROMA_INDEX_WARN_FACTOR = 0.5
_CHROMA_INDEX_MAX_M0 = 256
_CHROMA_INDEX_MAX_ELEMENTS = 10_000_000
_CHROMA_REBUILD_BATCH = 5000

_chroma_client_pool: dict[str, Any] = {}
_chroma_pool_lock = threading.Lock()

_SKIP_SEARCH_COLUMNS: set[str] = {
    "rowid", "id", "memory_id", "fact_key", "scope", "project_id",
    "created_at", "updated_at", "previous_value",
}

_SYSTEM_TABLES = {"_journal", "_schema", "_graph_nodes", "_graph_edges", "_graph_sync", "_edge_rules"}


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
        from hybriddb import default_embedding_fn as hybriddb_default

        return hybriddb_default(text)
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
    mag = sum(x ** 2 for x in embedding) ** 0.5
    if mag > 0:
        embedding = [x / mag for x in embedding]
    return embedding


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_SAFE_IDENTIFIER_RE = __import__("re").compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_safe_identifier(name: str) -> bool:
    return bool(_SAFE_IDENTIFIER_RE.match(name))


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
        from src.sdk.tools_core.apps import EMBEDDING_MODEL

        _EMBEDDING_MODEL_NAME = EMBEDDING_MODEL
    except ImportError:
        _EMBEDDING_MODEL_NAME = "unknown"
    return _EMBEDDING_MODEL_NAME


class HybridDB:
    """Hybrid search database: SQLite + FTS5 + ChromaDB + Graph + DuckDB with self-healing journal."""

    def __init__(
        self,
        path: str,
        embedding_fn: Any | None = None,
        embedding_model_name: str | None = None,
        force_model: bool = False,
        max_chroma_index_gb: int = 5,
        auto_rebuild_chroma: bool = False,
    ):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

        self._db_path = str((self.path / "app.db").resolve())
        self._vector_path = str((self.path / "vectors").resolve())
        Path(self._vector_path).mkdir(parents=True, exist_ok=True)

        self._embedding_fn = embedding_fn or _default_embedding_fn
        self._embedding_model_name = embedding_model_name or "unknown"
        if embedding_fn is not None and embedding_model_name is None:
            logger.warning(
                "hybriddb.embedding_model_name_missing",
                {"hint": "Pass embedding_model_name to detect embedding mismatches"},
                user_id="system",
            )
        self._max_chroma_index_gb = max_chroma_index_gb
        self._db_lock = threading.RLock()
        self._hybrid_disabled: dict[str, bool] = {}

        self._nx_cache: dict[str, Any] = {"graph": None, "dirty": True, "directed": None}

        self._init_system_tables()
        if self._max_chroma_index_gb > 0:
            self._init_chroma(force_model)
        else:
            self._chroma = None
        self._init_duckdb()
        if self._max_chroma_index_gb > 0:
            self._check_index_health(auto_rebuild_chroma)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Cursor, None, None]:
        with self._db_lock:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA foreign_keys = ON")
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

        self._init_graph_tables()

    def _init_graph_tables(self) -> None:
        with self._connect() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _graph_nodes (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT 'node',
                    domain TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'inferred',
                    properties JSON DEFAULT '{}',
                    embedding_model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _graph_edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'relates_to',
                    weight REAL DEFAULT 1.0,
                    properties JSON DEFAULT '{}',
                    valid_from TEXT,
                    valid_until TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES _graph_nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES _graph_nodes(id) ON DELETE CASCADE
                )
            """)
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_unique "
                "ON _graph_edges(source_id, target_id, type)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON _graph_edges(source_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON _graph_edges(target_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON _graph_edges(type)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON _graph_nodes(type)"
            )
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_domain ON _graph_nodes(domain)"
                )
            except sqlite3.OperationalError:
                pass
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_confidence ON _graph_nodes(confidence)"
                )
            except sqlite3.OperationalError:
                pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _graph_sync (
                    table_name TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    id_column TEXT NOT NULL DEFAULT 'id',
                    label_template TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _edge_rules (
                    source_table TEXT NOT NULL,
                    target_table TEXT NOT NULL,
                    target_match TEXT NOT NULL,
                    source_column TEXT,
                    target_column TEXT,
                    edge_type TEXT NOT NULL,
                    PRIMARY KEY (source_table, target_table, edge_type)
                )
            """)
            existing_cols = {
                row["name"] for row in cur.execute("PRAGMA table_info(_edge_rules)").fetchall()
            }
            if "source_column" not in existing_cols:
                cur.execute("ALTER TABLE _edge_rules ADD COLUMN source_column TEXT")
            if "target_column" not in existing_cols:
                cur.execute("ALTER TABLE _edge_rules ADD COLUMN target_column TEXT")

    def _init_chroma(self, force: bool = False) -> None:
        key = os.fspath(self._vector_path)
        with _chroma_pool_lock:
            if key in _chroma_client_pool:
                try:
                    _chroma_client_pool[key].heartbeat()
                except Exception:
                    _chroma_client_pool.pop(key, None)
                else:
                    self._chroma = _chroma_client_pool[key]
                    return

            try:
                client = chromadb.PersistentClient(
                    path=self._vector_path,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            except Exception:
                logger.warning(
                    "hybriddb.chroma_init_failed",
                    {"vector_path": self._vector_path},
                    user_id="system",
                )
                self._chroma = None
                return

            _chroma_client_pool[key] = client
            self._chroma = client

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

    def _init_duckdb(self) -> None:
        import duckdb

        self._duckdb_path = str((self.path / "analytics.duckdb").resolve())
        self._duckdb_synced_tables: dict[str, dict] = {}
        self._duckdb_conn = None

        try:
            self._duckdb_conn = duckdb.connect(self._duckdb_path)
            self._duckdb_conn.execute("SET threads = 4")
            self._duckdb_conn.execute("""
                CREATE TABLE IF NOT EXISTS _duckdb_sync (
                    table_name TEXT PRIMARY KEY,
                    synced_count INTEGER DEFAULT 0
                )
            """)
            existing = self._duckdb_conn.execute(
                "SELECT table_name FROM _duckdb_sync"
            ).fetchall()
            for (tname,) in existing:
                quoted_tname = self._duckdb_quote_identifier(tname)
                count = self._duckdb_conn.execute(
                    f"SELECT count(*) FROM {quoted_tname}"
                ).fetchone()[0]
                cols_info = self._duckdb_conn.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = ?", (tname,)
                ).fetchall()
                columns = {c: t for c, t in cols_info}
                self._duckdb_synced_tables[tname] = {"columns": columns, "count": count}
        except Exception as e:
            logger.warning("duckdb.init_failed", {"error": str(e)}, user_id="system")
            self._duckdb_path = ""
            self._duckdb_conn = None

    def _auto_register_duckdb_tables(self) -> None:
        """Auto-register all non-system app tables with DuckDB."""
        if not self._duckdb_path:
            return

        app_tables = self.list_tables()
        new_tables = [t for t in app_tables if t not in self._duckdb_synced_tables]

        if not new_tables:
            return

        for table in new_tables:
            self.register_duckdb_table(table)

        logger.info(
            "duckdb.auto_registered",
            {"tables": new_tables, "count": len(new_tables)},
            user_id="system",
        )

    def register_duckdb_table(self, table: str) -> bool:
        if not self._duckdb_path or self._duckdb_conn is None:
            return False

        meta = self._table_meta(table)
        if not meta:
            logger.warning("duckdb.register_missing_table", {"table": table}, user_id="system")
            return False

        cols = []
        for col_name, col_type in meta["columns"].items():
            base = col_type.replace("_PK", "")
            quoted_col = self._duckdb_quote_identifier(col_name)
            if base == "BOOLEAN":
                cols.append(f"{quoted_col} INTEGER")
            elif base == "JSON":
                cols.append(f"{quoted_col} TEXT")
            elif base in ("TEXT", "LONGTEXT"):
                cols.append(f"{quoted_col} TEXT")
            elif base == "INTEGER" or base == "INTEGER_PK":
                cols.append(f"{quoted_col} BIGINT")
            else:
                cols.append(f"{quoted_col} {base}")
        if "id" not in meta["columns"]:
            cols.insert(0, "id BIGINT")

        quoted_table = self._duckdb_quote_identifier(table)
        with self._db_lock:
            dk = self._duckdb_conn
            dk.execute(f"DROP TABLE IF EXISTS {quoted_table}")
            dk.execute(f"CREATE TABLE {quoted_table} ({', '.join(cols)})")
            dk.execute(
                "INSERT OR REPLACE INTO _duckdb_sync (table_name, synced_count) VALUES (?, 0)",
                (table,),
            )

        self._duckdb_synced_tables[table] = {"columns": dict(meta["columns"]), "count": 0}
        self._full_sync_duckdb_table(table)
        return True

    @staticmethod
    def _duckdb_quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _refresh_duckdb_table_if_registered(self, table: str) -> None:
        if table in self._duckdb_synced_tables:
            self.register_duckdb_table(table)

    def _full_sync_duckdb_table(self, table: str) -> None:
        if not self._duckdb_path or table not in self._duckdb_synced_tables:
            return

        with self._db_lock:
            dk = self._duckdb_conn
            quoted_table = self._duckdb_quote_identifier(table)
            dk.execute(f"DELETE FROM {quoted_table}")
            try:
                dk.execute("DETACH src")
            except Exception:
                pass
            try:
                dk.execute(f"ATTACH '{self._db_path}' AS src (TYPE sqlite)")
                dk.execute(f"INSERT INTO {quoted_table} SELECT * FROM src.{quoted_table}")
            finally:
                dk.execute("DETACH src")
            count = dk.execute(f"SELECT count(*) FROM {quoted_table}").fetchone()[0]
            dk.execute(
                "UPDATE _duckdb_sync SET synced_count = ? WHERE table_name = ?",
                (count, table),
            )
            self._duckdb_synced_tables[table]["count"] = count

    def unregister_duckdb_table(self, table: str) -> bool:
        if table not in self._duckdb_synced_tables:
            return False

        with self._db_lock:
            dk = self._duckdb_conn
            dk.execute(f"DROP TABLE IF EXISTS {self._duckdb_quote_identifier(table)}")
            dk.execute("DELETE FROM _duckdb_sync WHERE table_name = ?", (table,))
        self._duckdb_synced_tables.pop(table, None)
        return True

    def analytics(self, sql: str) -> list[dict]:
        if not self._duckdb_path:
            raise RuntimeError(
                "DuckDB analytics not available — DuckDB initialization failed or module not installed"
            )

        with self._db_lock:
            dk = self._duckdb_conn
            result = dk.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows

    def _sync_duckdb_from_journal(self, entries: list[dict]) -> None:
        if not self._duckdb_path or not self._duckdb_synced_tables:
            return

        by_table: dict[str, dict[str, list[int]]] = {}
        seen_ids: set[int] = set()

        for e in entries:
            if e["id"] in seen_ids:
                continue
            seen_ids.add(e["id"])
            tbl = e["app_table"]
            if tbl not in self._duckdb_synced_tables:
                continue
            if tbl not in by_table:
                by_table[tbl] = {"add": [], "delete": []}
            row_id = e["row_id"]
            if row_id is not None:
                by_table[tbl]["delete"].append(row_id)
                if e["op"] != "row_delete":
                    by_table[tbl]["add"].append(row_id)

        if not by_table:
            return

        with self._db_lock:
            dk = self._duckdb_conn
            dk.execute(f"ATTACH '{self._db_path}' AS src (TYPE sqlite)")

            for tbl, ops in by_table.items():
                quoted_tbl = self._duckdb_quote_identifier(tbl)
                if ops["delete"]:
                    ids = ",".join(str(i) for i in ops["delete"])
                    dk.execute(f"DELETE FROM {quoted_tbl} WHERE id IN ({ids})")
                if ops["add"]:
                    ids = ",".join(str(i) for i in ops["add"])
                    dk.execute(
                        f"INSERT INTO {quoted_tbl} SELECT * FROM src.{quoted_tbl} WHERE id IN ({ids})"
                    )
                count = dk.execute(f"SELECT count(*) FROM {quoted_tbl}").fetchone()[0]
                dk.execute(
                    "UPDATE _duckdb_sync SET synced_count = ? WHERE table_name = ?",
                    (count, tbl),
                )
                self._duckdb_synced_tables[tbl]["count"] = count

            dk.execute("DETACH src")

    def _check_index_health(self, auto_rebuild: bool = False) -> None:
        max_bytes = self._max_chroma_index_gb * 1024**3
        warn_bytes = int(max_bytes * _CHROMA_INDEX_WARN_FACTOR)

        vector_dir = Path(self._vector_path)
        for seg_dir in vector_dir.iterdir():
            if not seg_dir.is_dir():
                continue
            link_file = seg_dir / "link_lists.bin"
            header_file = seg_dir / "header.bin"
            if not link_file.exists() or not header_file.exists():
                continue

            size_bytes = link_file.stat().st_size
            size_gb = size_bytes / (1024**3)
            header_corrupt = self._is_hnsw_header_corrupt(str(header_file), str(link_file))

            if size_bytes >= warn_bytes or header_corrupt:
                logger.warning(
                    "chromadb.index_bloated",
                    {
                        "path": str(link_file),
                        "size_gb": round(size_gb, 2),
                        "max_gb": self._max_chroma_index_gb,
                        "header_corrupt": header_corrupt,
                    },
                    user_id="system",
                )

            if size_bytes > max_bytes or header_corrupt:
                logger.error(
                    "chromadb.index_needs_rebuild",
                    {
                        "path": str(link_file),
                        "size_gb": round(size_gb, 2),
                        "reason": "header_corrupt" if header_corrupt else "size_exceeded",
                    },
                    user_id="system",
                )
                if auto_rebuild:
                    logger.info(
                        "chromadb.auto_rebuilding",
                        {"path": str(link_file)},
                        user_id="system",
                    )
                    self._rebuild_chroma_index()
                    return

    @staticmethod
    def _is_hnsw_header_corrupt(header_path: str, link_path: str) -> bool:
        try:
            with open(header_path, "rb") as f:
                data = f.read()
            if len(data) < 68:
                return True

            max_elements = struct.unpack_from("Q", data, 8)[0]
            size_data_per_element = struct.unpack_from("Q", data, 24)[0]
            max_m0 = struct.unpack_from("I", data, 56)[0]

            if max_elements == 0 or max_elements > _CHROMA_INDEX_MAX_ELEMENTS:
                return True
            if size_data_per_element != EMBEDDING_DIM * 4:
                return True
            if max_m0 > _CHROMA_INDEX_MAX_M0:
                return True
            return False
        except Exception:
            return True

    def _rebuild_chroma_index(self) -> None:
        if self._chroma is None:
            return
        old_path = Path(self._vector_path)
        temp_root = Path(tempfile.mkdtemp(dir=old_path.parent, prefix="chroma_rebuild_"))
        temp_vectors = temp_root / "vectors"
        try:
            new_client = chromadb.PersistentClient(
                path=str(temp_vectors),
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            collection_names = self._chroma.list_collections()
            for coll_name in collection_names:
                coll_name_str = coll_name.name if hasattr(coll_name, "name") else str(coll_name)
                old_col = self._chroma.get_collection(coll_name_str)
                metadata = old_col.metadata
                new_col = new_client.create_collection(
                    name=coll_name_str, metadata=metadata
                )

                offset = 0
                while True:
                    result = old_col.get(
                        limit=_CHROMA_REBUILD_BATCH,
                        offset=offset,
                        include=["embeddings", "documents", "metadatas"],
                    )
                    ids = result.get("ids", [])
                    if not ids:
                        break
                    embeddings_list = result.get("embeddings", [])
                    docs_list = result.get("documents", [])
                    metas_list = result.get("metadatas", [])
                    if None in embeddings_list or None in docs_list:
                        raise RuntimeError(
                            f"Corrupt vector data in collection '{coll_name_str}' "
                            f"at offset {offset} — manual intervention required"
                        )
                    new_col.add(
                        ids=ids,
                        embeddings=embeddings_list,
                        documents=docs_list,
                        metadatas=metas_list,
                    )
                    offset += _CHROMA_REBUILD_BATCH

            backup_path = old_path.with_suffix(
                old_path.suffix
                + ".backup_"
                + datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            )
            shutil.move(str(old_path), str(backup_path))
            try:
                shutil.move(str(temp_vectors), str(old_path))
            except Exception:
                shutil.move(str(backup_path), str(old_path))
                raise

            shutil.rmtree(str(temp_root), ignore_errors=True)

            self._chroma = chromadb.PersistentClient(
                path=str(old_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            key = os.fspath(old_path)
            with _chroma_pool_lock:
                _chroma_client_pool[key] = self._chroma
            logger.info(
                "chromadb.index_rebuilt",
                {
                    "old_backup": str(backup_path),
                    "new_path": str(old_path),
                },
                user_id="system",
            )
        except Exception:
            shutil.rmtree(str(temp_root), ignore_errors=True)
            raise

    def force_rebuild_chroma_index(self) -> dict:
        if self._chroma is None:
            return {"status": "unavailable", "error": "ChromaDB not initialized"}
        self._rebuild_chroma_index()
        total = sum(
            self._chroma.get_collection(c.name if hasattr(c, "name") else str(c)).count()
            for c in self._chroma.list_collections()
        )
        return {
            "status": "rebuilt",
            "vectors_copied": total,
        }

    def _get_embedding(self, text: str) -> list[float]:
        if not text:
            return [0.0] * EMBEDDING_DIM
        return self._embedding_fn(text)

    def _get_collection(self, name: str):
        if self._chroma is None:
            return None
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
            logger.warning("row_to_metadata.table_not_found", {"table": table}, user_id="system")
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

    @staticmethod
    def _resolve_internal_rowid(cur: sqlite3.Cursor, table: str, user_pk: int | str) -> int | None:
        row = cur.execute(
            f"SELECT rowid FROM {table} WHERE id = ?", (user_pk,)
        ).fetchone()
        return row[0] if row else None

    def _create_fts5(
        self, cur: sqlite3.Cursor, table: str, col: str, use_id: bool | None = None
    ) -> None:
        fts_name = f"{table}_fts_{col}"
        if use_id is None:
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
        use_id = self._has_autoincrement_id(table)
        for col in self._get_text_columns(table):
            self._drop_fts5(cur, table, col)
            self._create_fts5(cur, table, col, use_id)

    def _invalidate_nx_cache(self) -> None:
        self._nx_cache["dirty"] = True

    # ── Schema ──────────────────────────────────────────────

    def create_table(self, table: str, columns: dict[str, str]) -> None:
        if "_fts_" in table:
            raise ValueError(
                f"Table name '{table}' contains '_fts_' which conflicts with FTS5 naming convention"
            )
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

            existing_meta = self._table_meta(table)
            existing_cols: dict[str, str] = existing_meta["columns"] if existing_meta else {}
            cur.execute(f"PRAGMA table_info({table})")
            actual_cols = {row["name"] for row in cur.fetchall()}
            for col_name, col_parsed_type in parsed.items():
                if col_name in existing_cols or col_name in actual_cols:
                    continue
                sqlite_type = (
                    "INTEGER" if col_parsed_type == "BOOLEAN"
                    else "TEXT" if col_parsed_type in ("LONGTEXT", "JSON")
                    else col_parsed_type.replace("_PK", "")
                )
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {sqlite_type}")
                logger.info(
                    "hybriddb.migrate_column_added",
                    {"table": table, "column": col_name, "type": col_parsed_type},
                    user_id="system",
                )

            text_cols = [c for c, t in parsed.items() if t in ("TEXT", "LONGTEXT")]
            use_id = self._has_autoincrement_id(table)
            for col in text_cols:
                self._create_fts5(cur, table, col, use_id)

            for col in self._get_longtext_columns_from_parsed(parsed):
                self._get_collection(f"{table}_{col}")

            self._save_table_meta(cur, table, parsed)

        self._refresh_duckdb_table_if_registered(table)

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
                self._create_fts5(cur, table, column, self._has_autoincrement_id(table))

            if base_type == "LONGTEXT":
                self._get_collection(f"{table}_{column}")

            self._save_table_meta(cur, table, new_columns, dirty=(base_type == "LONGTEXT"))

        self._refresh_duckdb_table_if_registered(table)

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

            self._save_table_meta(cur, table, old_columns, dirty=True)

            if col_type in ("TEXT", "LONGTEXT"):
                self._drop_fts5(cur, table, column)

            self._rebuild_all_fts5(cur, table)

            if col_type == "LONGTEXT" and self._chroma is not None:
                try:
                    self._chroma.delete_collection(f"{table}_{column}")
                except Exception:
                    pass

        self._refresh_duckdb_table_if_registered(table)

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
                self._create_fts5(cur, table, new_name, self._has_autoincrement_id(table))

            if col_type == "LONGTEXT" and self._chroma is not None:
                try:
                    old_coll = self._get_collection(f"{table}_{old_name}")
                    if old_coll is not None:
                        all_data = old_coll.get(
                            include=["embeddings", "documents", "metadatas"]
                        )
                        if all_data.get("ids"):
                            new_coll = self._get_collection(f"{table}_{new_name}")
                            new_coll.upsert(
                                ids=all_data["ids"],
                                embeddings=all_data["embeddings"],
                                documents=all_data["documents"],
                                metadatas=all_data.get("metadatas"),
                            )
                        self._chroma.delete_collection(f"{table}_{old_name}")
                except Exception as e:
                    logger.warning(
                        "hybriddb.rename_chroma_failed",
                        {"table": table, "old": old_name, "new": new_name, "error": str(e)},
                        user_id="system",
                    )

            self._save_table_meta(cur, table, new_columns, dirty=True)

        self._refresh_duckdb_table_if_registered(table)

    def list_tables(self) -> list[str]:
        with self._connect() as cur:
            cur.execute("SELECT table_name FROM _schema ORDER BY table_name")
            tables = [row["table_name"] for row in cur.fetchall()]
        return [t for t in tables if t not in _SYSTEM_TABLES and not t.startswith("_")]

    def get_schema(self, table: str) -> dict[str, str]:
        meta = self._table_meta(table)
        if not meta:
            return {}
        return meta["columns"]

    # ── CRUD ────────────────────────────────────────────────

    def insert(
        self,
        table: str,
        data: dict,
        sync: bool = True,
        skip_journal_columns: set[str] | None = None,
    ) -> int | str:
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
            internal_rowid = cur.lastrowid
            has_auto_id = self._has_autoincrement_id(table)

            if has_auto_id:
                user_pk = internal_rowid
                row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (user_pk,)).fetchone())
            elif "id" in filtered:
                user_pk = filtered["id"]
                row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (user_pk,)).fetchone())
            else:
                user_pk = internal_rowid
                row = dict(
                    cur.execute(f"SELECT * FROM {table} WHERE rowid = ?", (internal_rowid,)).fetchone()
                )

            metadata = self._row_to_metadata(table, row)
            now = _now_iso()
            for col in self._get_longtext_columns(table):
                if skip_journal_columns and col in skip_journal_columns:
                    continue
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                    "VALUES (?, ?, ?, 'add', ?, ?, ?)",
                    (table, internal_rowid, col, row.get(col, ""), json.dumps(metadata), now),
                )
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, op, data, created_at) "
                "VALUES (?, ?, 'row_add', ?, ?)",
                (table, internal_rowid, json.dumps(dict(row), default=str), now),
            )

        if sync:
            self._process_journal()
        return user_pk or 0

    def row_to_metadata(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        return self._row_to_metadata(table, row)

    def vector_upsert(
        self,
        collection_name: str,
        row_id: int | str,
        document: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        collection = self._get_collection(collection_name)
        if collection is None:
            return False
        collection.upsert(
            ids=[str(row_id)],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata or {}],
        )
        return True

    def sync_duckdb_table(self, table: str) -> None:
        self._full_sync_duckdb_table(table)

    def insert_batch(self, table: str, rows: list[dict], sync: bool = True) -> list[int]:
        if len(rows) > JOURNAL_CAP:
            logger.warning(
                "insert_batch.large_batch",
                {"table": table, "rows": len(rows), "limit": JOURNAL_CAP},
                user_id="system",
            )
        meta = self._table_meta(table)
        if not meta:
            raise ValueError(f"Table '{table}' not found")

        ids: list[int] = []
        with self._connect() as cur:
            now = _now_iso()
            has_auto_id = self._has_autoincrement_id(table)

            # Phase 1: insert all rows, collect IDs
            row_builders: list[tuple[dict[str, Any], int]] = []
            for data in rows:
                filtered = {k: v for k, v in data.items() if k in meta["columns"]}
                columns = list(filtered.keys())
                placeholders = ", ".join("?" * len(columns))
                values = list(filtered.values())

                cur.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    values,
                )
                internal_rowid = cur.lastrowid

                if has_auto_id:
                    user_pk = internal_rowid
                elif "id" in filtered:
                    user_pk = filtered["id"]
                else:
                    user_pk = internal_rowid
                ids.append(user_pk)
                row_builders.append((filtered, internal_rowid))

            # Phase 2: construct row dicts from inserted data (avoids N individual SELECTs)
            for filtered, internal_rowid in row_builders:
                row = dict(filtered)
                if has_auto_id:
                    row.setdefault("id", internal_rowid)

                metadata = self._row_to_metadata(table, row)
                for col in self._get_longtext_columns(table):
                    cur.execute(
                        "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                        "VALUES (?, ?, ?, 'add', ?, ?, ?)",
                        (table, internal_rowid, col, row.get(col, ""), json.dumps(metadata), now),
                    )
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, op, data, created_at) "
                    "VALUES (?, ?, 'row_add', ?, ?)",
                    (table, internal_rowid, json.dumps(dict(row), default=str), now),
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
            internal_rowid = self._resolve_internal_rowid(cur, table, row_id)
            if internal_rowid is None:
                return False

            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            cur.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?",
                list(filtered.values()) + [row_id],
            )
            if cur.rowcount == 0:
                return False

            row = dict(cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone())

            metadata = self._row_to_metadata(table, row)
            now = _now_iso()
            for col in self._get_longtext_columns(table):
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, data, metadata, created_at) "
                    "VALUES (?, ?, ?, 'update', ?, ?, ?)",
                    (table, internal_rowid, col, row.get(col, ""), json.dumps(metadata), now),
                )
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, op, data, created_at) "
                "VALUES (?, ?, 'row_update', ?, ?)",
                (table, internal_rowid, json.dumps(dict(row), default=str), now),
            )

        if sync:
            self._process_journal()
        return True

    def delete(self, table: str, row_id: int | str, sync: bool = True) -> bool:
        with self._connect() as cur:
            internal_rowid = self._resolve_internal_rowid(cur, table, row_id)
            if internal_rowid is None:
                return False

            cur.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            if cur.rowcount == 0:
                return False

            now = _now_iso()
            for col in self._get_longtext_columns(table):
                cur.execute(
                    "INSERT INTO _journal (app_table, row_id, column_name, op, created_at) "
                    "VALUES (?, ?, ?, 'delete', ?)",
                    (table, internal_rowid, col, now),
                )
            cur.execute(
                "INSERT INTO _journal (app_table, row_id, op, created_at) "
                "VALUES (?, ?, 'row_delete', ?)",
                (table, internal_rowid, now),
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

    # ── Graph ────────────────────────────────────────────────

    def register_entity_node(
        self,
        table_name: str,
        type: str = "entity",
        id_column: str = "id",
        label_template: str = "",
    ) -> bool:
        meta = self._table_meta(table_name)
        if not meta:
            return False
        tmpl = label_template or f"{table_name}: {{{id_column}}}"
        with self._connect() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO _graph_sync (table_name, node_type, id_column, label_template) "
                "VALUES (?, ?, ?, ?)",
                (table_name, type, id_column, tmpl),
            )
        return True

    def register_edge_rule(
        self,
        source_table: str,
        target_table: str,
        target_match: str | None = None,
        edge_type: str = "relates_to",
        source_column: str | None = None,
        target_column: str | None = None,
    ) -> bool:
        if bool(source_column) != bool(target_column):
            raise ValueError("source_column and target_column must be provided together")
        if source_column is None and target_column is None:
            if target_match is None:
                raise ValueError("target_match or source_column/target_column is required")
            source_column = target_match
            target_column = "id"

        with self._connect() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO _edge_rules "
                "(source_table, target_table, target_match, source_column, target_column, edge_type) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source_table, target_table, target_match or source_column, source_column, target_column, edge_type),
            )
        return True

    def _auto_sync_graph_nodes(self) -> dict:
        result = {"nodes_created": 0}
        rules = self.raw_query("SELECT * FROM _graph_sync")
        for rule in rules:
            table = rule["table_name"]
            if table in _SYSTEM_TABLES:
                continue
            id_col = rule["id_column"]
            if not _is_safe_identifier(table) or not _is_safe_identifier(id_col):
                continue
            tmpl = rule["label_template"]
            ntype = rule["node_type"]
            rows = self.raw_query(f"SELECT {id_col} FROM {table}")
            for row in rows:
                rid = str(row[id_col])
                label = tmpl.replace(f"{{{id_col}}}", rid)
                existing = self.get_node(rid)
                if existing and existing.get("type") == ntype:
                    continue
                self.add_node(rid, label=label, type=ntype, source="auto_sync")
                result["nodes_created"] += 1
        return result

    def _auto_sync_graph_edges(self) -> dict:
        result = {"edges_created": 0}
        rules = self.raw_query("SELECT * FROM _edge_rules")
        for rule in rules:
            src_table = rule["source_table"]
            tgt_table = rule["target_table"]
            src_col = rule.get("source_column") or rule["target_match"]
            tgt_col = rule.get("target_column") or rule["target_match"]
            if (
                not _is_safe_identifier(src_table)
                or not _is_safe_identifier(tgt_table)
                or not _is_safe_identifier(src_col)
                or not _is_safe_identifier(tgt_col)
            ):
                continue
            etype = rule["edge_type"]
            pairs = self.raw_query(
                f"SELECT s.id as sid, t.id as tid FROM {src_table} s "
                f"JOIN {tgt_table} t ON s.{src_col} = t.{tgt_col}"
            )
            for pair in pairs:
                self.add_edge(None, str(pair["sid"]), str(pair["tid"]), type=etype)
                result["edges_created"] += 1
        return result

    def add_node(
        self,
        node_id: str,
        label: str = "",
        type: str = "node",
        domain: str = "",
        confidence: float = 0.5,
        source: str = "inferred",
        properties: dict | None = None,
    ) -> str:
        self._invalidate_nx_cache()
        now = _now_iso()
        props_json = json.dumps(properties or {})
        with self._connect() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO _graph_nodes "
                "(id, label, type, domain, confidence, source, properties, embedding_model, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (node_id, label, type, domain, confidence, source, props_json,
                 self._embedding_model_name, now, now),
            )
        return node_id

    def add_nodes(self, nodes: list[dict]) -> list[str]:
        self._invalidate_nx_cache()
        ids: list[str] = []
        with self._connect() as cur:
            for n in nodes:
                node_id = n["id"]
                now = _now_iso()
                cur.execute(
                    "INSERT OR REPLACE INTO _graph_nodes "
                    "(id, label, type, domain, confidence, source, properties, embedding_model, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        node_id,
                        n.get("label", ""),
                        n.get("type", "node"),
                        n.get("domain", ""),
                        n.get("confidence", 0.5),
                        n.get("source", "inferred"),
                        json.dumps(n.get("properties", {})),
                        self._embedding_model_name,
                        now,
                        now,
                    ),
                )
                ids.append(node_id)
        return ids

    def get_node(self, node_id: str) -> dict | None:
        with self._connect() as cur:
            cur.execute("SELECT * FROM _graph_nodes WHERE id = ?", (node_id,))
            row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["properties"] = json.loads(d.get("properties", "{}"))
        return d

    def update_node(self, node_id: str, data: dict) -> bool:
        self._invalidate_nx_cache()
        node = self.get_node(node_id)
        if not node:
            return False
        updated: dict[str, Any] = {"updated_at": _now_iso()}
        for field in ("label", "type", "domain", "confidence", "source"):
            if field in data:
                updated[field] = data[field]
        if "properties" in data:
            merged = dict(node["properties"])
            merged.update(data["properties"])
            updated["properties"] = json.dumps(merged)
        set_clause = ", ".join(f"{k} = ?" for k in updated)
        values = list(updated.values()) + [node_id]
        with self._connect() as cur:
            cur.execute(f"UPDATE _graph_nodes SET {set_clause} WHERE id = ?", values)
        return True

    def delete_node(self, node_id: str) -> bool:
        self._invalidate_nx_cache()
        with self._connect() as cur:
            cur.execute("DELETE FROM _graph_nodes WHERE id = ?", (node_id,))
            if cur.rowcount == 0:
                return False
        return True

    def list_nodes(
        self,
        type: str | None = None,
        domain: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[dict]:
        sql = "SELECT * FROM _graph_nodes WHERE 1=1"
        params: list[Any] = []
        if type:
            sql += " AND type = ?"
            params.append(type)
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if min_confidence > 0:
            sql += " AND confidence >= ?"
            params.append(min_confidence)
        sql += " ORDER BY created_at DESC"
        if limit > 0:
            sql += f" LIMIT {limit}"
        with self._connect() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["properties"] = json.loads(d.get("properties", "{}"))
            result.append(d)
        return result

    def add_edge(
        self,
        edge_id: str | None,
        source_id: str,
        target_id: str,
        type: str = "relates_to",
        weight: float = 1.0,
        properties: dict | None = None,
        valid_until: str | None = None,
    ) -> str:
        self._invalidate_nx_cache()
        if edge_id is None:
            import uuid
            edge_id = uuid.uuid4().hex[:16]
        now = _now_iso()
        props_json = json.dumps(properties or {})
        with self._connect() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO _graph_edges "
                "(id, source_id, target_id, type, weight, properties, valid_until, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (edge_id, source_id, target_id, type, weight, props_json, valid_until, now),
            )
        return edge_id

    def add_edges(self, edges: list[dict]) -> list[str]:
        self._invalidate_nx_cache()
        import uuid

        ids: list[str] = []
        with self._connect() as cur:
            for e in edges:
                edge_id = e.get("id") or uuid.uuid4().hex[:16]
                now = _now_iso()
                cur.execute(
                    "INSERT OR REPLACE INTO _graph_edges "
                    "(id, source_id, target_id, type, weight, properties, valid_until, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        edge_id,
                        e["source_id"],
                        e["target_id"],
                        e.get("type", "relates_to"),
                        e.get("weight", 1.0),
                        json.dumps(e.get("properties", {})),
                        e.get("valid_until"),
                        now,
                    ),
                )
                ids.append(edge_id)
        return ids

    def get_edge(self, edge_id: str) -> dict | None:
        with self._connect() as cur:
            cur.execute("SELECT * FROM _graph_edges WHERE id = ?", (edge_id,))
            row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["properties"] = json.loads(d.get("properties", "{}"))
        return d

    def update_edge(self, edge_id: str, data: dict) -> bool:
        self._invalidate_nx_cache()
        edge = self.get_edge(edge_id)
        if not edge:
            return False
        allowed = {"type", "weight", "properties", "source_id", "target_id", "valid_from", "valid_until"}
        filtered = {k: v for k, v in data.items() if k in allowed}
        if not filtered:
            return False
        if "properties" in filtered:
            merged = dict(edge["properties"])
            merged.update(filtered["properties"])
            filtered["properties"] = json.dumps(merged)
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        with self._connect() as cur:
            cur.execute(
                f"UPDATE _graph_edges SET {set_clause} WHERE id = ?",
                list(filtered.values()) + [edge_id],
            )
        return True

    def delete_edge(self, edge_id: str) -> bool:
        self._invalidate_nx_cache()
        with self._connect() as cur:
            cur.execute("DELETE FROM _graph_edges WHERE id = ?", (edge_id,))
            if cur.rowcount == 0:
                return False
        return True

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        sql = "SELECT * FROM _graph_edges WHERE 1=1"
        params: list[Any] = []
        if source_id:
            sql += " AND source_id = ?"
            params.append(source_id)
        if target_id:
            sql += " AND target_id = ?"
            params.append(target_id)
        if type:
            sql += " AND type = ?"
            params.append(type)
        sql += " ORDER BY created_at DESC"
        if limit > 0:
            sql += f" LIMIT {limit}"
        with self._connect() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["properties"] = json.loads(d.get("properties", "{}"))
            result.append(d)
        return result

    def neighbors(
        self,
        node_id: str,
        direction: str = "both",
        type: str | None = None,
    ) -> list[dict]:
        params: list[Any] = [node_id, node_id]

        if direction == "out":
            edge_clause = "e.source_id = ?"
            params.append(node_id)
        elif direction == "in":
            edge_clause = "e.target_id = ?"
            params.append(node_id)
        else:
            edge_clause = "(e.source_id = ? OR e.target_id = ?)"
            params.append(node_id)
            params.append(node_id)
        if type:
            edge_clause += " AND e.type = ?"
            params.append(type)

        sql = f"""
            SELECT e.id as edge_id, e.type as edge_type, e.weight,
                   e.properties as edge_properties, e.source_id, e.target_id,
                   n.id as node_id, n.label as node_label,
                   n.type as node_type, n.properties as node_properties
            FROM _graph_edges e
            JOIN _graph_nodes n ON (
                CASE WHEN e.source_id = ? AND e.target_id = n.id THEN 1
                     WHEN e.target_id = ? AND e.source_id = n.id THEN 1
                     ELSE 0 END = 1
            )
            WHERE {edge_clause}
            ORDER BY e.weight DESC
        """
        with self._connect() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        result = []
        seen = set()
        for r in rows:
            d = dict(r)
            node_pid = d["node_id"]
            if node_pid in seen:
                continue
            seen.add(node_pid)
            result.append({
                "node": {
                    "id": node_pid,
                    "label": d["node_label"],
                    "type": d["node_type"],
                    "properties": json.loads(d.get("node_properties", "{}")),
                },
                "edge": {
                    "id": d["edge_id"],
                    "type": d["edge_type"],
                    "weight": d["weight"],
                    "source_id": d["source_id"],
                    "target_id": d["target_id"],
                    "properties": json.loads(d.get("edge_properties", "{}")),
                },
            })
        return result

    def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        direction: str = "out",
        type: str | None = None,
        max_cost: float = 3.0,
    ) -> list[dict]:
        if max_depth < 1 or max_depth > 10:
            raise ValueError("max_depth must be between 1 and 10")
        if direction not in ("in", "out", "both"):
            raise ValueError("direction must be 'in', 'out', or 'both'")

        params: list[Any] = [start_id, start_id, start_id]
        type_filter = ""
        if type:
            type_filter = " AND e.type = ?"
            params.append(type)

        sql = f"""
            WITH RECURSIVE graph_path(node_id, depth, path, cum_cost) AS (
                SELECT ?, 0, ?, 0.0
                UNION ALL
                SELECT
                    CASE WHEN '{direction}' = 'in' THEN e.source_id
                         WHEN '{direction}' = 'out' THEN e.target_id
                         ELSE CASE WHEN e.source_id = gp.node_id THEN e.target_id
                                   ELSE e.source_id END
                    END,
                    gp.depth + 1,
                    gp.path || '>' || CASE WHEN '{direction}' = 'in' THEN e.source_id
                                         WHEN '{direction}' = 'out' THEN e.target_id
                                         ELSE CASE WHEN e.source_id = gp.node_id THEN e.target_id
                                                   ELSE e.source_id END
                    END,
                    gp.cum_cost + (1.0 - e.weight)
                FROM _graph_edges e
                JOIN graph_path gp ON (
                    CASE WHEN '{direction}' = 'in' THEN e.target_id = gp.node_id
                         WHEN '{direction}' = 'out' THEN e.source_id = gp.node_id
                         ELSE (e.source_id = gp.node_id OR e.target_id = gp.node_id)
                    END
                )
                {type_filter}
                WHERE gp.depth < {max_depth}
                  AND gp.cum_cost + (1.0 - e.weight) <= {max_cost}
            )
            SELECT DISTINCT node_id, MIN(depth) as depth, MIN(path) as path,
                   MIN(cum_cost) as cum_cost
            FROM graph_path
            WHERE node_id != ?
            GROUP BY node_id
            ORDER BY depth, cum_cost
        """
        return self.raw_query(sql, tuple(params))

    def decay_edges(self) -> int:
        self._invalidate_nx_cache()
        now = _now_iso()
        expired = self.raw_query(
            "SELECT id, weight FROM _graph_edges "
            "WHERE valid_until IS NOT NULL AND valid_until < ?",
            (now,),
        )
        dec = 0
        for e in expired:
            new_weight = max(e["weight"] - 0.15, 0.05)
            if new_weight <= 0.05:
                self.delete_edge(e["id"])
            else:
                self.update_edge(e["id"], {"weight": new_weight})
            dec += 1
        return dec

    # ── Graph Algorithms (NetworkX) ──────────────────────────

    def to_networkx(self, directed: bool = True, use_cache: bool = True):
        import networkx as nx

        if (
            use_cache
            and not self._nx_cache["dirty"]
            and self._nx_cache["graph"] is not None
            and self._nx_cache.get("directed") == directed
        ):
            return self._nx_cache["graph"]

        g = nx.DiGraph() if directed else nx.Graph()
        nodes = self.raw_query(
            "SELECT id, label, type, domain, confidence, source, properties FROM _graph_nodes"
        )
        for n in nodes:
            props = (
                json.loads(n.get("properties", "{}"))
                if isinstance(n.get("properties"), str)
                else n.get("properties", {})
            )
            reserved = {"label", "type", "domain", "confidence", "source"}
            node_attrs = {k: v for k, v in props.items() if k not in reserved}
            g.add_node(
                n["id"],
                label=n["label"],
                type=n["type"],
                domain=n.get("domain", ""),
                confidence=n.get("confidence", 0.5),
                source=n.get("source", "inferred"),
                **node_attrs,
            )
        edges = self.raw_query(
            "SELECT id, source_id, target_id, type, weight, properties, valid_until "
            "FROM _graph_edges"
        )
        for e in edges:
            props = (
                json.loads(e.get("properties", "{}"))
                if isinstance(e.get("properties"), str)
                else e.get("properties", {})
            )
            reserved = {"id", "type", "weight", "valid_until"}
            edge_attrs = {k: v for k, v in props.items() if k not in reserved}
            g.add_edge(
                e["source_id"],
                e["target_id"],
                id=e["id"],
                type=e["type"],
                weight=e["weight"],
                valid_until=e.get("valid_until"),
                **edge_attrs,
            )
        if use_cache:
            self._nx_cache["graph"] = g
            self._nx_cache["dirty"] = False
            self._nx_cache["directed"] = directed
        return g

    def pagerank(self) -> dict[str, float]:
        import networkx as nx
        g = self.to_networkx(directed=True)
        return nx.pagerank(g, weight="weight")

    def betweenness_centrality(self) -> dict[str, float]:
        g = self.to_networkx(directed=False)
        import networkx as nx
        return nx.betweenness_centrality(g, weight="weight")

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        g = self.to_networkx(directed=True)
        import networkx as nx
        try:
            return nx.shortest_path(g, source=source, target=target, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def connected_components(self) -> list[set[str]]:
        g = self.to_networkx(directed=False)
        import networkx as nx
        return [set(c) for c in nx.connected_components(g)]

    def community_detect(self) -> list[set[str]]:
        g = self.to_networkx(directed=False)
        import networkx as nx
        partition = nx.community.louvain_communities(g, weight="weight")
        return [set(c) for c in partition]

    def search_graph(
        self,
        query: str,
        hop_expansion: int = 2,
        limit: int = 10,
    ) -> list[dict]:
        self._auto_sync_graph_nodes()
        self._auto_sync_graph_edges()

        registered = self.raw_query("SELECT table_name FROM _graph_sync")
        searchable_tables = [r["table_name"] for r in registered]

        found_nodes: dict[str, dict] = {}
        embedding: list[float] | None = None
        for table in searchable_tables:
            for col_name in self._get_longtext_columns(table):
                try:
                    if embedding is None:
                        embedding = self._get_embedding(query)
                    collection = self._get_collection(f"{table}_{col_name}")
                    if collection is None:
                        continue
                    vec_results = collection.query(
                        query_embeddings=[embedding],
                        n_results=limit,
                        include=["distances"],
                    )
                    for i, doc_id in enumerate(vec_results.get("ids", [[]])[0]):
                        distance = vec_results["distances"][0][i] if "distances" in vec_results else 0
                        found_nodes[str(doc_id)] = {
                            "table": table,
                            "similarity": max(0.0, 1.0 - distance),
                        }
                except Exception:
                    continue

        result_list = []
        for node_id, meta in found_nodes.items():
            entry = {"node_id": node_id, "similarity": meta["similarity"], "source_table": meta["table"]}
            if hop_expansion > 0:
                try:
                    neighbors = self.neighbors(node_id, direction="both")
                    entry["neighbors"] = neighbors[:hop_expansion * 2]
                except Exception:
                    entry["neighbors"] = []
            result_list.append(entry)
        result_list.sort(key=lambda x: x["similarity"], reverse=True)
        return result_list[:limit]

    # ── Search ──────────────────────────────────────────────

    def search(
        self,
        table: str,
        column: str,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
        fts_weight: float = 0.5,
        recency_weight: float = 0.0,
        recency_column: str | None = None,
        query_embedding: list[float] | None = None,
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
            vec_results = self._vector_search(
                table, column, query, None, limit * 2, query_embedding=query_embedding
            )

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
        all_text_cols = [c for c in self._get_text_columns(table) if c not in _SKIP_SEARCH_COLUMNS]

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
                escaped = query.replace("%", "\\%").replace("_", "\\_")
                with self._connect() as cur:
                    cur.execute(
                        f"SELECT id, 0.0 as score FROM {table} WHERE {column} LIKE ? LIMIT ?",
                        (f"%{escaped}%", limit),
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
        query_embedding: list[float] | None = None,
    ) -> list[tuple[int, float]]:
        collection_name = f"{table}_{column}"
        try:
            collection = self._get_collection(collection_name)
            embedding = query_embedding if query_embedding is not None else self._get_embedding(query)
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
                try:
                    out.append((int(doc_id), similarity))
                except ValueError:
                    out.append((doc_id, similarity))
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
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            days_ago = max((datetime.now(UTC) - ts).days, 0)
            return 1.0 / (1 + days_ago / 30)
        except (ValueError, TypeError):
            return 0.0

    def _fetch_rows_by_ids(self, table: str, ids: Sequence[int | str]) -> dict[int | str, dict]:
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

        chroma_entries = [e for e in entries if e["op"] in ("add", "update", "delete", "meta_update")]
        row_entries = [e for e in entries if e["op"].startswith("row_")]

        adds = [e for e in chroma_entries if e["op"] == "add"]
        updates = [e for e in chroma_entries if e["op"] == "update"]
        deletes = [e for e in chroma_entries if e["op"] == "delete"]
        meta_updates = [e for e in chroma_entries if e["op"] == "meta_update"]

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
            if collection is None:
                continue
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
            if collection is None:
                continue
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

        if row_entries:
            try:
                self._sync_duckdb_from_journal(row_entries)
            except Exception as e:
                logger.warning("duckdb.sync_failed", {"error": str(e)}, user_id="system")

        done_ids = [e["id"] for e in entries]
        with self._connect() as cur:
            placeholders = ",".join("?" * len(done_ids))
            cur.execute(f"DELETE FROM _journal WHERE id IN ({placeholders})", done_ids)

        for tbl in table_caps:
            if not self._hybrid_disabled.get(tbl):
                continue
            remaining = self._journal_count(tbl)
            if remaining <= JOURNAL_CAP:
                self._hybrid_disabled.pop(tbl, None)
                logger.info(
                    "hybrid_search_recovered",
                    {"table": tbl, "remaining": remaining},
                    user_id="system",
                )

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
                    cur.execute(f"SELECT rowid as _row, id, {col} FROM {table}")
                    sql_rows = cur.fetchall()

                sql_ids = {str(r["_row"]) for r in sql_rows}
                id_to_row = {str(r["_row"]): dict(r) for r in sql_rows}

                ghosts = chroma_ids - sql_ids
                if ghosts:
                    collection.delete(ids=list(ghosts))
                    result["ghosts_deleted"] += len(ghosts)

                missing = sql_ids - chroma_ids
                if missing:
                    with self._connect() as cur:
                        cur.execute(
                            f"SELECT *, rowid as _rowid FROM {table} WHERE rowid IN "
                            f"({','.join('?' * len(missing))})",
                            tuple(int(mid) for mid in missing),
                        )
                        full_rows = cur.fetchall()
                    full_row_by_rowid = {str(r["_rowid"]): dict(r) for r in full_rows}

                    ids_batch = []
                    embeddings_batch = []
                    docs_batch = []
                    metas_batch = []

                    for mid in missing:
                        row = id_to_row.get(mid)
                        full_row = full_row_by_rowid.get(mid)
                        if row:
                            doc = row[col] or ""
                            ids_batch.append(mid)
                            embeddings_batch.append(self._get_embedding(doc))
                            docs_batch.append(doc)

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

        self._auto_sync_graph_nodes()
        self._auto_sync_graph_edges()
        self.decay_edges()
        self.raw_query("DELETE FROM _graph_edges WHERE weight < 0.05")
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
        if self._duckdb_conn is not None:
            try:
                self._duckdb_conn.close()
            except Exception:
                pass
