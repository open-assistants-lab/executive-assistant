"""Profile storage using SQLite + FTS5."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class Profile:
    """User profile."""

    user_id: str
    name: str | None
    role: str | None
    company: str | None
    city: str | None
    bio: str | None
    preferences: dict | None
    interests: list | None
    background: dict | None
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime


class ProfileStore:
    """Manages user profile storage.

    Structure:
        /data/users/{user_id}/profile/
        └── profile.db    # SQLite + FTS5
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/profile")
        base_path.mkdir(parents=True, exist_ok=True)

        self.db_path = str((base_path / "profile.db").resolve())
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite with FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                company TEXT,
                city TEXT,
                bio TEXT,
                preferences JSON,
                interests JSON,
                background JSON,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'extracted',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS profile_fts USING fts5(
                name, role, company, city, bio
            )
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_ai AFTER INSERT ON profile BEGIN
                INSERT INTO profile_fts(rowid, name, role, company, city, bio)
                VALUES (new.rowid, new.name, new.role, new.company, new.city, new.bio);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_ad AFTER DELETE ON profile BEGIN
                INSERT INTO profile_fts(profile_fts, rowid, name, role, company, city, bio)
                VALUES ('delete', old.rowid, old.name, old.role, old.company, old.city, old.bio);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_au AFTER UPDATE ON profile BEGIN
                INSERT INTO profile_fts(profile_fts, rowid, name, role, company, city, bio)
                VALUES ('delete', old.rowid, old.name, old.role, old.company, old.city, old.bio);
                INSERT INTO profile_fts(rowid, name, role, company, city, bio)
                VALUES (new.rowid, new.name, new.role, new.company, new.city, new.bio);
            END
        """)

        conn.commit()
        conn.close()

    def get_profile(self) -> Profile | None:
        """Get user profile."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM profile WHERE user_id = ?", (self.user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Profile(
            user_id=row["user_id"],
            name=row["name"],
            role=row["role"],
            company=row["company"],
            city=row["city"],
            bio=row["bio"],
            preferences=row["preferences"],
            interests=row["interests"],
            background=row["background"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def set_profile(
        self,
        name: str | None = None,
        role: str | None = None,
        company: str | None = None,
        city: str | None = None,
        bio: str | None = None,
        preferences: dict | None = None,
        interests: list | None = None,
        background: dict | None = None,
        source: str = "manual",
    ) -> Profile:
        """Set or update profile fields."""
        now = datetime.now(UTC).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM profile WHERE user_id = ?", (self.user_id,))
        existing = cursor.fetchone()

        if existing:
            updates = []
            params = []

            for field, value in [
                ("name", name),
                ("role", role),
                ("company", company),
                ("city", city),
                ("bio", bio),
                ("preferences", preferences),
                ("interests", interests),
                ("background", background),
            ]:
                if value is not None:
                    updates.append(f"{field} = ?")
                    params.append(value if not isinstance(value, (dict, list)) else str(value))

            updates.append("updated_at = ?")
            params.append(now)
            updates.append("source = ?")
            params.append(source)

            params.append(self.user_id)

            cursor.execute(
                f"UPDATE profile SET {', '.join(updates)} WHERE user_id = ?",
                params,
            )
        else:
            cursor.execute(
                """
                INSERT INTO profile (user_id, name, role, company, city, bio, preferences, interests, background, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.user_id,
                    name,
                    role,
                    company,
                    city,
                    bio,
                    str(preferences) if preferences else None,
                    str(interests) if interests else None,
                    str(background) if background else None,
                    source,
                    now,
                    now,
                ),
            )

        conn.commit()
        conn.close()

        return self.get_profile()

    def update_field(
        self,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "extracted",
    ) -> Profile:
        """Update a single profile field."""
        allowed_fields = {
            "name",
            "role",
            "company",
            "city",
            "bio",
            "preferences",
            "interests",
            "background",
        }

        if key not in allowed_fields:
            raise ValueError(f"Invalid field: {key}. Allowed: {allowed_fields}")

        now = datetime.now(UTC).isoformat()

        # Convert dict/list to string for JSON fields
        if key in ("preferences", "interests", "background"):
            import json

            str_value = json.dumps(value) if isinstance(value, (dict, list)) else value
        else:
            str_value = value

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM profile WHERE user_id = ?", (self.user_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                f'UPDATE profile SET "{key}" = ?, updated_at = ?, source = ?, confidence = ? WHERE user_id = ?',
                (str_value, now, source, confidence, self.user_id),
            )
        else:
            cursor.execute(
                f'INSERT INTO profile (user_id, "{key}", source, confidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                (self.user_id, str_value, source, confidence, now, now),
            )

        conn.commit()
        conn.close()

        return self.get_profile()

    def search_fts(self, query: str, limit: int = 10) -> list[Profile]:
        """Search profile using FTS5."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.* FROM profile p
            JOIN profile_fts fts ON p.rowid = fts.rowid
            WHERE profile_fts MATCH ?
            LIMIT ?
        """,
            (query, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            Profile(
                user_id=row["user_id"],
                name=row["name"],
                role=row["role"],
                company=row["company"],
                city=row["city"],
                bio=row["bio"],
                preferences=row["preferences"],
                interests=row["interests"],
                background=row["background"],
                confidence=row["confidence"],
                source=row["source"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def to_context(self) -> str:
        """Convert profile to context string for injection."""
        profile = self.get_profile()
        if not profile:
            return ""

        parts = []
        if profile.name:
            parts.append(f"Name: {profile.name}")
        if profile.role:
            parts.append(f"Role: {profile.role}")
        if profile.company:
            parts.append(f"Company: {profile.company}")
        if profile.city:
            parts.append(f"City: {profile.city}")
        if profile.bio:
            parts.append(f"Bio: {profile.bio}")
        if profile.preferences:
            parts.append(f"Preferences: {profile.preferences}")
        if profile.interests:
            parts.append(f"Interests: {profile.interests}")

        if not parts:
            return ""

        return "## User Profile\n" + "\n".join(parts)


_profile_store_cache: dict[str, ProfileStore] = {}


def get_profile_store(user_id: str) -> ProfileStore:
    """Get or create profile store."""
    if user_id not in _profile_store_cache:
        _profile_store_cache[user_id] = ProfileStore(user_id)
    return _profile_store_cache[user_id]
