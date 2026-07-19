"""
storage/async_redis.py
----------------------
Async Redis storage backend using redis.asyncio.
"""

from __future__ import annotations
import logging
from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.models import UserUsage

logger = logging.getLogger(__name__)


class AsyncRedisStorage(AsyncBaseStorage):
    """
    Async Redis-backed token usage storage for production deployments.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        ssl: bool = False,
        key_prefix: str = "token_guard",
        ttl: int | None = None,
        max_connections: int = 10,
        client=None,
    ) -> None:
        self._prefix = key_prefix
        self._ttl = ttl

        if client is not None:
            self._r = client
        else:
            self._r = self._make_client(
                host=host,
                port=port,
                db=db,
                password=password,
                ssl=ssl,
                max_connections=max_connections,
            )

    @classmethod
    def from_url(
        cls,
        url: str,
        key_prefix: str = "token_guard",
        ttl: int | None = None,
        max_connections: int = 10,
    ) -> AsyncRedisStorage:
        """
        Create AsyncRedisStorage from a Redis URL.
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError(
                "Install redis to use AsyncRedisStorage:\n"
                "  pip install redis\n"
                "  or: pip install llm-token-guard[redis]"
            ) from exc

        client = aioredis.Redis.from_url(
            url,
            max_connections=max_connections,
            decode_responses=True,
        )
        instance = cls.__new__(cls)
        instance._prefix = key_prefix
        instance._ttl = ttl
        instance._r = client
        return instance

    @staticmethod
    def _make_client(
        host: str,
        port: int,
        db: int,
        password: str | None,
        ssl: bool,
        max_connections: int,
    ):
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError(
                "Install redis to use AsyncRedisStorage:\n"
                "  pip install redis\n"
                "  or: pip install llm-token-guard[redis]"
            ) from exc

        return aioredis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            max_connections=max_connections,
            decode_responses=True,
        )

    def _key(self, user_id: str) -> str:
        """Build the Redis hash key for a user."""
        return f"{self._prefix}:{user_id}"

    async def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """
        Increment token counters.
        """
        key = self._key(user_id)
        async with self._r.pipeline(transaction=True) as pipe:
            pipe.hincrby(key, "input_tokens", input_tokens)
            pipe.hincrby(key, "output_tokens", output_tokens)
            if self._ttl is not None:
                pipe.expire(key, self._ttl)
            await pipe.execute()

    async def get_usage(self, user_id: str) -> UserUsage:
        """Return cumulative usage for a user (zeros if not found)."""
        data = await self._r.hgetall(self._key(user_id))
        if not data:
            return UserUsage()

        def val_int(field_name: str) -> int:
            val = data.get(field_name) or data.get(field_name.encode("utf-8")) or 0
            return int(val)

        return UserUsage(
            input_tokens=val_int("input_tokens"),
            output_tokens=val_int("output_tokens"),
        )

    async def reset_usage(self, user_id: str) -> None:
        """Delete the user's key from Redis."""
        await self._r.delete(self._key(user_id))

    async def all_users(self) -> dict[str, UserUsage]:
        """
        Return usage for all tracked users.
        """
        pattern = f"{self._prefix}:*"
        prefix_len = len(self._prefix) + 1
        result: dict[str, UserUsage] = {}
        cursor = 0
        while True:
            cursor, keys = await self._r.scan(cursor, match=pattern, count=100)
            for key in keys:
                if isinstance(key, bytes):
                    key_str = key.decode("utf-8")
                else:
                    key_str = key
                data = await self._r.hgetall(key)
                user_id = key_str[prefix_len:]

                def val_int(field_name: str) -> int:
                    val = data.get(field_name) or data.get(field_name.encode("utf-8")) or 0
                    return int(val)

                result[user_id] = UserUsage(
                    input_tokens=val_int("input_tokens"),
                    output_tokens=val_int("output_tokens"),
                )
            if cursor == 0:
                break
        return result

    async def ping(self) -> bool:
        """
        Check if Redis is reachable.
        """
        try:
            return await self._r.ping()
        except Exception as exc:
            logger.warning("AsyncRedisStorage ping failed: %s", exc)
            return False
