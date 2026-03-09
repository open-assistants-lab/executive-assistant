"""App storage using SQLite + FTS5 + ChromaDB."""

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Cache directory in user's home
MODEL_CACHE_DIR = Path(os.path.expanduser("~")) / ".cache" / "sentence-transformers"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_embedding_model = None


def _get_embedding_model():
    """Get or create sentence-transformers model (singleton)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL,
                cache_folder=str(MODEL_CACHE_DIR),
            )
        except Exception:
            _embedding_model = None
    return _embedding_model


def get_embedding(text: str) -> list[float]:
    """Get embedding for text using sentence-transformers.

    Falls back to simple hash if model not available.
    """
    if not text:
        return [0.0] * EMBEDDING_DIM

    model = _get_embedding_model()
    if model is not None:
        try:
            embedding = model.encode(str(text), show_progress_bar=False)
            return embedding.tolist()
        except Exception:
            pass

    # Fallback to simple hash
    return _simple_embedding(text)


def _simple_embedding(text: str) -> list[float]:
    """Simple embedding using word hashing (fallback).

    This creates a sparse vector based on word hashes - not true semantic
    embedding but works as fallback.
    """
    if not text:
        return [0.0] * EMBEDDING_DIM

    words = str(text).lower().split()
    dim = EMBEDDING_DIM
    embedding = [0.0] * dim
    for word in words:
        hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
        embedding[hash_val] += 1.0
    mag = sum(x**2 for x in embedding) ** 0.5
    if mag > 0:
        embedding = [x / mag for x in embedding]
    return embedding


@dataclass
class TableSchema:
    """Schema definition for a table within an app."""

    name: str
    columns: dict[str, str]  # column_name -> type (TEXT, INTEGER, REAL, BOOLEAN)
    text_columns: list[str] = field(default_factory=list)  # columns with FTS5
    chroma_columns: list[str] = field(default_factory=list)  # columns with ChromaDB (semantic)


@dataclass
class AppSchema:
    """Schema definition for an app (can have multiple tables)."""

    name: str
    tables: dict[str, TableSchema]  # table_name -> TableSchema


class ChromaManager:
    """Manages ChromaDB collections for apps.

    Structure:
        data/users/{user_id}/apps/{app_name}/.chromadb/{table_name}_{column}/
    """

    def __init__(self, user_id: str, apps_path: Path):
        self.user_id = user_id
        self.apps_path = apps_path
        self._clients: dict[str, chromadb.PersistentClient] = {}
        self._embedding_function = None

    def _get_client(self, app_name: str) -> chromadb.PersistentClient:
        """Get or create ChromaDB client for an app."""
        if app_name not in self._clients:
            safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in app_name.lower())
            app_chroma_path = self.apps_path / safe_name / ".chromadb"
            app_chroma_path.mkdir(parents=True, exist_ok=True)
            self._clients[app_name] = chromadb.PersistentClient(
                path=str(app_chroma_path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._clients[app_name]

    def get_or_create_collection(self, app_name: str, table_name: str, column_name: str):
        """Get or create a ChromaDB collection for a column."""
        client = self._get_client(app_name)
        # Collection name format: {table}_{column} to match FTS5 naming
        collection_name = f"{table_name}_{column_name}"
        return client.get_or_create_collection(
            name=collection_name,
            metadata={
                "app": app_name,
                "table": table_name,
                "column": column_name,
            },
        )

    def delete_collection(self, app_name: str, table_name: str, column_name: str):
        """Delete a ChromaDB collection."""
        try:
            client = self._get_client(app_name)
            collection_name = f"{table_name}_{column_name}"
            client.delete_collection(name=collection_name)
        except Exception:
            pass

    def add(
        self,
        app_name: str,
        table_name: str,
        column_name: str,
        ids: list,
        documents: list[dict],
        embeddings: list[list[float]] | None = None,
    ):
        """Add documents to a collection.

        If embeddings not provided, generates embeddings using sentence-transformers.
        """
        collection = self.get_or_create_collection(app_name, table_name, column_name)

        # Auto-generate embeddings if not provided
        if embeddings is None:
            embeddings = []
            for doc in documents:
                # Get the text value from the document dict
                text = doc.get(column_name, "") if isinstance(doc, dict) else str(doc)
                embeddings.append(get_embedding(text))

        collection.add(
            ids=ids,
            documents=[
                doc.get(column_name, "") if isinstance(doc, dict) else str(doc) for doc in documents
            ],
            embeddings=embeddings,
        )

    def delete(self, app_name: str, table_name: str, column_name: str, ids: list):
        """Delete documents from a collection."""
        try:
            collection = self.get_or_create_collection(app_name, table_name, column_name)
            collection.delete(ids=ids)
        except Exception:
            pass

    def query(
        self,
        app_name: str,
        table_name: str,
        column_name: str,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """Query a collection."""
        try:
            collection = self.get_or_create_collection(app_name, table_name, column_name)
            return collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
            )
        except Exception:
            return {"ids": [], "documents": [], "distances": []}

    def get_all_collections(self, app_name: str) -> list[str]:
        """Get all collection names for an app."""
        try:
            client = self._get_client(app_name)
            return [c.name for c in client.list_collections()]
        except Exception:
            return []


class AppStorage:
    """Manages app storage with SQLite + FTS5 + ChromaDB.

    Structure:
        data/users/{user_id}/apps/
        ├── library/
        │   ├── data.db              # SQLite + FTS5
        │   ├── data.db-wal
        │   ├── data.db-shm
        │   └── .chromadb/           # ChromaDB for semantic search
        │       └── books_title      # Collection for title column
        │       └── books_author     # Collection for author column
        └── todo/
            └── data.db
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/apps")
        base_path.mkdir(parents=True, exist_ok=True)
        self.base_path = base_path
        self.chroma = ChromaManager(user_id, base_path)

    def _get_app_path(self, app_name: str) -> Path:
        """Get path to app directory."""
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in app_name.lower())
        app_path = self.base_path / safe_name
        app_path.mkdir(parents=True, exist_ok=True)
        return app_path

    def _get_db_path(self, app_name: str) -> Path:
        """Get path to app SQLite database."""
        return (self._get_app_path(app_name) / "data.db").resolve()

    def _get_conn(self, app_name: str) -> sqlite3.Connection:
        """Get connection to app database."""
        db_path = self._get_db_path(app_name)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _detect_text_columns(self, schema: dict[str, str]) -> list[str]:
        """Detect which columns are TEXT type."""
        return [col for col, col_type in schema.items() if col_type.upper() == "TEXT"]

    def create_app(self, name: str, tables: dict[str, dict[str, str]]) -> AppSchema:
        """Create a new app with multiple tables.

        Args:
            name: App name
            tables: Dict of {table_name: {column: type}}

        Returns:
            AppSchema with all tables
        """
        db_path = self._get_db_path(name)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")

        table_schemas: dict[str, TableSchema] = {}

        for table_name, schema in tables.items():
            text_columns = self._detect_text_columns(schema)

            # Determine which columns get ChromaDB (semantic search)
            # Only skip very long columns like full_text, content, body
            long_text_patterns = ["full_text", "content", "body"]
            chroma_columns = []
            for col in text_columns:
                is_long = any(pattern in col.lower() for pattern in long_text_patterns)
                if not is_long:
                    chroma_columns.append(col)

            # Create main table
            columns_def = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "created_at INTEGER NOT NULL"]
            for col, col_type in schema.items():
                if col_type.upper() == "TEXT":
                    columns_def.append(f"{col} TEXT")
                elif col_type.upper() == "INTEGER":
                    columns_def.append(f"{col} INTEGER")
                elif col_type.upper() == "REAL":
                    columns_def.append(f"{col} REAL")
                elif col_type.upper() == "BOOLEAN":
                    columns_def.append(f"{col} INTEGER")
                else:
                    columns_def.append(f"{col} TEXT")

            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_def)})")

            # Create FTS5 virtual table for each text column
            for col in text_columns:
                fts_table = f"{table_name}_fts_{col}"
                conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table} USING fts5(
                        {col},
                        content='{table_name}',
                        content_rowid='id'
                    )
                """)
                # Triggers for FTS5 sync
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table_name}_ai_{col} AFTER INSERT ON {table_name} BEGIN
                        INSERT INTO {fts_table}(rowid, {col}) VALUES (new.id, new.{col});
                    END
                """)

            # Create ChromaDB collections for semantic search
            for col in chroma_columns:
                try:
                    self.chroma.get_or_create_collection(name, table_name, col)
                except Exception:
                    pass  # ChromaDB might not be available

            table_schemas[table_name] = TableSchema(
                name=table_name,
                columns=schema,
                text_columns=text_columns,
                chroma_columns=chroma_columns,
            )

        # Save schema metadata
        schema_json = json.dumps(
            {
                "name": name,
                "tables": {
                    tname: {
                        "name": ts.name,
                        "columns": ts.columns,
                        "text_columns": ts.text_columns,
                        "chroma_columns": ts.chroma_columns,
                    }
                    for tname, ts in table_schemas.items()
                },
            }
        )
        conn.execute("CREATE TABLE IF NOT EXISTS _app_meta (schema JSON)")
        conn.execute("DELETE FROM _app_meta")
        conn.execute("INSERT INTO _app_meta (schema) VALUES (?)", (schema_json,))

        conn.commit()
        conn.close()

        return AppSchema(name=name, tables=table_schemas)

    def list_apps(self) -> list[str]:
        """List all apps for the user."""
        apps = []
        for db_file in self.base_path.glob("*.db"):
            if not db_file.name.startswith("."):
                apps.append(db_file.stem)
        return apps

    def get_schema(self, app_name: str) -> AppSchema | None:
        """Get schema for an app."""
        conn = self._get_conn(app_name)
        try:
            cursor = conn.execute("SELECT schema FROM _app_meta")
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                tables = {}
                for tname, tdata in data.get("tables", {}).items():
                    tables[tname] = TableSchema(
                        name=tdata["name"],
                        columns=tdata["columns"],
                        text_columns=tdata.get("text_columns", []),
                        chroma_columns=tdata.get("chroma_columns", []),
                    )
                return AppSchema(name=data["name"], tables=tables)
        except Exception:
            pass
        finally:
            conn.close()
        return None

    def delete_app(self, app_name: str) -> bool:
        """Delete an app and its ChromaDB collections."""
        db_path = self._get_db_path(app_name)
        if db_path.exists():
            db_path.unlink()
            # Clean up ChromaDB
            try:
                chroma_path = self.base_path / ".chromadb" / app_name
                if chroma_path.exists():
                    import shutil

                    shutil.rmtree(chroma_path)
            except Exception:
                pass
            return True
        return False

    def insert(self, app_name: str, table: str, data: dict[str, Any]) -> int:
        """Insert a row into a table, syncing to FTS5 and ChromaDB."""
        conn = self._get_conn(app_name)
        schema = self.get_schema(app_name)
        if not schema or table not in schema.tables:
            raise ValueError(f"Table '{table}' not found in app '{app_name}'")

        table_schema = schema.tables[table]
        now = int(datetime.now().timestamp() * 1000)

        filtered_data = {k: v for k, v in data.items() if k in table_schema.columns}

        columns = list(filtered_data.keys())
        placeholders = ["?"] * len(columns)
        values = list(filtered_data.values())

        query = f"INSERT INTO {table} (created_at, {', '.join(columns)}) VALUES (?, {', '.join(placeholders)})"
        cursor = conn.execute(query, [now] + values)
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Sync to ChromaDB for semantic columns
        for col in table_schema.chroma_columns:
            if col in filtered_data and filtered_data[col]:
                try:
                    self.chroma.add(
                        app_name=app_name,
                        table_name=table,
                        column_name=col,
                        ids=[str(row_id)],
                        documents=[{col: str(filtered_data[col])}],
                    )
                except Exception:
                    pass

        return row_id if row_id is not None else 0

    def update(self, app_name: str, table: str, row_id: int, data: dict[str, Any]) -> bool:
        """Update a row by ID, syncing to FTS5 and ChromaDB."""
        conn = self._get_conn(app_name)
        schema = self.get_schema(app_name)
        if not schema or table not in schema.tables:
            raise ValueError(f"Table '{table}' not found in app '{app_name}'")

        table_schema = schema.tables[table]
        filtered_data = {k: v for k, v in data.items() if k in table_schema.columns}

        if not filtered_data:
            return False

        # Get old data for ChromaDB sync
        old_cursor = conn.execute(f"SELECT * FROM {table} WHERE id = ?", [row_id])
        old_row = old_cursor.fetchone()
        old_data = dict(old_row) if old_row else {}

        set_clause = ", ".join([f"{k} = ?" for k in filtered_data.keys()])
        values = list(filtered_data.values()) + [row_id]

        cursor = conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()

        # Sync to ChromaDB - delete old, add new
        for col in table_schema.chroma_columns:
            if col in filtered_data or col in old_data:
                try:
                    # Delete old
                    self.chroma.delete(
                        app_name=app_name,
                        table_name=table,
                        column_name=col,
                        ids=[str(row_id)],
                    )
                    # Add new if present
                    if col in filtered_data and filtered_data[col]:
                        self.chroma.add(
                            app_name=app_name,
                            table_name=table,
                            column_name=col,
                            ids=[str(row_id)],
                            documents=[{col: str(filtered_data[col])}],
                        )
                except Exception:
                    pass

        return cursor.rowcount > 0

    def delete(self, app_name: str, table: str, row_id: int) -> bool:
        """Delete a row by ID, syncing to ChromaDB."""
        # Get schema for ChromaDB columns
        schema = self.get_schema(app_name)
        table_schema = schema.tables[table] if schema and table in schema.tables else None
        chroma_columns = table_schema.chroma_columns if table_schema else []

        conn = self._get_conn(app_name)
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", [row_id])
        conn.commit()
        conn.close()

        # Delete from ChromaDB
        for col in chroma_columns:
            try:
                self.chroma.delete(
                    app_name=app_name,
                    table_name=table,
                    column_name=col,
                    ids=[str(row_id)],
                )
            except Exception:
                pass

        return cursor.rowcount > 0

    def query_sql(
        self, app_name: str, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SQL query on an app."""
        conn = self._get_conn(app_name)
        if params:
            cursor = conn.execute(sql, params)
        else:
            cursor = conn.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def search_fts(
        self, app_name: str, table: str, column: str, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search using FTS5."""
        conn = self._get_conn(app_name)
        fts_table = f"{table}_fts_{column}"

        try:
            cursor = conn.execute(
                f"""
                SELECT {table}.* FROM {table}
                JOIN {fts_table} ON {table}.id = {fts_table}.rowid
                WHERE {fts_table} MATCH ?
                LIMIT ?
            """,
                [query, limit],
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            conn.close()
            return []

    def search_semantic(
        self,
        app_name: str,
        table: str,
        column: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search using ChromaDB semantic search.

        Uses sentence-transformers embeddings for semantic search.
        Returns matching rows from the table.
        """
        try:
            # Generate embedding for query
            query_embedding = get_embedding(query)

            # Query ChromaDB
            collection = self.chroma.get_or_create_collection(app_name, table, column)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
            )

            if not results or not results.get("ids") or not results["ids"][0]:
                return []

            # Get matching IDs and fetch from SQLite
            ids = results["ids"][0]
            conn = self._get_conn(app_name)
            placeholders = ",".join(["?"] * len(ids))
            cursor = conn.execute(f"SELECT * FROM {table} WHERE id IN ({placeholders})", ids)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception:
            return []

    def search_hybrid(
        self,
        app_name: str,
        table: str,
        column: str,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining keyword (FTS5) + semantic (ChromaDB).

        Args:
            app_name: Name of the app
            table: Table to search
            column: Column to search in (must be TEXT with search enabled)
            query: Search query
            limit: Max results to return
            fts_weight: Weight for FTS5 (0-1), semantic gets (1 - fts_weight)

        Returns:
            Combined results ranked by keyword + semantic similarity
        """
        try:
            # Generate embedding for semantic search
            query_embedding = get_embedding(query)

            # Get FTS5 results
            fts_results = self.search_fts(app_name, table, column, query, limit=limit * 2)
            fts_scores: dict[int, float] = {}
            for i, row in enumerate(fts_results):
                fts_scores[row["id"]] = 1.0 / (i + 1)  # Rank-based score

            # Get semantic results
            semantic_results = self.search_semantic(app_name, table, column, query, limit=limit * 2)
            semantic_scores: dict[int, float] = {}
            for i, row in enumerate(semantic_results):
                semantic_scores[row["id"]] = 1.0 / (i + 1)  # Rank-based score

            # Combine scores
            all_ids = set(fts_scores.keys()) | set(semantic_scores.keys())
            combined = []
            for row_id in all_ids:
                fts_score = fts_scores.get(row_id, 0)
                semantic_score = semantic_scores.get(row_id, 0)
                combined_score = fts_weight * fts_score + (1 - fts_weight) * semantic_score

                # Find the row data
                row_data = None
                for r in fts_results:
                    if r["id"] == row_id:
                        row_data = r
                        break
                if not row_data:
                    for r in semantic_results:
                        if r["id"] == row_id:
                            row_data = r
                            break

                if row_data:
                    combined.append((combined_score, row_data))

            # Sort by combined score
            combined.sort(key=lambda x: x[0], reverse=True)
            return [row for _, row in combined[:limit]]
        except Exception:
            return []

    def column_add(
        self, app_name: str, table: str, column: str, col_type: str, enable_search: bool = True
    ) -> bool:
        """Add a column to a table."""
        conn = self._get_conn(app_name)
        schema = self.get_schema(app_name)
        if not schema or table not in schema.tables:
            return False

        if col_type.upper() == "TEXT":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        elif col_type.upper() == "INTEGER":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER")
        elif col_type.upper() == "REAL":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} REAL")
        elif col_type.upper() == "BOOLEAN":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER")
        else:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")

        # Add FTS5 if enabled
        if enable_search and col_type.upper() == "TEXT":
            fts_table = f"{table}_fts_{column}"
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table} USING fts5(
                    {column},
                    content='{table}',
                    content_rowid='id'
                )
            """)

            # Add ChromaDB collection for semantic search
            if enable_search:
                try:
                    self.chroma.get_or_create_collection(app_name, table, column)
                except Exception:
                    pass

        conn.commit()
        conn.close()
        return True

    def column_delete(self, app_name: str, table: str, column: str) -> bool:
        """Delete a column from a table."""
        # Get schema first
        schema = self.get_schema(app_name)
        if not schema or table not in schema.tables or column not in schema.tables[table].columns:
            return False

        conn = self._get_conn(app_name)

        # Get all data
        cursor = conn.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        new_columns = [c for c in columns if c != column and c != "id" and c != "created_at"]

        # Create new table
        conn.execute(f"CREATE TABLE {table}_new (id INTEGER PRIMARY KEY, created_at INTEGER)")
        table_schema = schema.tables[table]
        for col in new_columns:
            col_type = table_schema.columns.get(col, "TEXT")
            if col_type.upper() == "INTEGER":
                conn.execute(f"ALTER TABLE {table}_new ADD COLUMN {col} INTEGER")
            elif col_type.upper() == "REAL":
                conn.execute(f"ALTER TABLE {table}_new ADD COLUMN {col} REAL")
            else:
                conn.execute(f"ALTER TABLE {table}_new ADD COLUMN {col} TEXT")

        # Copy data
        for row in rows:
            row_dict = dict(zip(columns, row))
            new_row = {"created_at": row_dict["created_at"]}
            for col in new_columns:
                new_row[col] = row_dict.get(col)
            placeholders = ", ".join(new_row.keys())
            values = list(new_row.values())
            conn.execute(
                f"INSERT INTO {table}_new ({placeholders}) VALUES ({','.join(['?'] * len(values))})",
                values,
            )

        # Drop old table and rename
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")

        # Drop FTS table
        try:
            conn.execute(f"DROP TABLE {table}_fts_{column}")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

        # Delete ChromaDB collection
        try:
            self.chroma.delete_collection(app_name, table, column)
        except Exception:
            pass

        return True

    def column_rename(self, app_name: str, table: str, old_name: str, new_name: str) -> bool:
        """Rename a column in a table."""
        conn = self._get_conn(app_name)

        try:
            conn.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
        except sqlite3.OperationalError:
            conn.close()
            return False

        # Rename FTS table
        try:
            conn.execute(f"ALTER TABLE {table}_fts_{old_name} RENAME TO {table}_fts_{new_name}")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

        # Note: ChromaDB collections can't be renamed, need to recreate
        # For now, leave the old collection and note this limitation

        return True
