"""Storage module for Executive Assistant."""

from src.storage.database import DatabaseManager, get_database, init_db
from src.storage.user_storage import UserStorage, get_user_storage

__all__ = [
    "DatabaseManager",
    "UserStorage",
    "get_database",
    "init_db",
    "get_user_storage",
]
