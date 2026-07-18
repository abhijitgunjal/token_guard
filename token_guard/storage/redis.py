"""
storage/redis.py
----------------
Production-grade Redis storage backend.

Requires:
    pip install redis
  or
    pip install llm-token-guard[redis]

WHY REDIS FOR PRODUCTION
------------------------
- Shared across ALL workers / processes / servers
- Atomic HINCRBY — concurrent updates never corrupt data
- Optional TTL — usage auto-expires (e.g. daily/monthly budgets)
- Connection pooling — efficient under high load
- Supports Redis Cluster and Redis Sentinel

CONFIGURATION OPTIONS
---------------------
Three ways to configure, pick whichever fits your app:

1. Simple host/port (quickstart):
        RedisStorage(host="localhost", port=6379)

2. Redis URL (most common in production / 12-factor apps):
        RedisStorage.from_url("redis://localhost:6379/0")
        RedisStorage.from_url("redis://:password@redis-host:6379/0")
        RedisStorage.from_url("rediss://redis-host:6380/0")  # TLS

3. Pass your own client (when your app already has one):
        import redis
        r = redis.Redis(host="...", decode_responses=True)
        RedisStorage(client=r)

DATA LAYOUT IN REDIS
--------------------
    Key   : <key_prefix>:<user_id>
    Type  : Hash
    Fields: input_tokens, output_tokens

    Example:
        127.0.0.1:6379> HGETALL token_guard:alice
        1) "input_tokens"
        2) "142"
        3) "output_tokens"
        4) "310"
"""

from __future__ import annotations
import logging
from token_guard.storage.base import BaseStorage
from token_guard.storage.models import UserUsage

logger = logging.getLogger(__name__)


class RedisStorage(BaseStorage):
    """
    Redis-backed token usage storage for production deployments.

    Args:
        host:         Redis host (default: ``"localhost"``).
        port:         Redis port (default: ``6379``).
        db:           Redis database index (default: ``0``).
        password:     Redis AUTH password (optional).
        ssl:          Use TLS/SSL connection (default: ``False``).
        key_prefix:   Namespace prefix for all Redis keys
                      (default: ``"token_guard"``).
                      Change this if multiple apps share one Redis.
        ttl:          Optional TTL in **seconds** for each user key.
                      ``None`` = keys never expire.
                      Examples:
                        ttl=86400    → reset usage every 24 hours
                        ttl=2592000  → reset usage every 30 days
        max_connections: Size of the connection pool (default: 10).
        client:       Pass an existing ``redis.Redis`` instance directly.
                      When provided, all other connection args are ignored.

    Examples::

        # Quickstart
        store = RedisStorage(host="localhost")

        # With password + TTL (daily budget reset)
        store = RedisStorage(
            host="redis.myapp.com",
            password="secret",
            ttl=86400,
            key_prefix="myapp:tokens",
        )

        # From URL
        store = RedisStorage.from_url("redis://:secret@redis.myapp.com:6379/0")

        # Pass existing client
        import redis
        r = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
        store = RedisStorage(client=r)
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

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_url(
        cls,
        url: str,
        key_prefix: str = "token_guard",
        ttl: int | None = None,
        max_connections: int = 10,
    ) -> "RedisStorage":
        """
        Create RedisStorage from a Redis URL.

        Args:
            url:            Redis connection URL.
                            Formats:
                              ``redis://host:port/db``
                              ``redis://:password@host:port/db``
                              ``rediss://host:port/db``  (TLS)
            key_prefix:     Namespace prefix for all keys.
            ttl:            Optional TTL in seconds.
            max_connections: Connection pool size.

        Example::

            store = RedisStorage.from_url(
                "redis://:mypassword@redis.myapp.com:6379/0",
                key_prefix="myapp:tokens",
                ttl=86400,
            )
        """
        try:
            import redis
        except ImportError as exc:
            raise ImportError(
                "Install redis to use RedisStorage:\n"
                "  pip install redis\n"
                "  or: pip install llm-token-guard[redis]"
            ) from exc

        pool = redis.ConnectionPool.from_url(
            url,
            max_connections=max_connections,
            decode_responses=True,
        )
        client = redis.Redis(connection_pool=pool)
        instance = cls.__new__(cls)
        instance._prefix = key_prefix
        instance._ttl = ttl
        instance._r = client
        return instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
            import redis
        except ImportError as exc:
            raise ImportError(
                "Install redis to use RedisStorage:\n"
                "  pip install redis\n"
                "  or: pip install llm-token-guard[redis]"
            ) from exc

        pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            max_connections=max_connections,
            decode_responses=True,
        )
        return redis.Redis(connection_pool=pool)

    def _key(self, user_id: str) -> str:
        """Build the Redis hash key for a user."""
        return f"{self._prefix}:{user_id}"

    # ------------------------------------------------------------------
    # BaseStorage interface
    # ------------------------------------------------------------------

    def add_usage(
        self, user_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """
        Atomically increment token counters using HINCRBY.
        Safe for concurrent writers — no race conditions.
        """
        key = self._key(user_id)
        pipe = self._r.pipeline()
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        if self._ttl is not None:
            pipe.expire(key, self._ttl)
        pipe.execute()

    def get_usage(self, user_id: str) -> UserUsage:
        """Return cumulative usage for a user (zeros if not found)."""
        data = self._r.hgetall(self._key(user_id))
        if not data:
            return UserUsage()
        return UserUsage(
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
        )

    def reset_usage(self, user_id: str) -> None:
        """Delete the user's key from Redis."""
        self._r.delete(self._key(user_id))

    def all_users(self) -> dict[str, UserUsage]:
        """
        Return usage for all tracked users.
        Uses SCAN (non-blocking) — safe to call on large Redis instances.
        """
        pattern = f"{self._prefix}:*"
        prefix_len = len(self._prefix) + 1   # +1 for the ":"
        result: dict[str, UserUsage] = {}
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=100)
            for key in keys:
                data = self._r.hgetall(key)
                user_id = key[prefix_len:]
                result[user_id] = UserUsage(
                    input_tokens=int(data.get("input_tokens", 0)),
                    output_tokens=int(data.get("output_tokens", 0)),
                )
            if cursor == 0:
                break
        return result

    def ping(self) -> bool:
        """
        Check if Redis is reachable.
        Useful for health checks at app startup.

        Returns:
            ``True`` if Redis responds, ``False`` otherwise.
        """
        try:
            return self._r.ping()
        except Exception as exc:
            logger.warning("RedisStorage ping failed: %s", exc)
            return False
