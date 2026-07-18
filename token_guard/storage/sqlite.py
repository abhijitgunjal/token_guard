"""
storage/sqlite.py
-----------------
SQLite-backed storage backend.

- Zero extra dependencies (sqlite3 is in Python stdlib)
- Persistent across restarts
- Good for single-server / single-process apps
- Uses WAL mode + UPSERT for safe concurrent writes

Usage::

    from token_guard.storage.sqlite import SQLiteStorage
    from token_guard import TokenGuard

    # File-based (persists across restarts)
    store = SQLiteStorage(path="token_usage.db")
    guard = TokenGuard(max_tokens=10_000, storage=store)

    # In-memory SQLite (useful for testing)
    store = SQLiteStorage(path=":memory:")
"""

from __future__ import annotations
import sqlite3
import threading
from token_guard.storage.base import BaseStorage
from token_guard.storage.models import UserUsage


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS token_usage (
    user_id       TEXT    PRIMARY KEY,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
"""

_UPSERT = """
INSERT INTO token_usage (user_id, input_tokens, output_tokens)
    VALUES (?, ?, ?)
ON CONFLICT(user_id) DO UPDATE SET
    input_tokens  = input_tokens  + excluded.input_tokens,
    output_tokens = output_tokens + excluded.output_tokens;
"""


class SQLiteStorage(BaseStorage):
    """
    SQLite-backed token usage storage.

    Thread-safe: uses a threading.Lock and per-thread connections
    (check_same_thread=False + explicit locking).

    Args:
        path: Path to the SQLite database file.
              Use ``":memory:"`` for an in-process, non-persistent store
              (useful for testing without touching disk).
    """

    def __init__(self, path: str = "token_guard.db") -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")  # better concurrency
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        with self._lock:
            self._conn.execute(_UPSERT, (user_id, input_tokens, output_tokens))
            self._conn.commit()

    def get_usage(self, user_id: str) -> UserUsage:
        with self._lock:
            row = self._conn.execute(
                "SELECT input_tokens, output_tokens FROM token_usage WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return UserUsage()
        return UserUsage(input_tokens=row[0], output_tokens=row[1])

    def reset_usage(self, user_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM token_usage WHERE user_id = ?", (user_id,)
            )
            self._conn.commit()

    def all_users(self) -> dict[str, UserUsage]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT user_id, input_tokens, output_tokens FROM token_usage"
            ).fetchall()
        return {
            row[0]: UserUsage(input_tokens=row[1], output_tokens=row[2])
            for row in rows
        }

    def close(self) -> None:
        """Explicitly close the database connection."""
        self._conn.close()

    def __enter__(self) -> "SQLiteStorage":
        """Support use as a context manager: ``with SQLiteStorage(...) as store:``."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
