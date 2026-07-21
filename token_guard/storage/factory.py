"""
storage/factory.py
------------------
StorageFactory — create the right storage backend from a simple
string name or a config dict.

This is the recommended way to configure storage in your application,
especially when the backend should be driven by environment variables
or a config file.

Usage::

    # By name
    store = StorageFactory.create("memory")
    store = StorageFactory.create("sqlite")
    store = StorageFactory.create("redis")
    store = StorageFactory.create("postgres", connection_string="postgresql://...")
    store = StorageFactory.create("dynamodb", table_name="token_guard_usage")

    # From environment variable (TOKEN_GUARD_STORAGE=postgres)
    store = StorageFactory.from_env()

    # From a config dict
    store = StorageFactory.from_config({
        "backend": "postgres",
        "connection_string": "postgresql://user:pass@localhost:5432/mydb",
    })
"""

from __future__ import annotations
import os
from typing import Any, Callable
from token_guard.storage.base import BaseStorage
from token_guard.storage.async_base import AsyncBaseStorage


# Registry: name → callable(**kwargs) -> BaseStorage | AsyncBaseStorage
_REGISTRY: dict[str, Callable[..., BaseStorage | AsyncBaseStorage]] = {}


def _register_defaults() -> None:
    from token_guard.storage.memory import InMemoryStorage
    from token_guard.storage.redis import RedisStorage
    from token_guard.storage.sqlite import SQLiteStorage
    from token_guard.storage.postgres import PostgreSQLStorage, AsyncPostgreSQLStorage
    from token_guard.storage.dynamodb import DynamoDBStorage, AsyncDynamoDBStorage

    from token_guard.storage.async_memory import AsyncInMemoryStorage
    from token_guard.storage.async_redis import AsyncRedisStorage
    from token_guard.storage.async_sqlite import AsyncSQLiteStorage

    _REGISTRY.update({
        "memory":           lambda **kw: InMemoryStorage(),
        "inmemory":         lambda **kw: InMemoryStorage(),
        "redis":            lambda **kw: RedisStorage(**kw),
        "sqlite":           lambda **kw: SQLiteStorage(**kw),
        "postgres":         lambda **kw: PostgreSQLStorage(**kw),
        "postgresql":       lambda **kw: PostgreSQLStorage(**kw),
        "dynamodb":         lambda **kw: DynamoDBStorage(**kw),
        "dynamo":           lambda **kw: DynamoDBStorage(**kw),
        "memory_async":     lambda **kw: AsyncInMemoryStorage(),
        "inmemory_async":   lambda **kw: AsyncInMemoryStorage(),
        "async_memory":     lambda **kw: AsyncInMemoryStorage(),
        "redis_async":      lambda **kw: AsyncRedisStorage(**kw),
        "async_redis":      lambda **kw: AsyncRedisStorage(**kw),
        "sqlite_async":     lambda **kw: AsyncSQLiteStorage(**kw),
        "async_sqlite":     lambda **kw: AsyncSQLiteStorage(**kw),
        "postgres_async":   lambda **kw: AsyncPostgreSQLStorage(**kw),
        "async_postgres":   lambda **kw: AsyncPostgreSQLStorage(**kw),
        "postgresql_async": lambda **kw: AsyncPostgreSQLStorage(**kw),
        "async_postgresql": lambda **kw: AsyncPostgreSQLStorage(**kw),
        "dynamodb_async":   lambda **kw: AsyncDynamoDBStorage(**kw),
        "async_dynamodb":   lambda **kw: AsyncDynamoDBStorage(**kw),
        "dynamo_async":     lambda **kw: AsyncDynamoDBStorage(**kw),
        "async_dynamo":     lambda **kw: AsyncDynamoDBStorage(**kw),
    })


class StorageFactory:
    """
    Factory for creating storage backends by name or config dict.
    """

    @classmethod
    def create(cls, backend: str = "memory", **kwargs: Any) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend by name.
        """
        if not _REGISTRY:
            _register_defaults()

        key = backend.lower().replace("-", "_")
        if key not in _REGISTRY:
            available = ", ".join(sorted(_REGISTRY))
            raise ValueError(
                f"Unknown storage backend '{backend}'. "
                f"Available: {available}. "
                f"Use StorageFactory.register() to add a custom backend."
            )
        return _REGISTRY[key](**kwargs)

    @classmethod
    def register(
        cls,
        name: str,
        factory: Callable[..., BaseStorage | AsyncBaseStorage],
    ) -> None:
        """Register a custom storage backend factory."""
        if not _REGISTRY:
            _register_defaults()
        _REGISTRY[name.lower().replace("-", "_")] = factory

    @classmethod
    def list_backends(cls) -> list[str]:
        """Return a sorted list of registered backend names."""
        if not _REGISTRY:
            _register_defaults()
        return sorted(_REGISTRY.keys())

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> BaseStorage | AsyncBaseStorage:
        """
        Create a Redis or PostgreSQL storage driver directly from a URL.
        """
        async_mode = kwargs.pop("async_mode", False)
        lowered = url.lower()
        if lowered.startswith("postgresql://") or lowered.startswith("postgres://"):
            if async_mode:
                from token_guard.storage.postgres import AsyncPostgreSQLStorage
                return AsyncPostgreSQLStorage.from_url(url, **kwargs)
            from token_guard.storage.postgres import PostgreSQLStorage
            return PostgreSQLStorage.from_url(url, **kwargs)

        if async_mode:
            from token_guard.storage.async_redis import AsyncRedisStorage
            return AsyncRedisStorage.from_url(url, **kwargs)

        from token_guard.storage.redis import RedisStorage
        return RedisStorage.from_url(url, **kwargs)

    @classmethod
    def from_env(
        cls,
        env_var: str = "TOKEN_GUARD_STORAGE",
        redis_url_var: str = "REDIS_URL",
        database_url_var: str = "DATABASE_URL",
        **kwargs: Any,
    ) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend driven by environment variables.
        """
        backend = os.getenv(env_var, "memory").lower().strip()

        if "ttl" not in kwargs:
            raw_ttl = os.getenv("TOKEN_GUARD_TTL")
            if raw_ttl:
                kwargs["ttl"] = int(raw_ttl)

        if "key_prefix" not in kwargs:
            prefix = os.getenv("TOKEN_GUARD_KEY_PREFIX")
            if prefix:
                kwargs["key_prefix"] = prefix

        if backend in ("redis", "redis_async", "async_redis"):
            redis_url = os.getenv(redis_url_var)
            if redis_url:
                kwargs["async_mode"] = "async" in backend
                return cls.from_url(redis_url, **kwargs)

        if backend in ("postgres", "postgresql", "postgres_async", "postgresql_async", "async_postgres", "async_postgresql"):
            db_url = os.getenv(database_url_var)
            if db_url:
                kwargs["async_mode"] = "async" in backend
                return cls.from_url(db_url, **kwargs)

        if backend in ("dynamodb", "dynamo", "dynamodb_async", "dynamo_async", "async_dynamodb", "async_dynamo"):
            if "table_name" not in kwargs and os.getenv("TOKEN_GUARD_TABLE"):
                kwargs["table_name"] = os.getenv("TOKEN_GUARD_TABLE")
            if "region_name" not in kwargs and os.getenv("AWS_REGION"):
                kwargs["region_name"] = os.getenv("AWS_REGION")

        return cls.create(backend, **kwargs)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> BaseStorage | AsyncBaseStorage:
        """
        Create a storage backend from a configuration dictionary.
        """
        cfg = dict(config)
        backend = cfg.pop("backend", "memory").lower()
        if "url" in cfg:
            url = cfg.pop("url")
            cfg["async_mode"] = "async" in backend
            return cls.from_url(url, **cfg)
        return cls.create(backend, **cfg)
