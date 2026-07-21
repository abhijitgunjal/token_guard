"""
storage/postgres.py
-------------------
PostgreSQL storage backends (sync and async) for TokenGuard.

Requires:
    pip install "llm-token-guard[postgres]"
  or:
    pip install psycopg[binary] asyncpg
"""

from __future__ import annotations
import asyncio
import logging
import re
import threading
from typing import Any, Dict, Optional

from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.base import BaseStorage
from token_guard.storage.models import UserUsage

logger = logging.getLogger(__name__)


def _validate_table_name(table_name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}'. "
            f"Table names must contain only alphanumeric characters and underscores."
        )


class PostgreSQLStorage(BaseStorage):
    """
    Synchronous PostgreSQL storage backend.

    Uses `psycopg` (v3) to persist per-user token usage with atomic SQL UPSERTs.
    Thread-safe via thread lock synchronization.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        table_name: str = "token_guard_usage",
        connection: Optional[Any] = None,
        auto_create: bool = True,
        **kwargs: Any,
    ) -> None:
        _validate_table_name(table_name)
        self.table_name = table_name
        self._dsn = connection_string
        self._conn = connection
        self._lock = threading.Lock()

        if self._conn is None and self._dsn is None:
            self._dsn = "postgresql://localhost:5432/token_guard"

        if auto_create:
            self._create_table_if_not_exists()

    @classmethod
    def from_url(cls, url: str, table_name: str = "token_guard_usage", **kwargs: Any) -> PostgreSQLStorage:
        """Create a PostgreSQLStorage instance from a database URL."""
        return cls(connection_string=url, table_name=table_name, **kwargs)

    def _get_connection(self) -> Any:
        if self._conn is not None:
            return self._conn

        try:
            import psycopg
        except ImportError as exc:
            raise ImportError(
                "Install psycopg to use PostgreSQLStorage:\n"
                "  pip install 'psycopg[binary]'\n"
                "  or: pip install 'llm-token-guard[postgres]'"
            ) from exc

        self._conn = psycopg.connect(self._dsn, autocommit=True)
        return self._conn

    def _create_table_if_not_exists(self) -> None:
        try:
            with self._lock:
                conn = self._get_connection()
                query = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    user_id VARCHAR(255) PRIMARY KEY,
                    input_tokens BIGINT NOT NULL DEFAULT 0,
                    output_tokens BIGINT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
                with conn.cursor() as cur:
                    cur.execute(query)
        except Exception as exc:
            logger.warning("Failed to verify/create PostgreSQL table '%s': %s", self.table_name, exc)

    def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        query = f"""
        INSERT INTO {self.table_name} (user_id, input_tokens, output_tokens, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE SET
            input_tokens = {self.table_name}.input_tokens + EXCLUDED.input_tokens,
            output_tokens = {self.table_name}.output_tokens + EXCLUDED.output_tokens,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self._lock:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query, (user_id, input_tokens, output_tokens))

    def get_usage(self, user_id: str) -> UserUsage:
        query = f"SELECT input_tokens, output_tokens FROM {self.table_name} WHERE user_id = %s;"
        with self._lock:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
                if not row:
                    return UserUsage()
                return UserUsage(input_tokens=int(row[0]), output_tokens=int(row[1]))

    def reset_usage(self, user_id: str) -> None:
        query = f"DELETE FROM {self.table_name} WHERE user_id = %s;"
        with self._lock:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))

    def all_users(self) -> dict[str, UserUsage]:
        query = f"SELECT user_id, input_tokens, output_tokens FROM {self.table_name};"
        res: dict[str, UserUsage] = {}
        with self._lock:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                for r in rows:
                    res[r[0]] = UserUsage(input_tokens=int(r[1]), output_tokens=int(r[2]))
        return res

    def ping(self) -> bool:
        try:
            with self._lock:
                conn = self._get_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    return cur.fetchone() is not None
        except Exception as exc:
            logger.warning("PostgreSQLStorage ping failed: %s", exc)
            return False


class AsyncPostgreSQLStorage(AsyncBaseStorage):
    """
    Asynchronous PostgreSQL storage backend.

    Uses `asyncpg` to persist per-user token usage with non-blocking atomic SQL UPSERTs.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        table_name: str = "token_guard_usage",
        pool: Optional[Any] = None,
        auto_create: bool = True,
        **kwargs: Any,
    ) -> None:
        _validate_table_name(table_name)
        self.table_name = table_name
        self._dsn = connection_string
        self._pool = pool
        self._auto_create = auto_create
        self._init_lock = asyncio.Lock()

        if self._pool is None and self._dsn is None:
            self._dsn = "postgresql://localhost:5432/token_guard"

    @classmethod
    def from_url(cls, url: str, table_name: str = "token_guard_usage", **kwargs: Any) -> AsyncPostgreSQLStorage:
        """Create an AsyncPostgreSQLStorage instance from a database URL."""
        return cls(connection_string=url, table_name=table_name, **kwargs)

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool

        async with self._init_lock:
            if self._pool is not None:
                return self._pool

            try:
                import asyncpg
            except ImportError as exc:
                raise ImportError(
                    "Install asyncpg to use AsyncPostgreSQLStorage:\n"
                    "  pip install asyncpg\n"
                    "  or: pip install 'llm-token-guard[postgres]'"
                ) from exc

            self._pool = await asyncpg.create_pool(dsn=self._dsn)
            if self._auto_create:
                await self._create_table_if_not_exists()
            return self._pool

    async def _create_table_if_not_exists(self) -> None:
        try:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                user_id VARCHAR(255) PRIMARY KEY,
                input_tokens BIGINT NOT NULL DEFAULT 0,
                output_tokens BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
            async with self._pool.acquire() as conn:
                await conn.execute(query)
        except Exception as exc:
            logger.warning("Failed to verify/create async PostgreSQL table '%s': %s", self.table_name, exc)

    async def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        pool = await self._get_pool()
        query = f"""
        INSERT INTO {self.table_name} (user_id, input_tokens, output_tokens, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            input_tokens = {self.table_name}.input_tokens + EXCLUDED.input_tokens,
            output_tokens = {self.table_name}.output_tokens + EXCLUDED.output_tokens,
            updated_at = NOW();
        """
        async with pool.acquire() as conn:
            await conn.execute(query, user_id, input_tokens, output_tokens)

    async def get_usage(self, user_id: str) -> UserUsage:
        pool = await self._get_pool()
        query = f"SELECT input_tokens, output_tokens FROM {self.table_name} WHERE user_id = $1;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            if not row:
                return UserUsage()
            return UserUsage(input_tokens=int(row["input_tokens"]), output_tokens=int(row["output_tokens"]))

    async def reset_usage(self, user_id: str) -> None:
        pool = await self._get_pool()
        query = f"DELETE FROM {self.table_name} WHERE user_id = $1;"
        async with pool.acquire() as conn:
            await conn.execute(query, user_id)

    async def all_users(self) -> dict[str, UserUsage]:
        pool = await self._get_pool()
        query = f"SELECT user_id, input_tokens, output_tokens FROM {self.table_name};"
        res: dict[str, UserUsage] = {}
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            for r in rows:
                res[r["user_id"]] = UserUsage(input_tokens=int(r["input_tokens"]), output_tokens=int(r["output_tokens"]))
        return res

    async def ping(self) -> bool:
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1;")
                return val == 1
        except Exception as exc:
            logger.warning("AsyncPostgreSQLStorage ping failed: %s", exc)
            return False
