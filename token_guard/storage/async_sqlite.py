"""
storage/async_sqlite.py
-----------------------
SQLite-backed async storage backend using aiosqlite.
"""

from __future__ import annotations
import asyncio
from token_guard.storage.async_base import AsyncBaseStorage
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


class AsyncSQLiteStorage(AsyncBaseStorage):
    """
    SQLite-backed async token usage storage.

    Uses aiosqlite for non-blocking I/O. Connections are established lazily
    on the first query to allow synchronous constructor calls.
    """

    def __init__(self, path: str = "token_guard.db") -> None:
        self._path = path
        self._conn = None
        self._lock = asyncio.Lock()

    async def _get_conn(self):
        async with self._lock:
            if self._conn is None:
                try:
                    import aiosqlite
                except ImportError as exc:
                    raise ImportError(
                        "Install aiosqlite to use AsyncSQLiteStorage:\n"
                        "  pip install aiosqlite\n"
                        "  or: pip install llm-token-guard[sqlite-async]"
                    ) from exc
                self._conn = await aiosqlite.connect(self._path)
                await self._conn.execute("PRAGMA journal_mode=WAL;")
                await self._conn.execute(_CREATE_TABLE)
                await self._conn.commit()
            return self._conn

    async def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        conn = await self._get_conn()
        async with self._lock:
            await conn.execute(_UPSERT, (user_id, input_tokens, output_tokens))
            await conn.commit()

    async def get_usage(self, user_id: str) -> UserUsage:
        conn = await self._get_conn()
        async with self._lock:
            async with conn.execute(
                "SELECT input_tokens, output_tokens FROM token_usage WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return UserUsage()
        return UserUsage(input_tokens=row[0], output_tokens=row[1])

    async def reset_usage(self, user_id: str) -> None:
        conn = await self._get_conn()
        async with self._lock:
            await conn.execute(
                "DELETE FROM token_usage WHERE user_id = ?", (user_id,)
            )
            await conn.commit()

    async def all_users(self) -> dict[str, UserUsage]:
        conn = await self._get_conn()
        async with self._lock:
            async with conn.execute(
                "SELECT user_id, input_tokens, output_tokens FROM token_usage"
            ) as cursor:
                rows = await cursor.fetchall()
        return {
            row[0]: UserUsage(input_tokens=row[1], output_tokens=row[2])
            for row in rows
        }

    async def close(self) -> None:
        """Explicitly close the database connection."""
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    async def __aenter__(self) -> AsyncSQLiteStorage:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def __del__(self) -> None:
        # Best effort synchronous cleanup if event loop is running or already closed
        if self._conn is not None:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self._conn.close())
            except Exception:
                pass
