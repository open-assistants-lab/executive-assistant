"""App storage using HybridDB.

Domain wrapper that adds:
- App-level metadata (_app_meta)
- Multi-table app management
- ChromaDB manager for per-app collection routing
"""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.sdk.hybrid_db import HybridDB, SearchMode, _hash_embedding
from src.storage.paths import get_paths

MODEL_CACHE_DIR = Path(os.path.expanduser("~")) / ".cache" / "sentence-transformers"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL,
                cache_folder=str(MODEL_CACHE_DIR),
            )
        except Exception:
            _embedding_model = None
    return _embedding_model


def get_embedding(text: str) -> list[float]:
    if not text:
        return [0.0] * EMBEDDING_DIM
    model = _get_embedding_model()
    if model is not None:
        try:
            embedding = model.encode(str(text), show_progress_bar=False)
            return embedding.tolist()
        except Exception:
            pass
    return _hash_embedding(text)


@dataclass
class TableSchema:
    name: str
    columns: dict[str, str]
    text_columns: list[str] = field(default_factory=list)
    chroma_columns: list[str] = field(default_factory=list)


@dataclass
class AppSchema:
    name: str
    tables: dict[str, TableSchema]


class AppStorage:
    """Manages app storage via HybridDB.

    Structure:
        data/private/apps/
        ├── library/
        │   ├── app.db     # SQLite + FTS5 + journal (HybridDB)
        │   └── vectors/   # ChromaDB for semantic search
        └── todo/
            └── app.db
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = get_paths(user_id).apps_dir()
        base_path.mkdir(parents=True, exist_ok=True)
        self.base_path = base_path
        self._dbs: dict[str, HybridDB] = {}

    def _get_app_path(self, app_name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in app_name.lower())
        app_path = self.base_path / safe_name
        app_path.mkdir(parents=True, exist_ok=True)
        return app_path

    def _get_db(self, app_name: str) -> HybridDB:
        if app_name not in self._dbs:
            app_path = self._get_app_path(app_name)
            self._dbs[app_name] = HybridDB(
                str(app_path),
                embedding_model_name="all-MiniLM-L6-v2",
            )
        return self._dbs[app_name]

    def _detect_text_columns(self, schema: dict[str, str]) -> list[str]:
        return [col for col, col_type in schema.items() if col_type.upper() in ("TEXT", "LONGTEXT")]

    def create_app(self, name: str, tables: dict[str, dict[str, str]]) -> AppSchema:
        db = self._get_db(name)
        table_schemas: dict[str, TableSchema] = {}

        for table_name, schema in tables.items():
            db.create_table(table_name, schema)

            text_columns = self._detect_text_columns(schema)
            chroma_columns = [
                col for col in text_columns if schema.get(col, "").upper() == "LONGTEXT"
            ]

            table_schemas[table_name] = TableSchema(
                name=table_name,
                columns=schema,
                text_columns=text_columns,
                chroma_columns=chroma_columns,
            )

        return AppSchema(name=name, tables=table_schemas)

    def list_apps(self) -> list[str]:
        apps = []
        for db_file in self.base_path.glob("*/app.db"):
            apps.append(db_file.parent.name)
        return apps

    def get_schema(self, app_name: str) -> AppSchema | None:
        db = self._get_db(app_name)
        tables = db.list_tables()
        if not tables:
            return None
        table_schemas = {}
        for tname in tables:
            cols = db.get_schema(tname)
            text_cols = [c for c, ct in cols.items() if ct in ("TEXT", "LONGTEXT")]
            chroma_cols = [c for c, ct in cols.items() if ct == "LONGTEXT"]
            table_schemas[tname] = TableSchema(
                name=tname,
                columns=cols,
                text_columns=text_cols,
                chroma_columns=chroma_cols,
            )
        return AppSchema(name=app_name, tables=table_schemas)

    def delete_app(self, app_name: str) -> bool:
        app_path = self._get_app_path(app_name)
        if app_path.exists():
            shutil.rmtree(app_path)
            self._dbs.pop(app_name, None)
            return True
        return False

    def insert(self, app_name: str, table: str, data: dict[str, Any]) -> int:
        db = self._get_db(app_name)
        schema = db.get_schema(table)
        if not schema:
            raise ValueError(f"Table '{table}' not found in app '{app_name}'")
        filtered = {k: v for k, v in data.items() if k in schema}
        return db.insert(table, filtered)

    def update(self, app_name: str, table: str, row_id: int, data: dict[str, Any]) -> bool:
        db = self._get_db(app_name)
        schema = db.get_schema(table)
        if not schema:
            raise ValueError(f"Table '{table}' not found in app '{app_name}'")
        filtered = {k: v for k, v in data.items() if k in schema}
        if not filtered:
            return False
        return db.update(table, row_id, filtered)

    def delete(self, app_name: str, table: str, row_id: int) -> bool:
        db = self._get_db(app_name)
        return db.delete(table, row_id)

    def query_sql(
        self, app_name: str, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        db = self._get_db(app_name)
        if sql.strip().upper().startswith("SELECT"):
            return db.raw_query(sql, tuple(params) if params else ())
        return []

    def search_fts(
        self, app_name: str, table: str, column: str, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        db = self._get_db(app_name)
        results = db.search(table, column, query, mode=SearchMode.KEYWORD, limit=limit)
        return results

    def search_semantic(
        self,
        app_name: str,
        table: str,
        column: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        db = self._get_db(app_name)
        results = db.search(table, column, query, mode=SearchMode.SEMANTIC, limit=limit)
        return results

    def search_hybrid(
        self,
        app_name: str,
        table: str,
        column: str,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        db = self._get_db(app_name)
        results = db.search(
            table, column, query, mode=SearchMode.HYBRID, limit=limit, fts_weight=fts_weight
        )
        return results

    def column_add(
        self, app_name: str, table: str, column: str, col_type: str, enable_search: bool = True
    ) -> bool:
        db = self._get_db(app_name)
        try:
            db.add_column(table, column, col_type)
            return True
        except Exception:
            return False

    def column_delete(self, app_name: str, table: str, column: str) -> bool:
        db = self._get_db(app_name)
        try:
            db.drop_column(table, column)
            return True
        except Exception:
            return False

    def column_rename(self, app_name: str, table: str, old_name: str, new_name: str) -> bool:
        db = self._get_db(app_name)
        try:
            db.rename_column(table, old_name, new_name)
            return True
        except Exception:
            return False
